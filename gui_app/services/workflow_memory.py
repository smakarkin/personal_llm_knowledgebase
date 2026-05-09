from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gui_app.services.workbench_state import WorkbenchState, WorkbenchStateStore


@dataclass(slots=True)
class WorkflowSession:
    session_id: str
    workflow_id: str
    step_index: int = 0
    status: str = "in_progress"
    notes: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class WorkflowMemoryService:
    """JSON-based workflow/session memory for guided V4 flows."""

    def __init__(self, data_dir: Path) -> None:
        self._store = WorkbenchStateStore(data_dir)

    def all_sessions(self) -> dict[str, dict]:
        state = self._store.load()
        return state.workflow_sessions

    def save_session(self, session: WorkflowSession) -> None:
        state = self._store.load()
        payload = {
            "session_id": session.session_id,
            "workflow_id": session.workflow_id,
            "step_index": session.step_index,
            "status": session.status,
            "notes": session.notes,
            "updated_at": datetime.now().isoformat(),
        }
        state.workflow_sessions[session.session_id] = payload
        self._store.save(state)

    def remember_focus(self, file_path: str) -> None:
        state = self._store.load()
        state.recent_artifacts = WorkbenchStateStore.push_recent(state.recent_artifacts, file_path, limit=20)
        self._store.save(state)

    def dismiss_queue(self, queue_id: str) -> None:
        state = self._store.load()
        state.dismissed_queues = WorkbenchStateStore.push_recent(state.dismissed_queues, queue_id, limit=40)
        self._store.save(state)
