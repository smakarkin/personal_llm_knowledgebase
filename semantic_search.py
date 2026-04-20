from pathlib import Path
import sys
import json
import re
import yaml
from typing import Any

from config import client, MODEL

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")
COLLECTIONS_DIRS = [
    VAULT / "11_llm_collections_primary",
    VAULT / "11_llm_collections_candidate",
]
CONCEPTS_DIR = VAULT / "12_llm_concepts"
OUTPUT_DIR = VAULT / "14_llm_traces"

MAX_BODY_CHARS = 2500
TOP_K_STAGE1 = 12
TOP_K_STAGE2 = 20


def safe_print(*args):
    text = " ".join(str(a) for a in args)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.flush()
    except Exception:
        print(text.encode("cp1251", errors="replace").decode("cp1251", errors="replace"))


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


def truncate(text: str, limit: int = MAX_BODY_CHARS) -> str:
    text = text.strip().replace("\r\n", "\n")
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def obsidian_link(path: Path) -> str:
    rel = path.relative_to(VAULT).as_posix()
    if rel.lower().endswith(".md"):
        rel = rel[:-3]
    return f"[[{rel}]]"


def load_knowledge_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for cdir in COLLECTIONS_DIRS:
        if not cdir.exists():
            continue
        for path in sorted(cdir.glob("*.md")):
            meta, body = parse_note(path)
            if meta.get("type") != "llm_collection":
                continue
            items.append({
                "kind": "collection",
                "path": path,
                "link": obsidian_link(path),
                "title": path.stem,
                "cluster": meta.get("cluster"),
                "mode": meta.get("collection_mode"),
                "scope": meta.get("based_on_scope"),
                "source_notes": meta.get("source_notes", []),
                "body": truncate(body),
            })

    if CONCEPTS_DIR.exists():
        for path in sorted(CONCEPTS_DIR.glob("*.md")):
            meta, body = parse_note(path)
            if meta.get("type") != "llm_concept":
                continue
            items.append({
                "kind": "concept",
                "path": path,
                "link": obsidian_link(path),
                "title": path.stem,
                "cluster": meta.get("cluster"),
                "mode": meta.get("concept_mode"),
                "source_collections": meta.get("source_collections", []),
                "source_scopes": meta.get("source_scopes", []),
                "body": truncate(body),
            })

    return items


def resolve_wikilink_to_path(link: str) -> Path | None:
    m = re.match(r"\[\[(.+?)\]\]", link.strip())
    if not m:
        return None
    rel = m.group(1)
    rel_path = VAULT / (rel + ".md")
    if rel_path.exists():
        return rel_path
    return None


