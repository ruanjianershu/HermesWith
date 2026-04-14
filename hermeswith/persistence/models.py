"""SQLAlchemy models for HermesWith persistence layer."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID

from hermeswith.persistence.database import Base


class CompanyDB(Base):
    """Company/tenant model for multi-tenant isolation."""
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    # Use 'meta' instead of 'metadata' to avoid SQLAlchemy reserved name
    meta = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APIKeyDB(Base):
    """API Key model for company authentication."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False)  # Hashed API key
    permissions = Column(JSONB, default=list)  # ["read", "write", "admin"]
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class AuditLogDB(Base):
    """Audit log for all API requests and actions."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True, index=True)
    
    # Request details
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    query_params = Column(JSONB, default=dict)
    request_body = Column(JSONB, nullable=True)
    
    # Response details
    status_code = Column(Integer, nullable=True)
    response_size = Column(Integer, default=0)
    
    # Context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    
    # Additional metadata
    action = Column(String, nullable=True)  # e.g., "goal_created", "agent_registered"
    resource_type = Column(String, nullable=True)  # e.g., "goal", "agent"
    resource_id = Column(String, nullable=True)
    # Additional metadata (use 'meta' to avoid SQLAlchemy reserved name)
    meta = Column(JSONB, default=dict)


class RateLimitDB(Base):
    """Rate limiting tracking per API key."""
    __tablename__ = "rate_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False, index=True)
    endpoint = Column(String, nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    request_count = Column(Integer, default=1, nullable=False)


class EncryptedConfigDB(Base):
    """Encrypted configuration storage for sensitive data."""
    __tablename__ = "encrypted_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Composite unique index for efficient config lookups
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    config_type = Column(String, nullable=False, index=True)
    config_key = Column(String, nullable=False)
    encrypted_value = Column(Text, nullable=False)  # Fernet encrypted
    key_version = Column(String, nullable=False)  # For key rotation tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class AgentDB(Base):
    """Agent model for Clawith integration."""
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    model = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=True)
    tools = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    clawith_agent_id = Column(String, nullable=True)  # Clawith agent ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskDB(Base):
    """Task model for agent assignments."""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    instruction = Column(Text, nullable=False)
    status = Column(String, default="pending", nullable=False)
    priority = Column(String, default="medium", nullable=False)
    clawith_task_id = Column(String, nullable=True)  # Clawith task ID
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentOutputDB(Base):
    """Agent output model for task results."""
    __tablename__ = "agent_outputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True)
    output_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    # Use 'meta' instead of 'metadata' to avoid SQLAlchemy reserved name
    meta = Column(JSONB, default=dict)
    clawith_output_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
