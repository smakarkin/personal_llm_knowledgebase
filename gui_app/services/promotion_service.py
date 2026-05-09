from __future__ import annotations

from pathlib import Path

from gui_app.services.concept_promotion_service import ConceptPromotionService


class PromotionService:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._legacy = ConceptPromotionService(repo_root)

    def promote_from_trace(self, trace_path: Path, concept_name: str, links: list[str]) -> Path:
        return self._legacy.create_concept_draft(trace_path, concept_name, links)

    def promote_from_collection(self, collection_path: Path, concept_name: str) -> Path:
        links = [f"[[{collection_path.relative_to(self._repo_root).as_posix()[:-3]}]]"]
        return self._legacy.create_concept_draft(collection_path, concept_name, links)

    def promote_from_multi_collection(self, collection_paths: list[Path], concept_name: str) -> Path:
        links = [f"[[{p.relative_to(self._repo_root).as_posix()[:-3]}]]" for p in collection_paths]
        return self._legacy.create_concept_draft(collection_paths[0], concept_name, links)
