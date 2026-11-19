# 多轮访谈运行说明（0.3.0）

本版本在本地命令行验证情境生成、连续提问、证据提取、画像组织和风险结果解释。所有命令在解压后的 `psych_agent_round1` 目录运行，Python 3.10+，只依赖标准库。实际测试环境为 Linux / Python 3.12。

## 1. 先跑不需要 API 的完整链路

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
```

输出目录必须是新目录；再次执行时换一个名称，或者省略 `--output` 自动生成目录。`dialogue-replay` 使用人工预制、严格配对的问答和 A3 响应，不调用 LLM，不对任意输入做关键词推断。所有模拟结果标记 `synthetic: true`。

`s01` 示例为 6 轮，`full` 示例为 56 轮。完整回放包含 6 类情境和 3 种霸凌形式；55 个计划内单元实例中，53 个适用单元完成，2 个按条件标为不适用。不适用不等于“没有风险”。交付包的 `examples/dialogue_full/` 已附一次完整结果，无需先配置 API 即可查看。

## 2. 接入现有 API 进行真实对话

将原来已经能运行 `extract` 的 `llm.local.json` 放在新项目的 `config/` 目录。没有配置文件时，可复制 `config/llm.example.json` 后填写自己的接口、模型和密钥来源。本次交付不包含本地密钥。

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py interview --plan s01 --llm-config config/llm.local.json
```

`doctor` 不带 `--connect` 只检查配置；`interview` 会实际调用所配置的模型服务。先用 `s01` 观察问题衔接，再运行：

```bash
python run.py interview --plan balanced --llm-config config/llm.local.json
```

默认 A1 使用固定情境模板，A2 使用 LLM 提问，A3 使用 LLM 抽取，A4 使用确定性的报告模板。四个 Agent 的 LLM 实现都已提供。若要分别配置模型，将 `config/agents.example.json` 复制为 `config/agents.local.json`，调整各 Agent 的 `backend`（`template` 或 `llm`）和 `llm_config`，然后运行：

```bash
python run.py interview --plan s01 --agents-config config/agents.local.json
```

这些路径相对项目根目录。A3 的真实访谈模式必须使用 LLM；离线验证走独立的回放命令。A1/A2/A4 可独立选择模板或 LLM。API 配置的环境变量优先级和网络诊断沿用旧版，详见 `llm_connection_troubleshooting.md`。四 Agent 的 HTTP 调用链已经通过本机模拟服务验证，但未使用你的账号连接智谱服务。

## 3. 选择访谈计划

| 计划             | 情境和范围                                      | 总轮数上限 | 固定回放轮数 |
| ---------------- | ----------------------------------------------- | ---------: | -----------: |
| `s01`          | S01；原七题、四变量，8 个测量单元               |         12 |            6 |
| `s01_extended` | S01 增加 E02/E03/D04；普通同学条件下 D04 不适用 |         15 |            8 |
| `s01_friend`   | S01 朋友冲突条件；D04 在本轮仅对应 PV10         |         15 |            9 |
| `balanced`     | S01/S03/S05/S06；计划涉及全部十变量             |         28 |           28 |
| `full`         | S01—S06；用于完整功能实验                      |        108 |           56 |

轮数包含每个情境的开放回答。`balanced` 每个情境最多 7 轮，预算可能先于全部单元完成，此时如实保留缺口。`full` 的 108 轮是工程上限，不是建议施测时长。可用 `--max-turns` 缩短一次新访谈的总预算；它不会放宽完成单元所需的信息要求。

运行时输入 `/skip` 跳过当前问题，输入 `/stop` 结束并生成已有画像，按 Ctrl+C 暂停。单元的定向提问默认最多 2 次；已完成或已拒答的单元不强制重问。

## 4. 输出文件与续跑

| 文件或目录                               | 内容                                             |
| ---------------------------------------- | ------------------------------------------------ |
| `scenarios/`                           | A1 生成并冻结的情境实例、条件和事实              |
| `turns/T001/` 等                       | 当轮任务、问题与回答、上下文、A3 候选、校验结果  |
| `checkpoints/`                         | 真实访谈的连续编号快照，每份独立保存             |
| `dialogue_state.json`                  | 正常结束、暂停或出错时发布的总快照               |
| `conversation_trace.jsonl`             | 已完成轮次的问题和回答                           |
| `coverage_report.json`                 | 单元状态、缺失信息、情境覆盖和停止原因           |
| `profile.json`                         | 十变量画像；保留来源、条件、原题、方向和缺口     |
| `validated_evidence.json`              | 经结构、引用和范围校验的证据及独立背景记录       |
| `risk_model_input.json`                | 给风险模型的标准输入及输入指纹；排除 F 类背景    |
| `risk_result.json`                     | 三种角色的相关因素，或通过接口校验的外部模型结果 |
| `report_narrative.json`、`report.md` | A4 的解释结构与可读报告                          |
| `llm_calls/`                           | 分 Agent、分请求保存提示词、原始响应和解析结果   |
| `error.json`、`errors/`              | 最近错误及逐次错误记录                           |

