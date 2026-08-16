"""設定タブ（キャラクター割当・ショートカット・OCRエンジン選択・前処理）。"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QPushButton, QHBoxLayout, QGroupBox, QCheckBox,
                               QScrollArea)
from PySide6.QtCore import Signal, Qt


class SettingsPanel(QWidget):
    settings_saved = Signal()   # 保存後に MainWindow が再設定するためのシグナル

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        # 項目が多いのでスクロール可能にする
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        layout.addWidget(QLabel("デスクトップOCRのショートカット (例: <ctrl>+<alt>+o):"))
        self.shortcut_input = QLineEdit(config.get("shortcut_key", "<ctrl>+<alt>+o"))
        layout.addWidget(self.shortcut_input)

        layout.addWidget(QLabel("OCRエンジン:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("RapidOCR / PP-OCR（推奨・劣化画像に強い）", "rapidocr")
        self.engine_combo.addItem("Windows OCR（最軽量・鮮明な画像向き）", "windows")
        idx = self.engine_combo.findData(config.get("ocr_engine", "rapidocr"))
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)
        layout.addWidget(self.engine_combo)

        hint_engine = QLabel("※ RapidOCR は日本語・英語を1つのモデルで認識します（言語設定は不要）。")
        hint_engine.setWordWrap(True)
        hint_engine.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint_engine)

        layout.addWidget(self._build_preprocess_group())

        self.chk_remove_spaces = QCheckBox("認識結果の半角スペースを除去する")
        self.chk_remove_spaces.setChecked(bool(config.get("remove_spaces", False)))
        layout.addWidget(self.chk_remove_spaces)

        layout.addWidget(QLabel("日本語校正（辞書＋類似字による誤認識の修正）:"))
        self.correction_combo = QComboBox()
        self.correction_combo.addItem("オフ", "off")
        self.correction_combo.addItem("候補提示（非破壊・推奨）", "suggest")
        self.correction_combo.addItem("自動修正（高信頼のみ置換）", "auto")
        ci = self.correction_combo.findData(config.get("correction_mode", "off"))
        if ci >= 0:
            self.correction_combo.setCurrentIndex(ci)
        layout.addWidget(self.correction_combo)

        layout.addWidget(QLabel("キャラクター割り当てキー:"))
        self.char_table = QTableWidget(0, 2)
        self.char_table.setHorizontalHeaderLabels(["キー (1-9)", "名前"])
        self.char_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.char_table)

        btn_row = QHBoxLayout()
        self.btn_add_char = QPushButton("キャラ追加")
        self.btn_add_char.clicked.connect(lambda: self.add_char_row())
        self.btn_del_char = QPushButton("選択行を削除")
        self.btn_del_char.clicked.connect(self._delete_selected_char)
        btn_row.addWidget(self.btn_add_char)
        btn_row.addWidget(self.btn_del_char)
        layout.addLayout(btn_row)

        self.btn_save = QPushButton("設定保存")
        self.btn_save.clicked.connect(self._save)
        layout.addWidget(self.btn_save)

        self._load_characters()

    def _build_preprocess_group(self) -> QGroupBox:
        pre = self.config.get("preprocess") or {}
        box = QGroupBox("OCR前処理（精度優先・速度低下）")
        v = QVBoxLayout(box)

        self.chk_pre_enabled = QCheckBox("前処理を有効にする")
        self.chk_pre_enabled.setChecked(bool(pre.get("enabled", False)))
        v.addWidget(self.chk_pre_enabled)

        up_row = QHBoxLayout()
        up_row.addWidget(QLabel("拡大率:"))
        self.upscale_combo = QComboBox()
        for label, val in [("1倍", 1), ("2倍（推奨）", 2), ("3倍", 3)]:
            self.upscale_combo.addItem(label, val)
        ui = self.upscale_combo.findData(int(pre.get("upscale", 2)))
        if ui >= 0:
            self.upscale_combo.setCurrentIndex(ui)
        up_row.addWidget(self.upscale_combo, 1)
        v.addLayout(up_row)

        self.chk_grayscale = QCheckBox("グレースケール化")
        self.chk_denoise = QCheckBox("ノイズ除去")
        self.chk_contrast = QCheckBox("コントラスト強調 (CLAHE)")
        self.chk_binarize = QCheckBox("二値化 (Otsu)")
        self.chk_invert = QCheckBox("色反転（暗い背景に明るい文字）")
        self.chk_grayscale.setChecked(bool(pre.get("grayscale", True)))
        self.chk_denoise.setChecked(bool(pre.get("denoise", True)))
        self.chk_contrast.setChecked(bool(pre.get("contrast", True)))
        self.chk_binarize.setChecked(bool(pre.get("binarize", False)))
        self.chk_invert.setChecked(bool(pre.get("invert", False)))
        for c in (self.chk_grayscale, self.chk_denoise, self.chk_contrast,
                  self.chk_binarize, self.chk_invert):
            v.addWidget(c)

        self.chk_vote = QCheckBox("多数決OCR（複数条件で認識して統合・低速）")
        self.chk_vote.setChecked(bool(self.config.get("multi_ocr_vote", False)))
        v.addWidget(self.chk_vote)

        hint = QLabel("※ ドットフォントや小さい文字には拡大＋コントラスト強調が有効です。"
                      "二値化は無地背景向け（模様のある背景では逆効果のことがあります）。"
                      "多数決OCRは前処理条件を変えて複数回認識し、辞書尤度と文字多数決で統合します。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        v.addWidget(hint)
        return box

    def _preprocess_from_ui(self) -> dict:
        return {
            "enabled": self.chk_pre_enabled.isChecked(),
            "upscale": int(self.upscale_combo.currentData()),
            "grayscale": self.chk_grayscale.isChecked(),
            "denoise": self.chk_denoise.isChecked(),
            "contrast": self.chk_contrast.isChecked(),
            "binarize": self.chk_binarize.isChecked(),
            "invert": self.chk_invert.isChecked(),
        }

    def add_char_row(self, key: str = "", name: str = ""):
        r = self.char_table.rowCount()
        self.char_table.insertRow(r)
        self.char_table.setItem(r, 0, QTableWidgetItem(key))
        self.char_table.setItem(r, 1, QTableWidgetItem(name))

    def _delete_selected_char(self):
        rows = sorted({i.row() for i in self.char_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.char_table.removeRow(r)

    def _load_characters(self):
        self.char_table.setRowCount(0)
        items = self.config.characters
        if not items:
            items = [{"key": "1", "name": "ずんだもん"}, {"key": "2", "name": "四国めたん"}]
        for char in items:
            self.add_char_row(char.get("key", ""), char.get("name", ""))

    def _save(self):
        self.config.set("shortcut_key", self.shortcut_input.text(), save=False)
        self.config.set("ocr_engine", self.engine_combo.currentData(), save=False)
        self.config.set("preprocess", self._preprocess_from_ui(), save=False)
        self.config.set("multi_ocr_vote", self.chk_vote.isChecked(), save=False)
        self.config.set("remove_spaces", self.chk_remove_spaces.isChecked(), save=False)
        self.config.set("correction_mode", self.correction_combo.currentData(), save=False)
        chars = []
        for r in range(self.char_table.rowCount()):
            key_item = self.char_table.item(r, 0)
            name_item = self.char_table.item(r, 1)
            if key_item and name_item and key_item.text().strip():
                chars.append({"key": key_item.text().strip(),
                              "name": name_item.text().strip()})
        self.config.set("characters", chars, save=True)
        self.settings_saved.emit()
