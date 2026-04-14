"""Unit tests for AgentRuntime class."""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pydantic import ValidationError

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hermeswith.runtime.agent_runtime import AgentConfig, AgentRuntime, Goal, GoalExecution


class TestGoal:
    """Tests for the Goal model."""

    def test_goal_creation_defaults(self):
        """Test Goal creation with default values."""
        goal = Goal(agent_id="test-agent", company_id="test-co", description="Test goal")

        assert goal.agent_id == "test-agent"
        assert goal.company_id == "test-co"
        assert goal.description == "Test goal"
        assert goal.status == "pending"
        assert isinstance(goal.id, str)
        assert uuid.UUID(goal.id)  # Valid UUID
        assert isinstance(goal.created_at, datetime)
        assert goal.context == {}

    def test_goal_creation_with_context(self):
        """Test Goal creation with custom context."""
        context = {"key": "value", "number": 42}
        goal = Goal(
            agent_id="agent-1",
            company_id="company-1",
            description="Do something",
            context=context,
            status="executing",
        )

        assert goal.context == context
        assert goal.status == "executing"

    def test_goal_serialization(self):
        """Test Goal can be serialized to dict and JSON."""
        goal = Goal(agent_id="a", company_id="c", description="test")
        data = goal.model_dump()

        assert data["agent_id"] == "a"
        assert data["company_id"] == "c"
        assert data["description"] == "test"

        # Test JSON serialization
        json_str = goal.model_dump_json()
        assert isinstance(json_str, str)
        assert "test" in json_str


class TestGoalExecution:
    """Tests for the GoalExecution model."""

    def test_execution_creation(self):
        """Test GoalExecution creation."""
        execution = GoalExecution(goal_id="g-1", agent_id="a-1")

        assert execution.goal_id == "g-1"
        assert execution.agent_id == "a-1"
        assert execution.status == "pending"
        assert execution.final_output == ""
        assert execution.trajectory == []
        assert execution.tool_calls == []
        assert execution.token_usage == 0
        assert execution.error is None

    def test_execution_with_trajectory(self):
        """Test GoalExecution with trajectory data."""
        trajectory = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        execution = GoalExecution(
            goal_id="g-1",
            agent_id="a-1",
            trajectory=trajectory,
            final_output="Completed",
            status="completed",
            token_usage=150,
        )

        assert len(execution.trajectory) == 2
        assert execution.final_output == "Completed"
        assert execution.status == "completed"
        assert execution.token_usage == 150


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_config_defaults(self):
        """Test AgentConfig with default values."""
        config = AgentConfig(agent_id="test-agent")

        assert config.agent_id == "test-agent"
        assert config.company_id == "default"
        assert config.role == "assistant"
        assert config.model == "kimi-k2.5"
        assert config.toolsets == ["terminal", "file"]
        assert config.max_iterations == 20

    def test_config_custom_values(self):
        """Test AgentConfig with custom values."""
        config = AgentConfig(
            agent_id="custom-agent",
            company_id="acme-corp",
            role="researcher",
            model="gpt-4",
            toolsets=["web", "code"],
            max_iterations=50,
        )

        assert config.agent_id == "custom-agent"
        assert config.company_id == "acme-corp"
        assert config.role == "researcher"
        assert config.model == "gpt-4"
        assert config.toolsets == ["web", "code"]
        assert config.max_iterations == 50

    @patch.dict(os.environ, {"AGENT_ID": "env-agent", "COMPANY_ID": "env-corp"}, clear=False)
    def test_config_from_env(self):
        """Test AgentConfig loads from environment variables."""
        config = AgentConfig.from_env()

        assert config.agent_id == "env-agent"
        assert config.company_id == "env-corp"

    @patch.dict(
        os.environ,
        {
            "AGENT_ID": "api-agent",
            "AGENT_API_KEY": "secret-key",
            "KIMI_API_KEY": "fallback-key",
        },
        clear=True,
    )
    def test_config_api_key_precedence(self):
        """Test that AGENT_API_KEY takes precedence over KIMI_API_KEY."""
        config = AgentConfig.from_env()

        assert config.agent_id == "api-agent"
        assert config.api_key == "secret-key"

    @patch.dict(os.environ, {"AGENT_TOOLSETS": "web,code,analysis"}, clear=False)
    def test_config_toolsets_from_env(self):
        """Test toolsets are parsed from comma-separated env variable."""
        config = AgentConfig.from_env()

        assert config.toolsets == ["web", "code", "analysis"]


