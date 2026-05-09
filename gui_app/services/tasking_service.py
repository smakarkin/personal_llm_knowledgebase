from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json, uuid

@dataclass
class TaskRecord:
    task_id: str
    kind: str
    status: str
    started_at: str
    finished_at: str | None = None
    reason: str = ""
    result: dict | None = None


class TaskingService:
    def __init__(self, repo_root: Path) -> None:
        self._file = repo_root / "gui_app" / "gui_app_data" / "task_history.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def start(self, kind: str) -> TaskRecord:
        rec = TaskRecord(task_id=str(uuid.uuid4()), kind=kind, status="running", started_at=datetime.now().isoformat())
        rows = self._load(); rows.insert(0, asdict(rec)); self._save(rows)
        return rec

    def finish(self, task_id: str, status: str, reason: str = "", result: dict | None = None) -> None:
        rows = self._load()
        for r in rows:
            if r["task_id"] == task_id:
                r["status"] = status; r["finished_at"] = datetime.now().isoformat(); r["reason"] = reason; r["result"] = result
                break
        self._save(rows)

    def recent(self, limit: int = 50) -> list[dict]:
        return self._load()[:limit]

    def _load(self) -> list[dict]:
        if not self._file.exists(): return []
        return json.loads(self._file.read_text(encoding='utf-8'))

    def _save(self, rows: list[dict]) -> None:
        self._file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
