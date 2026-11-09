"""
Playlist manager handling queue, next/previous tracks, repeat, and shuffle.
"""
import os
import random
from typing import List, Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal


class RepeatMode:
    OFF = "off"
    ALL = "all"
    ONE = "one"


class PlaylistManager(QObject):
    playlist_changed = pyqtSignal()
    track_changed = pyqtSignal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[Dict[str, str]] = []
        self._current_index: int = -1
        self._repeat_mode: str = RepeatMode.OFF
        self._shuffle: bool = False
        self._shuffle_order: List[int] = []

    def get_items(self) -> List[Dict[str, str]]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def current_index(self) -> int:
        return self._current_index

    def current_item(self) -> Optional[Dict[str, str]]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    def add_item(self, source: str) -> int:
        """Adds a source (file path or network URL) to the playlist."""
        if source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://"):
            title = source.split("/")[-1].split("?")[0] or source
        else:
            title = os.path.basename(source)

        item = {
            "source": source,
            "title": title or "Untitled Stream",
            "is_url": source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")
        }
        self._items.append(item)
        self._update_shuffle_order()
        self.playlist_changed.emit()
        return len(self._items) - 1

    def add_items(self, sources: List[str]):
        for s in sources:
            self.add_item(s)

    def remove_item(self, index: int):
        if 0 <= index < len(self._items):
            del self._items[index]
            if self._current_index == index:
                if len(self._items) == 0:
                    self._current_index = -1
                elif self._current_index >= len(self._items):
                    self._current_index = len(self._items) - 1
            elif self._current_index > index:
                self._current_index -= 1
            self._update_shuffle_order()
            self.playlist_changed.emit()

    def clear(self):
        self._items.clear()
        self._current_index = -1
        self._shuffle_order.clear()
        self.playlist_changed.emit()

    def set_current_index(self, index: int) -> Optional[Dict[str, str]]:
        if 0 <= index < len(self._items):
            self._current_index = index
            item = self._items[index]
            self.track_changed.emit(index, item)
            return item
        return None

    def next_track(self) -> Optional[Dict[str, str]]:
        if not self._items:
            return None

        if self._repeat_mode == RepeatMode.ONE and self._current_index != -1:
            return self._items[self._current_index]

        if self._shuffle and self._shuffle_order:
            try:
                curr_pos = self._shuffle_order.index(self._current_index)
                next_pos = curr_pos + 1
                if next_pos < len(self._shuffle_order):
                    return self.set_current_index(self._shuffle_order[next_pos])
                elif self._repeat_mode == RepeatMode.ALL:
                    return self.set_current_index(self._shuffle_order[0])
            except ValueError:
                return self.set_current_index(self._shuffle_order[0])
            return None

        next_idx = self._current_index + 1
        if next_idx < len(self._items):
            return self.set_current_index(next_idx)
        elif self._repeat_mode == RepeatMode.ALL:
            return self.set_current_index(0)

        return None

    def prev_track(self) -> Optional[Dict[str, str]]:
        if not self._items:
            return None

        if self._shuffle and self._shuffle_order:
            try:
                curr_pos = self._shuffle_order.index(self._current_index)
                prev_pos = curr_pos - 1
                if prev_pos >= 0:
                    return self.set_current_index(self._shuffle_order[prev_pos])
                elif self._repeat_mode == RepeatMode.ALL:
                    return self.set_current_index(self._shuffle_order[-1])
            except ValueError:
                return self.set_current_index(self._shuffle_order[-1])
            return None

        prev_idx = self._current_index - 1
        if prev_idx >= 0:
            return self.set_current_index(prev_idx)
        elif self._repeat_mode == RepeatMode.ALL:
            return self.set_current_index(len(self._items) - 1)

        return None

    def toggle_repeat(self) -> str:
        """Cycles through OFF -> ALL -> ONE -> OFF."""
        if self._repeat_mode == RepeatMode.OFF:
            self._repeat_mode = RepeatMode.ALL
        elif self._repeat_mode == RepeatMode.ALL:
            self._repeat_mode = RepeatMode.ONE
        else:
            self._repeat_mode = RepeatMode.OFF
        return self._repeat_mode

    def get_repeat_mode(self) -> str:
        return self._repeat_mode

    def toggle_shuffle(self) -> bool:
        self._shuffle = not self._shuffle
        self._update_shuffle_order()
        return self._shuffle

    def is_shuffled(self) -> bool:
        return self._shuffle

    def _update_shuffle_order(self):
        self._shuffle_order = list(range(len(self._items)))
        if self._shuffle:
            random.shuffle(self._shuffle_order)
