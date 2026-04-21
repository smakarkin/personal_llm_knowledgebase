from pathlib import Path
import sys
import re
import json
import yaml

from config import MODEL, VAULT_PATH, get_client

VAULT = VAULT_PATH
client = get_client()


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


def get_folder_arg() -> str:
    if len(sys.argv) < 2:
        raise SystemExit('Использование: python scripts\\classify_notes.py "Имя каталога"')
    return sys.argv[1]


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
    return "---\n" + yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ) + "---\n\n" + body.lstrip("\n")


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


def sanitize_name_for_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120]


def get_scheme_path(folder_arg: str) -> Path:
    safe_scope = sanitize_name_for_filename(folder_arg)
    return VAULT / "10_llm_meta" / f"Cluster Scheme - folder - {safe_scope}.md"


def load_cluster_scheme(folder_arg: str) -> dict:
    scheme_path = get_scheme_path(folder_arg)
    if not scheme_path.exists():
        raise FileNotFoundError(f"Cluster scheme not found: {scheme_path}")

    text = scheme_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"No JSON block found in scheme file: {scheme_path}")

    return json.loads(m.group(1))


def truncate_body(body: str, max_chars: int = 700) -> str:
    body = body.strip().replace("\r\n", "\n")
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...[truncated]"
    return body


def is_empty_body(body: str) -> bool:
    return len(body.strip()) == 0


def mark_note_skipped(path: Path, meta: dict, body: str, reason: str):
    meta["llm_processed"] = True
    meta["llm_skip_reason"] = reason
    path.write_text(dump_note(meta, body), encoding="utf-8")
    safe_print("MARKED SKIPPED:", path.name, "|", reason)


def classify_note(title: str, body: str, folder_arg: str, scheme: dict) -> dict:
    prompt = f"""
You classify a short Obsidian note using a predefined cluster scheme.

Write all output fields in Russian.
Use English only if there is no good natural Russian equivalent.

Return strict JSON with keys:
topic, semantic_type, primary_cluster, candidate_clusters.

semantic_type must be one of:
hypothesis, question, observation, claim, example, reference.

Rules:
- primary_cluster must be one of the provided cluster ids exactly
- candidate_clusters must be a list of 3 to 5 cluster ids
- every item in candidate_clusters must be one of the provided cluster ids exactly
- do not invent new cluster ids
- candidate_clusters must be ordered from most relevant to less relevant
- primary_cluster must be the first or strongest candidate
- topic must be in Russian
- do not summarize
- do not rewrite the note
- keep topic short

Folder scope: {folder_arg}

Cluster scheme:
{json.dumps(scheme, ensure_ascii=False, indent=2)}

Note title: {title}

Note body:
{truncate_body(body)}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "You classify notes using a fixed cluster scheme and return only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def is_processed(meta: dict) -> bool:
    if meta.get("llm_processed") is True:
        return True
    if meta.get("llm_skip_reason"):
        return True
    return False


def process_file(path: Path, folder_arg: str, scheme: dict, overwrite_existing: bool = True, progress_text: str = ""):
    meta, body = parse_note(path)

    if is_processed(meta) and not overwrite_existing:
        safe_print(progress_text, "SKIP already processed:", path.name)
        return

    if is_empty_body(body):
        mark_note_skipped(path, meta, body, "empty_body")
        safe_print(progress_text, "SKIPPED EMPTY:", path.name)
        return

    body = body.strip()

    result = classify_note(path.stem, body, folder_arg, scheme)

    primary_cluster = result.get("primary_cluster")
    candidate_clusters = result.get("candidate_clusters", [])

    if not isinstance(candidate_clusters, list):
        candidate_clusters = []

    if primary_cluster and primary_cluster not in candidate_clusters:
        candidate_clusters = [primary_cluster] + candidate_clusters

    seen = set()
    deduped = []
    for item in candidate_clusters:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)

    meta["llm_topic"] = result.get("topic")
    meta["llm_semantic_type"] = result.get("semantic_type")
    meta["llm_primary_cluster"] = primary_cluster
    meta["llm_candidate_clusters"] = deduped[:5]
    meta["llm_cluster"] = primary_cluster
    meta["llm_processed"] = True

    if "llm_skip_reason" in meta:
        del meta["llm_skip_reason"]

    path.write_text(dump_note(meta, body), encoding="utf-8")
    safe_print(progress_text, "UPDATED:", path.name, "->", meta["llm_primary_cluster"], "|", meta["llm_candidate_clusters"])


def main():
    folder_arg = get_folder_arg()
    folder_path, note_paths = load_notes_from_folder(folder_arg)
    scheme = load_cluster_scheme(folder_arg)

    total_files = len(note_paths)

    safe_print("FOLDER:", folder_arg)
    safe_print("FOLDER PATH:", folder_path)
    safe_print("NOTES:", total_files)
    safe_print("SCHEME CLUSTERS:", len(scheme.get("clusters", [])))

    for idx, path in enumerate(note_paths, start=1):
        progress_text = f"[{idx}/{total_files}]"
        try:
            process_file(path, folder_arg, scheme, overwrite_existing=True, progress_text=progress_text)
        except Exception as e:
            safe_print(progress_text, "ERROR:", path.name, e)


if __name__ == "__main__":
    main()