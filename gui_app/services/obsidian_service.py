"""Obsidian-aware integration layer (V2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


@dataclass(frozen=True)
class HandoffItem:
    title: str
    path: Path
    status: str


class OpenStrategy(Protocol):
    def open_path(self, path: Path) -> bool: ...


class FilesystemOpenStrategy:
    def open_path(self, path: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class ObsidianService:
    def __init__(self, vault_root: Path, strategy: OpenStrategy | None = None) -> None:
        self._vault_root = vault_root
        self._strategy = strategy or FilesystemOpenStrategy()
        self._handoff_queue: list[HandoffItem] = []

    @property
    def handoff_queue(self) -> tuple[HandoffItem, ...]:
        return tuple(self._handoff_queue)

    def open_vault_root(self) -> bool:
        return self._strategy.open_path(self._vault_root)

    def open_folder(self, folder: Path) -> bool:
        return self._strategy.open_path(folder)

    def open_file(self, file_path: Path) -> bool:
        return self._strategy.open_path(file_path)

    def open_parent_folder(self, file_path: Path) -> bool:
        return self._strategy.open_path(file_path.parent)

    def build_obsidian_uri(self, target: Path) -> str | None:
        try:
            rel = target.resolve().relative_to(self._vault_root.resolve())
        except Exception:
            return None
        return f"obsidian://open?vault={quote(self._vault_root.name)}&file={quote(rel.as_posix())}"

    def add_to_handoff(self, title: str, path: Path, status: str) -> None:
        if any(item.path == path for item in self._handoff_queue):
            return
        self._handoff_queue.append(HandoffItem(title=title, path=path, status=status))

    def write_handoff_report(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"handoff_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        now = datetime.now(timezone.utc).astimezone().isoformat()
        lines = [
            "# Handoff report (manual transfer via Obsidian)",
            "",
            f"- Дата формирования: {now}",
            f"- Vault root: `{self._vault_root}`",
            "",
            "## Очередь ready-to-transfer",
            "",
        ]
        if not self._handoff_queue:
            lines.append("- Очередь пуста.")
        for idx, item in enumerate(self._handoff_queue, start=1):
            rel = item.path.relative_to(self._vault_root) if item.path.is_relative_to(self._vault_root) else item.path
            lines += [
                f"{idx}. **{item.title}**",
                f"   - Статус: {item.status}",
                f"   - Wikilink: [[{item.path.stem}]]",
                f"   - Путь: `{rel}`",
                "",
            ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path
