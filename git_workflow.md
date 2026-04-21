# Git workflow для generated layers

Короткий и безопасный цикл работы с LLM-слоем без изменения архитектуры.

## Когда делать commit

1. **Перед rebuild** (checkpoint):
   - если есть ручные правки скриптов/правил/заметок,
   - чтобы можно было быстро откатить генерацию.
2. **После rebuild**:
   - отдельным коммитом только с generated-изменениями (`10_llm_meta` ... `13_llm_indexes`).
3. **Не смешивать** в одном коммите:
   - изменения пайплайна (`*.py`, `commands/*.bat`) и массовую перегенерацию markdown.

## Когда запускать rebuild

Рекомендуемый триггер:
- добавили новую пачку raw-заметок;
- изменили кластерную схему/правила классификации;
- изменили логику `build_collection.py`, `generate_concepts.py`, `generate_index.py`.

Перед rebuild полезно:
- убедиться, что рабочее дерево чистое (`git status`),
- либо сделать checkpoint-коммит.

## Как смотреть diff по generated слоям

### Быстрый обзор

```bash
git status
git diff --stat -- 10_llm_meta 11_llm_collections_primary 11_llm_collections_candidate 12_llm_concepts 13_llm_indexes
```

### Точечный просмотр только нужного mode

```bash
git diff -- 11_llm_collections_primary 12_llm_concepts 13_llm_indexes/Primary\ index.md
```

```bash
git diff -- 11_llm_collections_candidate 12_llm_concepts 13_llm_indexes/Candidate\ index.md
```

### Игнорировать шум в пробелах при обзоре

```bash
git diff -w -- 11_llm_collections_primary 11_llm_collections_candidate 12_llm_concepts 13_llm_indexes
```

## Минимальные правила стабильного diff

- Сохранять детерминированный порядок входов: сортировка путей/файлов перед генерацией.
- Не менять порядок frontmatter-полей без необходимости (в скриптах уже используется `sort_keys=False`).
- Служебные поля в frontmatter держать стабильными по структуре между перезапусками.
- Для каждого rebuild использовать одинаковый mode (`primary`/`candidate`) и одинаковые входные данные.
