"""文字の視覚的類似度（confusables）。

巨大な事前テーブルを持たず、フォントで各文字をビットマップ描画して ink の
IoU（重なり率）で類似度を求める。結果は lru_cache でキャッシュする。
「速↔遠(0.56)」は高く「永↔高(0.19)」は低い、といった直感に合う値が得られる。
"""
from functools import lru_cache

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except Exception:  # pragma: no cover
    _PIL = False

_FONT = None
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\meiryo.ttc",
    r"C:\Windows\Fonts\YuGothM.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
]
_SIZE = 48
_CANVAS = 56


def _get_font():
    global _FONT
    if _FONT is None and _PIL:
        for path in _FONT_CANDIDATES:
            try:
                _FONT = ImageFont.truetype(path, _SIZE)
                break
            except Exception:
                continue
    return _FONT


@lru_cache(maxsize=8192)
def _ink(ch: str):
    font = _get_font()
    if font is None:
        return None
    im = Image.new("L", (_CANVAS, _CANVAS), 0)
    d = ImageDraw.Draw(im)
    d.text((4, 0), ch, fill=255, font=font)
    a = np.asarray(im, dtype=np.float32)
    return (a > 64).astype(np.float32)


@lru_cache(maxsize=16384)
def similarity(a: str, b: str) -> float:
    """2文字の視覚的類似度 [0,1]（ink の IoU）。同一は1.0。"""
    if a == b:
        return 1.0
    if not _PIL:
        return 0.0
    A, B = _ink(a), _ink(b)
    if A is None or B is None:
        return 0.0
    inter = float((A * B).sum())
    union = float(A.sum() + B.sum() - inter)
    return inter / union if union > 0 else 0.0
