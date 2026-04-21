---
type: llm_trace
trace_created_at: YYYY-MM-DD HH:MM:SS
trace_query: "<исходный запрос>"
status: draft
---

# Trace: <краткое имя запроса>

## Исходный запрос
<вопрос/задача пользователя в исходной формулировке>

## Найденные collections/concepts
- **collection|concept** [[...]]
  - relevance: high|medium|low
  - extracted_idea: <какая идея извлекается>
  - why: <почему связано с запросом>

## Найденные source notes
- [[...]]
  - via: [[collection/concept, через который найдена заметка]]
  - relevance: high|medium|low
  - extracted_idea: <ключевой фрагмент смысла>
  - why_related: <почему заметка релевантна>

## Объяснение релевантности
<2–5 предложений: как верхний слой и source notes подтверждают ответ>

## Краткая synthesis/hypothesis *(опционально)*
<добавляется только если есть source notes и из них удалось собрать устойчивый синтез>
