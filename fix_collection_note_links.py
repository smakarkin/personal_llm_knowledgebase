from pathlib import Path
import re
import sys
from collections import defaultdict

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")

TARGET_DIRS = [
    VAULT / "11_llm_collections_primary",
    VAULT / "11_llm_collections_candidate",
]

SKIP_DIR_NAMES = {
    "10_llm_meta",
    "11_llm_collections",
    "11_llm_collections_primary",
    "11_llm_collections_candidate",
    "12_llm_concepts",
    "13_llm_indexes",
    "14_llm_traces",
}

DRY_RUN = False


def safe_print(*args):
    text = " ".join(str(a) for a in args)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        try:
            print(text.encode("cp1251", errors="replace").decode("cp1251", errors="replace"))
        except Exception:
            print("[UNPRINTABLE OUTPUT]")


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def build_note_index(vault: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)

    for path in vault.rglob("*.md"):
        if should_skip_path(path):
            continue
        index[path.stem].append(path)

    return index


def to_wikilink(path: Path, display_text: str) -> str:
    rel = path.relative_to(VAULT).as_posix()
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    rel = rel.replace("]", r"\]")
    display_text = display_text.replace("]", r"\]")
    return f"[[{rel}|{display_text}]]"


def fix_collection_text(text: str, note_index: dict[str, list[Path]], file_path: Path):
    lines = text.splitlines()
    in_target_section = False
    changed = False

    found_count = 0
    replaced_count = 0
    ambiguous = []
    missing = []

    bullet_pattern = re.compile(r"^(\s*[*-]\s+)\*\*(.+?)\*\*(.*)$")

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("# "):
            in_target_section = stripped == "# Заметки в кластере"
            continue

        if not in_target_section:
            continue

        m = bullet_pattern.match(line)
        if not m:
            continue

        prefix, note_title, suffix = m.groups()
        found_count += 1

        candidates = note_index.get(note_title, [])

        if len(candidates) == 1:
            wikilink = to_wikilink(candidates[0], note_title)
            new_line = f"{prefix}{wikilink}{suffix}"
            if new_line != line:
                lines[i] = new_line
                changed = True
                replaced_count += 1
        elif len(candidates) == 0:
            missing.append(note_title)
        else:
            ambiguous.append((note_title, candidates))

    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"

    return {
        "changed": changed,
        "text": new_text,
        "found_count": found_count,
        "replaced_count": replaced_count,
        "ambiguous": ambiguous,
        "missing": missing,
        "file_path": file_path,
    }


def process_target_file(path: Path, note_index: dict[str, list[Path]]):
    text = path.read_text(encoding="utf-8", errors="ignore")
    result = fix_collection_text(text, note_index, path)

    if result["changed"] and not DRY_RUN:
        path.write_text(result["text"], encoding="utf-8")

    return result


def main():
    safe_print("BUILDING NOTE INDEX...")
    note_index = build_note_index(VAULT)
    safe_print("INDEXED NOTE TITLES:", len(note_index))

    target_files = []
    for target_dir in TARGET_DIRS:
        if target_dir.exists():
            target_files.extend(sorted(target_dir.glob("*.md")))

    safe_print("TARGET FILES:", len(target_files))

    total_changed_files = 0
    total_replaced_links = 0

    all_missing = []
    all_ambiguous = []

    for idx, path in enumerate(target_files, start=1):
        safe_print(f"[{idx}/{len(target_files)}]", "PROCESSING:", path.name)
        result = process_target_file(path, note_index)

        if result["changed"]:
            total_changed_files += 1
            total_replaced_links += result["replaced_count"]
            safe_print(
                f"[{idx}/{len(target_files)}]",
                "UPDATED:",
                path.name,
                "| replaced:",
                result["replaced_count"],
                "/",
                result["found_count"],
            )
        else:
            safe_print(
                f"[{idx}/{len(target_files)}]",
                "NO CHANGES:",
                path.name,
                "| found:",
                result["found_count"],
            )

        for title in result["missing"]:
            all_missing.append((path.name, title))

        for title, candidates in result["ambiguous"]:
            all_ambiguous.append((path.name, title, candidates))

    safe_print("")
    safe_print("DONE")
    safe_print("FILES CHANGED:", total_changed_files)
    safe_print("LINKS REPLACED:", total_replaced_links)

    if all_missing:
        safe_print("")
        safe_print("MISSING TITLES:")
        for file_name, title in all_missing:
            safe_print("-", file_name, "->", title)

    if all_ambiguous:
        safe_print("")
        safe_print("AMBIGUOUS TITLES:")
        for file_name, title, candidates in all_ambiguous:
            safe_print("-", file_name, "->", title)
            for c in candidates:
                safe_print("   ", c.relative_to(VAULT).as_posix())


if __name__ == "__main__":
    main()