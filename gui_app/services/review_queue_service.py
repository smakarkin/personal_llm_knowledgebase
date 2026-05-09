from __future__ import annotations

from pathlib import Path

from gui_app.models.queues import ReviewItem
from gui_app.services.frontmatter_utils import parse_frontmatter_block


class ReviewQueueService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def build_review_queues(self) -> dict[str, list[ReviewItem]]:
        return {
            "weak_provenance_concepts": self._weak_provenance_concepts(),
            "promotion_candidates": self._promotion_candidates(),
            "traces_awaiting_decision": self._traces_awaiting_decision(),
            "unresolved_compare_cases": [],
            "source_notes_missing_backlinks": self._source_notes_missing_backlinks(),
            "attachments_deserve_source_note": self._attachments_without_note(),
        }

    def _weak_provenance_concepts(self) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for p in sorted((self.repo_root / "12_llm_concepts").glob("*.md")):
            meta = self._meta(p)
            if len(meta.get("source_collections", [])) == 0:
                items.append(ReviewItem(f"weak-{p.stem}", "weak_provenance", p.stem, "Нет source_collections", str(p)))
        return items

    def _promotion_candidates(self) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for p in sorted((self.repo_root / "14_llm_traces").glob("Trace - *.md"))[:30]:
            meta = self._meta(p)
            if bool(meta.get("candidate_for_concept", False)) and not bool(meta.get("promoted_to_concept", False)):
                items.append(ReviewItem(f"prom-{p.stem}", "promotion", p.stem, "Trace отмечен как candidate", str(p)))
        return items

    def _traces_awaiting_decision(self) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for p in sorted((self.repo_root / "14_llm_traces").glob("Trace - *.md"))[:30]:
            meta = self._meta(p)
            if str(meta.get("status", "draft")) in {"draft", "new", "curated"}:
                items.append(ReviewItem(f"trace-{p.stem}", "trace_decision", p.stem, "Нужен review trace", str(p)))
        return items

    def _source_notes_missing_backlinks(self) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for p in sorted((self.repo_root / "raw").glob("**/*.md"))[:200]:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "[[" not in text:
                items.append(ReviewItem(f"src-back-{p.stem}", "source_backlinks", p.stem, "Нет wikilinks/backlinks", str(p)))
        return items[:50]

    def _attachments_without_note(self) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for ext in ("*.pdf", "*.png", "*.jpg", "*.jpeg"):
            for p in (self.repo_root / "raw").glob(f"**/{ext}"):
                note = p.with_suffix(".md")
                if not note.exists():
                    items.append(ReviewItem(f"att-{p.stem}", "attachment_review", p.name, "Возможен source-note", str(p)))
        return items[:50]

    def _meta(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.startswith("---\n"):
            return {}
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            return {}
        return parse_frontmatter_block(parts[1]) or {}
