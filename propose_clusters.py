from pathlib import Path
import sys
import re
import json
import yaml

from config import client, MODEL

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")
OUTPUT_DIR = VAULT / "10_llm_meta"

MAX_NOTES_FOR_SCHEME = 40
BATCH_SIZE = 20
MAX_BODY_CHARS = 700


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
        raise SystemExit('Использование: python scripts\\propose_clusters.py "Имя каталога"')
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


def sanitize_name_for_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text)
    text = re.sub(r"\s+", " ", text)
    return text[:120]


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


def get_scheme_path(folder_arg: str) -> Path:
    safe_scope = sanitize_name_for_filename(folder_arg)
    return OUTPUT_DIR / f"Cluster Scheme - folder - {safe_scope}.md"


def load_existing_scheme(folder_arg: str) -> dict | None:
    scheme_path = get_scheme_path(folder_arg)
    if not scheme_path.exists():
        return None

    text = scheme_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"No JSON block found in scheme file: {scheme_path}")

    return json.loads(m.group(1))


def save_scheme(folder_arg: str, scheme: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = get_scheme_path(folder_arg)

    meta = {
        "type": "llm_cluster_scheme",
        "scope_type": "folder",
        "scope_folder": folder_arg,
    }

    body = "# Схема кластеров\n\n```json\n" + json.dumps(scheme, ensure_ascii=False, indent=2) + "\n```\n"
    text = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n" + body
    out_path.write_text(text, encoding="utf-8")
    safe_print("SAVED SCHEME:", out_path.name)


def truncate_body(body: str) -> str:
    body = body.strip().replace("\r\n", "\n")
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n...[truncated]"
    return body


def is_empty_body(body: str) -> bool:
    return len(body.strip()) == 0


def mark_note_skipped(path: Path, meta: dict, body: str, reason: str):
    meta["llm_processed"] = True
    meta["llm_skip_reason"] = reason
    path.write_text(dump_note(meta, body), encoding="utf-8")
    safe_print("MARKED SKIPPED:", path.name, "|", reason)


def propose_cluster_scheme(scope_name: str, note_paths: list[Path]) -> dict:
    notes_payload = []

    for path in note_paths:
        _, body = parse_note(path)
        body = truncate_body(body)
        if not body:
            continue

        notes_payload.append({
            "title": path.stem,
            "relative_path": str(path.relative_to(VAULT)),
            "text": body,
        })

    prompt = f"""
You are designing a reusable cluster scheme for Obsidian notes inside one selected folder.

Write all output in Russian.
Cluster ids must also be in Russian.
Do not use English unless there is no good Russian equivalent.

Task:
1. Read the notes.
2. Propose 8 to 12 broad, reusable clusters for this set of notes.
3. Clusters must be high-level enough that multiple notes can fit into each.
4. Avoid note-specific labels.
5. Return strict JSON.

Important rules for cluster ids:
- use short Russian labels
- 1 to 4 words
- lowercase
- no transliteration
- no English
- no note-specific wording
- clusters must be reusable across many notes

Required JSON format:
{{
  "scope_topic": "...",
  "clusters": [
    {{
      "id": "русское название кластера",
      "name": "человеко-читаемое русское название",
      "description": "какие заметки сюда относятся",
      "inclusion_rules": ["...", "..."],
      "exclusion_rules": ["...", "..."]
    }}
  ]
}}

Scope: {scope_name}

Notes:
{json.dumps(notes_payload, ensure_ascii=False, indent=2)}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You design note clustering schemes and return only valid JSON in Russian."
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


def count_processed(note_paths: list[Path]) -> int:
    processed = 0
    for path in note_paths:
        meta, _ = parse_note(path)
        if is_processed(meta):
            processed += 1
    return processed


def get_unprocessed_notes(note_paths: list[Path]) -> list[Path]:
    result = []
    for path in note_paths:
        meta, body = parse_note(path)

        if is_processed(meta):
            continue

        if is_empty_body(body):
            mark_note_skipped(path, meta, body, "empty_body")
            continue

        result.append(path)

    return result


def classify_batch(folder_arg: str, scheme: dict, note_paths: list[Path], total_files: int, already_processed_before_batch: int):
    for idx, path in enumerate(note_paths, start=1):
        meta, body = parse_note(path)
        absolute_progress = already_processed_before_batch + idx

        if is_processed(meta):
            safe_print(f"[{absolute_progress}/{total_files}]", "SKIP processed:", path.name)
            continue

        if is_empty_body(body):
            mark_note_skipped(path, meta, body, "empty_body")
            safe_print(f"[{absolute_progress}/{total_files}]", "SKIPPED EMPTY:", path.name)
            continue

        body = body.strip()

        try:
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
            safe_print(f"[{absolute_progress}/{total_files}]", "UPDATED:", path.name, "->", meta["llm_primary_cluster"], "|", meta["llm_candidate_clusters"])
        except Exception as e:
            safe_print(f"[{absolute_progress}/{total_files}]", "ERROR:", path.name, e)


def main():
    folder_arg = get_folder_arg()
    folder_path, all_note_paths = load_notes_from_folder(folder_arg)

    safe_print("FOLDER:", folder_arg)
    safe_print("FOLDER PATH:", folder_path)
    safe_print("ALL NOTES:", len(all_note_paths))

    scheme = load_existing_scheme(folder_arg)

    if scheme is None:
        seed_notes = get_unprocessed_notes(all_note_paths)[:MAX_NOTES_FOR_SCHEME]
        if not seed_notes:
            safe_print("Нет необработанных непустых заметок. Схема не нужна.")
            return

        safe_print("SCHEME NOT FOUND -> BUILDING NEW SCHEME")
        safe_print("NOTES FOR SCHEME:", len(seed_notes))
        scheme = propose_cluster_scheme(folder_arg, seed_notes)
        save_scheme(folder_arg, scheme)
    else:
        safe_print("EXISTING SCHEME FOUND")
        safe_print("SCHEME CLUSTERS:", len(scheme.get("clusters", [])))

    total_files = len(all_note_paths)

    while True:
        processed_now = count_processed(all_note_paths)
        unprocessed = get_unprocessed_notes(all_note_paths)
        remaining = len(unprocessed)

        safe_print("PROGRESS:", f"{processed_now}/{total_files}", "| REMAINING:", remaining)

        if not unprocessed:
            safe_print("Готово: в каталоге не осталось необработанных заметок.")
            break

        batch = unprocessed[:BATCH_SIZE]
        safe_print("PROCESSING BATCH:", len(batch), "| STARTING FROM:", processed_now + 1, "| TO:", processed_now + len(batch))
        classify_batch(folder_arg, scheme, batch, total_files, processed_now)


if __name__ == "__main__":
    main()