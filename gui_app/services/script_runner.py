"""Сервис для запуска существующих backend-скриптов через subprocess.

Пока в MVP сервис не интегрирован в UI-кнопки, но задаёт единый способ
вызова скриптов без изменения их бизнес-логики.
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Iterable


@dataclass
class ScriptResult:
    """Результат выполнения скрипта."""

    return_code: int
    stdout: str
    stderr: str


class ScriptRunner:
    """Обёртка для вызова python-скриптов базы знаний."""

    def __init__(self, repo_root: Path, scripts_path: Path | None = None) -> None:
        self.repo_root = repo_root
        self.scripts_path = scripts_path or repo_root

    def run_script(self, script_name: str, args: Iterable[str] | None = None) -> ScriptResult:
        args = list(args or [])
        script_path = self._resolve_script_path(script_name)

        process = subprocess.run(
            ["python", str(script_path), *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return ScriptResult(process.returncode, process.stdout, process.stderr)

    def _resolve_script_path(self, script_name: str) -> Path:
        """Поддерживает оба варианта размещения: ./scripts/* и корень репозитория."""
        candidates = [
            self.scripts_path / script_name,
            self.scripts_path / "scripts" / script_name,
            self.repo_root / "scripts" / script_name,
            self.repo_root / script_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        joined = "\n - ".join(str(path) for path in candidates)
        raise FileNotFoundError(f"Не найден скрипт '{script_name}'. Проверены пути:\n - {joined}")
