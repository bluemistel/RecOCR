"""画像/動画の表示・再生・領域選択ウィジェット。

QVideoWidget はネイティブサーフェスで子ウィジェットを重畳できないため、
QMediaPlayer + QVideoSink でフレームを受け取り、自前 QWidget に QPainter で
描画する。その上に RegionOverlay を子として重ね、矩形選択を可能にする。
"""
import os

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QSlider, QLabel, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QUrl, QRect
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

from .region_overlay import RegionOverlay
from . import frame_grabber
from ..models.transcript_model import TranscriptRow

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
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        if not self._image.isNull():
            target = frame_grabber.fitted_target_rect(
                self._image.size(), self.width(), self.height())
            painter.drawImage(target, self._image)


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

        # コントロール
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(44)
        self.btn_play.clicked.connect(self.toggle_play)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_slider_pressed", True))
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self.time_label = QLabel("00:00.000 / 00:00.000")
        self.time_label.setMinimumWidth(160)

        controls = QHBoxLayout()
        controls.addWidget(self.btn_play)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)

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
        self.btn_play.setText("⏸" if playing else "▶")
        self.playing_changed.emit(playing)

    def _on_slider_moved(self, value: int):
        self._update_time_label(value, self.player.duration())

    def _on_slider_released(self):
        self._slider_pressed = False
        self.seek(self.slider.value())

    def _update_controls_enabled(self, enabled: bool):
        self.btn_play.setEnabled(enabled)
        self.slider.setEnabled(enabled)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        self.time_label.setText(
            f"{TranscriptRow.format_timestamp(pos_ms)} / "
            f"{TranscriptRow.format_timestamp(dur_ms)}")
