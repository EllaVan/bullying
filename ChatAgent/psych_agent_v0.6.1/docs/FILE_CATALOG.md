# 文件目录说明 0.6.1

标签含义：

- **主路径**：多轮访谈产品链路依赖
- **遗留**：单案例 round1 兼容；勿作为默认扩展点
- **文档**：说明材料
- **工具**：脚本/测试/夹具
- **生成物**：运行输出（通常不入库，对照样例除外）
- **本地**：机器私有，勿提交密钥

`evidence_rubric.json`、`aggregation_rules.json` 由 `psych_agent/config.load_config` 读取，**不在** `config_manifest.json` 的受管文件列表中（遗留装载路径）。

---

## 根目录

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `VERSION` | 主路径 | 发行版本号 `0.6.1` |
| `README.md` | 文档 | 项目入口与文档索引 |
| `requirements.txt` | 工具 | Python 依赖 |
| `run.py` | 主路径 | CLI 入口；清理代理环境变量后调用 `psych_agent.cli.main` |
| `.gitignore` | 工具 | 忽略缓存、密钥、一般 outputs |

---

## config/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `config_manifest.json` | 主路径 | 配置集合 `CFG_008` 与受管文件清单 |
| `psychological_variable.json` | 主路径 | PV01–PV10 定义与解释边界 |
| `questionnaire_mapping.json` | 主路径 | 原题 A–G / F 背景映射 |
| `scenario_blueprint.json` | 主路径 | 情境蓝图与题目绑定 |
| `measurement_units.json` | 主路径 | 30 个测量单元、槽位、Facet 名 |
| `dialogue_rubric.json` | 主路径 | 多轮 Evidence 规则（DR_*） |
| `dialogue_scenarios.json` | 主路径 | 对话情境实例配置 |
| `interview_policy.json` | 主路径 | 访谈计划、跳题、追问策略 |
| `variable_facets.json` | 主路径 | 变量→Facet→unit 权重 |
| `variable_scoring.json` | 主路径 | 方向值、强度量表、冲突消解策略 |
| `evidence_quality.json` | 主路径 | 可计分主体/参照框架与冲突策略声明 |
| `risk_profile_rules.json` | 主路径 | 角色—变量关联（须与 A4 特征一致） |
| `risk_scoring.json` | 主路径 | A4 权重、阈值（literature_heuristic_v1）、旁观角色、经历上浮 |
| `scale_constraints.json` | 主路径 | 量表构念门控（锚定包 olweus_dbvs_bpbq_v1） |
| `confidence_policy.json` | 主路径 | 低信息/A3 降级对 confidence 的惩罚 |
| `report_policy.json` | 主路径 | A5 报告章节与边界；简洁报告开关 |
| `agents.example.json` | 主路径 | 分 Agent backend 示例 |
| `llm.local.example.json` | 主路径 | LLM 配置模板（无密钥） |
| `llm.local.json` | 本地 | 本机 LLM 配置；已 gitignore |
| `evidence_rubric.json` | 遗留 | 单案例规则（R_*）；`load_config` 需要 |
| `aggregation_rules.json` | 遗留 | 旧汇总策略校验常量 |
| `round1.json` | 遗留 | 单案例默认 scope |
| `round1_extended.example.json` | 遗留 | 扩展 scope 示例 |

---

## psych_agent/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `__init__.py` | 主路径 | 包版本 |
| `a3_consistency.py` | 主路径 | A3 多次抽取方向一致率纯函数 |
| `cli.py` | 主路径+遗留 | 统一 argparse：挂载对话命令 + 旧 validate/replay/extract 等 |
| `dialogue_cli.py` | 主路径 | 多轮命令实现（interview、replay、profile、risk、report…） |
| `dialogue_runner.py` | 主路径 | 会话运行、落盘、manifest |
| `dialogue_config.py` | 主路径 | 装载并交叉校验多轮配置 |
| `dialogue_contracts.py` | 主路径 | 任务/观察/Evidence 契约与 `validate_turn` |
| `measurement_controller.py` | 主路径 | 测量状态机、覆盖率、追问 |
| `scenario_agent.py` | 主路径 | A1 |
| `interviewer.py` | 主路径 | A2 |
| `turn_extractor.py` | 主路径 | A3（含一次结构修复与空观察降级） |
| `profile.py` | 主路径 | 画像构建与校验 |
| `facets.py` | 主路径 | Facet 汇总入口（委托 conflict_resolver） |
| `conflict_resolver.py` | 主路径 | 冲突分类、强度映射、软消解审计 |
| `evidence_labels.py` | 主路径 | 可读 `evidence_ref` 生成 |
| `scale_gates.py` | 主路径 | A4 后置量表门控 |
| `experience.py` | 主路径 | 真实经历台账 |
| `risk_engine.py` | 主路径 | A4 四角色计分 / 外部预测接入 |
| `risk_reporter.py` | 主路径 | A5；`report.md` + `report_brief.md` |
| `agent_transport.py` | 主路径 | Agent 请求传输 |
| `llm_client.py` | 主路径 | HTTP LLM 客户端与 doctor |
| `io_utils.py` | 主路径 | JSON 读写与 ValidationError |
| `contracts.py` | 主路径 | 通用 Schema 形状校验 |
| `model_output.py` | 工具 | 模型输出清洗（围栏等） |
| `config.py` | 遗留+底座 | 量表/旧规则装载；被 dialogue_config 调用 |
| `evidence.py` | 遗留 | 单案例 Evidence 校验 |
| `extractor.py` | 遗留 | 单案例 A3 提示组装与抽取 |
| `aggregate.py` | 遗留 | 单案例证据描述汇总（不计角色分） |

