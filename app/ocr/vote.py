"""マルチOCR多数決（複数の前処理条件でOCRし結果を統合）。

劣化画像では後加工より「認識そのもの」を強化するのが有効なことがある。
前処理（拡大率・二値化・反転）を変えて複数回OCRし、
- 同じ長さの結果が多数派なら文字単位の多数決、
- それ以外は「辞書尤度が最大の文字列」を選ぶ。
辞書尤度は wordfreq の頻度辞書（MeCac不要）で概算する。ワーカープロセス内で実行。
"""
import re
from collections import Counter

_KANJI_RUN = re.compile(r"[一-鿿々〆ヶ]{2,}")


def variants(base: dict | None) -> list[dict]:
    """基準の前処理設定から、投票用のバリエーション（最大5）を作る。"""
    b = dict(base or {})
    b["enabled"] = True
    b.setdefault("grayscale", True)
    b.setdefault("denoise", True)
    b.setdefault("contrast", True)
    outs = []
    for up in (2, 3):
        for binz in (False, True):
            v = dict(b); v["upscale"] = up; v["binarize"] = binz
            outs.append(v)
    v = dict(b); v["invert"] = not b.get("invert", False)
    outs.append(v)
    seen, uniq = set(), []
    for v in outs:
        k = tuple(sorted((kk, vv) for kk, vv in v.items()))
        if k not in seen:
            seen.add(k); uniq.append(v)
    return uniq[:5]


def plausibility(text: str, freq: dict) -> float:
    """辞書尤度: 有効な熟語ほど加点、辞書外の漢字連結は減点。"""
    if not text:
        return -1e9
    score = 0.0
    for run in _KANJI_RUN.findall(text):
        f = freq.get(run, 0.0)
        if f > 0:
            score += len(run) * 2.0
        else:
            score -= 1.0
    score += 0.01 * len(text)   # 認識文字数がある程度多い方を微加点
    return score


def combine(strings: list[str], freq: dict) -> str:
    """複数OCR結果を統合して1つの文字列にする。"""
    strings = [s for s in strings if s]
    if not strings:
        return ""
    if len(strings) == 1:
        return strings[0]
    voted = None
    lens = Counter(len(s) for s in strings)
    best_len, cnt = lens.most_common(1)[0]
    if cnt >= 2 and cnt >= len(strings) / 2:
        group = [s for s in strings if len(s) == best_len]
        voted = "".join(Counter(col).most_common(1)[0][0] for col in zip(*group))
    cands = list(dict.fromkeys(strings + ([voted] if voted else [])))
    return max(cands, key=lambda s: plausibility(s, freq))
