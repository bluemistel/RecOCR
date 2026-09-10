"""RecoOCR メインウィンドウ（旧 main.py の MainWindow を分割・拡張）。

- 入力ソース: デスクトップOCR / メディア（画像・動画）を切替。
- メディアの読み取り: 通常（都度確認）/ 連続（キュー・別プロセス）。
- OCR は常に別プロセス（OcrDispatcher）で実行し UI をブロックしない。
- 動画モードは取り込み時の再生位置を各行に記録（ブックマーク）。
"""
import os
import json

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QGroupBox, QRadioButton,
                               QButtonGroup, QTabWidget, QFileDialog, QMessageBox,
                               QLineEdit, QApplication, QSplitter)
from PySide6.QtCore import Qt, QRect, Signal, QObject, QTimer, QEvent
from PySide6.QtGui import QImage

from pynput import keyboard

from . import theme
from . import project
from .project import Project
from .config_manager import ConfigManager
from .paths import data_dir
from .capture.desktop_capture import CaptureWindow, grab_rect
from .media.media_player_widget import MediaPlayerWidget
from .widgets.transcript_table import TranscriptTable
from .widgets.settings_panel import SettingsPanel
from .widgets.correction_panel import CorrectionPanel
from .widgets.speaker_bar import SpeakerBar
from .widgets.status_strip import StatusStrip
from .widgets.collapsible import CollapsibleSection
from .correction.corrector import get_corrector
from .models.transcript_model import TranscriptRow
from .ocr.base import qimage_to_png_bytes
from .ocr.ocr_worker import OcrDispatcher
from .ocr.windows_ocr import WindowsOCREngine
from .export import exporter


EXPORT_TOOLTIP = """列の並び: 話者名, 台詞, [プリセット名]
話者名を「話者名,プリセット名」と登録した行があると、プリセット名が3列目に入ります（未指定の行は空欄）。
合成音声ソフトへの取り込み用のため、時刻は出力しません。時刻が必要な場合は SRT を使ってください。"""


SRT_TOOLTIP = """動画から取り込んだ行（時刻あり）を字幕ファイルとして書き出します。
終了時刻は次の台詞の開始時刻から自動で決めます。
時刻を持たない行（デスクトップ/画像から取り込んだ行）は含まれません。"""


class GlobalHotkeyEmitter(QObject):
    hotkey_triggered = Signal()


