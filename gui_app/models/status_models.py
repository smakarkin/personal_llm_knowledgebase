"""Typed models for GUI state and workflow statuses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


PipelineStatus = Literal["ok", "needs_attention", "stale", "not_run"]


@dataclass(frozen=True)
class PipelineStepStatus:
    title: str
    status: PipelineStatus
    explanation: str
    link: str


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
class RebuildScenario:
    key: str
    title: str
    description: str
    steps: tuple["RebuildStep", ...]


@dataclass(frozen=True)
class RebuildStep:
    title: str
    script_name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class TraceRunResult:
    return_code: int
    stdout: str
    report_path: Path | None
    error_message: str | None = None


@dataclass(frozen=True)
class KnowledgeBaseState:
    inbox_markdown_count: int
    zettelkasten_markdown_count: int
    zettelkasten_missing_primary_cluster_count: int
    collections_primary_count: int
    collections_candidate_count: int
    concepts_count: int
    indexes_count: int
    traces_count: int
    inbox_last_modified: datetime | None
    zettelkasten_last_modified: datetime | None
    collections_primary_last_modified: datetime | None
    collections_candidate_last_modified: datetime | None
    concepts_last_modified: datetime | None
    indexes_last_modified: datetime | None
    recommended_next_step: str
    diagnostics: list[str]
