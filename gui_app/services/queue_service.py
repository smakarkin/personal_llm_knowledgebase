"""Operational queue builder for V3 dashboard/work modes."""

from __future__ import annotations

from pathlib import Path

from gui_app.models.queues import OperationalQueue, QueuePriority, ReviewItem, WorkMode
from gui_app.models.status_models import KnowledgeBaseState


class QueueService:
    def __init__(self, repo_root: Path, inbox_folder: str = "InBox") -> None:
        self.repo_root = repo_root
        self.inbox_folder = inbox_folder

    def build_queues(self, state: KnowledgeBaseState) -> list[OperationalQueue]:
        return [
            self._inbox_queue(state),
            self._ready_to_transfer_queue(),
            self._rebuild_queue(state),
            self._trace_review_queue(state),
            self._concept_promotion_queue(),
            self._source_review_queue(),
            self._health_attention_queue(state),
        ]

    def work_modes(self) -> list[WorkMode]:
        return [
            WorkMode("quick_inbox", "Быстро разобрать входящие", ["inbox", "source_review"], ["classify", "open_inbox"]),
            WorkMode("update_layer", "Обновить knowledge layer", ["rebuild", "trace_review"], ["rebuild_all", "generate_index"]),
            WorkMode("explore_idea", "Исследовать идею", ["trace_review", "concept_promotion"], ["run_trace", "open_concepts"]),
            WorkMode("cleanup", "Очистить/починить базу", ["health", "rebuild"], ["run_health", "fix_links"]),
            WorkMode("sources", "Работать с источниками", ["source_review", "inbox"], ["review_sources", "classify"]),
            WorkMode("prepare_transfer", "Подготовить перенос в Zettelkasten", ["ready_transfer", "concept_promotion"], ["open_zettelkasten", "promote"]),
        ]

    def _inbox_queue(self, state: KnowledgeBaseState) -> OperationalQueue:
        count = state.inbox_markdown_count
        items = [ReviewItem(f"inbox-{i}", "inbox", f"InBox note #{i+1}", "Нужно классифицировать") for i in range(min(10, count))]
        pr = QueuePriority.high if count > 20 else QueuePriority.medium if count > 5 else QueuePriority.low
        return OperationalQueue("inbox", "InBox Queue", "Во входящих есть необработанные заметки.", "Запустить classify/propose и сделать review.", pr, items)

    def _ready_to_transfer_queue(self) -> OperationalQueue:
        folder = self.repo_root / "12_llm_concepts"
        files = sorted(folder.glob("*.md"))[:10] if folder.exists() else []
        items = [ReviewItem(f"transfer-{p.stem}", "ready_transfer", p.stem, "Готово к ручному переносу в Zettelkasten", str(p)) for p in files]
        return OperationalQueue("ready_transfer", "Ready to Transfer Queue", "Отобранные concepts готовы к переносу.", "Открыть concept и перенести в постоянные заметки.", QueuePriority.medium, items)

    def _rebuild_queue(self, state: KnowledgeBaseState) -> OperationalQueue:
        stale = [d for d in state.diagnostics if "missing" in d.lower() or "not found" in d.lower()]
        items = [ReviewItem(f"rebuild-{i}", "rebuild", s, "Требуется пересборка слоя") for i, s in enumerate(stale)]
        pr = QueuePriority.high if items else QueuePriority.low
        return OperationalQueue("rebuild", "Rebuild Queue", "Слой знаний должен регулярно пересобираться.", "Запустить rebuild primary+candidate.", pr, items)

    def _trace_review_queue(self, state: KnowledgeBaseState) -> OperationalQueue:
        items = [ReviewItem(f"trace-{i}", "trace_review", f"Trace item #{i+1}", "Ожидает интерпретации") for i in range(min(10, state.traces_count))]
        return OperationalQueue("trace_review", "Trace Review Queue", "Trace-артефакты требуют решения по follow-up.", "Открыть trace и пометить: reviewed/deferred/promoted.", QueuePriority.medium, items)

    def _concept_promotion_queue(self) -> OperationalQueue:
        concepts_dir = self.repo_root / "12_llm_concepts"
        files = sorted(concepts_dir.glob("*.md"))[:10] if concepts_dir.exists() else []
        items = [ReviewItem(f"promote-{p.stem}", "concept_promotion", p.stem, "Кандидат в promoted concept", str(p)) for p in files]
        return OperationalQueue("concept_promotion", "Concept Promotion Queue", "Candidate concepts ожидают решения.", "Отметить promoted или deferred.", QueuePriority.medium, items)

    def _source_review_queue(self) -> OperationalQueue:
        src = self.repo_root / "raw" / "imports"
        files = sorted(src.glob("*.md"))[:10] if src.exists() else []
        items = [ReviewItem(f"src-{p.stem}", "source_review", p.stem, "Нужна проверка качества источника", str(p)) for p in files]
        return OperationalQueue("source_review", "Source Review Queue", "Импортированные источники требуют валидации.", "Открыть source, проверить и классифицировать.", QueuePriority.low, items)

    def _health_attention_queue(self, state: KnowledgeBaseState) -> OperationalQueue:
        items = [ReviewItem(f"health-{i}", "health", d, "Health issue") for i, d in enumerate(state.diagnostics[:10])]
        pr = QueuePriority.critical if items else QueuePriority.low
        return OperationalQueue("health", "Health Attention Queue", "Проблемы структуры/ссылок/слоёв требуют внимания.", "Запустить health checks и исправить critical issues.", pr, items)
