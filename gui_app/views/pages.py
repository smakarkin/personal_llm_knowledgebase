"""Страницы приложения, включая Dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread, Signal
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

from gui_app.services.script_runner import ScriptRunner
from gui_app.services.health_service import HealthData, HealthIssue, HealthService
from gui_app.models.status_models import InboxNoteStatus, KnowledgeBaseState, PipelineStepStatus, ScenarioPlan, ScenarioStep, TraceRunResult
from gui_app.services.state_inspector import StateInspector
from gui_app.services.trace_service import TraceService
from gui_app.services.scenario_planner import ScenarioPlanner
from gui_app.services.obsidian_service import ObsidianService

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
        self._health_summary = QLabel("Health: —")

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
        cards_layout.addWidget(self._make_health_card(), 4, 0, 1, 2)

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
        self._recommendation.setStyleSheet(
            "background:#EEF6FF; border:1px solid #93C5FD; border-radius:8px; padding:10px; font-weight:600;"
        )
        body.addWidget(self._recommendation)
        return card

    def _make_diagnostics_card(self) -> QWidget:
        card, body = self._make_card("Диагностика")
        self._diagnostics.setWordWrap(True)
        self._diagnostics.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._diagnostics.setStyleSheet("color: #8A4B00;")
        body.addWidget(self._diagnostics)
        return card
    def _make_health_card(self) -> QWidget:
        card, body = self._make_card("Health summary")
        self._health_summary.setWordWrap(True)
        body.addWidget(self._health_summary)
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
        self._stat_labels["missing_primary"].setText("—")

        by_id = {item.node_id: item for item in state.layer_states}
        self._stat_labels["collections_primary"].setText(str(by_id.get("build_primary").output_files if by_id.get("build_primary") else 0))
        self._stat_labels["collections_candidate"].setText(str(by_id.get("build_candidate").output_files if by_id.get("build_candidate") else 0))
        concepts_total = sum(by_id.get(k).output_files for k in ("generate_primary_concepts", "generate_candidate_concepts") if by_id.get(k))
        indexes_total = sum(by_id.get(k).output_files for k in ("generate_primary_index", "generate_candidate_index") if by_id.get(k))
        self._stat_labels["concepts"].setText(str(concepts_total))
        self._stat_labels["indexes"].setText(str(indexes_total))
        self._stat_labels["traces"].setText(str(state.traces_count))

        self._time_labels["collections_primary"].setText(_fmt_dt(by_id.get("build_primary").outputs_last_modified if by_id.get("build_primary") else None))
        self._time_labels["collections_candidate"].setText(_fmt_dt(by_id.get("build_candidate").outputs_last_modified if by_id.get("build_candidate") else None))
        self._time_labels["concepts"].setText(_fmt_dt(by_id.get("generate_primary_concepts").outputs_last_modified if by_id.get("generate_primary_concepts") else None))
        self._time_labels["indexes"].setText(_fmt_dt(by_id.get("generate_primary_index").outputs_last_modified if by_id.get("generate_primary_index") else None))

        self._recommendation.setText(state.recommended_action.reason)
        if state.diagnostics:
            self._diagnostics.setText("\n".join(f"• {item}" for item in state.diagnostics))
        else:
            self._diagnostics.setText("Проблемы пути/файлов не обнаружены.")
        health = HealthService(self._inspector.repo_root, self._inspector.repo_root).build_health_report()
        self._health_summary.setText(f"Всего проблем: {len(health.issues)} | Категорий: {len(health.categories)}")


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

    def __init__(self, runner: ScriptRunner, scenario: ScenarioPlan) -> None:
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

    def __init__(self, repo_root: Path, scripts_path: Path, obsidian_service: ObsidianService | None = None, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)
        self._planner = ScenarioPlanner(self._inspector.nodes)
        state = self._inspector.inspect()
        self._scenarios = [self._planner.build_minimal_plan(state), self._planner.build_safe_plan(state), self._planner.build_full_plan(state)]
        self._scenario_by_key = {item.key: item for item in self._scenarios}
        self._worker: _ScenarioWorker | None = None
        self._obsidian = obsidian_service or ObsidianService(repo_root)

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
        risk_hint = "Это может занять несколько минут и перезаписать generated LLM-слои."
        answer = QMessageBox.question(
            self,
            "Подтверждение запуска",
            f"Запустить сценарий '{scenario.title}'?\n\n{risk_hint}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_scenario(scenario)

    def _start_scenario(self, scenario: ScenarioPlan) -> None:
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

    def __init__(self, repo_root: Path, scripts_path: Path, obsidian_service: ObsidianService | None = None, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._repo_root = repo_root
        self._inbox_folder = inbox_folder
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._worker: _ScenarioWorker | None = None
        self._obsidian = obsidian_service or ObsidianService(repo_root)

        self._stats = QLabel("")
        self._status_line = QLabel("")
        self._table = QTableWidget()
        self._classify_btn = QPushButton("Запустить классификацию InBox")
        self._open_folder_btn = QPushButton("Открыть папку InBox")
        self._refresh_btn = QPushButton("Обновить")
        self._open_note_btn = QPushButton("Открыть файл")
        self._open_parent_btn = QPushButton("Открыть родительскую папку")
        self._add_handoff_btn = QPushButton("Добавить в handoff")
        self._handoff_btn = QPushButton("Сформировать handoff report")
        self._handoff_list = QListWidget()
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
        controls.addWidget(self._open_note_btn)
        controls.addWidget(self._open_parent_btn)
        controls.addWidget(self._add_handoff_btn)
        controls.addWidget(self._handoff_btn)
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
        self._open_note_btn.clicked.connect(self._open_selected_note)
        self._open_parent_btn.clicked.connect(self._open_selected_parent)
        self._add_handoff_btn.clicked.connect(self._add_selected_to_handoff)
        self._handoff_btn.clicked.connect(self._generate_handoff_report)

        layout.addWidget(title)
        layout.addWidget(self._hint)
        layout.addLayout(controls)
        layout.addWidget(self._stats)
        layout.addWidget(self._status_line)
        layout.addWidget(self._table, 1)
        layout.addWidget(QLabel("Очередь handoff (ручной перенос в Obsidian)"))
        layout.addWidget(self._handoff_list)

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
        self._refresh_handoff_list()

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
            status_item = self._table.item(row, 5)
            if note.is_ready_for_transfer:
                status_item.setBackground(Qt.GlobalColor.green)
            else:
                status_item.setBackground(Qt.GlobalColor.yellow)
        self._table.resizeColumnsToContents()

    def _run_classification(self) -> None:
        scenario = ScenarioPlan(
            key="classify_inbox_only",
            title="Классификация InBox",
            description=f"Запуск propose_clusters.py для папки {self._inbox_folder}.",
            steps=(ScenarioStep("Классификация InBox", "propose_clusters.py", (self._inbox_folder,)),),
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
        inbox_path = self._inspector.repo_root / self._inbox_folder
        self._obsidian.open_folder(inbox_path)

    def _selected_note(self) -> InboxNoteStatus | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        notes = self._inspector.inspect_inbox_notes()
        return notes[row] if row < len(notes) else None

    def _open_selected_note(self) -> None:
        note = self._selected_note()
        if note:
            self._obsidian.open_file(note.path)

    def _open_selected_parent(self) -> None:
        note = self._selected_note()
        if note:
            self._obsidian.open_parent_folder(note.path)

    def _add_selected_to_handoff(self) -> None:
        note = self._selected_note()
        if note is None:
            return
        status = "ready" if note.is_ready_for_transfer else "needs_attention"
        self._obsidian.add_to_handoff(note.file_name, note.path, status)
        self._refresh_handoff_list()

    def _generate_handoff_report(self) -> None:
        report = self._obsidian.write_handoff_report(self._repo_root / "14_llm_traces")
        self._status_line.setText(f"Сформирован handoff report: {report}")
        self._obsidian.open_file(report)

    def _refresh_handoff_list(self) -> None:
        self._handoff_list.clear()
        for item in self._obsidian.handoff_queue:
            QListWidgetItem(f"{item.title} [{item.status}]", self._handoff_list)




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
    """Экран trace workflow V2: быстрый и углублённый режимы + promotion."""

    def __init__(self, repo_root: Path, scripts_path: Path) -> None:
        super().__init__()
        self._service = TraceService(repo_root=repo_root, scripts_path=scripts_path)
        from gui_app.services.concept_promotion_service import ConceptPromotionService
        self._promotion = ConceptPromotionService(repo_root=repo_root)
        self._worker: _TraceWorker | None = None
        self._last_report_path: Path | None = None

        self._mode = QComboBox(); self._mode.addItems(["Быстрый trace", "Углублённый trace"])
        self._query_input = QPlainTextEdit()
        self._search_btn = QPushButton("Запустить trace")
        self._open_btn = QPushButton("Открыть файл")
        self._status = QLabel("")
        self._history = QListWidget(); self._reports = QListWidget(); self._shortlist = QListWidget()
        self._preview = QPlainTextEdit(); self._log = QPlainTextEdit(); self._filters = QComboBox()
        self._filters.addItems(["Все", "Новые", "Candidate", "Не promoted"])
        self._curate_btn = QPushButton("Сохранить curated report")
        self._promote_btn = QPushButton("Создать concept draft")

        self._build_ui(); self._refresh_lists()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Trace / explainability workflow"))
        self._query_input.setPlaceholderText("Идея -> найденные collections/concepts -> source notes -> concept draft")
        self._preview.setReadOnly(True); self._log.setReadOnly(True)
        top=QHBoxLayout(); top.addWidget(QLabel("Режим:")); top.addWidget(self._mode); top.addWidget(QLabel("Фильтр:")); top.addWidget(self._filters); top.addStretch(1)
        controls=QHBoxLayout(); controls.addWidget(self._search_btn); controls.addWidget(self._open_btn); controls.addWidget(self._curate_btn); controls.addWidget(self._promote_btn); controls.addStretch(1)
        lists=QHBoxLayout(); l=QVBoxLayout(); l.addWidget(QLabel("История")); l.addWidget(self._history,1); l.addWidget(QLabel("Trace reports")); l.addWidget(self._reports,1); l.addWidget(QLabel("Shortlist источников")); l.addWidget(self._shortlist,1)
        r=QVBoxLayout(); r.addWidget(QLabel("Explainability preview")); r.addWidget(self._preview,2); r.addWidget(QLabel("Лог")); r.addWidget(self._log,1)
        lists.addLayout(l,1); lists.addLayout(r,2)
        self._search_btn.clicked.connect(self._start_search); self._open_btn.clicked.connect(self._open_report)
        self._history.itemClicked.connect(lambda it: self._query_input.setPlainText(it.text()))
        self._reports.itemClicked.connect(self._preview_selected_report)
        self._curate_btn.clicked.connect(self._save_curated); self._promote_btn.clicked.connect(self._promote_concept)
        self._filters.currentTextChanged.connect(lambda _: self._refresh_lists())
        layout.addLayout(top); layout.addWidget(self._query_input); layout.addLayout(controls); layout.addWidget(self._status); layout.addLayout(lists,1)

    def _start_search(self) -> None:
        query=self._query_input.toPlainText().strip()
        if not query: QMessageBox.warning(self,"Пустой запрос","Введите описание идеи или понятия."); return
        self._log.clear(); self._status.setText("Выполняется semantic trace..."); self._search_btn.setEnabled(False)
        self._worker=_TraceWorker(self._service,query); self._worker.output_line.connect(self._log.appendPlainText); self._worker.finished_with_result.connect(self._on_search_finished); self._worker.start()

    def _on_search_finished(self, result: TraceRunResult) -> None:
        self._search_btn.setEnabled(True)
        if result.return_code!=0: QMessageBox.warning(self,"Ошибка",result.error_message or "Ошибка semantic trace"); return
        self._last_report_path=result.report_path; self._status.setText(f"Готово: {self._last_report_path}"); self._refresh_lists()
        if self._last_report_path and self._last_report_path.exists(): self._load_report(self._last_report_path)

    def _refresh_lists(self) -> None:
        self._history.clear(); [QListWidgetItem(q,self._history) for q in self._service.recent_history()]
        self._reports.clear(); mode=self._filters.currentText()
        for meta in self._service.list_trace_report_meta():
            if mode=="Новые" and meta.status not in {"draft","new"}: continue
            if mode=="Candidate" and not meta.candidate_for_concept: continue
            if mode=="Не promoted" and meta.promoted_to_concept: continue
            item=QListWidgetItem(f"{meta.path.name} | status={meta.status} | sources={meta.source_items_count}")
            item.setData(Qt.ItemDataRole.UserRole,str(meta.path)); self._reports.addItem(item)

    def _preview_selected_report(self, item: QListWidgetItem) -> None:
        path=Path(item.data(Qt.ItemDataRole.UserRole)); self._last_report_path=path; self._load_report(path)

    def _load_report(self, path: Path) -> None:
        parsed=self._service.parse_trace_report(path); body=parsed['body']
        self._preview.setPlainText(body)
        links=parsed['links']; self._shortlist.clear(); [QListWidgetItem(l,self._shortlist) for l in links]

    def _save_curated(self) -> None:
        if not self._last_report_path: return
        shortlist=[self._shortlist.item(i).text() for i in range(self._shortlist.count())]
        out=self._service.save_curated_trace_report(self._last_report_path, shortlist)
        self._status.setText(f"Сохранён curated report: {out.name}")
        self._refresh_lists()

    def _promote_concept(self) -> None:
        if not self._last_report_path: return
        shortlist=[self._shortlist.item(i).text() for i in range(self._shortlist.count())]
        name=(self._query_input.toPlainText().strip() or "Candidate Concept")[:80]
        concept=self._promotion.create_concept_draft(self._last_report_path, name, shortlist)
        self._status.setText(f"Создан concept draft: {concept.name}")

    def _open_report(self) -> None:
        if self._last_report_path and self._last_report_path.exists(): ObsidianService(self._service.repo_root).open_file(self._last_report_path)


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
        self._issues = QTableWidget(0, 4)
        self._viewer = QPlainTextEdit()
        self._open_file_btn = QPushButton("Открыть файл")
        self._open_source_btn = QPushButton("Открыть источник")
        self._run_rebuild_btn = QPushButton("Запустить rebuild")
        self._goto_trace_btn = QPushButton("Перейти к trace")
        self._issues_cache: list[HealthIssue] = []

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
        self._viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._viewer.setPlaceholderText("Здесь появится текст health-отчёта.")
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
        self._open_file_btn.clicked.connect(self._open_selected_issue_file)
        self._open_source_btn.clicked.connect(self._open_selected_issue_source)
        self._run_rebuild_btn.clicked.connect(self._run_safe_rebuild)
        self._goto_trace_btn.clicked.connect(self._goto_trace)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(controls)
        layout.addWidget(self._status)
        layout.addLayout(report_row)
        layout.addWidget(QLabel("Категории проблем"))
        layout.addWidget(self._categories, 1)
        self._issues.setHorizontalHeaderLabels(["Severity", "Категория", "Файл", "Детали"])
        self._issues.horizontalHeader().setSectionResizeMode(3, self._issues.horizontalHeader().ResizeMode.Stretch)
        self._issues.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._issues.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(QLabel("Проблемы"))
        layout.addWidget(self._issues, 2)
        actions = QHBoxLayout()
        actions.addWidget(self._open_file_btn)
        actions.addWidget(self._open_source_btn)
        actions.addWidget(self._run_rebuild_btn)
        actions.addWidget(self._goto_trace_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Текст отчёта"))
        layout.addWidget(self._viewer, 2)

    def _run_lint(self) -> None:
        self._status.setText("Запуск lint_knowledge_base.py...")
        try:
            result, health = self._service.run_lint()
        except FileNotFoundError as exc:
            self._status.setText("Скрипт lint_knowledge_base.py не найден.")
            self._viewer.setPlainText(str(exc))
            return
        if result.return_code != 0:
            self._status.setText("Lint завершился с ошибкой. Ниже показан stdout/stderr.")
            self._viewer.setPlainText((result.stdout + "\n" + result.stderr).strip())
            self._fill_health(health)
            return
        report = self._service.build_health_report()
        report_path = self._service.save_report_markdown(report)
        self._status.setText(f"Health check завершён успешно. Агрегированный отчёт: {report_path.name}")
        self._fill_health(health)
        self._fill_issues(report.issues)

    def _load_latest(self) -> None:
        self._fill_health(self._service.load_latest_report())
        report = self._service.build_health_report()
        self._fill_issues(report.issues)
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
            ObsidianService(self._service.repo_root).open_file(self._last_report_path)

    def _fill_issues(self, issues: tuple[HealthIssue, ...]) -> None:
        self._issues_cache = list(issues)
        self._issues.setRowCount(0)
        for idx, issue in enumerate(issues):
            self._issues.insertRow(idx)
            self._issues.setItem(idx, 0, QTableWidgetItem(issue.severity))
            self._issues.setItem(idx, 1, QTableWidgetItem(issue.category))
            self._issues.setItem(idx, 2, QTableWidgetItem(issue.path.name))
            self._issues.setItem(idx, 3, QTableWidgetItem(issue.details))

    def _selected_issue(self) -> HealthIssue | None:
        row = self._issues.currentRow()
        if row < 0 or row >= len(self._issues_cache):
            return None
        return self._issues_cache[row]

    def _open_selected_issue_file(self) -> None:
        issue = self._selected_issue()
        if issue:
            ObsidianService(self._service.repo_root).open_file(issue.path)

    def _open_selected_issue_source(self) -> None:
        issue = self._selected_issue()
        if issue:
            ObsidianService(self._service.repo_root).open_parent_folder(issue.path)

    def _run_safe_rebuild(self) -> None:
        self._service._runner.run_script("generate_index.py", ("primary",))
        self._status.setText("Запущен safe rebuild action: generate_index.py primary.")

    def _goto_trace(self) -> None:
        issue = self._selected_issue()
        if issue and "trace" in issue.category:
            ObsidianService(self._service.repo_root).open_parent_folder(self._service.repo_root / "14_llm_traces")


def _build_pipeline_steps(state: KnowledgeBaseState) -> list[PipelineStepStatus]:
    steps: list[PipelineStepStatus] = []
    for layer in state.layer_states:
        steps.append(PipelineStepStatus(layer.title, layer.status, layer.reason, "Открыть Rebuild"))
    return steps


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
