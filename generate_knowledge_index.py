from pathlib import Path
import re
import sys
from typing import Callable
import yaml

from config import VAULT_PATH

VAULT = VAULT_PATH

COLLECTIONS_PRIMARY_DIR = VAULT / "11_llm_collections_primary"
COLLECTIONS_CANDIDATE_DIR = VAULT / "11_llm_collections_candidate"
CONCEPTS_DIR = VAULT / "12_llm_concepts"
INDEXES_DIR = VAULT / "13_llm_indexes"
DEFAULT_OUTPUT_NAME = "Knowledge index.md"


def safe_print(*args):
    text = " ".join(str(a) for a in args)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        print(text)


def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")

    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            yaml_text = parts[1]
            body = parts[2].lstrip("\n")
            try:
                meta = yaml.safe_load(yaml_text) or {}
                if not isinstance(meta, dict):
                    meta = {}
            except Exception:
                meta = {}
            return meta, body

    return {}, text


def obsidian_link(path: Path) -> str:
    rel = path.relative_to(VAULT).as_posix()
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    rel = rel.replace("]", r"\]")
    return f"[[{rel}]]"


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def _first_nonempty_line(body: str) -> str | None:
    for line in body.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    return None


def _cleanup_short_text(text: str, max_len: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def extract_short_description(meta: dict, body: str) -> str:
    preferred_keys = [
        "description",
        "summary",
        "short_description",
        "abstract",
        "definition",
    ]

    for key in preferred_keys:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return _cleanup_short_text(value)

    heading = _first_heading(body)
    if heading:
        return _cleanup_short_text(heading)

    first_line = _first_nonempty_line(body)
    if first_line:
        return _cleanup_short_text(first_line.lstrip("- ").strip())

    return "Без описания"


def collect_md_files(
    folder: Path,
    include: Callable[[Path, dict, str], bool] | None = None,
    exclude_name: str | None = None,
) -> list[dict]:
    if not folder.exists():
        return []

    items = []
    for path in sorted(folder.glob("*.md")):
        if exclude_name and path.name.lower() == exclude_name.lower():
            continue

        meta, body = parse_note(path)
        if include and not include(path, meta, body):
            continue

        items.append(
            {
                "path": path,
                "meta": meta,
                "body": body,
                "link": obsidian_link(path),
                "desc": extract_short_description(meta, body),
            }
        )

    return items


def load_primary_indexes(output_name: str) -> list[dict]:
    return collect_md_files(
        INDEXES_DIR,
        include=lambda _p, meta, _b: meta.get("index_mode") == "primary" or "primary" in _p.stem.lower(),
        exclude_name=output_name,
    )


def load_candidate_indexes(output_name: str) -> list[dict]:
    return collect_md_files(
        INDEXES_DIR,
        include=lambda _p, meta, _b: meta.get("index_mode") == "candidate" or "candidate" in _p.stem.lower(),
        exclude_name=output_name,
    )


def load_collections() -> list[dict]:
    primary_items = collect_md_files(
        COLLECTIONS_PRIMARY_DIR,
        include=lambda _p, meta, _b: meta.get("type") == "llm_collection",
    )
    for item in primary_items:
        item["mode"] = "primary"

    candidate_items = collect_md_files(
        COLLECTIONS_CANDIDATE_DIR,
        include=lambda _p, meta, _b: meta.get("type") == "llm_collection",
    )
    for item in candidate_items:
        item["mode"] = "candidate"

    return primary_items + candidate_items


def load_concepts() -> list[dict]:
    items = collect_md_files(
        CONCEPTS_DIR,
        include=lambda _p, meta, _b: meta.get("type") == "llm_concept",
    )
    for item in items:
        mode = item["meta"].get("concept_mode")
        item["mode"] = mode if isinstance(mode, str) else "unknown"
    return items


def section_lines(title: str, items: list[dict], with_mode: bool = False) -> list[str]:
    lines = [f"## {title}", ""]

    if not items:
        lines.append("- Нет файлов")
        lines.append("")
        return lines

    for item in items:
        mode_suffix = f" ({item.get('mode')})" if with_mode and item.get("mode") else ""
        lines.append(f"- {item['link']}{mode_suffix} — {item['desc']}")

    lines.append("")
    return lines


def build_markdown(output_name: str) -> str:
    primary_indexes = load_primary_indexes(output_name)
    candidate_indexes = load_candidate_indexes(output_name)
    collections = load_collections()
    concepts = load_concepts()

    lines = [
        "# Knowledge index",
        "",
        "Единая content-oriented точка входа в generated knowledge layer.",
        "",
    ]

    lines.extend(section_lines("Primary indexes", primary_indexes))
    lines.extend(section_lines("Candidate indexes", candidate_indexes))
    lines.extend(section_lines("Collections", collections, with_mode=True))
    lines.extend(section_lines("Concepts", concepts, with_mode=True))

    lines.extend(
        [
            "## Быстрые маршруты",
            "",
            "- [[13_llm_indexes/Knowledge index#Primary indexes]]",
            "- [[13_llm_indexes/Knowledge index#Candidate indexes]]",
            "- [[13_llm_indexes/Knowledge index#Collections]]",
            "- [[13_llm_indexes/Knowledge index#Concepts]]",
            "",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def save_markdown(content: str, output_name: str):
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INDEXES_DIR / output_name
    out_path.write_text(content, encoding="utf-8")
    safe_print("SAVED:", out_path)


def get_output_name() -> str:
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return DEFAULT_OUTPUT_NAME


def main():
    output_name = get_output_name()
    content = build_markdown(output_name)
    save_markdown(content, output_name)


if __name__ == "__main__":
    main()
