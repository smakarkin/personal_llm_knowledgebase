"""Конфигурация GUI-приложения (без отдельного экрана настроек)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Пути к vault Obsidian и каталогу backend-скриптов."""

    vault_path: Path
    scripts_path: Path


def load_app_config(config_path: Path | None = None) -> AppConfig:
    """Загружает конфиг из JSON-файла.

    По умолчанию ищет `gui_app/config.local.json`, затем `gui_app/config.json`.
    Если файлов нет, используются пути относительно корня репозитория.
    """

    repo_root = Path(__file__).resolve().parents[1]
    selected = _select_config_path(config_path)

    if selected is None:
        return AppConfig(vault_path=repo_root, scripts_path=repo_root)

    payload = json.loads(selected.read_text(encoding="utf-8"))

    vault_raw = payload.get("vault_path")
    scripts_raw = payload.get("scripts_path")

    vault_path = _resolve_path(vault_raw, base_dir=selected.parent, fallback=repo_root)
    scripts_path = _resolve_path(scripts_raw, base_dir=selected.parent, fallback=repo_root)

    return AppConfig(vault_path=vault_path, scripts_path=scripts_path)


def _select_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit

    gui_dir = Path(__file__).resolve().parent
    for name in ("config.local.json", "config.json"):
        candidate = gui_dir / name
        if candidate.exists():
            return candidate
    return None


def _resolve_path(raw_value: str | None, *, base_dir: Path, fallback: Path) -> Path:
    if not raw_value:
        return fallback

    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path
