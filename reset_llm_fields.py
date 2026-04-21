from pathlib import Path
import sys
import re
import yaml

from config import VAULT_PATH

VAULT = VAULT_PATH

REMOVE_FIELDS = [
    "llm_topic",
    "llm_semantic_type",
    "llm_primary_cluster",
    "llm_candidate_clusters",
    "llm_cluster",
    "llm_processed",
    "llm_skip_reason",
]


def get_folder_arg() -> str:
    if len(sys.argv) < 2:
        raise SystemExit('Использование: python scripts\\reset_llm_fields.py "Имя каталога"')
    return sys.argv[1]


def should_skip_path(path: Path) -> bool:
    path_parts = set(path.parts)
    ignored_exact = {
        "10_llm_meta",
        "11_llm_collections",
        "11_llm_collections_primary",
        "11_llm_collections_candidate",
        "12_llm_concepts",
        "13_llm_indexes",
    }
    return any(part in ignored_exact for part in path_parts)


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


def dump_note(meta: dict, body: str) -> str:
    if meta:
        return "---\n" + yaml.safe_dump(
            meta,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ) + "---\n\n" + body.lstrip("\n")
    return body


def load_notes_from_folder(folder_arg: str) -> tuple[Path, list[Path]]:
    folder_path = VAULT / folder_arg

    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    note_paths = []
    for path in folder_path.rglob("*.md"):
        if should_skip_path(path):
            continue
        note_paths.append(path)

    return folder_path, sorted(note_paths)


def reset_file(path: Path):
    meta, body = parse_note(path)
    changed = False

    for field in REMOVE_FIELDS:
        if field in meta:
            del meta[field]
            changed = True

    if changed:
        path.write_text(dump_note(meta, body), encoding="utf-8")
        print("RESET:", path.name)
    else:
        print("NO CHANGES:", path.name)


def main():
    folder_arg = get_folder_arg()
    folder_path, note_paths = load_notes_from_folder(folder_arg)

    print("FOLDER:", folder_arg)
    print("FOLDER PATH:", folder_path)
    print("NOTES FOUND:", len(note_paths))

    for path in note_paths:
        try:
            reset_file(path)
        except Exception as e:
            print("ERROR:", path.name, e)


if __name__ == "__main__":
    main()
