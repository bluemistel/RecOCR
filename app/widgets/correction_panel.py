"""校正候補パネル（非破壊）。

選択中の行の疑わしい熟語について、修正候補をボタンで提示する。
ボタンを押すと candidate_chosen(text_item, start, end, word) を emit し、
MainWindow が該当行のテキストの該当スパンを置換する。
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame)
from PySide6.QtCore import Signal, Qt


class CorrectionPanel(QWidget):
    candidate_chosen = Signal(object, int, int, str)  # (text_item, start, end, word)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        self._title = QLabel("修正候補")
        self._title.setStyleSheet("font-weight: bold;")
        root.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._inner = QWidget()
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

        self._current_item = None
        self.clear("行を選択すると修正候補を表示します。")

    def clear(self, message: str | None = None):
        while self._vbox.count():
            w = self._vbox.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        if message:
            lbl = QLabel(message)
            lbl.setStyleSheet("color: gray;")
            lbl.setWordWrap(True)
            self._vbox.addWidget(lbl)

    def show_for(self, text_item, suggestions: list):
        """text_item の行の suggestions を表示。"""
        self._current_item = text_item
        self.clear()
        if not suggestions:
            self.clear("この行に修正候補はありません。")
            return
        for s in suggestions:
            row = QFrame()
            row.setFrameShape(QFrame.Shape.StyledPanel)
            rl = QVBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)
            head = QLabel(f"『{s.original}』 の候補:")
            rl.addWidget(head)
            btn_row = QHBoxLayout()
            btn_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for word, score, dist in s.candidates:
                b = QPushButton(word)
                b.setToolTip(f"スコア {score} / 編集距離 {dist}")
                b.clicked.connect(
                    lambda _c=False, st=s.start, en=s.end, w=word:
                    self.candidate_chosen.emit(self._current_item, st, en, w))
                btn_row.addWidget(b)
            rl.addLayout(btn_row)
            self._vbox.addWidget(row)
