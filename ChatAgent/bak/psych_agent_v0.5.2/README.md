# 校园欺凌风险画像心理 Agent 0.5.2

本版本保留0.4的多轮工程结构，增加Facet、真实经历区分、动态追问和可审计的A4分数输出。

## 运行

```bash
python run.py dialogue-validate
python run.py interview --plan full --llm-config config/llm.local.json
python run.py dialogue-replay --plan full --output outputs/full
python -m unittest discover -s tests
```

A4角色结果是互相独立的0–100工程风险分数：`bully`、`victim`、`bully_victim`。三者不归一化，也不要求合计100；覆盖不足时输出null。分数阈值来自 `config/risk_scoring.json`。

## 目录

`psych_agent/`包含A1–A5、状态机、证据契约、Facet、经历汇总和报告；`config/`为受管测评配置；`schemas/`为公开接口；`prompts/`为模型提示词；`fixtures/`、`examples/`、`tests/`用于回放和回归；`docs/`包含交接说明与需求追踪。

本轮按要求暂不实现紧急风险处置、人工复核工作流和隐私权限系统。
