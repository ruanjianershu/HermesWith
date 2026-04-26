# SDC Subcommands - 子命令编排定义

# /sdc:spec - 规范生成
SPEC_PIPELINE = [
    "writing-plans",      # 结构化计划
    "requesting-code-review",  # 审查要点
]

# /sdc:plan - 实现计划
PLAN_PIPELINE = [
    "writing-plans",      # 详细计划
    "test-driven-development",  # TDD 指南
]

# /sdc:implement - 执行实现
IMPLEMENT_PIPELINE = [
    "writing-plans",      # 先生成计划
    "subagent-driven-development",  # 分发给子代理
    "requesting-code-review",  # 自动审查
]

# /sdc:review - 代码审查
REVIEW_PIPELINE = [
    "requesting-code-review",
    "systematic-debugging",
]

# /sdc:test - 测试驱动
TEST_PIPELINE = [
    "test-driven-development",
    "systematic-debugging",
]

# 质量检查 Guards
QUALITY_GUARDS = [
    "确保输出包含: 目标, 上下文, 步骤, 验证方法",
    "每个任务粒度: 2-5 分钟可完成",
    "必须包含: 文件路径, 代码示例, 测试命令",
]
