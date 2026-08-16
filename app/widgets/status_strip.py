"""状態表示ストリップ。

「今どういう状態で、次に何をすればいいか」を視線の中心（映像の直下）に集約する。
左に現在のメッセージ、右に前提条件のインジケータ（メディア / 読み取り領域 / モード）
を置き、未達の条件を琥珀で示すことで次の操作が分かるようにする。
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame

from .. import theme


class _Indicator(QLabel):
    """● ラベル形式の状態インジケータ。"""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self._caption = caption
        self.set_state(False, caption)

    def set_state(self, ok: bool, text: str | None = None):
        label = text if text is not None else self._caption
        color = theme.SUCCESS if ok else theme.TEXT_MUTED
        dot = "●" if ok else "○"
        self.setText(f"{dot} {label}")
        self.setStyleSheet(f"color:{color}; font-size:12px;")


class StatusStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        frame = QFrame(self)
        frame.setObjectName("card")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(14)

        # 現在の状態を示す点（メッセージの種類に応じて色を変える）
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{theme.TEXT_DIM}; font-size:11px;")
        lay.addWidget(self.dot)

        self.message = QLabel("待機中")
        self.message.setWordWrap(False)
        self.message.setStyleSheet(
            f"color:{theme.TEXT}; font-size:13px; font-weight:600;")
        lay.addWidget(self.message, 1)

        self.ind_media = _Indicator("メディア")
        self.ind_region = _Indicator("読み取り領域")
        self.mode_label = QLabel("")
        self.mode_label.setStyleSheet(
            f"color:{theme.ACCENT}; font-size:12px; font-weight:700;"
            f" font-family:{theme.FONT_MONO};")
        for w in (self.ind_media, self.ind_region, self.mode_label):
            lay.addWidget(w)

    # --- 更新 API --------------------------------------------------
    def set_message(self, text: str, kind: str = "info"):
        color = {"info": theme.TEXT, "busy": theme.ACCENT,
                 "error": theme.DANGER, "ok": theme.SUCCESS}.get(kind, theme.TEXT)
        dot_color = {"info": theme.TEXT_DIM, "busy": theme.ACCENT,
                     "error": theme.DANGER, "ok": theme.SUCCESS}.get(kind, theme.TEXT_DIM)
        self.message.setText(text)
        self.message.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:600;")
        self.dot.setStyleSheet(f"color:{dot_color}; font-size:11px;")

    def set_media(self, loaded: bool, name: str = ""):
        self.ind_media.set_state(loaded, name or "メディア")

    def set_region(self, has_region: bool, size: str = ""):
        self.ind_region.set_state(has_region, f"領域 {size}" if size else "読み取り領域")

    def set_mode(self, text: str):
        self.mode_label.setText(text)

    def set_indicators_visible(self, visible: bool):
        self.ind_media.setVisible(visible)
        self.ind_region.setVisible(visible)
