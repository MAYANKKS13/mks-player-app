"""
VLC-inspired dark theme stylesheet for PyQt5.
Features VLC signature orange accents (#FF8800), clean dark slate background,
modern sliders, styled menus, and playlist widgets.
"""

VLC_DARK_THEME = """
/* Global Window Styling */
QMainWindow {
    background-color: #1e1e1e;
    color: #f0f0f0;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-size: 12px;
}

/* Menu Bar */
QMenuBar {
    background-color: #252526;
    color: #cccccc;
    border-bottom: 1px solid #333333;
    padding: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
    border-radius: 3px;
}

QMenuBar::item:selected {
    background-color: #3e3e42;
    color: #ffffff;
}

QMenu {
    background-color: #252526;
    color: #f0f0f0;
    border: 1px solid #3f3f46;
    padding: 3px;
}

QMenu::item {
    padding: 5px 20px 5px 14px;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #ff8800;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #3e3e42;
    margin: 3px 6px;
}

/* Controls Bar Container */
#controlBar {
    background-color: #181818;
    border-top: 1px solid #282828;
    padding: 3px 8px 6px 8px;
}

/* Systematic Compact Buttons */
QPushButton {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 0px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #383838;
    border-color: #ff8800;
    color: #ff8800;
}

QPushButton:pressed {
    background-color: #e67300;
    color: #ffffff;
    border-color: #ff8800;
}

QPushButton:checked {
    background-color: #ff8800;
    color: #ffffff;
    border-color: #ff9922;
}

/* Primary Play Button */
#playBtn {
    background-color: #ff8800;
    color: #ffffff;
    border: 1px solid #e67300;
    font-size: 13px;
    font-weight: bold;
    border-radius: 3px;
}

#playBtn:hover {
    background-color: #ffa033;
    color: #ffffff;
    border-color: #ffaa33;
}

#playBtn:pressed {
    background-color: #cc6d00;
}

/* Seek Bar / Progress Slider */
QSlider::groove:horizontal {
    height: 4px;
    background: #333336;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #ff8800;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #ff8800;
    width: 10px;
    height: 10px;
    margin-top: -3px;
    margin-bottom: -3px;
    border-radius: 5px;
}

QSlider::handle:horizontal:hover {
    background: #ffaa33;
    border-color: #ffffff;
}

/* Volume Slider */
#volumeSlider::groove:horizontal {
    height: 3px;
    background: #333336;
    border-radius: 1px;
}

#volumeSlider::sub-page:horizontal {
    background: #ff8800;
    border-radius: 1px;
}

#volumeSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #ff8800;
    width: 8px;
    height: 8px;
    margin-top: -3px;
    margin-bottom: -3px;
    border-radius: 4px;
}

/* Combo Box (Speed) */
QComboBox {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 1px 3px;
    font-size: 11px;
    font-weight: 500;
}

QComboBox:hover {
    border-color: #ff8800;
}

QComboBox QAbstractItemView {
    background-color: #252526;
    color: #ffffff;
    selection-background-color: #ff8800;
    selection-color: #ffffff;
    border: 1px solid #3f3f46;
}

/* Labels */
QLabel {
    color: #aaaaaa;
}

#timeLabel {
    color: #e0e0e0;
    font-size: 11px;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-weight: bold;
    padding: 0 4px;
}

/* On-Screen Display (OSD) Notification Banner */
#osdBanner {
    background-color: rgba(20, 20, 22, 225);
    color: #ffffff;
    border: 1px solid #ff8800;
    border-radius: 4px;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 14px;
}

/* Fullscreen Floating Timeline Overlay */
#fullscreenOverlay {
    background-color: rgba(18, 18, 20, 235);
    border: 1px solid #ff8800;
    border-radius: 6px;
    padding: 2px 10px;
}

#fullscreenOverlay QLabel {
    background: transparent;
    background-color: transparent;
    color: #ffffff;
    font-size: 12px;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-weight: bold;
    padding: 0 6px;
}

#fullscreenOverlay QSlider {
    background: transparent;
    background-color: transparent;
}

/* Dialog / Playlist Styling */
QDialog {
    background-color: #1e1e1e;
    color: #f0f0f0;
}

QListWidget {
    background-color: #181818;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 4px;
    outline: none;
    padding: 4px;
}

QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #242424;
    border-radius: 3px;
}

QListWidget::item:hover {
    background-color: #2d2d30;
    color: #ffffff;
}

QListWidget::item:selected {
    background-color: #ff8800;
    color: #ffffff;
    font-weight: bold;
}

/* Status Bar */
QStatusBar {
    background-color: #141414;
    color: #888888;
    font-size: 11px;
    border-top: 1px solid #222222;
}

QStatusBar::item {
    border: none;
}

/* Tooltips */
QToolTip {
    background-color: #2d2d30;
    color: #ffffff;
    border: 1px solid #ff8800;
    padding: 3px 6px;
    border-radius: 3px;
    font-size: 11px;
}
"""
