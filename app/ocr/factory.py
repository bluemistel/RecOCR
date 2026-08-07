"""OCR エンジンの生成（名前 → インスタンス）。"""
from .base import OCREngine


def create_engine(name: str, lang: str = "ja") -> OCREngine:
    name = (name or "windows").lower()
    if name == "easyocr":
        from .easyocr_engine import EasyOCREngine
        langs = [lang, "en"] if lang != "en" else ["en"]
        return EasyOCREngine(langs)
    # 既定: Windows OCR
    from .windows_ocr import WindowsOCREngine
    return WindowsOCREngine(lang)
