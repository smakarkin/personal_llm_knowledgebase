"""Конфигурация GUI-приложения и пользовательских настроек."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INBOX_FOLDER = "InBox"
DEFAULT_ZETTELKASTEN_FOLDER = "Zettelkasten"
LLM_COLLECTIONS_PRIMARY_DIR = "11_llm_collections_primary"
LLM_COLLECTIONS_CANDIDATE_DIR = "11_llm_collections_candidate"
LLM_CONCEPTS_DIR = "12_llm_concepts"
LLM_INDEXES_DIR = "13_llm_indexes"
LLM_TRACES_DIR = "14_llm_traces"


@dataclass(frozen=True)
class AppConfig:
    """Пути к vault Obsidian и каталогу backend-скриптов."""

    vault_path: Path
    scripts_path: Path
    inbox_folder: str
    preferred_startup_page: str = "Dashboard"
    log_location: str = "gui_app_data/logs"
    obsidian_integration_mode: bool = True
    show_candidate_by_default: bool = True
    data_dir: Path = Path("gui_app_data")


def load_app_config(config_path: Path | None = None) -> AppConfig:
    """Загружает конфиг из JSON-файла.

    По умолчанию ищет `gui_app/config.local.json`, затем `gui_app/config.json`.
    Если файлов нет, используются пути относительно корня репозитория.
    """

    repo_root = Path(__file__).resolve().parents[1]
    selected = _select_config_path(config_path)

    if selected is None:
        return AppConfig(vault_path=repo_root, scripts_path=repo_root, inbox_folder=DEFAULT_INBOX_FOLDER)

    payload = json.loads(selected.read_text(encoding="utf-8"))

    vault_raw = payload.get("vault_path")
    scripts_raw = payload.get("scripts_path")
    inbox_folder = payload.get("inbox_folder", DEFAULT_INBOX_FOLDER)

    vault_path = _resolve_path(vault_raw, base_dir=selected.parent, fallback=repo_root)
    scripts_path = _resolve_path(scripts_raw, base_dir=selected.parent, fallback=repo_root)

    return AppConfig(
        vault_path=vault_path,
        scripts_path=scripts_path,
        inbox_folder=str(inbox_folder),
        preferred_startup_page=str(payload.get("preferred_startup_page", "Dashboard")),
        log_location=str(payload.get("log_location", "gui_app_data/logs")),
        obsidian_integration_mode=bool(payload.get("obsidian_integration_mode", True)),
        show_candidate_by_default=bool(payload.get("show_candidate_by_default", True)),
        data_dir=_resolve_path(payload.get("data_dir", "gui_app_data"), base_dir=selected.parent, fallback=repo_root / "gui_app_data"),
    )


def save_app_config(config: AppConfig, config_path: Path | None = None) -> Path:
    selected = _select_config_path(config_path) or (Path(__file__).resolve().parent / "config.local.json")
    payload = {
        "vault_path": str(config.vault_path),
        "scripts_path": str(config.scripts_path),
        "inbox_folder": config.inbox_folder,
        "preferred_startup_page": config.preferred_startup_page,
        "log_location": config.log_location,
        "obsidian_integration_mode": config.obsidian_integration_mode,
        "show_candidate_by_default": config.show_candidate_by_default,
        "data_dir": str(config.data_dir),
    }
    selected.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return selected


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
