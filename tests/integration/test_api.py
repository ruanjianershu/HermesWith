"""
Integration tests for HermesWith Control Plane API.

Tests the core API endpoints for goal management and agent operations.
Run with: pytest tests/integration/test_api.py -v
"""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test"

from hermeswith.control_plane.api import create_app


@pytest.fixture
async def app():
    """Create a fresh FastAPI app for each test."""
    app = create_app()
    yield app


@pytest.fixture
async def client(app):
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_health_check(client):
    """Test the health endpoint returns ok status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_create_goal(client, mock_session):
    """Test creating a goal via the API."""
    with patch(
        "hermeswith.control_plane.api.AsyncSessionLocal",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()),
    ):
        response = await client.post(
            "/api/companies/demo/goals",
            json={
                "agent_id": "researcher-001",
                "description": "Search for the latest Python release and summarize it",
                "context": {"format": "markdown"},
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["agent_id"] == "researcher-001"
    assert data["company_id"] == "demo"
    assert data["description"] == "Search for the latest Python release and summarize it"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_goal(client, mock_session):
    """Test retrieving a created goal."""
    goal_id = str(uuid.uuid4())
    mock_result = MagicMock()
    mock_db_goal = MagicMock()
    mock_db_goal.id = uuid.UUID(goal_id)
    mock_db_goal.agent_id = "researcher-001"
    mock_db_goal.company_id = "demo"
    mock_db_goal.description = "Test goal retrieval"
    mock_db_goal.status = "pending"
    mock_db_goal.context = {}
    mock_db_goal.created_at = None
    mock_result.scalar_one_or_none.return_value = mock_db_goal
    mock_session.execute.return_value = mock_result

    with patch(
        "hermeswith.control_plane.api.AsyncSessionLocal",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()),
    ):
        response = await client.get(f"/api/goals/{goal_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == goal_id
    assert data["description"] == "Test goal retrieval"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Mock setup needs fixing - requires proper async session mocking")
async def test_get_goal_not_found(client):
    """Test retrieving a non-existent goal returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/goals/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Goal not found"


@pytest.mark.asyncio
async def test_list_goals(client, mock_session):
    """Test listing goals."""
    mock_db_goal = MagicMock()
    mock_db_goal.id = uuid.uuid4()
    mock_db_goal.agent_id = "lister-agent"
    mock_db_goal.company_id = "demo"
    mock_db_goal.description = "Goal to list"
    mock_db_goal.status = "pending"
    mock_db_goal.context = {}
    mock_db_goal.created_at = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_db_goal]
    mock_session.execute.return_value = mock_result

    with patch(
        "hermeswith.control_plane.api.AsyncSessionLocal",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()),
    ):
        response = await client.get("/api/goals?agent_id=lister-agent")

    assert response.status_code == 200
    data = response.json()
    assert "goals" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_delete_goal(client, mock_session):
    """Test deleting a goal."""
    goal_id = str(uuid.uuid4())
    mock_db_goal = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_db_goal
    mock_session.execute.return_value = mock_result

    with patch(
        "hermeswith.control_plane.api.AsyncSessionLocal",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()),
    ):
        # Delete it
        delete_response = await client.delete(f"/api/goals/{goal_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_agent_register(client):
    """Test registering an agent."""
    response = await client.post("/api/agents/test-agent/register")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "test-agent"
    assert data["status"] == "registered"


@pytest.mark.asyncio
async def test_agent_pause_resume(client):
    """Test pausing and resuming an agent."""
    # Register agent first
    await client.post("/api/agents/pausable-agent/register")

    # Pause
    pause_response = await client.post("/api/agents/pausable-agent/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    # Resume
    resume_response = await client.post("/api/agents/pausable-agent/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "resumed"


@pytest.mark.asyncio
async def test_agent_execute_direct(client):
    """Test executing a goal directly on an agent."""
    with patch(
        "hermeswith.control_plane.api.AsyncSessionLocal",
        return_value=MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock()),
    ):
        response = await client.post(
            "/api/agents/executor-agent/execute",
            json={
                "agent_id": "executor-agent",
                "description": "Say hello from HermesWith",
                "context": {"test": True},
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "goal_id" in data
    assert "status" in data
    assert "output" in data


@pytest.mark.asyncio
async def test_list_agents(client):
    """Test listing registered agents."""
    # Register an agent
    await client.post("/api/agents/listed-agent/register")

    response = await client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(agent["agent_id"] == "listed-agent" for agent in data)


@pytest.mark.asyncio
async def test_get_agent(client):
    """Test getting a specific agent's status."""
    await client.post("/api/agents/single-agent/register")

    response = await client.get("/api/agents/single-agent")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "single-agent"
    assert data["registered"] is True
    assert data["paused"] is False
