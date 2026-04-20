from pathlib import Path
import sys
import yaml

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")

GENERATED_DIRS = [
    VAULT / "11_llm_collections_primary",
    VAULT / "11_llm_collections_candidate",
    VAULT / "12_llm_concepts",
    VAULT / "13_llm_indexes",
]


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


def as_list(value) -> list:
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    if value in (None, ""):
        return []
    return [value]


def unique_keep_order(items: list) -> list:
    out = []
    seen = set()
    for item in items:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def normalize_collection(meta: dict, folder_mode: str) -> dict:
    mode = meta.get("collection_mode") or folder_mode
    scope = meta.get("based_on_scope")
    source_scopes = as_list(meta.get("source_scopes"))
    if scope and scope not in source_scopes:
        source_scopes.insert(0, scope)

    return {
        "type": "llm_collection",
        "collection_mode": mode,
        "based_on_scope": scope,
        "cluster": meta.get("cluster"),
        "source_notes": unique_keep_order(as_list(meta.get("source_notes"))),
        "source_scopes": unique_keep_order(source_scopes),
        "topics": as_list(meta.get("topics")),
        "status": meta.get("status") or "draft",
    }


def normalize_concept(meta: dict) -> dict:
    return {
        "type": "llm_concept",
        "concept_mode": meta.get("concept_mode"),
        "cluster": meta.get("cluster"),
        "source_notes": unique_keep_order(as_list(meta.get("source_notes"))),
        "source_collections": unique_keep_order(as_list(meta.get("source_collections"))),
        "source_scopes": unique_keep_order(as_list(meta.get("source_scopes"))),
        "status": meta.get("status") or "draft",
    }


def normalize_index(meta: dict) -> dict:
    return {
        "type": "llm_index",
        "index_mode": meta.get("index_mode"),
        "cluster": meta.get("cluster"),
        "source_notes": unique_keep_order(as_list(meta.get("source_notes"))),
        "source_collections": unique_keep_order(as_list(meta.get("source_collections"))),
        "source_concepts": unique_keep_order(as_list(meta.get("source_concepts"))),
        "source_scopes": unique_keep_order(as_list(meta.get("source_scopes"))),
        "status": meta.get("status") or "draft",
    }


def normalize_file(path: Path) -> bool:
    meta, body = parse_note(path)
    if not meta:
        return False

    folder_name = path.parent.name
    if folder_name == "11_llm_collections_primary":
        normalized = normalize_collection(meta, "primary")
    elif folder_name == "11_llm_collections_candidate":
        normalized = normalize_collection(meta, "candidate")
    elif folder_name == "12_llm_concepts":
        normalized = normalize_concept(meta)
    elif folder_name == "13_llm_indexes":
        normalized = normalize_index(meta)
    else:
        return False

    if normalized == meta:
        return False

    text = "---\n" + yaml.safe_dump(
        normalized,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ) + "---\n\n" + body.rstrip() + "\n"

    path.write_text(text, encoding="utf-8")
    return True


def main():
    changed = 0
    checked = 0

    for folder in GENERATED_DIRS:
        if not folder.exists():
            continue

        for path in sorted(folder.glob("*.md")):
            checked += 1
            try:
                was_changed = normalize_file(path)
                if was_changed:
                    changed += 1
                    safe_print("UPDATED:", path.name)
            except Exception as e:
                safe_print("ERROR:", path.name, e)

    safe_print("CHECKED:", checked)
    safe_print("UPDATED:", changed)


if __name__ == "__main__":
    main()
