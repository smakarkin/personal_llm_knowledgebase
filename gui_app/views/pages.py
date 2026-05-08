"""Страницы приложения, включая Dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_app.services.state_inspector import KnowledgeBaseState, StateInspector

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


class DashboardPage(QWidget):
    """Страница с мониторингом состояния knowledge layer."""

    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)

        self._header = QLabel("Dashboard")
        self._status_line = QLabel("")
        self._recommendation = QLabel("")

        self._stat_labels: dict[str, QLabel] = {}
        self._time_labels: dict[str, QLabel] = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._header.setStyleSheet("font-size: 22px; font-weight: 700;")

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)

        top_row = QHBoxLayout()
        top_row.addWidget(self._header)
        top_row.addStretch(1)
        top_row.addWidget(refresh_btn)

        self._status_line.setStyleSheet("color: #555;")

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(12)
        cards_layout.setVerticalSpacing(12)

        cards_layout.addWidget(self._make_counts_card(), 0, 0)
        cards_layout.addWidget(self._make_layers_card(), 0, 1)
        cards_layout.addWidget(self._make_timestamps_card(), 1, 0, 1, 2)
        cards_layout.addWidget(self._make_recommendation_card(), 2, 0, 1, 2)

        layout.addLayout(top_row)
        layout.addWidget(self._status_line)
        layout.addLayout(cards_layout)
        layout.addStretch(1)

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("QFrame { border: 1px solid #DDD; border-radius: 8px; }")
        body = QVBoxLayout(card)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(6)

        caption = QLabel(title)
        caption.setStyleSheet("font-size: 15px; font-weight: 650;")
        body.addWidget(caption)
        return card, body

    def _make_counts_card(self) -> QWidget:
        card, body = self._make_card("Содержимое базы")
        for key, title in [
            ("inbox_md", "Markdown в InBox"),
            ("zettelkasten_md", "Markdown в Zettelkasten"),
            ("missing_primary", "Без llm_primary_cluster"),
        ]:
            body.addLayout(self._labeled_value(title, self._stat_labels, key))
        return card

    def _make_layers_card(self) -> QWidget:
        card, body = self._make_card("Файлы LLM-слоёв")
        for key, title in [
            ("collections_primary", "11_llm_collections_primary"),
            ("collections_candidate", "11_llm_collections_candidate"),
            ("concepts", "12_llm_concepts"),
            ("indexes", "13_llm_indexes"),
            ("traces", "14_llm_traces"),
        ]:
            body.addLayout(self._labeled_value(title, self._stat_labels, key))
        return card

    def _make_timestamps_card(self) -> QWidget:
        card, body = self._make_card("Последние изменения")
        for key, title in [
            ("collections_primary", "Primary collections"),
            ("collections_candidate", "Candidate collections"),
            ("concepts", "Concepts"),
            ("indexes", "Indexes"),
        ]:
            body.addLayout(self._labeled_value(title, self._time_labels, key))
        return card

    def _make_recommendation_card(self) -> QWidget:
        card, body = self._make_card("Рекомендуемый следующий шаг")
        self._recommendation.setWordWrap(True)
        self._recommendation.setAlignment(Qt.AlignmentFlag.AlignTop)
        body.addWidget(self._recommendation)
        return card

    def _labeled_value(self, label: str, bucket: dict[str, QLabel], key: str) -> QHBoxLayout:
        row = QHBoxLayout()
        name = QLabel(label)
        value = QLabel("-")
        value.setStyleSheet("font-weight: 700;")
        row.addWidget(name)
        row.addStretch(1)
        row.addWidget(value)
        bucket[key] = value
        return row

    def refresh(self) -> None:
        state = self._inspector.inspect()
        self._fill_values(state)

    def _fill_values(self, state: KnowledgeBaseState) -> None:
        self._status_line.setText(
            f"Обновлено: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

        self._stat_labels["inbox_md"].setText(str(state.inbox_markdown_count))
        self._stat_labels["zettelkasten_md"].setText(str(state.zettelkasten_markdown_count))
        self._stat_labels["missing_primary"].setText(str(state.zettelkasten_missing_primary_cluster_count))

        self._stat_labels["collections_primary"].setText(str(state.collections_primary_count))
        self._stat_labels["collections_candidate"].setText(str(state.collections_candidate_count))
        self._stat_labels["concepts"].setText(str(state.concepts_count))
        self._stat_labels["indexes"].setText(str(state.indexes_count))
        self._stat_labels["traces"].setText(str(state.traces_count))

        self._time_labels["collections_primary"].setText(_fmt_dt(state.collections_primary_last_modified))
        self._time_labels["collections_candidate"].setText(_fmt_dt(state.collections_candidate_last_modified))
        self._time_labels["concepts"].setText(_fmt_dt(state.concepts_last_modified))
        self._time_labels["indexes"].setText(_fmt_dt(state.indexes_last_modified))

        self._recommendation.setText(state.recommended_next_step)


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "нет файлов"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


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
