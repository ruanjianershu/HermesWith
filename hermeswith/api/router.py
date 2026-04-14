"""FastAPI router for Hermeswith API."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from hermeswith.api.dependencies import get_current_company, get_db, require_permissions
from hermeswith.persistence.models import CompanyDB
from hermeswith.services.agent_service import AgentService
from hermeswith.services.task_service import TaskService
from hermeswith.services.output_service import OutputService


router = APIRouter()


# Pydantic models for request/response
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model: str = Field(default="anthropic/claude-opus-4")
    system_prompt: Optional[str] = None
    tools: List[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    model: str
    system_prompt: Optional[str]
    tools: List[str]
    is_active: bool
    clawith_agent_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    instruction: str = Field(..., min_length=1)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")


class TaskResponse(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID
    title: str
    description: Optional[str]
    instruction: str
    status: str
    priority: str
    clawith_task_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgentOutputResponse(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID
    task_id: Optional[UUID]
    output_type: str
    content: str
    metadata: dict
    created_at: datetime
    
    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


# Health check endpoint (no auth required)
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.utcnow(),
    )


# Agent endpoints
@router.post("/v1/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a new agent."""
    service = AgentService(db)
    agent = service.create_agent(
        company_id=company.id,
        name=agent_data.name,
        model=agent_data.model,
        system_prompt=agent_data.system_prompt,
        tools=agent_data.tools,
    )
    return agent


@router.get("/v1/agents", response_model=List[AgentResponse])
async def list_agents(
    is_active: Optional[bool] = None,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all agents for the company."""
    service = AgentService(db)
    agents = service.list_agents(
        company_id=company.id,
        filters={"is_active": is_active} if is_active is not None else None,
    )
    return agents


@router.get("/v1/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get a specific agent."""
    service = AgentService(db)
    agent = service.get_agent(company_id=company.id, agent_id=agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    return agent


@router.put("/v1/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update an agent."""
    service = AgentService(db)
    
    updates = agent_data.model_dump(exclude_unset=True)
    agent = service.update_agent(
        company_id=company.id,
        agent_id=agent_id,
        updates=updates,
    )
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    return agent


@router.delete("/v1/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Delete an agent."""
    service = AgentService(db)
    success = service.delete_agent(company_id=company.id, agent_id=agent_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    return None


# Task endpoints
@router.post("/v1/agents/{agent_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    agent_id: UUID,
    task_data: TaskCreate,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create and assign a task to an agent."""
    service = TaskService(db)
    
    task = service.create_task(
        company_id=company.id,
        agent_id=agent_id,
        title=task_data.title,
        description=task_data.description,
        instruction=task_data.instruction,
        priority=task_data.priority,
    )
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Assign task to agent (sync with Clawith)
    assigned = service.assign_task_to_agent(company_id=company.id, task_id=task.id)
    
    if not assigned:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign task to agent",
        )
    
    return task


@router.get("/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get task status."""
    service = TaskService(db)
    task = service.get_task(company_id=company.id, task_id=task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    # Sync status from Clawith
    service.sync_task_status(company_id=company.id, task_id=task_id)
    
    return task


@router.get("/v1/tasks/{task_id}/output")
async def get_task_output(
    task_id: UUID,
    company: CompanyDB = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get task output."""
    output_service = OutputService(db)
    outputs = output_service.get_task_outputs(
        company_id=company.id,
        task_id=task_id,
    )
    
    return {
        "task_id": task_id,
        "outputs": [
            {
                "id": str(o.id),
                "type": o.output_type,
                "content": o.content,
                "created_at": o.created_at.isoformat(),
            }
            for o in outputs
        ],
    }
