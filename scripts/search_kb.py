from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import VAULT_PATH

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

DEFAULT_SEARCH_DIRS = (
    "11_llm_collections_primary",
    "11_llm_collections_candidate",
    "12_llm_concepts",
    "13_llm_indexes",
)


@dataclass
class SearchHit:
    path: Path
    rel_path: str
    title: str
    snippet: str


def safe_print(*args: object) -> None:
    text = " ".join(str(a) for a in args)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        print(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Локальный поиск по markdown knowledge base. "
            "По умолчанию ищет в generated layers (11-13)."
        )
    )
    parser.add_argument("query", nargs="*", help="Поисковый запрос (ключевые слова).")
    parser.add_argument(
        "--vault",
        type=Path,
        default=VAULT_PATH,
        help="Путь к корню базы (по умолчанию: VAULT_PATH из config.py).",
    )
    parser.add_argument(
        "--dir",
        dest="dirs",
        action="append",
        default=None,
        help=(
            "Доп. директория для поиска (относительно --vault). "
            "Можно указать несколько раз. Если указано, заменяет стандартный набор 11-13."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("primary", "candidate"),
        default=None,
        help="Фильтр по mode (frontmatter: collection_mode/concept_mode/index_mode или имени файла).",
    )
    parser.add_argument(
        "--type",
        dest="type_filter",
        choices=("llm_collection", "llm_concept", "llm_index"),
        default=None,
        help="Фильтр по frontmatter полю type.",
    )
    parser.add_argument(
        "--frontmatter-only",
        action="store_true",
        help="Искать только в frontmatter (без тела заметки).",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Чувствительный к регистру поиск.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Лимит результатов (по умолчанию: 20).",
    )
    return parser.parse_args()


def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            yaml_text = parts[1]
            body = parts[2].lstrip("\n")
            return parse_frontmatter_yaml(yaml_text), body
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


def iter_markdown_files(vault: Path, target_dirs: list[str]) -> list[Path]:
    files: list[Path] = []
    for dirname in target_dirs:
        root = vault / dirname
        if not root.exists() or not root.is_dir():
            continue
        files.extend(sorted(p for p in root.rglob("*.md") if p.is_file()))
    return sorted(files)


def normalize_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(normalize_text(v) for v in value)
    return str(value)


def resolve_mode(meta: dict, path: Path) -> str | None:
    for key in ("collection_mode", "concept_mode", "index_mode"):
        value = meta.get(key)
        if isinstance(value, str) and value in ("primary", "candidate"):
            return value

    name = path.stem.lower()
    if "primary" in name:
        return "primary"
    if "candidate" in name:
        return "candidate"
    return None


def build_title(meta: dict, body: str, path: Path) -> str:
    for key in ("title", "concept", "cluster"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def build_search_text(meta: dict, body: str, frontmatter_only: bool) -> str:
    fm_text = "\n".join(f"{k}: {normalize_text(v)}" for k, v in meta.items())
    if frontmatter_only:
        return fm_text
    return f"{fm_text}\n{body}".strip()


def match_query(text: str, query: str, case_sensitive: bool) -> int:
    if not query:
        return 0

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(re.escape(query), flags)
    except re.error:
        return -1

    found = pattern.search(text)
    if not found:
        return -1
    return found.start()


def make_snippet(text: str, pos: int, radius: int = 80) -> str:
    clean = " ".join(text.split())
    if not clean:
        return "(пустой фрагмент)"
    if pos < 0:
        pos = 0

    start = max(0, pos - radius)
    end = min(len(clean), pos + radius)
    snippet = clean[start:end].strip()

    if start > 0:
        snippet = "…" + snippet
    if end < len(clean):
        snippet = snippet + "…"
    return snippet or "(пустой фрагмент)"


def find_hits(
    files: list[Path],
    vault: Path,
    query: str,
    mode_filter: str | None,
    type_filter: str | None,
    frontmatter_only: bool,
    case_sensitive: bool,
    limit: int,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for path in files:
        meta, body = parse_note(path)

        if type_filter:
            current_type = meta.get("type")
            if current_type != type_filter:
                continue

        if mode_filter:
            current_mode = resolve_mode(meta, path)
            if current_mode != mode_filter:
                continue

        search_text = build_search_text(meta, body, frontmatter_only)
        pos = match_query(search_text, query, case_sensitive)
        if query and pos < 0:
            continue

        rel = path.relative_to(vault).as_posix()
        rel_no_ext = rel[:-3] if rel.lower().endswith(".md") else rel
        hits.append(
            SearchHit(
                path=path,
                rel_path=rel,
                title=build_title(meta, body, path),
                snippet=make_snippet(search_text, pos),
            )
        )

        if len(hits) >= limit:
            break
    return hits


def print_results(hits: list[SearchHit], query: str) -> None:
    if not hits:
        safe_print("Ничего не найдено.")
        return

    safe_print(f"Найдено: {len(hits)} (запрос: {query or '<пустой>'})")
    safe_print("-" * 80)
    for i, hit in enumerate(hits, start=1):
        link = f"[[{hit.rel_path[:-3]}]]" if hit.rel_path.lower().endswith(".md") else f"[[{hit.rel_path}]]"
        safe_print(f"{i}. path: {hit.rel_path}")
        safe_print(f"   link: {link}")
        safe_print(f"   title: {hit.title}")
        safe_print(f"   snippet: {hit.snippet}")
        safe_print()


def main() -> int:
    args = parse_args()

    query = " ".join(args.query).strip()
    target_dirs = args.dirs if args.dirs else list(DEFAULT_SEARCH_DIRS)

    vault = args.vault.expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        safe_print(f"Ошибка: vault не найден или не является каталогом: {vault}")
        return 2

    files = iter_markdown_files(vault, target_dirs)
    if not files:
        safe_print("Предупреждение: markdown-файлы для поиска не найдены в указанных директориях.")
        safe_print("Проверено:", ", ".join(target_dirs))
        return 0

    hits = find_hits(
        files=files,
        vault=vault,
        query=query,
        mode_filter=args.mode,
        type_filter=args.type_filter,
        frontmatter_only=args.frontmatter_only,
        case_sensitive=args.case_sensitive,
        limit=max(1, args.limit),
    )
    print_results(hits, query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
