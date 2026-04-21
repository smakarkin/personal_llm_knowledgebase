# AGENTS.md — каноническое описание LLM-слоя Obsidian-базы

## Knowledge layer журнал
- Основной bat-пайплайн `commands/rebuild_zettelkasten_all.bat` дописывает append-only журнал операций в markdown-файл `13_llm_indexes/log.md` (внутри configured VAULT).
- Формат записи: дата/время, каталог, режим, шаг, статус (`success` или `error`).
- Для записи используется скрипт `append_log.py`.

## 1) Назначение
Этот репозиторий управляет **генерируемым LLM-слоем** поверх Obsidian-хранилища:
- классификация raw-заметок,
- сборка collections,
- синтез concepts,
- построение index-файлов.

Исходные заметки (InBox / Zettelkasten / Концентраторы и др.) — первичный слой знаний. LLM-папки — производные артефакты.

---

## 2) Актуальная структура слоёв
- `raw/` — **immutable raw layer** для исходных источников (`raw/articles`, `raw/books`, `raw/assets`, `raw/imports`) без автоматической миграции старых заметок.
- `InBox`, `Zettelkasten`, `Концентраторы` и другие содержательные папки — **рабочие заметки и интерпретации** поверх raw-источников.
- `10_llm_meta` — схемы кластеров (cluster scheme) по scope-папкам.
- `11_llm_collections_primary` — collections по `llm_primary_cluster`.
- `11_llm_collections_candidate` — collections по `llm_candidate_clusters`.
- `12_llm_concepts` — concept-заметки, синтезированные из collections выбранного mode.
- `13_llm_indexes` — обзорные index-файлы по mode.
- `14_llm_traces` — служебный слой для трасс/отладочных артефактов (не участвует в текущей генерации).

Важно: скрипты специально исключают LLM-слои из обхода raw-заметок (`10_llm_meta`, `11_llm_*`, `12_llm_concepts`, `13_llm_indexes`; в link-fixer также `14_llm_traces`).

---

## 3) Naming conventions (обязательные)
- **Cluster scheme**: `Cluster Scheme - folder - <scope>.md` (в `10_llm_meta`).
- **Collections**: `<имя кластера> - <mode>.md`, где `<mode>` = `primary` | `candidate`.
- **Concepts**: `<имя concept>.md` (берётся из секции `# Понятие`).
- **Indexes**: `Primary index.md` и `Candidate index.md`.

Санитизация имени файла обязательна: недопустимые символы Windows (`<>:"/\\|?*`) заменяются на `-`.

---

## 4) Обязательные frontmatter-поля

## 4.1 Raw note (после classify/propose)
Для заметки, прошедшей классификацию, обязательны:
- `llm_topic`
- `llm_semantic_type` (одно из: `hypothesis`, `question`, `observation`, `claim`, `example`, `reference`)
- `llm_primary_cluster`
- `llm_candidate_clusters` (list, до 5)
- `llm_cluster` (дублирует primary)
- `llm_processed: true`

Для пропущенной пустой заметки:
- `llm_processed: true`
- `llm_skip_reason: empty_body`

## 4.2 Cluster scheme (`10_llm_meta`)
- `type: llm_cluster_scheme`
- `scope_type: folder`
- `scope_folder: <имя папки scope>`

## 4.3 Collection (`11_llm_collections_*`)
- `type: llm_collection`
- `collection_mode: primary|candidate`
- `based_on_scope: <scope>`
- `cluster: <cluster id>`
- `source_notes: ["[[...]]", ...]`
- `topics: []`
- `status: draft`

## 4.4 Concept (`12_llm_concepts`)
- `type: llm_concept`
- `concept_mode: primary|candidate`
- `cluster: <cluster id>`
- `source_collections: ["[[...]]", ...]`
- `source_scopes: ["...", ...]`
- `status: draft`

## 4.5 Index (`13_llm_indexes`)
- `type: llm_index`
- `index_mode: primary|candidate`
- `source_collections: ["[[...]]", ...]`
- `source_concepts: ["[[...]]", ...]`
- `source_scopes: ["...", ...]`
- `status: draft`

---

## 5) Канонический пайплайн
`ingest -> classify -> collections -> concepts -> index`

1. **Ingest**
   - Новые заметки попадают в scope-папку (часто `__Inbox`/`InBox`).
   - Опционально сбросить LLM-поля: `reset_llm_fields.py <folder>`.

2. **Classify**
   - `propose_clusters.py <folder>`:
     - если схемы нет — создаёт cluster scheme в `10_llm_meta`;
     - классифицирует необработанные заметки батчами;
     - выставляет `llm_*` поля в raw notes.
   - `classify_notes.py <folder>` — альтернативный классификатор по существующей схеме.

3. **Collections**
   - `build_collection.py <folder> primary|candidate`.
   - Генерирует collections в соответствующий каталог `11_llm_collections_*`.

4. **Concepts**
   - `generate_concepts.py primary|candidate`.
   - Читает collections выбранного mode и создаёт concept-файлы в `12_llm_concepts`.

5. **Index**
   - `generate_index.py primary|candidate`.
   - Создаёт mode-специфичный обзорный index в `13_llm_indexes`.

Готовые bat-оркестраторы:
- `commands/run_folder_pipeline.bat` — classify + collections (по mode).
- `commands/rebuild_zettelkasten_all.bat` — полный rebuild: primary и candidate (collections+concepts+indexes).
- `commands/run_inbox.bat` — запуск папочного пайплайна для `__Inbox` в режиме `both`.

---

## 6) Primary vs Candidate
- **Primary**
  - Основан только на `llm_primary_cluster` каждой заметки.
  - Даёт более строгую, менее шумную структуру.
  - Используется как «основной» слой обзора.

- **Candidate**
  - Основан на полном списке `llm_candidate_clusters`.
  - Одна заметка может участвовать в нескольких кластерах.
  - Даёт более широкий поисковый/гипотезный контур, но с большим шумом.

Indexes и concepts строятся **отдельно** для каждого mode.

---

## 7) Правила безопасных изменений
1. **Не переписывать raw notes без необходимости**.
   - Допустимые изменения: только frontmatter `llm_*` и только скриптами пайплайна.
2. **Не ломать ссылки**.
   - Для нормализации ссылок в collections использовать `fix_collection_note_links.py`.
3. **Не смешивать слои**.
   - Zettelkasten/raw-папки ≠ generated LLM layers (`10+`).
4. **Соблюдать mode-изоляцию**.
   - Primary и candidate не объединять в один файл/индекс.
5. **Не менять naming conventions и `type`-поля frontmatter без миграции всех скриптов**.
6. **При правках пайплайна сохранять идемпотентность**.
   - Повторный запуск не должен разрушать структуру и связи.

---

## 8) Проверка после изменений
- [ ] Скрипты запускаются без изменения их контрактов CLI.
- [ ] Новые/обновлённые файлы попадают в правильные каталоги (`10`–`13`).
- [ ] Имена файлов соответствуют шаблонам (`<cluster> - <mode>`, `<concept>.md`, `Primary/Candidate index.md`).
- [ ] Frontmatter содержит обязательные поля для каждого типа файла.
- [ ] В raw notes не затронут контент, кроме допустимых `llm_*` полей.
- [ ] Wikilinks в collections/concepts/indexes валидны и не укорочены вручную.
