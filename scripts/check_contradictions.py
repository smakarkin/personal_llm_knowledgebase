from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import datetime as dt
import json
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import MODEL, VAULT_PATH, get_client

try:
    import yaml
except Exception:
    yaml = None

client = None

CONCEPTS_DIR = "12_llm_concepts"
COLLECTIONS_DIRS = ["11_llm_collections_primary", "11_llm_collections_candidate"]
DEFAULT_OUTPUT = "13_llm_indexes/Contradiction check report.md"


@dataclass
class NoteDoc:
    path: Path
    note_type: str
    mode: str
    cluster: str
    title: str
    body: str
    definition: str
    sources: list[str]


def safe_print(*args: Any) -> None:
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
            meta = parse_frontmatter(parts[1])
            return meta, parts[2].lstrip("\n")
    return {}, text


def parse_frontmatter(yaml_text: str) -> dict:
    if yaml is not None:
        try:
            data = yaml.safe_load(yaml_text) or {}
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    result: dict[str, Any] = {}
    for raw_line in yaml_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            result[key] = value.lower() == "true"
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                items = [i.strip().strip("\"'") for i in inner.split(",")]
                result[key] = [i for i in items if i]
        else:
            result[key] = value.strip("\"'")
    return result


def extract_heading_block(markdown_text: str, heading: str) -> str:
    pattern = rf"(?ms)^#{{1,3}}\s+{re.escape(heading)}\s*$\n(.*?)(?=^#{{1,3}}\s+|\Z)"
    m = re.search(pattern, markdown_text)
    return m.group(1).strip() if m else ""


def extract_title(markdown_text: str, fallback: str) -> str:
    title_block = extract_heading_block(markdown_text, "Понятие")
    if title_block:
        first = next((line.strip() for line in title_block.splitlines() if line.strip()), "")
        if first:
            return re.sub(r"^[-*#\s]+", "", first).strip()
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def parse_wikilink(link: str) -> str:
    link = link.strip()
    if link.startswith("[[") and link.endswith("]]"):
        raw = link[2:-2]
        if "|" in raw:
            raw = raw.split("|", 1)[0]
        return raw.strip()
    return link


def normalize_tokens(text: str) -> set[str]:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9_\-]{3,}", text.lower())
    stop = {
        "это", "когда", "который", "которая", "которые", "также", "очень", "между", "через",
        "чтобы", "или", "при", "как", "для", "его", "её", "под", "над", "без", "есть", "быть",
        "что", "где", "они", "она", "оно", "the", "and", "for", "with", "from", "into",
    }
    return {w for w in words if w not in stop}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def load_docs(vault: Path) -> list[NoteDoc]:
    docs: list[NoteDoc] = []

    concepts_path = vault / CONCEPTS_DIR
    if concepts_path.exists():
        for path in sorted(concepts_path.glob("*.md")):
            meta, body = parse_note(path)
            if meta.get("type") != "llm_concept":
                continue
            title = extract_title(body, path.stem)
            definition = extract_heading_block(body, "Определение") or body[:600]
            docs.append(
                NoteDoc(
                    path=path,
                    note_type="concept",
                    mode=str(meta.get("concept_mode") or "unknown"),
                    cluster=str(meta.get("cluster") or ""),
                    title=title,
                    body=body,
                    definition=definition,
                    sources=[parse_wikilink(s) for s in meta.get("source_collections", []) if isinstance(s, str)],
                )
            )

    for folder in COLLECTIONS_DIRS:
        col_path = vault / folder
        if not col_path.exists():
            continue
        for path in sorted(col_path.glob("*.md")):
            meta, body = parse_note(path)
            if meta.get("type") != "llm_collection":
                continue
            title = path.stem.rsplit(" - ", 1)[0].strip()
            definition = extract_heading_block(body, "Определение") or body[:600]
            docs.append(
                NoteDoc(
                    path=path,
                    note_type="collection",
                    mode=str(meta.get("collection_mode") or "unknown"),
                    cluster=str(meta.get("cluster") or ""),
                    title=title,
                    body=body,
                    definition=definition,
                    sources=[parse_wikilink(s) for s in meta.get("source_notes", []) if isinstance(s, str)],
                )
            )

    return docs


def resolve_vault_path(raw_vault: str) -> tuple[Path, list[Path]]:
    raw = raw_vault.strip()
    if raw in {"", ".", "./"}:
        vault = VAULT_PATH.resolve()
        return vault, [vault]

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate, [candidate]


