"""
HermesWith Runtime Tools

Custom tools registered for the HermesWith agent runtime.
These tools are discovered automatically when hermes-agent's
model_tools._discover_tools() runs and imports this module.
"""

import json
from typing import Any, Dict, Optional

# Ensure vendor hermes-agent is on path before importing registry
import sys
import os

_VENDOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "vendor",
    "hermes-agent",
)
if _VENDOR_PATH not in sys.path:
    sys.path.insert(0, _VENDOR_PATH)

from tools.registry import registry, tool_error


def goal_complete_tool(summary: str, status: str = "completed") -> str:
    """Mark the current goal as complete with a summary."""
    if not summary or not summary.strip():
        return tool_error("Summary is required to complete a goal.")
    return json.dumps({
        "status": status,
        "summary": summary.strip(),
        "message": "Goal marked as complete.",
    }, ensure_ascii=False)


def ask_user_tool(question: str, ws_client=None) -> str:
    """Ask the user a question via WebSocket (or fallback to queued message)."""
    if not question or not question.strip():
        return tool_error("Question text is required.")

    question = question.strip()

    # If a WebSocket client is provided, try to send the question
    if ws_client is not None:
        try:
            import asyncio
            message = {
                "type": "ask_user",
                "question": question,
            }
            # ws_client.send is async
            if asyncio.iscoroutinefunction(ws_client.send):
                # We are in an async context -- caller should await
                return json.dumps({
                    "question": question,
                    "sent": True,
                    "note": "Question sent via WebSocket. Awaiting user response.",
                }, ensure_ascii=False)
            else:
                ws_client.send(message)
                return json.dumps({
                    "question": question,
                    "sent": True,
                    "note": "Question sent via WebSocket. Awaiting user response.",
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "question": question,
                "sent": False,
                "error": str(e),
                "note": "Failed to send via WebSocket. Consider retrying.",
            }, ensure_ascii=False)

    # Fallback: no WS client available
    return json.dumps({
        "question": question,
        "sent": False,
        "note": "No WebSocket connection available. Question queued for later delivery.",
    }, ensure_ascii=False)


def delegate_to_agent_tool(
    target_agent_id: str,
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
    priority: str = "normal",
    ws_client=None,
) -> str:
    """Delegate a subtask to another agent in the system."""
    if not target_agent_id or not target_agent_id.strip():
        return tool_error("target_agent_id is required to delegate a task.")
    if not task_description or not task_description.strip():
        return tool_error("task_description is required to delegate a task.")

    target_agent_id = target_agent_id.strip()
    task_description = task_description.strip()
    context = context or {}

    delegation_message = {
        "type": "delegate",
        "target_agent_id": target_agent_id,
        "task_description": task_description,
        "context": context,
        "priority": priority,
    }

    # If a WebSocket client is provided, try to send the delegation request
    if ws_client is not None:
        try:
            import asyncio
            if asyncio.iscoroutinefunction(ws_client.send):
                return json.dumps({
                    "delegated": True,
                    "target_agent_id": target_agent_id,
                    "task_description": task_description,
                    "priority": priority,
                    "note": "Delegation request sent via WebSocket.",
                }, ensure_ascii=False)
            else:
                ws_client.send(delegation_message)
                return json.dumps({
                    "delegated": True,
                    "target_agent_id": target_agent_id,
                    "task_description": task_description,
                    "priority": priority,
                    "note": "Delegation request sent via WebSocket.",
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "delegated": False,
                "target_agent_id": target_agent_id,
                "error": str(e),
                "note": "Failed to send delegation via WebSocket. Task queued for later delivery.",
            }, ensure_ascii=False)

    # Fallback: queue for later delivery
    return json.dumps({
        "delegated": False,
        "target_agent_id": target_agent_id,
        "task_description": task_description,
        "priority": priority,
        "note": "No WebSocket connection available. Delegation queued for later delivery.",
    }, ensure_ascii=False)


def check_runtime_tools_requirements() -> bool:
    """Runtime tools have no external API dependencies."""
    return True


GOAL_COMPLETE_SCHEMA = {
    "name": "goal_complete",
    "description": (
        "Mark the current goal as successfully completed and provide a concise summary "
        "of what was accomplished. Call this tool when you have finished all required steps "
        "and produced the requested deliverable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A brief summary of the completed work and its outcome.",
            },
            "status": {
                "type": "string",
                "enum": ["completed", "partial"],
                "description": "Whether the goal was fully completed or only partially.",
            },
        },
        "required": ["summary"],
    },
}

ASK_USER_SCHEMA = {
    "name": "ask_user",
    "description": (
        "Ask the user a question when you need clarification, additional context, or a "
        "decision before proceeding. In a live deployment the question is sent over WebSocket; "
        "in testing it is queued for later review."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to present to the user.",
            },
        },
        "required": ["question"],
    },
}

DELEGATE_TO_AGENT_SCHEMA = {
    "name": "delegate_to_agent",
    "description": (
        "Delegate a subtask to another specialized agent in the system. "
        "Use this when a task requires expertise or capabilities that another agent possesses. "
        "Provide a clear task description and any relevant context so the target agent "
        "can proceed autonomously."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_agent_id": {
                "type": "string",
                "description": "The unique ID of the agent to delegate the task to.",
            },
            "task_description": {
                "type": "string",
                "description": "A clear, actionable description of the subtask to delegate.",
            },
            "context": {
                "type": "object",
                "description": "Optional additional context or constraints for the target agent.",
                "default": {},
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "Priority level of the delegated task.",
                "default": "normal",
            },
        },
        "required": ["target_agent_id", "task_description"],
    },
}


# Register tools under the hermeswith-runtime toolset
registry.register(
    name="goal_complete",
    toolset="hermeswith-runtime",
    schema=GOAL_COMPLETE_SCHEMA,
    handler=lambda args, **kw: goal_complete_tool(
        summary=args.get("summary", ""),
        status=args.get("status", "completed"),
    ),
    check_fn=check_runtime_tools_requirements,
    emoji="✅",
)

registry.register(
    name="ask_user",
    toolset="hermeswith-runtime",
    schema=ASK_USER_SCHEMA,
    handler=lambda args, **kw: ask_user_tool(
        question=args.get("question", ""),
        ws_client=kw.get("ws_client"),
    ),
    check_fn=check_runtime_tools_requirements,
    emoji="❓",
)

registry.register(
    name="delegate_to_agent",
    toolset="hermeswith-runtime",
    schema=DELEGATE_TO_AGENT_SCHEMA,
    handler=lambda args, **kw: delegate_to_agent_tool(
        target_agent_id=args.get("target_agent_id", ""),
        task_description=args.get("task_description", ""),
        context=args.get("context", {}),
        priority=args.get("priority", "normal"),
        ws_client=kw.get("ws_client"),
    ),
    check_fn=check_runtime_tools_requirements,
    emoji="📤",
)
