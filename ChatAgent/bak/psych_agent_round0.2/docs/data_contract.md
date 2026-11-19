**第一轮输入输出约定**

一个case是一个合成受测者在S01中的完整实验记录。`turn_id`在case内唯一；同一事件的多轮追问使用同一`event_id`。不同case永不合并。本轮不保存学校账号、姓名或学号。

`response_context`由实验记录整理者填写，而不是由A3自行修改：hypothetical表示假设回答；real_event表示本人开始讲真实经历；mixed表示混合；general_opinion表示一般观点。即使是self_report，也只是本人陈述，未被外部核实。

| 输入字段 | 说明 |
|---|---|
| `case_id` | 字母、数字、下划线或短横线，1—64字符 |
| `scenario_id` | 第一轮固定S01 |
| `scenario_text` | 实验所用的完整情境文字 |
| `turns` | 问答数组，每条含轮次、问题编号、事件编号、question、answer和response_context |

A3输出按`schemas/extraction.schema.json`约束。例如：

```json
{
  "case_id": "S01_001",
  "evidence": [
    {
      "rule_id": "R_E01_HELP",
      "turn_id": "T1",
      "quote": "找老师",
      "source_kind": "hypothetical_intent",
      "subject": "self",
      "rationale": "明确表达向老师求助的意向，未证明已经获得支持。"
    }
  ],
  "gaps": [
    {
      "variable_id": "PV03",
      "reason": "当前回答没有归因信息。"
    }
  ]
}
```

这是候选片段的格式示例，完整S01_001参考回放包含多条证据。`gaps`用于说明抽取时的信息缺口；最终汇总仍独立计算每个变量是否有可用证据，不能用gaps强行覆盖已有证据。

程序根据rule_id生成variable_id、direction、item_ids和context_only，A3不能覆盖。程序还生成evidence_id、question_id、event_id和source_span。字符位置以Python Unicode码点计数，start包含、end不包含；若以后在JavaScript中定位含emoji文本，需要转换UTF-16索引，本轮不实现浏览器定位。

汇总输出中，每个变量都有value=null、confidence=null和观察组。状态含义如下：

| 状态 | 解释 |
|---|---|
| `insufficient_evidence` | 没有可归于本人、非背景的可用证据，不等于低分 |
| `ambiguous_evidence` | 有相关表达，但规则方向为unclear |
| `directional_evidence_observed` | 本次表达出现某个方向的候选信息，不等于稳定特质 |
| `multiple_directions_observed` | 保留多个方向的信息；需核对条件、事件和语境 |

`context_evidence`保存F类；`excluded_subject_or_source_evidence`保存第三方或主体/来源不明的记录；`evidence_ledger`保留全部已通过结构校验的证据。去重不会删除不同题目或规则的追溯信息，但不会把同一事件的多次复述算成多次独立观察。

校验器不自动评定“规则选择是否符合心理语义”，所有输出为`semantic_review_status: not_reviewed`。不能把字段校验当作心理有效性证明。
