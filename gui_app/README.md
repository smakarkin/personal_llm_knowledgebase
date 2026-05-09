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

## V3 Review / Promotion / Provenance layer
Добавлен новый экран **Sources** (review center), который собирает целостный workflow review/provenance:
- lineage viewer (tree/expand) для concept/collection/trace/source-note,
- review actions с confirm + draft-first поведением,
- compare view (left/right) с shared sources, differing claims/framing и рекомендацией merge/split/keep separate,
- очереди review для weak provenance, promotion candidates, traces awaiting decision и source/attachment gaps.

### Новые сервисы
- `gui_app/services/provenance_service.py` — построение provenance tree:
  - concept -> source_collections -> source_notes -> attachments,
  - trace -> upstream matches + supporting notes.
- `gui_app/services/review_queue_service.py` — построение V3 review queues.
- `gui_app/services/compare_service.py` — compare двух markdown-артефактов.
- `gui_app/services/promotion_service.py` — guided promotion-обёртка (trace/collection/multi-collection -> concept draft).

### Review workflow (практически)
1. Открыть **Sources** и выбрать очередь (например `promotion_candidates`).
2. Выбрать элемент -> справа открыть preview и provenance tree.
3. Запустить action (accept/refine/attach/open collections/contradiction/manual revision) с подтверждением.
4. При необходимости сравнить текущий draft с существующим concept в compare-блоке.
5. Принять решение: сохранить draft concept, доработать, или оставить trace.

### Путь от trace к stable concept
1. Trace попадает в `traces_awaiting_decision`.
2. Если есть достаточная поддержка источниками — попадает в `promotion_candidates`.
3. Через promotion flow создаётся concept draft в `12_llm_concepts`.
4. Через review actions concept отмечается как stable (или refinement).
5. Provenance tree остаётся explainable: concept -> collections -> notes -> source artifacts.

### Manual test plan
1. Открыть GUI и перейти в раздел **Sources**.
2. Проверить, что queues отображаются и не пустые при наличии данных в `12_llm_concepts`, `14_llm_traces`, `raw`.
3. Выбрать concept item и проверить дерево lineage (collection -> notes -> attachment).
4. Выбрать trace item и проверить upstream/supporting nodes.
5. Нажать любой review-action и убедиться в confirm-диалоге.
6. Заполнить два пути в compare и проверить генерацию рекомендации.
7. Проверить, что существующие страницы (Dashboard/Trace/Rebuild/Health/InBox) продолжают открываться.
