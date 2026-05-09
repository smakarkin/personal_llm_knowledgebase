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
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Workstation V4"))
        grid = QGridLayout()

        left = QWidget(); ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Guided workflow"))
        self._workflow_select.addItems([f"{w.title}" for w in self._workflows])
        ll.addWidget(self._workflow_select)
        row = QHBoxLayout()
        b_start = QPushButton("Start/Resume")
        b_start.clicked.connect(self._start_or_resume)
        b_next = QPushButton("Next")
        b_next.clicked.connect(self._next_step)
        row.addWidget(b_start); row.addWidget(b_next)
        ll.addLayout(row)
        ll.addWidget(QLabel("Session memory"))
        ll.addWidget(self._sessions)

        center = QWidget(); cl = QVBoxLayout(center)
        cl.addWidget(QLabel("Explainable next actions (3-5)"))
        cl.addWidget(self._actions)
        cl.addWidget(QLabel("Quick command palette"))
        cl.addWidget(self._commands)

        right = QWidget(); rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Details / why this matters"))
        rl.addWidget(self._details)

        grid.addWidget(left, 0, 0); grid.addWidget(center, 0, 1); grid.addWidget(right, 0, 2)
        root.addLayout(grid)

        self._actions.itemClicked.connect(lambda i: self._details.setPlainText(i.data(32) or ""))
        self._commands.itemClicked.connect(self._focus_command)

    def _build_workflows(self) -> list[GuidedWorkflow]:
        return [
            GuidedWorkflow("morning", "Morning review", "Понять текущее состояние и риски.", ("Dashboard refresh", "Review urgent queues", "Pick top action"), "Снижает вероятность пропуска критичных проблем."),
            GuidedWorkflow("inbox", "InBox triage", "Разобрать входящие заметки.", ("Inspect InBox", "Classify", "Prepare transfer bundle"), "Стабилизирует поток новых знаний."),
            GuidedWorkflow("refresh", "Knowledge refresh", "Освежить LLM-слои.", ("Build collections", "Generate concepts", "Generate indexes"), "Поддерживает актуальность knowledge layer."),
            GuidedWorkflow("trace", "Trace investigation", "Проверить спорные связи.", ("Select trace", "Inspect evidence", "Decision"), "Повышает explainability и качество концептов."),
        ]

    def refresh(self) -> None:
        self._sessions.clear()
        for s in self._memory.all_sessions().values():
            self._sessions.addItem(f"{s['session_id']} | {s['workflow_id']} | step={s['step_index']} | {s['status']} | {s['updated_at']}")
        self._fill_actions()
        self._fill_commands()

    def _fill_actions(self) -> None:
        self._actions.clear()
        state = self._inspector.inspect()
        actions = [
            ("urgent maintenance", "Запустить lint и health-check", "Снижает операционные риски прямо сейчас.", "низкая", ["Health", "raw", "12/13"]),
            ("high leverage knowledge work", state.recommended_action.title, state.recommended_action.reason, "средняя", list(state.recommended_action.impacted_layers)),
            ("safe cleanup", "Review deferred queue items", "Закрывает накопившиеся ручные решения без risky writes.", "низкая", ["Review queues"]),
            ("exploratory work", "Trace investigation session", "Помогает найти новые концепты и противоречия.", "средняя", ["14_llm_traces"]),
        ]
        for group, title, why, effort, layers in actions[:5]:
            item = QListWidgetItem(f"[{group}] {title} ({effort})")
            item.setData(32, f"Benefit: {why}\nWhy now: based on current state.\nPrerequisites: none/basic.\nRelated: {', '.join(layers) or '—'}")
            self._actions.addItem(item)

    def _fill_commands(self) -> None:
        self._commands.clear()
        for cmd in ["Open Dashboard", "Open InBox", "Open Sources Review", "Open Health", "Open Trace", "Export transfer queue"]:
            self._commands.addItem(cmd)

    def _start_or_resume(self) -> None:
        wf = self._workflows[self._workflow_select.currentIndex()]
        session = WorkflowSession(session_id=str(uuid.uuid4()), workflow_id=wf.workflow_id, step_index=0)
        self._memory.save_session(session)
        self._details.setPlainText(f"{wf.title}\nGoal: {wf.goal}\nWhy: {wf.why}\nCurrent step: {wf.steps[0]}")
        self.refresh()

    def _next_step(self) -> None:
        selected = self._sessions.currentItem()
        if not selected:
            return
        sid = selected.text().split(" | ")[0]
        sessions = self._memory.all_sessions()
        payload = sessions.get(sid)
        if payload:
            session = WorkflowSession(
                session_id=payload["session_id"],
                workflow_id=payload["workflow_id"],
                step_index=payload["step_index"] + 1,
                status="done" if payload["step_index"] + 1 > 2 else "in_progress",
                notes=payload.get("notes", []),
            )
            self._memory.save_session(session)
        self.refresh()

    def _focus_command(self, item: QListWidgetItem) -> None:
        self._details.setPlainText(f"Command: {item.text()}\nЭто quick access/handoff команда (safe-first, preview-first).")
