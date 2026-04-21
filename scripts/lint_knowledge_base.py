from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import VAULT_PATH

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


GENERATED_LAYER_DIRS = (
    "11_llm_collections_primary",
    "11_llm_collections_candidate",
    "12_llm_concepts",
    "13_llm_indexes",
)


WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")


@dataclass
class LintIssue:
    check: str
    severity: str
    path: Path
    details: str


def safe_print(*args: object) -> None:
    text = " ".join(str(a) for a in args)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        try:
            fallback = text.encode("cp1251", errors="replace").decode("cp1251", errors="replace")
            print(fallback)
        except Exception:
            print("[UNPRINTABLE OUTPUT]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MVP-линтер knowledge base: диагностирует проблемы в generated layers и Zettelkasten."
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=VAULT_PATH,
        help="Путь к корню базы (по умолчанию: VAULT_PATH из config.py).",
    )
    parser.add_argument(
        "--min-source-notes",
        type=int,
        default=2,
        help="Минимум source_notes для collection (по умолчанию: 2).",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Куда сохранить отчёт (по умолчанию: <vault>/14_llm_traces).",
    )
    return parser.parse_args()


def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")

    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            yaml_text = parts[1]
            body = parts[2].lstrip("\n")
            meta = parse_frontmatter_yaml(yaml_text)
            return meta, body

    return {}, text


def parse_frontmatter_yaml(yaml_text: str) -> dict:
    if yaml is not None:
        try:
            meta = yaml.safe_load(yaml_text) or {}
            if isinstance(meta, dict):
                return meta
        except Exception:
            return {}
        return {}

    # Минимальный fallback-парсер, если PyYAML недоступен.
    # Поддерживает плоские поля и списки вида:
    # key:
    #   - item
    data: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if line.lstrip().startswith("- ") and current_list_key:
            item = line.lstrip()[2:].strip().strip('"').strip("'")
            data.setdefault(current_list_key, [])
            if isinstance(data[current_list_key], list):
                data[current_list_key].append(item)
            continue

        current_list_key = None
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            data[key] = []
            current_list_key = key
            continue

        normalized = value.strip('"').strip("'")
        lowered = normalized.lower()
        if lowered == "true":
            data[key] = True
        elif lowered == "false":
            data[key] = False
        else:
            data[key] = normalized

    return data


def collect_markdown_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def build_note_index(vault: Path) -> tuple[set[str], dict[str, int]]:
    paths = collect_markdown_files(vault)
    rel_no_ext: set[str] = set()
    basename_count: dict[str, int] = {}

    for path in paths:
        rel = path.relative_to(vault).as_posix()
        rel_key = rel[:-3] if rel.lower().endswith(".md") else rel
        rel_no_ext.add(rel_key)

        base = path.stem
        basename_count[base] = basename_count.get(base, 0) + 1

    return rel_no_ext, basename_count


def iter_generated_layer_files(vault: Path) -> list[Path]:
    files: list[Path] = []
    for dirname in GENERATED_LAYER_DIRS:
        layer_path = vault / dirname
        if layer_path.exists():
            files.extend(collect_markdown_files(layer_path))
    return sorted(files)


