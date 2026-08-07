"""日本語OCR結果の校正（非LLM）。

方針:
- 有効語辞書（wordfreq の頻度辞書）＋ 編集距離（RapidFuzz）＋ 視覚類似字（visual）。
- 検査対象は「漢字の連なり（熟語）」で、辞書に存在しない（頻度0）ものだけ。
  → 正しい語（例: 職務）は触らない＝過剰修正を防ぐ。
- Sudachi で「有効な複合語の連結（例: 人口管理＝人口＋管理）」を誤検出しないよう除外。
- 候補は同じ長さ・編集距離1〜2に限定し、頻度＋視覚類似で再ランク。

一致率の限界: 「満↔遠」のように視覚的に離れた誤りは文脈（n-gram/LM）が必要で、
候補上位には出るが自動確定は外すことがある。→ 非破壊の候補提示と併用する。
"""
import re
import threading
from dataclasses import dataclass, field
from math import log10

from . import visual
from . import lm

_KANJI_RUN = re.compile(r"[一-鿿々〆ヶ]{2,6}")

# スコア重み・しきい値（PoCで調整）
FREQ_W = 1.0
VIS_W = 1.2
CTX_W = 0.15            # 文脈（バイグラム）の再ランク重み
DIST_PENALTY = 0.5
MIN_FREQ = 1e-6          # これ未満の頻度の候補は採用しない
SUGGEST_SCORE = 0.60     # これ未満なら候補として出さない
AUTO_SCORE = 0.85        # 自動修正で置換する最小スコア
MAX_EDIT = 2
CTX_RERANK_TOPK = 8      # 文脈再ランクの対象候補数


@dataclass
class Suggestion:
    start: int
    end: int
    original: str
    candidates: list = field(default_factory=list)  # [(word, score, dist)]

    @property
    def best(self):
        return self.candidates[0][0] if self.candidates else None

    @property
    def best_score(self):
        return self.candidates[0][1] if self.candidates else 0.0


