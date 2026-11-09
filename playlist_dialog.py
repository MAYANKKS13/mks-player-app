"""
Standalone Playlist Dialog for VLC Python Player.
Keeps the main player window distraction-free while providing full queue control.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt
from playlist_manager import PlaylistManager, RepeatMode


class PlaylistDialog(QDialog):
    def __init__(self, playlist: PlaylistManager, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.setWindowTitle("MKS Player - Playlist")
        self.resize(440, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header Row
        header_row = QHBoxLayout()
        title_label = QLabel("Playback Queue")
        title_label.setObjectName("titleLabel")
        header_row.addWidget(title_label)
        header_row.addStretch(1)

        self.repeat_btn = QPushButton("🔁")
        self.repeat_btn.setToolTip("Repeat: Off")
        self.repeat_btn.setFixedWidth(50)
        self.repeat_btn.clicked.connect(self._toggle_repeat)

        self.shuffle_btn = QPushButton("🔀")
        self.shuffle_btn.setToolTip("Shuffle: Off")
        self.shuffle_btn.setFixedWidth(50)
        self.shuffle_btn.clicked.connect(self._toggle_shuffle)

        header_row.addWidget(self.repeat_btn)
        header_row.addWidget(self.shuffle_btn)
        layout.addLayout(header_row)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        add_file_btn = QPushButton("➕ Add File")
        add_file_btn.clicked.connect(self._add_file)

        add_url_btn = QPushButton("🌐 Add URL")
        add_url_btn.clicked.connect(self._add_url)

        del_btn = QPushButton("❌ Remove")
        del_btn.clicked.connect(self._remove_selected)

        clear_btn = QPushButton("🧹 Clear")
        clear_btn.clicked.connect(self.playlist.clear)

        btn_row.addWidget(add_file_btn)
        btn_row.addWidget(add_url_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Connect signals
        self.playlist.playlist_changed.connect(self.sync_list)
        self.sync_list()
        self._update_repeat_ui()
        self._update_shuffle_ui()

    def sync_list(self):
        self.list_widget.clear()
        curr_idx = self.playlist.current_index()
        for idx, item in enumerate(self.playlist.get_items()):
            prefix = "▶  " if idx == curr_idx else f"{idx + 1}.  "
            list_item = QListWidgetItem(f"{prefix}{item['title']}")
            if idx == curr_idx:
                list_item.setForeground(Qt.white)
            self.list_widget.addItem(list_item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        if self.parent():
            self.parent()._play_track_index(row)

    def _add_file(self):
        if self.parent():
            self.parent()._open_multiple_files_dialog()

    def _add_url(self):
        if self.parent():
            self.parent()._open_stream_dialog()

    def _remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.playlist.remove_item(row)

    def _toggle_repeat(self):
        mode = self.playlist.toggle_repeat()
        self._update_repeat_ui()

    def _update_repeat_ui(self):
        mode = self.playlist.get_repeat_mode()
        if mode == RepeatMode.ALL:
            self.repeat_btn.setText("🔁 All")
            self.repeat_btn.setToolTip("Repeat: All")
        elif mode == RepeatMode.ONE:
            self.repeat_btn.setText("🔂 One")
            self.repeat_btn.setToolTip("Repeat: Current")
        else:
            self.repeat_btn.setText("🔁")
            self.repeat_btn.setToolTip("Repeat: Off")

    def _toggle_shuffle(self):
        is_shuf = self.playlist.toggle_shuffle()
        self._update_shuffle_ui()

    def _update_shuffle_ui(self):
        is_shuf = self.playlist.is_shuffled()
        self.shuffle_btn.setChecked(is_shuf)
        self.shuffle_btn.setToolTip(f"Shuffle: {'On' if is_shuf else 'Off'}")
