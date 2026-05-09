from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable

from gui_app.config import (
    LLM_COLLECTIONS_CANDIDATE_DIR,
    LLM_COLLECTIONS_PRIMARY_DIR,
    LLM_CONCEPTS_DIR,
    LLM_INDEXES_DIR,
    LLM_TRACES_DIR,
)
from gui_app.services.script_runner import ScriptResult, ScriptRunner
from gui_app.services.state_inspector import StateInspector


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


@dataclass(frozen=True)
class HealthIssue:
    category: str
    severity: str
    path: Path
    details: str
    sample: str = ""


@dataclass(frozen=True)
class HealthReport:
    created_at: datetime
    source: str
    issues: tuple[HealthIssue, ...]
    categories: tuple[HealthCategory, ...]


_CATEGORY_TITLES = {
    "broken links": "Битые ссылки",
    "missing sources": "Отсутствуют источники",
    "broken_wikilinks_generated_layers": "Битые ссылки",
    "concepts_without_source_collections": "Concepts без source_collections",
    "indexes_missing_sources": "Indexes без источников",
    "collections_low_source_notes": "Collections слишком маленькие",
    "files with stale upstream dependencies": "Устаревшие зависимости",
    "orphan generated pages": "Сироты generated-слоёв",
    "traces not reviewed": "Trace не reviewed",
    "candidate concepts not promoted": "Candidate concepts не promoted",
    "notes without llm_primary_cluster": "Notes без llm_primary_cluster",
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
    @property
    def repo_root(self) -> Path:
        return self._repo_root

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

    def build_health_report(self) -> HealthReport:
        issues: list[HealthIssue] = []
        lint_data = self.load_latest_report()
        issues.extend(self._issues_from_lint_markdown(lint_data.report_text))
        issues.extend(self._deterministic_filesystem_checks())
        issues.extend(self._stale_issues())
        issues.extend(self._broken_links_generated_layers())
        categories = self._aggregate_categories(issues)
        return HealthReport(
            created_at=datetime.now(),
            source="aggregated_v2",
            issues=tuple(issues),
            categories=categories,
        )

    def save_report_markdown(self, report: HealthReport, keep_last: int = 10) -> Path:
        target = self._repo_root / LLM_TRACES_DIR
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"Health center report - {report.created_at.strftime('%Y-%m-%d %H-%M-%S')}.md"
        lines = [
            "# Health Center Report",
            f"- created_at: {report.created_at.isoformat()}",
            f"- source: {report.source}",
            "",
            "## Summary",
            "| severity | category | count |",
            "|---|---|---:|",
        ]
        for cat in report.categories:
            lines.append(f"| {cat.key} | {cat.title} | {cat.count} |")
        lines.extend(["", "## Issues", "| severity | category | path | details |", "|---|---|---|---|"])
        for issue in report.issues:
            lines.append(f"| {issue.severity} | {issue.category} | {issue.path.as_posix()} | {issue.details} |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._trim_history(prefix="Health center report - ", keep_last=keep_last)
        return path

    def _trim_history(self, prefix: str, keep_last: int) -> None:
        reports = sorted((self._repo_root / LLM_TRACES_DIR).glob(f"{prefix}*.md"), reverse=True)
        for stale in reports[keep_last:]:
            stale.unlink(missing_ok=True)

    def _aggregate_categories(self, issues: Iterable[HealthIssue]) -> tuple[HealthCategory, ...]:
        counts: dict[str, int] = {}
        for issue in issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        categories = [
            HealthCategory(key=key, title=_CATEGORY_TITLES.get(key, key), count=count)
            for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        return tuple(categories)

    def _issues_from_lint_markdown(self, markdown: str) -> list[HealthIssue]:
        issues: list[HealthIssue] = []
        pattern = re.compile(r"^\|\s*(error|warning)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", re.MULTILINE)
        for sev, check, path, details in pattern.findall(markdown or ""):
            category = check.strip().replace("_", " ")
            mapped = "missing sources" if "missing_sources" in check or "indexes_missing_sources" in check else category
            mapped = "notes without llm_primary_cluster" if "llm_primary_cluster" in check else mapped
            mapped = "broken links" if "wikilinks" in check else mapped
            issues.append(HealthIssue(mapped, sev.strip(), Path(path.strip()), details.strip()))
        return issues

    def _deterministic_filesystem_checks(self) -> list[HealthIssue]:
        issues: list[HealthIssue] = []
        concepts_dir = self._repo_root / LLM_CONCEPTS_DIR
        for concept in concepts_dir.glob("*.md"):
            text = concept.read_text(encoding="utf-8", errors="ignore")
            if "concept_mode: candidate" in text and "promoted_to_primary: true" not in text:
                issues.append(HealthIssue("candidate concepts not promoted", "warning", concept, "Нет promoted_to_primary: true"))
        traces_dir = self._repo_root / LLM_TRACES_DIR
        for trace in traces_dir.glob("Trace - *.md"):
            text = trace.read_text(encoding="utf-8", errors="ignore")
            if "status: reviewed" not in text:
                issues.append(HealthIssue("traces not reviewed", "warning", trace, "Нет status: reviewed"))
        return issues

    def _stale_issues(self) -> list[HealthIssue]:
        inspector = StateInspector(self._repo_root)
        state = inspector.inspect()
        return [
            HealthIssue("files with stale upstream dependencies", "warning", self._repo_root / layer.node_id, layer.reason)
            for layer in state.layer_states
            if layer.status in {"stale", "missing"}
        ]

    def _broken_links_generated_layers(self) -> list[HealthIssue]:
        issues: list[HealthIssue] = []
        markdown_files = list((self._repo_root / LLM_COLLECTIONS_PRIMARY_DIR).glob("*.md"))
        markdown_files += list((self._repo_root / LLM_COLLECTIONS_CANDIDATE_DIR).glob("*.md"))
        markdown_files += list((self._repo_root / LLM_CONCEPTS_DIR).glob("*.md"))
        markdown_files += list((self._repo_root / LLM_INDEXES_DIR).glob("*.md"))
        names = {p.stem for p in self._repo_root.rglob("*.md")}
        for path in markdown_files:
            body = path.read_text(encoding="utf-8", errors="ignore")
            for link in re.findall(r"\[\[([^\]|#]+)", body):
                target = link.strip()
                if target and target not in names:
                    issues.append(HealthIssue("broken links", "error", path, f"Broken wikilink: [[{target}]]", sample=target))
        return issues
