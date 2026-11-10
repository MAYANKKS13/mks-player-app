"""
Main Player Window for the VLC-style Media Player.
"""
import os
import sys
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QFileDialog, QInputDialog,
    QAction, QMenu, QMessageBox, QComboBox, QShortcut,
    QApplication
)
from PyQt5.QtGui import QIcon, QKeySequence, QFont, QDragEnterEvent, QDropEvent, QCursor

from media_engine import create_media_engine, BaseMediaEngine
from playlist_manager import PlaylistManager, RepeatMode
from subtitle_manager import SubtitleTrack, SubtitleOverlay, EmbeddedSubtitleTrack, probe_media_streams
from playlist_dialog import PlaylistDialog


def format_time(ms: int) -> str:
    """Formats milliseconds into HH:MM:SS or MM:SS."""
    if ms < 0:
        ms = 0
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class ClickableSlider(QSlider):
    """
    QSlider subclass that immediately jumps to the clicked position
    when clicked anywhere along its length (VLC-style click-to-seek).
    """
    seek_requested = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.width()
            if w > 0:
                ratio = max(0.0, min(1.0, event.x() / float(w)))
                new_val = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
                self.setValue(new_val)
                self.seek_requested.emit(new_val)
        super().mousePressEvent(event)


class OsdBanner(QLabel):
    """
    On-Screen Display badge showing feedback for language/caption changes.
    """
    def __init__(self, parent_video_widget):
        super().__init__(parent_video_widget)
        self.setObjectName("osdBanner")
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def update_position(self):
        if self.parent():
            w = self.sizeHint().width() + 24
            h = self.sizeHint().height() + 10
            x = self.parent().width() - w - 24
            y = 24
            self.setGeometry(max(10, x), y, w, h)

    def show_message(self, text: str, duration_ms: int = 1800):
        self.setText(text)
        self.adjustSize()
        self.update_position()
        self.show()
        self.raise_()
        self.timer.start(duration_ms)


