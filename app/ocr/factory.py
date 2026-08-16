"""OCR エンジンの生成（名前 → インスタンス）。"""
from .base import OCREngine


def create_engine(name: str, lang: str = "ja") -> OCREngine:
    name = (name or "windows").lower()
    if name == "easyocr":
        from .easyocr_engine import EasyOCREngine
        langs = [lang, "en"] if lang != "en" else ["en"]
        return EasyOCREngine(langs)
    if name in ("rapidocr", "paddle", "paddleocr"):
        from .rapidocr_engine import RapidOCREngine
        return RapidOCREngine(lang)
    if name.startswith("rapidocr:"):
        # 例: "rapidocr:medium" でモデルサイズを指定
        from .rapidocr_engine import RapidOCREngine
        return RapidOCREngine(lang, name.split(":", 1)[1])
    # 既定: Windows OCR
    from .windows_ocr import WindowsOCREngine
    return WindowsOCREngine(lang)