---

## prompts/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `scenario_generator.md` | 主路径 | A1 |
| `interviewer.md` | 主路径 | A2 |
| `turn_extractor.md` | 主路径 | A3（含 intensity / 冲突边界） |
| `turn_repair.md` | 主路径 | A3 结构修复 |
| `report_agent.md` | 主路径 | A5（四角色） |
| `evidence_extractor.md` | 遗留 | 单案例抽取提示 |

---

## schemas/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `dialogue_state.schema.json` | 主路径 | 会话状态 |
| `question_task.schema.json` | 主路径 | A2 任务 |
| `turn_observation.schema.json` | 主路径 | 轮次观察导出形态 |
| `profile.schema.json` | 主路径 | 画像 |
| `experience.schema.json` | 主路径 | 经历 |
| `risk_model_input.schema.json` | 主路径 | A4 输入 |
| `risk_result.schema.json` | 主路径 | A4 结果（含 bystander） |
| `risk_prediction.schema.json` | 主路径 | 外部预测接入 |
| `case.schema.json` | 遗留 | 单案例输入 |
| `extraction.schema.json` | 遗留 | 单案例抽取结果 |

已删除空壳：`dialogue.schema.json`、`evidence.schema.json`、`risk.schema.json`。

---

## scripts/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `recompute_profile_risk.py` | 工具 | 已有 profile 按当前配置重算 A4/报告 |
| `rerun_llm_from_trace.py` | 工具 | 真人轨迹自动填答 + LLM 重抽（见 USAGE） |
| `measure_a3_consistency.py` | 工具 | 同一轨迹多次 A3，输出方向一致率 |
| `build_measurement_config.py` | 工具 | 从 source 重建测量配置 |
| `build_dialogue_fixtures.py` | 工具 | 生成对话回放 fixture |
| `export_dialogue_schemas.py` | 工具 | 导出对话相关 Schema |

---

## tests/

| 文件 | 标签 | 用途 |
| --- | --- | --- |
| `test_dialogue.py` | 主路径 | 多轮行为与计分契约 |
| `test_dialogue_cli.py` | 主路径 | CLI 回放/访谈链路 |
| `test_conflict_resolver.py` | 主路径 | 冲突/强度单元测试 |
| `test_conflict_confidence.py` | 主路径 | 冲突置信折减与标签 |
| `test_followup.py` | 遗留 | 旧规则部分映射 |
| `test_round1.py` | 遗留 | 单案例 CLI/配置 |
| `test_model_output.py` | 遗留/工具 | 模型输出与旧 CLI |
| `test_network_diagnostics.py` | 工具 | doctor/网络诊断 |

已删除：`test_v05.py`（调用不存在的 `demo`）。

---

## fixtures/ / data/ / examples/

| 路径 | 标签 | 用途 |
| --- | --- | --- |
| `fixtures/dialogue/*.json` | 主路径 | `dialogue-replay` 合成会话 |
| `fixtures/real/20260914_69db8d61_trace.jsonl` | 主路径 | 真人访谈轨迹（供 `rerun_llm_from_trace`） |
| `fixtures/replay/S01_*.json` | 遗留 | 单案例预制 A3 响应 |
| `data/cases.dev.jsonl` | 遗留 | 合成开发案例集 |
| `data/single_case.json` | 遗留 | 单案例样例 |
| `data/reference_annotations.jsonl` | 遗留 | 开发参考标签（非金标准） |
| `data/README.md` | 文档 | 合成数据说明 |
| `examples/E03_D04.*` | 遗留 | 抽取/汇总手工样例 |

---

## docs/ / source/ / outputs/

| 路径 | 标签 | 用途 |
| --- | --- | --- |
| `docs/PROJECT_HANDOVER_v0.6.1.md` | 文档 | 现行交接 |
| `docs/ARCHITECTURE.md` | 文档 | 架构与数据流 |
| `docs/USAGE.md` | 文档 | 使用与排错 |
| `docs/SCALE_RULES_SOURCE.md` | 文档 | 发表量表计分逻辑锚定包映射 |
| `docs/PSYCH_WEIGHT_THRESHOLDS.md` | 文档 | 文献启发式权重与阈值 |
| `docs/CREDIBILITY_ROADMAP.md` | 文档 | 可信度提升路线图 |
| `docs/REPORT_SCORING_AUDIT.md` | 文档 | recompute 报告七问逐条解答 |
| `docs/FILE_CATALOG.md` | 文档 | 本文件 |
| `docs/V0.5.2_PROBLEMS.md` | 文档 | 0.5.2 问题诊断 |
| `docs/V0.6.1_CHANGES.md` | 文档 | 0.6.1 变更 |
| `docs/history/` | 文档 | 旧交接归档 |
| `source/心理Agent+量表与心理变量.md` | 主路径 | 量表与变量设计源稿 |
| `outputs/recompute_69db8d61/` | 生成物 | 终版对照样例（锚定包+冲突置信+冲突证据；gitignore 白名单） |
| `outputs/*`（其他） | 生成物 | 本地运行结果；默认 gitignore |
