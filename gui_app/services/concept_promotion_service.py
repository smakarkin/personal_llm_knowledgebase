from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import yaml


class ConceptPromotionService:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def create_concept_draft(self, trace_path: Path, concept_name: str, shortlist_links: list[str]) -> Path:
        safe_name = re.sub(r'[<>:"/\\|?*]', '-', concept_name).strip() or "Новый concept"
        concept_path = self._repo_root / "12_llm_concepts" / f"{safe_name}.md"
        source_scopes = sorted({link.split('/')[0].replace('[[', '') for link in shortlist_links if '/' in link})

        frontmatter = {
            "type": "llm_concept",
            "concept_mode": "candidate",
            "cluster": "from_trace",
            "source_collections": [],
            "source_scopes": source_scopes,
            "status": "draft",
            "trace_source": f"[[{trace_path.relative_to(self._repo_root).as_posix()[:-3]}]]",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        body = [
            f"# Понятие\n{safe_name}\n",
            "## Основания из trace",
            *[f"- {item}" for item in shortlist_links],
            "\n## Черновой синтез",
            "Заполните вручную на основе supporting notes из trace.",
        ]
        concept_path.write_text("---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n" + "\n".join(body), encoding="utf-8")
        return concept_path
