# HermesWith - GitHub 项目简介

## 简短描述（Short description）

Clawith 的多租户控制平面（Control Plane），为企业提供智能体管理、任务调度和多租户隔离的 API 层。

## 详细描述（Long description）

### 🏢 Clawith 的企业级控制平面

HermesWith 是 Clawith 的多租户控制平面，为企业内部系统提供统一的智能体管理 API。它不是 Clawith 的二次开发，而是在 Clawith 之上构建的管理层，解决以下问题：

- **多租户隔离** - 企业内部多个团队/项目共用 Clawith，需要数据隔离
- **统一 API** - 为内部系统提供标准化的智能体和任务管理接口
- **审计追踪** - 记录谁创建了智能体、分配了什么任务
- **权限控制** - 基于 API Key 的细粒度权限管理

### ✨ 核心能力

- **多租户管理** - 公司级别的数据隔离，API Key 认证
- **智能体生命周期** - 创建、配置、监控、删除 Clawith 智能体
- **任务调度** - 优先级任务队列，异步执行，状态追踪
- **企业安全** - Fernet 加密，审计日志，速率限制
- **Clawith 代理** - 作为 Clawith 的代理层，管理所有交互

### 🏗️ 技术栈

- **后端**: Python 3.11+, FastAPI, SQLAlchemy 2.0
- **数据库**: PostgreSQL 15+, Redis 7+
- **安全**: JWT, API Key, Fernet 加密
- **部署**: Docker, Docker Compose

### 🚀 适用场景

- 企业内部 AI 自动化平台
- 多团队共用 Clawith 的隔离方案
- 需要审计和权限控制的 Clawith 使用场景
- 为内部系统提供 Clawith 的统一 API 层

### 📊 项目统计

- 35+ Python 模块
- 完整的测试覆盖
- 详尽的 API 文档
- Docker 一键部署

---

## 英文版本

### Short Description

Multi-tenant Control Plane for Clawith, providing enterprise-grade agent management, task scheduling, and tenant isolation API layer.

### Long Description

**HermesWith** is a multi-tenant Control Plane for Clawith, designed for enterprises that need to share Clawith across multiple teams while maintaining data isolation and audit trails.

**Key Features:**
- 🔐 Multi-tenant isolation with company-based data separation
- 🤖 Full agent lifecycle management for Clawith agents
- 📋 Priority task queue with async execution and status tracking
- 🔒 Enterprise security: Fernet encryption, audit logging, rate limiting
- ⚡ Acts as a proxy layer to manage all Clawith interactions

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Docker

**Use Cases:** Enterprise AI automation platform, multi-team Clawith sharing with isolation, audit and permission control for Clawith usage