def build_candidates(docs: list[NoteDoc], limit: int) -> list[tuple[NoteDoc, NoteDoc, float, str]]:
    scored: list[tuple[NoteDoc, NoteDoc, float, str]] = []

    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a = docs[i]
            b = docs[j]
            ta = normalize_tokens(f"{a.title} {a.definition}")
            tb = normalize_tokens(f"{b.title} {b.definition}")
            sim = jaccard(ta, tb)

            reasons = []
            score = 0.0

            if a.cluster and b.cluster and a.cluster == b.cluster:
                score += 0.7
                reasons.append("один cluster")

            if sim >= 0.2:
                score += sim
                reasons.append(f"лексическая близость {sim:.2f}")

            if a.note_type != b.note_type:
                score += 0.1

            if score >= 0.65:
                scored.append((a, b, score, ", ".join(reasons)))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:limit]


def heuristic_assessment(a: NoteDoc, b: NoteDoc) -> dict[str, Any]:
    neg_markers = [" не ", " нельзя", "невозможно", "ошибка", "ложн", "противореч"]

    da = f" {a.definition.lower()} "
    db = f" {b.definition.lower()} "

    neg_a = any(m in da for m in neg_markers)
    neg_b = any(m in db for m in neg_markers)

    token_sim = jaccard(normalize_tokens(a.definition), normalize_tokens(b.definition))

    if neg_a != neg_b and token_sim >= 0.15:
        kind = "вероятный конфликт"
        verdict = "похоже на реальное противоречие"
        confidence = 0.62
    elif token_sim >= 0.35:
        kind = "конкурирующие интерпретации"
        verdict = "скорее разные framing / уровни абстракции"
        confidence = 0.48
    else:
        kind = "слабый сигнал"
        verdict = "маловероятный конфликт"
        confidence = 0.31

    explanation = (
        f"Сходство определений: {token_sim:.2f}. "
        f"Маркер отрицания: A={neg_a}, B={neg_b}."
    )

    return {
        "is_conflict": kind != "слабый сигнал",
        "conflict_type": kind,
        "explanation": explanation,
        "verdict": verdict,
        "confidence": confidence,
    }


