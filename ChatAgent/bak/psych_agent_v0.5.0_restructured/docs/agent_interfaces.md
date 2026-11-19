# Agent接口与测量边界（0.5.0）

## 完整链路

| 接口 | 输入 | 输出 | 不负责 |
| --- | --- | --- | --- |
| A1 `generate(task)` | 情境蓝图和条件 | 情境文字、冻结事实 | 选择变量、计算风险 |
| A2 `ask(task, history)` | 当前单元、缺失槽位、历史 | 一个问题 | 判分、提取证据 |
| A3 `extract(task, turn, history)` | 问题、回答、允许单元和规则 | 候选观察和逐字原话 | 更改映射、计算概率 |
| 画像 `build_profile(state,cfg)` | 经校验观察 | 十变量画像 | 生成新证据 |
| A4 `assess(profile)` | 只读画像 | 三角色与三形式风险结果 | 解释报告、修改A3证据 |
| A5 `report(profile,risk)` | 只读画像和A4结果 | 引用已有证据的说明 | 重新计算或修改概率 |

协议位于 `psych_agent/dialogue_contracts.py`。A1、A2、A3、A5均有独立命令和LLM适配器；A4默认是确定性的 `TestRiskScoringAgent`，外部模型通过 `ExternalPredictionRiskScoringAgent` 接入。

A3边界错误采用保守容错：非法历史引用由确定性代码删除；一次模型修复后仍不合法则返回空观察。空观察只代表本轮没有可提交证据，不会生成低风险值。控制器把低信息目标回答标记为待补充，换角度追问一次后继续下一个单元。A3诊断与测量状态分开保存，Agent仍无权修改计划或覆盖状态。

## 量表到画像

配置链为：

`questionnaire_mapping.json` → `scenario_blueprint.json` → `measurement_units.json` → `dialogue_rubric.json` → `interview_policy.json`。

程序校验原题、变量、情境和规则不能越界。E03可在S01扩展计划中启用；D04保留PV08/PV10原始映射，但S01朋友条件仅选择PV10。F01—F04只记录自发背景。

画像按变量、测量单元、事件、情境条件、参照方式和参照时期分组。重复原话保留来源但不增加测试权重；不同条件或不同方面分别保存；第三方和来源不清内容不进入核心画像。

## 测试计分和置信度

0.4将方向证据转换为变量流程测试值：higher=1、lower=0、同组冲突=0.5。变量缺失时 `value=null`，但根据本轮明确要求，十变量 `confidence=1.0`。输出同时写入：

```json
{
  "confidence_mode": "fixed_test_value",
  "scoring_status": "uncalibrated_flow_test",
  "human_review_required": true
}
```

所以1.0只用于检查接口和页面能否接收数字，不表示模型完全确定。

## A4风险计算

A4配置位于 `config/risk_scoring.json`。每个变量权重暂时相同，风险因素直接使用变量值，保护因素使用 `1-value`。分别输出：

- 施暴边际测试概率；
- 受害边际测试概率；
- 施暴且受害联合测试概率；
- 身体、言语、关系三种形式下的对应测试值。

联合值必须位于两个边际概率允许范围内。默认模式为 `heuristic_equal_weight_test_only`，不能用于正式判断。外部模型接口使用 `session_id`、`profile_id`、`model_input_id`、`config_set_id`和文件路径关联输入，不使用哈希。

## A5报告

A5必须逐变量说明，并且证据编号属于对应变量；三个角色只能引用A4提供的因素编号。固定模板和LLM解释均展示测试声明。报告同时展示简略回答、低信息回答、换角度追问和A3降级次数；简略度超过50%只触发信息不足提示。A5无权补出新变量、调整置信度、改变概率、诊断、推断被试动机或作自动干预决定。

正式产品接入模型时只替换A4，A1—A3和画像接口保持不变。人工重新校验置信度时修改 `confidence_policy.json` 并创建新的配置集合编号。
