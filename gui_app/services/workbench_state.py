from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal
from pathlib import Path


@dataclass
class WorkbenchState:
    last_page: str = "Dashboard"
    recent_trace_queries: list[str] = field(default_factory=list)
    recent_rebuild_scenarios: list[str] = field(default_factory=list)
    pinned_files: list[str] = field(default_factory=list)
    pinned_concepts: list[str] = field(default_factory=list)
    pinned_indexes: list[str] = field(default_factory=list)
    pinned_actions: list[str] = field(default_factory=list)
    recent_artifacts: list[str] = field(default_factory=list)
    recent_runs: list[str] = field(default_factory=list)
    dismissed_recommendations: list[str] = field(default_factory=list)
    deferred_review_items: list[str] = field(default_factory=list)
    pinned_queues: list[str] = field(default_factory=list)
    recent_scenarios: list[str] = field(default_factory=list)
    work_mode_preferences: dict[str, str] = field(default_factory=dict)
    ui_sections_expanded: dict[str, bool] = field(default_factory=dict)
    last_viewed_artifact_per_section: dict[str, str] = field(default_factory=dict)
    review_item_status: dict[str, str] = field(default_factory=dict)
    workflow_sessions: dict[str, dict] = field(default_factory=dict)
    dismissed_queues: list[str] = field(default_factory=list)
    review_decisions: dict[str, list[dict]] = field(default_factory=dict)


class WorkbenchStateStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "workbench_state.json"

    def load(self) -> WorkbenchState:
        if not self.path.exists():
            return WorkbenchState()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return WorkbenchState(**{k: payload.get(k, getattr(WorkbenchState(), k)) for k in WorkbenchState.__annotations__})

    def save(self, state: WorkbenchState) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def push_recent(values: list[str], item: str, limit: int = 10) -> list[str]:
        cleaned = [v for v in values if v != item]
        cleaned.insert(0, item)
        return cleaned[:limit]
