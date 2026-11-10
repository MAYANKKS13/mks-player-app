"""
Media Engine abstraction supporting FFmpeg (ffpyplayer), QtMultimedia, and LibVLC.
"""
import os
import sys
import gc
import time
from abc import ABC, abstractmethod
from PyQt5.QtCore import QObject, pyqtSignal, QUrl, Qt, QTimer, QRect
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPainter, QImage, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget


class BaseMediaEngine(QObject):
    state_changed = pyqtSignal(str)          # 'playing', 'paused', 'stopped'
    position_changed = pyqtSignal(int)       # position in milliseconds
    duration_changed = pyqtSignal(int)       # total duration in milliseconds
    media_ended = pyqtSignal()               # playback finished
    error_occurred = pyqtSignal(str)         # error message

    def __init__(self, parent=None):
        super().__init__(parent)

    @abstractmethod
    def get_video_widget(self) -> QWidget:
        """Returns the QWidget used for video rendering."""
        pass

    @abstractmethod
    def load_media(self, source: str):
        """Loads a local file path or network URL."""
        pass

    @abstractmethod
    def play(self):
        pass

    @abstractmethod
    def pause(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def set_position(self, pos_ms: int):
        pass

    @abstractmethod
    def set_volume(self, volume: int):
        """Sets volume from 0 to 100."""
        pass

    @abstractmethod
    def set_playback_rate(self, rate: float):
        """Sets playback speed multiplier, e.g. 1.0, 1.5, 2.0."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        pass

    @abstractmethod
    def engine_name(self) -> str:
        pass

    def cycle_audio_track(self) -> str:
        return "Audio Track: Default"

    def cycle_subtitle_track(self) -> str:
        return "Subtitle Track: Default"

    def close(self):
        """Cleans up engine resources on application shutdown."""
        self.stop()


class VideoSurfaceWidget(QWidget):
    """
    High-performance video renderer that paints frames while maintaining aspect ratio.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setStyleSheet("background-color: #000000;")
        self.current_frame = None

    def set_frame(self, frame: QImage):
        self.current_frame = frame
        self.update()

    def clear(self):
        self.current_frame = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        if self.current_frame and not self.current_frame.isNull():
            fw = self.current_frame.width()
            fh = self.current_frame.height()
            ww = self.width()
            wh = self.height()

            if fw > 0 and fh > 0 and ww > 0 and wh > 0:
                aspect = fw / fh
                target_w = ww
                target_h = int(ww / aspect)
                if target_h > wh:
                    target_h = wh
                    target_w = int(wh * aspect)

                x = (ww - target_w) // 2
                y = (wh - target_h) // 2
                target_rect = QRect(x, y, target_w, target_h)
                painter.drawImage(target_rect, self.current_frame)


class FFmpegMediaEngine(BaseMediaEngine):
    """
    Universal media engine powered by FFmpeg (via ffpyplayer).
    Natively supports MKV, MP4, AVI, WebM, HEVC/x265, H.264, 5.1/7.1 audio,
    and network streams without requiring external DirectShow filters.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_widget = VideoSurfaceWidget()
        self.player = None
        self.current_source = None
        self._duration = 0
        self._volume = 0.5
        self._is_paused = True
        self._is_stopped = True
        self._loading = False
        self._current_audio_track = 1
        self._current_sub_track = 0

        # Polling timer for frame and time synchronization
        self.poll_timer = QTimer(self)
        self.poll_timer.setTimerType(Qt.PreciseTimer)
        self.poll_timer.timeout.connect(self._poll_frame)

    def get_video_widget(self) -> QWidget:
        return self.video_widget

    def load_media(self, source: str):
        self._loading = True
        self.poll_timer.stop()

        if self.player:
            try:
                self.player.set_pause(True)
                self.player.set_volume(0.0)
            except Exception:
                pass
            import time
            time.sleep(0.05)
            try:
                self.player.close_player()
            except Exception:
                pass
            self.player = None
            import gc
            gc.collect()
            time.sleep(0.4)

        self.current_source = source
        self._duration = 0
        self._is_stopped = False
        self._current_audio_track = 1
        self._current_sub_track = 0

        from ffpyplayer.player import MediaPlayer
        ff_opts = {
            'out_fmt': 'rgb24',
            'autoexit': False,
            'sync': 'audio',
            'framedrop': True,
            'af': 'volume=2.0'
        }
        try:
            self.player = MediaPlayer(source, ff_opts=ff_opts)
            self._is_paused = False
            self._is_stopped = False
            self._loading = False
            self.state_changed.emit("playing")
            self.poll_timer.start(10)
        except Exception as e:
            self._loading = False
            self.error_occurred.emit(f"Failed to open media: {e}")

    def play(self):
        if self.player and not self._loading:
            self.player.set_pause(False)
            self._is_paused = False
            self._is_stopped = False
            if not self.poll_timer.isActive():
                self.poll_timer.start(10)
            self.state_changed.emit("playing")

    def pause(self):
        if self.player and not self._loading:
            self.player.set_pause(True)
            self._is_paused = True
            self.state_changed.emit("paused")

    def stop(self):
        if self.player and not self._loading:
            try:
                self.player.set_pause(True)
                meta = self.player.get_metadata()
                if meta.get('duration') is not None:
                    self.player.seek(0.0, relative=False, accurate=False)
            except Exception:
                pass
        self._is_paused = True
        self._is_stopped = True
        self.video_widget.clear()
        self.state_changed.emit("stopped")

    def set_position(self, pos_ms: int):
        if self.player and not self._loading:
            meta = self.player.get_metadata()
            if meta.get('duration') is None:
                # Stream still probing headers, ignore premature seek
                return
            target_sec = max(0.0, pos_ms / 1000.0)
            try:
                self.player.seek(target_sec, relative=False, accurate=False)
            except Exception:
                pass
            QTimer.singleShot(30, self._poll_frame)

    def set_volume(self, volume: int):
        # Maps 0-200% volume to normalized 0.0 - 1.0 (with 2.0x audio gain filter)
        self._volume = max(0.0, min(1.0, volume / 200.0))
        if self.player and not self._loading and self._duration > 0:
            try:
                self.player.set_volume(self._volume)
            except Exception:
                pass

    def set_playback_rate(self, rate: float):
        pass

    def is_playing(self) -> bool:
        return self.player is not None and not self._is_paused and not self._is_stopped and not self._loading

    def engine_name(self) -> str:
        return "FFmpeg Universal Engine (MKV / HEVC / 5.1)"

    def cycle_audio_track(self) -> str:
        if self.player and not self._loading:
            meta = self.player.get_metadata()
            if meta.get('duration') is None:
                return "Audio Track: Loading..."
            try:
                self.player.request_channel('audio', action='cycle')
                self._current_audio_track += 1
                return f"Audio Track {self._current_audio_track}"
            except Exception:
                return "Audio Track: Switched"
        return "Audio Track: Default"

    def cycle_subtitle_track(self) -> str:
        if self.player and not self._loading:
            meta = self.player.get_metadata()
            if meta.get('duration') is None:
                return "Subtitle Track: Loading..."
            try:
                self.player.request_channel('subtitle', action='cycle')
                self._current_sub_track += 1
                return f"Subtitle Track {self._current_sub_track}"
            except Exception:
                return "Subtitle Track: Switched"
        return "Subtitle Track: Default"

    def close(self):
        self._loading = True
        self.poll_timer.stop()
        if self.player:
            try:
                self.player.close_player()
            except Exception:
                pass
            self.player = None

    def _poll_frame(self):
        if self._loading or not self.player:
            return

        # Poll duration if not yet acquired
        if self._duration == 0:
            meta = self.player.get_metadata()
            dur = meta.get('duration')
            if dur and dur > 0 and meta.get('src_vid_size') != (0, 0):
                self._duration = int(dur * 1000)
                try:
                    self.player.set_volume(self._volume)
                except Exception:
                    pass
                self.duration_changed.emit(self._duration)
            else:
                return

        try:
            frame, val = self.player.get_frame()
            if val == 'eof':
                self.poll_timer.stop()
                self._is_stopped = True
                self.state_changed.emit("stopped")
                self.media_ended.emit()
                return

            # A/V Sync Guard: Instantly drop stale frames after seek or file open
            while frame is not None:
                vid_pts = frame[1]
                aud_pts = self.player.get_pts()
                if aud_pts is not None and vid_pts < aud_pts - 0.04:
                    nxt_frame, nxt_val = self.player.get_frame()
                    if nxt_frame is not None:
                        frame = nxt_frame
                        val = nxt_val
                        continue
                    else:
                        frame = None
                        break
                break
        except Exception:
            return

        if frame is not None:
            img, pts = frame
            w, h = img.get_size()
            data = img.to_bytearray()[0]
            qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888).copy()
            self.video_widget.set_frame(qimg)
            self.position_changed.emit(int(pts * 1000))

        # Precision delay matching FFmpeg audio-video sync
        interval = 10
        if isinstance(val, (int, float)):
            if val > 0.002:
                interval = min(40, max(1, int(val * 1000)))
            else:
                interval = 2 # Next frame immediately to maintain lock
        self.poll_timer.setInterval(interval)


class QtMediaEngine(BaseMediaEngine):
    """
    Native Qt Multimedia engine using Windows Media Foundation (WMF).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.player.setVideoOutput(self.video_widget)

        self._duration = 0
        self._current_source = None

        self.player.stateChanged.connect(self._on_state_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    def get_video_widget(self) -> QWidget:
        return self.video_widget

    def load_media(self, source: str):
        self._current_source = source
        if source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://"):
            url = QUrl(source)
        else:
            url = QUrl.fromLocalFile(os.path.abspath(source))

        content = QMediaContent(url)
        self.player.setMedia(content)

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def set_position(self, pos_ms: int):
        self.player.setPosition(pos_ms)

    def set_volume(self, volume: int):
        self.player.setVolume(max(0, min(100, volume)))

    def set_playback_rate(self, rate: float):
        self.player.setPlaybackRate(rate)

    def is_playing(self) -> bool:
        return self.player.state() == QMediaPlayer.PlayingState

    def engine_name(self) -> str:
        return "Qt Media Foundation"

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.state_changed.emit("playing")
        elif state == QMediaPlayer.PausedState:
            self.state_changed.emit("paused")
        else:
            self.state_changed.emit("stopped")

    def _on_position_changed(self, pos_ms):
        self.position_changed.emit(pos_ms)

    def _on_duration_changed(self, duration_ms):
        self._duration = duration_ms
        self.duration_changed.emit(duration_ms)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.media_ended.emit()
        elif status == QMediaPlayer.InvalidMedia:
            err = self.player.errorString() or "Failed to load media or codec unsupported"
            self.error_occurred.emit(err)


class VlcMediaEngine(BaseMediaEngine):
    """
    Python-VLC engine wrapping libvlc.
    """
    def __init__(self, vlc_module, parent=None):
        super().__init__(parent)
        self.vlc = vlc_module
        self.instance = self.vlc.Instance("--no-xlib", "--quiet")
        self.player = self.instance.media_player_new()

        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")

        from PyQt5.QtCore import QTimer
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self._poll_vlc)

        self._duration = 0

    def get_video_widget(self) -> QWidget:
        return self.video_widget

    def _attach_hwnd(self):
        if sys.platform == "win32":
            self.player.set_hwnd(int(self.video_widget.winId()))
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(int(self.video_widget.winId()))
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.video_widget.winId()))

    def load_media(self, source: str):
        if source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://"):
            media = self.instance.media_new(source)
        else:
            media = self.instance.media_new(os.path.abspath(source))
        self.player.set_media(media)
        self._attach_hwnd()

    def play(self):
        self._attach_hwnd()
        self.player.play()
        self.poll_timer.start()
        self.state_changed.emit("playing")

    def pause(self):
        self.player.pause()
        self.state_changed.emit("paused")

    def stop(self):
        self.player.stop()
        self.poll_timer.stop()
        self.state_changed.emit("stopped")

    def set_position(self, pos_ms: int):
        self.player.set_time(pos_ms)

    def set_volume(self, volume: int):
        self.player.audio_set_volume(max(0, min(100, volume)))

    def set_playback_rate(self, rate: float):
        self.player.set_rate(rate)

    def is_playing(self) -> bool:
        return bool(self.player.is_playing())

    def engine_name(self) -> str:
        return "LibVLC Engine"

    def set_subtitle_file(self, subtitle_path: str):
        self.player.video_set_spu_file(os.path.abspath(subtitle_path))

    def _poll_vlc(self):
        vlc_state = self.player.get_state()
        if vlc_state == self.vlc.State.Ended:
            self.poll_timer.stop()
            self.state_changed.emit("stopped")
            self.media_ended.emit()
            return

        current_time = self.player.get_time()
        if current_time >= 0:
            self.position_changed.emit(current_time)

        duration = self.player.get_length()
        if duration > 0 and duration != self._duration:
            self._duration = duration
            self.duration_changed.emit(duration)


