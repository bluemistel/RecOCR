"""折りたたみ可能なセクション。

設定項目が増えて縦に長くなったため、普段触らない項目（前処理・校正など）を
畳んでおけるようにする。見出しをクリックで開閉し、開閉状態は呼び出し側が
config に保存できるよう toggled シグナルで通知する。
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QFrame
from PySide6.QtCore import Qt, Signal

from .. import theme


class CollapsibleSection(QWidget):
    toggled = Signal(bool)   # True=開いている

    def __init__(self, title: str, expanded: bool = False, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._button = QToolButton()
        self._button.setText(title)
        self._button.setCheckable(True)
        self._button.setChecked(expanded)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._button.setStyleSheet(
            f"QToolButton {{ background:{theme.BG_PANEL}; color:{theme.TEXT_DIM};"
            f" border:1px solid {theme.BORDER}; border-radius:8px;"
            f" padding:8px 10px; font-weight:600; text-align:left; }}"
            f"QToolButton:hover {{ color:{theme.TEXT}; border-color:{theme.ACCENT_DIM}; }}"
            f"QToolButton:checked {{ color:{theme.ACCENT};"
            f" border-bottom-left-radius:0; border-bottom-right-radius:0; }}")
        self._button.clicked.connect(self._on_clicked)
        root.addWidget(self._button)

        self._body = QFrame()
        self._body.setObjectName("collapseBody")
        self._body.setStyleSheet(
            f"QFrame#collapseBody {{ background:{theme.BG_PANEL};"
            f" border:1px solid {theme.BORDER}; border-top:none;"
            f" border-bottom-left-radius:8px; border-bottom-right-radius:8px; }}")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(10, 8, 10, 10)
        self._body_layout.setSpacing(6)
        self._body.setVisible(expanded)
        root.addWidget(self._body)

    def _on_clicked(self):
        expanded = self._button.isChecked()
        self._body.setVisible(expanded)
        self._button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggled.emit(expanded)

    def set_expanded(self, expanded: bool):
        self._button.setChecked(expanded)
        self._on_clicked()

    def is_expanded(self) -> bool:
        return self._button.isChecked()

    def add_widget(self, w: QWidget):
        self._body_layout.addWidget(w)

    def add_layout(self, lay):
        self._body_layout.addLayout(lay)

    def body_layout(self):
        return self._body_layout
