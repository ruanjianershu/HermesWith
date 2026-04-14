"""Integration tests for the HermesWith Control Plane Goal API."""

import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hermeswith.control_plane.api import create_app
from hermeswith.persistence.database import Base, async_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_db_session():
    """Provide a mocked async DB session context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    # Default scalar_one_or_none to return None
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    result_mock.scalars.return_value.all.return_value = []
    session.execute.return_value = result_mock

    return session


@pytest.fixture(scope="function")
def mock_async_session_local(mock_db_session):
    """Patch AsyncSessionLocal to yield the mock session."""
    with patch("hermeswith.control_plane.api.AsyncSessionLocal") as mock:
        async_cm = AsyncMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_db_session)
        async_cm.__aexit__ = AsyncMock(return_value=False)
        mock.return_value = async_cm
        yield mock


@pytest.fixture(scope="function")
def mock_redis_queue():
    """Provide a mocked RedisGoalQueue."""
    queue = AsyncMock()
    queue.push = AsyncMock()
    queue.pull = AsyncMock(return_value=None)
    queue.list_pending = AsyncMock(return_value=[])
    queue.remove = AsyncMock(return_value=False)
    return queue


@pytest.fixture(scope="function")
def test_client(mock_async_session_local, mock_redis_queue):
    """Create a TestClient with mocked dependencies."""
    app = create_app()
    app.state.goal_queue = mock_redis_queue

    # Clear in-memory agents between tests
    app.state.agents = {}

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
async def async_client(mock_async_session_local, mock_redis_queue):
    """Create an AsyncClient with mocked dependencies."""
    app = create_app()
    app.state.goal_queue = mock_redis_queue
    app.state.agents = {}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Health Endpoint Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, test_client):
        """Test health check returns 200 and status ok."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Goal API Tests
# ---------------------------------------------------------------------------

