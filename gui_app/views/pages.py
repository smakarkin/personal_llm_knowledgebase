"""Страницы приложения, включая Dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread, Signal
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
)

from gui_app.services.script_runner import ScriptRunner, build_rebuild_scenarios
from gui_app.services.health_service import HealthData, HealthService
from gui_app.models.status_models import InboxNoteStatus, KnowledgeBaseState, PipelineStepStatus, RebuildScenario, RebuildStep, TraceRunResult
from gui_app.services.state_inspector import StateInspector
from gui_app.services.trace_service import TraceService

PAGE_TITLES = [
    "Dashboard",
    "Pipeline Map",
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
        self._inbox_folder = inbox_folder

        self._header = QLabel("Dashboard")
        self._status_line = QLabel("")
        self._recommendation = QLabel("")
        self._diagnostics = QLabel("")

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
        cards_layout.addWidget(self._make_diagnostics_card(), 3, 0, 1, 2)

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
            ("inbox_md", f"Markdown в {self._inbox_folder}"),
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

    def _make_diagnostics_card(self) -> QWidget:
        card, body = self._make_card("Диагностика")
        self._diagnostics.setWordWrap(True)
        self._diagnostics.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._diagnostics.setStyleSheet("color: #8A4B00;")
        body.addWidget(self._diagnostics)
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
        if state.diagnostics:
            self._diagnostics.setText("\n".join(f"• {item}" for item in state.diagnostics))
        else:
            self._diagnostics.setText("Проблемы пути/файлов не обнаружены.")


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "нет файлов"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


class PipelineMapPage(QWidget):
    """Экран с картой этапов пайплайна и их текущим состоянием."""

    _STATUS_STYLES = {
        "ok": ("OK", "#E8F5E9", "#1B5E20"),
        "needs_attention": ("Требует внимания", "#FFF8E1", "#8A4B00"),
        "stale": ("Устарело", "#FFF3E0", "#A84300"),
        "not_run": ("Не запускалось", "#F3F4F6", "#4B5563"),
    }

    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)
        self._rows: list[tuple[QLabel, QLabel, QPushButton, str]] = []
        self._status_line = QLabel("")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        title = QLabel("Pipeline Map")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)

        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh_btn)
        layout.addLayout(top)
        layout.addWidget(self._status_line)

        self._list = QVBoxLayout()
        self._list.setSpacing(8)
        layout.addLayout(self._list)
        layout.addStretch(1)

    def refresh(self) -> None:
        state = self._inspector.inspect()
        self._status_line.setText(
            f"Обновлено: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for step in _build_pipeline_steps(state):
            self._list.addWidget(self._make_step_row(step))

    def _make_step_row(self, step: PipelineStepStatus) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet("QFrame { border: 1px solid #DDD; border-radius: 8px; }")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        name = QLabel(step.title)
        name.setStyleSheet("font-weight: 700;")
        status_text, bg, fg = self._STATUS_STYLES[step.status]
        status = QLabel(status_text)
        status.setStyleSheet(f"padding: 2px 8px; border-radius: 10px; background: {bg}; color: {fg};")
        explanation = QLabel(step.explanation)
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #444;")

        link_btn = QPushButton(step.link)
        link_btn.setEnabled(bool(step.link))

        text_col = QVBoxLayout()
        text_col.addWidget(name)
        text_col.addWidget(explanation)

        row.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(text_col, 1)
        row.addWidget(link_btn, 0, Qt.AlignmentFlag.AlignTop)
        return wrap


class _ScenarioWorker(QThread):
    step_started = Signal(int, int, str)
    output_line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, runner: ScriptRunner, scenario: RebuildScenario) -> None:
        super().__init__()
        self._runner = runner
        self._scenario = scenario

    def run(self) -> None:
        results = self._runner.run_scenario(
            self._scenario,
            on_step_start=lambda current, total, step: self.step_started.emit(current, total, step.title),
            on_output=lambda line: self.output_line.emit(line),
        )
        code = 0 if results and results[-1].return_code == 0 and len(results) == len(self._scenario.steps) else 1
        self.finished_with_code.emit(code)


class RebuildPage(QWidget):
    """Экран оркестрации rebuild-сценариев поверх существующих скриптов."""

    def __init__(self, repo_root: Path, scripts_path: Path, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._scenarios = build_rebuild_scenarios(inbox_folder=inbox_folder, zettelkasten_folder="Zettelkasten")
        self._scenario_by_key = {item.key: item for item in self._scenarios}
        self._worker: _ScenarioWorker | None = None

        self._scenario_combo = QComboBox()
        self._description = QLabel("")
        self._progress = QProgressBar()
        self._status = QLabel("Сценарий не запущен")
        self._log = QPlainTextEdit()
        self._run_btn = QPushButton("Запустить сценарий")
        self._clear_btn = QPushButton("Очистить лог")

        self._build_ui()
        self._on_scenario_changed(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Rebuild")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")

        for scenario in self._scenarios:
            self._scenario_combo.addItem(scenario.title, scenario.key)

        self._scenario_combo.currentIndexChanged.connect(self._on_scenario_changed)
        self._run_btn.clicked.connect(self._confirm_and_start)
        self._clear_btn.clicked.connect(self._log.clear)

        self._description.setWordWrap(True)
        self._progress.setMinimum(0)
        self._progress.setValue(0)
        self._log.setReadOnly(True)

        controls = QHBoxLayout()
        controls.addWidget(self._scenario_combo, 1)
        controls.addWidget(self._run_btn)
        controls.addWidget(self._clear_btn)

        layout.addWidget(title)
        layout.addLayout(controls)
        layout.addWidget(self._description)
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addWidget(self._log, 1)

    def _on_scenario_changed(self, index: int) -> None:
        key = self._scenario_combo.itemData(index)
        scenario = self._scenario_by_key.get(key)
        if scenario is None:
            return
        lines = "\n".join(f"{i}. {step.title}" for i, step in enumerate(scenario.steps, start=1))
        self._description.setText(f"{scenario.description}\n\nШаги:\n{lines}")
        self._progress.setMaximum(len(scenario.steps))
        self._progress.setValue(0)

    def _confirm_and_start(self) -> None:
        scenario = self._scenario_by_key[self._scenario_combo.currentData()]
        answer = QMessageBox.question(
            self,
            "Подтверждение запуска",
            f"Запустить сценарий '{scenario.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_scenario(scenario)

    def _start_scenario(self, scenario: RebuildScenario) -> None:
        self._run_btn.setEnabled(False)
        self._scenario_combo.setEnabled(False)
        self._progress.setMaximum(len(scenario.steps))
        self._progress.setValue(0)
        self._status.setText("Запуск...")
        self._append_log(f"=== Старт сценария: {scenario.title} ===")

        self._worker = _ScenarioWorker(self._runner, scenario)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.output_line.connect(self._append_log)
        self._worker.finished_with_code.connect(self._on_finished)
        self._worker.start()

    def _on_step_started(self, current: int, total: int, title: str) -> None:
        self._progress.setValue(current - 1)
        self._status.setText(f"Шаг {current}/{total}: {title}")
        self._append_log(f"\n--- Шаг {current}/{total}: {title} ---")

    def _on_finished(self, code: int) -> None:
        self._progress.setValue(self._progress.maximum())
        if code == 0:
            self._status.setText("Сценарий завершён успешно")
            self._append_log("=== Сценарий завершён успешно ===")
        else:
            self._status.setText("Сценарий завершился с ошибкой")
            self._append_log("=== Сценарий завершился с ошибкой ===")
        self._run_btn.setEnabled(True)
        self._scenario_combo.setEnabled(True)

    def _append_log(self, text: str) -> None:
        self._log.appendPlainText(text)


class InBoxPage(QWidget):
    """Экран мониторинга InBox без автоматического переноса заметок."""

    def __init__(self, repo_root: Path, scripts_path: Path, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._repo_root = repo_root
        self._inbox_folder = inbox_folder
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._worker: _ScenarioWorker | None = None

        self._stats = QLabel("")
        self._status_line = QLabel("")
        self._table = QTableWidget()
        self._classify_btn = QPushButton("Запустить классификацию InBox")
        self._open_folder_btn = QPushButton("Открыть папку InBox")
        self._refresh_btn = QPushButton("Обновить")
        self._hint = QLabel(
            "Важно: перенос заметок в Zettelkasten выполняется вручную в Obsidian. "
            "GUI только показывает состояние и готовность к переносу."
        )
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("InBox")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #8A4B00;")

        controls = QHBoxLayout()
        controls.addWidget(self._classify_btn)
        controls.addWidget(self._open_folder_btn)
        controls.addStretch(1)
        controls.addWidget(self._refresh_btn)

        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Файл", "primary", "candidate", "skip_reason", "Пустая", "Статус"]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._classify_btn.clicked.connect(self._run_classification)
        self._open_folder_btn.clicked.connect(self._open_inbox_folder)
        self._refresh_btn.clicked.connect(self.refresh)

        layout.addWidget(title)
        layout.addWidget(self._hint)
        layout.addLayout(controls)
        layout.addWidget(self._stats)
        layout.addWidget(self._status_line)
        layout.addWidget(self._table, 1)

    def refresh(self) -> None:
        notes = self._inspector.inspect_inbox_notes()
        ready = sum(1 for note in notes if note.is_ready_for_transfer)
        needs_attention = len(notes) - ready
        self._stats.setText(
            f"Всего заметок: {len(notes)} | Готово к переносу: {ready} | Требуют внимания: {needs_attention}"
        )
        self._status_line.setText(
            f"Критерий готовности: не пустая, без llm_skip_reason, есть осмысленная llm-разметка."
        )
        self._fill_table(notes)

    def _fill_table(self, notes: list[InboxNoteStatus]) -> None:
        self._table.setRowCount(len(notes))
        for row, note in enumerate(notes):
            self._table.setItem(row, 0, QTableWidgetItem(note.file_name))
            self._table.setItem(row, 1, QTableWidgetItem("Да" if note.has_primary_cluster else "Нет"))
            self._table.setItem(row, 2, QTableWidgetItem("Да" if note.has_candidate_clusters else "Нет"))
            self._table.setItem(row, 3, QTableWidgetItem("Да" if note.has_skip_reason else "Нет"))
            self._table.setItem(row, 4, QTableWidgetItem("Да" if note.is_empty else "Нет"))
            self._table.setItem(
                row, 5, QTableWidgetItem("Готово к переносу" if note.is_ready_for_transfer else "Ещё требует обработки")
            )
        self._table.resizeColumnsToContents()

    def _run_classification(self) -> None:
        scenario = RebuildScenario(
            key="classify_inbox_only",
            title="Классификация InBox",
            description=f"Запуск propose_clusters.py для папки {self._inbox_folder}.",
            steps=(RebuildStep("Классификация InBox", "propose_clusters.py", (self._inbox_folder,)),),
        )
        self._classify_btn.setEnabled(False)
        self._status_line.setText("Запуск классификации InBox...")
        self._worker = _ScenarioWorker(self._runner, scenario)
        self._worker.finished_with_code.connect(self._on_classification_finished)
        self._worker.start()

    def _on_classification_finished(self, code: int) -> None:
        self._classify_btn.setEnabled(True)
        self._status_line.setText("Классификация завершена успешно." if code == 0 else "Классификация завершилась с ошибкой.")
        self.refresh()

    def _open_inbox_folder(self) -> None:
        inbox_path, _ = self._inspector.repo_root / self._inbox_folder, None
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(inbox_path)))




class _TraceWorker(QThread):
    output_line = Signal(str)
    finished_with_result = Signal(object)

    def __init__(self, service: TraceService, query: str) -> None:
        super().__init__()
        self._service = service
        self._query = query

    def run(self) -> None:
        result = self._service.run_trace(self._query, on_output=lambda line: self.output_line.emit(line))
        self.finished_with_result.emit(result)


class TracePage(QWidget):
    """Экран semantic trace-поиска по описанию идеи."""

    def __init__(self, repo_root: Path, scripts_path: Path) -> None:
        super().__init__()
        self._service = TraceService(repo_root=repo_root, scripts_path=scripts_path)
        self._worker: _TraceWorker | None = None
        self._last_report_path: Path | None = None

        self._query_input = QPlainTextEdit()
        self._search_btn = QPushButton("Найти по смыслу")
        self._open_btn = QPushButton("Открыть файл")
        self._status = QLabel("")
        self._history = QListWidget()
        self._reports = QListWidget()
        self._preview = QPlainTextEdit()
        self._log = QPlainTextEdit()

        self._build_ui()
        self._refresh_lists()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Trace / semantic search")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        hint = QLabel("Поиск выполняется по смыслу описания идеи, а не по буквальному вхождению слов.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #1F4E79;")

        self._query_input.setPlaceholderText("Опишите идею, гипотезу или понятие своими словами...")
        self._preview.setReadOnly(True)
        self._log.setReadOnly(True)
        self._open_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(self._search_btn)
        controls.addWidget(self._open_btn)
        controls.addStretch(1)

        lists = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("История запросов"))
        left.addWidget(self._history, 1)
        left.addWidget(QLabel("Найденные trace-отчёты"))
        left.addWidget(self._reports, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Предпросмотр последнего результата"))
        right.addWidget(self._preview, 1)
        right.addWidget(QLabel("Лог запуска"))
        right.addWidget(self._log, 1)

        lists.addLayout(left, 1)
        lists.addLayout(right, 2)

        self._search_btn.clicked.connect(self._start_search)
        self._open_btn.clicked.connect(self._open_report)
        self._history.itemClicked.connect(lambda item: self._query_input.setPlainText(item.text()))
        self._reports.itemClicked.connect(self._preview_selected_report)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._query_input)
        layout.addLayout(controls)
        layout.addWidget(self._status)
        layout.addLayout(lists, 1)

    def _start_search(self) -> None:
        query = self._query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Пустой запрос", "Введите описание идеи или понятия.")
            return
        if not self._service.script_exists():
            QMessageBox.warning(self, "Скрипт не найден", "Скрипт semantic_trace.py не найден. Проверьте путь scripts_path/repo_root.")
            return

        self._log.clear()
        self._status.setText("Выполняется semantic trace...")
        self._search_btn.setEnabled(False)
        self._worker = _TraceWorker(self._service, query)
        self._worker.output_line.connect(self._log.appendPlainText)
        self._worker.finished_with_result.connect(self._on_search_finished)
        self._worker.start()

    def _on_search_finished(self, result: TraceRunResult) -> None:
        self._search_btn.setEnabled(True)
        if result.return_code != 0:
            message = result.error_message or "semantic_trace.py завершился с ошибкой."
            self._status.setText(message)
            QMessageBox.warning(self, "Ошибка semantic trace", message)
            return

        self._last_report_path = result.report_path
        self._open_btn.setEnabled(self._last_report_path is not None and self._last_report_path.exists())
        path_text = str(self._last_report_path) if self._last_report_path else "(файл не найден)"
        self._status.setText(f"Готово. Создан trace-файл: {path_text}")
        self._refresh_lists()
        if self._last_report_path and self._last_report_path.exists():
            self._preview.setPlainText(self._last_report_path.read_text(encoding='utf-8', errors='ignore'))

    def _refresh_lists(self) -> None:
        self._history.clear()
        for query in self._service.recent_history():
            QListWidgetItem(query, self._history)

        self._reports.clear()
        for report in self._service.list_trace_reports():
            item = QListWidgetItem(report.name)
            item.setData(Qt.ItemDataRole.UserRole, str(report))
            self._reports.addItem(item)

    def _preview_selected_report(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self._last_report_path = path
        self._open_btn.setEnabled(path.exists())
        if path.exists():
            self._preview.setPlainText(path.read_text(encoding='utf-8', errors='ignore'))

    def _open_report(self) -> None:
        if self._last_report_path and self._last_report_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_report_path)))


class HealthPage(QWidget):
    """Экран health-диагностики: запуск lint и просмотр отчёта."""

    def __init__(self, repo_root: Path, scripts_path: Path) -> None:
        super().__init__()
        self._service = HealthService(repo_root=repo_root, scripts_path=scripts_path)
        self._last_report_path: Path | None = None

        self._run_btn = QPushButton("Запустить health check")
        self._refresh_btn = QPushButton("Обновить из последнего отчёта")
        self._open_btn = QPushButton("Открыть отчёт")
        self._status = QLabel("")
        self._report_path_label = QLabel("—")
        self._categories = QTableWidget(0, 2)
        self._viewer = QPlainTextEdit()

        self._build_ui()
        self._load_latest()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Health")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        hint = QLabel("Диагностика базы: запуск lint_knowledge_base.py и разбор категорий проблем.")
        hint.setWordWrap(True)

        self._categories.setHorizontalHeaderLabels(["Категория", "Кол-во"])
        self._categories.horizontalHeader().setStretchLastSection(False)
        self._categories.horizontalHeader().setSectionResizeMode(0, self._categories.horizontalHeader().ResizeMode.Stretch)
        self._categories.horizontalHeader().setSectionResizeMode(1, self._categories.horizontalHeader().ResizeMode.ResizeToContents)
        self._categories.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._categories.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._categories.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self._viewer.setReadOnly(True)
        self._open_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(self._run_btn)
        controls.addWidget(self._refresh_btn)
        controls.addWidget(self._open_btn)
        controls.addStretch(1)

        report_row = QHBoxLayout()
        report_row.addWidget(QLabel("Последний отчёт:"))
        report_row.addWidget(self._report_path_label, 1)

        self._run_btn.clicked.connect(self._run_lint)
        self._refresh_btn.clicked.connect(self._load_latest)
        self._open_btn.clicked.connect(self._open_report)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(controls)
        layout.addWidget(self._status)
        layout.addLayout(report_row)
        layout.addWidget(QLabel("Категории проблем"))
        layout.addWidget(self._categories, 1)
        layout.addWidget(QLabel("Текст отчёта"))
        layout.addWidget(self._viewer, 2)

    def _run_lint(self) -> None:
        self._status.setText("Запуск lint_knowledge_base.py...")
        result, health = self._service.run_lint()
        if result.return_code != 0:
            self._status.setText("Lint завершился с ошибкой. Ниже показан stdout/stderr.")
            self._viewer.setPlainText((result.stdout + "\n" + result.stderr).strip())
            self._fill_health(health)
            return
        self._status.setText("Health check завершён успешно.")
        self._fill_health(health)

    def _load_latest(self) -> None:
        self._fill_health(self._service.load_latest_report())
        if self._last_report_path:
            self._status.setText("Загружен последний health report.")
        else:
            self._status.setText("Health report пока не найден.")

    def _fill_health(self, health: HealthData) -> None:
        self._last_report_path = health.report_path
        self._open_btn.setEnabled(self._last_report_path is not None and self._last_report_path.exists())
        self._report_path_label.setText(str(self._last_report_path) if self._last_report_path else "—")

        self._categories.setRowCount(0)
        for row_idx, category in enumerate(health.categories):
            self._categories.insertRow(row_idx)
            self._categories.setItem(row_idx, 0, QTableWidgetItem(category.title))
            self._categories.setItem(row_idx, 1, QTableWidgetItem(str(category.count)))

        if health.report_text:
            self._viewer.setPlainText(health.report_text)
        else:
            self._viewer.setPlainText("Отчёт отсутствует. Нажмите «Запустить health check».")

    def _open_report(self) -> None:
        if self._last_report_path and self._last_report_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_report_path)))


def _build_pipeline_steps(state: KnowledgeBaseState) -> list[PipelineStepStatus]:
    collections_latest = _newest(state.collections_primary_last_modified, state.collections_candidate_last_modified)
    concepts_stale = _is_older(state.concepts_last_modified, collections_latest)
    indexes_stale = _is_older(state.indexes_last_modified, state.concepts_last_modified)

    return [
        PipelineStepStatus("InBox ingest", "needs_attention" if state.inbox_markdown_count > 0 else "ok",
            f"Во входящих {state.inbox_markdown_count} заметок: нужен разбор." if state.inbox_markdown_count > 0 else "Входящие пусты или уже разобраны.",
            "Перейти к InBox"),
        PipelineStepStatus("Classification", "needs_attention" if state.zettelkasten_missing_primary_cluster_count > 0 else "ok",
            f"Без llm_primary_cluster: {state.zettelkasten_missing_primary_cluster_count}." if state.zettelkasten_missing_primary_cluster_count > 0 else "Ключевые llm-кластеры в заметках присутствуют.",
            "Перейти к Health"),
        PipelineStepStatus("Primary collections", "not_run" if state.collections_primary_count == 0 else "ok", f"Файлов primary collections: {state.collections_primary_count}.", "Перейти к Pipeline"),
        PipelineStepStatus("Candidate collections", "not_run" if state.collections_candidate_count == 0 else "ok", f"Файлов candidate collections: {state.collections_candidate_count}.", "Перейти к Pipeline"),
        PipelineStepStatus("Concepts", "not_run" if state.concepts_count == 0 else ("stale" if concepts_stale else "ok"),
            "Concepts отсутствуют." if state.concepts_count == 0 else ("Concepts старее collections: рекомендуется пересборка." if concepts_stale else "Concepts актуальны относительно collections."),
            "Перейти к Pipeline"),
        PipelineStepStatus("Indexes", "not_run" if state.indexes_count == 0 else ("stale" if indexes_stale else "ok"),
            "Indexes отсутствуют." if state.indexes_count == 0 else ("Indexes старее concepts: рекомендуется пересборка." if indexes_stale else "Indexes актуальны."),
            "Перейти к Pipeline"),
        PipelineStepStatus("Trace / semantic search", "not_run" if state.traces_count == 0 else "ok", f"Файлов trace-слоя: {state.traces_count}.", "Перейти к Trace"),
        PipelineStepStatus("Health check", "needs_attention" if state.diagnostics else "ok", "Найдены диагностические замечания." if state.diagnostics else "Проблемы путей и структуры не обнаружены.", "Перейти к Health"),
        PipelineStepStatus("Manual transfer to Zettelkasten", "needs_attention" if state.inbox_markdown_count > 0 else "ok",
            "Есть входящие, перенос в Zettelkasten ещё не завершён." if state.inbox_markdown_count > 0 else "Нет входящих для ручного переноса.", "Перейти к InBox"),
    ]

def _is_older(target: datetime | None, baseline: datetime | None) -> bool:
    return bool(target and baseline and target < baseline)


def _newest(first: datetime | None, second: datetime | None) -> datetime | None:
    values = [value for value in (first, second) if value is not None]
    return max(values) if values else None


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