class TestAgentRuntime:
    """Tests for AgentRuntime."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AgentConfig."""
        return AgentConfig(
            agent_id="test-agent",
            company_id="test-co",
            role="tester",
            model="test-model",
            api_key="test-key",
            toolsets=[],
        )

    @pytest.fixture
    def runtime(self, mock_config):
        """Create an AgentRuntime instance with mocked dependencies."""
        with patch.object(AgentRuntime, "_init_hermes_agent"):
            runtime = AgentRuntime(mock_config)
            runtime._has_hermes = False  # Simulate no Hermes available
            runtime.agent = None
            return runtime

    def test_runtime_initialization(self, mock_config):
        """Test AgentRuntime initialization."""
        with patch.object(AgentRuntime, "_init_hermes_agent"):
            runtime = AgentRuntime(mock_config)

            assert runtime.config == mock_config
            assert runtime.agent_id == "test-agent"
            assert runtime.company_id == "test-co"
            assert runtime.paused is False
            assert runtime.current_execution is None

    def test_pause_resume(self, runtime):
        """Test pause and resume functionality."""
        assert runtime.paused is False

        runtime.pause()
        assert runtime.paused is True

        runtime.resume()
        assert runtime.paused is False

    @pytest.mark.asyncio
    async def test_submit_goal_when_paused(self, runtime):
        """Test that submit_goal raises error when paused."""
        runtime.pause()

        with pytest.raises(RuntimeError, match="is paused"):
            await runtime.submit_goal("Test goal")

    @pytest.mark.asyncio
    async def test_submit_goal_mock_execution(self, runtime):
        """Test submit_goal with mock execution."""
        with patch.object(runtime, "_execute_goal") as mock_execute:
            mock_execute.return_value = None

            goal = await runtime.submit_goal("Test goal description", context={"test": True})

            assert goal.agent_id == "test-agent"
            assert goal.company_id == "test-co"
            assert goal.description == "Test goal description"
            assert goal.context == {"test": True}
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_goal_mock_mode(self, runtime):
        """Test _execute_goal in mock mode (no Hermes)."""
        goal = Goal(
            agent_id="test-agent",
            company_id="test-co",
            description="Mock test goal",
        )

        with patch.object(runtime, "_notify") as mock_notify:
            with patch.object(runtime, "_save_execution") as mock_save:
                await runtime._execute_goal(goal)

                assert runtime.current_execution is not None
                assert runtime.current_execution.status == "completed"
                assert "Mock result for: Mock test goal" in runtime.current_execution.final_output
                assert mock_notify.call_count == 2  # goal_started + goal_completed
                mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_goal_failure_handling(self, runtime):
        """Test that _execute_goal handles failures gracefully."""
        goal = Goal(
            agent_id="test-agent",
            company_id="test-co",
            description="Failing goal",
        )

        # Force an error in execution
        async def mock_execute_mock(goal):
            raise Exception("Simulated error")

        runtime._execute_mock = mock_execute_mock

        with patch.object(runtime, "_notify") as mock_notify:
            with patch.object(runtime, "_save_execution") as mock_save:
                await runtime._execute_goal(goal)

                assert runtime.current_execution.status == "failed"
                assert "Simulated error" in runtime.current_execution.error
                assert mock_notify.call_count == 2  # goal_started + goal_failed
                mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_system_prompt(self, runtime):
        """Test system prompt generation."""
        prompt = runtime._build_system_prompt()

        assert "test-agent" in prompt
        assert "test-co" in prompt
        assert "tester" in prompt
        assert "Available tools:" in prompt

    @pytest.mark.asyncio
    async def test_build_goal_message(self, runtime):
        """Test goal message building."""
        goal = Goal(
            agent_id="test-agent",
            company_id="test-co",
            description="Do something important",
            context={"priority": "high", "deadline": "tomorrow"},
        )

        message = runtime._build_goal_message(goal)

        assert "Goal: Do something important" in message
        assert "Additional context:" in message
        assert "priority" in message
        assert "deadline" in message

    def test_build_goal_message_no_context(self, runtime):
        """Test goal message building without context."""
        goal = Goal(
            agent_id="test-agent",
            company_id="test-co",
            description="Simple task",
        )

        message = runtime._build_goal_message(goal)

        assert message == "Goal: Simple task"
        assert "Additional context" not in message

    @pytest.mark.asyncio
    async def test_save_execution(self, runtime):
        """Test execution saving (MVP just prints)."""
        execution = GoalExecution(
            goal_id="test-goal-id",
            agent_id="test-agent",
            status="completed",
        )

        # Just verify it doesn't raise an exception
        await runtime._save_execution(execution)

    @pytest.mark.asyncio
    async def test_handle_intervention_pause(self, runtime):
        """Test handling pause intervention."""
        intervention = {"type": "pause"}

        result = await runtime._handle_intervention(intervention)

        assert result is False
        assert runtime.paused is True

    @pytest.mark.asyncio
    async def test_handle_intervention_resume(self, runtime):
        """Test handling resume intervention."""
        runtime.pause()
        intervention = {"type": "resume"}

        result = await runtime._handle_intervention(intervention)

        assert result is True
        assert runtime.paused is False

    @pytest.mark.asyncio
    async def test_handle_intervention_cancel(self, runtime):
        """Test handling cancel intervention."""
        intervention = {"type": "cancel"}

        result = await runtime._handle_intervention(intervention)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_intervention_message(self, runtime):
        """Test handling message intervention."""
        intervention = {"type": "intervene", "message": "Please stop and reconsider"}

        result = await runtime._handle_intervention(intervention)

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_intervention_unknown(self, runtime):
        """Test handling unknown intervention type."""
        intervention = {"type": "unknown_action"}

        result = await runtime._handle_intervention(intervention)

        assert result is True  # Unknown types default to continue