def llm_assessment(a: NoteDoc, b: NoteDoc) -> dict[str, Any]:
    if client is None or MODEL is None:
        return heuristic_assessment(a, b)

    prompt = f"""
Ты анализируешь пару заметок knowledge base и оцениваешь, есть ли между ними противоречие.

Верни ТОЛЬКО JSON-объект со схемой:
{{
  "is_conflict": true/false,
  "conflict_type": "вероятный конфликт|конкурирующие интерпретации|разные уровни абстракции|нет конфликта",
  "explanation": "кратко, по-русски",
  "verdict": "реальный конфликт|скорее разный framing|нужно ручное чтение",
  "confidence": 0.0-1.0
}}

Важно:
- Не придумывай факты вне текста.
- Если различие связано с уровнем детализации, не называй это жёстким конфликтом.
- Пиши кратко.

=== Документ A ===
Тип: {a.note_type}
Режим: {a.mode}
Cluster: {a.cluster}
Заголовок: {a.title}
Определение/фрагмент:
{a.definition[:1300]}

=== Документ B ===
Тип: {b.note_type}
Режим: {b.mode}
Cluster: {b.cluster}
Заголовок: {b.title}
Определение/фрагмент:
{b.definition[:1300]}
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": "Ты аккуратный аналитик противоречий в knowledge base."},
                {"role": "user", "content": prompt},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("LLM вернул не JSON-объект")
        return {
            "is_conflict": bool(data.get("is_conflict", False)),
            "conflict_type": str(data.get("conflict_type", "нет конфликта")),
            "explanation": str(data.get("explanation", "")),
            "verdict": str(data.get("verdict", "нужно ручное чтение")),
            "confidence": float(data.get("confidence", 0.0)),
        }
    except Exception as e:
        fallback = heuristic_assessment(a, b)
        fallback["explanation"] = f"{fallback['explanation']} (LLM fallback: {e})"
        return fallback


def format_doc_link(vault: Path, doc: NoteDoc) -> str:
    rel = doc.path.relative_to(vault).as_posix()
    return f"`{rel}`"


def build_report(
    vault: Path,
    candidates: list[tuple[NoteDoc, NoteDoc, float, str]],
    use_llm: bool,
    top_n: int,
    docs_count: int,
    checked_paths: list[Path] | None = None,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Contradiction check (MVP)",
        "",
        f"- Дата: {now}",
        "- Слой: concepts + collections",
        f"- Кандидатов после преселекции: {len(candidates)}",
        f"- Загружено документов: {docs_count}",
        f"- LLM-анализ: {'включён' if use_llm else 'выключен (только эвристики)'}",
        "",
        "## Метод",
        "1. Предварительный отбор пар по общему cluster и/или лексической близости.",
        "2. Анализ каждой пары на предмет противоречия, competing interpretations или разницы абстракций.",
        "",
        "## Подозреваемые конфликты",
        "",
    ]

    if docs_count == 0:
        lines.extend([
            "Документы для анализа не найдены.",
            "",
            "Проверьте путь `--vault` и наличие папок:",
            f"- `{CONCEPTS_DIR}`",
            f"- `{COLLECTIONS_DIRS[0]}`",
            f"- `{COLLECTIONS_DIRS[1]}`",
        ])
        if checked_paths:
            lines.append("")
            lines.append("Проверенные пути:")
            for p in checked_paths:
                lines.append(f"- `{p.as_posix()}`")
        return "\n".join(lines) + "\n"

    if not candidates:
        lines.extend([
            "Ничего подозрительного не найдено по текущим порогам.",
            "",
            "Рекомендация: уменьшить порог отбора (`--candidate-limit` увеличить, добавить `--use-llm`).",
        ])
        return "\n".join(lines) + "\n"

    shown = 0
    for idx, (a, b, score, reason) in enumerate(candidates, start=1):
        if shown >= top_n:
            break
        assessment = llm_assessment(a, b) if use_llm else heuristic_assessment(a, b)
        if not assessment.get("is_conflict"):
            continue

        shown += 1
        lines.extend([
            f"### {shown}. {assessment.get('conflict_type', 'сигнал')}",
            f"- Преселекция: {reason}; score={score:.2f}",
            f"- Оценка: {assessment.get('verdict', '')} (confidence={assessment.get('confidence', 0.0):.2f})",
            f"- Объяснение: {assessment.get('explanation', '').strip()}",
            "- Источники:",
            f"  - A: {a.note_type}/{a.mode} — **{a.title}** ({format_doc_link(vault, a)})",
            f"  - B: {b.note_type}/{b.mode} — **{b.title}** ({format_doc_link(vault, b)})",
            "",
        ])

    if shown == 0:
        lines.extend([
            "Подозрительных **конфликтов** не найдено, но были пары с похожей тематикой.",
            "Рекомендация: запуск с `--use-llm` и более высоким `--candidate-limit`.",
            "",
        ])

    lines.extend([
        "## Дальше (ручная проверка)",
        "- Прочитать пары с confidence >= 0.55.",
        "- Проверить, это реальное противоречие или просто разный уровень абстракции.",
        "- При необходимости завести отдельную concept-note с явным reconciliation.",
    ])

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MVP-проверка противоречий в concepts/collections с Markdown-отчётом."
    )
    parser.add_argument(
        "--vault",
        default=str(VAULT_PATH),
        help="Путь к корню vault (по умолчанию: VAULT_PATH из config.py).",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Путь выходного Markdown-отчёта.")
    parser.add_argument("--candidate-limit", type=int, default=60, help="Сколько пар анализировать после преселекции.")
    parser.add_argument("--top", type=int, default=20, help="Максимум конфликтов в отчёте.")
    parser.add_argument("--use-llm", action="store_true", help="Включить LLM-анализ после преселекции.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global client
    if args.use_llm:
        try:
            client = get_client()
        except Exception as e:
            safe_print(f"WARNING: LLM отключён: {e}")
            args.use_llm = False

    vault, checked_paths = resolve_vault_path(args.vault)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (vault / output_path).resolve()

    docs = load_docs(vault)
    candidates = build_candidates(docs, max(1, args.candidate_limit)) if docs else []
    report = build_report(
        vault,
        candidates,
        use_llm=args.use_llm,
        top_n=max(1, args.top),
        docs_count=len(docs),
        checked_paths=checked_paths,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    safe_print(f"Готово: {output_path}")
    safe_print(f"Vault: {vault}")
    safe_print(f"Документов: {len(docs)}; кандидатов: {len(candidates)}")


if __name__ == "__main__":
    main()
