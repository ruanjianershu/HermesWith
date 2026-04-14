#!/bin/bash
# Hermeswith 并行开发脚本 (2并发 + 跳过权限检查)
# 用于完成 Track 3-6 的开发

set -e

PROJECT_DIR="/Users/liting/workspace/hermeswith"
cd "$PROJECT_DIR"

# 检查虚拟环境
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

echo "🚀 启动并行开发任务..."
echo "Track 3: API层开发 (多租户认证)"
echo "Track 4: 集成层开发 (Clawith连接器)"

# Track 3: API层开发
claude -p --dangerously-skip-permissions "
在 /Users/liting/workspace/hermeswith 项目中，完成 Track 3: API层开发。

**前置检查**：
1. 检查 hermeswith/security/ 目录是否存在，如果不存在先创建它
2. 检查 hermeswith/persistence/models.py 是否已有 CompanyDB/APIKeyDB/AuditLogDB 模型

**任务**：
创建以下文件：

1. hermeswith/api/__init__.py
2. hermeswith/api/dependencies.py - FastAPI依赖注入，包含：
   - get_db() - 数据库会话
   - get_current_company() - 从API Key解析当前公司
   - require_permissions(permissions: List[str]) - 权限检查依赖
3. hermeswith/api/middleware.py - 中间件，包含：
   - AuditMiddleware - 记录所有请求到审计日志
   - RateLimitMiddleware - 基于公司ID的速率限制
   - TenantIsolationMiddleware - 确保查询自动过滤company_id
4. hermeswith/api/router.py - 主路由，包含：
   - /health - 健康检查
   - POST /v1/agents - 创建Agent
   - GET /v1/agents - 列出Agent
   - GET /v1/agents/{id} - 获取Agent
   - PUT /v1/agents/{id} - 更新Agent
   - DELETE /v1/agents/{id} - 删除Agent
   - POST /v1/agents/{id}/tasks - 分配任务
   - GET /v1/tasks/{id} - 获取任务状态
   - GET /v1/tasks/{id}/output - 获取任务输出

**要求**：
- 所有路由必须依赖 get_current_company()
- 所有数据库查询必须过滤 company_id
- 使用 hermeswith/security/auth.py 中的认证函数
- 使用 hermeswith/security/rate_limit.py 中的限流函数
- 使用 hermeswith/security/audit.py 中的审计函数

完成后返回：成功创建的文件列表
" &

PID3=$!

# Track 4: 集成层开发
claude -p --dangerously-skip-permissions "
在 /Users/liting/workspace/hermeswith 项目中，完成 Track 4: 集成层开发。

**前置检查**：
检查 hermeswith/persistence/models.py 是否已有 AgentDB/TaskDB/AgentOutputDB 模型。

**任务**：
创建以下文件：

1. hermeswith/integrations/__init__.py
2. hermeswith/integrations/clawith_client.py - Clawith API客户端：
   - ClawithClient 类
   - __init__(base_url, api_key)
   - create_agent(name, model, system_prompt, tools, company_id) -> agent_id
   - assign_task(agent_id, task_data) -> task_id
   - get_task_status(task_id) -> status
   - get_task_output(task_id) -> output
   - list_agents(company_id) -> agents
   - delete_agent(agent_id) -> bool
3. hermeswith/integrations/sync_service.py - 同步服务：
   - SyncService 类
   - sync_agent_to_clawith(agent_db) - 同步Agent到Clawith
   - sync_task_from_clawith(task_id) - 从Clawith同步任务状态
   - sync_outputs_from_clawith(agent_id) - 同步Agent输出

**要求**：
- 使用 httpx 进行HTTP调用
- 添加适当的错误处理和重试逻辑
- 使用 hermeswith/persistence/database.py 中的 get_db()
- Agent模型必须包含 clawith_agent_id 字段存储远程ID

完成后返回：成功创建的文件列表
" &

PID4=$!

echo ""
echo "⏳ 等待任务完成..."
echo "Track 3 PID: $PID3"
echo "Track 4 PID: $PID4"

wait $PID3
RESULT3=$?
wait $PID4
RESULT4=$?

echo ""
echo "✅ 并行任务完成"
echo "Track 3 结果: $RESULT3"
echo "Track 4 结果: $RESULT4"

