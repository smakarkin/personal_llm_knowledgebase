"""Фабрика placeholder-страниц."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

PAGE_TITLES = [
    "Dashboard",
    "Pipeline",
    "InBox",
    "Rebuild",
    "Trace",
    "Sources",
    "Health",
    "Logs",
]


def create_placeholder_page(title: str) -> QWidget:
    """Создаёт простую страницу-заглушку с заголовком и описанием."""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    header = QLabel(title)
    header.setStyleSheet("font-size: 22px; font-weight: 700;")

    description = QLabel(
        "Здесь будет функциональность раздела. "
        "На этапе MVP это базовый каркас интерфейса."
    )
    description.setWordWrap(True)
    description.setAlignment(Qt.AlignmentFlag.AlignTop)

    layout.addWidget(header)
    layout.addWidget(description)
    layout.addStretch(1)
    return page
