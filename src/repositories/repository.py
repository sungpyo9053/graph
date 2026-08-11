from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.models.schemas import IdeaState
from src.repositories.entities import FinalReport, GraphRun, HumanApproval, Idea, NodeRun


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def create_idea(self, *, title: str, description: str, is_fixture: bool) -> Idea:
        idea = Idea(title=title, description=description, is_fixture=is_fixture)
        self.session.add(idea)
        self.session.commit()
        return idea

    def list_ideas(self) -> list[Idea]:
        return list(self.session.scalars(select(Idea).order_by(Idea.created_at.desc())))

    def get_idea(self, idea_id: str) -> Idea | None:
        return self.session.get(Idea, idea_id)

    def create_run(self, state: IdeaState) -> GraphRun:
        run = GraphRun(
            id=state.run_id,
            idea_id=state.candidate_id,
            status=state.status,
            current_node=state.current_node,
            state_snapshot=state.model_dump(mode="json"),
        )
        self.session.add(run)
        self.session.commit()
        return run

    def save_state(self, state: IdeaState) -> None:
        run = self.session.get(GraphRun, state.run_id)
        if run is None:
            raise LookupError(state.run_id)
        run.status = state.status
        run.current_node = state.current_node
        run.state_snapshot = state.model_dump(mode="json")
        run.pending_approval_id = state.pending_approval_id
        run.total_node_count = state.total_node_count
        run.total_model_calls = state.total_model_calls
        run.estimated_cost = state.estimated_cost
        idea = self.session.get(Idea, state.candidate_id)
        if idea:
            idea.status = state.status
            idea.risk_level = state.risk_level
            idea.evidence_score = (
                state.problem_strength_score.value
                + state.repetition_score.value
                + state.workaround_score.value
            )
            idea.total_score = state.total_score
            idea.confidence = state.confidence
        self.session.commit()

    def load_state(self, run_id: str) -> IdeaState:
        run = self.session.get(GraphRun, run_id)
        if run is None:
            raise LookupError(run_id)
        return IdeaState.model_validate(run.state_snapshot)

    def add_node_run(self, node_run: NodeRun) -> None:
        self.session.add(node_run)
        self.session.commit()

    def node_runs(self, run_id: str) -> list[NodeRun]:
        stmt = select(NodeRun).where(NodeRun.run_id == run_id).order_by(NodeRun.started_at)
        return list(self.session.scalars(stmt))

    def create_approval(self, state: IdeaState, reason: str) -> HumanApproval:
        approval = HumanApproval(run_id=state.run_id, idea_id=state.candidate_id, reason=reason)
        self.session.add(approval)
        self.session.commit()
        return approval

    def get_approval(self, approval_id: str) -> HumanApproval | None:
        return self.session.get(HumanApproval, approval_id)

    def save_report(self, idea_id: str, human_card: str, payload: dict[str, Any]) -> FinalReport:
        report = self.session.scalar(select(FinalReport).where(FinalReport.idea_id == idea_id))
        if report is None:
            report = FinalReport(idea_id=idea_id, human_card=human_card, payload=payload)
            self.session.add(report)
        else:
            report.human_card = human_card
            report.payload = payload
        self.session.commit()
        return report

    def get_report(self, idea_id: str) -> FinalReport | None:
        return self.session.scalar(select(FinalReport).where(FinalReport.idea_id == idea_id))
