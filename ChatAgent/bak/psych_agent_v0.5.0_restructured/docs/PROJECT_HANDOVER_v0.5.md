# 校园欺凌风险画像心理 Agent 0.5.0 交接报告

## 1. 定位与边界

本项目是量表驱动的情境多轮对话流程原型，目标是从学生回答中形成PV01—PV10 facet画像，并输出施暴相关、受害相关、施暴与受害兼有三类角色的流程测试结果。当前数值为未校准的工程测试值，不能称为临床概率、诊断或自动处分依据。

本版本沿用0.4的严格数据链：A1情境 → A2问题 → 学生回答 → A3观察与Evidence →画像 → A4风险 → A5报告。控制器独占会话状态、轮次预算、测量单元和追问决策，Agent不能自行推进状态。

## 2. 目录结构

|目录|作用|
|---|---|
|`psych_agent/`|核心Python实现：配置、控制器、A1—A5、Schema和输出校验|
|`config/`|受管配置集合，包含量表派生映射、情境、测量单元、证据规则、风险权重和报告策略|
|`schemas/`|问题、回答、Evidence、画像、风险结果等JSON契约|
|`prompts/`|A1、A2、A3、A5提示词；A3结构修复提示词单独保存|
|`fixtures/`|合成对话与固定回放输入，不能当作真实模型准确率证明|
|`examples/`|完整输出示例和E03/D04接口示例|
|`tests/`|配置、控制器、A3校验、CLI和回放测试|
|`docs/`|使用、配置、标注、验证、迁移和接口说明|

## 3. 运行命令

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
python run.py interview --plan s01 --llm-config config/llm.local.json
python run.py dialogue-profile --run-dir outputs/某次运行
python run.py risk --run-dir outputs/某次运行
python run.py report --run-dir outputs/某次运行
```

`dialogue-replay`不调用LLM；`interview`才会使用本地LLM配置。回答“不清楚”“不想回答”或`/skip`会保留为信息不足；简略回答最多换角度追问一次，仍无有效信息则进入下一测量单元；`/stop`会保存快照并暂停。

## 4. 0.5主要改动

- PV01—PV10保留核心变量，同时按facet保存证据和覆盖状态。
- 区分`hypothetical_intent`、`habitual_self_report`、`real_event_self_report`等来源框架。
- 区分自身、他人、群体主体及过去、当前、未来时间范围。
- 保护性变量在A4中反向转换，避免保护能力增加风险分数。
- 缺失值保持`null`，不以0.5填充；证据覆盖度低于40%时输出“无法判断”。
- 角色风险支持值按配置权重计算；三类角色保留身体、言语、关系三种形式的结果位置。
- 报告显示回答简略度、低信息轮次、覆盖缺口、每个变量的原话证据和工程预警阈值。

## 5. 风险阈值

当前仅为流程测试建议值：施暴和受害 `0–0.35` 为低、`0.35–0.65` 为关注、`>0.65` 为高；施暴与受害兼有 `0–0.40` 为低、`0.40–0.70` 为关注、`>0.70` 为重点关注。正式使用前必须依据人工标注样本重新校准。

## 6. 输出文件

- `dialogue_state.json`：可恢复的完整状态快照。
- `coverage_report.json`：测量单元状态、缺失槽位、情境形式和回答质量。
- `validated_evidence.json`：通过契约校验的Evidence和背景信息。
- `profile.json`：十变量、facet、测量组、覆盖度和证据台账。
- `risk_model_input.json`：提供给A4的只读输入。
- `risk_result.json`：三角色及身体/言语/关系形式结果。
- `report_narrative.json`：A5结构化解释。
- `report.md`：交接和业务人员可读的完整报告。

## 7. 当前验证状态

配置检查和`S01`、`full`合成回放已通过，full回放为56轮并生成完整报告。合成回放只证明工程链路，不证明真实GLM的抽取准确性。真实使用前还需建立各facet的人工金标准样本，并评估准确率、召回率、误报率和不同群体的一致性。
