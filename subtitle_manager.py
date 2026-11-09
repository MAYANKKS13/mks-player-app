"""
Subtitle parser, embedded MKV/MP4 stream extractor, and overlay display for PyQt video player.
Supports SRT, VTT, and embedded Matroska/MP4 subtitle streams.
"""
import re
from typing import List, Tuple, Optional, Dict
from PyQt5.QtWidgets import QLabel, QWidget
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont


def parse_timecode(tc_str: str) -> int:
    """Converts '00:01:23,456' or '00:01:23.456' to milliseconds."""
    tc_str = tc_str.strip().replace(',', '.')
    parts = tc_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        sec, ms = s.split('.') if '.' in s else (s, '0')
        return (int(h) * 3600 + int(m) * 60 + int(sec)) * 1000 + int(ms.ljust(3, '0')[:3])
    elif len(parts) == 2:
        m, s = parts
        sec, ms = s.split('.') if '.' in s else (s, '0')
        return (int(m) * 60 + int(sec)) * 1000 + int(ms.ljust(3, '0')[:3])
    return 0


def probe_media_streams(file_path: str) -> Tuple[List[str], List[Dict]]:
    """
    Rapidly probes embedded audio and subtitle tracks from a media file using PyAV.
    """
    audio_tracks = []
    sub_tracks = []
    try:
        import av
        c = av.open(file_path)
        for i, s in enumerate(c.streams.audio):
            t = s.metadata.get('title') or s.metadata.get('language') or f"Audio Track {i+1}"
            audio_tracks.append(t)
        for i, s in enumerate(c.streams.subtitles):
            t = s.metadata.get('title') or s.metadata.get('language') or f"Subtitle Track {i+1}"
            sub_tracks.append({'index': i, 'title': t, 'language': s.language})
        c.close()
    except Exception as e:
        pass
    return audio_tracks, sub_tracks


class EmbeddedSubtitleTrack:
    """
    Extracts and parses embedded subtitle streams (e.g. from MKV / MP4)
    using PyAV without freezing the media player engine.
    """
    def __init__(self, media_path: str, stream_index: int, track_title: str):
        self.media_path = media_path
        self.stream_index = stream_index
        self.track_title = track_title
        self.cues: List[Tuple[int, int, str]] = []
        self._load_cues()

    def _load_cues(self):
        try:
            import av
            c = av.open(self.media_path)
            st = c.streams.subtitles[self.stream_index]
            for pkt in c.demux(st):
                raw_pts = pkt.pts if pkt.pts is not None else pkt.dts
                if raw_pts is None:
                    continue
                start_ms = int(raw_pts * st.time_base * 1000)
                dur_ms = int(pkt.duration * st.time_base * 1000) if pkt.duration else 3000

                for sub in pkt.decode():
                    text = ""
                    if hasattr(sub, 'dialogue') and sub.dialogue:
                        text = sub.dialogue.decode('utf-8', 'ignore').strip()
                    elif hasattr(sub, 'text') and sub.text:
                        text = sub.text.decode('utf-8', 'ignore').strip()

                    if text:
                        # Clean up formatting tags like {\an8} or <i>
                        text = re.sub(r'\{[^}]+\}', '', text)
                        text = re.sub(r'<[^>]+>', '', text)
                        text = text.strip()
                        if text:
                            self.cues.append((start_ms, start_ms + dur_ms, text))
            c.close()
            self.cues.sort(key=lambda x: x[0])
        except Exception as e:
            print(f"Notice: Failed to load embedded subtitle: {e}")

    def get_text_at(self, pos_ms: int) -> Optional[str]:
        for start, end, text in self.cues:
            if start <= pos_ms <= end:
                return text
            if start > pos_ms:
                break
        return None


class SubtitleTrack:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.track_title = file_path.split("/")[-1].split("\\")[-1]
        self.cues: List[Tuple[int, int, str]] = []
        self._load_file(file_path)

    def _load_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Error loading subtitles: {e}")
            return

        time_pattern = re.compile(
            r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})'
        )

        blocks = content.replace('\r\n', '\n').split('\n\n')
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if not lines:
                continue

            time_line_idx = -1
            match = None
            for idx, line in enumerate(lines):
                m = time_pattern.search(line)
                if m:
                    match = m
                    time_line_idx = idx
                    break

            if match and time_line_idx != -1:
                start_ms = parse_timecode(match.group(1))
                end_ms = parse_timecode(match.group(2))
                text_lines = lines[time_line_idx + 1:]
                clean_text = "\n".join(text_lines)
                clean_text = re.sub(r'\{[^}]+\}', '', clean_text)
                clean_text = re.sub(r'<[^>]+>', '', clean_text)
                if clean_text:
                    self.cues.append((start_ms, end_ms, clean_text))

        self.cues.sort(key=lambda x: x[0])

    def get_text_at(self, pos_ms: int) -> Optional[str]:
        for start, end, text in self.cues:
            if start <= pos_ms <= end:
                return text
            if start > pos_ms:
                break
        return None


class SubtitleOverlay(QLabel):
    """
    Transparent overlay label positioned over the video viewport.
    """
    def __init__(self, parent_video_widget: QWidget):
        super().__init__(parent_video_widget)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 20px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 160);
                padding: 6px 14px;
                border-radius: 6px;
            }
        """)
        self.hide()

    def update_position(self, parent_width: int, parent_height: int):
        """Aligns subtitle towards the bottom center of the parent widget."""
        w = min(int(parent_width * 0.85), 800)
        h = self.sizeHint().height() + 20
        x = (parent_width - w) // 2
        y = parent_height - h - 30
        self.setGeometry(max(10, x), max(10, y), w, h)

    def set_subtitle(self, text: Optional[str], parent_width: int, parent_height: int):
        if text:
            self.setText(text)
            self.adjustSize()
            self.update_position(parent_width, parent_height)
            self.show()
            self.raise_()
        else:
            self.hide()
