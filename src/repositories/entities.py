from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.schemas import utcnow
from src.repositories.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Idea(Base, TimestampMixin):
    __tablename__ = "ideas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW")
    evidence_score: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)


class GraphRun(Base, TimestampMixin):
    __tablename__ = "graph_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    current_node: Mapped[str] = mapped_column(String(64), default="START")
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    pending_approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    total_node_count: Mapped[int] = mapped_column(Integer, default=0)
    total_model_calls: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)


class NodeRun(Base):
    __tablename__ = "node_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("graph_runs.id"), index=True)
    node_name: Mapped[str] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schema_validation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    suggested_route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actual_route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    route_reason: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class HumanApproval(Base, TimestampMixin):
    __tablename__ = "human_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("graph_runs.id"), index=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    reason: Mapped[str] = mapped_column(Text, default="")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revise_node: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PayloadEntityMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Signal(Base, PayloadEntityMixin):
    __tablename__ = "signals"


class Evidence(Base, PayloadEntityMixin):
    __tablename__ = "evidence"


class Problem(Base, PayloadEntityMixin):
    __tablename__ = "problems"


class MarketStructure(Base, PayloadEntityMixin):
    __tablename__ = "market_structures"


class Wedge(Base, PayloadEntityMixin):
    __tablename__ = "wedges"


class AccumulatingAsset(Base, PayloadEntityMixin):
    __tablename__ = "accumulating_assets"


class ExpansionPath(Base, PayloadEntityMixin):
    __tablename__ = "expansion_paths"


class Review(Base, PayloadEntityMixin):
    __tablename__ = "reviews"


class Experiment(Base, PayloadEntityMixin):
    __tablename__ = "experiments"


class FinalReport(Base, TimestampMixin):
    __tablename__ = "final_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), unique=True, index=True)
    human_card: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
