"""画像/動画の表示・再生・領域選択ウィジェット。

QVideoWidget はネイティブサーフェスで子ウィジェットを重畳できないため、
QMediaPlayer + QVideoSink でフレームを受け取り、自前 QWidget に QPainter で
描画する。その上に RegionOverlay を子として重ね、矩形選択を可能にする。
"""
import os

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QSlider, QLabel, QSizePolicy, QComboBox)
from PySide6.QtCore import Qt, Signal, QUrl, QRect, QPointF, QRectF, QSize
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPixmap, QIcon, QPolygonF
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

from .region_overlay import RegionOverlay
from . import frame_grabber
from ..models.transcript_model import TranscriptRow
from .. import theme

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".flv"}


class VideoDisplay(QWidget):
    """現在フレーム（または静止画）をレターボックス描画し、上に選択オーバーレイを持つ。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image = QImage()
        self.overlay = RegionOverlay(self)
        self.overlay.setGeometry(self.rect())

    def set_image(self, image: QImage):
        self._image = image if image is not None else QImage()
        self.update()

    def current_image(self) -> QImage:
        return self._image

    def resizeEvent(self, event):
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG_BASE))
        if not self._image.isNull():
            target = frame_grabber.fitted_target_rect(
                self._image.size(), self.width(), self.height())
            painter.drawImage(target, self._image)
            return
        self._paint_placeholder(painter)

    def _paint_placeholder(self, painter: QPainter):
        """未読込時の案内（黒画面のままでは何をすべきか分からないため）。"""
        r = self.rect()
        # 破線の枠でドロップ領域であることを示す
        pen = QPen(QColor(theme.BORDER_STRONG), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        inset = r.adjusted(24, 24, -24, -24)
        painter.drawRoundedRect(inset, 12, 12)

        painter.setPen(QColor(theme.TEXT_DIM))
        f = painter.font()
        f.setPixelSize(20)
        f.setBold(True)
        painter.setFont(f)
        title_rect = QRect(r.left(), r.center().y() - 46, r.width(), 32)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter,
                         "画像・動画をここにドラッグ&ドロップ")

        painter.setPen(QColor(theme.TEXT_MUTED))
        f.setPixelSize(13)
        f.setBold(False)
        painter.setFont(f)
        painter.drawText(QRect(r.left(), r.center().y() - 8, r.width(), 24),
                         Qt.AlignmentFlag.AlignCenter,
                         "または「画像・動画を開く」から選択")
        painter.drawText(QRect(r.left(), r.center().y() + 20, r.width(), 24),
                         Qt.AlignmentFlag.AlignCenter,
                         "対応形式: mp4 / mkv / avi / mov  ·  jpg / png / bmp / webp")
        painter.drawText(QRect(r.left(), r.center().y() + 46, r.width(), 24),
                         Qt.AlignmentFlag.AlignCenter,
                         "読み込み後、映像上をドラッグして読み取り領域を指定します")


def _media_icon(kind: str) -> QIcon:
    """再生操作ボタンのアイコンを文字色で描く（kind: play / pause / prev / next）。

    「⏸」「◀」などの記号文字は Windows ではカラー絵文字（青い四角など）で
    表示されてしまうため、テーマの文字色で自前描画する。
    """
    size = 32   # 高DPIでも潰れないよう大きめに描いて縮小表示する
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.TEXT))
    if kind == "pause":
        # 縦棒2本
        p.drawRoundedRect(QRectF(8, 7, 6, 18), 1.5, 1.5)
        p.drawRoundedRect(QRectF(18, 7, 6, 18), 1.5, 1.5)
    elif kind == "play":
        # 右向き三角
        p.drawPolygon(QPolygonF([QPointF(10, 6), QPointF(26, 16), QPointF(10, 26)]))
    elif kind == "prev":
        # 縦棒＋左向き三角（前のファイル）
        p.drawRect(QRectF(7, 8, 3, 16))
        p.drawPolygon(QPolygonF([QPointF(24, 8), QPointF(11, 16), QPointF(24, 24)]))
    elif kind == "next":
        # 右向き三角＋縦棒（次のファイル）
        p.drawPolygon(QPolygonF([QPointF(8, 8), QPointF(21, 16), QPointF(8, 24)]))
        p.drawRect(QRectF(22, 8, 3, 16))
    p.end()
    return QIcon(pm)


class _SeekSlider(QSlider):
    """ホイールで 1 秒ずつシーク位置を動かせるスライダー。"""

    step_requested = Signal(int)   # 秒（+1 / -1）

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.step_requested.emit(1 if delta > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class MediaPlayerWidget(QWidget):
    media_loaded = Signal(bool)       # is_video
    position_changed = Signal(int)    # ms
    duration_changed = Signal(int)    # ms
    region_selected = Signal(QRect)
    region_cleared = Signal()
    playing_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_video = False
        self._has_media = False
        self._slider_pressed = False
        self._path: str | None = None

        self.display = VideoDisplay()
        self.display.overlay.region_selected.connect(self.region_selected)
        self.display.overlay.region_cleared.connect(self.region_cleared)

        # QMediaPlayer + 音声 + フレームシンク
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_playback_state)

        # --- コントロール ---
        # ファイル送り（画像・動画で共通。読み込んだフォルダ内を移動する）
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(_media_icon("prev"))
        self.btn_prev.setIconSize(QSize(16, 16))
        self.btn_prev.setFixedWidth(42)
        self.btn_prev.setToolTip("同じフォルダの前のファイル")
        self.btn_prev.clicked.connect(self.open_prev_file)
        self.btn_next = QPushButton()
        self.btn_next.setIcon(_media_icon("next"))
        self.btn_next.setIconSize(QSize(16, 16))
        self.btn_next.setFixedWidth(42)
        self.btn_next.setToolTip("同じフォルダの次のファイル")
        self.btn_next.clicked.connect(self.open_next_file)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(_media_icon("play"))
        self.btn_play.setIconSize(QSize(16, 16))
        self.btn_play.setFixedWidth(44)
        self.btn_play.clicked.connect(self.toggle_play)

        # 向きを明示する（既定は縦向きになるため）
        self.slider = _SeekSlider(Qt.Orientation.Horizontal)   # ホイールで±1秒
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_slider_pressed", True))
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.slider.step_requested.connect(self.step_seconds)

        self.time_label = QLabel("00:00.000 / 00:00.000")
        self.time_label.setFixedWidth(158)   # 等幅なので桁が動かない
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(f"font-family:{theme.FONT_MONO}; font-size:12px;")

        # 再生速度
        self.speed_combo = QComboBox()
        self.speed_combo.setFixedWidth(74)
        self.speed_combo.setToolTip("再生速度")
        for label, rate in [("0.25x", 0.25), ("0.5x", 0.5), ("0.75x", 0.75),
                            ("1x", 1.0), ("1.5x", 1.5), ("2x", 2.0),
                            ("4x", 4.0), ("8x", 8.0)]:
            self.speed_combo.addItem(label, rate)
        self.speed_combo.setCurrentIndex(3)   # 1x
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        # 音量（アイコンでミュート切替、バーで音量調整）
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedWidth(44)
        self.btn_mute.setToolTip("クリックでミュート切替")
        self.btn_mute.clicked.connect(self.toggle_mute)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setToolTip("音量")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.audio.setVolume(0.8)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        controls.addWidget(self.btn_prev)
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_next)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)
        controls.addWidget(self.speed_combo)
        controls.addWidget(self.btn_mute)
        controls.addWidget(self.volume_slider)

        layout = QVBoxLayout(self)
        layout.addWidget(self.display, 1)
        layout.addLayout(controls)
        self._update_controls_enabled(False)

    # --- 読み込み ---------------------------------------------------
    @staticmethod
    def is_supported(path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in IMAGE_EXTS or ext in VIDEO_EXTS

    def current_path(self) -> str | None:
        return self._path

    def unload(self):
        """読み込み前の状態へ戻す（プロジェクトを閉じたときなどに使う）。

        再生を止めてソースを外し、表示・選択領域・再生位置をすべて初期化する。
        表示が空になるのでドラッグ&ドロップの案内が再び出る。
        """
        self.player.stop()
        self.player.setSource(QUrl())
        self._is_video = False
        self._has_media = False
        self._path = None
        self.display.set_image(QImage())      # 案内表示に戻る
        self.display.overlay.set_region(None)  # 読み取り領域も解除
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.speed_combo.setCurrentIndex(self.speed_combo.findData(1.0))
        self.player.setPlaybackRate(1.0)
        self._update_controls_enabled(False)
        self._update_time_label(0, 0)

    def load(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTS:
            img = QImage(path)
            if img.isNull():
                return False
            self.player.stop()
            self.player.setSource(QUrl())
            self._is_video = False
            self._has_media = True
            self._path = path
            self.display.set_image(img)
            self.slider.setRange(0, 0)
            self._update_controls_enabled(False)
            self._update_time_label(0, 0)
            self.media_loaded.emit(False)
            return True
        elif ext in VIDEO_EXTS:
            self._is_video = True
            self._has_media = True
            self._path = path
            self.player.setSource(QUrl.fromLocalFile(path))
            self._update_controls_enabled(True)
            self.media_loaded.emit(True)
            # 最初のフレームを表示するため一瞬再生して止める
            self.player.play()
            self.player.pause()
            return True
        return False

    # --- 同フォルダ内のファイル送り -----------------------------------
    def sibling_files(self) -> list[str]:
        """現在のファイルと同じフォルダにある対応ファイル（名前順）。"""
        if not self._path:
            return []
        folder = os.path.dirname(os.path.abspath(self._path))
        try:
            names = sorted(os.listdir(folder), key=str.lower)
        except Exception:
            return []
        return [os.path.join(folder, n) for n in names
                if self.is_supported(os.path.join(folder, n))]

    def _step_file(self, delta: int) -> bool:
        files = self.sibling_files()
        if not files or not self._path:
            return False
        cur = os.path.abspath(self._path)
        try:
            i = [os.path.abspath(f) for f in files].index(cur)
        except ValueError:
            return False
        j = i + delta
        if not (0 <= j < len(files)):
            return False   # 端まで来たら何もしない
        return self.load(files[j])

    def open_next_file(self) -> bool:
        return self._step_file(1)

    def open_prev_file(self) -> bool:
        return self._step_file(-1)

    # --- 音量・速度 ---------------------------------------------------
    def _on_volume_changed(self, value: int):
        self.audio.setVolume(value / 100.0)
        if value > 0 and self.audio.isMuted():
            self.audio.setMuted(False)
        self._update_mute_icon()

    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        self._update_mute_icon()

    def _update_mute_icon(self):
        muted = self.audio.isMuted() or self.volume_slider.value() == 0
        self.btn_mute.setText("🔇" if muted else "🔊")

    def _on_speed_changed(self, _idx: int):
        rate = float(self.speed_combo.currentData() or 1.0)
        self.player.setPlaybackRate(rate)

    def step_seconds(self, seconds: int):
        """現在位置を指定秒だけ動かす（ホイールシーク用）。"""
        if not self._is_video:
            return
        dur = self.player.duration()
        pos = max(0, min(dur if dur > 0 else 0,
                         self.player.position() + seconds * 1000))
        self.player.setPosition(int(pos))

    # --- 再生制御 ---------------------------------------------------
    def play(self):
        if self._is_video:
            self.player.play()

    def pause(self):
        if self._is_video:
            self.player.pause()

    def toggle_play(self):
        if not self._is_video:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, ms: int):
        if self._is_video:
            self.player.setPosition(int(ms))

    def current_position_ms(self) -> int:
        return int(self.player.position()) if self._is_video else 0

    def is_video(self) -> bool:
        return self._is_video

    def has_media(self) -> bool:
        return self._has_media

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # --- 領域 -------------------------------------------------------
    def set_region(self, rect: QRect | None):
        self.display.overlay.set_region(rect)

    def region(self) -> QRect | None:
        return self.display.overlay.region()

    def grab_region_image(self) -> QImage:
        """現在フレームを選択領域で切り出す（領域未指定なら全体）。"""
        img = self.display.current_image()
        return frame_grabber.crop(
            img, self.region(), self.display.width(), self.display.height())

    # --- シグナル処理 -----------------------------------------------
    def _on_frame(self, frame):
        if frame is not None and frame.isValid():
            self.display.set_image(frame.toImage())

    def _on_position(self, ms: int):
        if not self._slider_pressed:
            self.slider.setValue(int(ms))
        self._update_time_label(ms, self.player.duration())
        self.position_changed.emit(int(ms))

    def _on_duration(self, ms: int):
        self.slider.setRange(0, int(ms))
        self._update_time_label(self.player.position(), ms)
        self.duration_changed.emit(int(ms))

    def _on_playback_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setIcon(_media_icon("pause" if playing else "play"))
        self.playing_changed.emit(playing)

    def _on_slider_moved(self, value: int):
        self._update_time_label(value, self.player.duration())

    def _on_slider_released(self):
        self._slider_pressed = False
        self.seek(self.slider.value())

    def _update_controls_enabled(self, enabled: bool):
        """enabled は動画向けコントロールの可否。ファイル送りは画像でも使える。"""
        for w in (self.btn_play, self.slider, self.speed_combo,
                  self.btn_mute, self.volume_slider):
            w.setEnabled(enabled)
        nav = self._has_media
        self.btn_prev.setEnabled(nav)
        self.btn_next.setEnabled(nav)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        self.time_label.setText(
            f"{TranscriptRow.format_timestamp(pos_ms)} / "
            f"{TranscriptRow.format_timestamp(dur_ms)}")