def stage1_rank(query: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for idx, item in enumerate(items, start=1):
        payload.append({
            "id": idx,
            "kind": item["kind"],
            "title": item["title"],
            "link": item["link"],
            "cluster": item.get("cluster"),
            "mode": item.get("mode"),
            "scope": item.get("scope"),
            "text": item["body"],
        })

    prompt = f"""
Ты делаешь семантический отбор материалов по смысловому запросу.

Запрос:
{query}

Нужно:
- найти наиболее релевантные файлы
- учитывать смысл, а не совпадение слов
- вернуть только JSON

Формат ответа:
{{
  "matches": [
    {{
      "id": 1,
      "relevance": "high|medium|low",
      "why": "кратко, почему это связано",
      "extracted_idea": "какая именно связанная идея здесь найдена"
    }}
  ]
}}

Выбирай только действительно релевантные материалы.
Старайся отдать не больше {TOP_K_STAGE1}.
Материалы:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "Ты делаешь точный семантический отбор и возвращаешь только валидный JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)

    by_id = {i + 1: item for i, item in enumerate(items)}
    ranked: list[dict[str, Any]] = []

    for m in data.get("matches", []):
        src = by_id.get(m.get("id"))
        if not src:
            continue
        enriched = dict(src)
        enriched["relevance"] = m.get("relevance")
        enriched["why"] = m.get("why")
        enriched["extracted_idea"] = m.get("extracted_idea")
        ranked.append(enriched)

    return ranked[:TOP_K_STAGE1]


def collect_source_notes(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    note_items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in matches:
        if item["kind"] == "collection":
            for link in item.get("source_notes", []):
                path = resolve_wikilink_to_path(link)
                if not path:
                    continue
                if str(path) in seen:
                    continue
                seen.add(str(path))
                meta, body = parse_note(path)
                note_items.append({
                    "kind": "note",
                    "path": path,
                    "link": obsidian_link(path),
                    "title": path.stem,
                    "body": truncate(body),
                    "meta": meta,
                    "via": item["link"],
                })

        elif item["kind"] == "concept":
            for clink in item.get("source_collections", []):
                cpath = resolve_wikilink_to_path(clink)
                if not cpath:
                    continue
                cmeta, _ = parse_note(cpath)
                for nlink in cmeta.get("source_notes", []):
                    npath = resolve_wikilink_to_path(nlink)
                    if not npath:
                        continue
                    if str(npath) in seen:
                        continue
                    seen.add(str(npath))
                    nmeta, nbody = parse_note(npath)
                    note_items.append({
                        "kind": "note",
                        "path": npath,
                        "link": obsidian_link(npath),
                        "title": npath.stem,
                        "body": truncate(nbody),
                        "meta": nmeta,
                        "via": item["link"],
                    })

    return note_items


def stage2_trace_notes(query: str, note_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for idx, item in enumerate(note_items, start=1):
        payload.append({
            "id": idx,
            "title": item["title"],
            "link": item["link"],
            "via": item["via"],
            "text": item["body"],
        })

    prompt = f"""
Ты восстанавливаешь основания понятия или идеи по исходным заметкам.

Запрос:
{query}

Нужно:
- выбрать заметки, реально поддерживающие эту идею
- для каждой заметки объяснить, что именно из неё извлекается
- объяснить, почему это связано с запросом
- вернуть только JSON

Формат ответа:
{{
  "notes": [
    {{
      "id": 1,
      "relevance": "high|medium|low",
      "extracted_idea": "какая именно идея извлекается",
      "why_related": "почему это связано с запросом"
    }}
  ],
  "synthesis": "краткая гипотеза, какое общее понятие здесь складывается"
}}

Выбирай не больше {TOP_K_STAGE2} заметок.
Материалы:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "Ты восстанавливаешь смысловые основания понятия и возвращаешь только валидный JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    text = resp.choices[0].message.content.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)

    by_id = {i + 1: item for i, item in enumerate(note_items)}
    traced: list[dict[str, Any]] = []

    for n in data.get("notes", []):
        src = by_id.get(n.get("id"))
        if not src:
            continue
        enriched = dict(src)
        enriched["relevance"] = n.get("relevance")
        enriched["extracted_idea"] = n.get("extracted_idea")
        enriched["why_related"] = n.get("why_related")
        traced.append(enriched)

    return traced, data.get("synthesis", "")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\wа-яА-ЯёЁ\- ]+", "", text)
    text = re.sub(r"\s+", "-", text)
    return text[:80]


def save_report(query: str, stage1_matches: list[dict[str, Any]], stage2_notes: list[dict[str, Any]], synthesis: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"Trace - {slugify(query)}.md"

    lines = []
    lines.append(f"# Trace: {query}\n")
    lines.append("## Верхний слой: concepts и collections\n")
    for item in stage1_matches:
        lines.append(f"- **{item['kind']}** {item['link']}")
        lines.append(f"  - relevance: {item.get('relevance')}")
        lines.append(f"  - extracted idea: {item.get('extracted_idea')}")
        lines.append(f"  - why: {item.get('why')}")
        lines.append("")

    lines.append("## Основания: исходные заметки\n")
    for note in stage2_notes:
        lines.append(f"- {note['link']}")
        lines.append(f"  - via: {note.get('via')}")
        lines.append(f"  - relevance: {note.get('relevance')}")
        lines.append(f"  - extracted idea: {note.get('extracted_idea')}")
        lines.append(f"  - why related: {note.get('why_related')}")
        lines.append("")

    lines.append("## Сводная гипотеза\n")
    lines.append(synthesis or "_Нет сводной гипотезы_")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Использование: python scripts\\semantic_trace.py "Описание идеи или понятия"')

    query = sys.argv[1].strip()
    safe_print("QUERY:", query)

    items = load_knowledge_items()
    safe_print("LOADED TOP-LAYER ITEMS:", len(items))

    stage1_matches = stage1_rank(query, items)
    safe_print("STAGE 1 MATCHES:", len(stage1_matches))

    note_items = collect_source_notes(stage1_matches)
    safe_print("COLLECTED SOURCE NOTES:", len(note_items))

    stage2_notes, synthesis = stage2_trace_notes(query, note_items)
    safe_print("STAGE 2 NOTES:", len(stage2_notes))

    report_path = save_report(query, stage1_matches, stage2_notes, synthesis)
    safe_print("SAVED REPORT:", report_path)


if __name__ == "__main__":
    main()