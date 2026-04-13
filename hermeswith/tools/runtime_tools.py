"""HermesWith runtime-specific tools.

Registers tools used by the AgentRuntime:
- goal_complete: mark a goal as completed
- ask_user: ask the user a clarifying question
"""

from tools.registry import registry, tool_result


# ---------------------------------------------------------------------------
# goal_complete
# ---------------------------------------------------------------------------

def _handle_goal_complete(args: dict) -> str:
    goal_id = args.get("goal_id", "unknown")
    summary = args.get("summary", "")
    return tool_result(
        success=True,
        message=f"Goal {goal_id} marked as complete.",
        summary=summary,
    )


GOAL_COMPLETE_SCHEMA = {
    "name": "goal_complete",
    "description": "Mark the current goal as completed and provide a final summary.",
    "parameters": {
        "type": "object",
        "properties": {
            "goal_id": {
                "type": "string",
                "description": "The ID of the goal being completed.",
            },
            "summary": {
                "type": "string",
                "description": "Final summary of what was accomplished.",
            },
        },
        "required": ["summary"],
    },
}


# ---------------------------------------------------------------------------
# ask_user
# ---------------------------------------------------------------------------

def _handle_ask_user(args: dict) -> str:
    question = args.get("question", "")
    return tool_result(
        success=True,
        message="Question delivered to user (mock WebSocket).",
        question=question,
        answer="(awaiting user response)",
    )


ASK_USER_SCHEMA = {
    "name": "ask_user",
    "description": "Ask the user a clarifying question via WebSocket.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user.",
            },
        },
        "required": ["question"],
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="goal_complete",
    toolset="hermeswith-runtime",
    schema=GOAL_COMPLETE_SCHEMA,
    handler=_handle_goal_complete,
    description="Mark the current goal as completed.",
    emoji="✅",
)

registry.register(
    name="ask_user",
    toolset="hermeswith-runtime",
    schema=ASK_USER_SCHEMA,
    handler=_handle_ask_user,
    description="Ask the user a clarifying question.",
    emoji="❓",
)
