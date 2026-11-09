"""
VLC-style Media Player Entry Point
"""
import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from styles import VLC_DARK_THEME
from player_window import PlayerWindow


def main():
    # Enable Windows 1ms high-precision multimedia timer for frame-perfect A/V sync
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MKS Player")
    app.setStyleSheet(VLC_DARK_THEME)

    initial_file = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.exists(arg) or arg.startswith("http://") or arg.startswith("https://") or arg.startswith("rtsp://"):
            initial_file = arg

    window = PlayerWindow(initial_source=initial_file)
    window.show()

    ret = app.exec_()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
    sys.exit(ret)


if __name__ == "__main__":
    main()
