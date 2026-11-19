# 校园欺凌风险画像心理 Agent 0.6.1

通过情境多轮对话收集可追溯 Evidence，输出 PV01–PV10 画像与四类独立工程风险分数：`bully`、`victim`、`bully_victim`、`bystander`。

配置集合：`CFG_008`。本仓库为工程原型，**不是**临床诊断或发生概率模型。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [docs/PROJECT_HANDOVER_v0.6.1.md](docs/PROJECT_HANDOVER_v0.6.1.md) | 交接报告（v0.5.2 七段体例） |
| [docs/0.6.1_REQUIREMENT_TRACEABILITY.md](docs/0.6.1_REQUIREMENT_TRACEABILITY.md) | 需求追踪表 |
| [docs/V0.6.1_CHANGELOG_SCALE_REPORT.md](docs/V0.6.1_CHANGELOG_SCALE_REPORT.md) | 本轮修改说明（量表门控+双报告） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | A1–A5 与冲突消解架构 |
| [docs/USAGE.md](docs/USAGE.md) | 安装、联机、命令、测试、排错 |
| [docs/SCALE_RULES_SOURCE.md](docs/SCALE_RULES_SOURCE.md) | 发表量表计分逻辑锚定包（Olweus/DBVS/BPBQ） |
| [docs/PSYCH_WEIGHT_THRESHOLDS.md](docs/PSYCH_WEIGHT_THRESHOLDS.md) | 文献启发式权重与阈值（无标注者） |
| [docs/CREDIBILITY_ROADMAP.md](docs/CREDIBILITY_ROADMAP.md) | 可信度提升路线（fallback/规则/一致率/定权） |
| [docs/REPORT_SCORING_AUDIT.md](docs/REPORT_SCORING_AUDIT.md) | recompute 报告七问逐条解答 |
| [docs/FILE_CATALOG.md](docs/FILE_CATALOG.md) | 逐文件用途 |
| [docs/V0.6.1_CHANGES.md](docs/V0.6.1_CHANGES.md) | 相对 0.5.2 的分析层变更 |
| [docs/history/](docs/history/) | 旧版交接归档 |

## 快速开始

```bash
cd psych_agent_v0.6.1
pip install -r requirements.txt
python run.py dialogue-validate
python run.py dialogue-replay --plan s01
# 联机：先配置 config/llm.local.json（见 llm.local.example.json）
python run.py interview --plan full --llm-config config/llm.local.json
# 真人轨迹自动重跑（默认冻结原问答，A3 走 LLM）
python scripts/rerun_llm_from_trace.py --max-turns 8
# 以上省略 --output 时均自动生成 outputs/YYYYMMDDTHHMMSS_<命令>_<id>/
python -m unittest tests.test_dialogue tests.test_conflict_resolver tests.test_conflict_confidence tests.test_evidence_labels_and_gates tests.test_rubric_semantics tests.test_a3_consistency tests.test_dialogue_cli
```

## 目录一览

- `psych_agent/` — 运行时代码（多轮主路径 + 单案例遗留）
- `config/` — 受管测评配置（`CFG_008`）
- `prompts/` — Agent 提示词
- `schemas/` — 公开 JSON Schema
- `fixtures/dialogue/` — 多轮离线回放
- `tests/` — 回归测试
- `docs/` — 交接与二次开发文档
- `outputs/` — 运行产物（对照样例见 `recompute_69db8d61/`：锚定包 + 冲突置信标签 + 冲突证据原文）

详细文件说明见 [FILE_CATALOG.md](docs/FILE_CATALOG.md)。

## 边界

不实现紧急风险处置、人工复核工作流、隐私权限系统。密钥勿写入版本库；使用 `config/llm.local.example.json` 作为模板。
