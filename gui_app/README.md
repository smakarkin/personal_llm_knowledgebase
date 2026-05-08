# GUI MVP для управления Knowledge Base

Это первый каркас desktop-приложения на **PySide6** поверх существующих Python-скриптов.

## Что уже есть
- Главное окно с левым меню.
- Разделы: Dashboard, Pipeline, InBox, Rebuild, Trace, Sources, Health, Logs.
- Пустые страницы-заглушки для каждого раздела.
- Базовый сервис `ScriptRunner` для запуска backend-скриптов через `subprocess`.

## Установка
Из корня репозитория:

```bash
python -m venv .venv
source .venv/bin/activate  # для Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Запуск
Из корня репозитория:

```bash
python -m gui_app.main
```

## Следующий шаг
Подключить кнопки и формы на странице Pipeline/Rebuild для вызова существующих скриптов
(`propose_clusters.py`, `build_collection.py`, `generate_concepts.py`, `generate_index.py` и т.д.)
без изменения их бизнес-логики.

## Конфиг путей (без GUI)
По умолчанию приложение читает `gui_app/config.local.json`, а если его нет — `gui_app/config.json`.

Поля:
- `vault_path` — путь к Obsidian-хранилищу (где лежат InBox/Zettelkasten/LLM-слои).
- `scripts_path` — путь к папке с backend-скриптами.
- `inbox_folder` — имя папки входящих в vault (например, `__Inbox`).

Пример:
```json
{
  "vault_path": "../my_obsidian_vault",
  "scripts_path": "..",
  "inbox_folder": "__Inbox"
}
```

Рекомендуется создать `gui_app/config.local.json` со своими путями и не коммитить его.
