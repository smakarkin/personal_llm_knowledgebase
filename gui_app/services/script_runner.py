"""Сервис для запуска backend-скриптов и готовых rebuild-сценариев."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Callable, Iterable


@dataclass
class ScriptResult:
    """Результат выполнения скрипта."""

    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ScriptStep:
    """Один шаг сценария запуска."""

    title: str
    script_name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScriptScenario:
    """Сценарий, состоящий из последовательности шагов."""

    key: str
    title: str
    description: str
    steps: tuple[ScriptStep, ...]


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

    def run_scenario(
        self,
        scenario: ScriptScenario,
        *,
        on_step_start: Callable[[int, int, ScriptStep], None] | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> list[ScriptResult]:
        """Последовательно выполняет шаги сценария."""
        results: list[ScriptResult] = []
        total = len(scenario.steps)
        for index, step in enumerate(scenario.steps, start=1):
            if on_step_start:
                on_step_start(index, total, step)
            result = self._run_script_streaming(step.script_name, step.args, on_output=on_output)
            results.append(result)
            if result.return_code != 0:
                break
        return results

    def _run_script_streaming(
        self,
        script_name: str,
        args: Iterable[str] | None = None,
        *,
        on_output: Callable[[str], None] | None = None,
    ) -> ScriptResult:
        args = list(args or [])
        script_path = self._resolve_script_path(script_name)
        process = subprocess.Popen(
            ["python", str(script_path), *args],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            if on_output:
                on_output(line.rstrip("\n"))

        return_code = process.wait()
        output = "".join(lines)
        return ScriptResult(return_code=return_code, stdout=output, stderr="")


def build_rebuild_scenarios(inbox_folder: str = "InBox", zettelkasten_folder: str = "Zettelkasten") -> list[ScriptScenario]:
    """Возвращает централизованное описание сценариев для экрана Rebuild."""
    return [
        ScriptScenario(
            key="classify_inbox",
            title="Дозаполнить классификацию InBox",
            description=f"Запустить propose_clusters.py для папки {inbox_folder}.",
            steps=(ScriptStep("Классификация InBox", "propose_clusters.py", (inbox_folder,)),),
        ),
        ScriptScenario(
            key="classify_zettelkasten",
            title="Дозаполнить классификацию Zettelkasten",
            description=f"Запустить propose_clusters.py для папки {zettelkasten_folder}.",
            steps=(ScriptStep("Классификация Zettelkasten", "propose_clusters.py", (zettelkasten_folder,)),),
        ),
        ScriptScenario(
            key="rebuild_primary",
            title="Пересобрать primary layer",
            description="Collections -> Concepts -> Index для режима primary.",
            steps=(
                ScriptStep("Сборка primary collections", "build_collection.py", (zettelkasten_folder, "primary")),
                ScriptStep("Генерация primary concepts", "generate_concepts.py", ("primary",)),
                ScriptStep("Генерация primary index", "generate_index.py", ("primary",)),
            ),
        ),
        ScriptScenario(
            key="rebuild_candidate",
            title="Пересобрать candidate layer",
            description="Collections -> Concepts -> Index для режима candidate.",
            steps=(
                ScriptStep("Сборка candidate collections", "build_collection.py", (zettelkasten_folder, "candidate")),
                ScriptStep("Генерация candidate concepts", "generate_concepts.py", ("candidate",)),
                ScriptStep("Генерация candidate index", "generate_index.py", ("candidate",)),
            ),
        ),
        ScriptScenario(
            key="rebuild_full",
            title="Полная пересборка knowledge layer",
            description="Классификация папки, затем полные primary и candidate этапы.",
            steps=(
                ScriptStep("Классификация Zettelkasten", "propose_clusters.py", (zettelkasten_folder,)),
                ScriptStep("Сборка primary collections", "build_collection.py", (zettelkasten_folder, "primary")),
                ScriptStep("Генерация primary concepts", "generate_concepts.py", ("primary",)),
                ScriptStep("Генерация primary index", "generate_index.py", ("primary",)),
                ScriptStep("Сборка candidate collections", "build_collection.py", (zettelkasten_folder, "candidate")),
                ScriptStep("Генерация candidate concepts", "generate_concepts.py", ("candidate",)),
                ScriptStep("Генерация candidate index", "generate_index.py", ("candidate",)),
            ),
        ),
    ]
