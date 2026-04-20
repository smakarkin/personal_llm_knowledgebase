# Dataview-запросы для generated LLM-слоя

Ниже — готовые примеры для стабильных полей frontmatter в generated-файлах (`11_*`, `12_*`, `13_*`).

## 1) Concepts по режиму (mode)

```dataview
TABLE concept_mode AS "Режим", cluster AS "Кластер", status AS "Статус"
FROM "12_llm_concepts"
WHERE type = "llm_concept" AND concept_mode = "primary"
SORT cluster ASC
```

## 2) Collections по кластеру

```dataview
TABLE collection_mode AS "Режим", length(source_notes) AS "Кол-во заметок", based_on_scope AS "Scope"
FROM "11_llm_collections_primary" OR "11_llm_collections_candidate"
WHERE type = "llm_collection" AND cluster = "ВАШ_КЛАСТЕР"
SORT file.name ASC
```

## 3) Все generated-файлы со статусом draft

```dataview
TABLE type AS "Тип", status AS "Статус", file.folder AS "Папка"
FROM "11_llm_collections_primary" OR "11_llm_collections_candidate" OR "12_llm_concepts" OR "13_llm_indexes"
WHERE status = "draft"
SORT type ASC, file.name ASC
```

## 4) Collections с недостаточным числом source_notes

```dataview
TABLE cluster AS "Кластер", collection_mode AS "Режим", length(source_notes) AS "Кол-во source_notes"
FROM "11_llm_collections_primary" OR "11_llm_collections_candidate"
WHERE type = "llm_collection" AND length(source_notes) < 2
SORT length(source_notes) ASC, file.name ASC
```

## 5) Index-файлы с покрытием по источникам

```dataview
TABLE index_mode AS "Режим",
      length(source_collections) AS "Collections",
      length(source_concepts) AS "Concepts",
      length(source_scopes) AS "Scopes"
FROM "13_llm_indexes"
WHERE type = "llm_index"
SORT index_mode ASC
```
