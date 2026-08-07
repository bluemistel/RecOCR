"""Windows OCR（Windows.Media.Ocr）実装。

検証済みの要点:
- SoftwareBitmap.create_copy_from_buffer(buffer, BGRA8, w, h) は **4引数**。
- IBuffer は DataWriter().write_bytes(bytes) -> detach_buffer() で作る。
- QImage(Format_ARGB32) のメモリ配置はリトルエンディアンで BGRA 並び＝そのまま渡せる。
- 日本語は文字間に空白が挿入されるため CJK 隣接の空白を除去する後処理を入れる。
- winrt-Windows.Foundation.Collections パッケージが必要。
"""
import asyncio

from PySide6.QtGui import QImage

from .base import OCREngine

try:
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine as _WinOcrEngine
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat
    from winrt.windows.storage.streams import DataWriter
    _WINRT_OK = True
    _WINRT_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - 環境依存
    _WINRT_OK = False
    _WINRT_IMPORT_ERROR = e


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x3000 <= o <= 0x30FF     # 記号・ひらがな・カタカナ
        or 0x3400 <= o <= 0x4DBF  # 漢字拡張A
        or 0x4E00 <= o <= 0x9FFF  # 漢字
        or 0xFF00 <= o <= 0xFFEF  # 全角英数・半角カナ
    )


def strip_cjk_spaces(text: str) -> str:
    """CJK 文字に隣接する空白を除去（英単語間の空白は保持）。"""
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            prev = text[i - 1] if i > 0 else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if _is_cjk(prev) or _is_cjk(nxt):
                continue  # CJK隣接の空白はスキップ
        out.append(ch)
    return "".join(out)


class WindowsOCREngine(OCREngine):
    """Windows.Media.Ocr を用いた OCR エンジン。"""

    def __init__(self, lang: str = "ja"):
        if not _WINRT_OK:
            raise RuntimeError(f"winrt をインポートできません: {_WINRT_IMPORT_ERROR}")
        self.lang = lang
        self._engine = self._create_engine(lang)
        if self._engine is None:
            raise RuntimeError(
                f"言語 '{lang}' の Windows OCR エンジンを作成できません。"
                "言語パック（基本入力）が未導入の可能性があります。"
            )

    @staticmethod
    def _create_engine(lang: str):
        try:
            eng = _WinOcrEngine.try_create_from_language(Language(lang))
        except Exception:
            eng = None
        if eng is None:
            try:
                eng = _WinOcrEngine.try_create_from_user_profile_languages()
            except Exception:
                eng = None
        return eng

    @staticmethod
    def available_languages() -> list[str]:
        """OCR 利用可能な言語タグ一覧。"""
        if not _WINRT_OK:
            return []
        try:
            return [l.language_tag for l in _WinOcrEngine.available_recognizer_languages]
        except Exception:
            return []

    @staticmethod
    def is_available(lang: str = "ja") -> bool:
        if not _WINRT_OK:
            return False
        try:
            return bool(_WinOcrEngine.is_language_supported(Language(lang)))
        except Exception:
            return False

    def _to_software_bitmap(self, image: QImage):
        img = image.convertToFormat(QImage.Format.Format_ARGB32)
        w, h = img.width(), img.height()
        ptr = img.constBits()          # memoryview（BGRA 並び）
        data = bytes(ptr)              # w*h*4 バイト
        writer = DataWriter()
        writer.write_bytes(data)
        ibuf = writer.detach_buffer()
        return SoftwareBitmap.create_copy_from_buffer(ibuf, BitmapPixelFormat.BGRA8, w, h)

    def recognize(self, image: QImage) -> str:
        if image is None or image.isNull():
            return ""
        sb = self._to_software_bitmap(image)

        async def _run():
            return await self._engine.recognize_async(sb)

        result = asyncio.run(_run())
        text = getattr(result, "text", None)
        if text is None:
            text = " ".join(line.text for line in result.lines)
        return strip_cjk_spaces(text).strip()
