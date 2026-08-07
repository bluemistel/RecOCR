"""書き起こしテーブル（話者 / テキスト / 時刻 / 削除）。

旧 main.py の add_to_list / setup_speaker_combo / on_delete_row / update_all_comboboxes
を集約し、時刻列（ブックマーク）とプレースホルダ行（連続モード）を追加した。
"""
from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QPushButton, QWidget, QHBoxLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from ..models.transcript_model import TranscriptRow

# 暗い背景でも視認しやすい水色（ブックマーク時刻用）
TIMESTAMP_COLOR = QColor("#4FD6FF")
# 校正候補ありの行のハイライト（明るい琥珀・黒文字で両テーマ可読）
FLAG_BG = QColor("#FFE9A8")

COL_SPEAKER = 0
COL_TEXT = 1
COL_TIME = 2
COL_DELETE = 3

UNSET = "未設定"
PLACEHOLDER = "…認識中"


class TranscriptTable(QTableWidget):
    seek_requested = Signal(int)   # timestamp_ms（時刻セルクリック時）
    content_changed = Signal()     # 追加/編集/削除で発火（自動保存トリガ）

    def __init__(self, characters: list | None = None, parent=None):
        super().__init__(0, 4, parent)
        self._characters = characters or []
        self._suppress_change = False   # 行構築中の itemChanged 抑制
        self.setHorizontalHeaderLabels(["話者", "テキスト", "時刻", "削除"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_SPEAKER, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_SPEAKER, 120)
        header.setSectionResizeMode(COL_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TIME, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_TIME, 90)
        header.setSectionResizeMode(COL_DELETE, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_DELETE, 50)
        self.setWordWrap(True)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.cellClicked.connect(self._on_cell_clicked)
        self.itemChanged.connect(self._on_item_changed)

    # --- 話者コンボ -------------------------------------------------
    def set_characters(self, characters: list) -> None:
        self._characters = characters or []

    def _setup_speaker_combo(self, combo: QComboBox, current_name: str) -> None:
        combo.addItem(UNSET)
        for char in self._characters:
            combo.addItem(char.get("name", ""))
        idx = combo.findText(current_name)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def update_all_comboboxes(self) -> None:
        for row in range(self.rowCount()):
            combo = self.cellWidget(row, COL_SPEAKER)
            if isinstance(combo, QComboBox):
                current = combo.currentText()
                combo.clear()
                self._setup_speaker_combo(combo, current)

    # --- 行追加 -----------------------------------------------------
    def add_row(self, row: TranscriptRow, placeholder: bool = False) -> QTableWidgetItem:
        """1行追加し、テキストセルの QTableWidgetItem を返す。

        placeholder=True なら "…認識中" を灰色表示（後から set_text_for_item で差替）。
        戻り値の item は行の削除やソートを跨いでも有効（連続モードの結果差替に使う）。
        """
        r = self.rowCount()
        self._suppress_change = True
        self.insertRow(r)

        combo = QComboBox()
        self._setup_speaker_combo(combo, row.speaker)
        combo.currentTextChanged.connect(lambda _t: self.content_changed.emit())
        self.setCellWidget(r, COL_SPEAKER, combo)

        text_item = QTableWidgetItem(PLACEHOLDER if placeholder else (row.text or ""))
        if placeholder:
            text_item.setForeground(Qt.GlobalColor.gray)
        self.setItem(r, COL_TEXT, text_item)

        time_item = QTableWidgetItem(TranscriptRow.format_timestamp(row.timestamp_ms))
        time_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if row.timestamp_ms is not None:
            time_item.setData(Qt.ItemDataRole.UserRole, int(row.timestamp_ms))
            time_item.setForeground(TIMESTAMP_COLOR)
            time_item.setToolTip("クリックでこの再生位置へ移動")
        self.setItem(r, COL_TIME, time_item)

        self.setCellWidget(r, COL_DELETE, self._make_delete_widget())
        self.scrollToBottom()
        self._suppress_change = False
        self.content_changed.emit()
        return text_item

    def _on_item_changed(self, _item):
        if not self._suppress_change:
            self.content_changed.emit()

    def current_text_item(self):
        r = self.currentRow()
        return self.item(r, COL_TEXT) if r >= 0 else None

    def set_flag(self, text_item, on: bool):
        """校正候補ありの行を強調（テキストセルの背景）。"""
        if text_item is None:
            return
        try:
            if text_item.tableWidget() is None:
                return
        except RuntimeError:
            return
        self._suppress_change = True
        if on:
            text_item.setBackground(FLAG_BG)
            text_item.setForeground(Qt.GlobalColor.black)
        else:
            text_item.setBackground(QBrush())
            text_item.setForeground(QBrush())
        self._suppress_change = False

    def set_text_for_item(self, text_item: QTableWidgetItem, text: str) -> None:
        """プレースホルダ行のテキストを確定値に差し替える。"""
        if text_item is None:
            return
        # 行が既に削除されていると tableWidget() は None（Qt が item を破棄）
        try:
            if text_item.tableWidget() is None:
                return
        except RuntimeError:
            return
        text_item.setText(text)
        text_item.setForeground(Qt.GlobalColor.black)

    # --- 削除 -------------------------------------------------------
    def _make_delete_widget(self) -> QWidget:
        btn = QPushButton("×")
        btn.setFixedSize(30, 30)
        btn.setStyleSheet("color: red; font-weight: bold;")
        btn.clicked.connect(self._on_delete_clicked)
        wrapper = QWidget()
        lay = QHBoxLayout(wrapper)
        lay.addWidget(btn)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return wrapper

    def _on_delete_clicked(self):
        btn = self.sender()
        if not btn:
            return
        wrapper = btn.parentWidget()
        idx = self.indexAt(wrapper.pos())
        if idx.isValid():
            self.removeRow(idx.row())
            self.content_changed.emit()

    # --- クリック/編集 ---------------------------------------------
    def _on_cell_clicked(self, row: int, col: int):
        if col == COL_TIME:
            item = self.item(row, COL_TIME)
            if item is not None:
                ts = item.data(Qt.ItemDataRole.UserRole)
                if ts is not None:
                    self.seek_requested.emit(int(ts))

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        if item.column() == COL_TEXT:
            self.editItem(item)

    # --- 取り出し ---------------------------------------------------
    def to_rows(self) -> list[TranscriptRow]:
        rows = []
        for r in range(self.rowCount()):
            combo = self.cellWidget(r, COL_SPEAKER)
            speaker = combo.currentText() if isinstance(combo, QComboBox) else UNSET
            text_item = self.item(r, COL_TEXT)
            text = text_item.text() if text_item else ""
            time_item = self.item(r, COL_TIME)
            ts = time_item.data(Qt.ItemDataRole.UserRole) if time_item else None
            rows.append(TranscriptRow(speaker, text, int(ts) if ts is not None else None))
        return rows

    def has_timestamps(self) -> bool:
        for r in range(self.rowCount()):
            time_item = self.item(r, COL_TIME)
            if time_item and time_item.data(Qt.ItemDataRole.UserRole) is not None:
                return True
        return False
