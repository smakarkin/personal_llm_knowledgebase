"""Главное окно: левое меню + страницы."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui_app.config import AppConfig
from gui_app.views.pages import PAGE_TITLES, DashboardPage, create_placeholder_page


class MainWindow(QMainWindow):
    """Базовый каркас MVP-приложения."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("Управление базой знаний Obsidian")
        self.resize(1200, 760)

        self._menu = QListWidget()
        self._stack = QStackedWidget()
        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        menu_panel = self._create_menu_panel()
        content_panel = self._create_content_panel()

        layout.addWidget(menu_panel)
        layout.addWidget(content_panel, 1)
        self.setCentralWidget(root)

        self._menu.setCurrentRow(0)
        self._stack.setCurrentIndex(0)

    def _create_menu_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(260)
        panel.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 16, 12, 12)

        title = QLabel("Разделы")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")

        self._menu.setSpacing(2)
        self._menu.setAlternatingRowColors(False)

        for page_title in PAGE_TITLES:
            QListWidgetItem(page_title, self._menu)

        layout.addWidget(title)
        layout.addWidget(self._menu, 1)
        return panel

    def _create_content_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)

        for page_title in PAGE_TITLES:
            if page_title == "Dashboard":
                self._stack.addWidget(DashboardPage(repo_root=self._config.vault_path))
            else:
                self._stack.addWidget(create_placeholder_page(page_title))

        layout.addWidget(self._stack)
        return panel

    def _bind_events(self) -> None:
        self._menu.currentRowChanged.connect(self._stack.setCurrentIndex)
