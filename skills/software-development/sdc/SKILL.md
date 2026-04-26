---
name: sdc
description: Spec-Driven-Coding — 规范驱动的开发工作流。基于 OpenSpec 和 Superpowers 设计理念，提供 /sdc:spec, /sdc:plan, /sdc:implement 等子命令。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sdc, spec-driven, coding, workflow, openspec, superpowers]
    related_skills: [writing-plans, plan, subagent-driven-development, test-driven-development]
---

# Spec-Driven-Coding (SDC) 规范驱动开发

## 概述

SDC 是基于 OpenSpec 和 Superpowers 设计理念的统一开发工作流。
通过 `/sdc:子命令` 格式触发，自动编排底层技能组合。

## 可用子命令

| 命令 | 功能 | 自动编排的技能 |
|------|------|----------------|
| `/sdc:spec <需求>` | 生成规范文档 | writing-plans + 质量保障 |
| `/sdc:plan <需求>` | 生成实现计划 | writing-plans + TDD 指南 |
| `/sdc:implement <需求>` | 执行开发实现 | 编写计划 + 子代理分发 |
| `/sdc:review <路径>` | 代码审查 | requesting-code-review |
| `/sdc:test <目标>` | 测试驱动开发 | test-driven-development |
| `/sdc:quality` | 质量检查 | systematic-debugging + 代码规范 |

## 核心设计理念

1. **命名空间隔离**：所有 SDC 命令统一在 `/sdc:` 命名空间下
2. **自动编排**：用户只需输入高层命令，系统自动触发底层 Skill 组合
3. **渐进式开发**：spec → plan → implement → test → review 的完整闭环
4. **质量内置**：每个阶段都注入对应的质量检查机制

## 使用方式

```
# 生成功能规范
/sdc:spec 实现用户登录功能

# 生成实现计划
/sdc:plan 用户登录功能的密码重置模块

# 执行开发（会自动生成计划并分发给子代理）
/sdc:implement 实现 JWT 认证中间件

# 代码审查
/sdc:review ./middleware/auth.py

# TDD 模式开发
/sdc:test tests/unit/test_auth.py
```

## 执行流程

当用户输入 `/sdc:spec <需求>` 时：
1. 触发 `writing-plans` skill — 结构化计划生成
2. 注入质量检查机制 — 确保规范完整性
3. 应用项目编码规范 — 符合团队约定
4. 调用 OpenSpec 格式生成器 — 输出标准规范文档

**注意：本 skill 是入口点，实际的子命令逻辑由 SDC 命令处理器在运行时动态编排。**
