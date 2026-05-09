# GUI V3 — Knowledge Operations Center (desktop-first)

GUI остаётся **thin orchestration layer** над существующими `scripts/*.py` и структурой Obsidian-vault.

## Запуск
```bash
python -m gui_app.main
```

## Новая операционная модель V3
Вместо «набор экранов» приложение теперь работает как **центр рабочих очередей**:
- InBox Queue
- Ready to Transfer Queue
- Rebuild Queue
- Trace Review Queue
- Concept Promotion Queue
- Source Review Queue
- Health Attention Queue

Для каждой очереди показываются:
- count,
- severity/priority,
- why it exists,
- recommended action,
- open items.

## Dashboard V3
Dashboard теперь стартовая operational-страница:
- summary cards по состоянию базы,
- active queues,
- review-list с unified item status,
- recent operations/pinned state,
- health summary и диагностика,
- actionable follow-up в одной точке.

## Unified review workflow
Единая модель review item (`gui_app/models/queues.py`):
- open item,
- preview/reason,
- upstream/downstream контекст (модель поддерживает поля),
- mark reviewed/deferred/promoted (persisted в local state),
- открыть связанный артефакт (через существующие сервисы).

## Work modes
Сервис work-modes добавляет task-oriented режимы:
- Быстро разобрать входящие,
- Обновить knowledge layer,
- Исследовать идею,
- Очистить/починить базу,
- Работать с источниками,
- Подготовить перенос в Zettelkasten.

## Local persistence V3
`gui_app_data/workbench_state.json` теперь хранит дополнительно:
- dismissed recommendations,
- deferred review items,
- pinned queues,
- pinned files,
- recent scenarios,
- work mode preferences,
- expanded/collapsed UI sections,
- last viewed artifact per section,
- review item status map.

## Архитектура (cleaner split)
- `models/` — typed dataclasses для статусов, очередей, review item.
- `services/` — инспекция состояния, queue builder, скрипт-раннеры, health/trace.
- `views/` — pages + main window.
- `widgets/` — переиспользуемые UI-блоки (progress/log).
- `persistence/` — реализована через `WorkbenchStateStore` (JSON local-first).

## Known limitations
- Не используется внешняя БД (только JSON persistence).
- Очереди формируются эвристически из текущих файлов/слоёв; deep semantic routing можно усилить в следующей версии.
- Основные действия по backend по-прежнему выполняются через существующие скрипты subprocess.
