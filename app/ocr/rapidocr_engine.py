"""RapidOCR エンジン（PaddleOCR の PP-OCR モデルを ONNX Runtime で実行）。

PaddleOCR 本家（paddlepaddle）は Python 3.14 向けの配布が無いため、
同じ PP-OCR モデルを ONNX 化した RapidOCR を用いる。torch 不要で軽量。

ベンチマークでは、ディザ・低解像度のゲーム字幕のような劣化画像で
Windows OCR より大幅に高精度（CER 0.123 → 0.017）だった。
一方、綺麗な画像では末尾の句点を落とすことがある。
"""
import io

from PySide6.QtGui import QImage

from .base import OCREngine

# 認識モデルの大きさ。SMALL が既定（速度と精度のバランスが良い）
_MODEL_TYPES = ("small", "medium", "mobile", "server", "tiny")


class RapidOCREngine(OCREngine):
    def __init__(self, lang: str = "ja", model_type: str = "small"):
        import numpy as np  # 遅延 import
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import LangRec, ModelType
        self._np = np

        lang_rec = LangRec.JAPAN if lang == "ja" else LangRec.EN
        mt = getattr(ModelType, (model_type or "small").upper(), ModelType.SMALL)
        params = {"Rec.lang_type": lang_rec, "Rec.model_type": mt}
        try:
            self._engine = RapidOCR(params=params)
        except Exception:
            # 指定モデルが入手できない場合は既定にフォールバック
            self._engine = RapidOCR(params={"Rec.lang_type": lang_rec})

    # --- 内部 -------------------------------------------------------
    def _recognize_array(self, arr) -> str:
        result = self._engine(arr)
        txts = getattr(result, "txts", None)
        if not txts:
            return ""
        return "".join(t for t in txts if t)

    # --- OCREngine 実装 --------------------------------------------
    def recognize(self, image: QImage) -> str:
        if image is None or image.isNull():
            return ""
        img = image.convertToFormat(QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        # QImage は行を4バイト境界にパディングするためストライドを考慮する
        bpl = img.bytesPerLine()
        buf = bytes(img.constBits())
        arr = self._np.frombuffer(buf, dtype=self._np.uint8).reshape((h, bpl))
        arr = arr[:, : w * 3].reshape((h, w, 3))
        return self._recognize_array(arr)

    def recognize_png_bytes(self, data: bytes) -> str:
        """PNG バイト列から直接認識（Qt を経由しないぶん軽い）。"""
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data)).convert("RGB")
            return self._recognize_array(self._np.array(im))
        except Exception:
            return super().recognize_png_bytes(data)

    @staticmethod
    def is_available() -> bool:
        import importlib.util
        return importlib.util.find_spec("rapidocr") is not None
