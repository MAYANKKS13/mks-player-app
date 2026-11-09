"""
Unit and integration tests for VLC Python Player.
Run with: python -m unittest test_player.py
"""
import os
import sys
import unittest
import tempfile
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Ensure offscreen Qt platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from subtitle_manager import parse_timecode, SubtitleTrack
from playlist_manager import PlaylistManager, RepeatMode
from media_engine import create_media_engine, QtMediaEngine
from player_window import PlayerWindow, format_time


class TestPlayerComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

    def test_format_time(self):
        self.assertEqual(format_time(0), "00:00")
        self.assertEqual(format_time(65000), "01:05")
        self.assertEqual(format_time(3665000), "01:01:05")

    def test_subtitle_timecode_parsing(self):
        ms = parse_timecode("00:01:23,456")
        self.assertEqual(ms, 83456)
        ms2 = parse_timecode("01:00:00.000")
        self.assertEqual(ms2, 3600000)

    def test_subtitle_track_loading(self):
        srt_content = """1
00:00:01,000 --> 00:00:04,000
First subtitle line

2
00:00:05,500 --> 00:00:09,000
Second subtitle line
"""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".srt", encoding="utf-8") as f:
            f.write(srt_content)
            temp_path = f.name

        try:
            track = SubtitleTrack(temp_path)
            self.assertEqual(len(track.cues), 2)
            self.assertEqual(track.get_text_at(500), None)
            self.assertEqual(track.get_text_at(2000), "First subtitle line")
            self.assertEqual(track.get_text_at(4500), None)
            self.assertEqual(track.get_text_at(6000), "Second subtitle line")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_playlist_manager(self):
        pl = PlaylistManager()
        self.assertEqual(pl.count(), 0)

        # Add items
        pl.add_item("C:/videos/movie1.mp4")
        pl.add_item("https://example.com/stream.m3u8")
        self.assertEqual(pl.count(), 2)

        # Navigation
        first = pl.set_current_index(0)
        self.assertEqual(first["title"], "movie1.mp4")

        nxt = pl.next_track()
        self.assertEqual(nxt["title"], "stream.m3u8")

        # End of playlist with Repeat OFF
        self.assertIsNone(pl.next_track())

        # Repeat ALL
        pl.toggle_repeat() # -> ALL
        self.assertEqual(pl.get_repeat_mode(), RepeatMode.ALL)
        wrapped = pl.next_track()
        self.assertEqual(wrapped["title"], "movie1.mp4")

        # Repeat ONE
        pl.toggle_repeat() # -> ONE
        self.assertEqual(pl.get_repeat_mode(), RepeatMode.ONE)
        same = pl.next_track()
        self.assertEqual(same["title"], "movie1.mp4")

    def test_media_engine_creation(self):
        engine = create_media_engine()
        self.assertIsNotNone(engine)
        self.assertIsNotNone(engine.get_video_widget())
        engine.set_volume(80)

    def test_player_window_init(self):
        window = PlayerWindow()
        self.assertIsNotNone(window)
        self.assertTrue(window.windowTitle().startswith("MKS Player"))
        # Verify initial controls state
        self.assertEqual(window.vol_slider.value(), 100)
        self.assertEqual(window.playlist.count(), 0)
        window.close()

    def test_mkv_and_mp4_playback(self):
        engine = create_media_engine()
        test_files = [
            r"C:\Users\mayank.sinha\Videos\Screen Recordings\Screen Recording 2026-07-31 150040.mp4",
            r"C:\Users\mayank.sinha\Downloads\Never After Dark 2026 1080p DUAL WEB-DL HEVC x265 5.1 BO.mkv"
        ]
        for tf in test_files:
            if os.path.exists(tf):
                engine.load_media(tf)
                self.assertTrue(engine.is_playing() or not engine._is_paused)
                engine.pause()
                self.assertTrue(engine._is_paused)
                engine.play()
                engine.set_position(5000)
                engine.stop()
        engine.close()


if __name__ == "__main__":
    unittest.main()
