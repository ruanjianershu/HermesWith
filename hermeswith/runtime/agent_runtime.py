"""
AgentRuntime - The core execution engine for HermesWith.

Wraps Hermes AIAgent to execute Goals in a containerized environment.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add vendor hermes-agent to path
sys.path.insert(0, "/app/vendor/hermes-agent")

from pydantic import BaseModel, Field


class Goal(BaseModel):
    """A Goal is what needs to be achieved (not how)."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    company_id: str
    description: str  # Natural language description of what to achieve
    context: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending/planning/executing/completed/failed
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GoalExecution(BaseModel):
    """Record of how a Goal was executed."""
    
    goal_id: str
    agent_id: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    trajectory: List[Dict[str, Any]] = Field(default_factory=list)
    final_output: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: int = 0
    status: str = "pending"
    error: Optional[str] = None


class AgentRuntime:
    """
    Runtime environment for a single Agent.
    
    Each Agent runs in its own container with:
    - Hermes AIAgent for reasoning and tool use
    - PersistentMemory for long-term context
    - DockerSandbox for safe code execution
    - Connection to Control Plane via Redis and WebSocket
    """
    
    def __init__(self, config: "AgentConfig"):
        self.config = config
        self.agent_id = config.agent_id
        self.company_id = config.company_id
        
        # Initialize Hermes AIAgent
        self._init_hermes_agent()
        
        # Initialize connections (lazy load)
        self._redis = None
        self._ws_client = None
        self._intervention_queue = None
        
        # Track executions
        self.current_execution: Optional[GoalExecution] = None
        self.paused = False

    def pause(self):
        """Pause the agent - it will not accept new goals."""
        self.paused = True
        print(f"⏸️  Agent {self.agent_id} paused")

    def resume(self):
        """Resume the agent."""
        self.paused = False
        print(f"▶️  Agent {self.agent_id} resumed")

    async def _notify(self, message: Dict[str, Any]):
        """Broadcast a progress message via WebSocket."""
        if self._ws_client is None:
            from hermeswith.runtime.ws_client import WSClient
            self._ws_client = WSClient(self.agent_id)
            await self._ws_client.connect(self.config.control_plane_ws)
        await self._ws_client.send(message)

    async def _check_intervention(self, timeout: float = 0.5) -> Optional[Dict[str, Any]]:
        """Check for user intervention messages."""
        if self._intervention_queue is None:
            from hermeswith.runtime.intervention import InterventionQueue
            self._intervention_queue = InterventionQueue()
        return await self._intervention_queue.get(timeout=timeout)

    async def _handle_intervention(self, intervention: Dict[str, Any]) -> bool:
        """Process an intervention message. Returns True if goal should continue."""
        msg_type = intervention.get("type")
        if msg_type == "pause":
            self.pause()
            return False
        if msg_type == "resume":
            self.resume()
            return True
        if msg_type == "cancel":
            print("🛑 Goal cancelled by user")
            return False
        if msg_type == "intervene":
            # Store intervention text for injection into next LLM turn
            print(f"💬 User intervention: {intervention.get('message', '')}")
            return True
        return True

    def _init_hermes_agent(self):
        """Initialize the Hermes AIAgent."""
        try:
            # Import Hermes core (may not be available during MVP)
            from run_agent import AIAgent
            import model_tools

            # Explicitly discover tools to ensure registry is populated
            model_tools._discover_tools()

            # Register HermesWith runtime tools
            try:
                import hermeswith.tools.runtime_tools  # noqa: F401
            except Exception as e:
                print(f"⚠️  Failed to load runtime tools: {e}")

            self.agent = AIAgent(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                model=self.config.model,
                enabled_toolsets=self.config.toolsets,
                max_iterations=self.config.max_iterations,
                platform="hermeswith",
                save_trajectories=True,
                quiet_mode=True,  # Reduce noise in logs
            )

            # Expose tool registry for introspection
            self.agent.tool_registry = self.agent.tools or []
            self._has_hermes = True
            print(f"✅ Hermes AIAgent initialized: {self.config.model}")
        except ImportError as e:
            print(f"⚠️  Hermes AIAgent not available: {e}")
            self._has_hermes = False
            self.agent = None
        except Exception as e:
            print(f"❌ Failed to initialize AIAgent: {e}")
            self._has_hermes = False
            self.agent = None
    
    async def run(self):
        """Main loop: continuously pull and execute Goals."""
        print(f"🚀 AgentRuntime started for {self.agent_id}")
        print(f"   Model: {self.config.model}")
        print(f"   Toolsets: {self.config.toolsets}")
        
        while True:
            try:
                goal = await self._pull_goal()
                if goal:
                    await self._execute_goal(goal)
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    async def _pull_goal(self) -> Optional[Goal]:
        """Pull next Goal from Redis queue."""
        # MVP: mock implementation, read from file or return None
        # TODO: Implement Redis queue
        return None
    
    async def _execute_goal(self, goal: Goal):
        """Execute a single Goal."""
        print(f"\n📋 New Goal: {goal.description[:60]}...")
        
        # Notify goal started
        await self._notify({
            "type": "goal_started",
            "goal_id": goal.id,
            "agent_id": self.agent_id,
            "description": goal.description,
        })
        
        execution = GoalExecution(
            goal_id=goal.id,
            agent_id=self.agent_id,
            started_at=datetime.utcnow(),
            status="executing"
        )
        self.current_execution = execution
        
        try:
            if self._has_hermes and self.agent:
                # Use Hermes AIAgent
                result = await self._execute_with_hermes(goal)
            else:
                # Fallback: mock execution
                result = await self._execute_mock(goal)
            
            execution.final_output = result.get("output", "")
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            
            print(f"✅ Goal completed: {execution.final_output[:100]}...")
            
            # Notify goal completed
            await self._notify({
                "type": "goal_completed",
                "goal_id": goal.id,
                "agent_id": self.agent_id,
                "output": execution.final_output,
            })
            
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            print(f"❌ Goal failed: {e}")
            
            # Notify goal failed
            await self._notify({
                "type": "goal_failed",
                "goal_id": goal.id,
                "agent_id": self.agent_id,
                "error": str(e),
            })
        
        await self._save_execution(execution)
    
    async def _execute_with_hermes(self, goal: Goal) -> Dict[str, Any]:
        """Execute using Hermes AIAgent."""
        import asyncio
        
        # Build system prompt with role and memory
        system_prompt = self._build_system_prompt()
        
        # Build user message from Goal
        user_message = self._build_goal_message(goal)
        
        # Run Hermes conversation (run_conversation is synchronous)
        result = await asyncio.to_thread(
            self.agent.run_conversation,
            user_message=user_message,
            system_message=system_prompt,
            task_id=goal.id,
        )
        
        return {
            "output": result.get("final_response", ""),
            "trajectory": result.get("messages", []),
        }
    
    async def _execute_mock(self, goal: Goal) -> Dict[str, Any]:
        """Mock execution for MVP testing without Hermes."""
        print(f"🤖 Mock execution: {goal.description}")
        await asyncio.sleep(2)
        return {
            "output": f"Mock result for: {goal.description}",
        }
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with role definition and memories."""
        tools_str = "None"
        if self._has_hermes and self.agent and getattr(self.agent, "tool_registry", None):
            tools = [
                t["function"]["name"]
                for t in self.agent.tool_registry
                if isinstance(t, dict) and t.get("function", {}).get("name")
            ]
            tools_str = ", ".join(tools) if tools else "None"

        return f"""You are {self.agent_id}, a digital employee of company {self.company_id}.

