# Track A2: Runtime Config & Dependencies

## 目标
整理依赖、修复 Dockerfile、确保容器能正确运行 AgentRuntime。

## 任务清单

### 1. 依赖梳理
- 检查 `vendor/hermes-agent/requirements.txt`
- 将必要依赖合并到 `pyproject.toml`
- 确保 `pip install -e .` 能成功安装

### 2. Dockerfile.runtime 修复
- 确保 Hermes agent 代码在容器内可用
- 正确设置 `PYTHONPATH`
- 处理 `vendor/hermes-agent` 的复制（当前是 symlink，Docker build 会失败）

### 3. .env 文件支持
- 在 `AgentConfig.from_env()` 中支持从 `.env` 文件加载
- 使用 `python-dotenv`

### 4. 容器启动测试
```bash
docker build -f Dockerfile.runtime -t hermeswith-runtime .
docker run -e KIMI_API_KEY=... hermeswith-runtime python examples/verify_llm_path.py
```

## 验收标准
```bash
cd /Users/liting/workspace/hermeswith
docker-compose build control-plane
docker-compose build researcher
```
