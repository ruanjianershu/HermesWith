"""
Control Plane API - FastAPI application for managing goals and agents.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from hermeswith.runtime import AgentConfig, AgentRuntime


class CreateGoalRequest(BaseModel):
    agent_id: str
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)


class GoalResponse(BaseModel):
    id: str
    agent_id: str
    description: str
    status: str


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
    # Startup
    print("🎛️  Control Plane starting...")
    yield
    # Shutdown
    print("🎛️  Control Plane shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(title="HermesWith Control Plane", version="0.1.0", lifespan=lifespan)
    
    # In-memory storage for MVP
    app.state.goals: Dict[str, dict] = {}
    app.state.agents: Dict[str, AgentRuntime] = {}
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}
    
    @app.post("/api/companies/{company_id}/goals", response_model=GoalResponse)
    async def create_goal(company_id: str, req: CreateGoalRequest):
        from hermeswith.runtime.agent_runtime import Goal
        
        goal = Goal(
            agent_id=req.agent_id,
            company_id=company_id,
            description=req.description,
            context=req.context,
        )
        app.state.goals[goal.id] = {
            "id": goal.id,
            "agent_id": goal.agent_id,
            "company_id": goal.company_id,
            "description": goal.description,
            "status": goal.status,
            "context": goal.context,
        }
        
        # TODO: Push to Redis queue
        return GoalResponse(
            id=goal.id,
            agent_id=goal.agent_id,
            description=goal.description,
            status=goal.status,
        )
    
    @app.get("/api/goals/{goal_id}")
    async def get_goal(goal_id: str):
        if goal_id not in app.state.goals:
            return {"error": "Goal not found"}, 404
        return app.state.goals[goal_id]
    
    @app.get("/api/goals")
    async def list_goals(agent_id: Optional[str] = None):
        goals = list(app.state.goals.values())
        if agent_id:
            goals = [g for g in goals if g["agent_id"] == agent_id]
        return {"goals": goals, "total": len(goals)}
    
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
