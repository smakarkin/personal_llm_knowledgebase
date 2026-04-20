from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

VAULT = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")
LOG_PATH = VAULT / "13_llm_indexes" / "log.md"


def parse_args() -> tuple[str, str, str, str]:
    if len(sys.argv) != 5:
        raise SystemExit(
            'Использование: python append_log.py "Каталог" "Режим" "Шаг" "success|error"'
        )

    folder, mode, step, status = sys.argv[1:5]
    status = status.strip().lower()
    if status not in {"success", "error"}:
        raise SystemExit('Статус должен быть "success" или "error"')

    return folder, mode, step, status


def ensure_header(path: Path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Журнал операций knowledge layer\n\n", encoding="utf-8")


def append_record(path: Path, folder: str, mode: str, step: str, status: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"- {timestamp} | каталог: {folder} | режим: {mode} | "
        f"шаг: {step} | статус: {status}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)


def main():
    folder, mode, step, status = parse_args()
    ensure_header(LOG_PATH)
    append_record(LOG_PATH, folder, mode, step, status)


if __name__ == "__main__":
    main()