class Corrector:
    def __init__(self, lang: str = "ja"):
        self.lang = lang
        self._ready = False
        self._error = None
        self._freq = {}
        self._pool_by_len = {}
        self._tok = None
        self._mode = None
        self._rf = None
        self._lm = lm.get_lm()
        self._lock = threading.Lock()

    # --- 遅延初期化（辞書ロードは重いので初回のみ） -------------------
    def ensure_loaded(self) -> bool:
        if self._ready or self._error is not None:
            return self._ready
        with self._lock:
            if self._ready or self._error is not None:
                return self._ready
            return self._load()

    def _load(self) -> bool:
        try:
            from wordfreq import get_frequency_dict
            from rapidfuzz import process, distance
            self._rf = (process, distance)
            self._freq = get_frequency_dict(self.lang)
            buckets: dict[int, list] = {}
            for w in self._freq:
                if 2 <= len(w) <= 6 and _KANJI_RUN.fullmatch(w):
                    buckets.setdefault(len(w), []).append(w)
            self._pool_by_len = buckets
            # Sudachi（任意。無ければ複合語の除外チェックを省略）
            try:
                from sudachipy import dictionary, tokenizer
                self._tok = dictionary.Dictionary(dict="core").create()
                self._mode = tokenizer.Tokenizer.SplitMode.C
            except Exception as e:
                print(f"[correction] Sudachi 無効（頻度のみで動作）: {e}")
                self._tok = None
            self._ready = True
        except Exception as e:
            self._error = e
            print(f"[correction] 初期化失敗: {e}")
        return self._ready

    def _freq_of(self, w: str) -> float:
        return self._freq.get(w, 0.0)

    def _is_valid_compound(self, run: str) -> bool:
        """Sudachi で全て『長さ2以上の有効語』に分割できるなら正当な複合とみなす。"""
        if self._tok is None:
            return False
        try:
            toks = self._tok.tokenize(run, self._mode)
        except Exception:
            return False
        if len(toks) <= 1:
            return False
        return all(len(m.surface()) >= 2 and self._freq_of(m.surface()) > 0 for m in toks)

    @staticmethod
    def _freq_score(freq: float) -> float:
        if freq <= 0:
            return 0.0
        return max(0.0, min(1.0, (log10(freq) + 9.0) / 8.0))

    def _visual_score(self, a: str, b: str) -> float:
        """同じ長さの a,b について、異なる位置の視覚類似度の平均。"""
        diffs = [(a[i], b[i]) for i in range(len(a)) if a[i] != b[i]]
        if not diffs:
            return 1.0
        return sum(visual.similarity(x, y) for x, y in diffs) / len(diffs)

    def _candidates_for(self, run: str):
        process, distance = self._rf
        pool = self._pool_by_len.get(len(run))
        if not pool:
            return []
        raw = process.extract(
            run, pool,
            scorer=distance.DamerauLevenshtein.normalized_similarity,
            limit=40, processor=None)
        scored = []
        for cand, _s, _ in raw:
            if len(cand) != len(run) or cand == run:
                continue
            d = distance.DamerauLevenshtein.distance(run, cand)
            if d < 1 or d > MAX_EDIT:
                continue
            f = self._freq_of(cand)
            if f < MIN_FREQ:
                continue
            vis = self._visual_score(run, cand)
            score = (FREQ_W * self._freq_score(f) + VIS_W * vis
                     - DIST_PENALTY * (d - 1))
            scored.append((cand, round(score, 4), d))
        scored.sort(key=lambda x: -x[1])
        return scored

    def _neighbors(self, line: str, start: int, cand: str):
        """置換後の文での左右の隣接語を返す（Sudachi・文脈スコア用）。"""
        if self._tok is None:
            return None, None
        lp = line[:start] + cand + line[start + len(cand):]
        try:
            toks = list(self._tok.tokenize(lp, self._mode))
        except Exception:
            return None, None
        left, right = None, None
        end = start + len(cand)
        for i, m in enumerate(toks):
            if m.begin() == start:
                left = toks[i - 1].surface() if i > 0 else None
            if m.begin() == end:
                right = m.surface()
        return left, right

    def _context_rerank(self, line: str, start: int, cands: list) -> list:
        """上位候補を文脈（バイグラム）で再ランク。base_score は表示用に保持。"""
        if not cands or not self._lm.ensure_loaded():
            return cands
        head = cands[:CTX_RERANK_TOPK]
        rest = cands[CTX_RERANK_TOPK:]
        scored = []
        for cand, base, dist in head:
            left, right = self._neighbors(line, start, cand)
            ctx = self._lm.context_score(left, cand, right)
            total = base + CTX_W * ctx
            scored.append((total, (cand, base, dist)))
        scored.sort(key=lambda x: -x[0])
        return [t for _tot, t in scored] + rest

    def correct_line(self, text: str) -> list[Suggestion]:
        """1行を解析し、疑わしい熟語の修正候補（Suggestion）一覧を返す。"""
        if not text or not self.ensure_loaded():
            return []
        suggestions = []
        for m in _KANJI_RUN.finditer(text):
            run = m.group()
            if self._freq_of(run) > 0:          # 辞書にある＝正しい語 → 触らない
                continue
            if self._is_valid_compound(run):    # 有効語の連結 → スキップ
                continue
            cands = self._candidates_for(run)
            cands = [c for c in cands if c[1] >= SUGGEST_SCORE]
            if not cands:
                continue
            cands = self._context_rerank(text, m.start(), cands)  # 文脈で再ランク
            suggestions.append(Suggestion(m.start(), m.end(), run, cands[:5]))
        return suggestions

    def apply_best(self, text: str, suggestions=None, threshold: float = AUTO_SCORE) -> str:
        """自動修正: しきい値以上の最良候補で置換した文字列を返す。"""
        if suggestions is None:
            suggestions = self.correct_line(text)
        # 右から置換してオフセットのズレを防ぐ
        out = text
        for s in sorted(suggestions, key=lambda x: -x.start):
            if s.best and s.best_score >= threshold:
                out = out[:s.start] + s.best + out[s.end:]
        return out


# アプリ内で使い回すシングルトン
_corrector: Corrector | None = None


def get_corrector(lang: str = "ja") -> Corrector:
    global _corrector
    if _corrector is None or _corrector.lang != lang:
        _corrector = Corrector(lang)
    return _corrector
