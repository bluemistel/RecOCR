"""話者キーバー（1〜9 の割り当てを常時表示する）。

このアプリの中心操作は「1〜9 キーを押して話者を決めながら読み取る」ことなので、
どのキーが誰に割り当たっているかが常に見えている必要がある。
映像の直下に置き、キーを押した瞬間に該当チップを光らせて対応を示す。
チップはクリックでも同じ動作を行う（キーボードを使わない操作にも対応）。
"""
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                               QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer

from .. import theme
from ..models.transcript_model import TranscriptRow


class SpeakerChip(QPushButton):
    """1つのキー割り当てを表すチップ。"""

    def __init__(self, key: str, name: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.name = name
        # 「話者名,プリセット名」形式なら、チップ上では分けて見せる
        display_name, preset = TranscriptRow.split_speaker(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)          # クリックしやすい高さ
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tip = f"{key} キー → {display_name}"
        if preset:
            tip += f"（プリセット: {preset}）"
        self.setToolTip(tip + " / クリックでも読み取れます")
        self._flash = QTimer(self)
        self._flash.setSingleShot(True)
        self._flash.setInterval(320)
        self._flash.timeout.connect(self._restore)
        self._apply(active=False)
        label = f"  {key}   {display_name}"
        if preset:
            label += f" / {preset}"
        self.setText(label + "  ")

    def _apply(self, active: bool):
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.ACCENT}; color:{theme.ACCENT_TEXT};"
                f" border:1px solid {theme.ACCENT}; border-radius:8px;"
                f" font-weight:700; text-align:left; padding:4px 10px; }}")
        else:
            self.setStyleSheet(
                f"QPushButton {{ background:{theme.BG_ELEVATED}; color:{theme.TEXT};"
                f" border:1px solid {theme.BORDER_STRONG}; border-radius:8px;"
                f" text-align:left; padding:4px 10px; }}"
                f"QPushButton:hover {{ background:{theme.BG_HOVER};"
                f" border-color:{theme.ACCENT_DIM}; }}")

    def flash(self):
        """キー押下時に一瞬光らせる。"""
        self._apply(active=True)
        self._flash.start()

    def _restore(self):
        self._apply(active=False)


class SpeakerBar(QWidget):
    """割り当て済みの話者キーを横に並べて表示する。"""

    speaker_triggered = Signal(str)   # 押された/クリックされたキー("1"〜"9")

    def __init__(self, characters: list | None = None, parent=None):
        super().__init__(parent)
        self._chips: dict[str, SpeakerChip] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._caption = QLabel("話者キー")
        self._caption.setStyleSheet(
            f"color:{theme.TEXT_MUTED}; font-size:11px; letter-spacing:1px;")
        root.addWidget(self._caption)

        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)
        root.addLayout(self._row)

        self.set_characters(characters or [])

    def set_characters(self, characters: list):
        """設定変更に追従してチップを作り直す。"""
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._chips.clear()

        valid = [c for c in (characters or [])
                 if c.get("key", "").strip() and c.get("name", "").strip()]
        if not valid:
            hint = QLabel("話者が未設定です — 「設定」タブで 1〜9 キーに名前を割り当ててください")
            hint.setStyleSheet(f"color:{theme.WARN}; font-size:12px;")
            self._row.addWidget(hint)
            self._row.addStretch()
            return

        for char in sorted(valid, key=lambda c: c["key"]):
            chip = SpeakerChip(char["key"], char["name"])
            chip.clicked.connect(lambda _c=False, k=char["key"]: self.speaker_triggered.emit(k))
            self._row.addWidget(chip)
            self._chips[char["key"]] = chip
        self._row.addStretch()

    def flash(self, key: str):
        """該当キーのチップを光らせる（キー押下のフィードバック）。"""
        chip = self._chips.get(key)
        if chip is not None:
            chip.flash()

    def has_key(self, key: str) -> bool:
        return key in self._chips
