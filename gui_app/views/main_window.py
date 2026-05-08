"""Главное окно: левое меню + страницы."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStatusBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from gui_app.config import AppConfig
from gui_app.views.pages import PAGE_TITLES, DashboardPage, HealthPage, InBoxPage, PipelineMapPage, RebuildPage, TracePage, create_placeholder_page


class MainWindow(QMainWindow):
    """Базовый каркас MVP-приложения."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("Управление базой знаний Obsidian")
        self.resize(1200, 760)

        self._menu = QListWidget()
        self._stack = QStackedWidget()
        self._status_bar = QStatusBar()
        self._build_ui()
        self._bind_events()
        self._build_menu_bar()
        self._apply_global_styles()
        self.statusBar().showMessage("Готово")

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
                self._stack.addWidget(
                    DashboardPage(
                        repo_root=self._config.vault_path,
                        inbox_folder=self._config.inbox_folder,
                    )
                )
            elif page_title == "Pipeline Map":
                self._stack.addWidget(
                    PipelineMapPage(
                        repo_root=self._config.vault_path,
                        inbox_folder=self._config.inbox_folder,
                    )
                )
            elif page_title == "Rebuild":
                self._stack.addWidget(
                    RebuildPage(
                        repo_root=self._config.vault_path,
                        scripts_path=self._config.scripts_path,
                        inbox_folder=self._config.inbox_folder,
                    )
                )
            elif page_title == "InBox":
                self._stack.addWidget(
                    InBoxPage(
                        repo_root=self._config.vault_path,
                        scripts_path=self._config.scripts_path,
                        inbox_folder=self._config.inbox_folder,
                    )
                )
            elif page_title == "Trace":
                self._stack.addWidget(
                    TracePage(
                        repo_root=self._config.vault_path,
                        scripts_path=self._config.scripts_path,
                    )
                )
            elif page_title == "Health":
                self._stack.addWidget(
                    HealthPage(
                        repo_root=self._config.vault_path,
                        scripts_path=self._config.scripts_path,
                    )
                )
            else:
                self._stack.addWidget(create_placeholder_page(page_title))

        layout.addWidget(self._stack)
        return panel

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        open_vault = QAction("Открыть vault root", self)
        open_vault.triggered.connect(self._open_vault_root)
        file_menu.addAction(open_vault)
        self.setStatusBar(self._status_bar)

    def _open_vault_root(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._config.vault_path)))
        self.statusBar().showMessage(f"Открыт vault root: {self._config.vault_path}", 4000)

    def _apply_global_styles(self) -> None:
        self.setStyleSheet(
            """
            QPushButton {
                background: #2563EB;
                color: white;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:disabled {
                background: #9CA3AF;
                color: #F3F4F6;
            }
            QLabel[status="ok"] { color: #166534; }
            QLabel[status="warn"] { color: #92400E; }
            QLabel[status="error"] { color: #991B1B; }
            """
        )

    def _bind_events(self) -> None:
        self._menu.currentRowChanged.connect(self._stack.setCurrentIndex)
