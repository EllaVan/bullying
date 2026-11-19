# 项目交接报告 0.6.1

## 1. 目标与边界

系统通过完整情境多轮对话收集可追溯 Evidence，形成 PV01–PV10 画像，并计算施暴、受害、施暴-受害、旁观四类独立 0–100 工程风险分数。评分叠加量表构念门控（假设意向封顶、高等级需真实/习惯线索等），不推翻问答流、不缩短测评计划。

它是工程流程测试与待校准原型，不是临床诊断或统计概率模型。紧急风险处置、人工复核工作流、隐私权限按本轮要求暂不实现。

## 2. 架构

A1 生成情境，A2 提出带条件和跳题的任务，A3 按 Schema 抽取观察、Evidence（可选 intensity）和真实经历，画像层汇总 Facet、冲突软消解（写明原因与证据原文，消解值满分计入）并生成可读 `evidence_ref`，A4 按受管权重计分后经 `scale_constraints` 门控并输出冲突置信标签，A5 生成完整 `report.md` 与简洁 `report_brief.md`。对照样例：`outputs/recompute_69db8d61/`。

遗留单案例 round1 链路（`validate`/`replay`/`extract`）仍保留，非产品主路径。详见 `ARCHITECTURE.md`、`FILE_CATALOG.md`。

## 3. 分数契约

角色字段为 `score`、`form_scores`、`confidence`、`level`，可选 `experience_boost`、`gate_applied`。`score` 范围 0–100，四类互相独立，不求和；阈值默认施暴/受害/旁观 35/65，双重 40/70。观测不足时 score=null。confidence 只表示信息覆盖和抽取质量。门控审计见 `risk_result.scale_constraints`。

## 4. 目录与关键文件

- `psych_agent/`：`dialogue_cli.py` 入口；`measurement_controller.py` 状态机；`turn_extractor.py` A3；`conflict_resolver.py` / `evidence_labels.py` / `scale_gates.py`；`risk_engine.py` A4；`risk_reporter.py` A5。
- `config/`：原题、单元、69 条多轮规则、Facet、权重、阈值、`scale_constraints.json`、报告策略；配置集合 `CFG_008`。
- `schemas/`：对话、画像、经历、风险输入/结果/外部预测 Schema。
- `outputs/<session>/`：`dialogue_state.json`、`profile.json`、`risk_result.json`、`report.md`、`report_brief.md` 及逐轮审计。

## 5. 已处理的问题

详见 `docs/0.6.1_REQUIREMENT_TRACEABILITY.md`。包括强度与冲突软消解、旁观角色、量表门控、简洁报告与可读证据标签。0.5.x 闭环见 `docs/history/`。本轮修改说明见 `docs/V0.6.1_CHANGELOG_SCALE_REPORT.md`。

## 6. 使用与验证

先运行 `python run.py dialogue-validate`，再使用 `interview` 联机或 `dialogue-replay` 离线回放。主路径回归：

```bash
python -m unittest tests.test_dialogue tests.test_conflict_resolver tests.test_dialogue_cli tests.test_evidence_labels_and_gates
```

细则见 `docs/USAGE.md`。

## 7. 后续校准

需独立人工标注校准 Facet、角色权重、阈值、规则语义与门控松紧；当前不把工程分数宣称为发生概率。缩短对话、紧急风险、人工复核、隐私权限仍暂缓。