class VideoContainerWidget(QWidget):
    """
    Container for the video output widget that handles resize events,
    subtitle positioning, mouse tracking, and floating overlay alignment.
    Clicking the video does NOT pause/play; only double clicking toggles fullscreen.
    """
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setMouseTracking(True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.overlay = None
        self.fullscreen_overlay = None
        self.osd_banner = None

    def set_overlay(self, overlay: SubtitleOverlay):
        self.overlay = overlay

    def set_fullscreen_overlay(self, fs_overlay: QWidget):
        self.fullscreen_overlay = fs_overlay

    def set_osd_banner(self, banner: OsdBanner):
        self.osd_banner = banner

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overlay and self.overlay.isVisible():
            self.overlay.update_position(self.width(), self.height())

        if self.osd_banner and self.osd_banner.isVisible():
            self.osd_banner.update_position()

        # Keep floating fullscreen overlay centered at the bottom without altering video size
        if self.fullscreen_overlay:
            w = min(int(self.width() * 0.72), 850)
            h = 36
            x = (self.width() - w) // 2
            y = self.height() - h - 25
            self.fullscreen_overlay.setGeometry(max(10, x), max(10, y), w, h)

    def mouseDoubleClickEvent(self, event):
        if self.parent_window:
            self.parent_window._toggle_fullscreen()

    def mouseMoveEvent(self, event):
        if self.parent_window:
            self.parent_window._on_user_activity()
        super().mouseMoveEvent(event)


class PlayerWindow(QMainWindow):
    def __init__(self, initial_source=None):
        super().__init__()
        self.setWindowTitle("MKS Player")
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        # Calculate safe initial geometry accounting for Windows taskbar
        screen = QApplication.primaryScreen().availableGeometry()
        init_w = min(1040, max(680, int(screen.width() * 0.8)))
        init_h = min(640, max(440, int(screen.height() * 0.78)))
        init_x = screen.left() + (screen.width() - init_w) // 2
        init_y = screen.top() + (screen.height() - init_h) // 2
        self.setGeometry(init_x, init_y, init_w, init_h)
        self.setMinimumSize(540, 340)

        # Core state
        self.playlist = PlaylistManager(self)
        self.playlist_dialog = None
        self.active_subtitle_track = None
        self.external_subtitle_track = None
        self.audio_track_names = []
        self.embedded_sub_tracks = []
        self.current_audio_track_idx = 0
        self.current_sub_choice_idx = -1
        self.cached_sub_tracks = {}
        self.show_remaining_time = False
        self.is_seeking = False
        self.last_volume = 100

        # Fullscreen auto-hide timer (VLC-style)
        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.setSingleShot(True)
        self.fullscreen_timer.setInterval(2500)
        self.fullscreen_timer.timeout.connect(self._on_fullscreen_timeout)

        # Setup UI
        self._init_engine()
        self._init_ui()
        self._init_menus()
        self._init_shortcuts()
        self._wire_signals()

        # Set default volume (100% standard line level)
        self.engine.set_volume(100)
        self.vol_slider.setValue(100)

        # Initial source if passed via CLI
        if initial_source:
            self.playlist.add_item(initial_source)
            self._play_track_index(0)

        self._update_playlist_buttons_visibility()

    def _init_engine(self):
        self.engine: BaseMediaEngine = create_media_engine(self)

    def _init_ui(self):
        # Main central widget (Video takes full screen, controls at bottom)
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Video Container (Full 100% width)
        self.video_container = VideoContainerWidget(self)
        video_output = self.engine.get_video_widget()
        video_output.setMouseTracking(True)
        self.video_container.layout.addWidget(video_output)

        # Subtitle overlay
        self.subtitle_overlay = SubtitleOverlay(self.video_container)
        self.video_container.set_overlay(self.subtitle_overlay)

        # OSD Banner for Track/Language feedback
        self.osd_banner = OsdBanner(self.video_container)
        self.video_container.set_osd_banner(self.osd_banner)

        # Floating Fullscreen Timeline Overlay (Appears on mouse move in fullscreen only)
        self.fullscreen_overlay = QWidget(self.video_container)
        self.fullscreen_overlay.setObjectName("fullscreenOverlay")
        self.fullscreen_overlay.setMouseTracking(True)
        fs_layout = QHBoxLayout(self.fullscreen_overlay)
        fs_layout.setContentsMargins(10, 2, 10, 2)
        fs_layout.setSpacing(8)

        self.fs_time_current = QLabel("00:00")
        self.fs_time_current.setObjectName("timeLabel")
        self.fs_time_current.setStyleSheet("background: transparent; color: #ffffff; font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;")

        self.fs_seek_slider = ClickableSlider(Qt.Horizontal)
        self.fs_seek_slider.setRange(0, 1000)
        self.fs_seek_slider.setValue(0)
        self.fs_seek_slider.setTracking(True)
        self.fs_seek_slider.setFocusPolicy(Qt.NoFocus)
        self.fs_seek_slider.setStyleSheet("background: transparent;")
        self.fs_seek_slider.seek_requested.connect(self._on_seek_direct)
        self.fs_seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.fs_seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.fs_seek_slider.sliderReleased.connect(self._on_seek_released)

        self.fs_time_total = QLabel("00:00")
        self.fs_time_total.setObjectName("timeLabel")
        self.fs_time_total.setCursor(Qt.PointingHandCursor)
        self.fs_time_total.setToolTip("Click to toggle remaining / total time")
        self.fs_time_total.setStyleSheet("background: transparent; color: #ffffff; font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;")
        self.fs_time_total.mousePressEvent = self._toggle_time_display_mode

        fs_layout.addWidget(self.fs_time_current)
        fs_layout.addWidget(self.fs_seek_slider, stretch=1)
        fs_layout.addWidget(self.fs_time_total)

        self.video_container.set_fullscreen_overlay(self.fullscreen_overlay)
        self.fullscreen_overlay.hide()

        main_layout.addWidget(self.video_container, stretch=1)

        # 2. Normal View Control Bar (Edge-to-edge, compact, systematic)
        self.control_bar = QWidget(self)
        self.control_bar.setObjectName("controlBar")
        self.control_bar.setMouseTracking(True)
        control_layout = QVBoxLayout(self.control_bar)
        control_layout.setContentsMargins(10, 4, 10, 6)
        control_layout.setSpacing(4)

        # Progress / Timeline Row
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(8)

        self.time_label_current = QLabel("00:00")
        self.time_label_current.setObjectName("timeLabel")

        # Custom ClickableSlider for instant click-to-seek
        self.seek_slider = ClickableSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setTracking(True)
        self.seek_slider.seek_requested.connect(self._on_seek_direct)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)

        self.time_label_total = QLabel("00:00")
        self.time_label_total.setObjectName("timeLabel")
        self.time_label_total.setCursor(Qt.PointingHandCursor)
        self.time_label_total.setToolTip("Click to toggle remaining / total time")
        self.time_label_total.mousePressEvent = self._toggle_time_display_mode

        progress_row.addWidget(self.time_label_current)
        progress_row.addWidget(self.seek_slider, stretch=1)
        progress_row.addWidget(self.time_label_total)
        control_layout.addLayout(progress_row)

        # Transport & Volume Row (Uniform 26px height, compact, no collisions)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(5)

        # Prev Track (28x26) - Hidden when only 1 track
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(28, 26)
        self.prev_btn.setToolTip("Previous Track (P)")
        self.prev_btn.clicked.connect(self._on_prev_track)

        # Rewind 10s (28x26)
        self.rewind_btn = QPushButton("⟲")
        self.rewind_btn.setFixedSize(28, 26)
        self.rewind_btn.setToolTip("Rewind 10 seconds (Left Arrow)")
        self.rewind_btn.clicked.connect(lambda: self._seek_relative(-10000))

        # Play / Pause (34x26)
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setFixedSize(34, 26)
        self.play_btn.setToolTip("Play / Pause (Space)")
        self.play_btn.clicked.connect(self._toggle_play)

        # Stop (28x26)
        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(28, 26)
        self.stop_btn.setToolTip("Stop Playback (S)")
        self.stop_btn.clicked.connect(self._on_stop)

        # Forward 10s (28x26)
        self.forward_btn = QPushButton("⟳")
        self.forward_btn.setFixedSize(28, 26)
        self.forward_btn.setToolTip("Forward 10 seconds (Right Arrow)")
        self.forward_btn.clicked.connect(lambda: self._seek_relative(10000))

        # Next Track (28x26) - Hidden when only 1 track
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(28, 26)
        self.next_btn.setToolTip("Next Track (N)")
        self.next_btn.clicked.connect(self._on_next_track)

        btn_row.addWidget(self.prev_btn)
        btn_row.addWidget(self.rewind_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.forward_btn)
        btn_row.addWidget(self.next_btn)

        btn_row.addSpacing(10)

        # Volume Controls (0% - 200% VLC style)
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(28, 26)
        self.mute_btn.setToolTip("Mute / Unmute (M)")
        self.mute_btn.clicked.connect(self._toggle_mute)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("volumeSlider")
        self.vol_slider.setRange(0, 200)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedSize(75, 16)
        self.vol_slider.setToolTip("Volume: 100%")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        btn_row.addWidget(self.mute_btn)
        btn_row.addWidget(self.vol_slider)

        # Spacer between left controls and right controls
        btn_row.addStretch(1)

        # Speed Dropdown (54x26)
        self.speed_combo = QComboBox()
        self.speed_combo.setToolTip("Playback Speed")
        self.speed_combo.setFixedSize(54, 26)
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        btn_row.addWidget(self.speed_combo)

        # Subtitle Button (30x26)
        self.sub_btn = QPushButton("CC")
        self.sub_btn.setFixedSize(30, 26)
        self.sub_btn.setToolTip("Load Subtitle File (Ctrl+S)")
        self.sub_btn.clicked.connect(self._open_subtitle_dialog)
        btn_row.addWidget(self.sub_btn)

        # Playlist Button (28x26)
        self.playlist_btn = QPushButton("☰")
        self.playlist_btn.setFixedSize(28, 26)
        self.playlist_btn.setToolTip("Playlist Queue (Ctrl+L)")
        self.playlist_btn.clicked.connect(self._toggle_playlist_dialog)
        btn_row.addWidget(self.playlist_btn)

        # Fullscreen Button (28x26)
        self.fs_btn = QPushButton("⛶")
        self.fs_btn.setFixedSize(28, 26)
        self.fs_btn.setToolTip("Toggle Fullscreen (F)")
        self.fs_btn.clicked.connect(self._toggle_fullscreen)
        btn_row.addWidget(self.fs_btn)

        # Prevent buttons/controls from stealing Spacebar keyboard focus
        for control in [
            self.prev_btn, self.rewind_btn, self.play_btn, self.stop_btn,
            self.forward_btn, self.next_btn, self.mute_btn, self.vol_slider,
            self.seek_slider, self.speed_combo, self.sub_btn,
            self.playlist_btn, self.fs_btn
        ]:
            control.setFocusPolicy(Qt.NoFocus)

        control_layout.addLayout(btn_row)
        main_layout.addWidget(self.control_bar)

    def _init_menus(self):
        menubar = self.menuBar()

        # Media Menu
        media_menu = menubar.addMenu("&Media")
        open_file_act = QAction("Open &File...", self)
        open_file_act.setShortcut(QKeySequence("Ctrl+O"))
        open_file_act.triggered.connect(self._open_file_dialog)
        media_menu.addAction(open_file_act)

        open_multiple_act = QAction("Open &Multiple Files...", self)
        open_multiple_act.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_multiple_act.triggered.connect(self._open_multiple_files_dialog)
        media_menu.addAction(open_multiple_act)

        open_stream_act = QAction("Open &Network Stream...", self)
        open_stream_act.setShortcut(QKeySequence("Ctrl+N"))
        open_stream_act.triggered.connect(self._open_stream_dialog)
        media_menu.addAction(open_stream_act)

        media_menu.addSeparator()
        pl_act = QAction("Show &Playlist", self)
        pl_act.setShortcut(QKeySequence("Ctrl+L"))
        pl_act.triggered.connect(self._toggle_playlist_dialog)
        media_menu.addAction(pl_act)

        media_menu.addSeparator()
        exit_act = QAction("&Quit", self)
        exit_act.setShortcut(QKeySequence("Ctrl+Q"))
        exit_act.triggered.connect(self.close)
        media_menu.addAction(exit_act)

        # Playback Menu
        pb_menu = menubar.addMenu("&Playback")
        play_act = QAction("&Play / Pause", self)
        play_act.setShortcut(Qt.Key_Space)
        play_act.triggered.connect(self._toggle_play)
        pb_menu.addAction(play_act)

        stop_act = QAction("&Stop", self)
        stop_act.setShortcut(Qt.Key_S)
        stop_act.triggered.connect(self._on_stop)
        pb_menu.addAction(stop_act)

        pb_menu.addSeparator()
        next_act = QAction("&Next", self)
        next_act.setShortcut(Qt.Key_N)
        next_act.triggered.connect(self._on_next_track)
        pb_menu.addAction(next_act)

        prev_act = QAction("&Previous", self)
        prev_act.setShortcut(Qt.Key_P)
        prev_act.triggered.connect(self._on_prev_track)
        pb_menu.addAction(prev_act)

        pb_menu.addSeparator()
        jump_fwd = QAction("Jump Forward 10s", self)
        jump_fwd.setShortcut(Qt.Key_Right)
        jump_fwd.setShortcutContext(Qt.ApplicationShortcut)
        jump_fwd.triggered.connect(lambda: self._seek_relative(10000))
        pb_menu.addAction(jump_fwd)

        jump_bwd = QAction("Jump Backward 10s", self)
        jump_bwd.setShortcut(Qt.Key_Left)
        jump_bwd.setShortcutContext(Qt.ApplicationShortcut)
        jump_bwd.triggered.connect(lambda: self._seek_relative(-10000))
        pb_menu.addAction(jump_bwd)

        # Audio Menu
        audio_menu = menubar.addMenu("&Audio")
        mute_act = QAction("&Mute", self)
        mute_act.setShortcut(Qt.Key_M)
        mute_act.setShortcutContext(Qt.ApplicationShortcut)
        mute_act.triggered.connect(self._toggle_mute)
        audio_menu.addAction(mute_act)

        vol_up = QAction("Volume &Up", self)
        vol_up.setShortcut(Qt.Key_Up)
        vol_up.setShortcutContext(Qt.ApplicationShortcut)
        vol_up.triggered.connect(lambda: self._adjust_volume(5))
        audio_menu.addAction(vol_up)

        vol_down = QAction("Volume &Down", self)
        vol_down.setShortcut(Qt.Key_Down)
        vol_down.setShortcutContext(Qt.ApplicationShortcut)
        vol_down.triggered.connect(lambda: self._adjust_volume(-5))
        audio_menu.addAction(vol_down)

        cycle_audio_act = QAction("Cycle &Audio Track / Language", self)
        cycle_audio_act.setShortcut(Qt.Key_V)
        cycle_audio_act.setShortcutContext(Qt.ApplicationShortcut)
        cycle_audio_act.triggered.connect(self._on_cycle_audio)
        audio_menu.addAction(cycle_audio_act)

        # Video Menu
        video_menu = menubar.addMenu("&Video")
        fs_act = QAction("&Fullscreen", self)
        fs_act.setShortcut(Qt.Key_F)
        fs_act.setShortcutContext(Qt.ApplicationShortcut)
        fs_act.triggered.connect(self._toggle_fullscreen)
        video_menu.addAction(fs_act)

        # Subtitle Menu
        sub_menu = menubar.addMenu("&Subtitle")
        add_sub_act = QAction("&Add Subtitle File...", self)
        add_sub_act.setShortcut(QKeySequence("Ctrl+S"))
        add_sub_act.triggered.connect(self._open_subtitle_dialog)
        sub_menu.addAction(add_sub_act)

        cycle_sub_act = QAction("Cycle &Caption Track", self)
        cycle_sub_act.setShortcut(Qt.Key_C)
        cycle_sub_act.setShortcutContext(Qt.ApplicationShortcut)
        cycle_sub_act.triggered.connect(self._on_cycle_captions)
        sub_menu.addAction(cycle_sub_act)

        # View Menu
        view_menu = menubar.addMenu("&View")
        toggle_pl_act = QAction("&Playlist", self)
        toggle_pl_act.setShortcut(QKeySequence("Ctrl+L"))
        toggle_pl_act.triggered.connect(self._toggle_playlist_dialog)
        view_menu.addAction(toggle_pl_act)

        always_top_act = QAction("&Always on Top", self, checkable=True)
        always_top_act.triggered.connect(self._toggle_always_on_top)
        view_menu.addAction(always_top_act)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        about_act = QAction("&About VLC Python Player", self)
        about_act.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_act)

    def _init_shortcuts(self):
        # Escape key exits fullscreen
        esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_shortcut.setContext(Qt.ApplicationShortcut)
        esc_shortcut.activated.connect(self._exit_fullscreen)

    def keyPressEvent(self, event):
        # Guarantee all media playback keys work everywhere in both normal and fullscreen
        key = event.key()
        if key == Qt.Key_Space:
            self._toggle_play()
            event.accept()
            return
        elif key == Qt.Key_F:
            self._toggle_fullscreen()
            event.accept()
            return
        elif key == Qt.Key_Escape:
            if self.isFullScreen():
                self._exit_fullscreen()
                event.accept()
                return
        elif key == Qt.Key_Left:
            self._seek_relative(-10000)
            if self.isFullScreen():
                self._on_user_activity()
            event.accept()
            return
        elif key == Qt.Key_Right:
            self._seek_relative(10000)
            if self.isFullScreen():
                self._on_user_activity()
            event.accept()
            return
        elif key == Qt.Key_Up:
            self._adjust_volume(5)
            event.accept()
            return
        elif key == Qt.Key_Down:
            self._adjust_volume(-5)
            event.accept()
            return
        elif key == Qt.Key_M:
            self._toggle_mute()
            event.accept()
            return
        elif key == Qt.Key_N:
            self._on_next_track()
            event.accept()
            return
        elif key == Qt.Key_P:
            self._on_prev_track()
            event.accept()
            return
        elif key == Qt.Key_C:
            self._on_cycle_captions()
            event.accept()
            return
        elif key == Qt.Key_V:
            self._on_cycle_audio()
            event.accept()
            return
        super().keyPressEvent(event)

    def _wire_signals(self):
        self.engine.state_changed.connect(self._on_engine_state_changed)
        self.engine.position_changed.connect(self._on_engine_position_changed)
        self.engine.duration_changed.connect(self._on_engine_duration_changed)
        self.engine.media_ended.connect(self._on_engine_media_ended)
        self.playlist.track_changed.connect(self._on_track_changed)
        self.playlist.playlist_changed.connect(self._update_playlist_buttons_visibility)

    def _update_playlist_buttons_visibility(self):
        has_multiple = self.playlist.count() > 1
        self.prev_btn.setVisible(has_multiple)
        self.next_btn.setVisible(has_multiple)

    # --- Mouse Tracking & Fullscreen Floating Overlay ---
    def mouseMoveEvent(self, event):
        self._on_user_activity()
        super().mouseMoveEvent(event)

    def _on_user_activity(self):
        if self.isFullScreen():
            self.setCursor(Qt.ArrowCursor)
            self.video_container.setCursor(Qt.ArrowCursor)
            if not self.fullscreen_overlay.isVisible():
                self.fullscreen_overlay.show()
                self.fullscreen_overlay.raise_()
            self.fullscreen_timer.start(2500)

    def _on_fullscreen_timeout(self):
        if self.isFullScreen():
            # If user is hovering over the timeline overlay, don't hide it yet
            if not self.fullscreen_overlay.underMouse():
                self.fullscreen_overlay.hide()
                self.setCursor(Qt.BlankCursor)
                self.video_container.setCursor(Qt.BlankCursor)
            else:
                self.fullscreen_timer.start(1500)

    # --- Fullscreen Logic ---
    def _toggle_fullscreen(self, event=None):
        if self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        self.menuBar().hide()
        self.control_bar.hide()
        self.fullscreen_overlay.hide()
        self.showFullScreen()
        self.fs_btn.setText("🗗")
        self.fs_btn.setToolTip("Exit Fullscreen (F / Esc)")
        self.fullscreen_timer.start(2000)

    def _exit_fullscreen(self):
        self.fullscreen_timer.stop()
        self.setCursor(Qt.ArrowCursor)
        self.video_container.setCursor(Qt.ArrowCursor)
        self.fullscreen_overlay.hide()
        self.showNormal()
        self.menuBar().show()
        self.control_bar.show()
        self.fs_btn.setText("⛶")
        self.fs_btn.setToolTip("Fullscreen (F)")

    def _toggle_always_on_top(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        files_to_add = []
        sub_file = None
        for u in urls:
            fpath = u.toLocalFile()
            if os.path.isfile(fpath):
                ext = os.path.splitext(fpath)[1].lower()
                if ext in ['.srt', '.vtt']:
                    sub_file = fpath
                else:
                    files_to_add.append(fpath)

        if sub_file:
            self._load_subtitle(sub_file)

        if files_to_add:
            start_index = self.playlist.count()
            self.playlist.add_items(files_to_add)
            self._update_playlist_buttons_visibility()
            if not self.engine.is_playing() and self.playlist.current_index() == -1:
                self._play_track_index(start_index)

    # --- Engine Callbacks ---
    def _on_engine_state_changed(self, state: str):
        if state == "playing":
            self.play_btn.setText("❚❚")
            self.play_btn.setToolTip("Pause (Space)")
        elif state == "paused":
            self.play_btn.setText("▶")
            self.play_btn.setToolTip("Play (Space)")
        else:
            self.play_btn.setText("▶")
            self.play_btn.setToolTip("Play (Space)")
            self.seek_slider.setValue(0)
            self.fs_seek_slider.setValue(0)
            self.time_label_current.setText("00:00")
            self.fs_time_current.setText("00:00")
            self.subtitle_overlay.set_subtitle(None, self.video_container.width(), self.video_container.height())

    def _on_engine_position_changed(self, pos_ms: int):
        if not self.is_seeking:
            dur = self.seek_slider.maximum()
            if dur > 0:
                self.seek_slider.setValue(pos_ms)
                self.fs_seek_slider.setValue(pos_ms)
            formatted = format_time(pos_ms)
            self.time_label_current.setText(formatted)
            self.fs_time_current.setText(formatted)
            self._update_time_label_total(dur, pos_ms)

        # Update subtitles
        if self.active_subtitle_track:
            text = self.active_subtitle_track.get_text_at(pos_ms)
            self.subtitle_overlay.set_subtitle(text, self.video_container.width(), self.video_container.height())

    def _on_engine_duration_changed(self, duration_ms: int):
        self.seek_slider.setRange(0, duration_ms)
        self.fs_seek_slider.setRange(0, duration_ms)
        self._update_time_label_total(duration_ms, self.seek_slider.value())

    def _update_time_label_total(self, duration_ms: int, current_pos_ms: int):
        if self.show_remaining_time:
            remaining = max(0, duration_ms - current_pos_ms)
            text = f"-{format_time(remaining)}"
        else:
            text = format_time(duration_ms)
        self.time_label_total.setText(text)
        self.fs_time_total.setText(text)

    def _on_engine_media_ended(self):
        next_item = self.playlist.next_track()
        if next_item:
            self._load_and_play_item(next_item)
        else:
            self.engine.stop()

    # --- Controls Handlers ---
    def _toggle_play(self):
        if self.engine.is_playing():
            self.engine.pause()
        else:
            if self.playlist.current_index() == -1 and self.playlist.count() > 0:
                self._play_track_index(0)
            else:
                self.engine.play()

    def _on_stop(self):
        self.engine.stop()

    def _seek_relative(self, delta_ms: int):
        cur = self.seek_slider.value()
        dur = self.seek_slider.maximum()
        new_pos = max(0, min(dur, cur + delta_ms))
        self.seek_slider.setValue(new_pos)
        self.fs_seek_slider.setValue(new_pos)
        formatted = format_time(new_pos)
        self.time_label_current.setText(formatted)
        self.fs_time_current.setText(formatted)
        self.engine.set_position(new_pos)

    def _on_seek_direct(self, target_ms: int):
        """Called when user clicks directly on either seek bar."""
        formatted = format_time(target_ms)
        self.time_label_current.setText(formatted)
        self.fs_time_current.setText(formatted)
        self.seek_slider.setValue(target_ms)
        self.fs_seek_slider.setValue(target_ms)
        self.engine.set_position(target_ms)

    def _on_seek_pressed(self):
        self.is_seeking = True

    def _on_seek_moved(self, value):
        formatted = format_time(value)
        self.time_label_current.setText(formatted)
        self.fs_time_current.setText(formatted)

    def _on_seek_released(self):
        self.is_seeking = False
        target_ms = self.seek_slider.value()
        self.engine.set_position(target_ms)

    def _toggle_time_display_mode(self, event):
        self.show_remaining_time = not self.show_remaining_time
        dur = self.seek_slider.maximum()
        pos = self.seek_slider.value()
        self._update_time_label_total(dur, pos)

    def _on_volume_changed(self, value):
        self.engine.set_volume(value)
        self.vol_slider.setToolTip(f"Volume: {value}%")
        if value == 0:
            self.mute_btn.setText("🔇")
        elif value <= 100:
            self.mute_btn.setText("🔊")
        else:
            self.mute_btn.setText("📢")

    def _toggle_mute(self):
        if self.vol_slider.value() > 0:
            self.last_volume = self.vol_slider.value()
            self.vol_slider.setValue(0)
            self.osd_banner.show_message("🔇 Volume: Muted", 1200)
        else:
            vol = self.last_volume if self.last_volume > 0 else 100
            self.vol_slider.setValue(vol)
            icon = "🔊" if vol <= 100 else "📢"
            self.osd_banner.show_message(f"{icon} Volume: {vol}%", 1200)

    def _adjust_volume(self, delta: int):
        new_vol = max(0, min(200, self.vol_slider.value() + delta))
        self.vol_slider.setValue(new_vol)
        icon = "🔇" if new_vol == 0 else ("🔊" if new_vol <= 100 else "📢")
        self.osd_banner.show_message(f"{icon} Volume: {new_vol}%", 1200)

    def _on_speed_changed(self):
        speed_text = self.speed_combo.currentText().replace("x", "")
        try:
            rate = float(speed_text)
            self.engine.set_playback_rate(rate)
        except ValueError:
            pass

    def _on_cycle_audio(self):
        msg = self.engine.cycle_audio_track()
        if self.audio_track_names:
            self.current_audio_track_idx = (self.current_audio_track_idx + 1) % len(self.audio_track_names)
            track_name = self.audio_track_names[self.current_audio_track_idx]
            self.osd_banner.show_message(f"🔊 Audio: {track_name}")
        else:
            self.osd_banner.show_message(f"🔊 {msg}")

    def _on_cycle_captions(self):
        choices = []
        if self.external_subtitle_track:
            choices.append(('external', self.external_subtitle_track.track_title, self.external_subtitle_track))
        for sub_info in self.embedded_sub_tracks:
            choices.append(('embedded', sub_info['title'], sub_info['index']))
        choices.append(('off', 'Off', None))

        if not choices:
            self.osd_banner.show_message("💬 Subtitles: None available")
            return

        self.current_sub_choice_idx = (self.current_sub_choice_idx + 1) % len(choices)
        choice_type, title, ref = choices[self.current_sub_choice_idx]

        if choice_type == 'off':
            self.active_subtitle_track = None
            self.subtitle_overlay.hide()
            self.osd_banner.show_message("💬 Subtitles: Off")
        elif choice_type == 'external':
            self.active_subtitle_track = ref
            self.subtitle_overlay.show()
            self.osd_banner.show_message(f"💬 Subtitles: {title}")
        elif choice_type == 'embedded':
            stream_idx = ref
            cur_item = self.playlist.current_item()
            if stream_idx not in self.cached_sub_tracks and cur_item:
                self.cached_sub_tracks[stream_idx] = EmbeddedSubtitleTrack(cur_item["source"], stream_idx, title)
            self.active_subtitle_track = self.cached_sub_tracks.get(stream_idx)
            self.subtitle_overlay.show()
            self.osd_banner.show_message(f"💬 Subtitles: {title}")

    # --- Playlist & Track Handlers ---
    def _toggle_playlist_dialog(self):
        if self.playlist_dialog is None:
            self.playlist_dialog = PlaylistDialog(self.playlist, self)
        if self.playlist_dialog.isVisible():
            self.playlist_dialog.hide()
        else:
            self.playlist_dialog.sync_list()
            self.playlist_dialog.show()
            self.playlist_dialog.raise_()
            self.playlist_dialog.activateWindow()

    def _on_track_changed(self, index: int, item: dict):
        self.setWindowTitle(f"{item['title']} - MKS Player")
        self._update_playlist_buttons_visibility()

    def _play_track_index(self, index: int):
        item = self.playlist.set_current_index(index)
        if item:
            self._load_and_play_item(item)

    def _load_and_play_item(self, item: dict):
        self.engine.load_media(item["source"])
        self.engine.play()

        # Probe audio and subtitle streams
        self.audio_track_names, self.embedded_sub_tracks = probe_media_streams(item["source"])
        self.current_audio_track_idx = 0
        self.current_sub_choice_idx = -1
        self.cached_sub_tracks.clear()
        self.external_subtitle_track = None
        self.active_subtitle_track = None
        self.subtitle_overlay.hide()

        # Check for matching subtitle file alongside local video
        if not item["is_url"]:
            video_dir = os.path.dirname(item["source"])
            base_name = os.path.splitext(os.path.basename(item["source"]))[0]
            for ext in ['.srt', '.vtt']:
                sub_candidate = os.path.join(video_dir, base_name + ext)
                if os.path.exists(sub_candidate):
                    self._load_subtitle(sub_candidate)
                    break

    def _on_prev_track(self):
        item = self.playlist.prev_track()
        if item:
            self._load_and_play_item(item)

    def _on_next_track(self):
        item = self.playlist.next_track()
        if item:
            self._load_and_play_item(item)

    # --- Dialogs ---
    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video or Audio File",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.mp3 *.wav *.aac *.m4a);;All Files (*.*)"
        )
        if file_path:
            idx = self.playlist.add_item(file_path)
            self._update_playlist_buttons_visibility()
            self._play_track_index(idx)

    def _open_multiple_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Multiple Media Files",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.mp3 *.wav *.aac *.m4a);;All Files (*.*)"
        )
        if files:
            was_empty = self.playlist.count() == 0
            self.playlist.add_items(files)
            self._update_playlist_buttons_visibility()
            if was_empty:
                self._play_track_index(0)

    def _open_stream_dialog(self):
        url, ok = QInputDialog.getText(
            self,
            "Open Network Stream",
            "Enter Network URL (e.g. https://... or rtsp://...):"
        )
        if ok and url.strip():
            idx = self.playlist.add_item(url.strip())
            self._update_playlist_buttons_visibility()
            self._play_track_index(idx)

    def _open_subtitle_dialog(self):
        sub_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            "Subtitle Files (*.srt *.vtt);;All Files (*.*)"
        )
        if sub_path:
            self._load_subtitle(sub_path)

    def _load_subtitle(self, path: str):
        self.external_subtitle_track = SubtitleTrack(path)
        self.active_subtitle_track = self.external_subtitle_track
        self.subtitle_overlay.show()
        sub_name = os.path.basename(path)
        self.osd_banner.show_message(f"💬 Subtitles: {sub_name}")

    def _show_about_dialog(self):
        QMessageBox.about(
            self,
            "About MKS Player",
            "<h3>MKS Player</h3>"
            "<p>A modern, lightweight desktop media player featuring:</p>"
            "<ul>"
            "<li>Universal FFmpeg Engine (MKV, HEVC/x265, 5.1 Surround, MP4, AVI, WebM)</li>"
            "<li>Pure Full-screen cinematic playback with floating timer overlay</li>"
            "<li>Distraction-free 100% video display</li>"
            "<li>Detachable playlist queue with repeat and shuffle</li>"
            "<li>Custom SRT/VTT Subtitle rendering</li>"
            "<li>Full keyboard shortcut control</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        if self.playlist_dialog:
            self.playlist_dialog.close()
        self.engine.close()
        super().closeEvent(event)
