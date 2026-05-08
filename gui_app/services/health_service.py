from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from gui_app.config import LLM_TRACES_DIR
from gui_app.services.script_runner import ScriptResult, ScriptRunner


@dataclass(frozen=True)
class HealthCategory:
    key: str
    title: str
    count: int


@dataclass(frozen=True)
class HealthData:
    report_path: Path | None
    report_text: str
    categories: tuple[HealthCategory, ...]
    parse_ok: bool


_CATEGORY_TITLES = {
    "broken_wikilinks_generated_layers": "Битые ссылки",
    "concepts_without_source_collections": "Concepts без source_collections",
    "indexes_missing_sources": "Indexes без источников",
    "collections_low_source_notes": "Collections слишком маленькие",
    "zettelkasten_missing_llm_primary_cluster": "Notes без llm_primary_cluster",
}


class HealthService:
    def __init__(self, repo_root: Path, scripts_path: Path) -> None:
        self._repo_root = repo_root
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)

    def run_lint(self) -> tuple[ScriptResult, HealthData]:
        result = self._runner.run_script("lint_knowledge_base.py")
        report_path = self._extract_report_path(result.stdout + "\n" + result.stderr)
        return result, self.load_report(report_path)

    def latest_report_path(self) -> Path | None:
        reports = sorted((self._repo_root / LLM_TRACES_DIR).glob("Knowledge base health report - *.md"), reverse=True)
        return reports[0] if reports else None

    def load_latest_report(self) -> HealthData:
        return self.load_report(self.latest_report_path())

    def load_report(self, report_path: Path | None) -> HealthData:
        if report_path is None or not report_path.exists():
            return HealthData(None, "", tuple(), False)

        report_text = report_path.read_text(encoding="utf-8", errors="ignore")
        categories = self._parse_categories_from_markdown(report_text)
        return HealthData(report_path, report_text, categories, bool(categories))

    def _extract_report_path(self, output: str) -> Path | None:
        match = re.search(r"Отчёт:\s*(.+)", output)
        if not match:
            return self.latest_report_path()
        raw = match.group(1).strip().strip('"')
        path = Path(raw)
        if not path.is_absolute():
            path = (self._repo_root / path).resolve()
        return path

    def _parse_categories_from_markdown(self, markdown: str) -> tuple[HealthCategory, ...]:
        rows = re.findall(r"^\|\s*(error|warning)\s*\|\s*([^|]+?)\s*\|", markdown, flags=re.MULTILINE)
        if not rows:
            return tuple()

        counts: dict[str, int] = {}
        for _sev, check in rows:
            key = check.strip()
            counts[key] = counts.get(key, 0) + 1

        categories = [
            HealthCategory(key=key, title=_CATEGORY_TITLES.get(key, key), count=count)
            for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        return tuple(categories)
