# HermesWith - 多租户智能体管理平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0+-orange.svg" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License">
</p>

## 🎯 项目简介

HermesWith 是一个面向企业的多租户智能体（Agent）管理平台，提供与 Clawith 的无缝集成。支持创建、管理和监控 AI 智能体，实现任务的自动化分配和执行追踪。

## ✨ 核心特性

- **🏢 多租户架构** - 基于公司的数据隔离，API Key 认证机制
- **🤖 智能体管理** - 创建、配置、监控 AI 智能体，支持 Clawith 同步
- **📋 任务调度** - 优先级任务队列，状态跟踪和结果输出
- **🔒 企业级安全** - Fernet 加密敏感数据，完整的审计日志
- **⚡ 性能优化** - Redis 限流保护，异步数据库操作
- **🔍 可观测性** - 详细的审计追踪，速率限制监控

## 🚀 快速开始

### 使用 Docker Compose（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 创建公司和 API Key
docker-compose exec api python -m hermeswith.cli create-company "我的公司"
docker-compose exec api python -m hermeswith.cli create-api-key <公司ID>
```

### 手动安装

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 初始化数据库
python -m hermeswith.cli init-db

# 创建公司和 API Key
python -m hermeswith.cli create-company "我的公司"
python -m hermeswith.cli create-api-key <公司ID>

# 启动服务
uvicorn hermeswith.main:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 API 接口

### 健康检查
```
GET /health
```

### 智能体管理
```
POST   /v1/agents              # 创建智能体
GET    /v1/agents              # 列出智能体
GET    /v1/agents/{id}         # 获取智能体详情
PUT    /v1/agents/{id}         # 更新智能体
DELETE /v1/agents/{id}         # 删除智能体
```

### 任务管理
```
POST   /v1/agents/{id}/tasks   # 创建任务
GET    /v1/tasks/{id}          # 获取任务详情
GET    /v1/tasks/{id}/output   # 获取任务输出
```

## 🔐 认证方式

### API Key 认证（推荐）
```http
X-API-Key: hw_xxxxxxxxxxxxxxxx
```

### JWT Bearer Token
```http
Authorization: Bearer <jwt-token>
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────┐
│           API Gateway (Nginx)           │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         FastAPI Application            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Auth   │ │  Rate   │ │  Audit  │ │
│  │Middleware│ │ Limiter │ │ Logger  │ │
│  └─────────┘ └─────────┘ └─────────┘ │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Agent  │ │  Task   │ │ Output  │ │
│  │ Service │ │ Service │ │ Service │ │
│  └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Integration Layer              │
│      ┌───────────────────┐            │
│      │   Clawith Client │            │
│      │   Sync Service   │            │
│      └───────────────────┘            │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Data Layer                     │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │PostgreSQL│ │  Redis  │ │Fernet│ │
│  │  (ORM)  │ │ (Cache) │ │(Encrypt)│
│  └─────────┘ └─────────┘ └────────┘ │
└─────────────────────────────────────────┘
```

## 📁 项目结构

```
hermeswith/
├── api/                    # FastAPI 路由和中间件
│   ├── dependencies.py     # 依赖注入
│   ├── middleware.py       # 中间件组件
│   └── router.py           # API 路由定义
├── persistence/            # 数据持久层
│   ├── database.py         # 数据库连接
│   └── models.py           # SQLAlchemy 模型
├── security/               # 安全模块
│   ├── auth.py             # 认证授权
│   ├── encryption.py       # 加密管理
│   ├── rate_limit.py       # 限流控制
│   └── audit.py            # 审计日志
├── integrations/           # 第三方集成
│   ├── clawith_client.py   # Clawith API 客户端
│   └── sync_service.py     # 数据同步服务
├── services/               # 业务服务层
│   ├── agent_service.py    # 智能体服务
│   ├── task_service.py     # 任务服务
│   └── output_service.py   # 输出服务
├── cli.py                  # 命令行工具
├── config.py               # 配置管理
└── main.py                 # 应用入口
```

## 🔧 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql://postgres:postgres@localhost:5432/hermeswith` |
| `CLAWITH_BASE_URL` | Clawith API 地址 | `http://localhost:3000` |
| `CLAWITH_API_KEY` | Clawith API 密钥 | - |
| `REDIS_URL` | Redis 连接地址 | `redis://localhost:6379` |
| `RATE_LIMIT_PER_MINUTE` | 每分钟请求限制 | `60` |
| `SECRET_KEY` | 加密密钥 | 自动生成 |
| `DEBUG` | 调试模式 | `false` |

## 🧪 测试

```bash
# 运行测试
pytest tests/

# 带覆盖率报告
pytest --cov=hermeswith tests/
```

## 📚 文档

- [API 文档](http://localhost:8000/docs) - Swagger UI（启动后访问）
- [ReDoc 文档](http://localhost:8000/redoc) - ReDoc 格式文档

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request


## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

## 💬 联系方式

- 项目主页：[https://github.com/yourusername/hermeswith](https://github.com/yourusername/hermeswith)
- 问题反馈：[GitHub Issues](https://github.com/yourusername/hermeswith/issues)
- 邮箱：contact@hermeswith.com

---

<p align="center">Made with ❤️ by HermesWith Team</p>
