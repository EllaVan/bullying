# 心理 Agent 情景多轮对话实验（0.3.0）

本项目依据已上传的《心理Agent+量表与心理变量.md》，在本地运行“情境生成 → 多轮提问 → 证据观察与校验 → 十变量画像 → 三角色风险线索解释”。四个 Agent、测量控制器和风险引擎均有独立接口，不需要系统后端。使用 Python 3.10+，仅依赖标准库。

原定义保留 10 个心理变量、30 道题和 6 类情境。本版本用 30 个测量单元组织 26 道核心题；F01—F04 只接收自发背景。E03/D04 等题按情境选择部分变量，原题映射不变。

默认风险输出是施暴、受害、两者兼有三种角色的证据画像。没有配置训练好的风险模型时，概率、置信度和变量数值均为 `null`；外部模型接入接口已经实现。

## 先运行完整离线示例

解压后进入 `psych_agent_round1` 目录：

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
```

输出目录需为新目录，也可省略 `--output` 自动命名。`s01` 回放 6 轮，`full` 回放 56 轮；全部使用明确标记的合成问答和候选响应，不调用 LLM。查看输出目录中的 `report.md`、`coverage_report.json` 和 `profile.json`。交付包的 `examples/dialogue_full/` 已含完整示例。

## 用自己的 API 开始多轮对话

将原来已能运行 `extract` 的 `llm.local.json` 放入本项目 `config/` 目录，然后执行：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py interview --plan s01 --llm-config config/llm.local.json
```

确认 S01 对话衔接后，用 `--plan balanced` 运行涉及十变量的四情境计划。该计划有 28 轮上限，未完成内容会明确保留缺口。`full` 计划用于完整功能实验，可能较长。

默认 A1/A4 使用模板，A2/A3 调用 LLM。A1/A4 的 LLM 实现也已完成，可通过 `--agents-config config/agents.local.json` 分别选择，配置样例为 `config/agents.example.json`。每个 Agent 可使用不同的 API 配置。

输入 `/skip` 跳过当前问题，`/stop` 结束，Ctrl+C 暂停。连接或抽取出错后保留已有问题和回答，不自动重试；恢复命令为：

```bash
python run.py interview --resume outputs/实际运行目录 --llm-config config/llm.local.json
```

## 文件与接口

| 路径 | 职责 |
| --- | --- |
| `config/` | 原题、变量、情境绑定、测量单元、规则和访谈计划 |
| `psych_agent/dialogue_contracts.py` | Agent 和风险引擎协议、观察校验 |
| `psych_agent/measurement_controller.py` | 测量状态、缺口、追问和停止 |
| `psych_agent/scenario_agent.py`、`interviewer.py`、`turn_extractor.py`、`risk_reporter.py` | 四 Agent 的独立实现 |
| `psych_agent/profile.py`、`risk_engine.py` | 确定性画像和独立风险接口 |
| `psych_agent/dialogue_runner.py`、`dialogue_cli.py` | 本地编排、保存与命令行 |
| `prompts/`、`schemas/` | 各 Agent 提示词和接口结构 |
| `fixtures/dialogue/`、`tests/` | 五套固定回放及功能测试 |
| `examples/dialogue_full/` | 完整画像、报告及第一轮单 Agent 输入输出示例 |
| `docs/`、`source/` | 运行与接口说明、本轮功能报告、原设计附件 |

独立命令为 `scenario`、`ask`、`observe`、`dialogue-profile`、`risk`、`report`。完整参数与可复制命令见 [多轮运行说明](docs/multiturn_usage.md)。边界与扩展方式见 [Agent 接口](docs/agent_interfaces.md)。

旧 `validate / replay / prepare-prompt / extract / aggregate / doctor` 保持可用，原默认七题与聚合规则保留。旧格式与新多轮格式分别处理；旧命令说明在 [旧版使用记录](docs/legacy_round1_readme.md)。

## 本轮交付与验证

110 项测试通过，包括旧 69 项回归测试、全部访谈计划、恢复与证据边界，以及四 Agent 经本机模拟 HTTP 服务运行的完整链路。未使用用户的真实模型账号；未在 Windows 实机测试。

```bash
python -m unittest discover -s tests
```

[本轮修改、已完成与待完成功能报告](docs/round_0_3_report.md)明确列出实现范围和剩余工作，尤其是真实风险模型、计分与概率标定。`docs/change_report_template.md` 提供后续每轮修改的同结构报告模板。
