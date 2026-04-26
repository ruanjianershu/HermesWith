# SDC - Spec-Driven-Coding

规范驱动的开发工作流，参考 OpenSpec 和 Superpowers 设计理念。

## 目录结构

```
sdc/
├── SKILL.md                    # 主 skill 定义（用户可见）
├── references/
│   └── pipeline.py             # 子命令编排定义
└── scripts/
    └── executor.py             # 执行器（未来）
```

## 设计理念

- **命名空间隔离**：`/sdc:*` 统一前缀
- **自动编排**：用户输入高层命令，系统自动组合底层 skills
- **流水线模式**：每个子命令对应一个 skill 执行管道
