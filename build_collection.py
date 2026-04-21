from pathlib import Path
import sys
import re
import yaml
from collections import defaultdict

from config import MODEL, VAULT_PATH, get_client

VAULT = VAULT_PATH
client = get_client()

OUTPUT_DIR_PRIMARY = VAULT / "11_llm_collections_primary"
OUTPUT_DIR_CANDIDATE = VAULT / "11_llm_collections_candidate"

OVERWRITE_EXISTING = True
MIN_NOTES_IN_CLUSTER = 2


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


def get_args() -> tuple[str, str]:
    if len(sys.argv) < 2:
        raise SystemExit(
            'Использование: python scripts\\build_collection.py "Имя каталога" [primary|candidate]'
        )

    folder_arg = sys.argv[1]

    if len(sys.argv) >= 3:
        mode = sys.argv[2].strip().lower()
    else:
        mode = "primary"

    if mode not in {"primary", "candidate"}:
        raise SystemExit('Режим должен быть "primary" или "candidate"')

    return folder_arg, mode


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


def load_clustered_notes(note_paths: list[Path], mode: str) -> dict[str, list[dict]]:
    clusters = defaultdict(list)

    for path in note_paths:
        try:
            meta, body = parse_note(path)
        except Exception as e:
            safe_print("ERROR loading:", path.name, e)
            continue

        body = body.strip()
        if not body:
            safe_print("SKIP empty body:", path.name)
            continue

        title = path.stem
        topic = meta.get("llm_topic")
        semantic_type = meta.get("llm_semantic_type")

        if mode == "primary":
            cluster = meta.get("llm_primary_cluster") or meta.get("llm_cluster")
            if not cluster:
                continue

            clusters[cluster].append(
                {
                    "title": title,
                    "path": path,
                    "topic": topic,
                    "semantic_type": semantic_type,
                    "body": body,
                }
            )

        else:
            candidate_clusters = meta.get("llm_candidate_clusters", [])
            if not isinstance(candidate_clusters, list) or not candidate_clusters:
                continue

            seen = set()
            for cluster in candidate_clusters:
                if not cluster or cluster in seen:
                    continue
                seen.add(cluster)

                clusters[cluster].append(
                    {
                        "title": title,
                        "path": path,
                        "topic": topic,
                        "semantic_type": semantic_type,
                        "body": body,
                    }
                )

    return clusters


def build_collection_markdown(cluster_name: str, notes: list[dict], scope_name: str, mode: str) -> str:
    notes_block = []

    for idx, note in enumerate(notes, start=1):
        notes_block.append(
            f"""## Заметка {idx}
Название: {note["title"]}
Тема: {note.get("topic")}
Семантический тип: {note.get("semantic_type")}

Текст:
{note["body"]}
"""
        )

    prompt = f"""
You are building a synthesis collection from many short Obsidian notes.

Return markdown only.

Write the output in Russian.
Use English only for terms that do not have a good natural Russian equivalent.
All headings, explanations, bullet points, and synthesis must be in Russian.
Do not switch to English for style.
Keep original note titles unchanged when listing source notes.

Your task:
- infer the shared theme of this cluster
- identify subthemes
- identify recurring patterns
- identify tensions or contradictions
- identify open questions
- keep the output concise but useful
- do not invent facts that are not grounded in the notes

Scope: {scope_name}
Collection mode: {mode}
Cluster: {cluster_name}

Notes:
{chr(10).join(notes_block)}

Output structure:

# Тема

# Подтемы

# Повторяющиеся паттерны

# Напряжения и противоречия

# Открытые вопросы

# Заметки в кластере
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You synthesize Obsidian note clusters into markdown collections."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()

    source_notes = [f"[[{n['title']}]]" for n in notes]

    source_scopes = [scope_name] if scope_name else []

    meta = {
        "type": "llm_collection",
        "collection_mode": mode,
        "based_on_scope": scope_name,
        "cluster": cluster_name,
        "source_notes": source_notes,
        "source_scopes": source_scopes,
        "topics": [],
        "status": "draft",
    }

    frontmatter_block = "---\n" + yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ) + "---\n\n"

    return frontmatter_block + text + "\n"


def get_output_dir(mode: str) -> Path:
    if mode == "primary":
        return OUTPUT_DIR_PRIMARY
    return OUTPUT_DIR_CANDIDATE


def collection_filename(cluster_name: str, mode: str) -> str:
    return f"{cluster_name.strip()} - {mode}.md"


def save_collection(cluster_name: str, content: str, mode: str):
    output_dir = get_output_dir(mode)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = collection_filename(cluster_name, mode)
    safe_filename = re.sub(r'[<>:"/\\\\|?*]+', "-", filename)
    out_path = output_dir / safe_filename

    if out_path.exists() and not OVERWRITE_EXISTING:
        safe_print("SKIP existing:", out_path.name)
        return

    out_path.write_text(content, encoding="utf-8")
    safe_print("SAVED:", out_path.name)


def main():
    folder_arg, mode = get_args()
    folder_path, note_paths = load_notes_from_folder(folder_arg)

    safe_print("FOLDER:", folder_arg)
    safe_print("FOLDER PATH:", folder_path)
    safe_print("MODE:", mode)
    safe_print("NOTES FOUND:", len(note_paths))

    clusters = load_clustered_notes(note_paths, mode)
    cluster_items = list(clusters.items())

    safe_print("CLUSTERS FOUND:", len(cluster_items))

    for idx, (cluster_name, notes) in enumerate(cluster_items, start=1):
        progress = f"[{idx}/{len(cluster_items)}]"
        safe_print(progress, "CLUSTER:", cluster_name, "| NOTES:", len(notes))

        if len(notes) < MIN_NOTES_IN_CLUSTER:
            safe_print(progress, "SKIP too small:", cluster_name)
            continue

        try:
            content = build_collection_markdown(cluster_name, notes, folder_arg, mode)
            save_collection(cluster_name, content, mode)
        except Exception as e:
            safe_print(progress, "ERROR cluster:", cluster_name, e)


if __name__ == "__main__":
    main()
