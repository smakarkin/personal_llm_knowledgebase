"""Typed models for V3 operational queues and review workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QueuePriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ReviewStatus(str, Enum):
    new = "new"
    in_review = "in_review"
    deferred = "deferred"
    accepted = "accepted"
    rejected = "rejected"
    promoted = "promoted"
    archived = "archived"


@dataclass(slots=True)
class ReviewItem:
    item_id: str
    queue_id: str
    title: str
    reason: str
    file_path: str | None = None
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    preview: str = ""
    status: ReviewStatus = ReviewStatus.new


@dataclass(slots=True)
class OperationalQueue:
    queue_id: str
    title: str
    why_exists: str
    recommended_action: str
    priority: QueuePriority
    open_items: list[ReviewItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len([i for i in self.open_items if i.status in {ReviewStatus.new, ReviewStatus.in_review}])


@dataclass(slots=True)
class WorkMode:
    mode_id: str
    title: str
    queue_ids: list[str]
    actions: list[str]
