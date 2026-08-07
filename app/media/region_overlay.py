"""動画/画像表示の上に重ねる矩形選択オーバーレイ。

旧 capture_window.py の paintEvent / mouse* を流用。ただし背景 grab は行わず
（下に動画/画像ウィジェットがある）、透過してマウス選択矩形のみを描く。
座標は自ウィジェット相対（＝直下の表示ウィジェットと同座標系）。
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen


class RegionOverlay(QWidget):
    region_selected = Signal(QRect)   # 確定した矩形（ウィジェット座標）
    region_cleared = Signal()         # クリック（ドラッグ無し）で領域を解除

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        # 子ウィジェットを半透明背景にして、塗らない画素は下の映像を透過表示する。
        # （これを設定しないと未描画画素が黒になり、読み取り領域が塗り潰されて見える）
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._region: QRect | None = None
        self._start = QPoint()
        self._end = QPoint()
        self._drawing = False

    def set_region(self, rect: QRect | None):
        self._region = rect
        self.update()

    def region(self) -> QRect | None:
        return self._region

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = None
        if self._drawing:
            rect = QRect(self._start, self._end).normalized()
        elif self._region is not None:
            rect = self._region
        if rect is None or rect.width() <= 0 or rect.height() <= 0:
            return
        # 読み取り領域は一切塗らない（＝下の映像がそのまま見える）。
        # 領域の外側だけを薄暗くして焦点を示し、領域の枠は赤い輪郭線のみで描く。
        full = self.rect()
        dim = QColor(0, 0, 0, 70)
        r = rect.intersected(full)
        # 領域外を上下左右の4矩形に分けて暗転（領域内には決してかからない）
        painter.fillRect(QRect(full.left(), full.top(), full.width(), r.top() - full.top()), dim)
        painter.fillRect(QRect(full.left(), r.bottom() + 1, full.width(), full.bottom() - r.bottom()), dim)
        painter.fillRect(QRect(full.left(), r.top(), r.left() - full.left(), r.height()), dim)
        painter.fillRect(QRect(r.right() + 1, r.top(), full.right() - r.right(), r.height()), dim)
        # 赤い輪郭線
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self._drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._end = event.position().toPoint()
            self._drawing = False
            rect = QRect(self._start, self._end).normalized()
            if rect.width() > 5 and rect.height() > 5:
                # 有効なドラッグ → 領域を確定
                self._region = rect
                self.region_selected.emit(rect)
            else:
                # ドラッグではなくクリック → 領域選択をキャンセル（解除）
                self._region = None
                self.region_cleared.emit()
            self.update()
