from __future__ import annotations

from gui_app.models.status_models import KnowledgeBaseState, PipelineNode, RecommendedAction, ScenarioPlan, ScenarioStep


class ScenarioPlanner:
    """Строит сценарии из текущего состояния графа, без хардкода на UI-уровне."""

    def __init__(self, nodes: dict[str, PipelineNode]) -> None:
        self._nodes = nodes

    def build_minimal_plan(self, state: KnowledgeBaseState) -> ScenarioPlan:
        action = state.recommended_action
        step = ScenarioStep(action.title, action.command[0], tuple(action.command[1:]))
        return ScenarioPlan(
            key="minimal_recommended",
            title="Минимальный рекомендованный",
            description=action.reason,
            steps=(step,),
        )

    def build_safe_plan(self, state: KnowledgeBaseState) -> ScenarioPlan:
        desired = ["classify_inbox", "classify_zettelkasten", "build_primary", "generate_primary_concepts", "generate_primary_index"]
        steps = tuple(self._to_step(node_id) for node_id in desired if node_id in self._nodes)
        return ScenarioPlan(
            key="safe_path",
            title="Безопасный сценарий",
            description="Консервативный проход: классификация и полный primary-слой.",
            steps=steps,
        )

    def build_full_plan(self, state: KnowledgeBaseState) -> ScenarioPlan:
        order = [
            "classify_zettelkasten",
            "build_primary",
            "generate_primary_concepts",
            "generate_primary_index",
            "build_candidate",
            "generate_candidate_concepts",
            "generate_candidate_index",
        ]
        steps = tuple(self._to_step(node_id) for node_id in order if node_id in self._nodes)
        return ScenarioPlan(
            key="full_rebuild",
            title="Полная пересборка",
            description="Полный rebuild primary/candidate поверх текущего Zettelkasten.",
            steps=steps,
        )

    def _to_step(self, node_id: str) -> ScenarioStep:
        node = self._nodes[node_id]
        return ScenarioStep(node.title, node.command[0], tuple(node.command[1:]))
