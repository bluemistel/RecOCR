"""デスクトップの矩形キャプチャ（旧 capture_window.py を移植）。

全画面オーバーレイでマウス矩形選択し、選択範囲の QPixmap とグローバル座標を返す。
マルチモニター対応（virtualGeometry を利用）。
"""
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap


class CaptureWindow(QWidget):
    capture_finished = Signal(QRect, QPixmap)  # (グローバル座標, 選択範囲Pixmap)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        desktop = QApplication.primaryScreen()
        geometry = desktop.virtualGeometry()
        self.setGeometry(geometry)
        self.original_pixmap = desktop.grabWindow(
            0, geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )

        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.is_drawing:
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.drawPixmap(rect.topLeft(), self.original_pixmap.copy(rect))
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.end_point = self.start_point
            self.is_drawing = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.end_point = event.pos()
            self.is_drawing = False
            self.update()
            rect = QRect(self.start_point, self.end_point).normalized()
            if rect.width() > 10 and rect.height() > 10:
                captured = self.original_pixmap.copy(rect)
                global_rect = rect.translated(self.geometry().topLeft())
                self.capture_finished.emit(global_rect, captured)
            self.close()


def grab_rect(global_rect: QRect) -> QPixmap:
    """保存済みグローバル座標の矩形を再取得（旧 _capture_specific_rect のロジック）。"""
    screen = QApplication.primaryScreen()
    v_geom = screen.virtualGeometry()
    full = screen.grabWindow(0, v_geom.x(), v_geom.y(), v_geom.width(), v_geom.height())
    local_rect = global_rect.translated(-v_geom.topLeft())
    return full.copy(local_rect)
