from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable

from gui_app.config import LLM_TRACES_DIR
from gui_app.models.status_models import TraceRunResult
from gui_app.services.script_runner import ScriptRunner


class TraceService:
    """Сервис semantic trace: запуск скрипта, история запросов, поиск отчётов."""

    def __init__(self, repo_root: Path, scripts_path: Path | None = None) -> None:
        self._repo_root = repo_root
        self._runner = ScriptRunner(repo_root=repo_root, scripts_path=scripts_path)
        self._history: list[str] = []

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
