from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from datetime import datetime
from typing import Callable


from gui_app.config import LLM_TRACES_DIR
from gui_app.models.status_models import TraceRunResult
from gui_app.services.script_runner import ScriptRunner
from gui_app.services.frontmatter_utils import dump_frontmatter, parse_frontmatter_block


@dataclass(frozen=True)
class TraceReportMeta:
    path: Path
    title: str
    status: str
    candidate_for_concept: bool
    promoted_to_concept: bool
    source_items_count: int
    trace_created_at: str


class TraceService:
    """Сервис semantic trace: запуск, чтение отчётов, explainability-данные."""

    def __init__(self, repo_root: Path, scripts_path: Path | None = None) -> None:
        self._repo_root = repo_root
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._history: list[str] = []

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def script_exists(self) -> bool:
        try:
            self._runner._resolve_script_path("semantic_trace.py")
            return True
        except FileNotFoundError:
            return False

    def add_history(self, query: str, limit: int = 10) -> None:
        value = query.strip()
        if not value:
            return
        self._history = [item for item in self._history if item != value]
        self._history.insert(0, value)
        del self._history[limit:]

    def recent_history(self) -> list[str]:
        return list(self._history)

    def list_trace_reports(self, limit: int = 50) -> list[Path]:
        traces_dir = self._repo_root / LLM_TRACES_DIR
        if not traces_dir.exists():
            return []
        files = sorted(traces_dir.glob("Trace - *.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]

    def parse_trace_report(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = {}
        body = text
        if text.startswith("---\n"):
            parts = text.split("---\n", 2)
            if len(parts) >= 3:
                meta = parse_frontmatter_block(parts[1]) or {}
                body = parts[2]
        links = re.findall(r"\[\[(.+?)\]\]", body)
        return {"meta": meta, "body": body, "links": links, "path": path}

    def list_trace_report_meta(self) -> list[TraceReportMeta]:
        items: list[TraceReportMeta] = []
        for path in self.list_trace_reports(limit=200):
            parsed = self.parse_trace_report(path)
            meta = parsed["meta"]
            source_items = meta.get("source_items") or []
            items.append(
                TraceReportMeta(
                    path=path,
                    title=path.stem,
                    status=str(meta.get("status", "draft")),
                    candidate_for_concept=bool(meta.get("candidate_for_concept", False)),
                    promoted_to_concept=bool(meta.get("promoted_to_concept", False)),
                    source_items_count=len(source_items) if isinstance(source_items, list) else 0,
                    trace_created_at=str(meta.get("trace_created_at", "")),
                )
            )
        return items

    def save_curated_trace_report(self, source_path: Path, shortlist_links: list[str], note: str = "") -> Path:
        parsed = self.parse_trace_report(source_path)
        meta = parsed["meta"]
        body = parsed["body"]
        meta.update(
            {
                "type": "llm_trace",
                "status": meta.get("status", "curated"),
                "candidate_for_concept": bool(meta.get("candidate_for_concept", False)),
                "promoted_to_concept": bool(meta.get("promoted_to_concept", False)),
                "source_items": shortlist_links,
                "curated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        appendix = "\n\n## Curated shortlist\n" + "\n".join(f"- {item}" for item in shortlist_links)
        if note.strip():
            appendix += f"\n\n## Curator notes\n{note.strip()}\n"
        target = source_path.with_name(source_path.stem + " - curated.md")
        target.write_text("---\n" + dump_frontmatter(meta) + "---\n" + body + appendix, encoding="utf-8")
        return target

    def run_trace(self, query: str, on_output: Callable[[str], None] | None = None) -> TraceRunResult:
        cleaned = query.strip()
        if not cleaned:
            return TraceRunResult(return_code=1, stdout="", report_path=None, error_message="Введите описание идеи.")

        try:
            script_path = self._runner._resolve_script_path("semantic_trace.py")
        except FileNotFoundError as exc:
            return TraceRunResult(return_code=1, stdout="", report_path=None, error_message=str(exc))

        process = subprocess.Popen(
            ["python", str(script_path), cleaned],
            cwd=self._repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        report_path: Path | None = None
        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            value = line.rstrip("\n")
            lines.append(line)
            if value.startswith("SAVED REPORT:"):
                maybe = Path(value.replace("SAVED REPORT:", "", 1).strip())
                if maybe.exists():
                    report_path = maybe
            if on_output:
                on_output(value)

        code = process.wait()
        output = "".join(lines)
        if report_path is None:
            reports = self.list_trace_reports(limit=1)
            if reports:
                report_path = reports[0]

        if code == 0:
            self.add_history(cleaned)
        return TraceRunResult(return_code=code, stdout=output, report_path=report_path)