class TestCreateGoal:
    """Tests for POST /api/companies/{company_id}/goals"""

    def test_create_goal_success(self, test_client, mock_db_session, mock_redis_queue):
        """Test creating a goal succeeds."""
        response = test_client.post(
            "/api/companies/acme/goals",
            json={
                "agent_id": "agent-1",
                "description": "Test goal",
                "context": {"priority": "high"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-1"
        assert data["company_id"] == "acme"
        assert data["description"] == "Test goal"
        assert data["status"] == "pending"
        assert "id" in data

        # Verify DB session and Redis queue were called
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_redis_queue.push.assert_called_once()

    def test_create_goal_minimal(self, test_client, mock_db_session, mock_redis_queue):
        """Test creating a goal with minimal fields."""
        response = test_client.post(
            "/api/companies/demo/goals",
            json={
                "agent_id": "agent-2",
                "description": "Simple task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Simple task"
        assert data["context"] == {}  # Default empty dict

    def test_create_goal_invalid_json(self, test_client):
        """Test creating a goal with invalid JSON fails."""
        response = test_client.post(
            "/api/companies/demo/goals",
            data="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_create_goal_missing_agent_id(self, test_client):
        """Test creating a goal without agent_id fails validation."""
        response = test_client.post(
            "/api/companies/demo/goals",
            json={"description": "Test goal"},
        )

        assert response.status_code == 422

    def test_create_goal_missing_description(self, test_client):
        """Test creating a goal without description fails validation."""
        response = test_client.post(
            "/api/companies/demo/goals",
            json={"agent_id": "agent-1"},
        )

        assert response.status_code == 422


class TestGetGoal:
    """Tests for GET /api/goals/{goal_id}"""

    def test_get_goal_success(self, test_client, mock_db_session):
        """Test retrieving a goal by ID."""
        goal_id = str(uuid.uuid4())

        # Mock the DB result
        db_goal = MagicMock()
        db_goal.id = uuid.UUID(goal_id)
        db_goal.agent_id = "agent-1"
        db_goal.company_id = "acme"
        db_goal.description = "Found goal"
        db_goal.status = "pending"
        db_goal.context = {"key": "value"}
        db_goal.created_at = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = db_goal
        mock_db_session.execute.return_value = result_mock

        response = test_client.get(f"/api/goals/{goal_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == goal_id
        assert data["description"] == "Found goal"
        assert data["context"] == {"key": "value"}

    def test_get_goal_not_found(self, test_client, mock_db_session):
        """Test retrieving a non-existent goal returns 404."""
        goal_id = str(uuid.uuid4())

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = result_mock

        response = test_client.get(f"/api/goals/{goal_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Goal not found"

    def test_get_goal_invalid_uuid(self, test_client):
        """Test retrieving a goal with invalid UUID format."""
        response = test_client.get("/api/goals/not-a-uuid")

        # Should fail UUID parsing
        assert response.status_code == 422


class TestListGoals:
    """Tests for GET /api/goals"""

    def test_list_goals_empty(self, test_client):
        """Test listing goals when none exist."""
        response = test_client.get("/api/goals")

        assert response.status_code == 200
        data = response.json()
        assert data["goals"] == []
        assert data["total"] == 0

    def test_list_goals_with_results(self, test_client, mock_db_session):
        """Test listing goals with filters."""
        db_goal1 = MagicMock()
        db_goal1.id = uuid.uuid4()
        db_goal1.agent_id = "agent-1"
        db_goal1.company_id = "demo"
        db_goal1.description = "Goal 1"
        db_goal1.status = "pending"
        db_goal1.context = {}
        db_goal1.created_at = None

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [db_goal1]
        mock_db_session.execute.return_value = result_mock

        response = test_client.get("/api/goals?agent_id=agent-1&status=pending&skip=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["goals"]) == 1
        assert data["goals"][0]["agent_id"] == "agent-1"

    def test_list_goals_pagination(self, test_client):
        """Test listing goals with pagination parameters."""
        response = test_client.get("/api/goals?skip=10&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 10
        assert data["limit"] == 5

    def test_list_goals_limit_validation(self, test_client):
        """Test limit parameter validation."""
        response = test_client.get("/api/goals?limit=1000")
        assert response.status_code == 422  # max is 500

        response = test_client.get("/api/goals?limit=0")
        assert response.status_code == 422  # min is 1


class TestDeleteGoal:
    """Tests for DELETE /api/goals/{goal_id}"""

    def test_delete_goal_success(self, test_client, mock_db_session):
        """Test deleting a goal succeeds."""
        goal_id = str(uuid.uuid4())

        db_goal = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = db_goal
        mock_db_session.execute.return_value = result_mock

        response = test_client.delete(f"/api/goals/{goal_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        mock_db_session.delete.assert_called_once_with(db_goal)
        mock_db_session.commit.assert_called_once()

    def test_delete_goal_not_found(self, test_client, mock_db_session):
        """Test deleting a non-existent goal returns 404."""
        goal_id = str(uuid.uuid4())

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = result_mock

        response = test_client.delete(f"/api/goals/{goal_id}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Agent Management API Tests
# ---------------------------------------------------------------------------

class TestAgentManagement:
    """Tests for agent management endpoints."""

    def test_list_agents_empty(self, test_client):
        """Test listing agents when none are registered."""
        response = test_client.get("/api/agents")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_agent_not_found(self, test_client):
        """Test getting a non-existent agent returns 404."""
        response = test_client.get("/api/agents/nonexistent")

        assert response.status_code == 404

    @patch("hermeswith.control_plane.api.AgentRuntime")
    @patch("hermeswith.control_plane.api.AgentConfig.from_env")
    def test_pause_agent_registers_if_missing(self, mock_from_env, mock_runtime_cls, test_client):
        """Test pausing an unregistered agent auto-registers it."""
        mock_config = MagicMock()
        mock_config.agent_id = "new-agent"
        mock_from_env.return_value = mock_config

        mock_runtime = MagicMock()
        mock_runtime.paused = True
        mock_runtime.config.role = "assistant"
        mock_runtime.config.company_id = "default"
        mock_runtime_cls.return_value = mock_runtime

        response = test_client.post("/api/agents/new-agent/pause")

        assert response.status_code == 200
        assert response.json()["status"] == "paused"
        mock_runtime_cls.assert_called_once_with(mock_config)
        mock_runtime.pause.assert_called_once()

    @patch("hermeswith.control_plane.api.AgentRuntime")
    @patch("hermeswith.control_plane.api.AgentConfig.from_env")
    def test_resume_agent(self, mock_from_env, mock_runtime_cls, test_client):
        """Test resuming a paused agent."""
        mock_config = MagicMock()
        mock_from_env.return_value = mock_config

        mock_runtime = MagicMock()
        mock_runtime.paused = False
        mock_runtime.config.role = "worker"
        mock_runtime.config.company_id = "demo"
        mock_runtime_cls.return_value = mock_runtime

        response = test_client.post("/api/agents/worker-1/resume")

        assert response.status_code == 200
        assert response.json()["status"] == "resumed"
        mock_runtime.resume.assert_called_once()

    @patch("hermeswith.control_plane.api.AgentRuntime")
    @patch("hermeswith.control_plane.api.AgentConfig.from_env")
    def test_register_agent(self, mock_from_env, mock_runtime_cls, test_client):
        """Test registering an agent."""
        mock_config = MagicMock()
        mock_from_env.return_value = mock_config

        mock_runtime = MagicMock()
        mock_runtime_cls.return_value = mock_runtime

        response = test_client.post("/api/agents/test-agent/register")

        assert response.status_code == 200
        assert response.json()["status"] == "registered"

    @patch("hermeswith.control_plane.api.AgentRuntime")
    @patch("hermeswith.control_plane.api.AgentConfig.from_env")
    def test_execute_goal_direct(self, mock_from_env, mock_runtime_cls, test_client, mock_db_session):
        """Test direct goal execution on an agent."""
        mock_config = MagicMock()
        mock_from_env.return_value = mock_config

        mock_execution = MagicMock()
        mock_execution.status = "completed"
        mock_execution.final_output = "Done!"
        mock_execution.started_at = None
        mock_execution.completed_at = None
        mock_execution.trajectory = []
        mock_execution.tool_calls = []
        mock_execution.token_usage = 0

        mock_runtime = AsyncMock()
        mock_runtime.current_execution = mock_execution
        mock_runtime.config.role = "worker"
        mock_runtime.config.company_id = "demo"

        # Mock the goal returned by submit_goal
        from hermeswith.runtime.agent_runtime import Goal
        goal = Goal(
            id=str(uuid.uuid4()),
            agent_id="exec-agent",
            company_id="demo",
            description="Execute this",
            context={},
            status="pending",
        )
        mock_runtime.submit_goal = AsyncMock(return_value=goal)
        mock_runtime_cls.return_value = mock_runtime

        response = test_client.post(
            "/api/agents/exec-agent/execute",
            json={
                "agent_id": "exec-agent",
                "description": "Execute this",
                "context": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["output"] == "Done!"
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# WebSocket Tests
# ---------------------------------------------------------------------------

class TestWebSocket:
    """Tests for WebSocket endpoint."""

    def test_websocket_connect_and_disconnect(self, test_client):
        """Test WebSocket connection lifecycle."""
        with test_client.websocket_connect("/ws/agents/test-agent") as websocket:
            pass  # Connect and disconnect

    def test_websocket_intervention(self, test_client):
        """Test WebSocket intervention message handling."""
        with test_client.websocket_connect("/ws/agents/test-agent") as websocket:
            websocket.send_json({"type": "intervene", "message": "Stop please"})
            # Since the response is sent back to the same connection, we receive it
            data = websocket.receive_json()
            assert data["type"] == "intervention_received"
            assert data["message"] == "Stop please"


# ---------------------------------------------------------------------------
# Async Client Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsyncAPI:
    """Async integration tests using AsyncClient."""

    async def test_health_async(self, async_client):
        """Async health check test."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_create_goal_async(self, async_client, mock_db_session, mock_redis_queue):
        """Async goal creation test."""
        response = await async_client.post(
            "/api/companies/demo/goals",
            json={
                "agent_id": "async-agent",
                "description": "Async task",
                "context": {"async": True},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "async-agent"
        assert data["description"] == "Async task"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