Your role: {self.config.role}

Mission: Autonomously achieve assigned goals using available tools. You are a proactive agent, not a passive assistant.

Available tools: {tools_str}

Behavior guidelines:
1. Understand the goal before planning - read context carefully and ask for clarification only when truly necessary.
2. Use tools autonomously to achieve the goal - prefer action over explanation.
3. Self-correct when encountering errors - retry with adjusted parameters, try alternative tools, or revise your approach.
4. Provide clear deliverables - complete the task fully and call `goal_complete` with a concise summary when done.
5. Think step-by-step for complex tasks, but keep responses focused on results.
"""
    
    def _build_goal_message(self, goal: Goal) -> str:
        """Build user message from Goal."""
        context_str = ""
        if goal.context:
            context_str = f"\n\nAdditional context:\n{goal.context}"
        
        return f"Goal: {goal.description}{context_str}"
    
    async def _save_execution(self, execution: GoalExecution):
        """Save execution record."""
        # MVP: print to stdout, later: save to PostgreSQL
        print(f"💾 Execution saved: {execution.goal_id} -> {execution.status}")
    
    async def submit_goal(self, description: str, context: Optional[Dict] = None) -> Goal:
        """Submit a Goal directly (for testing)."""
        if self.paused:
            raise RuntimeError(f"Agent {self.agent_id} is paused")
        goal = Goal(
            agent_id=self.agent_id,
            company_id=self.company_id,
            description=description,
            context=context or {},
        )
        await self._execute_goal(goal)
        return goal


class AgentConfig(BaseModel):
    """Configuration for AgentRuntime."""
    
    agent_id: str
    company_id: str = "default"
    role: str = "assistant"
    model: str = "k2p5"
    base_url: str = "https://api.kimi.com/coding/v1"
    api_key: str = ""
    toolsets: List[str] = Field(default_factory=lambda: ["terminal", "file"])
    max_iterations: int = 20
    
    # Connections
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://user:pass@localhost/db"
    control_plane_ws: str = "ws://localhost:8000/ws"
    
    # Paths
    workspace_dir: str = "/workspace"
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "AgentConfig":
        """Create config from environment variables, optionally loading a .env file."""
        import dotenv

        # Determine .env file path: explicit arg -> project root -> CWD
        if env_file is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            for candidate in [os.path.join(project_root, ".env"), ".env"]:
                if os.path.isfile(candidate):
                    env_file = candidate
                    break

        if env_file and os.path.isfile(env_file):
            dotenv.load_dotenv(env_file, override=False)

        return cls(
            agent_id=os.getenv("AGENT_ID", "agent-001"),
            company_id=os.getenv("COMPANY_ID", "default"),
            role=os.getenv("AGENT_ROLE", "assistant"),
            model=os.getenv("AGENT_MODEL", "k2p5"),
            base_url=os.getenv("AGENT_BASE_URL", "https://api.kimi.com/coding/v1"),
            api_key=os.getenv("AGENT_API_KEY", os.getenv("KIMI_API_KEY", "")),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            control_plane_ws=os.getenv("CONTROL_PLANE_WS", "ws://localhost:8000/ws"),
            workspace_dir=os.getenv("WORKSPACE_DIR", "/workspace"),
            toolsets=os.getenv("AGENT_TOOLSETS", "terminal,file").split(","),
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "20")),
        )
