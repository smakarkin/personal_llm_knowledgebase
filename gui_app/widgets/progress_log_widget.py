from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class ProgressLogWidget(QWidget):
    open_log_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._status = QLabel("Ожидание")
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log_path: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        copy_btn = QPushButton("Копировать лог")
        clear_btn = QPushButton("Очистить")
        open_btn = QPushButton("Открыть лог-файл")
        copy_btn.clicked.connect(lambda: self._log.selectAll() or self._log.copy())
        clear_btn.clicked.connect(self._log.clear)
        open_btn.clicked.connect(self.open_log_requested.emit)
        controls.addWidget(self._status)
        controls.addStretch(1)
        controls.addWidget(copy_btn)
        controls.addWidget(clear_btn)
        controls.addWidget(open_btn)
        layout.addLayout(controls)
        layout.addWidget(self._log)

    def append(self, line: str) -> None:
        self._log.appendPlainText(line)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_log_path(self, path: Path | None) -> None:
        self._log_path = path
