"""Детерминированный V2 анализ состояния knowledge base через state graph."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from gui_app.config import DEFAULT_ZETTELKASTEN_FOLDER, LLM_COLLECTIONS_CANDIDATE_DIR, LLM_COLLECTIONS_PRIMARY_DIR, LLM_CONCEPTS_DIR, LLM_INDEXES_DIR, LLM_TRACES_DIR
from gui_app.services.frontmatter_utils import parse_frontmatter_block
from gui_app.models.status_models import InboxNoteStatus, KnowledgeBaseState, LayerState, PipelineEdge, PipelineNode, RecommendedAction


class StateInspector:
    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        self.repo_root = repo_root
        self.inbox_folder = inbox_folder
        self.nodes, self.edges = self._build_graph()

    def _build_graph(self) -> tuple[dict[str, PipelineNode], tuple[PipelineEdge, ...]]:
        nodes = {
            "classify_inbox": PipelineNode("classify_inbox", "Классификация InBox", ("propose_clusters.py", self.inbox_folder)),
            "classify_zettelkasten": PipelineNode("classify_zettelkasten", "Классификация Zettelkasten", ("propose_clusters.py", DEFAULT_ZETTELKASTEN_FOLDER)),
            "build_primary": PipelineNode("build_primary", "Primary collections", ("build_collection.py", DEFAULT_ZETTELKASTEN_FOLDER, "primary"), ("classify_zettelkasten",), (LLM_COLLECTIONS_PRIMARY_DIR,)),
            "generate_primary_concepts": PipelineNode("generate_primary_concepts", "Primary concepts", ("generate_concepts.py", "primary"), ("build_primary",), (LLM_CONCEPTS_DIR,)),
            "generate_primary_index": PipelineNode("generate_primary_index", "Primary index", ("generate_index.py", "primary"), ("generate_primary_concepts",), (LLM_INDEXES_DIR,)),
            "build_candidate": PipelineNode("build_candidate", "Candidate collections", ("build_collection.py", DEFAULT_ZETTELKASTEN_FOLDER, "candidate"), ("classify_zettelkasten",), (LLM_COLLECTIONS_CANDIDATE_DIR,)),
            "generate_candidate_concepts": PipelineNode("generate_candidate_concepts", "Candidate concepts", ("generate_concepts.py", "candidate"), ("build_candidate",), (LLM_CONCEPTS_DIR,)),
            "generate_candidate_index": PipelineNode("generate_candidate_index", "Candidate index", ("generate_index.py", "candidate"), ("generate_candidate_concepts",), (LLM_INDEXES_DIR,)),
            "trace": PipelineNode("trace", "Semantic trace", ("semantic_trace.py", "<query>"), output_dirs=(LLM_TRACES_DIR,)),
            "health": PipelineNode("health", "Health check", ("lint_knowledge_base.py",)),
        }
        edges = tuple(PipelineEdge(src, dst) for dst, n in nodes.items() for src in n.dependencies)
        return nodes, edges

    def inspect(self) -> KnowledgeBaseState:
        inbox = self.repo_root / self.inbox_folder
        zettel = self.repo_root / DEFAULT_ZETTELKASTEN_FOLDER
        zettel_last = _latest_mtime(_iter_markdown_files(zettel))

        layer_states: list[LayerState] = []
        diagnostics: list[str] = []
        for node in self.nodes.values():
            files = []
            for out in node.output_dirs:
                output_dir = self.repo_root / out
                if not output_dir.exists():
                    diagnostics.append(f"Отсутствует папка: {output_dir}")
                files.extend(_iter_markdown_files(output_dir))
            outputs_last = _latest_mtime(files)
            if not node.output_dirs:
                status, reason = "ok", "Служебный узел без материального артефакта."
            elif not files:
                status, reason = "missing", "Выходные артефакты не найдены."
            elif zettel_last and outputs_last and outputs_last < zettel_last and "classify" not in node.node_id:
                status, reason = "stale", "Артефакты устарели относительно изменений в Zettelkasten."
            else:
                status, reason = "ok", "Артефакты выглядят актуальными."
            layer_states.append(LayerState(node.node_id, node.title, status, reason, zettel_last, outputs_last, len(files)))

        recommended = self._build_recommendation(layer_states, inbox)
        return KnowledgeBaseState(
            inbox_markdown_count=len(_iter_markdown_files(inbox)),
            zettelkasten_markdown_count=len(_iter_markdown_files(zettel)),
            traces_count=len(_iter_files(self.repo_root / LLM_TRACES_DIR)),
            layer_states=tuple(layer_states),
            recommended_action=recommended,
            diagnostics=diagnostics,
        )

    def _build_recommendation(self, layers: list[LayerState], inbox: Path) -> RecommendedAction:
        if _iter_markdown_files(inbox):
            return RecommendedAction("classify_inbox", "Классифицировать InBox", self.nodes["classify_inbox"].command, "В InBox есть заметки, сначала нужно разметить входящий слой.", ("InBox",))
        stale = [layer for layer in layers if layer.status in {"stale", "missing"}]
        if stale:
            first = stale[0]
            node = self.nodes[first.node_id]
            return RecommendedAction(first.node_id, f"Запустить: {first.title}", node.command, first.reason, tuple(item.title for item in stale))
        return RecommendedAction("health", "Запустить Health check", self.nodes["health"].command, "Явных stale-слоёв не найдено; рекомендуем проверку целостности.", ("health",))

    def inspect_inbox_notes(self) -> list[InboxNoteStatus]:
        inbox = self.repo_root / self.inbox_folder
        notes: list[InboxNoteStatus] = []
        for note_path in sorted(_iter_markdown_files(inbox), key=lambda item: item.name.lower()):
            text = note_path.read_text(encoding="utf-8", errors="ignore")
            meta = _parse_frontmatter(text)
            has_primary = bool(str(meta.get("llm_primary_cluster", "")).strip())
            has_candidates = _has_candidate_clusters(meta.get("llm_candidate_clusters"))
            has_skip_reason = bool(str(meta.get("llm_skip_reason", "")).strip())
            is_processed = bool(meta.get("llm_processed") is True)
            has_topic = bool(str(meta.get("llm_topic", "")).strip())
            has_semantic_type = bool(str(meta.get("llm_semantic_type", "")).strip())
            has_cluster_alias = bool(str(meta.get("llm_cluster", "")).strip())
            body = text.split("---", 2)[-1].strip() if text.startswith("---") else text.strip()
            is_empty = not body
            is_ready = (
                (not is_empty)
                and (not has_skip_reason)
                and is_processed
                and has_topic
                and has_semantic_type
                and has_cluster_alias
                and (has_primary or has_candidates)
            )
            notes.append(InboxNoteStatus(note_path.name, note_path, has_primary, has_candidates, has_skip_reason, is_empty, is_ready))
        return notes


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return parse_frontmatter_block(parts[1]) or {}


def _has_candidate_clusters(raw_value: object) -> bool:
    if isinstance(raw_value, list):
        return any(str(item).strip() for item in raw_value)
    return bool(str(raw_value or "").strip())


def _iter_markdown_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".markdown"}]


def _iter_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return [path for path in folder.rglob("*") if path.is_file()]


def _latest_mtime(files: list[Path]) -> datetime | None:
    if not files:
        return None
    newest = max(path.stat().st_mtime for path in files)
    return datetime.fromtimestamp(newest)
