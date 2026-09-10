"""設定タブ（キャラクター割当・ショートカット・OCRエンジン選択・前処理）。"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QPushButton, QHBoxLayout, QGroupBox, QCheckBox,
                               QScrollArea)
from PySide6.QtCore import Signal, Qt

from .. import theme
from .collapsible import CollapsibleSection


class SettingsPanel(QWidget):
    settings_saved = Signal()   # 保存後に MainWindow が再設定するためのシグナル

    @staticmethod
    def _hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{theme.TEXT_MUTED}; font-size:11px;")
        return lbl

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{theme.TEXT_DIM}; font-size:12px; font-weight:600;")
        return lbl

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._dirty = False
        self._loading = True   # 初期化中の変更を dirty 扱いしない

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

        layout.setSpacing(10)

        # --- 0. ホットキー（先頭に配置） ---
        hk = QGroupBox("ホットキー")
        hk_l = QVBoxLayout(hk)
        hk_l.setSpacing(6)
        hk_l.addWidget(self._label("デスクトップ切り取り"))
        self.shortcut_input = QLineEdit(config.get("shortcut_key", "<ctrl>+<alt>+o"))
        hk_l.addWidget(self.shortcut_input)
        hk_l.addWidget(self._hint("例: <ctrl>+<alt>+o （pynput 形式）"))
        layout.addWidget(hk)

        # --- 1. 話者 ---
        spk = QGroupBox("話者キー")
        spk_l = QVBoxLayout(spk)
        spk_l.setSpacing(6)
        spk_l.addWidget(self._hint("1〜9 のキーに話者名を割り当てます。ここで設定した内容が"
                                   "映像の下にチップとして表示されます。"))
        self.char_table = QTableWidget(0, 2)
        self.char_table.setHorizontalHeaderLabels(["キー", "話者名"])
        self.char_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.char_table.setColumnWidth(0, 56)
        self.char_table.verticalHeader().setVisible(False)
        self.char_table.setMinimumHeight(160)
        spk_l.addWidget(self.char_table)
        # プリセット指定は分かりにくい機能なので、入力欄のすぐ下で説明する
        spk_l.addWidget(self._hint(
            "話者名を「話者名,プリセット名」のように半角カンマで区切ると、"
            "カンマ以降をプリセット名として扱い、CSV / TXT の3列目に書き出します。"
            "一部の合成音声ソフトが3列目を、その話者に対する声の種類（プリセット）"
            "として読み込むための機能です。"))
        spk_l.addWidget(self._hint(
            "例）  紲星 あかり,ノーマル  →  「紲星 あかり」「台詞」「ノーマル」の3列で出力されます。"
            "同じ話者の声を使い分けたい場合は、"
            "「あかり,ノーマル」「あかり,ささやき」のように別のキーへ登録してください"
            "（アプリ側では同一話者かどうかを判定しません）。"))
        btn_row = QHBoxLayout()
        self.btn_add_char = QPushButton("＋ 話者を追加")
        self.btn_add_char.clicked.connect(lambda: self.add_char_row())
        self.btn_del_char = QPushButton("選択行を削除")
        self.btn_del_char.clicked.connect(self._delete_selected_char)
        btn_row.addWidget(self.btn_add_char)
        btn_row.addWidget(self.btn_del_char)
        spk_l.addLayout(btn_row)
        layout.addWidget(spk)

        # --- 2. OCR ---
        ocr = QGroupBox("OCR")
        ocr_l = QVBoxLayout(ocr)
        ocr_l.setSpacing(6)
        ocr_l.addWidget(self._label("認識エンジン"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("RapidOCR / PP-OCR（推奨・劣化画像に強い）", "rapidocr")
        self.engine_combo.addItem("Windows OCR（最軽量・鮮明な画像向き）", "windows")
        idx = self.engine_combo.findData(config.get("ocr_engine", "rapidocr"))
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)
        ocr_l.addWidget(self.engine_combo)
        ocr_l.addWidget(self._hint(
            "RapidOCR は日本語・英語を1つのモデルで認識するため言語設定は不要です。"))
        self.chk_remove_spaces = QCheckBox("認識結果の半角スペースを除去する")
        self.chk_remove_spaces.setChecked(bool(config.get("remove_spaces", False)))
        ocr_l.addWidget(self.chk_remove_spaces)
        layout.addWidget(ocr)

        # --- 3. 前処理（既定では畳んでおく。無くても実用上ほぼ問題ないため） ---
        self.sec_preprocess = CollapsibleSection(
            "OCR前処理（精度優先・速度低下）",
            expanded=bool(config.get("ui_expand_preprocess", False)))
        self._fill_preprocess(self.sec_preprocess.body_layout())
        layout.addWidget(self.sec_preprocess)

        # --- 4. 校正（同上） ---
        self.sec_correction = CollapsibleSection(
            "日本語校正",
            expanded=bool(config.get("ui_expand_correction", False)))
        corr_l = self.sec_correction.body_layout()
        corr_l.addWidget(self._hint(
            "辞書・類似字・文脈から「永速→永遠」のような誤認識を見つけます。"))
        self.correction_combo = QComboBox()
        self.correction_combo.addItem("オフ", "off")
        self.correction_combo.addItem("候補提示（非破壊・推奨）", "suggest")
        self.correction_combo.addItem("自動修正（高信頼のみ置換）", "auto")
        ci = self.correction_combo.findData(config.get("correction_mode", "off"))
        if ci >= 0:
            self.correction_combo.setCurrentIndex(ci)
        corr_l.addWidget(self.correction_combo)
        layout.addWidget(self.sec_correction)

        # 折りたたみ状態を覚えておく
        self.sec_preprocess.toggled.connect(
            lambda v: self.config.set("ui_expand_preprocess", v))
        self.sec_correction.toggled.connect(
            lambda v: self.config.set("ui_expand_correction", v))

        layout.addStretch()

        self.btn_save = QPushButton("設定を保存")
        self.btn_save.setMinimumHeight(42)
        self.btn_save.clicked.connect(self._save)
        outer.addWidget(self.btn_save)   # スクロールの外に固定して常に押せるように

        self._load_characters()
        # 変更があったときだけ保存ボタンを強調する（押し時が分かるように）
        self._loading = False
        self._connect_dirty_watchers()
        self._set_dirty(False)

    def _fill_preprocess(self, target_layout) -> None:
        pre = self.config.get("preprocess") or {}
        v = target_layout

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
        hint.setStyleSheet(f"color:{theme.TEXT_MUTED}; font-size: 11px;")
        v.addWidget(hint)

    # --- 未保存の変更を追跡して保存ボタンを強調する -------------------
    def _connect_dirty_watchers(self):
        mark = self._mark_dirty
        self.shortcut_input.textChanged.connect(lambda *_: mark())
        for combo in (self.engine_combo, self.correction_combo, self.upscale_combo):
            combo.currentIndexChanged.connect(lambda *_: mark())
        for chk in (self.chk_remove_spaces, self.chk_pre_enabled, self.chk_grayscale,
                    self.chk_denoise, self.chk_contrast, self.chk_binarize,
                    self.chk_invert, self.chk_vote):
            chk.toggled.connect(lambda *_: mark())
        self.char_table.itemChanged.connect(lambda *_: mark())
        self.char_table.model().rowsInserted.connect(lambda *_: mark())
        self.char_table.model().rowsRemoved.connect(lambda *_: mark())

    def _mark_dirty(self):
        if not self._loading:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool):
        self._dirty = dirty
        self.btn_save.setProperty("accent", dirty)
        self.btn_save.setText("設定を保存 ●" if dirty else "設定を保存")
        self.btn_save.setToolTip("未保存の変更があります" if dirty else "変更はありません")
        # プロパティ変更を反映させるためスタイルを再適用する
        self.btn_save.style().unpolish(self.btn_save)
        self.btn_save.style().polish(self.btn_save)

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
        self._set_dirty(False)      # 保存済みなのでハイライトを消す
        self.settings_saved.emit()