def try_init_vlc():
    """Tries to locate and initialize the python-vlc module."""
    try:
        possible_paths = [
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC"
        ]
        for p in possible_paths:
            if os.path.exists(os.path.join(p, "libvlc.dll")):
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(p)
                os.environ["PYTHON_VLC_LIB_PATH"] = os.path.join(p, "libvlc.dll")
                break

        import vlc
        inst = vlc.Instance("--quiet")
        if inst:
            return vlc
    except Exception:
        pass
    return None


def create_media_engine(parent=None, force_engine=None) -> BaseMediaEngine:
    """
    Factory function prioritizing the universal FFmpeg engine for complete codec support
    (MKV, HEVC/x265, 5.1 surround sound, MP4, etc.), with automatic fallbacks.
    """
    if force_engine == "vlc":
        vlc_mod = try_init_vlc()
        if vlc_mod:
            return VlcMediaEngine(vlc_mod, parent)

    if force_engine == "qt":
        return QtMediaEngine(parent)

    # 1. Primary: FFmpeg Engine (plays all video/audio formats and modern codecs)
    try:
        import ffpyplayer
        return FFmpegMediaEngine(parent)
    except Exception as e:
        print(f"Notice: ffpyplayer engine unavailable ({e}). Checking LibVLC...")

    # 2. Secondary: LibVLC
    vlc_mod = try_init_vlc()
    if vlc_mod:
        try:
            return VlcMediaEngine(vlc_mod, parent)
        except Exception:
            pass

    # 3. Tertiary: Qt DirectShow/WMF
    return QtMediaEngine(parent)
