# agent-sandbox

这是一个基于 LangGraph、结构化错误解析和 Docker 隔离执行的代码修复实验项目。

## 目录结构

```text
agent_sandbox/
├── integrations/       # Azure OpenAI 等外部服务
├── parsing/            # Python 错误日志解析与数据模型
├── repair/             # pytest 报告、补丁生成和 LangGraph 修复流
└── sandbox/            # Docker 隔离执行
scripts/                # 可直接运行的 CLI 和评估入口
examples/               # 示例代码与日志数据
fixtures/               # 可重复使用的故障项目和测试场景
docs/learning/          # 按迭代阶段保留的项目记录和复盘
```

## 常用命令

所有命令都从仓库根目录运行：

```bash
# 使用正则解析示例日志
python -m scripts.parse_logs \
	--input examples/log_parser/samples/dirty_logs_small.jsonl \
	--parser regex

# 评估单个解析器
python -m scripts.evaluate_parser \
	--jsonl_path examples/log_parser/samples/dirty_logs.jsonl \
	--parser regex

# 运行故障 fixture，并解析 pytest JSON report（预期测试失败）
python -m agent_sandbox.repair.test_runner

# 运行完整修复图（需要 Azure OpenAI 环境变量）
python -m agent_sandbox.repair.repair_graph
```

`fixtures/buggy_project/` 是故意保留错误的修复目标，不代表仓库自身测试失败。
