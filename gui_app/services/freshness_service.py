from __future__ import annotations
from pathlib import Path
from datetime import datetime

class FreshnessService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def compute(self) -> dict[str, str]:
        def mtime(p: Path) -> float:
            files = list(p.glob('*.md')) if p.exists() else []
            return max((f.stat().st_mtime for f in files), default=0.0)
        collections = max(mtime(self.repo_root/'11_llm_collections_primary'), mtime(self.repo_root/'11_llm_collections_candidate'))
        concepts = mtime(self.repo_root/'12_llm_concepts')
        indexes = mtime(self.repo_root/'13_llm_indexes')
        traces = mtime(self.repo_root/'14_llm_traces')
        idx_file = self.repo_root/'gui_app'/'gui_app_data'/'semantic_index.json'
        idx = idx_file.stat().st_mtime if idx_file.exists() else 0.0
        return {
            'semantic_index': 'stale' if idx < max(collections, concepts, indexes, traces) else 'fresh',
            'concepts_vs_collections': 'stale' if concepts < collections else 'fresh',
            'indexes_vs_concepts': 'stale' if indexes < concepts else 'fresh',
            'traces_vs_layers': 'stale' if traces < concepts else 'fresh',
            'checked_at': datetime.now().isoformat(),
        }