# 检查完成状态
if [ $RESULT3 -eq 0 ] && [ $RESULT4 -eq 0 ]; then
    echo ""
    echo "🎉 Track 3 和 Track 4 完成！"
    echo ""
    echo "接下来运行 Track 5 和 Track 6..."
    
    # Track 5: 核心服务层
    claude -p --dangerously-skip-permissions "
在 /Users/liting/workspace/hermeswith 项目中，完成 Track 5: 核心服务层。

**前置检查**：
1. 检查 hermeswith/api/router.py 是否存在
2. 检查 hermeswith/integrations/clawith_client.py 是否存在

**任务**：
创建以下文件：

1. hermeswith/services/__init__.py
2. hermeswith/services/agent_service.py - Agent服务：
   - AgentService 类
   - create_agent(company_id, name, model, system_prompt, tools) -> AgentDB
   - get_agent(company_id, agent_id) -> AgentDB
   - list_agents(company_id, filters) -> List[AgentDB]
   - update_agent(company_id, agent_id, updates) -> AgentDB
   - delete_agent(company_id, agent_id) -> bool
   - 调用 integrations/clawith_client.py 同步到Clawith
3. hermeswith/services/task_service.py - 任务服务：
   - TaskService 类
   - create_task(company_id, agent_id, title, description, instruction) -> TaskDB
   - get_task(company_id, task_id) -> TaskDB
   - list_tasks(company_id, agent_id, status) -> List[TaskDB]
   - assign_task_to_agent(company_id, task_id) -> bool
   - sync_task_status(company_id, task_id) - 从Clawith同步
4. hermeswith/services/output_service.py - 输出服务：
   - OutputService 类
   - get_agent_outputs(company_id, agent_id, since) -> List[AgentOutputDB]
   - get_latest_output(company_id, agent_id) -> AgentOutputDB
   - sync_outputs_from_clawith(company_id, agent_id) -> int (同步数量)

**要求**：
- 所有服务方法必须接收 company_id 参数
- 所有数据库查询必须过滤 company_id
- 调用 integrations/ 中的客户端进行外部同步
- 返回数据库模型对象

完成后返回：成功创建的文件列表
" &
    
    PID5=$!
    
    # Track 6: 主应用和配置
    claude -p --dangerously-skip-permissions "
在 /Users/liting/workspace/hermeswith 项目中，完成 Track 6: 主应用和配置。

**前置检查**：
1. 检查 hermeswith/api/router.py 是否存在
2. 检查 hermeswith/services/agent_service.py 是否存在

**任务**：
创建以下文件：

1. hermeswith/main.py - FastAPI主应用：
   - 创建 FastAPI 实例
   - 添加中间件：CORS、AuditMiddleware、RateLimitMiddleware、TenantIsolationMiddleware
   - 包含 router.py 的路由
   - 启动时初始化数据库
   - 健康检查端点
2. hermeswith/config.py - 配置管理：
   - Settings 类 (pydantic-settings)
   - 数据库URL、Clawith API URL、密钥等
   - 从环境变量加载
3. hermeswith/cli.py - CLI工具：
   - Typer 应用
   - init-db 命令 - 初始化数据库
   - create-company 命令 - 创建公司
   - create-api-key 命令 - 创建API密钥
   - server 命令 - 启动服务
4. .env.example - 环境变量示例
5. Dockerfile - 容器化
6. docker-compose.yml - 完整编排（包含PostgreSQL）

**要求**：
- 使用 python-dotenv 加载环境变量
- Dockerfile 使用多阶段构建
- docker-compose 包含 postgres 和 app 服务
- 确保所有组件能正常导入

完成后返回：成功创建的文件列表
" &
    
    PID6=$!
    
    echo "Track 5 PID: $PID5"
    echo "Track 6 PID: $PID6"
    
    wait $PID5
    RESULT5=$?
    wait $PID6
    RESULT6=$?
    
    echo ""
    echo "✅ 所有任务完成"
    echo "Track 5 结果: $RESULT5"
    echo "Track 6 结果: $RESULT6"
    
    if [ $RESULT5 -eq 0 ] && [ $RESULT6 -eq 0 ]; then
        echo ""
        echo "🎉🎉🎉 所有 Track 完成！"
        echo ""
        echo "运行验证:"
        echo "  cd /Users/liting/workspace/hermeswith"
        echo "  python -c \"from hermeswith.main import app; print('OK')\""
        echo ""
        echo "启动服务:"
        echo "  docker-compose up -d"
    fi
else
    echo ""
    echo "⚠️ 部分任务失败，请检查日志"
fi
