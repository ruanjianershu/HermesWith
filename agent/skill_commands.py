"""Shared slash command helpers for skills and built-in prompt-style modes.

Shared between CLI (cli.py) and gateway (gateway/run.py) so both surfaces
can invoke skills via /skill-name commands and prompt-only built-ins like
/plan.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import display_hermes_home

logger = logging.getLogger(__name__)

_skill_commands: Dict[str, Dict[str, Any]] = {}
_PLAN_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Patterns for sanitizing skill names into clean hyphen-separated slugs.
_SKILL_INVALID_CHARS = re.compile(r"[^a-z0-9-]")
_SKILL_MULTI_HYPHEN = re.compile(r"-{2,}")


def build_plan_path(
    user_instruction: str = "",
    *,
    now: datetime | None = None,
) -> Path:
    """Return the default workspace-relative markdown path for a /plan invocation.

    Relative paths are intentional: file tools are task/backend-aware and resolve
    them against the active working directory for local, docker, ssh, modal,
    daytona, and similar terminal backends. That keeps the plan with the active
    workspace instead of the Hermes host's global home directory.
    """
    slug_source = (user_instruction or "").strip().splitlines()[0] if user_instruction else ""
    slug = _PLAN_SLUG_RE.sub("-", slug_source.lower()).strip("-")
    if slug:
        slug = "-".join(part for part in slug.split("-")[:8] if part)[:48].strip("-")
    slug = slug or "conversation-plan"
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return Path(".hermes") / "plans" / f"{timestamp}-{slug}.md"


def _load_skill_payload(skill_identifier: str, task_id: str | None = None) -> tuple[dict[str, Any], Path | None, str] | None:
    """Load a skill by name/path and return (loaded_payload, skill_dir, display_name)."""
    raw_identifier = (skill_identifier or "").strip()
    if not raw_identifier:
        return None

    try:
        from tools.skills_tool import SKILLS_DIR, skill_view

        identifier_path = Path(raw_identifier).expanduser()
        if identifier_path.is_absolute():
            try:
                normalized = str(identifier_path.resolve().relative_to(SKILLS_DIR.resolve()))
            except Exception:
                normalized = raw_identifier
        else:
            normalized = raw_identifier.lstrip("/")

        loaded_skill = json.loads(skill_view(normalized, task_id=task_id))
    except Exception:
        return None

    if not loaded_skill.get("success"):
        return None

    skill_name = str(loaded_skill.get("name") or normalized)
    skill_path = str(loaded_skill.get("path") or "")
    skill_dir = None
    # Prefer the absolute skill_dir returned by skill_view() — this is
    # correct for both local and external skills.  Fall back to the old
    # SKILLS_DIR-relative reconstruction only when skill_dir is absent
    # (e.g. legacy skill_view responses).
    abs_skill_dir = loaded_skill.get("skill_dir")
    if abs_skill_dir:
        skill_dir = Path(abs_skill_dir)
    elif skill_path:
        try:
            skill_dir = SKILLS_DIR / Path(skill_path).parent
        except Exception:
            skill_dir = None

    return loaded_skill, skill_dir, skill_name


def _inject_skill_config(loaded_skill: dict[str, Any], parts: list[str]) -> None:
    """Resolve and inject skill-declared config values into the message parts.

    If the loaded skill's frontmatter declares ``metadata.hermes.config``
    entries, their current values (from config.yaml or defaults) are appended
    as a ``[Skill config: ...]`` block so the agent knows the configured values
    without needing to read config.yaml itself.
    """
    try:
        from agent.skill_utils import (
            extract_skill_config_vars,
            parse_frontmatter,
            resolve_skill_config_values,
        )

        # The loaded_skill dict contains the raw content which includes frontmatter
        raw_content = str(loaded_skill.get("raw_content") or loaded_skill.get("content") or "")
        if not raw_content:
            return

        frontmatter, _ = parse_frontmatter(raw_content)
        config_vars = extract_skill_config_vars(frontmatter)
        if not config_vars:
            return

        resolved = resolve_skill_config_values(config_vars)
        if not resolved:
            return

        lines = ["", f"[Skill config (from {display_hermes_home()}/config.yaml):"]
        for key, value in resolved.items():
            display_val = str(value) if value else "(not set)"
            lines.append(f"  {key} = {display_val}")
        lines.append("]")
        parts.extend(lines)
    except Exception:
        pass  # Non-critical — skill still loads without config injection


def _build_skill_message(
    loaded_skill: dict[str, Any],
    skill_dir: Path | None,
    activation_note: str,
    user_instruction: str = "",
    runtime_note: str = "",
) -> str:
    """Format a loaded skill into a user/system message payload."""
    from tools.skills_tool import SKILLS_DIR

    content = str(loaded_skill.get("content") or "")

    parts = [activation_note, "", content.strip()]

    # ── Inject resolved skill config values ──
    _inject_skill_config(loaded_skill, parts)

    if loaded_skill.get("setup_skipped"):
        parts.extend(
            [
                "",
                "[Skill setup note: Required environment setup was skipped. Continue loading the skill and explain any reduced functionality if it matters.]",
            ]
        )
    elif loaded_skill.get("gateway_setup_hint"):
        parts.extend(
            [
                "",
                f"[Skill setup note: {loaded_skill['gateway_setup_hint']}]",
            ]
        )
    elif loaded_skill.get("setup_needed") and loaded_skill.get("setup_note"):
        parts.extend(
            [
                "",
                f"[Skill setup note: {loaded_skill['setup_note']}]",
            ]
        )

    supporting = []
    linked_files = loaded_skill.get("linked_files") or {}
    for entries in linked_files.values():
        if isinstance(entries, list):
            supporting.extend(entries)

    if not supporting and skill_dir:
        for subdir in ("references", "templates", "scripts", "assets"):
            subdir_path = skill_dir / subdir
            if subdir_path.exists():
                for f in sorted(subdir_path.rglob("*")):
                    if f.is_file() and not f.is_symlink():
                        rel = str(f.relative_to(skill_dir))
                        supporting.append(rel)

    if supporting and skill_dir:
        try:
            skill_view_target = str(skill_dir.relative_to(SKILLS_DIR))
        except ValueError:
            # Skill is from an external dir — use the skill name instead
            skill_view_target = skill_dir.name
        parts.append("")
        parts.append("[This skill has supporting files you can load with the skill_view tool:]")
        for sf in supporting:
            parts.append(f"- {sf}")
        parts.append(
            f'\nTo view any of these, use: skill_view(name="{skill_view_target}", file_path="<path>")'
        )

    if user_instruction:
        parts.append("")
        parts.append(f"The user has provided the following instruction alongside the skill invocation: {user_instruction}")

    if runtime_note:
        parts.append("")
        parts.append(f"[Runtime note: {runtime_note}]")

    return "\n".join(parts)


def scan_skill_commands() -> Dict[str, Dict[str, Any]]:
    """Scan ~/.hermes/skills/ and return a mapping of /command -> skill info.

    Returns:
        Dict mapping "/skill-name" to {name, description, skill_md_path, skill_dir}.
    """
    global _skill_commands
    _skill_commands = {}
    try:
        from tools.skills_tool import SKILLS_DIR, _parse_frontmatter, skill_matches_platform, _get_disabled_skill_names
        from agent.skill_utils import get_external_skills_dirs
        disabled = _get_disabled_skill_names()
        seen_names: set = set()

        # Scan local dir first, then external dirs
        dirs_to_scan = []
        if SKILLS_DIR.exists():
            dirs_to_scan.append(SKILLS_DIR)
        dirs_to_scan.extend(get_external_skills_dirs())

        for scan_dir in dirs_to_scan:
            for skill_md in scan_dir.rglob("SKILL.md"):
                if any(part in ('.git', '.github', '.hub') for part in skill_md.parts):
                    continue
                try:
                    content = skill_md.read_text(encoding='utf-8')
                    frontmatter, body = _parse_frontmatter(content)
                    # Skip skills incompatible with the current OS platform
                    if not skill_matches_platform(frontmatter):
                        continue
                    name = frontmatter.get('name', skill_md.parent.name)
                    if name in seen_names:
                        continue
                    # Respect user's disabled skills config
                    if name in disabled:
                        continue
                    description = frontmatter.get('description', '')
                    if not description:
                        for line in body.strip().split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                description = line[:80]
                                break
                    seen_names.add(name)
                    # Normalize to hyphen-separated slug, stripping
                    # non-alnum chars (e.g. +, /) to avoid invalid
                    # Telegram command names downstream.
                    cmd_name = name.lower().replace(' ', '-').replace('_', '-')
                    cmd_name = _SKILL_INVALID_CHARS.sub('', cmd_name)
                    cmd_name = _SKILL_MULTI_HYPHEN.sub('-', cmd_name).strip('-')
                    if not cmd_name:
                        continue
                    _skill_commands[f"/{cmd_name}"] = {
                        "name": name,
                        "description": description or f"Invoke the {name} skill",
                        "skill_md_path": str(skill_md),
                        "skill_dir": str(skill_md.parent),
                    }
                except Exception:
                    continue
    except Exception:
        pass
    return _skill_commands


def get_skill_commands() -> Dict[str, Dict[str, Any]]:
    """Return the current skill commands mapping (scan first if empty)."""
    if not _skill_commands:
        scan_skill_commands()
    return _skill_commands


def resolve_skill_command_key(command: str) -> Optional[str]:
    """Resolve a user-typed /command to its canonical skill_cmds key.

    Skills are always stored with hyphens — ``scan_skill_commands`` normalizes
    spaces and underscores to hyphens when building the key. Hyphens and
    underscores are treated interchangeably in user input: this matches
    ``_check_unavailable_skill`` and accommodates Telegram bot-command names
    (which disallow hyphens, so ``/claude-code`` is registered as
    ``/claude_code`` and comes back in the underscored form).

    Returns the matching ``/slug`` key from ``get_skill_commands()`` or
    ``None`` if no match.
    """
    if not command:
        return None
    cmd_key = f"/{command.replace('_', '-')}"
    return cmd_key if cmd_key in get_skill_commands() else None


def build_skill_invocation_message(
    cmd_key: str,
    user_instruction: str = "",
    task_id: str | None = None,
    runtime_note: str = "",
) -> Optional[str]:
    """Build the user message content for a skill slash command invocation.

    Args:
        cmd_key: The command key including leading slash (e.g., "/gif-search").
        user_instruction: Optional text the user typed after the command.

    Returns:
        The formatted message string, or None if the skill wasn't found.
    """
    commands = get_skill_commands()
    skill_info = commands.get(cmd_key)
    if not skill_info:
        return None

    loaded = _load_skill_payload(skill_info["skill_dir"], task_id=task_id)
    if not loaded:
        return f"[Failed to load skill: {skill_info['name']}]"

    loaded_skill, skill_dir, skill_name = loaded
    activation_note = (
        f'[SYSTEM: The user has invoked the "{skill_name}" skill, indicating they want '
        "you to follow its instructions. The full skill content is loaded below.]"
    )
    return _build_skill_message(
        loaded_skill,
        skill_dir,
        activation_note,
        user_instruction=user_instruction,
        runtime_note=runtime_note,
    )


def build_preloaded_skills_prompt(
    skill_identifiers: list[str],
    task_id: str | None = None,
) -> tuple[str, list[str], list[str]]:
    """Load one or more skills for session-wide CLI preloading.

    Returns (prompt_text, loaded_skill_names, missing_identifiers).
    """
    prompt_parts: list[str] = []
    loaded_names: list[str] = []
    missing: list[str] = []

    seen: set[str] = set()
    for raw_identifier in skill_identifiers:
        identifier = (raw_identifier or "").strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)

        loaded = _load_skill_payload(identifier, task_id=task_id)
        if not loaded:
            missing.append(identifier)
            continue

        loaded_skill, skill_dir, skill_name = loaded
        activation_note = (
            f'[SYSTEM: The user launched this CLI session with the "{skill_name}" skill '
            "preloaded. Treat its instructions as active guidance for the duration of this "
            "session unless the user overrides them.]"
        )
        prompt_parts.append(
            _build_skill_message(
                loaded_skill,
                skill_dir,
                activation_note,
            )
        )
        loaded_names.append(skill_name)

    return "\n\n".join(prompt_parts), loaded_names, missing


# ── SDC (Spec-Driven-Coding) 命名空间命令 ──
# 参考 OpenSpec /opsx:propose 和 Superpowers 设计理念

import re
_SDC_COMMAND_PATTERN = re.compile(r"^/sdc:([a-z]+)(\s+.*)?$", re.IGNORECASE)

# SDC 子命令定义：子命令名称 -> (描述, 技能管道列表)
SDC_SUBCOMMANDS = {
    "spec": (
        "生成规范文档 - 结构化需求分析与设计规范",
        ["writing-plans"],
    ),
    "plan": (
        "生成实现计划 - 详细的分步执行方案",
        ["writing-plans", "test-driven-development"],
    ),
    "implement": (
        "执行开发实现 - 自动生成计划并分发给子代理",
        ["writing-plans", "subagent-driven-development", "requesting-code-review"],
    ),
    "review": (
        "代码审查 - 质量检查与改进建议",
        ["requesting-code-review", "systematic-debugging"],
    ),
    "test": (
        "测试驱动开发 - TDD 模式开发",
        ["test-driven-development", "systematic-debugging"],
    ),
    "quality": (
        "质量检查 - 代码规范与质量保障",
        ["systematic-debugging", "requesting-code-review"],
    ),
}


def is_sdc_command(command: str) -> bool:
    """检查是否为 SDC 命名空间命令。
    
    示例: /sdc:spec, /sdc:plan, /sdc:implement
    """
    return bool(_SDC_COMMAND_PATTERN.match(command.strip()))


def parse_sdc_command(command: str) -> tuple[str | None, str]:
    """解析 SDC 命令，返回 (子命令, 用户输入)。
    
    示例: "/sdc:spec 实现用户登录" -> ("spec", "实现用户登录")
    """
    match = _SDC_COMMAND_PATTERN.match(command.strip())
    if not match:
        return None, ""
    subcmd = match.group(1).lower()
    user_input = (match.group(2) or "").strip()
    return subcmd, user_input


def get_sdc_pipeline(subcommand: str) -> list[str]:
    """获取子命令对应的技能管道。"""
    if subcommand not in SDC_SUBCOMMANDS:
        return []
    return SDC_SUBCOMMANDS[subcommand][1]


def build_sdc_invocation_message(
    command: str,
    task_id: str | None = None,
) -> str | None:
    """构建 SDC 命令调用消息，自动编排技能管道。
    
    当用户输入 /sdc:spec <需求> 时:
    1. 解析子命令和用户输入
    2. 加载该子命令对应的所有技能
    3. 组合成完整的系统提示
    """
    subcmd, user_instruction = parse_sdc_command(command)
    
    if not subcmd or subcmd not in SDC_SUBCOMMANDS:
        available = ", ".join(f"/sdc:{k}" for k in sorted(SDC_SUBCOMMANDS.keys()))
        return (
            f"[SDC] 未知子命令: /sdc:{subcmd or '(none)'}\\n"
            f"可用子命令: {available}"
        )
    
    description, pipeline = SDC_SUBCOMMANDS[subcmd]
    
    # 构建激活消息
    parts = [
        f"[SYSTEM: 用户已调用 Spec-Driven-Coding (SDC) 命令 /sdc:{subcmd}]",
        f"[SDC 模式: {description}]",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "SDC 基于 OpenSpec 和 Superpowers 设计理念",
        "自动编排底层技能组合，提供规范驱动的开发工作流",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    # 加载并编排管道中的每个技能
    loaded_skills = []
    missing_skills = []
    
    for skill_name in pipeline:
        # 尝试加载 skill
        loaded = _load_skill_payload(skill_name, task_id=task_id)
        if loaded:
            loaded_skill, skill_dir, display_name = loaded
            loaded_skills.append((loaded_skill, skill_dir, display_name))
        else:
            missing_skills.append(skill_name)
    
    # 添加已加载的技能内容
    for idx, (loaded_skill, skill_dir, display_name) in enumerate(loaded_skills, 1):
        parts.extend([
            f"## [SDC 管道步骤 {idx}/{len(loaded_skills)}: {display_name}]",
            "─" * 50,
            loaded_skill.get("content", "").strip(),
            "",
        ])
    
    if missing_skills:
        parts.append(f"[SDC 注意: 以下技能未找到: {', '.join(missing_skills)}]")
    
    # 添加用户指令
    if user_instruction:
        parts.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"## 用户指令",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            user_instruction,
        ])
    
    # 添加 SDC 质量保障注入
    parts.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "## SDC 质量保障准则",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "1. **每个任务粒度**: 单个任务应在 2-5 分钟内可完成",
        "2. **可验证性**: 每个步骤必须包含明确的验证方法",
        "3. **文档完整性**: 包含目标、上下文、分步方案、风险点",
        "4. **可执行性**: 提供确切的文件路径、代码示例、测试命令",
        "",
        f"请按照 SDC /sdc:{subcmd} 模式处理用户需求。",
    ])
    
    return "\n".join(parts)


def get_sdc_command_list() -> list[tuple[str, str]]:
    """获取所有 SDC 子命令列表，用于 /help 显示。"""
    return [
        (f"/sdc:{name}", desc)
        for name, (desc, _) in SDC_SUBCOMMANDS.items()
    ]
