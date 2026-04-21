from __future__ import annotations

from pathlib import Path

RAW_ROOT = Path("raw")
OUTPUT = RAW_ROOT / "RAW_INDEX.md"
SECTIONS = [
    ("articles", "Статьи"),
    ("books", "Книги"),
    ("imports", "Импорты"),
]


def collect_md_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.rglob("*.md") if p.name != "RAW_INDEX.md")


def to_wikilink(path: Path) -> str:
    rel = path.as_posix()
    return f"[[{rel}|{path.stem}]]"


def main() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Raw index",
        "",
        "Автогенерируемый обзор markdown-файлов в raw-слое.",
        "",
    ]

    total = 0
    for section_key, section_title in SECTIONS:
        folder = RAW_ROOT / section_key
        files = collect_md_files(folder)
        total += len(files)

        lines.append(f"## {section_title} (`raw/{section_key}`)")
        if files:
            for file_path in files:
                lines.append(f"- {to_wikilink(file_path)}")
        else:
            lines.append("- _(пока пусто)_")
        lines.append("")

    lines.append(f"Всего markdown-файлов: **{total}**")
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Готово: {OUTPUT.as_posix()}")


if __name__ == "__main__":
    main()
