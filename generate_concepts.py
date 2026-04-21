from pathlib import Path
import sys
import re
import yaml

from config import MODEL, VAULT_PATH, get_client

VAULT = VAULT_PATH
client = get_client()

COLLECTIONS_PRIMARY_DIR = VAULT / "11_llm_collections_primary"
COLLECTIONS_CANDIDATE_DIR = VAULT / "11_llm_collections_candidate"
CONCEPTS_DIR = VAULT / "12_llm_concepts"

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
            'Использование: python scripts\\generate_concepts.py [primary|candidate]'
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
                "meta": meta,
                "body": body.strip(),
                "cluster": meta.get("cluster"),
                "source_notes": meta.get("source_notes", []),
                "based_on_scope": meta.get("based_on_scope"),
            }
        )

    return items


def group_collections_by_cluster(collections: list[dict]) -> dict[str, list[dict]]:
    grouped = {}
    for item in collections:
        cluster = item.get("cluster")
        if not cluster:
            continue
        grouped.setdefault(cluster, []).append(item)
    return grouped


def build_concept_markdown(cluster_name: str, mode: str, collections: list[dict]) -> str:
    collections_block = []

    for idx, item in enumerate(collections, start=1):
        collections_block.append(
            f"""## Collection {idx}
Файл: {item['path'].name}
Кластер: {item.get('cluster')}
Исходная область: {item.get('based_on_scope')}

Текст collection:
{item.get('body', '')}
"""
        )

    prompt = f"""
You are building a concept note from one or more Obsidian collection notes.

Return markdown only.

Write the output in Russian.
Use English only for terms that do not have a good natural Russian equivalent.
All headings, explanations, and bullet points must be in Russian.

Important rule:
Under the heading "# Понятие" put only the concept title on the next non-empty line.
The title must be short, natural, and in Russian.

Your task:
- infer the core concept behind the cluster
- define the concept clearly
- explain why it matters
- describe its boundaries
- identify related ideas
- identify unresolved questions
- stay grounded in the collection notes
- do not invent unsupported claims

Mode: {mode}
Cluster: {cluster_name}

Collections:
{chr(10).join(collections_block)}

Output structure:

# Понятие
<одно короткое название понятия>

# Определение

# Почему это важно

# Основные аспекты

# Границы и различения

# Связанные идеи

# Открытые вопросы

# Основания
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You synthesize concept notes from Obsidian collections."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()

    source_collections = [f"[[{item['path'].stem}]]" for item in collections]
    source_scopes = sorted({item.get("based_on_scope") for item in collections if item.get("based_on_scope")})
    source_notes = []
    seen_notes = set()
    for item in collections:
        raw_notes = item.get("source_notes", [])
        if not isinstance(raw_notes, list):
            continue
        for note_link in raw_notes:
            if not note_link or note_link in seen_notes:
                continue
            seen_notes.add(note_link)
            source_notes.append(note_link)

    meta = {
        "type": "llm_concept",
        "concept_mode": mode,
        "cluster": cluster_name,
        "source_notes": source_notes,
        "source_collections": source_collections,
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


def extract_concept_title(content: str, fallback: str) -> str:
    lines = content.splitlines()

    for i, line in enumerate(lines):
        if line.strip() == "# Понятие":
            for j in range(i + 1, len(lines)):
                candidate = lines[j].strip()
                if not candidate:
                    continue
                if candidate.startswith("#"):
                    break
                return candidate

    return fallback


def concept_filename(concept_title: str) -> str:
    safe = re.sub(r'[<>:"/\\\\|?*]+', "-", concept_title.strip())
    return f"{safe}.md"


def save_concept(content: str, fallback_cluster_name: str):
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)

    concept_title = extract_concept_title(content, fallback_cluster_name)
    filename = concept_filename(concept_title)
    out_path = CONCEPTS_DIR / filename

    if out_path.exists() and not OVERWRITE_EXISTING:
        safe_print("SKIP existing:", out_path.name)
        return

    out_path.write_text(content, encoding="utf-8")
    safe_print("SAVED:", out_path.name)


def main():
    mode = get_mode_arg()

    safe_print("MODE:", mode)

    collections = load_collections(mode)
    safe_print("COLLECTIONS FOUND:", len(collections))

    grouped = group_collections_by_cluster(collections)
    grouped_items = list(grouped.items())

    safe_print("CLUSTERS FOUND:", len(grouped_items))

    for idx, (cluster_name, items) in enumerate(grouped_items, start=1):
        progress = f"[{idx}/{len(grouped_items)}]"
        safe_print(progress, "BUILD CONCEPT:", cluster_name, "| collections:", len(items))
        try:
            content = build_concept_markdown(cluster_name, mode, items)
            save_concept(content, cluster_name)
        except Exception as e:
            safe_print(progress, "ERROR:", cluster_name, e)


if __name__ == "__main__":
    main()
