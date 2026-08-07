"""単語バイグラム言語モデル（非LLM・オフライン）。

Tatoeba 日本語コーパスを Sudachi で分割して構築した bigram を読み込み、
文脈（前後の単語）に基づく妥当性スコアを与える。Stupid Backoff で平滑化。
これにより「永満に」→「永遠に」のような、視覚類似では判別できない
文脈依存の誤りを候補の再ランクで救済する。
"""
import gzip
import json
import os
import math
import threading

_DATA = os.path.join(os.path.dirname(__file__), "data", "jp_bigram.json.gz")
BOS, EOS = "<s>", "</s>"
_ALPHA = 0.4          # stupid backoff の割引
_CLAMP = -9.0         # log スコアの下限


class BigramLM:
    def __init__(self, path: str = _DATA):
        self.path = path
        self._uni = {}
        self._bi = {}
        self._total = 1
        self._ready = False
        self._error = None
        self._lock = threading.Lock()

    def ensure_loaded(self) -> bool:
        if self._ready or self._error is not None:
            return self._ready
        with self._lock:
            if self._ready or self._error is not None:
                return self._ready
            try:
                with gzip.open(self.path, "rt", encoding="utf-8") as f:
                    m = json.load(f)
                self._uni = m["uni"]
                self._bi = m["bi"]
                self._total = max(1, m.get("total", 1))
                self._ready = True
            except Exception as e:
                self._error = e
                print(f"[lm] 読み込み失敗: {e}")
        return self._ready

    def _sb(self, w1: str, w2: str) -> float:
        """Stupid Backoff による P(w2|w1) 近似。"""
        b = self._bi.get(f"{w1}\t{w2}")
        if b:
            u1 = self._uni.get(w1, 0)
            if u1:
                return b / u1
        u2 = self._uni.get(w2, 0)
        return _ALPHA * ((u2 + 1) / self._total)

    def _logsb(self, w1: str, w2: str) -> float:
        return max(_CLAMP, math.log(self._sb(w1, w2) + 1e-12))

    def context_score(self, left: str, word: str, right: str) -> float:
        """left, word, right の並びの文脈妥当性（logスコアの和）。大きいほど自然。"""
        if not self.ensure_loaded():
            return 0.0
        return self._logsb(left or BOS, word) + self._logsb(word, right or EOS)


_lm: BigramLM | None = None


def get_lm() -> BigramLM:
    global _lm
    if _lm is None:
        _lm = BigramLM()
    return _lm
