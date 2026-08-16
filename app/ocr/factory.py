"""OCR エンジンの生成（名前 → インスタンス）。"""
from .base import OCREngine


def create_engine(name: str, lang: str = "ja") -> OCREngine:
    """name: rapidocr（既定）| windows

    RapidOCR は日本語・英語を1つの多言語モデルで扱うため lang による切替は不要。
    lang は Windows OCR の言語選択にのみ使う。
    """
    name = (name or "rapidocr").lower()
    if name == "windows":
        from .windows_ocr import WindowsOCREngine
        return WindowsOCREngine(lang)
    if name.startswith("rapidocr:"):
        # 例: "rapidocr:medium" でモデルサイズを指定（モデルが同梱されている場合のみ）
        from .rapidocr_engine import RapidOCREngine
        return RapidOCREngine(lang, name.split(":", 1)[1])
    # 既定: RapidOCR（PP-OCR / ONNX Runtime）
    from .rapidocr_engine import RapidOCREngine
    return RapidOCREngine(lang)
