"""Детерминированный анализ текущего состояния базы знаний."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class KnowledgeBaseState:
    inbox_markdown_count: int
    zettelkasten_markdown_count: int
    zettelkasten_missing_primary_cluster_count: int
    collections_primary_count: int
    collections_candidate_count: int
    concepts_count: int
    indexes_count: int
    traces_count: int
    collections_primary_last_modified: datetime | None
    collections_candidate_last_modified: datetime | None
    concepts_last_modified: datetime | None
    indexes_last_modified: datetime | None
    recommended_next_step: str
    diagnostics: list[str]


class StateInspector:
    """Считывает состояние репозитория только по файлам и frontmatter."""

    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        self.repo_root = repo_root
        self.inbox_folder = inbox_folder

    def inspect(self) -> KnowledgeBaseState:
        inbox, inbox_hint = _resolve_vault_dir(self.repo_root, self.inbox_folder)
        zettelkasten, zettelkasten_hint = _resolve_vault_dir(self.repo_root, "Zettelkasten")

        inbox_markdowns = list(_iter_markdown_files(inbox))
        zettelkasten_markdowns = list(_iter_markdown_files(zettelkasten))

        missing_primary = sum(
            1 for note_path in zettelkasten_markdowns if not _has_nonempty_frontmatter_key(note_path, "llm_primary_cluster")
        )

        primary_dir, primary_hint = _resolve_vault_dir(self.repo_root, "11_llm_collections_primary")
        candidate_dir, candidate_hint = _resolve_vault_dir(self.repo_root, "11_llm_collections_candidate")
        concepts_dir, concepts_hint = _resolve_vault_dir(self.repo_root, "12_llm_concepts")
        indexes_dir, indexes_hint = _resolve_vault_dir(self.repo_root, "13_llm_indexes")
        traces_dir, traces_hint = _resolve_vault_dir(self.repo_root, "14_llm_traces")

        primary_files = list(_iter_markdown_files(primary_dir))
        candidate_files = list(_iter_markdown_files(candidate_dir))
        concept_files = list(_iter_markdown_files(concepts_dir))
        index_files = list(_iter_markdown_files(indexes_dir))
        trace_files = list(_iter_files(traces_dir))

        primary_last = _latest_mtime(primary_files)
        candidate_last = _latest_mtime(candidate_files)
        concepts_last = _latest_mtime(concept_files)
        indexes_last = _latest_mtime(index_files)

        diagnostics = self._collect_diagnostics(
            inbox=inbox,
            zettelkasten=zettelkasten,
            primary_dir=primary_dir,
            candidate_dir=candidate_dir,
            concepts_dir=concepts_dir,
            indexes_dir=indexes_dir,
            traces_dir=traces_dir,
            primary_files=primary_files,
            candidate_files=candidate_files,
            concept_files=concept_files,
            index_files=index_files,
            trace_files=trace_files,
            hints=[inbox_hint, zettelkasten_hint, primary_hint, candidate_hint, concepts_hint, indexes_hint, traces_hint],
        )

        recommendation = self._build_recommendation(
            inbox_markdowns=inbox_markdowns,
            zettelkasten_markdowns=zettelkasten_markdowns,
            primary_last=primary_last,
            candidate_last=candidate_last,
            concepts_last=concepts_last,
            indexes_last=indexes_last,
        )

        return KnowledgeBaseState(
            inbox_markdown_count=len(inbox_markdowns),
            zettelkasten_markdown_count=len(zettelkasten_markdowns),
            zettelkasten_missing_primary_cluster_count=missing_primary,
            collections_primary_count=len(primary_files),
            collections_candidate_count=len(candidate_files),
            concepts_count=len(concept_files),
            indexes_count=len(index_files),
            traces_count=len(trace_files),
            collections_primary_last_modified=primary_last,
            collections_candidate_last_modified=candidate_last,
            concepts_last_modified=concepts_last,
            indexes_last_modified=indexes_last,
            recommended_next_step=recommendation,
            diagnostics=diagnostics,
        )


    def _collect_diagnostics(
        self,
        *,
        inbox: Path,
        zettelkasten: Path,
        primary_dir: Path,
        candidate_dir: Path,
        concepts_dir: Path,
        indexes_dir: Path,
        traces_dir: Path,
        primary_files: list[Path],
        candidate_files: list[Path],
        concept_files: list[Path],
        index_files: list[Path],
        trace_files: list[Path],
        hints: list[str | None],
    ) -> list[str]:
        diagnostics: list[str] = []

        for hint in hints:
            if hint:
                diagnostics.append(hint)

        for folder in (inbox, zettelkasten, primary_dir, candidate_dir, concepts_dir, indexes_dir, traces_dir):
            if not folder.exists():
                diagnostics.append(f"Отсутствует папка: {folder}")

        if any(path.exists() for path in (primary_dir, candidate_dir, concepts_dir, indexes_dir)) and not any(
            (primary_files, candidate_files, concept_files, index_files)
        ):
            diagnostics.append("LLM-папки существуют, но markdown-файлы не найдены (проверьте расширения и путь к vault).")

        return diagnostics

    def _build_recommendation(
        self,
        *,
        inbox_markdowns: list[Path],
        zettelkasten_markdowns: list[Path],
        primary_last: datetime | None,
        candidate_last: datetime | None,
        concepts_last: datetime | None,
        indexes_last: datetime | None,
    ) -> str:
        if inbox_markdowns:
            return "В InBox есть заметки: рекомендуется сначала разобрать входящие и разложить их по базе."

        zettelkasten_last = _latest_mtime(zettelkasten_markdowns)
        collections_last = _max_dt(primary_last, candidate_last)

        if zettelkasten_last and (collections_last is None or collections_last < zettelkasten_last):
            return "Collections устарели относительно Zettelkasten: рекомендуется пересобрать collections (primary/candidate)."

        if collections_last and (concepts_last is None or concepts_last < collections_last):
            return "Concepts устарели относительно collections: рекомендуется пересобрать concepts."

        if concepts_last and (indexes_last is None or indexes_last < concepts_last):
            return "Indexes устарели относительно concepts: рекомендуется пересобрать indexes."

        return "Явных проблем не найдено: knowledge layer выглядит актуальным."


def _iter_markdown_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".markdown"}
    ]


def _iter_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return [path for path in folder.rglob("*") if path.is_file()]


def _latest_mtime(files: list[Path]) -> datetime | None:
    if not files:
        return None
    newest = max(path.stat().st_mtime for path in files)
    return datetime.fromtimestamp(newest)


def _max_dt(*values: datetime | None) -> datetime | None:
    existing = [value for value in values if value is not None]
    return max(existing) if existing else None


def _has_nonempty_frontmatter_key(note_path: Path, key: str) -> bool:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return False

    lines = text.splitlines()
    for idx in range(1, len(lines)):
        line = lines[idx]
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            value = line.split(":", 1)[1].strip()
            return bool(value)
    return False


def _resolve_vault_dir(repo_root: Path, configured_name: str) -> tuple[Path, str | None]:
    exact = repo_root / configured_name
    if exact.exists():
        return exact, None

    normalized_target = _normalize_folder_name(configured_name)
    candidates = [p for p in repo_root.iterdir() if p.is_dir() and _normalize_folder_name(p.name) == normalized_target]
    if candidates:
        picked = sorted(candidates, key=lambda item: (item.name != configured_name, item.name))[0]
        return picked, (
            f"Папка '{configured_name}' не найдена, используется '{picked.name}' (правило нормализации имён)."
        )

    return exact, None


def _normalize_folder_name(name: str) -> str:
    return name.strip().lstrip("_").lower().replace("-", "_")
