from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui_app.services.state_inspector import StateInspector
from gui_app.services.workflow_memory import WorkflowMemoryService, WorkflowSession
from gui_app.services.workbench_state import WorkbenchStateStore


@dataclass(frozen=True)
class GuidedWorkflow:
    workflow_id: str
    title: str
    goal: str
    steps: tuple[str, ...]
    why: str


class WorkstationPage(QWidget):
    """V4: guided workflows + explainable planning + quick command access."""

    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        super().__init__()
        self._repo_root = repo_root
        self._inspector = StateInspector(repo_root, inbox_folder=inbox_folder)
        self._memory = WorkflowMemoryService(repo_root / "gui_app" / "gui_app_data")
        self._state_store = WorkbenchStateStore(repo_root / "gui_app" / "gui_app_data")
        self._workflows = self._build_workflows()
        self._commands = QListWidget()
        self._actions = QListWidget()
        self._sessions = QListWidget()
        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)
        self._workflow_select = QComboBox()
        self._current_session_id: str | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Рабочая станция V4"))
        grid = QGridLayout()

        left = QWidget(); ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Пошаговый сценарий"))
        self._workflow_select.addItems([f"{w.title}" for w in self._workflows])
        ll.addWidget(self._workflow_select)
        row = QHBoxLayout()
        b_start = QPushButton("Начать / продолжить")
        b_start.clicked.connect(self._start_or_resume)
        b_next = QPushButton("Следующий шаг")
        b_next.clicked.connect(self._next_step)
        row.addWidget(b_start); row.addWidget(b_next)
        ll.addLayout(row)
        ll.addWidget(QLabel("Память сессий"))
        ll.addWidget(self._sessions)

        center = QWidget(); cl = QVBoxLayout(center)
        cl.addWidget(QLabel("Понятные следующие действия (3–5)"))
        cl.addWidget(self._actions)
        cl.addWidget(QLabel("Быстрые команды"))
        cl.addWidget(self._commands)

        right = QWidget(); rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Подробности / почему это важно"))
        rl.addWidget(self._details)

        grid.addWidget(left, 0, 0); grid.addWidget(center, 0, 1); grid.addWidget(right, 0, 2)
        root.addLayout(grid)

        self._actions.itemClicked.connect(lambda i: self._details.setPlainText(i.data(32) or ""))
        self._commands.itemClicked.connect(self._focus_command)

    def _build_workflows(self) -> list[GuidedWorkflow]:
        return [
            GuidedWorkflow("morning", "Утренний обзор", "Понять текущее состояние и риски.", ("Обновить дашборд", "Проверить срочные очереди", "Выбрать главное действие"), "Снижает вероятность пропуска критичных проблем."),
            GuidedWorkflow("inbox", "Разбор InBox", "Разобрать входящие заметки.", ("Проверить InBox", "Классифицировать", "Подготовить перенос"), "Стабилизирует поток новых знаний."),
            GuidedWorkflow("refresh", "Обновление базы знаний", "Освежить LLM-слои.", ("Собрать коллекции", "Сгенерировать концепты", "Сгенерировать индексы"), "Поддерживает актуальность слоя знаний."),
            GuidedWorkflow("trace", "Проверка трасс", "Проверить спорные связи.", ("Выбрать трассу", "Проверить доказательства", "Принять решение"), "Повышает объяснимость и качество концептов."),
        ]

    def refresh(self) -> None:
        self._sessions.clear()
        for s in self._memory.all_sessions().values():
            row = QListWidgetItem(f"{s['session_id']} | {s['workflow_id']} | step={s['step_index']} | {s['status']} | {s['updated_at']}")
            row.setData(32, s["session_id"])
            self._sessions.addItem(row)
            if s["session_id"] == self._current_session_id:
                self._sessions.setCurrentItem(row)
        self._fill_actions()
        self._fill_commands()

    def _fill_actions(self) -> None:
        self._actions.clear()
        state = self._inspector.inspect()
        actions = [
            ("срочное обслуживание", "Запустить lint и health-check", "Снижает операционные риски прямо сейчас.", "низкая", ["Health", "raw", "12/13"]),
            ("важная работа со знаниями", state.recommended_action.title, state.recommended_action.reason, "средняя", list(state.recommended_action.impacted_layers)),
            ("безопасная очистка", "Проверить отложенные элементы очереди", "Закрывает накопившиеся ручные решения без рискованных изменений.", "низкая", ["Очереди review"]),
            ("исследование", "Сессия проверки трасс", "Помогает найти новые концепты и противоречия.", "средняя", ["14_llm_traces"]),
        ]
        for group, title, why, effort, layers in actions[:5]:
            item = QListWidgetItem(f"[{group}] {title} ({effort})")
            item.setData(32, f"Польза: {why}\nПочему сейчас: основано на текущем состоянии.\nТребования: нет/базовые.\nСвязано с: {', '.join(layers) or '—'}")
            self._actions.addItem(item)

    def _fill_commands(self) -> None:
        self._commands.clear()
        for cmd in ["Открыть Dashboard", "Открыть InBox", "Открыть проверку источников", "Открыть Health", "Открыть Trace", "Экспортировать очередь переноса"]:
            self._commands.addItem(cmd)

    def _start_or_resume(self) -> None:
        wf = self._workflows[self._workflow_select.currentIndex()]
        session = WorkflowSession(session_id=str(uuid.uuid4()), workflow_id=wf.workflow_id, step_index=0)
        self._memory.save_session(session)
        self._current_session_id = session.session_id
        self._details.setPlainText(f"{wf.title}\nЦель: {wf.goal}\nПочему: {wf.why}\nТекущий шаг: {wf.steps[0]}")
        self.refresh()

    def _next_step(self) -> None:
        selected = self._sessions.currentItem()
        sid = selected.data(32) if selected else self._current_session_id
        if not sid:
            self._details.setPlainText("Сначала запустите или выберите workflow session.")
            return
        sessions = self._memory.all_sessions()
        payload = sessions.get(sid)
        if payload:
            wf = next((w for w in self._workflows if w.workflow_id == payload["workflow_id"]), None)
            next_step_index = payload["step_index"] + 1
            done = wf is not None and next_step_index >= len(wf.steps)
            session = WorkflowSession(
                session_id=payload["session_id"],
                workflow_id=payload["workflow_id"],
                step_index=next_step_index,
                status="done" if done else "in_progress",
                notes=payload.get("notes", []),
            )
            self._memory.save_session(session)
            self._current_session_id = session.session_id
            if wf is not None:
                step_label = "Завершено" if done else wf.steps[next_step_index]
                self._details.setPlainText(
                    f"{wf.title}\nШаг: {session.step_index}/{len(wf.steps)}\nСтатус: {session.status}\nТекущий: {step_label}"
                )
        self.refresh()

    def _focus_command(self, item: QListWidgetItem) -> None:
        self._details.setPlainText(f"Команда: {item.text()}\nЭто команда быстрого доступа (сначала безопасный просмотр).")
