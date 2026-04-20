from pathlib import Path
import sys
import re
import yaml

from config import client, MODEL

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")

COLLECTIONS_PRIMARY_DIR = VAULT / "11_llm_collections_primary"
COLLECTIONS_CANDIDATE_DIR = VAULT / "11_llm_collections_candidate"
CONCEPTS_DIR = VAULT / "12_llm_concepts"
INDEXES_DIR = VAULT / "13_llm_indexes"

OVERWRITE_EXISTING = True
DEFAULT_MODE = "primary"


def safe_print(*args):
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


def get_mode_arg() -> str:
    if len(sys.argv) < 2:
        raise SystemExit(
            'Использование: python scripts\\generate_index.py [primary|candidate]'
        )

    mode = sys.argv[1].strip().lower()

    if mode not in {"primary", "candidate"}:
        raise SystemExit('Режим должен быть "primary" или "candidate"')

    return mode


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


def get_collections_dir(mode: str) -> Path:
    if mode == "primary":
        return COLLECTIONS_PRIMARY_DIR
    return COLLECTIONS_CANDIDATE_DIR


def load_collections(mode: str) -> list[dict]:
    collections_dir = get_collections_dir(mode)
    if not collections_dir.exists():
        return []

    items = []
    for path in sorted(collections_dir.glob("*.md")):
        meta, body = parse_note(path)
        if meta.get("type") != "llm_collection":
            continue
        if meta.get("collection_mode") != mode:
            continue

        items.append(
            {
                "path": path,
                "link": obsidian_link(path),
                "meta": meta,
                "body": body.strip(),
                "cluster": meta.get("cluster"),
                "source_notes": meta.get("source_notes", []),
                "based_on_scope": meta.get("based_on_scope"),
            }
        )

    return items


def load_concepts(mode: str) -> list[dict]:
    if not CONCEPTS_DIR.exists():
        return []

    items = []
    for path in sorted(CONCEPTS_DIR.glob("*.md")):
        meta, body = parse_note(path)
        if meta.get("type") != "llm_concept":
            continue
        if meta.get("concept_mode") != mode:
            continue

        items.append(
            {
                "path": path,
                "link": obsidian_link(path),
                "meta": meta,
                "body": body.strip(),
                "cluster": meta.get("cluster"),
                "source_collections": meta.get("source_collections", []),
                "source_scopes": meta.get("source_scopes", []),
            }
        )

    return items


def index_filename(mode: str) -> str:
    return f"{mode.capitalize()} index.md"


def build_index_markdown(mode: str, collections: list[dict], concepts: list[dict]) -> str:
    collections_block = []
    for item in collections:
        collections_block.append(
            f"- cluster: {item.get('cluster')} | link: {item.get('link')} | scope: {item.get('based_on_scope')}"
        )

    concepts_block = []
    for item in concepts:
        concepts_block.append(
            f"- cluster: {item.get('cluster')} | link: {item.get('link')} | scopes: {', '.join(item.get('source_scopes', []))}"
        )

    prompt = f"""
You are building an overview index for an Obsidian knowledge layer.

Return markdown only.

Write the output in Russian.
Use English only for terms that do not have a good natural Russian equivalent.
All headings, explanations, and bullet points must be in Russian.

Very important link rules:
- Use only the exact wikilinks provided below.
- Do not invent new wikilinks.
- Do not shorten wikilinks.
- Do not rewrite paths inside wikilinks.
- Keep every wikilink exactly as provided.

Your task:
- summarize the topic landscape of this mode
- identify major clusters
- identify the most important concepts
- identify tensions and open areas
- identify missing areas or white spots
- stay grounded in the provided collections and concepts

Mode: {mode}

Collections:
{chr(10).join(collections_block)}

Concepts:
{chr(10).join(concepts_block)}

Output structure:

# Обзор темы

# Ключевые кластеры

# Ключевые concepts

# Основные напряжения

# Белые пятна

# Что стоит развивать дальше
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You build overview indexes for Obsidian knowledge bases. You must preserve provided wikilinks exactly."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()

    collection_links = [item["link"] for item in collections]
    concept_links = [item["link"] for item in concepts]
    source_scopes = sorted({item.get("based_on_scope") for item in collections if item.get("based_on_scope")})

    meta = {
        "type": "llm_index",
        "index_mode": mode,
        "source_collections": collection_links,
        "source_concepts": concept_links,
        "source_scopes": source_scopes,
        "status": "draft",
    }

    frontmatter_block = "---\n" + yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ) + "---\n\n"

    return frontmatter_block + text + "\n"


def save_index(mode: str, content: str):
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)

    filename = index_filename(mode)
    out_path = INDEXES_DIR / filename

    if out_path.exists() and not OVERWRITE_EXISTING:
        safe_print("SKIP existing:", out_path.name)
        return

    out_path.write_text(content, encoding="utf-8")
    safe_print("SAVED:", out_path.name)


def main():
    mode = get_mode_arg()

    safe_print("MODE:", mode)

    collections = load_collections(mode)
    concepts = load_concepts(mode)

    safe_print("COLLECTIONS FOUND:", len(collections))
    safe_print("CONCEPTS FOUND:", len(concepts))

    try:
        safe_print("[1/1]", "BUILD INDEX:", mode)
        content = build_index_markdown(mode, collections, concepts)
        save_index(mode, content)
    except Exception as e:
        safe_print("[1/1]", "ERROR:", e)


if __name__ == "__main__":
    main()