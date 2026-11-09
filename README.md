# MKS Player

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![GUI: PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Engine: FFmpeg](https://img.shields.io/badge/Engine-FFmpeg-red.svg)](https://ffmpeg.org/)

**MKS Player** is a modern, lightweight, open-source desktop media player application inspired by **VLC Media Player**, built with **Python**, **PyQt5**, and the **FFmpeg** multimedia engine.

---

## ✨ Features

- **📢 Volume Boost**:
  - Boosts audio volume past 100% up to **200%** using the Up Arrow (`↑`) key or slider, giving quiet movies and dialogue an extra boost.
  - Real-time on-screen display (OSD) feedback in the top-right corner shows exact volume percentage (`🔊 Volume: 100%`, `📢 Volume: 150%`, `📢 Volume: 200%`).
- **🌐 Multi-Audio & Dual-Language Switching (`V`)**:
  - Dynamically cycle through multiple language tracks embedded in dual-audio and multi-track movies (e.g., English, Japanese, Hindi) on-the-fly with OSD feedback.
- **💬 Caption & Subtitle Cycling (`C`)**:
  - Automatically detects and cycles through embedded subtitle streams (`English`, `Forced`, `SDH`) and external `.srt` / `.vtt` subtitles with on-screen OSD feedback.
- **🍿 True VLC-Style Fullscreen (`F`)**:
  - Fullscreen hides all menus and controls for a pure cinematic experience.
  - Moving the mouse brings up a floating timeline capsule over the video that smoothly auto-hides after 2.5 seconds—**with zero screen jitter or resizing**.
  - Pressing `F` or `Esc` returns to normal view instantly.
- **🎯 Instant Click-to-Seek**:
  - Click anywhere along the timeline to jump immediately to that timestamp without needing to drag.
- **📜 Distraction-Free 100% Video Display & Detachable Playlist**:
  - Full-width video screen with no bulky permanent sidebars.
  - Detachable playlist queue accessible via `Ctrl+L` or the `☰` toolbar button.
  - Previous and Next buttons automatically hide when only one video is in the queue.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :---: | :--- |
| **`Space`** | Play / Pause |
| **`F`** / **`Esc`** | Toggle Fullscreen / Return to Normal View |
| **`V`** | **Cycle Audio / Language Tracks** (for Dual Audio movies) |
| **`C`** | **Cycle Captions / Subtitle Tracks** |
| **`→`** / **`←`** | Jump Forward / Backward 10 seconds |
| **`↑`** / **`↓`** | **Volume Up / Down** (boosts up to 200%) |
| **`M`** | Mute / Unmute Audio |
| **`S`** | Stop Playback |
| **`N`** | Next Track *(visible when playlist > 1)* |
| **`P`** | Previous Track *(visible when playlist > 1)* |
| **`Ctrl + L`** | Open / Close Playlist Queue Window |
| **`Ctrl + O`** | Open File |
| **`Ctrl + Shift + O`** | Open Multiple Files |
| **`Ctrl + N`** | Open Network Stream |
| **`Ctrl + S`** | Load Subtitle File (`.srt`, `.vtt`) |
| **`Ctrl + Q`** | Quit Application |

---

## 🚀 Quick Start for Developers (Running from Source)

If you have Python installed and want to run or contribute to the project:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mks-player-app.git
   cd mks-player-app
   ```

2. **Install dependencies** (similar to `npm install` in Node.js):
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the player**:
   ```bash
   python main.py
   ```

4. **Launch directly with a movie file**:
   ```bash
   python main.py "path/to/movie.mkv"
   ```

5. **Run automated test suite**:
   ```bash
   python -m unittest -v test_player.py
   ```

---

## 📦 Downloads (Pre-Compiled Windows Executables)

If you just want to run **MKS Player** on Windows without installing Python or using a terminal:

1. Head to the **[Releases](https://github.com/MAYANKKS13/mks-player-app/releases)** page.
2. Under the **v1.0.0** release assets, choose the package that fits your needs:
   - **`MKS-Player-v1.0.0-Portable.zip`** *(Folder version)*: Extract and double-click `MKS-Player.exe`. Recommended for daily use due to instant startup (~0.1s).
   - **`MKS-Player-v1.0.0-Standalone.zip`** *(Single-file version)*: A single self-contained `MKS-Player.exe` file. Recommended if you want a single file to copy to a USB drive or share with friends.
3. Both packages include the complete Python runtime, Qt GUI, and FFmpeg engine—no external codecs or installations required!

---

## 🛠️ Building the Standalone Executable

To compile the application into a standalone `.exe` using PyInstaller:

```bash
# Single-file standalone executable:
pyinstaller --onefile --noconsole --name "MKS-Player" --hidden-import "ffpyplayer" --hidden-import "ffpyplayer.player" --hidden-import "ffpyplayer.player.core" --hidden-import "ffpyplayer.pic" --hidden-import "av" --clean --noconfirm main.py
```

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)** — see the [LICENSE](LICENSE) file for details.