真实访谈过程中优先保存独立快照，避免把唯一的恢复状态反复覆盖。API 请求失败不会自动重试。修好连接或输出配置后，明确续跑：

```bash
python run.py interview --resume outputs/实际运行目录 --llm-config config/llm.local.json
```

传入运行目录或总快照时，程序优先选择最近编号的快照；也可指定某一 `checkpoints/000123.json`。已记录的问题和回答会保留，不要求学生为一次 A3 请求失败重新回答。续跑沿用原计划、会话编号和预算，不可同时覆盖这些参数。测量配置或提示词改变后不套用旧快照；修复 API 配置不改变测量指纹。

`/stop` 后或全部完成的访谈不再续跑。若仅 A4 生成报告失败，可使用独立 `report` 命令；也可以从快照重新生成默认画像和报告：

```bash
python run.py dialogue-profile --state-file outputs/demo_full/dialogue_state.json --output outputs/recomputed_full
```

## 5. 单独验证每个接口

以下命令复用交付包内的合成示例，每个步骤都可以单独执行：

```bash
python run.py scenario --plan s01 --output outputs/only_a1
python run.py ask --task-file examples/dialogue_full/turns/T001/task.json --history-file examples/dialogue_full/turns/T001/history.json --output outputs/only_a2
python run.py observe --task-file examples/dialogue_full/turns/T001/task.json --turn-file examples/dialogue_full/turns/T001/input.json --history-file examples/dialogue_full/turns/T001/history.json --response-json examples/dialogue_full/turns/T001/candidate_result.json --output outputs/only_a3
python run.py risk --profile-file examples/dialogue_full/profile.json --output outputs/only_risk
python run.py report --profile-file examples/dialogue_full/profile.json --risk-file examples/dialogue_full/risk_result.json --output outputs/only_a4
```

`scenario`、`ask`、`report` 加 `--llm-config config/llm.local.json` 可切换到各自的 LLM 实现。`observe` 要实际抽取时，用 `--llm-config` 替代 `--response-json`。不要将一个学生、情境或配置版本的候选结果用于另一个任务。

## 6. 风险模型接入

默认风险引擎只组织原变量表中的角色相关因素，三种概率和置信度均为 `null`。有训练好的模型时，让模型读取 `risk_model_input.json`，输出符合 `schemas/risk_prediction.schema.json` 的 JSON，然后执行：

```bash
python run.py risk --profile-file examples/dialogue_full/profile.json --prediction-file examples/dialogue_full/synthetic_prediction.json --output outputs/model_contract_demo
```

这里的 `synthetic_prediction.json` 是明确标记的接口示例；数值是人工设置的模拟输入，不是对样例学生的预测，不能套用到真实访谈。真正接入时使用模型自己的输出。程序校验会话、输入指纹、模拟标记、概率范围和三角色之间的概率关系。接口含义和代码注入方式见 `agent_interfaces.md`。

## 7. 旧命令与配置维护

旧 `validate`、`replay`、`prepare-prompt`、`extract`、`aggregate`、`doctor` 保持可用。原 S01 七题范围及旧聚合规则未改变。旧单案例格式与新多轮观察格式不同，不要把新的 `candidate_result.json` 交给旧 `aggregate`。旧命令完整说明见 `legacy_round1_readme.md`。

新配置中的题目、变量和规则映射是显式编写的。`scripts/build_measurement_config.py` 是维护者重建派生配置的脚本；普通运行不需要执行。它会重写受管理配置，因此人工调整配置后不要无意运行它。配置改变后，执行 `dialogue-validate`，更新对应问答样例，再运行相关测试。

```bash
python -m unittest discover -s tests
```

每次修改按 `change_report_template.md` 更新修改、已完成和待完成功能报告。本轮记录见 `round_0_3_report.md`。
