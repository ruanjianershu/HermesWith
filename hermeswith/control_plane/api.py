"""
Control Plane API - FastAPI application for managing goals and agents.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select

from hermeswith.control_plane.goal_queue import RedisGoalQueue
from hermeswith.persistence.database import AsyncSessionLocal
from hermeswith.persistence.models import GoalDB, GoalExecutionDB
from hermeswith.runtime import AgentConfig, AgentRuntime


class CreateGoalRequest(BaseModel):
    agent_id: str
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)


class GoalResponse(BaseModel):
    id: str
    agent_id: str
    company_id: str
    description: str
    status: str
    created_at: Optional[str] = None


class AgentStatusResponse(BaseModel):
    agent_id: str
    registered: bool
    paused: bool
    role: Optional[str] = None
    company_id: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections for real-time agent updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, agent_id: str):
        await websocket.accept()
        if agent_id not in self.active_connections:
            self.active_connections[agent_id] = []
        self.active_connections[agent_id].append(websocket)

    def disconnect(self, websocket: WebSocket, agent_id: str):
        if agent_id in self.active_connections:
            self.active_connections[agent_id].remove(websocket)

    async def send_to_agent(self, agent_id: str, message: dict):
        if agent_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[agent_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn, agent_id)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    print("🎛️  Control Plane starting...")
    redis_url = AgentConfig.from_env().redis_url
    app.state.goal_queue = RedisGoalQueue(redis_url)
    yield
    print("🎛️  Control Plane shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HermesWith Control Plane",
        description="API for managing autonomous agents, goals, and real-time collaboration.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # In-memory storage for agent runtimes only
    app.state.agents: Dict[str, AgentRuntime] = {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    # ------------------------------------------------------------------
    # Goal API
    # ------------------------------------------------------------------

    @app.post("/api/companies/{company_id}/goals", response_model=GoalResponse)
    async def create_goal(company_id: str, req: CreateGoalRequest):
        from hermeswith.runtime.agent_runtime import Goal

        goal = Goal(
            agent_id=req.agent_id,
            company_id=company_id,
            description=req.description,
            context=req.context,
        )

        async with AsyncSessionLocal() as session:
            db_goal = GoalDB(
                id=uuid.UUID(goal.id),
                agent_id=goal.agent_id,
                company_id=goal.company_id,
                description=goal.description,
                context=goal.context,
                status=goal.status,
                created_at=goal.created_at,
            )
            session.add(db_goal)
            await session.commit()

        # Push to Redis queue for agent pickup
        try:
            app.state.goal_queue.push(req.agent_id, goal)
        except Exception as e:
            print(f"⚠️  Failed to push goal to Redis queue: {e}")

        return GoalResponse(
            id=goal.id,
            agent_id=goal.agent_id,
            company_id=goal.company_id,
            description=goal.description,
            status=goal.status,
            created_at=goal.created_at.isoformat() if goal.created_at else None,
        )

    @app.get("/api/goals/{goal_id}")
    async def get_goal(goal_id: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GoalDB).where(GoalDB.id == uuid.UUID(goal_id))
            )
            db_goal = result.scalar_one_or_none()
            if not db_goal:
                raise HTTPException(status_code=404, detail="Goal not found")
            return {
                "id": str(db_goal.id),
                "agent_id": db_goal.agent_id,
                "company_id": db_goal.company_id,
                "description": db_goal.description,
                "status": db_goal.status,
                "context": db_goal.context,
                "created_at": db_goal.created_at.isoformat() if db_goal.created_at else None,
            }

    @app.get("/api/goals")
    async def list_goals(
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ):
        async with AsyncSessionLocal() as session:
            stmt = select(GoalDB)
            if agent_id:
                stmt = stmt.where(GoalDB.agent_id == agent_id)
            if status:
                stmt = stmt.where(GoalDB.status == status)
            stmt = stmt.offset(skip).limit(limit)
            result = await session.execute(stmt)
            db_goals = result.scalars().all()
            goals = [
                {
                    "id": str(g.id),
                    "agent_id": g.agent_id,
                    "company_id": g.company_id,
                    "description": g.description,
                    "status": g.status,
                    "context": g.context,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in db_goals
            ]
            return {"goals": goals, "total": len(goals), "skip": skip, "limit": limit}

    @app.delete("/api/goals/{goal_id}")
    async def delete_goal(goal_id: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GoalDB).where(GoalDB.id == uuid.UUID(goal_id))
            )
            db_goal = result.scalar_one_or_none()
            if not db_goal:
                raise HTTPException(status_code=404, detail="Goal not found")
            await session.delete(db_goal)
            await session.commit()
            return {"id": goal_id, "status": "deleted"}

    # ------------------------------------------------------------------
    # Agent Management API
    # ------------------------------------------------------------------

    @app.get("/api/agents", response_model=List[AgentStatusResponse])
    async def list_agents():
        agents = []
        for agent_id, runtime in app.state.agents.items():
            agents.append(
                AgentStatusResponse(
                    agent_id=agent_id,
                    registered=True,
                    paused=runtime.paused,
                    role=runtime.config.role,
                    company_id=runtime.config.company_id,
                )
            )
        return agents

    @app.get("/api/agents/{agent_id}", response_model=AgentStatusResponse)
    async def get_agent(agent_id: str):
        if agent_id not in app.state.agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        runtime = app.state.agents[agent_id]
        return AgentStatusResponse(
            agent_id=agent_id,
            registered=True,
            paused=runtime.paused,
            role=runtime.config.role,
            company_id=runtime.config.company_id,
        )

    @app.post("/api/agents/{agent_id}/pause")
    async def pause_agent(agent_id: str):
        if agent_id not in app.state.agents:
            # Auto-register if not present
            config = AgentConfig.from_env()
            config.agent_id = agent_id
            app.state.agents[agent_id] = AgentRuntime(config)
        runtime = app.state.agents[agent_id]
        runtime.pause()
        return {"agent_id": agent_id, "status": "paused"}

    @app.post("/api/agents/{agent_id}/resume")
    async def resume_agent(agent_id: str):
        if agent_id not in app.state.agents:
            config = AgentConfig.from_env()
            config.agent_id = agent_id
            app.state.agents[agent_id] = AgentRuntime(config)
        runtime = app.state.agents[agent_id]
        runtime.resume()
        return {"agent_id": agent_id, "status": "resumed"}

    @app.post("/api/agents/{agent_id}/register")
    async def register_agent(agent_id: str):
        """Register an agent runtime with the control plane."""
        config = AgentConfig.from_env()
        config.agent_id = agent_id
        runtime = AgentRuntime(config)
        app.state.agents[agent_id] = runtime
        return {"agent_id": agent_id, "status": "registered"}

    @app.post("/api/agents/{agent_id}/execute")
    async def execute_goal_direct(agent_id: str, req: CreateGoalRequest):
        """Execute a goal directly on a registered agent."""
        if agent_id not in app.state.agents:
            # Auto-register
            config = AgentConfig.from_env()
            config.agent_id = agent_id
            app.state.agents[agent_id] = AgentRuntime(config)

        runtime = app.state.agents[agent_id]
        goal = await runtime.submit_goal(req.description, req.context)

        # Persist goal and execution to database
        async with AsyncSessionLocal() as session:
            db_goal = GoalDB(
                id=uuid.UUID(goal.id),
                agent_id=goal.agent_id,
                company_id=goal.company_id,
                description=goal.description,
                context=goal.context,
                status=goal.status,
                created_at=goal.created_at,
            )
            session.add(db_goal)

            if runtime.current_execution:
                exec_obj = runtime.current_execution
                db_execution = GoalExecutionDB(
                    id=uuid.uuid4(),
                    goal_id=uuid.UUID(goal.id),
                    agent_id=agent_id,
                    status=exec_obj.status,
                    final_output=exec_obj.final_output,
                    trajectory=exec_obj.trajectory,
                    tool_calls=exec_obj.tool_calls,
                    token_usage=exec_obj.token_usage,
                    created_at=exec_obj.started_at or goal.created_at,
                    completed_at=exec_obj.completed_at,
                )
                session.add(db_execution)

            await session.commit()

        return {
            "goal_id": goal.id,
            "status": "completed" if runtime.current_execution and runtime.current_execution.status == "completed" else "failed",
            "output": runtime.current_execution.final_output if runtime.current_execution else "",
        }

    @app.websocket("/ws/agents/{agent_id}")
    async def agent_websocket(websocket: WebSocket, agent_id: str):
        await manager.connect(websocket, agent_id)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "intervene":
                    # Handle user intervention
                    await manager.send_to_agent(
                        agent_id,
                        {"type": "intervention_received", "message": data.get("message")}
                    )
        except WebSocketDisconnect:
            manager.disconnect(websocket, agent_id)

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