class TestAgentRuntimeWithHermes:
    """Tests for AgentRuntime with mocked Hermes integration."""

    @pytest.fixture
    def mock_config(self):
        return AgentConfig(
            agent_id="hermes-agent",
            company_id="test-co",
            role="assistant",
            model="test-model",
        )

    @pytest.mark.asyncio
    async def test_execute_with_hermes(self, mock_config):
        """Test _execute_with_hermes method."""
        with patch.object(AgentRuntime, "_init_hermes_agent"):
            runtime = AgentRuntime(mock_config)
            runtime._has_hermes = True

            # Mock the Hermes agent
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {
                "final_response": "Task completed successfully",
                "messages": [{"role": "assistant", "content": "Done"}],
            }
            runtime.agent = mock_agent

            goal = Goal(
                agent_id="hermes-agent",
                company_id="test-co",
                description="Test with Hermes",
            )

            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = {
                    "final_response": "Task completed successfully",
                    "messages": [{"role": "assistant", "content": "Done"}],
                }

                result = await runtime._execute_with_hermes(goal)

                assert result["output"] == "Task completed successfully"
                assert len(result["trajectory"]) == 1


class TestAgentRuntimeMainLoop:
    """Tests for the main execution loop."""

    @pytest.fixture
    def mock_config(self):
        return AgentConfig(
            agent_id="loop-agent",
            company_id="test-co",
            toolsets=[],
        )

    @pytest.mark.asyncio
    async def test_pull_goal_returns_none(self, mock_config):
        """Test _pull_goal returns None when no goals available."""
        with patch.object(AgentRuntime, "_init_hermes_agent"):
            runtime = AgentRuntime(mock_config)

            result = await runtime._pull_goal()
            assert result is None

    @pytest.mark.asyncio
    async def test_main_loop_handles_errors(self, mock_config):
        """Test main loop continues after errors."""
        with patch.object(AgentRuntime, "_init_hermes_agent"):
            runtime = AgentRuntime(mock_config)

            call_count = 0

            async def mock_pull_goal():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Simulated error")
                # Stop the loop after error handling
                raise asyncio.CancelledError()

            runtime._pull_goal = mock_pull_goal

            with pytest.raises(asyncio.CancelledError):
                await runtime.run()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
