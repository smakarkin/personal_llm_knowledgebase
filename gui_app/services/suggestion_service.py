from __future__ import annotations

class SuggestionService:
    def build(self, freshness: dict[str, str]) -> dict[str, list[str]]:
        plan = []
        if freshness.get('semantic_index') == 'stale':
            plan.append('Пересобрать локальный semantic index (preview-first).')
        if freshness.get('concepts_vs_collections') == 'stale':
            plan.append('Обновить concepts после изменений collections.')
        if freshness.get('indexes_vs_concepts') == 'stale':
            plan.append('Перегенерировать indexes после concepts.')
        if not plan:
            plan.append('Слой свежий: выполнить targeted trace для новых гипотез.')
        return {
            'recommended_rebuild_plan': plan,
            'next_manual_actions': plan[:3],
            'traces_to_revisit': ['trace со статусом draft/new и низким source_items coverage'],
            'candidate_concepts_review': ['проверить concepts без promoted статуса'],
            'attachments_to_promote': ['raw/assets и raw/imports без source-note вики-ссылок'],
        }
