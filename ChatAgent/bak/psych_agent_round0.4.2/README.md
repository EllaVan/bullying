# 心理 Agent 情景多轮对话实验（0.4.2）

本项目依据 `source/心理Agent+量表与心理变量.md`，在本地验证“情境生成 → 多轮提问 → 证据抽取与校验 → 十变量画像 → 三角色及三种形式风险计算 → 报告”。不包含系统后端、数据库、账号、部署或自动干预。

0.4.2 使用 `CFG_005` 配置集合，保留 10 个心理变量、30 道原题、30 个测量单元、69 条多轮规则和 6 类校园情境。F01—F04 只记录自发背景，不进入变量和风险计算。E03、D04 等部分映射继续由情境绑定和测量单元共同限制。

## Agent 分工

| Agent/模块 | 职责                                         |
| ---------- | -------------------------------------------- |
| A1         | 根据固定蓝图生成情境文字，不能改变事实       |
| A2         | 根据当前测量目标和缺失信息提出一个问题       |
| A3         | 从本轮回答提取候选观察、原话、槽位和证据规则 |
| 画像模块   | 确定性汇总十个心理变量及覆盖缺口             |
| A4         | 等权流程测试或外部模型风险计算               |
| A5         | 只读解释画像和A4结果，不修改数值             |

当前十个变量的 `confidence` 固定为 `1.0`，变量权重也固定为 `1.0`。默认A4会输出未校准的测试概率和置信度，用于打通完整产品流程；所有相关文件均标记 `human_review_required` 和 `uncalibrated_flow_test`。这些数值不是已经验证的心理测量结论，也不能作为自动决策依据。

## 离线运行

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
python -m unittest discover -s tests
```

前两套回放不调用LLM。`s01` 为6轮；`full` 为56轮，覆盖6类情境、身体/言语/关系三种形式及十变量。预制回答和A3结果是合成功能样例，不代表真实抽取准确率。

## 接入现有LLM配置

将自己的 `config/llm.local.json` 放入项目后运行：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py interview --plan s01 --llm-config config/llm.local.json
```

默认A1/A5使用模板，A2/A3调用LLM，A4在本地执行等权测试计算。使用 `config/agents.example.json` 可以分别配置A1/A2/A3/A5；A4读取 `config/risk_scoring.json`，不允许LLM直接猜测概率。

输入 `/skip` 跳过当前题，`/stop` 结束，Ctrl+C暂停。网络失败不会自动重试。A3会先删除当前轮次、未来轮次或不同情境的非法上下文引用；其余结构不合规时执行至多一次可审计修复，仍失败则安全提交空观察并继续，不伪造证据。低信息回答会换角度追问一次，仍未取得信息则继续下一测量单元。

`coverage_report.json` 和 `report.md` 会统计回答简略度。去除空白后不超过6个字符记为简略回答；严格超过50%时提示画像可能受信息不足影响。该指标只描述文本长度，不推断拒绝、欺骗或“不配合”动机。

恢复命令：

```bash
python run.py interview --resume outputs/实际运行目录 --llm-config config/llm.local.json
```

## 主要文件

| 路径                              | 内容                                       |
| --------------------------------- | ------------------------------------------ |
| `config/config_manifest.json`   | 当前配置集合编号及所有配置路径             |
| `config/measurement_units.json` | 原题派生的多轮测量单元                     |
| `config/dialogue_rubric.json`   | A3允许使用的证据规则                       |
| `config/variable_scoring.json`  | 变量测试值和等权配置                       |
| `config/confidence_policy.json` | 固定置信度1.0及人工复核声明                |
| `config/risk_scoring.json`      | A4三角色、三形式、保护/风险方向配置        |
| `config/report_policy.json`     | A5报告边界                                 |
| `config/interview_policy.json`  | 单元追问上限、完整流程预算和回答简略度策略 |
| `examples/dialogue_full/`       | 0.4完整合成画像、风险结果和报告            |
| `docs/round_0_4_report.md`      | 0.4.0完整流程报告                          |
| `docs/round_0_4_1_report.md`    | A3联机结构修复补丁报告                     |
| `docs/round_0_4_2_report.md`    | A3安全降级、追问和简略度报告               |

0.4业务输出不再保存配置哈希、画像哈希或输入哈希，改用 `config_set_id`、`profile_id`、`model_input_id`、文件路径和会话编号。修改任何受管理配置时必须创建新的 `config_set_id`。

完整命令见 `docs/multiturn_usage.md`，接口边界见 `docs/agent_interfaces.md`。旧单案例命令仍可使用，说明保存在 `docs/legacy_round1_readme.md`。
