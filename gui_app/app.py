"""Инициализация и запуск Qt-приложения."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui_app.config import load_app_config
from gui_app.views.main_window import MainWindow


def run() -> int:
    """Создаёт QApplication и показывает главное окно."""
    app = QApplication(sys.argv)
    app.setApplicationName("Knowledge Base GUI")

    config = load_app_config()
    window = MainWindow(config=config)
    window.show()

    return app.exec()
