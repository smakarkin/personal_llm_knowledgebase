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
