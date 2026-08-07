"""EasyOCR エンジン（旧 ocr_engine.py。フォールバック用に温存）。

既定では未使用。使うには `pip install easyocr` が必要（torch 依存で重い）。
"""
from PySide6.QtGui import QImage

from .base import OCREngine


class EasyOCREngine(OCREngine):
    def __init__(self, langs: list[str] | None = None):
        import numpy as np  # 遅延 import
        import easyocr
        self._np = np
        # 初回実行時にモデルがダウンロードされる
        self.reader = easyocr.Reader(langs or ["ja", "en"])

    def recognize(self, image: QImage) -> str:
        if image is None or image.isNull():
            return ""
        img = image.convertToFormat(QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        # QImage は各行を4バイト境界にパディングするため bytesPerLine >= w*3。
        # ストライドぶんで reshape してから有効幅(w*3)だけ切り出す。
        bpl = img.bytesPerLine()
        buf = bytes(img.constBits())
        arr = self._np.frombuffer(buf, dtype=self._np.uint8).reshape((h, bpl))
        arr = arr[:, : w * 3].reshape((h, w, 3))
        results = self.reader.readtext(arr, detail=0)
        return " ".join(results) if results else ""
