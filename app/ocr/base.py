"""OCR エンジンの差し替え可能インターフェース。

契約: recognize(image: QImage) -> str
別プロセス受け渡し用に recognize_png_bytes(bytes) -> str も提供する
（QImage / QPixmap はプロセス間で pickle 不可のため PNG バイト列で渡す）。
"""
from abc import ABC, abstractmethod

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage


def qimage_to_png_bytes(image: QImage) -> bytes:
    """QImage を PNG バイト列へ（別プロセスへ渡す運搬形式）。"""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def png_bytes_to_qimage(data: bytes) -> QImage:
    image = QImage()
    image.loadFromData(data, "PNG")
    return image


class OCREngine(ABC):
    """全 OCR エンジンの基底。"""

    @abstractmethod
    def recognize(self, image: QImage) -> str:
        """画像から1本のテキストを返す。"""

    def recognize_png_bytes(self, data: bytes) -> str:
        """PNG バイト列から認識。既定は QImage 化して recognize に委譲。"""
        return self.recognize(png_bytes_to_qimage(data))