class _DigitKeyFilter(QObject):
    """アプリ全体の KeyPress を監視し、メディアモードの 1〜9 キーを拾う軽量フィルタ。

    QMainWindow 自体をフィルタにすると super().eventFilter との再入で
    RecursionError を起こし得るため、独立した QObject に分離する。
    例外は握りつぶし、消費時のみ True を返す（それ以外は False で通常配送）。

    日本語IMEの変換中（未確定文字列がある間）は数字キーを横取りしない。
    変換中にウィジェットツリーを触るとネイティブクラッシュし得るため。
    """

    def __init__(self, handler, parent=None):
        super().__init__(parent)
        self._handler = handler
        self._composing = False

    def eventFilter(self, obj, event):
        try:
            et = event.type()
            if et == QEvent.Type.InputMethod:
                # 未確定文字列の有無で IME 変換中かどうかを追跡
                self._composing = bool(event.preeditString())
                return False
            if et == QEvent.Type.KeyPress:
                if self._composing:
                    return False
                return bool(self._handler(event))
        except Exception:
            pass
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RecoOCR")
        self.resize(1000, 640)
        self.setAcceptDrops(True)

        self.config = ConfigManager()
        self.last_ocr_text = ""
        self.waiting_for_key = False
        self.is_always_on_top = False
        self._jobs: dict[int, dict] = {}
        self._in_digit = False   # 数字キー処理の再入ガード

        # プロジェクト（未保存なら session.json、保存済みならそのファイルへ自動保存）
        self.project = Project()
        self._session_path = self.project.storage_path()
        self._session_error_shown = False
        self._session_timer = QTimer(self)
        self._session_timer.setSingleShot(True)
        self._session_timer.setInterval(500)   # 変更後500msでまとめて保存
        self._session_timer.timeout.connect(self._write_session)

        # OCR ディスパッチャ（別プロセス）
        self.dispatcher = OcrDispatcher(
            engine_name=self.config.get("ocr_engine", "rapidocr"),
            lang=self.config.get("ocr_lang", "ja"),
            max_workers=2,
        )
        self.dispatcher.result_ready.connect(self._on_ocr_result, Qt.ConnectionType.QueuedConnection)
        self.dispatcher.failed.connect(self._on_ocr_failed, Qt.ConnectionType.QueuedConnection)

        # 日本語校正（候補は選択時に都度再計算するため保持しない）
        self.corrector = get_corrector(self.config.get("ocr_lang", "ja"))
        self._warmup_corrector()

        # グローバルホットキー
        self.hotkey_emitter = GlobalHotkeyEmitter()
        self.hotkey_emitter.hotkey_triggered.connect(self.start_capture)
        self.hotkey_listener = None
        self.setup_hotkey()

        self._build_ui()
        self._apply_input_mode(self.config.get("input_mode", "desktop"))
        self._apply_correction_visibility()

        # 前回の作業状態を復元してから、変更監視（自動保存）を接続
        self._restore_session()
        self.table.content_changed.connect(self._schedule_session_save)

        # 数字キーをメディアモードで拾う専用フィルタ（QMainWindow とは分離）
        self._key_filter = _DigitKeyFilter(self._maybe_handle_media_digit)
        QApplication.instance().installEventFilter(self._key_filter)

        self._check_ocr_availability()

    # ================================================================
    # UI 構築
    # ================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # 左右をドラッグで調整できる水平スプリッタ
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- 左パネル（コントロール / 設定タブ） ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_control_tab(), "実行")
        self.settings_panel = SettingsPanel(self.config)
        self.settings_panel.settings_saved.connect(self._on_settings_saved)
        self.tabs.addTab(self.settings_panel, "設定")
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.tabs)
        left.setMinimumWidth(240)
        self.main_splitter.addWidget(left)

        # --- 右パネル（メディア / 書き起こしを縦スプリッタで、下にエクスポート） ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # プレビューと取り込み欄の境界をドラッグで調整できる垂直スプリッタ
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.media = MediaPlayerWidget()
        self.media.region_selected.connect(self._on_region_selected)
        self.media.region_cleared.connect(self._on_region_cleared)
        self.media.media_loaded.connect(self._on_media_loaded)
        self.media.media_loaded.connect(lambda _v: self._schedule_session_save())
        self.media.setMinimumHeight(160)
        self.right_splitter.addWidget(self.media)

        # 映像の直下に「状態」と「話者キー」を集約する（視線の中心に置く）
        stage = QWidget()
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(8)

        self.status_strip = StatusStrip()
        stage_layout.addWidget(self.status_strip)

        # 話者キー列（右端にリスト操作を固定配置する）
        speaker_row = QHBoxLayout()
        speaker_row.setContentsMargins(0, 0, 0, 0)
        speaker_row.setSpacing(8)
        self.speaker_bar = SpeakerBar(self.config.characters)
        self.speaker_bar.speaker_triggered.connect(self._on_speaker_triggered)
        speaker_row.addWidget(self.speaker_bar, 1)

        self.btn_clear = QPushButton("リストをクリア")
        self.btn_clear.setProperty("danger", True)
        self.btn_clear.setToolTip("書き起こしリストを空にします")
        self.btn_clear.clicked.connect(self._clear_list)
        speaker_row.addWidget(self.btn_clear, 0, Qt.AlignmentFlag.AlignBottom)
        stage_layout.addLayout(speaker_row)
        stage.setMaximumHeight(140)
        self.right_splitter.addWidget(stage)
        self._stage = stage

        self.table = TranscriptTable(self.config.characters)
        self.table.seek_requested.connect(self._on_seek_requested)
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self.table.setMinimumHeight(100)
        self.right_splitter.addWidget(self.table)

        # 校正候補パネル（候補提示モードで使用）
        self.correction_panel = CorrectionPanel()
        self.correction_panel.candidate_chosen.connect(self._on_candidate_chosen)
        self.correction_panel.setMinimumHeight(80)
        self.right_splitter.addWidget(self.correction_panel)

        self.right_splitter.setStretchFactor(0, 3)   # 映像
        self.right_splitter.setStretchFactor(1, 0)   # 状態＋話者キー（固定気味）
        self.right_splitter.setStretchFactor(2, 2)   # 書き起こし
        self.right_splitter.setStretchFactor(3, 1)   # 校正候補
        self.right_splitter.setChildrenCollapsible(False)
        right_layout.addWidget(self.right_splitter, 1)

        # 書き出し操作（リスト操作は話者キー列の右端に移したのでここは書き出しのみ）
        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        self.btn_csv = QPushButton("CSV エクスポート")
        self.btn_txt = QPushButton("TXT エクスポート")
        for _b in (self.btn_csv, self.btn_txt):
            _b.setToolTip(EXPORT_TOOLTIP)
        self.btn_srt = QPushButton("SRT エクスポート")
        self.btn_srt.setToolTip(SRT_TOOLTIP)
        self.btn_sort = QPushButton("時刻順にソート")
        self.btn_sort.setToolTip("リストを時刻の昇順に並び替えます（確認あり）")
        self.btn_csv.clicked.connect(lambda: self._export("csv"))
        self.btn_txt.clicked.connect(lambda: self._export("txt"))
        self.btn_srt.clicked.connect(self._export_srt)
        self.btn_sort.clicked.connect(self._sort_by_time)
        export_row.addWidget(self.btn_csv)
        export_row.addWidget(self.btn_txt)
        export_row.addWidget(self.btn_srt)
        export_row.addWidget(self.btn_sort)
        export_row.addStretch()
        right_layout.addLayout(export_row)

        self.main_splitter.addWidget(right)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setSizes([340, 660])
        main_layout.addWidget(self.main_splitter)

    @staticmethod
    def _segment(text: str, tooltip: str = "") -> QPushButton:
        """モード選択用のセグメントボタン（ラジオより現在値が一目で分かる）。"""
        b = QPushButton(text)
        b.setCheckable(True)
        b.setProperty("segment", True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(36)
        if tooltip:
            b.setToolTip(tooltip)
        return b

    @staticmethod
    def _hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{theme.TEXT_MUTED}; font-size:11px;")
        return lbl

    def _build_control_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # --- プロジェクト（最上段） ---
        proj_box = QGroupBox("プロジェクト")
        p_layout = QVBoxLayout(proj_box)
        p_layout.setSpacing(6)
        self.project_label = QLabel(project.UNTITLED)
        self.project_label.setStyleSheet(
            f"color:{theme.ACCENT}; font-weight:700; font-size:13px;")
        self.project_label.setWordWrap(True)
        p_layout.addWidget(self.project_label)
        p_row1 = QHBoxLayout()
        self.btn_proj_open = QPushButton("開く")
        self.btn_proj_open.clicked.connect(self._project_open)
        self.btn_proj_save = QPushButton("名前を付けて保存")
        self.btn_proj_save.clicked.connect(self._project_save_as)
        p_row1.addWidget(self.btn_proj_open)
        p_row1.addWidget(self.btn_proj_save)
        p_layout.addLayout(p_row1)
        self.btn_proj_close = QPushButton("プロジェクトを閉じる")
        self.btn_proj_close.clicked.connect(self._project_close)
        p_layout.addWidget(self.btn_proj_close)
        p_layout.addWidget(self._hint(
            "未保存のあいだは「新しいプロジェクト」として自動保存されます。"))
        layout.addWidget(proj_box)

        # --- 入力ソース（セグメント切替） ---
        src_box = QGroupBox("入力ソース")
        src_layout = QVBoxLayout()
        src_layout.setSpacing(6)
        self.src_bg = QButtonGroup(self)
        self.rb_src_desktop = self._segment("デスクトップ画面を読み取る",
                                            "ホットキーまたはボタンで画面を矩形選択します")
        self.rb_src_media = self._segment("画像・動画を読み込んで読み取る",
                                          "ファイルをドラッグ&ドロップでも読み込めます")
        self.src_bg.addButton(self.rb_src_desktop, 0)
        self.src_bg.addButton(self.rb_src_media, 1)
        src_layout.addWidget(self.rb_src_desktop)
        src_layout.addWidget(self.rb_src_media)
        src_box.setLayout(src_layout)
        layout.addWidget(src_box)
        self.src_bg.buttonClicked.connect(self._on_src_changed)

        # --- デスクトップ ---
        self.desktop_box = CollapsibleSection(
            "デスクトップ読み取り",
            expanded=bool(self.config.get("ui_expand_desktop", True)))
        self.desktop_box.toggled.connect(
            lambda v: self.config.set("ui_expand_desktop", v))
        d_layout = self.desktop_box.body_layout()
        self.btn_capture = QPushButton("画面を切り取って読み取る")
        self.btn_capture.setProperty("accent", True)
        self.btn_capture.setMinimumHeight(44)
        self.btn_capture.clicked.connect(self.start_capture)
        self.btn_capture_last = QPushButton("前回と同じ範囲で読み取る")
        self.btn_capture_last.clicked.connect(self.capture_last_rect)
        d_layout.addWidget(self.btn_capture)
        d_layout.addWidget(self.btn_capture_last)
        d_layout.addWidget(self._hint(
            f"ホットキー {self.config.get('shortcut_key', '<ctrl>+<alt>+o')} でも実行できます"))

        d_layout.addSpacing(4)
        d_layout.addWidget(self._hint("読み取った後の動作"))
        self.mode_bg = QButtonGroup(self)
        self.rb_numkey = self._segment("1〜9 キーで話者を選んで追加",
                                       "読み取り後にキー入力を待ちます")
        self.rb_direct = self._segment("話者「未設定」ですぐ追加")
        self.rb_clipboard = self._segment("クリップボードにコピー")
        self.mode_bg.addButton(self.rb_clipboard, 1)
        self.mode_bg.addButton(self.rb_direct, 2)
        self.mode_bg.addButton(self.rb_numkey, 3)
        for b in (self.rb_numkey, self.rb_direct, self.rb_clipboard):
            d_layout.addWidget(b)
        mode = self.config.get("ocr_mode", "numkey")
        {"clipboard": self.rb_clipboard, "direct": self.rb_direct,
         "numkey": self.rb_numkey}.get(mode, self.rb_numkey).setChecked(True)
        self.mode_bg.buttonClicked.connect(self._save_ocr_mode)
        layout.addWidget(self.desktop_box)

        # --- メディア ---
        self.media_box = CollapsibleSection(
            "メディア読み取り",
            expanded=bool(self.config.get("ui_expand_media", True)))
        self.media_box.toggled.connect(
            lambda v: self.config.set("ui_expand_media", v))
        m_layout = self.media_box.body_layout()
        self.btn_open = QPushButton("画像・動画を開く")
        self.btn_open.setProperty("accent", True)
        self.btn_open.setMinimumHeight(44)
        self.btn_open.clicked.connect(self._open_file_dialog)
        m_layout.addWidget(self.btn_open)
        m_layout.addWidget(self._hint(
            "ドラッグ&ドロップでも読み込めます。映像上をドラッグして読み取り領域を指定"
            "（ドラッグせずクリックで解除）"))

        m_layout.addSpacing(4)
        m_layout.addWidget(self._hint("読み取り方"))
        self.read_bg = QButtonGroup(self)
        self.rb_normal = self._segment("通常 — 1件ずつ確認しながら",
                                       "一時停止して読み取り、内容を確認・修正できます")
        self.rb_continuous = self._segment("連続 — 再生を止めずに次々と",
                                           "キーを押すたび行を追加し、認識結果を後から埋めます")
        self.read_bg.addButton(self.rb_normal, 0)
        self.read_bg.addButton(self.rb_continuous, 1)
        m_layout.addWidget(self.rb_normal)
        m_layout.addWidget(self.rb_continuous)
        rmode = self.config.get("read_mode", "normal")
        (self.rb_continuous if rmode == "continuous" else self.rb_normal).setChecked(True)
        self.read_bg.buttonClicked.connect(self._save_read_mode)
        layout.addWidget(self.media_box)

        layout.addStretch()

        # 最前面表示トグル
        self.btn_pin = QPushButton("📌  常に手前に表示")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setProperty("segment", True)
        self.btn_pin.clicked.connect(self._toggle_always_on_top)
        layout.addWidget(self.btn_pin)
        return tab

    # ================================================================
    # 入力モード切替
    # ================================================================
    def _on_src_changed(self):
        mode = "media" if self.rb_src_media.isChecked() else "desktop"
        self.config.set("input_mode", mode)
        self._apply_input_mode(mode)

    def _apply_input_mode(self, mode: str):
        is_media = mode == "media"
        (self.rb_src_media if is_media else self.rb_src_desktop).setChecked(True)
        self.desktop_box.setVisible(not is_media)
        self.media_box.setVisible(is_media)
        self.media.setVisible(is_media)
        # メディア固有の前提条件（読み込み/領域）はメディアモードでのみ意味を持つ
        self.status_strip.set_indicators_visible(is_media)
        if is_media:
            self.status_strip.set_message("画像・動画を読み込んでください（ドラッグ&ドロップ可）")
        else:
            self.status_strip.set_message("画面を切り取って読み取れます")
        self._refresh_state_indicators()

    def _refresh_state_indicators(self):
        """スタータス右側のインジケータ（メディア/領域/モード）を現在値に同期する。"""
        is_media = self.config.get("input_mode") == "media"
        if is_media:
            path = self.media.current_path()
            self.status_strip.set_media(self.media.has_media(),
                                        os.path.basename(path) if path else "")
            rect = self.media.region()
            self.status_strip.set_region(
                rect is not None,
                f"{rect.width()}×{rect.height()}" if rect is not None else "")
            self.status_strip.set_mode(
                "連続" if self.config.get("read_mode") == "continuous" else "通常")
        else:
            mode = self.config.get("ocr_mode", "numkey")
            self.status_strip.set_mode(
                {"numkey": "1〜9キー", "direct": "即追加",
                 "clipboard": "クリップボード"}.get(mode, mode))

    def _save_ocr_mode(self):
        if self.rb_clipboard.isChecked():
            self.config.set("ocr_mode", "clipboard")
        elif self.rb_numkey.isChecked():
            self.config.set("ocr_mode", "numkey")
        else:
            self.config.set("ocr_mode", "direct")
        self._refresh_state_indicators()

    def _save_read_mode(self):
        self.config.set("read_mode",
                        "continuous" if self.rb_continuous.isChecked() else "normal")
        self._refresh_state_indicators()

    def _on_speaker_triggered(self, key: str):
        """話者チップのクリック（キー押下と同じ動作）。"""
        if self.config.get("input_mode") == "media":
            self.speaker_bar.flash(key)
            self._handle_media_digit(key)
        elif self.waiting_for_key:
            self.speaker_bar.flash(key)
            self._commit_waiting_key(key)

    # ================================================================
    # デスクトップOCR
    # ================================================================
    def setup_hotkey(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        try:
            hotkey_str = self.config.get("shortcut_key", "<ctrl>+<alt>+o")
            if "ctrl+alt+o" == hotkey_str:
                hotkey_str = "<ctrl>+<alt>+o"
            h = keyboard.HotKey(keyboard.HotKey.parse(hotkey_str),
                                lambda: self.hotkey_emitter.hotkey_triggered.emit())
            self.hotkey_listener = keyboard.Listener(on_press=h.press, on_release=h.release)
            self.hotkey_listener.start()
        except Exception as e:
            print(f"[hotkey] register error: {e}")

    def start_capture(self):
        if self.config.get("input_mode") == "media":
            return
        self.hide()
        QTimer.singleShot(200, self._open_capture_window)

    def _open_capture_window(self):
        self.cap_win = CaptureWindow()
        self.cap_win.capture_finished.connect(self._process_capture)
        self.cap_win.show()

    def _process_capture(self, rect: QRect, pixmap):
        self.show()
        self.config.set("last_rect", [rect.x(), rect.y(), rect.width(), rect.height()])
        self._submit_desktop_ocr(pixmap.toImage())

    def capture_last_rect(self):
        rect_data = self.config.get("last_rect")
        if not rect_data:
            QMessageBox.warning(self, "エラー", "前回の座標データがありません。")
            return
        x, y, w, h = rect_data
        self.hide()
        QTimer.singleShot(400, lambda: self._grab_and_ocr(QRect(x, y, w, h)))

    def _grab_and_ocr(self, rect: QRect):
        pixmap = grab_rect(rect)
        self.show()
        self._submit_desktop_ocr(pixmap.toImage())

    def _submit_desktop_ocr(self, image: QImage):
        if image is None or image.isNull():
            self.status_strip.set_message("画像の取得に失敗しました", "error")
            return
        seq = self.dispatcher.submit(qimage_to_png_bytes(image), self.config.get("preprocess"),
                                     self.config.get("multi_ocr_vote", False))
        self._jobs[seq] = {"kind": "desktop"}
        self.status_strip.set_message("認識中…", "busy")

    def handle_ocr_result(self, text: str):
        """デスクトップOCR結果の後処理（clipboard/direct/numkey）。"""
        self.last_ocr_text = text
        mode = self.config.get("ocr_mode", "numkey")
        if not text:
            self.status_strip.set_message("文字を認識できませんでした", "error")
            return
        if mode == "clipboard":
            QApplication.clipboard().setText(text)
            self.status_strip.set_message("クリップボードにコピーしました", "ok")
        elif mode == "direct":
            item = self.table.add_row(TranscriptRow("未設定", text))
            self._handle_new_text(item, text)
            self.status_strip.set_message("リストに追加しました", "ok")
        elif mode == "numkey":
            self.waiting_for_key = True
            self.status_strip.set_message(f"『{text}』…対応する数字キー(1-9)を押してください。")
            self.activateWindow()

    # ================================================================
    # メディアOCR（数字キー）
    # ================================================================
    def _resolve_speaker(self, key: str) -> str:
        for char in self.config.characters:
            if char.get("key") == key:
                return char.get("name", "不明")
        return "不明"

    def _maybe_handle_media_digit(self, event) -> bool:
        """メディアモードでの 1〜9 キーを処理。消費したら True。

        テキスト編集中（フォーカスが QLineEdit）は横取りしない。再入もガードする。
        """
        if self._in_digit:
            return False
        if self.config.get("input_mode") != "media" or not self.media.has_media():
            return False
        fw = QApplication.focusWidget()
        if isinstance(fw, QLineEdit):
            return False
        t = event.text()
        if not t or not t.isdigit() or t == "0":
            return False
        # イベントフィルタ内で直接ウィジェットを操作すると、IME確定などの
        # イベント配送中に再入してクラッシュし得る。次サイクルへ遅延実行する。
        QTimer.singleShot(0, lambda key=t: self._handle_media_digit(key))
        return True

    def _handle_media_digit(self, key: str):
        if not self.media.has_media():
            self.status_strip.set_message("先に画像・動画を読み込んでください", "error")
            return
        image = self.media.grab_region_image()
        if image is None or image.isNull():
            self.status_strip.set_message("映像上をドラッグして読み取り領域を指定してください", "error")
            return
        speaker = self._resolve_speaker(key)
        self.speaker_bar.flash(key)          # どのキーが効いたかを視覚的に返す
        pos = self.media.current_position_ms() if self.media.is_video() else None
        png = qimage_to_png_bytes(image)
        opts = self.config.get("preprocess")
        vote = self.config.get("multi_ocr_vote", False)
        read_mode = self.config.get("read_mode", "normal")
        if read_mode == "continuous":
            item = self.table.add_row(TranscriptRow(speaker, "", pos), placeholder=True)
            seq = self.dispatcher.submit(png, opts, vote)
            self._jobs[seq] = {"kind": "cont", "item": item}
            self.status_strip.set_message(f"{speaker} … 連続読み取り中", "busy")
        else:
            seq = self.dispatcher.submit(png, opts, vote)
            self._jobs[seq] = {"kind": "normal", "speaker": speaker, "ts": pos}
            self.status_strip.set_message(f"{speaker} … 認識中", "busy")

    # ================================================================
    # OCR 結果受信（別スレッド→キュー接続でUIスレッド）
    # ================================================================
    def _clean_ocr_text(self, text: str) -> str:
        """認識結果の後処理（半角スペース除去など）。"""
        if text and self.config.get("remove_spaces", False):
            text = text.replace(" ", "")
        return text

    def _on_ocr_result(self, seq: int, text: str):
        job = self._jobs.pop(seq, None)
        if job is None:
            return
        text = self._clean_ocr_text(text)
        kind = job["kind"]
        if kind == "desktop":
            self.handle_ocr_result(text)
        elif kind == "normal":
            item = self.table.add_row(TranscriptRow(job["speaker"], text, job["ts"]))
            self._handle_new_text(item, text)
            self.status_strip.set_message(f"{job['speaker']} を追加しました", "ok")
        elif kind == "cont":
            self.table.set_text_for_item(job["item"], text or "")
            self._handle_new_text(job["item"], text or "")

    def _on_ocr_failed(self, seq: int, msg: str):
        job = self._jobs.pop(seq, None)
        if job and job.get("kind") == "cont":
            self.table.set_text_for_item(job["item"], "[OCR失敗]")
        self.status_strip.set_message(f"OCRエラー: {msg}", "error")

    # ================================================================
    # 日本語校正
    # ================================================================
    def _warmup_corrector(self):
        """辞書ロードは重いので、校正が有効なら起動時に別スレッドで温める。"""
        if self.config.get("correction_mode", "off") == "off":
            return
        import threading
        threading.Thread(target=self.corrector.ensure_loaded, daemon=True).start()

    def _apply_correction_visibility(self):
        self.correction_panel.setVisible(
            self.config.get("correction_mode", "off") != "off")

    def _handle_new_text(self, text_item, raw_text: str):
        """OCRで確定したテキストに校正を適用（自動/候補提示）。"""
        mode = self.config.get("correction_mode", "off")
        if mode == "off" or not raw_text or text_item is None:
            return
        try:
            suggestions = self.corrector.correct_line(raw_text)
        except Exception as e:
            print(f"[correction] error: {e}")
            return
        if mode == "auto":
            corrected = self.corrector.apply_best(raw_text, suggestions)
            if corrected != raw_text:
                self.table.set_text_for_item(text_item, corrected)
                self.table.set_flag(text_item, True)
        elif mode == "suggest":
            if suggestions:
                self.table.set_flag(text_item, True)

    def _on_row_selection_changed(self):
        if self.config.get("correction_mode", "off") != "suggest":
            return
        item = self.table.current_text_item()
        if item is None:
            self.correction_panel.clear("行を選択すると修正候補を表示します。")
            return
        # 選択のたびに最新テキストで再計算（手動編集後も追随）
        try:
            suggestions = self.corrector.correct_line(item.text())
        except Exception:
            suggestions = []
        self.table.set_flag(item, bool(suggestions))
        self.correction_panel.show_for(item, suggestions)

    def _on_candidate_chosen(self, text_item, start: int, end: int, word: str):
        if text_item is None or text_item.tableWidget() is None:
            return
        txt = text_item.text()
        text_item.setText(txt[:start] + word + txt[end:])
        # 適用後は最新状態で候補を更新（候補は同長置換なので他のオフセットは不変）
        self._on_row_selection_changed()

    # ================================================================
    # メディア関連コールバック
    # ================================================================
    def _on_region_selected(self, rect: QRect):
        self.status_strip.set_message("準備完了 — 1〜9 キー（または下のチップ）で読み取り", "ok")
        self._refresh_state_indicators()

    def _on_region_cleared(self):
        self.status_strip.set_message("読み取り領域を解除しました — ドラッグで指定し直せます")
        self._refresh_state_indicators()

    def _on_media_loaded(self, is_video: bool):
        kind = "動画" if is_video else "画像"
        self.status_strip.set_message(
            f"{kind}を読み込みました — 映像上をドラッグして読み取り領域を指定してください")
        self._refresh_state_indicators()

    def _on_seek_requested(self, ms: int):
        # 一時停止中はそのまま（再生開始しない）。再生中はそのまま再生を継続。
        if self.media.is_video():
            self.media.seek(ms)

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "メディアを開く", "",
            "メディア (*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.jpg *.jpeg *.png *.bmp *.webp);;すべて (*.*)")
        if path:
            self._load_media(path)

    def _load_media(self, path: str):
        if not self.media.is_supported(path):
            QMessageBox.warning(self, "非対応", "対応していないファイル形式です。")
            return
        self.rb_src_media.setChecked(True)
        self.config.set("input_mode", "media")
        self._apply_input_mode("media")
        if not self.media.load(path):
            QMessageBox.warning(self, "読み込み失敗", "ファイルを読み込めませんでした。")

    # ================================================================
    # ドラッグ&ドロップ
    # ================================================================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if self.media.is_supported(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self.media.is_supported(path):
                self._load_media(path)
                break

    # ================================================================
    # キーボード（デスクトップ numkey）※メディア digit は _DigitKeyFilter で処理
    # ================================================================
    def _commit_waiting_key(self, key_text: str):
        """デスクトップOCRの数字キー待機を確定する。"""
        speaker = self._resolve_speaker(key_text)
        item = self.table.add_row(TranscriptRow(speaker, self.last_ocr_text))
        self._handle_new_text(item, self.last_ocr_text)
        self.waiting_for_key = False
        self.status_strip.set_message(f"{speaker} を追加しました", "ok")

    def keyPressEvent(self, event):
        if self.waiting_for_key:
            key_text = event.text()
            if key_text.isdigit():
                self.speaker_bar.flash(key_text)
                self._commit_waiting_key(key_text)
                return
        super().keyPressEvent(event)

    # ================================================================
    # 設定保存後
    # ================================================================
    def _on_settings_saved(self):
        self.setup_hotkey()
        self.table.set_characters(self.config.characters)
        self.table.update_all_comboboxes()
        self.speaker_bar.set_characters(self.config.characters)
        self._refresh_state_indicators()
        # エンジン/言語が変わった可能性 → プール作り直し
        self.dispatcher.restart(self.config.get("ocr_engine", "rapidocr"),
                                self.config.get("ocr_lang", "ja"))
        # 校正: 言語追従・表示切替・ウォームアップ
        self.corrector = get_corrector(self.config.get("ocr_lang", "ja"))
        self._apply_correction_visibility()
        self._warmup_corrector()
        QMessageBox.information(self, "保存完了", "設定を保存しました。")
        self._check_ocr_availability()

    # ================================================================
    # その他
    # ================================================================
    def _toggle_always_on_top(self):
        self.is_always_on_top = self.btn_pin.isChecked()
        flags = self.windowFlags()
        if self.is_always_on_top:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setStyleSheet("background-color:#fff9c4; color:black;")
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setStyleSheet("")
        self.show()

    def _export(self, fmt: str):
        rows = self.table.to_rows()
        if not rows:
            QMessageBox.warning(self, "エラー", "エクスポートするデータがありません。")
            return
        ext = ".csv" if fmt == "csv" else ".txt"
        file_filter = "CSVファイル (*.csv)" if fmt == "csv" else "テキストファイル (*.txt)"
        path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", f"export{ext}", file_filter)
        if not path:
            return
        try:
            exporter.export(rows, path, fmt,
                            include_preset=exporter.has_presets(rows))
            QMessageBox.information(self, "エクスポート完了", f"{path} に保存しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました: {e}")

    def _export_srt(self):
        """字幕ファイル（SRT）として書き出す。時刻を持つ行のみが対象。"""
        rows = self.table.to_rows()
        if not rows:
            QMessageBox.warning(self, "エラー", "エクスポートするデータがありません。")
            return
        timed = exporter.timed_rows(rows)
        if not timed:
            QMessageBox.warning(
                self, "SRTを作成できません",
                "時刻を持つ行がありません。\n\n"
                "SRT は字幕ファイルのため、動画から取り込んだ行"
                "（時刻列に値がある行）が必要です。")
            return
        skipped = len(rows) - len(timed)
        path, _ = QFileDialog.getSaveFileName(
            self, "名前を付けて保存", "export.srt", "字幕ファイル (*.srt)")
        if not path:
            return
        try:
            count = exporter.export_srt(rows, path)
            msg = f"{path} に保存しました。（{count}件）"
            if skipped:
                msg += f"\n時刻を持たない {skipped} 行は含まれていません。"
            QMessageBox.information(self, "エクスポート完了", msg)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました: {e}")

    def _clear_list(self):
        self.table.setRowCount(0)
        self._write_session()

    # ================================================================
    # 作業状態の自動保存 / 復元
    # ================================================================
    def _schedule_session_save(self):
        # 変更のたびに呼ばれるので、500ms のデバウンスでまとめて書き込む
        self._session_timer.start()

    # ================================================================
    # プロジェクト
    # ================================================================
    def _update_project_label(self):
        name = self.project.name
        self.project_label.setText(name if self.project.is_saved else f"{name}（未保存）")
        self.project_label.setToolTip(self.project.path or "まだ名前を付けていません")
        self.btn_proj_close.setEnabled(self.project.is_saved)

    def _project_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "プロジェクトを開く", project.default_dir(),
            f"RecoOCR プロジェクト (*{project.EXT});;すべて (*.*)")
        if not path:
            return
        try:
            data = project.read(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"プロジェクトを開けませんでした:\n{e}")
            return
        # 現在の内容を保存してから切り替える（取りこぼし防止）
        self._write_session()
        self.project.open(path)
        self.config.set("last_project", path)
        self.table.setRowCount(0)
        for r in data.get("rows", []):
            self.table.add_row(TranscriptRow(
                r.get("speaker", "未設定"), r.get("text", ""), r.get("timestamp_ms")))
        media_path = data.get("media_path")
        if media_path and os.path.exists(media_path) and self.media.is_supported(media_path):
            self._load_media(media_path)
        self._session_path = self.project.storage_path()
        self._update_project_label()
        self.status_strip.set_message(f"プロジェクト「{self.project.name}」を開きました", "ok")

    def _project_save_as(self):
        default = os.path.join(project.default_dir(),
                               (self.project.name if self.project.is_saved else "project") + project.EXT)
        path, _ = QFileDialog.getSaveFileName(
            self, "プロジェクトに名前を付けて保存", default,
            f"RecoOCR プロジェクト (*{project.EXT})")
        if not path:
            return
        path = self.project.save_as(path)
        self.config.set("last_project", path)
        self._session_path = path
        self._write_session()
        self._update_project_label()
        self.status_strip.set_message(f"「{self.project.name}」として保存しました", "ok")

    def _project_close(self):
        if not self.project.is_saved:
            return
        if QMessageBox.question(
                self, "プロジェクトを閉じる",
                f"「{self.project.name}」を閉じます。\n"
                "リストは空になり、未保存の状態に戻ります。よろしいですか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._write_session()          # 閉じる前に現在の内容を確定保存
        self.project.close()
        self.config.set("last_project", None)
        self.table.setRowCount(0)
        self.media.unload()            # 読み込んでいた画像/動画も解放する
        self._session_path = self.project.storage_path()
        self._update_project_label()
        self._refresh_state_indicators()
        self.status_strip.set_message("プロジェクトを閉じました（新しいプロジェクト）")

    # ================================================================
    # リスト操作
    # ================================================================
    def _sort_by_time(self):
        rows = self.table.to_rows()
        if not rows:
            QMessageBox.information(self, "並び替え", "リストが空です。")
            return
        if QMessageBox.question(
                self, "時刻順にソート",
                "リストを時刻順に並び替えます。\nこの操作は元に戻せません。よろしいですか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        # 時刻なしの行は末尾へ（元の順序は保つ）
        ordered = sorted(
            enumerate(rows),
            key=lambda p: (p[1].timestamp_ms is None,
                           p[1].timestamp_ms if p[1].timestamp_ms is not None else 0,
                           p[0]))
        self.table.setRowCount(0)
        for _i, row in ordered:
            self.table.add_row(row)
        self.status_strip.set_message("時刻順に並び替えました", "ok")

    def _write_session(self):
        path = self.project.storage_path()
        try:
            rows = [{"speaker": r.speaker, "text": r.text, "timestamp_ms": r.timestamp_ms}
                    for r in self.table.to_rows()]
            project.write(path, rows, {
                "input_mode": self.config.get("input_mode", "desktop"),
                "media_path": self.media.current_path(),
            })
            self._session_path = path
        except Exception as e:
            print(f"[session] save error: {e}")
            self._session_path = path
            # 保存できないと書き起こしが失われるため、一度だけ明示的に警告する
            if not self._session_error_shown:
                self._session_error_shown = True
                QMessageBox.warning(
                    self, "自動保存に失敗しました",
                    f"作業状態を保存できませんでした。\n\n保存先: {self._session_path}\n{e}\n\n"
                    "書き込み権限のある場所にアプリを配置するか、"
                    "ウイルス対策ソフトの「フォルダーアクセスの制御」等の設定をご確認ください。\n"
                    "こまめに CSV/TXT へエクスポートすることを推奨します。")

    def _restore_session(self):
        # 前回開いていたプロジェクトがあればそれを、無ければ自動保存を読む
        last = self.config.get("last_project")
        if last and os.path.exists(last):
            self.project.open(last)
        path = self.project.storage_path()
        self._session_path = path
        self._update_project_label()
        if not os.path.exists(path):
            return
        try:
            data = project.read(path)
            rows = data.get("rows", [])
        except Exception as e:
            print(f"[session] load error: {e}")
            return
        for r in rows:
            self.table.add_row(TranscriptRow(
                r.get("speaker", "未設定"), r.get("text", ""), r.get("timestamp_ms")))

        # 前回開いていた画像/動画を復元
        media_path = data.get("media_path")
        media_restored = False
        if media_path and os.path.exists(media_path) and self.media.is_supported(media_path):
            self._load_media(media_path)
            media_restored = True

        msgs = []
        if rows:
            msgs.append(f"{len(rows)}行")
        if media_restored:
            msgs.append(os.path.basename(media_path))
        if msgs:
            self.status_strip.set_message("前回の作業状態を復元しました（" + " / ".join(msgs) + "）。")

    def _check_ocr_availability(self):
        engine = self.config.get("ocr_engine", "rapidocr")
        if engine != "windows":
            import importlib.util
            if importlib.util.find_spec("rapidocr") is None:
                QMessageBox.warning(
                    self, "RapidOCR 未インストール",
                    "RapidOCR が選択されていますが、インストールされていません。\n\n"
                    "次のコマンドで導入してください:\n"
                    "    pip install rapidocr onnxruntime\n\n"
                    "初回実行時に PP-OCR モデル（数十MB）が自動ダウンロードされます。")
            return
        lang = self.config.get("ocr_lang", "ja")
        if not WindowsOCREngine.is_available(lang):
            QMessageBox.warning(
                self, "OCR言語パック未導入",
                f"Windows OCR の言語 '{lang}' が見つかりません。\n\n"
                "設定 → 時刻と言語 → 言語と地域 → 日本語 → オプション →\n"
                "「基本入力」をインストールすると利用できます。\n\n"
                "利用可能な言語: " + (", ".join(WindowsOCREngine.available_languages()) or "なし"))

    def closeEvent(self, event):
        # 終了時に作業状態を確実に書き出す
        self._write_session()
        try:
            app = QApplication.instance()
            if app is not None and getattr(self, "_key_filter", None) is not None:
                app.removeEventFilter(self._key_filter)
        except Exception:
            pass
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
        except Exception:
            pass
        self.dispatcher.shutdown()
        super().closeEvent(event)
