"""SQLAlchemy models for HermesWith persistence layer."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID

from hermeswith.persistence.database import Base


class GoalDB(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String, index=True, nullable=False)
    company_id = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    context = Column(JSONB, default=dict)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GoalExecutionDB(Base):
    __tablename__ = "goal_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    agent_id = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    final_output = Column(Text, default="")
    trajectory = Column(JSONB, default=list)
    tool_calls = Column(JSONB, default=list)
    token_usage = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class AgentMemoryDB(Base):
    __tablename__ = "agent_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String, index=True, nullable=False)
    memory_type = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    importance = Column(Float, default=0.5, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
