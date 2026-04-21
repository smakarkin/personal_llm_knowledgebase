# InBox ingest workflow (короткий формальный регламент)

## Назначение
Этот workflow описывает **минимальный** и повторяемый процесс обработки входящих заметок из `__Inbox` (или `InBox`, если у вас так называется папка):

`__Inbox -> classify/cluster -> collections -> (опционально) indexes -> ручная проверка -> перенос в Zettelkasten вручную`

Важно:
- автоматического переноса в `Zettelkasten` нет;
- основной `rebuild_zettelkasten_all.bat` не затрагивается.

---

## Предусловия
- Входящие заметки находятся в папке `__Inbox` (или `InBox`, если у вас так настроено).
- Скрипты доступны в корне репозитория:
  - `propose_clusters.py`
  - `classify_notes.py` (альтернатива при уже готовой схеме)
  - `build_collection.py`
  - `generate_index.py`

---

## Пошаговый процесс ingest

### Шаг 1. Классификация и дозаполнение схемы
Рекомендуемая команда:

```bat
python propose_clusters.py __Inbox
```

Что делает:
- при отсутствии схемы создаёт/дополняет cluster scheme;
- проставляет `llm_*` поля у необработанных заметок;
- помечает обработанные заметки (`llm_processed: true`).

> Если схема уже стабильна и нужна только классификация, допускается:
>
> `python classify_notes.py __Inbox`

### Шаг 2. Сборка collections по InBox
Выполнить оба режима:

```bat
python build_collection.py __Inbox primary
python build_collection.py __Inbox candidate
```

Результат:
- обновлены `11_llm_collections_primary`;
- обновлены `11_llm_collections_candidate`.

### Шаг 3. (Опционально) обновление index-файлов
Запускать, если после ingest хотите сразу актуализировать обзорный слой:

```bat
python generate_index.py primary
python generate_index.py candidate
```

---

## Критерий готовности заметки к переносу в Zettelkasten
Заметка из `__Inbox`/`InBox` считается готовой к **ручному** переносу, если одновременно выполнено:

1. У заметки заполнены обязательные поля классификации:
   - `llm_topic`
   - `llm_semantic_type`
   - `llm_primary_cluster`
   - `llm_candidate_clusters`
   - `llm_cluster`
   - `llm_processed: true`
2. Содержимое заметки достаточно оформлено человеком (заголовок, формулировка мысли, отсутствие черновых пометок «TODO позже»).
3. Заметка попала минимум в одну актуальную collection (обычно `primary`).
4. Решение о переносе принято вручную (без автоматических move/rename в скриптах).

---

## Короткий чеклист ручной проверки после ingest
- [ ] В `__Inbox` (или вашей входящей папке) не осталось важных заметок без `llm_processed: true`.
- [ ] Для обработанных заметок заполнены ключевые `llm_*` поля (topic/type/clusters).
- [ ] Сформировались/обновились collections для `primary` и `candidate`.
- [ ] В collections корректные wikilinks на исходные заметки.
- [ ] (Если запускали) `Primary index.md` и `Candidate index.md` обновлены без ошибок.
- [ ] Перенос в `Zettelkasten` выполняется только вручную, точечно.

---

## Рекомендуемый быстрый запуск
Для стандартного прогона ingest используйте:

```bat
commands\run_inbox_ingest.bat __Inbox yes
```

Где:
- `__Inbox` — имя scope-папки по умолчанию (можно передать `InBox` или другое имя вашей входящей папки);
- `yes` — обновлять индексы (`no` — пропустить).
