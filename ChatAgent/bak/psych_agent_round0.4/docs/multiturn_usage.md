# 多轮访谈运行说明（0.4.0）

## 1. 功能验证

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan full --output outputs/demo_full
```

输出目录必须为空或不存在。完整回放产生：

- `dialogue_state.json`：可恢复的访谈状态；
- `coverage_report.json`：计划内单元的完成、拒答、不适用和缺失；
- `profile.json`：十变量测试值、固定测试置信度及证据组；
- `risk_model_input.json`：A4独立输入；
- `risk_result.json`：三角色总体及身体/言语/关系分项测试概率；
- `report_narrative.json`、`report.md`：A5解释；
- `turns/`：每轮任务、问答、A3候选和校验结果。

所有对象通过 `CFG_004`、会话编号、情境编号、变量编号和相对文件路径关联，不使用哈希字段。

## 2. 访谈计划

| 计划 | 用途 | 固定回放轮数 |
| --- | --- | ---: |
| `s01` | 原S01七题和四变量 | 6 |
| `s01_extended` | S01增加E02/E03/D04，普通同学条件下D04不适用 | 8 |
| `s01_friend` | 朋友冲突条件，D04本轮只对应PV10 | 9 |
| `balanced` | 四情境涉及十变量，预算结束保留缺口 | 28 |
| `full` | 六情境完整功能实验 | 56 |

`full` 的工程预算上限为108轮，不是推荐施测时长。覆盖率只表示信息槽位完成，不表示心理信度。

## 3. 真实交互与恢复

```bash
python run.py interview --plan s01 --llm-config config/llm.local.json
python run.py interview --plan balanced --llm-config config/llm.local.json
```

真实访谈中A2和A3默认使用LLM。A3没有关键词模板模式；离线测试必须使用固定回放。每个请求独立保存原始响应和解析结果，不保存API密钥。

```bash
python run.py interview --resume outputs/实际运行目录 --llm-config config/llm.local.json
```

恢复时读取最近的编号快照并逐轮重建校验。配置集合编号不同时拒绝续跑；修复API地址或密钥不改变测量配置集合。

## 4. 独立运行接口

```bash
python run.py scenario --plan s01 --output outputs/a1
python run.py ask --task-file examples/dialogue_full/turns/T001/task.json --history-file examples/dialogue_full/turns/T001/history.json --output outputs/a2
python run.py observe --task-file examples/dialogue_full/turns/T001/task.json --turn-file examples/dialogue_full/turns/T001/input.json --history-file examples/dialogue_full/turns/T001/history.json --response-json examples/dialogue_full/turns/T001/candidate_result.json --output outputs/a3
python run.py risk --profile-file examples/dialogue_full/profile.json --output outputs/a4
python run.py report --profile-file examples/dialogue_full/profile.json --risk-file examples/dialogue_full/risk_result.json --output outputs/a5
```

`risk` 默认运行A4等权测试计算。导入正式外部模型结果时使用：

```bash
python run.py risk --profile-file examples/dialogue_full/profile.json --prediction-file examples/dialogue_full/synthetic_prediction.json --output outputs/a4_external_contract_test
```

示例预测文件只验证接口，不是模型预测。正式文件必须使用自己的模型编号、目标、时间范围、概率和验证状态。

## 5. 测试数值的含义

- `variable.value`：higher=1、lower=0、同组冲突=0.5，再按不同测量组平均；缺失为null。
- `variable.confidence`：十个变量都固定为1.0，即使未观察也保留该测试占位值。
- `feature_weight`：十个变量全部为1.0。
- 保护因素由A4转换为 `1-value`，风险因素直接使用 `value`。
- A4先按变量等权计算角色和形式测试值，再约束“施暴且受害”不超过两个边际值。
- A4角色置信度暂时固定为1.0；没有可用特征时概率和角色置信度为null。

上述规则仅用于验证数据是否能从A3完整流向A5。正式产品必须经过人工审阅变量方向，并以训练、验证和校准后的风险模型替换默认A4。
