# 项目交接报告 0.5.2

## 1. 目标与边界

系统通过情境对话收集可追溯Evidence，形成PV01–PV10画像，并计算施暴、受害、施暴-受害三类独立风险分数。它是工程流程测试与待校准原型，不是临床诊断或统计概率模型。

## 2. 架构

A1生成情境，A2提出带条件和跳题的任务，A3按Schema抽取观察、Evidence和真实经历，画像层汇总Facet并区分假设/习惯/真实经历/旁观，A4按受管权重输出0–100分数，A5生成含来源与限制的Markdown报告。所有轮次、原始响应和诊断文件均可追溯。

## 3. 分数契约

角色字段为 `score`、`form_scores`、`confidence`、`level`。`score`范围0–100，三类角色互相独立，不求和；35/65为施暴和受害低/关注/高阈值，40/70为双重角色阈值。观测不足、拒答或方向冲突不会补成0.5，角色分数改为null并说明原因。confidence只表示信息覆盖和抽取质量。

## 4. 目录与关键文件

- `psych_agent/`: `dialogue_cli.py`入口；`measurement_controller.py`状态机；`dialogue_contracts.py`契约；`turn_extractor.py` A3；`facets.py`与`experience.py`画像；`risk_engine.py` A4；`risk_reporter.py` A5。
- `config/`: 原题、30单元、69规则、情境、计划、Facet、权重、阈值和报告策略。
- `schemas/`: 对话、画像、经历、风险输入/结果/外部预测Schema。
- `outputs/<session>/`: `dialogue_state.json`、`profile.json`、`risk_result.json`、`report.md`及逐轮审计文件。

## 5. 已处理的0.4问题

详见同目录 `0.5.2_REQUIREMENT_TRACEABILITY.md`。包括旧概率接口、保护变量方向、未知值中点化、A3结构错误、非法上下文、简短回答推进、真实经历区分、PV10求助Facet、动态跳题和详细报告。

> 归档说明：本文描述 0.5.x（三类角色）。现行交接见 `docs/PROJECT_HANDOVER_v0.6.1.md`。

## 6. 使用与验证

先运行 `python run.py dialogue-validate`，再使用 `interview` 联机或 `dialogue-replay` 离线回放。交付前已通过121项单元测试、配置校验和56轮full合成回放。

## 7. 后续校准

需要使用独立人工标注样本校准Facet、角色权重、阈值和分数解释；当前代码不会把工程分数宣称为发生概率。紧急风险、人工复核流程、隐私权限按本轮范围暂缓。
