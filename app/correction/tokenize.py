"""軽量な日本語分割（Sudachi 非搭載時のフォールバック）。

Sudachi + 辞書は 200MB 超と大きいため、配布物には含めない。
代わりに、校正で既に読み込んでいる語彙（wordfreq の頻度辞書）に対する
最長一致で分割する。形態素解析ほど正確ではないが、
- 複合語かどうかの判定（例: 人口管理 = 人口 + 管理）
- 文脈バイグラムのための前後の語の取得
には十分機能する。

Sudachi が入っていればそちらを優先して使う（精度が高いため）。
"""
import re

_KANA = re.compile(r"[ぁ-んァ-ヴー]")
_MAX_LEN = 6


class SimpleTokenizer:
    """語彙に対する最長一致分割器。"""

    def __init__(self, vocab: dict):
        self._vocab = vocab

    def _is_word(self, s: str) -> bool:
        return self._vocab.get(s, 0.0) > 0

    def tokenize(self, text: str) -> list[str]:
        """文字列を語のリストに分割する（語彙外は1文字ずつ）。"""
        out = []
        i, n = 0, len(text)
        while i < n:
            hit = None
            for length in range(min(_MAX_LEN, n - i), 1, -1):
                cand = text[i:i + length]
                if self._is_word(cand):
                    hit = cand
                    break
            if hit:
                out.append(hit)
                i += len(hit)
            else:
                # 語彙に無い場合、ひらがな/カタカナは連続をまとめる
                j = i
                if _KANA.match(text[i]):
                    while j < n and _KANA.match(text[j]):
                        j += 1
                    out.append(text[i:j])
                    i = j
                else:
                    out.append(text[i])
                    i += 1
        return out

    def split_all_valid(self, text: str) -> bool:
        """text 全体が「2文字以上の有効語」だけに分割できるか。

        『人口管理』のような正当な複合語を誤検出しないために使う。
        """
        toks = self.tokenize(text)
        if len(toks) <= 1:
            return False
        return all(len(t) >= 2 and self._is_word(t) for t in toks)

    def neighbors(self, line: str, start: int, word: str):
        """line 内の位置 start にある word の、左右の隣接語を返す。"""
        toks = self.tokenize(line)
        pos, left, right = 0, None, None
        end = start + len(word)
        for idx, t in enumerate(toks):
            if pos == start:
                left = toks[idx - 1] if idx > 0 else None
            if pos == end:
                right = t
            pos += len(t)
        return left, right