def check_concepts_without_source_collections(vault: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    concepts_dir = vault / "12_llm_concepts"
    if not concepts_dir.exists():
        return issues

    for path in collect_markdown_files(concepts_dir):
        meta, _ = parse_note(path)
        source_collections = meta.get("source_collections")
        if not isinstance(source_collections, list) or len(source_collections) == 0:
            issues.append(
                LintIssue(
                    check="concepts_without_source_collections",
                    severity="error",
                    path=path,
                    details="Пустой или отсутствует source_collections.",
                )
            )
    return issues


def check_indexes_missing_sources(vault: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    indexes_dir = vault / "13_llm_indexes"
    if not indexes_dir.exists():
        return issues

    for path in collect_markdown_files(indexes_dir):
        meta, _ = parse_note(path)
        source_collections = meta.get("source_collections")
        source_concepts = meta.get("source_concepts")

        missing_collections = not isinstance(source_collections, list) or len(source_collections) == 0
        missing_concepts = not isinstance(source_concepts, list) or len(source_concepts) == 0

        if missing_collections or missing_concepts:
            missing = []
            if missing_collections:
                missing.append("source_collections")
            if missing_concepts:
                missing.append("source_concepts")

            issues.append(
                LintIssue(
                    check="indexes_missing_sources",
                    severity="error",
                    path=path,
                    details=f"Пустые/отсутствуют поля: {', '.join(missing)}.",
                )
            )
    return issues


def check_collections_min_source_notes(vault: Path, min_source_notes: int) -> list[LintIssue]:
    issues: list[LintIssue] = []

    for dirname in ("11_llm_collections_primary", "11_llm_collections_candidate"):
        directory = vault / dirname
        if not directory.exists():
            continue

        for path in collect_markdown_files(directory):
            meta, _ = parse_note(path)
            source_notes = meta.get("source_notes")
            if not isinstance(source_notes, list):
                count = 0
            else:
                count = len(source_notes)

            if count < min_source_notes:
                issues.append(
                    LintIssue(
                        check="collections_low_source_notes",
                        severity="warning",
                        path=path,
                        details=f"source_notes={count}, порог={min_source_notes}.",
                    )
                )

    return issues


def normalize_wikilink_target(raw_target: str) -> str:
    target = raw_target.split("|", 1)[0].strip()
    target = target.split("#", 1)[0].strip()
    if target.endswith(".md"):
        target = target[:-3]
    return target


def wikilink_exists(target: str, all_rel_paths_no_ext: set[str], basename_count: dict[str, int]) -> bool:
    if not target:
        return True
    if target in all_rel_paths_no_ext:
        return True

    basename = Path(target).name
    return basename_count.get(basename, 0) > 0


def check_broken_wikilinks(vault: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    all_rel_paths_no_ext, basename_count = build_note_index(vault)

    for path in iter_generated_layer_files(vault):
        _, body = parse_note(path)
        for match in WIKILINK_RE.finditer(body):
            raw = match.group(1)
            target = normalize_wikilink_target(raw)
            if not wikilink_exists(target, all_rel_paths_no_ext, basename_count):
                issues.append(
                    LintIssue(
                        check="broken_wikilinks_generated_layers",
                        severity="warning",
                        path=path,
                        details=f"Битая wikilink: [[{raw}]].",
                    )
                )

    return issues


def check_zettelkasten_missing_primary_cluster(vault: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    zettelkasten_dir = vault / "Zettelkasten"
    if not zettelkasten_dir.exists():
        return issues

    for path in collect_markdown_files(zettelkasten_dir):
        meta, _ = parse_note(path)
        cluster = meta.get("llm_primary_cluster")
        if isinstance(cluster, str):
            cluster = cluster.strip()

        if not cluster:
            issues.append(
                LintIssue(
                    check="zettelkasten_missing_llm_primary_cluster",
                    severity="warning",
                    path=path,
                    details="Отсутствует llm_primary_cluster.",
                )
            )

    return issues


def render_issues_table(vault: Path, issues: list[LintIssue]) -> str:
    if not issues:
        return "Проблем не обнаружено."

    lines = [
        "| severity | check | file | details |",
        "|---|---|---|---|",
    ]

    for issue in issues:
        rel = issue.path.relative_to(vault).as_posix()
        details = issue.details.replace("|", "\\|")
        lines.append(f"| {issue.severity} | {issue.check} | `[[{rel[:-3]}]]` | {details} |")

    return "\n".join(lines)


def render_report(vault: Path, issues: list[LintIssue], args: argparse.Namespace) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    checks = [
        "concepts без source_collections",
        "indexes без source_concepts или source_collections",
        "collections с source_notes ниже порога",
        "broken wikilinks в generated layers",
        "заметки в Zettelkasten без llm_primary_cluster",
    ]

    checks_md = "\n".join(f"- {item}" for item in checks)

    report = f"""# LLM Health Check Report

- Время запуска: **{now}**
- Vault: `{vault}`
- Минимум source_notes: **{args.min_source_notes}**

## Покрытие проверок
{checks_md}

## Сводка
- Ошибки: **{error_count}**
- Предупреждения: **{warning_count}**
- Всего проблем: **{len(issues)}**

## Детали
{render_issues_table(vault, issues)}
"""
    return report


def write_report(report_dir: Path, report_body: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"Knowledge base health report - {ts}.md"
    report_path.write_text(report_body, encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    vault = args.vault.resolve()
    report_dir = args.report_dir.resolve() if args.report_dir else (vault / "14_llm_traces")

    safe_print("[1/6] Инициализация...")
    safe_print("Vault:", vault)

    safe_print("[2/6] Проверка concepts...")
    issues = check_concepts_without_source_collections(vault)

    safe_print("[3/6] Проверка indexes...")
    issues.extend(check_indexes_missing_sources(vault))

    safe_print("[4/6] Проверка collections...")
    issues.extend(check_collections_min_source_notes(vault, args.min_source_notes))

    safe_print("[5/6] Проверка wikilinks...")
    issues.extend(check_broken_wikilinks(vault))

    safe_print("[6/6] Проверка Zettelkasten...")
    issues.extend(check_zettelkasten_missing_primary_cluster(vault))

    report = render_report(vault, issues, args)
    report_path = write_report(report_dir, report)

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    safe_print("Готово.")
    safe_print("Ошибки:", error_count, "| Предупреждения:", warning_count, "| Всего:", len(issues))
    safe_print("Отчёт:", report_path)


if __name__ == "__main__":
    main()
