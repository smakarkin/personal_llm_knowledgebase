"""Typed models for GUI orchestration/state V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

PipelineStatus = Literal["ok", "needs_attention", "stale", "not_run", "blocked", "missing"]


@dataclass(frozen=True)
class LayerState:
    """Состояние отдельного слоя/этапа knowledge base."""

    node_id: str
    title: str
    status: PipelineStatus
    reason: str
    inputs_last_modified: datetime | None
    outputs_last_modified: datetime | None
    output_files: int
    stale_sources: tuple[str, ...] = ()
    blocking_nodes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineNode:
    """Узел state-graph с явными зависимостями и артефактами."""

    node_id: str
    title: str
    command: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    output_dirs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineEdge:
    """Ребро между узлами графа pipeline."""

    source: str
    target: str


@dataclass(frozen=True)
class RecommendedAction:
    """Объяснимая рекомендация следующего шага."""

    node_id: str
    title: str
    command: tuple[str, ...]
    reason: str
    impacted_layers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioStep:
    title: str
    script_name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioPlan:
    """План запуска сценария для Rebuild/Plan Preview."""

    key: str
    title: str
    description: str
    steps: tuple[ScenarioStep, ...]


@dataclass(frozen=True)
class InboxNoteStatus:
    file_name: str
    path: Path
    has_primary_cluster: bool
    has_candidate_clusters: bool
    has_skip_reason: bool
    is_empty: bool
    is_ready_for_transfer: bool


@dataclass(frozen=True)
class TraceRunResult:
    return_code: int
    stdout: str
    report_path: Path | None
    error_message: str | None = None


@dataclass(frozen=True)
class KnowledgeBaseState:
    """Сводное состояние knowledge base + оркестрационный граф."""

    inbox_markdown_count: int
    zettelkasten_markdown_count: int
    traces_count: int
    layer_states: tuple[LayerState, ...]
    recommended_action: RecommendedAction
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineStepStatus:
    title: str
    status: PipelineStatus
    explanation: str
    link: str
