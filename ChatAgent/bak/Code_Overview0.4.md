# Psych Agent Round 0.4 — Code Overview 与使用报告

> 归档对象：`psych_agent_round0.4.zip`。压缩包内部项目根目录为 `psych_agent_round1/`；该目录名是历史遗留，实际包版本由 `psych_agent/__init__.py`、`README.md` 与 `config/config_manifest.json` 确认为 **0.4.0 / CFG_004**。

## 1. 报告范围与结论

本报告基于对压缩包内全部源码、配置、Prompt、Schema、合成数据、Fixtures、Examples、脚本、测试与文档的逐文件阅读，并结合实际执行结果整理。项目共 **132 个文件**；当前测试命令 `python -m unittest discover -s tests -q` 实际执行 **112 项测试，全部通过**。

当前0.4版本已经形成一个可在本地独立运行的工程闭环：

```text
量表/变量/情境配置
      ↓
MeasurementController（测量计划、槽位、覆盖、预算、恢复）
      ↓
A1 情境生成/冻结 → A2 单轮提问 → 学生回答 → A3 候选观察抽取
                                                ↓
                                   程序化证据校验与状态提交
                                                ↓
                                     十变量确定性画像 Profile
                                                ↓
                         A4 等权流程测试 / 外部模型预测适配器
                                                ↓
                                  A5 只读解释 → Markdown 报告
```

它是“Agent功能与数据契约验证工程”，**不是完整校园系统后端**：当前不包含数据库、账号权限、学校多租户、前端、线上部署、任务下发或自动干预。A4默认概率和confidence均是为了打通流程而设置的未校准测试值，不能视为已完成心理测量标定。

## 2. 代码组织与主次关系

代码中同时保留两套链路，这是交接时最需要区分的结构：

1. **0.4当前主流程**：`dialogue_config.py → measurement_controller.py → scenario_agent.py/interviewer.py/turn_extractor.py → dialogue_contracts.py → profile.py → risk_engine.py → risk_reporter.py → dialogue_runner.py`。新功能应优先在这条链路扩展。
2. **旧单案例兼容流程**：`config.py → extractor.py → evidence.py → aggregate.py`，对应旧 `case/extraction/summary` 数据和 `replay/extract/aggregate` 命令。它仍有回归测试，但不应被误认为0.4完整访谈主流程。

0.4配置关系建议理解为：

```text
psychological_variable.json
questionnaire_mapping.json
          ↓
scenario_blueprint.json
          ↓
measurement_units.json
          ↓
dialogue_rubric.json + dialogue_scenarios.json + interview_policy.json
          ↓
evidence_quality.json + variable_scoring.json
          ↓
risk_profile_rules.json + risk_scoring.json + confidence_policy.json
          ↓
report_policy.json

以上13份受管文件统一登记在 config_manifest.json（CFG_004）
```

一个重要实现细节：0.4按要求从**业务输出字段**中删除了配置哈希/画像哈希/输入哈希，但代码仍会使用SHA-256摘要生成稳定的 `event_id/observation_id/evidence_id/group_id` 等内部对象ID。这不是业务哈希版本控制；配置版本仍以 `config_set_id + 相对路径` 为准。

## 3. Agent职责与不可越界边界

| 模块                              | 输入                                    | 输出                         | 程序边界                                                                                                      |
| --------------------------------- | --------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| A1`scenario_agent.py`           | blueprint、scenario condition、允许单元 | 自然语言情境文本 + 原样facts | LLM不能新增/删除/改变facts；冻结后才可进入访谈                                                                |
| A2`interviewer.py`              | 当前task、缺失slot、必要history         | 单个问题                     | 只负责措辞与追问，不读取/修改风险结果，不评分                                                                 |
| A3`turn_extractor.py`           | 本轮问答、允许units/rules、必要history  | 候选observations/background  | 候选结果不直接可信，必须经`validate_turn()`                                                                 |
| 证据校验`dialogue_contracts.py` | A3候选 + 当前task                       | ValidatedTurn                | quote必须在当前回答唯一出现；rule/unit/item/variable必须白名单匹配；第三方/参照框架不合格证据不能进入核心画像 |
| Profile`profile.py`             | 已校验turns/evidence                    | 十变量画像                   | 确定性分组与均值，不调用LLM，不让LLM直接“总结一个分数”                                                      |
| A4`risk_engine.py`              | `risk_model_input`                    | 三角色/三形式风险结果        | 默认本地确定性测试；外部预测也必须满足严格契约和联合概率边界                                                  |
| A5`risk_reporter.py`            | profile + A4 result                     | narrative + report.md        | 只读解释；所有证据ID/factor ID必须来自输入；不能重算或修改概率                                                |

## 4. 测量、画像与风险计算语义

### 4.1 十个心理变量

| ID   | 变量                                       | 在当前工程中的主要作用                   |
| ---- | ------------------------------------------ | ---------------------------------------- |
| PV01 | 情绪调节 Emotion Regulation                | 冲突升级、施暴-受害转换相关保护/风险因素 |
| PV02 | 攻击倾向 Aggression                        | 施暴风险核心风险因素                     |
| PV03 | 敌意归因 Hostile Attribution               | 施暴-受害循环相关风险因素                |
| PV04 | 共情 Empathy                               | 施暴风险保护因素                         |
| PV05 | 道德脱离 Moral Disengagement               | 为伤害/排斥合理化的施暴风险因素          |
| PV06 | 支配 Dominance                             | 身体/关系控制与施暴相关                  |
| PV07 | 群体敏感/顺从 Group Sensitivity/Conformity | 关系性攻击、群体站队/顺从相关            |
| PV08 | 关系支持 Relational Support                | 受害持续风险的保护因素                   |
| PV09 | 排斥敏感 Rejection Sensitivity             | 受害与施暴-受害风险因素                  |
| PV10 | 求助与冲突解决 Help Seeking & Coping       | 三角色共享保护因素                       |

### 4.2 30个测量单元

0.4不是直接把30道原题逐题照问，而是把26个核心题拆成30个可追问单元；F01—F04只允许作为自发背景。关键拆分包括A02、B03、C05、G03等一题多facet，以及A04/D04/E04/E05等一单元多变量。完整单元定义以 `config/measurement_units.json` 为唯一运行时依据。

| Unit                     | 原题     | 目标变量   | 参照框架                 | facet                    |
| ------------------------ | -------- | ---------- | ------------------------ | ------------------------ |
| `U_A01_RECOVERY`       | A01      | PV01       | `habitual_self_report` | 情绪恢复过程             |
| `U_A02_ATTRIBUTION`    | A02, A03 | PV03       | `hypothetical_intent`  | 对他人意图的解释         |
| `U_A02_RUMINATION`     | A02      | PV03       | `habitual_self_report` | 认为被针对后的反复思考   |
| `U_A03_REVENGE`        | A03      | PV02       | `hypothetical_intent`  | 报复意向                 |
| `U_A04_PAUSE`          | A04      | PV01, PV10 | `hypothetical_intent`  | 暂停后再决策             |
| `U_B01_EMOTION`        | B01      | PV04       | `hypothetical_intent`  | 识别他人情绪             |
| `U_B02_CONCERN`        | B02      | PV04       | `hypothetical_intent`  | 对不亲近同学的痛苦关注   |
| `U_B03_HARM`           | B03      | PV04       | `hypothetical_intent`  | 玩笑中的感受与伤害       |
| `U_B03_JUSTIFICATION`  | B03      | PV05       | `general_belief`       | 玩笑是否可以继续的判断   |
| `U_B04_RESPONSIBILITY` | B04      | PV05       | `general_belief`       | 群体责任判断             |
| `U_B05_CONSEQUENCES`   | B05      | PV05       | `general_belief`       | 无身体伤害时的后果判断   |
| `U_C01_VOICE`          | C01      | PV06       | `hypothetical_intent`  | 对意见分量的重视         |
| `U_C02_REFUSAL`        | C02      | PV06       | `hypothetical_intent`  | 面对意见被拒绝           |
| `U_C03_DETERRENCE`     | C03      | PV06       | `general_belief`       | 威慑认知                 |
| `U_C04_DISSENT`        | C04      | PV07       | `hypothetical_intent`  | 群体中表达不同意见       |
| `U_C05_CONFORMITY`     | C05      | PV07       | `hypothetical_intent`  | 因关系压力而顺从         |
| `U_C05_REJECTION`      | C05      | PV09       | `hypothetical_intent`  | 对关系疏远的担忧         |
| `U_D01_EXCLUSION`      | D01      | PV09       | `hypothetical_intent`  | 被排除在活动外的担忧     |
| `U_D02_NO_RESPONSE`    | D02      | PV09       | `hypothetical_intent`  | 对未获回应的解释         |
| `U_D03_PEER_SUPPORT`   | D03      | PV08       | `habitual_self_report` | 同伴交流资源             |
| `U_D04_REPAIR`         | D04      | PV08, PV10 | `hypothetical_intent`  | 朋友关系修复预期         |
| `U_E01_CHANNEL`        | E01      | PV10       | `hypothetical_intent`  | 求助渠道认知             |
| `U_E02_EXPRESSION`     | E02      | PV10       | `task_performance`     | 向成年人说明情况         |
| `U_E03_BARRIER`        | E03      | PV10       | `hypothetical_intent`  | 向老师家长求助的顾虑     |
| `U_E04_DEESCALATION`   | E04      | PV01, PV10 | `hypothetical_intent`  | 避免争执升级             |
| `U_E05_PROTECTION`     | E05      | PV04, PV10 | `hypothetical_intent`  | 帮助他人与自我保护       |
| `U_G01_FORCE`          | G01      | PV02       | `general_belief`       | 强制或身体伤害的解决倾向 |
| `U_G02_VERBAL`         | G02      | PV02       | `general_belief`       | 尖锐语言回击的效用判断   |
| `U_G03_ALLIANCE`       | G03      | PV06       | `hypothetical_intent`  | 朋友支持与关系控制       |
| `U_G03_GROUP`          | G03      | PV07       | `hypothetical_intent`  | 朋友站队时的群体影响     |

### 4.3 Evidence进入画像的门槛

- A3只能产出候选观察，不能直接写画像。
- quote必须是**当前学生回答中的唯一原文片段**；程序保存unicode codepoint span。
- 当前task只允许访问白名单measurement unit与rule；A3不能自行扩展到“看起来相关”的变量。
- `subject=self` 且reference frame与该unit一致，才具有核心画像覆盖资格；朋友/第三方叙述会保留但不当作本人核心证据。
- `real_event_self_report`、`habitual_self_report` 与假设情境使用不同事件ID，防止把真实经历、习惯和当前假设场景混成同一次观察。
- F01—F04背景信息生成独立context记录，`context_only=true`、`included_in_core_or_risk=false`。
- 同一unit/事件/条件/参照框架/时期属于同一观察组，重复证据不会重复加权；相反方向可同时保留。

### 4.4 当前0.4测试计分

- 变量方向：higher=1、lower=0、mixed=0.5、unclear=null。
- 变量value：不同观察组测试值的平均，四舍五入4位；无可用证据为null。
- 变量confidence：当前十个变量全部固定1.0，即使未观察也保留该测试占位字段。
- A4所有特征权重均为1.0；风险因素用value，保护因素用 `1-value`。
- bully-victim联合概率执行Fréchet边界：不能高于两个边际概率，也不能低于数学下界。
- 输出字段虽然叫 `probability`，状态明确为 `test_probability_only / uncalibrated_flow_test / human_review_required`。

## 5. 运行与使用

### 5.1 环境

```bash
python --version   # 需要 Python 3.10+
python -m unittest discover -s tests -q
```

无强制第三方依赖。建议在项目根目录 `psych_agent_round1/` 执行命令。

### 5.2 离线验证

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
```

固定回放轮数：`s01=6`、`s01_extended=8`、`s01_friend=9`、`balanced=28`、`full=56`。其中full工程预算上限是108轮，只是上限而不是建议真实施测时长。

### 5.3 接入LLM

复制 `config/llm.example.json` 为 `config/llm.local.json`，填写模型名/endpoint；API Key优先使用环境变量，不建议写入文件。然后：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py interview --plan s01 --llm-config config/llm.local.json
```

默认实时链路：A1模板、A2 LLM、A3 LLM、A4本地等权测试、A5模板。`config/agents.example.json` 可分别切换A1/A2/A3/A5实现；A4概率不会交给LLM“自由猜测”。

交互控制：`/skip`跳过当前题，`/stop`结束，Ctrl+C暂停。API失败不会自动重试，避免重复请求与状态不一致。

### 5.4 恢复

```bash
python run.py interview --resume outputs/实际运行目录 --llm-config config/llm.local.json
```

恢复逻辑会从最新编号checkpoint读取历史并重新构造控制器，逐轮重放和重校验，再比较重算状态；因此不是简单“相信旧dialogue_state.json”。若 `config_set_id` 不一致会拒绝继续。

### 5.5 独立调用A1—A5

```bash
python run.py scenario --plan s01 --output outputs/a1
python run.py ask --task-file examples/dialogue_full/turns/T001/task.json --history-file examples/dialogue_full/turns/T001/history.json --output outputs/a2
python run.py observe --task-file examples/dialogue_full/turns/T001/task.json --turn-file examples/dialogue_full/turns/T001/input.json --history-file examples/dialogue_full/turns/T001/history.json --response-json examples/dialogue_full/turns/T001/candidate_result.json --output outputs/a3
python run.py risk --profile-file examples/dialogue_full/profile.json --output outputs/a4
python run.py report --profile-file examples/dialogue_full/profile.json --risk-file examples/dialogue_full/risk_result.json --output outputs/a5
```

外部A4模型契约测试：

```bash
python run.py risk --profile-file examples/dialogue_full/profile.json --prediction-file examples/dialogue_full/synthetic_prediction.json --output outputs/a4_external_contract_test
```

正式接入时必须替换成真实模型编号、目标、时间窗、概率、置信度和验证状态；示例 `synthetic_prediction.json` 只是接口样例。

## 6. 运行输出目录组织

一次0.4会话的关键运行产物组织如下：

```text
outputs/<run>/
├── dialogue_state.json          # 当前可恢复状态
├── conversation_trace.jsonl    # 公共逐轮轨迹
├── coverage_report.json        # 覆盖/缺口/不适用统计
├── profile.json                # 十变量画像
├── risk_model_input.json       # A4独立输入
├── risk_result.json            # A4结果
├── report_narrative.json       # A5结构化解释
├── report.md                   # 最终Markdown报告
├── validated_evidence.json     # 全部已校验证据
├── checkpoints/                # 只追加的编号快照
├── turns/Txxx/                 # 每轮task/history/input/candidate/validated
├── llm_calls/<role>/<request>/ # LLM请求审计；不保存API Key
└── errors/                     # 失败阶段记录，便于恢复和排查
```

写checkpoint使用临时文件 + `fsync` + `replace` 的原子写策略，降低中断时损坏状态文件的风险。

## 7. 全部文件说明

以下按要求使用**三级标题对应文件夹名**。表中的“当前性”用于交接时区分0.4主流程、兼容层、示例/生成物和历史文档。

### `/`

| 文件                 | 当前性/角色 | 用途                                                                                                                                                                      |
| -------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.gitignore`       | 工程基础    | Git忽略规则。排除`__pycache__/`、`*.pyc`、虚拟环境、`.env`、本地LLM密钥配置 `config/llm.local.json` 和运行输出 `outputs/`，防止缓存、凭证和运行产物进入版本库。 |
| `README.md`        | 当前入口    | 0.4.0 当前主入口说明。定义项目范围、A1—A5职责、离线/在线运行命令、主要配置与“未校准流程测试”边界。交接时应优先阅读。                                                   |
| `requirements.txt` | 工程基础    | 运行环境声明。项目要求 Python 3.10+，核心实现只使用标准库；LLM HTTP 调用基于`urllib`，没有必须安装的第三方SDK。                                                         |
| `run.py`           | 当前入口    | 唯一顶层可执行入口。仅导入`psych_agent.cli.main` 并将命令行参数交给CLI层，所有实际逻辑位于 `psych_agent/`。                                                           |

### `config/`

| 文件                             | 当前性/角色   | 用途                                                                                                                                                                                         |
| -------------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agents.example.json`          | LLM示例       | 多Agent运行方式示例。分别指定A1/A2/A3/A4/A5使用模板、LLM或本地测试计算；默认思路是A1模板、A2 LLM、A3 LLM、A4本地等权测试、A5模板。                                                           |
| `aggregation_rules.json`       | 兼容/历史配置 | 旧单案例链路的聚合配置（历史兼容）。只做证据描述与分组，不产生正式数值风险；与0.4主画像评分链路不同。                                                                                        |
| `confidence_policy.json`       | 0.4受管配置   | 0.4置信度测试策略。当前变量和有可用特征的角色置信度固定为1.0，并强制标记为测试占位、需人工复核；1.0不能解释为“完全确定”。                                                                  |
| `config_manifest.json`         | 0.4受管配置   | 0.4配置集合清单。当前`CFG_004 / 0.4.0`，列出13份受管配置及相对路径；任一受管配置修改后应创建新的 `config_set_id`。业务配置不保存配置哈希。                                               |
| `dialogue_rubric.json`         | 0.4受管配置   | 0.4 A3多轮证据规则，共69条。每条规则绑定测量单元、原题、心理变量、方向和解释边界；A3只能从当前测量单元允许的规则中选择。                                                                     |
| `dialogue_scenarios.json`      | 0.4受管配置   | 0.4可执行情境库，共6类校园情境及条件变体。保存冻结事实、关系、意图清晰度、冲突阶段、霸凌形式等，供A1和控制器判定单元适用性。                                                                 |
| `evidence_quality.json`        | 0.4受管配置   | 0.4证据质量/纳入策略。约束主体必须为self、可进入画像的参照框架、背景信息隔离、重复组不增权、矛盾方向同组取中值等。                                                                           |
| `evidence_rubric.json`         | 兼容/历史配置 | 旧单案例A3证据规则（19条，历史兼容）。用于`extract/replay/aggregate` 老链路，不是0.4多轮主流程的69条 `dialogue_rubric`。                                                                 |
| `interview_policy.json`        | 0.4受管配置   | 多轮访谈计划与控制策略。定义默认plan、每单元最大尝试次数、`s01/s01_extended/s01_friend/balanced/full`五套计划、停止/跳过命令及背景项策略。                                                 |
| `llm.example.json`             | LLM示例       | LLM连接配置模板。定义OpenAI风格`/chat/completions` 端点、模型、API Key环境变量、超时、JSON模式等；实际密钥应放在被Git忽略的 `config/llm.local.json` 或环境变量。                         |
| `measurement_units.json`       | 0.4受管配置   | 0.4核心测量单元定义，共30个。把30道原题中的26个核心题拆成可追问的“测量单元”，为每个单元定义目标变量、facet、参照框架、必需槽位、适用条件、提问模板和允许规则。F01—F04不作为主动测量单元。 |
| `psychological_variable.json`  | 0.4受管配置   | 十个心理变量的主定义文件（PV01—PV10）。保存中英文名称、含义、解释边界及与校园霸凌角色画像的关联说明。                                                                                       |
| `questionnaire_mapping.json`   | 0.4受管配置   | 30道原题到心理变量的基础映射。包含A/B/C/D/E/F/G题组；F01—F04为背景上下文项，不进入核心变量/风险计算。                                                                                       |
| `report_policy.json`           | 0.4受管配置   | A5报告边界。规定报告章节、必须引用证据和风险因素、必须展示置信度/测试状态，并禁止诊断、自动干预或越过A4修改数值。                                                                            |
| `risk_profile_rules.json`      | 0.4受管配置   | 角色—心理变量关联配置。定义施暴、受害、施暴-受害三类角色的主要变量及共享变量PV10，用于风险特征组织。                                                                                        |
| `risk_scoring.json`            | 0.4受管配置   | A4风险流程测试配置。定义三角色、身体/言语/关系三种形式、风险/保护因素方向、等权聚合、最少可用特征、联合概率约束和输出状态。                                                                  |
| `round1.json`                  | 兼容/历史配置 | 旧单案例/早期Round1作用域配置。保留S01四变量和题目范围，`risk_output_enabled=false`；0.4加载基础配置时仍用于兼容校验，但不是完整访谈plan。                                                 |
| `round1_extended.example.json` | 兼容/历史配置 | 旧链路扩展示例，展示E03/D04部分映射与作用域扩展方式；主要用于回归和理解历史设计，不应作为0.4主计划配置。                                                                                     |
| `scenario_blueprint.json`      | 0.4受管配置   | 六类情境的稳定蓝图及题目/变量绑定。位于原始量表映射与可执行`dialogue_scenarios` 之间，决定某情境可测哪些原题/变量。                                                                        |
| `variable_scoring.json`        | 0.4受管配置   | 画像变量测试值配置。方向映射为 higher=1、lower=0、mixed=0.5、unclear=null；按不同观察组等权平均，重复证据权重为0，十变量权重均为1.0。                                                        |

### `psych_agent/`

| 文件                          | 当前性/角色  | 用途                                                                                                                                                                                                |
| ----------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`               | 共享基础设施 | Python包标识，声明项目版本`__version__ = "0.4.0"`。                                                                                                                                               |
| `agent_transport.py`        | 共享基础设施 | LLM Agent传输封装。`JsonTransport` 将system/user内容发送给统一LLM客户端，要求JSON输出，并按角色/请求ID保存 messages、raw、parsed 审计文件；不做自动重试。                                         |
| `aggregate.py`              | 旧单案例兼容 | 旧单案例证据聚合器。把经过旧`evidence.py` 校验的证据按变量/事件分组，输出工程摘要；保持value/confidence为空，不参与0.4数值画像。                                                                  |
| `cli.py`                    | 共享基础设施 | 顶层CLI分发器。整合0.4多轮命令与旧单案例命令，并实现`doctor/validate/replay/prepare-prompt/extract/aggregate` 等历史入口。`run.py`最终进入这里。                                                |
| `config.py`                 | 旧单案例兼容 | 旧基础配置加载与交叉校验层。读取变量、题目、情境蓝图、旧证据规则和Round1作用域；提供`scenario_bindings()`、`allowed_rules()` 等，0.4 `dialogue_config.py` 会在其上继续扩展验证。              |
| `contracts.py`              | 旧单案例兼容 | 旧单案例JSON契约校验器。实现一个受控JSON Schema子集和形状验证；对不支持的schema关键字直接拒绝，保证旧链路输入边界明确。                                                                             |
| `dialogue_cli.py`           | 0.4主流程    | 0.4多轮CLI实现。注册并执行`dialogue-validate/dialogue-replay/interview/dialogue-profile/risk/report/scenario/ask/observe`，负责选择Agent实现、恢复点和独立A1—A5命令。                            |
| `dialogue_config.py`        | 0.4主流程    | 0.4配置总装载器和强一致性校验器。加载`CFG_004` 13份受管配置，校验30测量单元、69规则、6情境、plan、风险/报告策略及跨文件映射，向运行时提供统一 `DialogueConfig`。                                |
| `dialogue_contracts.py`     | 0.4主流程    | 0.4运行时数据契约核心。定义A1/A2/A3/A4/A5 Protocol、`ValidatedTurn`、动态Schema、问题与本轮观察校验；特别负责原话唯一定位、允许单元/规则、上下文引用、主体/参照框架和背景项边界。                 |
| `dialogue_runner.py`        | 0.4主流程    | 完整会话编排器。将控制器、A1、A2、用户输入、A3、画像、A4、A5串成闭环；按阶段写入turn文件、原子化checkpoint、错误文件，并支持离线ReplayBundle和中断恢复。                                            |
| `evidence.py`               | 旧单案例兼容 | 旧单案例证据验证器。验证case/extraction、quote定位、rule→item→variable映射、source_kind和主体等，生成带稳定ID的`ValidatedEvidence`。                                                            |
| `extractor.py`              | 旧单案例兼容 | 旧单案例A3 Prompt构造与文本抽取入口。把变量、题目、允许规则和学生回答组装为LLM消息，用于旧`extract` 命令。                                                                                        |
| `interviewer.py`            | 0.4主流程    | A2实现。`TemplateInterviewer`直接使用测量单元模板；`LLMInterviewer`只接收当前任务、缺失槽位与对话历史生成“一次一个问题”，不接触风险评分。                                                     |
| `io_utils.py`               | 共享基础设施 | 通用严格I/O工具。JSON读取支持UTF-8 BOM，拒绝重复键和NaN；JSON写入禁止NaN并统一格式；定义项目级`ValidationError`。                                                                                 |
| `llm_client.py`             | 共享基础设施 | 底层OpenAI兼容HTTP客户端与网络诊断。支持HTTPS远端/localhost HTTP、代理system/direct、API Key环境变量或文件、thinking开关、JSON mode、响应体上限和凭证脱敏；明确无自动重试。                         |
| `measurement_controller.py` | 0.4主流程    | 多轮测量状态机，也是会话状态唯一写入者。按plan选择情境/测量单元，维护not_asked/partial/covered/ambiguous/declined/not_applicable状态、槽位、尝试次数、预算、skip/stop，并通过逐轮重放实现可信恢复。 |
| `model_output.py`           | 共享基础设施 | LLM JSON输出解析器。只接受纯JSON或单个完整 ```json fenced block，拒绝夹杂解释文本/多代码块，随后交给严格JSON解析。                                                                                  |
| `profile.py`                | 0.4主流程    | 确定性十变量画像聚合器。只纳入通过主体与参照框架门槛的核心证据，按`(unit,event,condition,reference_frame,reference_period)` 分组，组内方向映射后再跨组求平均；生成coverage、证据台账和排除证据。  |
| `risk_engine.py`            | 0.4主流程    | A4核心。`TestRiskScoringAgent`执行未校准等权流程测试；`ExternalPredictionRiskScoringAgent`校验并接收外部真实模型预测契约；同时构造独立 `risk_model_input`、校验三角色联合概率和三种形式结果。 |
| `risk_reporter.py`          | 0.4主流程    | A5报告实现。模板或LLM只读解释profile与A4结果；严格校验十变量、三角色、证据ID和factor ID引用，最终渲染中文`report.md`，不能修改A4概率。                                                            |
| `scenario_agent.py`         | 0.4主流程    | A1实现。根据plan和固定蓝图构造scenario task；模板或LLM只可改写情境文本，`freeze_scenario()`强制事实集合完全不变，避免LLM改变测量条件。                                                            |
| `turn_extractor.py`         | 0.4主流程    | 0.4 A3 LLM适配器。向LLM提供当前情境事实、本轮问答、允许测量单元、相关规则/变量/原题及必要历史，返回候选observations/background，随后必须经过`dialogue_contracts.validate_turn()`。                |

### `prompts/`

| 文件                      | 当前性/角色     | 用途                                                                                                              |
| ------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------- |
| `evidence_extractor.md` | 兼容/历史Prompt | 旧单案例A3系统Prompt。要求只使用白名单变量/规则、保留原话、按限定gaps输出，不做诊断或风险推断。                   |
| `interviewer.md`        | 0.4主Prompt     | 0.4 A2系统Prompt。限定只负责自然提问与必要追问，不评分、不诊断、不根据风险结果驱动问题。                          |
| `report_agent.md`       | 0.4主Prompt     | 0.4正式A5系统Prompt。要求只读解释十变量画像和A4结果、引用既有证据/因素并保留人工复核警告。                        |
| `risk_reporter.md`      | 兼容/历史Prompt | 0.3时期/兼容用风险解释Prompt。0.4正式A5优先使用`report_agent.md`；该文件保留历史兼容与回溯。                    |
| `scenario_generator.md` | 0.4主Prompt     | 0.4 A1系统Prompt。允许把固定事实自然化为情境文本，但禁止新增、删除或改变facts。                                   |
| `turn_extractor.md`     | 0.4主Prompt     | 0.4 A3系统Prompt。规定本轮候选观察结构、当前回答原话引用、历史仅用于指代解析、白名单单元/规则和F01—F04背景处理。 |

### `schemas/`

| 文件                             | 当前性/角色  | 用途                                                                                                                                    |
| -------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `case.schema.json`             | 旧单案例契约 | 旧单案例输入Schema：case_id、scenario_id、scenario_text、turns。                                                                        |
| `dialogue_state.schema.json`   | 0.4公开契约  | 0.4可恢复会话状态Schema。定义session、plan、inventory、scenario/turn历史和运行状态；实际恢复时还会逐轮重放，不能只信任该JSON。          |
| `extraction.schema.json`       | 旧单案例契约 | 旧单案例A3输出Schema：case_id、evidence、gaps。                                                                                         |
| `profile.schema.json`          | 0.4公开契约  | 0.4十变量画像公开Schema，描述variables、coverage、evidence ledger、context、scenario instances等输出结构。                              |
| `question_task.schema.json`    | 0.4公开契约  | 0.4 A2/A3问题任务Schema。描述当前scenario、target unit、missing slots、allowed units等；运行时还会校验其必须是当前配置的精确投影。      |
| `risk_model_input.schema.json` | 0.4公开契约  | A4独立模型输入Schema，使画像层与风险模型层解耦，便于以后替换真实模型。                                                                  |
| `risk_prediction.schema.json`  | 0.4公开契约  | 外部A4预测结果契约Schema。要求session/profile/model input/model id/目标/时间窗/三角色概率与置信度等，并由代码继续做联合概率和归属校验。 |
| `risk_result.schema.json`      | 0.4公开契约  | A4标准输出Schema，统一本地测试计算和外部模型适配后的三角色、三形式、因素、状态字段。                                                    |
| `turn_observation.schema.json` | 0.4公开契约  | 0.4 A3候选输出Schema的公开版，定义turn_id、observations、background；真正白名单会在运行时按当前任务动态收窄。                           |

### `data/`

| 文件                            | 当前性/角色  | 用途                                                                                                                                 |
| ------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| `README.md`                   | 合成开发数据 | 合成开发数据说明。明确这些case/annotation仅用于工程验证，不是人工金标准、真实学生数据或模型效果评估集。                              |
| `cases.dev.jsonl`             | 合成开发数据 | 16个S01合成开发case，覆盖暂停/求助、敌意归因、报复、攻击、恢复、第三方、条件假设、背景、自主拒答、prompt injection和矛盾方向等边界。 |
| `reference_annotations.jsonl` | 合成开发数据 | 与16个case对应的预期规则ID草案，用于工程对照；reviewed_by/notes保留人工审阅位置，不应当成已验证标签。                                |
| `single_case.json`            | 合成开发数据 | S01_001的便捷单案例输入，供旧`prepare-prompt/extract/replay/aggregate` 链路快速演示。                                              |

### `fixtures/dialogue/`

| 文件                  | 当前性/角色 | 用途                                                                                                   |
| --------------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| `s01.json`          | 0.4固定回放 | 固定离线回放bundle：plan=s01，共6轮，用于最小S01多轮链路验证。                                         |
| `s01_extended.json` | 0.4固定回放 | 固定离线回放bundle：plan=s01_extended，共8轮；普通同学条件下D04应判not_applicable。                    |
| `s01_friend.json`   | 0.4固定回放 | 固定离线回放bundle：plan=s01_friend，共9轮；朋友冲突条件使D04适用，并验证本轮受情境绑定约束。          |
| `balanced.json`     | 0.4固定回放 | 固定离线回放bundle：plan=balanced，共28轮，覆盖四类情境和十变量但允许预算结束后保留缺口。              |
| `full.json`         | 0.4固定回放 | 固定离线回放bundle：plan=full，共56轮，覆盖6情境、三种霸凌形式和十变量，是0.4完整闭环的主回归fixture。 |

### `fixtures/replay/`

| 文件             | 当前性/角色        | 用途                                                                           |
| ---------------- | ------------------ | ------------------------------------------------------------------------------ |
| `S01_001.json` | 旧单案例固定A3响应 | “先离开、冷静、找老师”——验证调节/求助证据，不自动推断攻击或敌意。          |
| `S01_002.json` | 旧单案例固定A3响应 | 明确敌意归因——验证PV03对应规则。                                             |
| `S01_003.json` | 旧单案例固定A3响应 | 保留替代性解释——验证较低敌意归因。                                           |
| `S01_004.json` | 旧单案例固定A3响应 | 表达报复意向——验证攻击倾向，但不自动把报复等同于敌意归因。                   |
| `S01_005.json` | 旧单案例固定A3响应 | “更强/更厉害”类模糊表达——验证不越界推断。                                  |
| `S01_006.json` | 旧单案例固定A3响应 | 明确推搡/身体动作——验证明确攻击证据。                                        |
| `S01_007.json` | 旧单案例固定A3响应 | 明确拒绝伤害——验证相反方向证据。                                             |
| `S01_008.json` | 旧单案例固定A3响应 | 情绪恢复困难——验证PV01方向。                                                 |
| `S01_009.json` | 旧单案例固定A3响应 | 不知道/缺少求助渠道——验证PV10较低方向。                                      |
| `S01_010.json` | 旧单案例固定A3响应 | 先暂停再决定——同一回答可分别命中PV01和PV10，验证一段原话映射到不同合法规则。 |
| `S01_011.json` | 旧单案例固定A3响应 | 叙述朋友/第三方行为——验证subject非self不能进入本人核心画像。                 |
| `S01_012.json` | 旧单案例固定A3响应 | 条件式“如果他是故意的……”——验证不能自动当作实际敌意归因事实。             |
| `S01_013.json` | 旧单案例固定A3响应 | 提到老师支持——验证F02背景证据单独保存、不进入核心变量/风险。                 |
| `S01_014.json` | 旧单案例固定A3响应 | 拒答/未知——验证gap和无证据处理。                                             |
| `S01_015.json` | 旧单案例固定A3响应 | 回答中包含prompt injection式文本——验证把学生文本当数据而非指令。             |
| `S01_016.json` | 旧单案例固定A3响应 | 同一案例出现相反方向——验证保留矛盾/多方向证据而不是覆盖或判断撒谎。          |

### `examples/`

| 文件                                | 当前性/角色 | 用途                                                                                                                       |
| ----------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------- |
| `E03_D04.case.json`               | 旧链路示例  | 旧链路“部分映射”案例输入：E03求助顾虑 + D04朋友关系修复，专门验证同一PV10可出现不同方向且不强行互相覆盖。                |
| `E03_D04.extraction.json`         | 旧链路示例  | 上述案例的旧A3候选抽取示例，包含R_E03_HELP_BARRIER与R_D04_REPAIR_EXPECTATION及变量缺口。                                   |
| `E03_D04.summary.json`            | 旧链路示例  | 上述案例经旧聚合器得到的工程摘要。PV10呈现multiple_directions_observed，value/confidence仍为null，说明旧链路只做证据描述。 |
| `S01_001.summary.json`            | 旧链路示例  | 旧S01_001案例聚合输出示例，展示PV01/PV10方向证据、证据台账和gap，不做风险数值。                                            |
| `S01_001.validated_evidence.json` | 旧链路示例  | 旧S01_001经白名单、原话与映射校验后的证据清单，供旧聚合示例复现。                                                          |

### `examples/dialogue_full/`

| 文件                          | 当前性/角色     | 用途                                                                                                                                                  |
| ----------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `conversation_trace.jsonl`  | 0.4完整闭环示例 | 0.4`full` 合成回放的56轮公共对话轨迹，每行一轮，便于重放、审计和外部分析。                                                                          |
| `coverage_report.json`      | 0.4完整闭环示例 | 完整回放的覆盖报告：56轮回答、计划55个测量单元实例，53 covered、2 not_applicable；同时汇总身体/言语/关系三种形式覆盖。                                |
| `dialogue_state.json`       | 0.4完整闭环示例 | 完整回放最终可恢复状态。包含plan、情境实例、单元inventory、turns、状态和计数；可用于验证恢复/重算。                                                   |
| `profile.json`              | 0.4完整闭环示例 | 完整回放十变量画像。示例value：PV01=1、PV02=0、PV03=0.5、PV04=1、PV05=0、PV06=0.25、PV07=0、PV08=1、PV09=0.75、PV10=0.7778；confidence均为测试值1.0。 |
| `report.md`                 | 0.4完整闭环示例 | A5最终Markdown报告示例，包含人工复核警告、覆盖、三角色/三形式结果、因素、十变量证据组和背景信息。                                                     |
| `report_narrative.json`     | 0.4完整闭环示例 | A5结构化叙述层输出。先校验变量/角色/证据/factor引用，再由`render_report()` 转成report.md。                                                          |
| `risk_model_input.json`     | 0.4完整闭环示例 | 从profile确定性派生的A4独立输入示例，作为本地A4或未来外部模型统一接口。                                                                               |
| `risk_result.json`          | 0.4完整闭环示例 | 本地等权A4流程测试输出示例：bully≈0.0787、victim≈0.3241、bully_victim≈0.0787，并含身体/言语/关系分项和测试状态。                                   |
| `synthetic_prediction.json` | 0.4完整闭环示例 | 外部A4契约的合成预测示例，仅用于验证接口和Frechet联合概率约束；不是任何真实模型的预测结果。                                                           |
| `validated_evidence.json`   | 0.4完整闭环示例 | 完整56轮回放产生的全部已校验核心证据和背景证据汇总，是profile的可追溯来源。                                                                           |

### `examples/dialogue_full/turns/T001/`

| 文件                      | 当前性/角色         | 用途                                                                                         |
| ------------------------- | ------------------- | -------------------------------------------------------------------------------------------- |
| `candidate_result.json` | 0.4单轮中间产物示例 | T001 A3候选输出，尚未注入程序生成的observation/evidence ID，也尚未通过全部跨文件校验。       |
| `history.json`          | 0.4单轮中间产物示例 | T001提问前的历史；第一轮为空，用于演示A2/A3独立调用接口。                                    |
| `input.json`            | 0.4单轮中间产物示例 | T001实际question/answer输入，供A3 observe命令复现。                                          |
| `task.json`             | 0.4单轮中间产物示例 | 控制器为T001生成的question task，包含冻结情境、当前target、missing slots、allowed units等。  |
| `validated_turn.json`   | 0.4单轮中间产物示例 | T001经过`validate_turn()` 后的正式结果，已完成原话span、映射、ID、coverage资格等程序校验。 |

### `scripts/`

| 文件                            | 当前性/角色   | 用途                                                                                                                                                              |
| ------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `build_dialogue_fixtures.py`  | 维护/生成工具 | 维护/开发脚本。内置每个测量单元的合成回答样本，调用控制器生成五套固定`fixtures/dialogue/*.json`；这些是功能回放数据，不是心理测量gold label。                   |
| `build_measurement_config.py` | 维护/生成工具 | 维护/开发脚本。由原题映射和人工编码的测量设计生成/更新30个measurement units、69条dialogue rules、6情境及plan相关配置；修改测量设计时应同时重新验证CFG编号和测试。 |
| `export_dialogue_schemas.py`  | 维护/生成工具 | 维护/发布脚本。把运行时0.4数据结构导出为`schemas/*.schema.json` 公共契约；跨文件一致性仍由Python运行时校验，不只依赖静态Schema。                                |

### `tests/`

| 文件                            | 当前性/角色 | 用途                                                                                                                                                               |
| ------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_dialogue.py`            | 自动化测试  | 0.4核心单元/集成测试。覆盖测量单元适用性、槽位、参照框架、原话/白名单限制、第三方排除、A1/A2/A3/A5适配、A4计算、固定置信度、外部预测约束、无业务哈希字段、恢复等。 |
| `test_dialogue_cli.py`        | 自动化测试  | 0.4 CLI端到端测试。验证独立A1—A5命令、full回放可从状态独立重算、最新checkpoint恢复，以及使用本机mock HTTP完成interview链路。                                      |
| `test_followup.py`            | 自动化测试  | 0.2及后续兼容回归。重点覆盖部分映射、默认作用域、ID分离、API配置/凭证来源和provider错误处理。                                                                      |
| `test_model_output.py`        | 自动化测试  | 模型输出边界测试。验证单个JSON fenced block可解析、夹杂文本/非法结构被拒绝，以及CLI能记录正确失败阶段。                                                            |
| `test_network_diagnostics.py` | 自动化测试  | LLM网络诊断测试。覆盖DNS、TLS、timeout、响应体、代理、thinking、direct模式、doctor和敏感凭证脱敏。                                                                 |
| `test_round1.py`              | 自动化测试  | 旧Round1单案例回归。确保旧配置、证据校验、去重/分组、缺失和CLI在0.4新增多轮能力后仍保持兼容。                                                                      |

### `docs/`

| 文件                                  | 当前性/角色   | 用途                                                                                                                           |
| ------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `agent_interfaces.md`               | 0.4当前文档   | 0.4 A1—A5接口与职责边界说明。适合开发者快速理解每个Agent能读什么、能写什么、哪些判断必须由程序完成。                          |
| `change_manifest.json`              | 0.4当前文档   | 0.4相对0.3的机器可读变更清单，记录CONFIG/PROFILE/A4/A5/CLI/TESTS/DOCS等修改范围及去哈希字段调整。                              |
| `change_report_template.md`         | 0.4当前文档   | 后续版本迭代报告模板。要求每轮记录修改内容、已完成功能、待完成项和验证结果，符合当前项目交付约定。                             |
| `data_contract.md`                  | 历史/兼容参考 | 历史0.1/0.2单案例数据契约说明，解释case/evidence/gap等结构。仍对旧链路有参考价值，但不是0.4多轮状态的首选文档。                |
| `extraction_output_fix.md`          | 历史/兼容参考 | 0.2.2历史修复记录：处理模型返回Markdown JSON围栏、gaps越界等问题，并给出安装/诊断说明。                                        |
| `feature_status.json`               | 0.4当前文档   | 机器可读功能完成度清单，标记已完成与待完成能力，便于自动化交接检查。                                                           |
| `file_organization.md`              | 历史/兼容参考 | 历史文件组织说明（主要针对0.2）。文中补充0.4已形成A1—A5闭环；看当前代码时应以README、multiturn_usage和本报告为准。            |
| `followup_0_2.md`                   | 历史/兼容参考 | 0.2阶段扩展记录，重点说明E03/D04部分映射、evidence_id与rule_id分离、API诊断和后续路线。                                        |
| `legacy_round1_readme.md`           | 历史/兼容参考 | 旧单案例/Round1命令的专用使用说明。用于维护兼容链路，避免与0.4多轮命令混用。                                                   |
| `llm_connection_troubleshooting.md` | 历史/兼容参考 | LLM网络连接排错手册。覆盖doctor、DNS/TLS/timeout/proxy/thinking、凭证读取和常见错误。                                          |
| `measurement_decisions.md`          | 历史/兼容参考 | 历史测量设计决策记录。解释为何按原题派生Evidence、部分映射如何约束、哪些结论不能从情境回答直接推断。                           |
| `multiturn_usage.md`                | 0.4当前文档   | 0.4最重要的操作手册。包含离线回放、五套plan、真实访谈与恢复、独立A1—A5命令、测试值语义。                                      |
| `round_0_3_report.md`               | 历史/兼容参考 | 0.3版本变更报告，用于追溯0.4之前的架构；其中A4职责与0.4不同，阅读时需注意版本。                                                |
| `round_0_4_report.md`               | 0.4当前文档   | 当前最新版本变更/功能报告。记录0.4将原A4解释迁为A5、引入独立A4风险计算、固定confidence=1、CFG_004、无业务哈希字段及112项验证。 |
| `verification.md`                   | 历史/兼容参考 | 历史验证说明，覆盖旧0.1/0.2回归；0.4最终验证结果应以`verification_0_4.json` 和当前测试运行结果为准。                         |
| `verification_0_4.json`             | 0.4当前文档   | 0.4机器可读验证记录。记录测试数量、环境、各plan回放和完整示例属性；当前重新运行仍为112/112通过。                               |

### `source/`

| 文件                            | 当前性/角色     | 用途                                                                                                                       |
| ------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `心理Agent+量表与心理变量.md` | 设计源/追溯依据 | 项目原始设计/测量依据。包含十心理变量、量表题目映射、Evidence设计和最初Agent分工，是配置可追溯源；运行时不直接解析该文档。 |

## 8. 文件之间的关键读写关系

| 阶段       | 主要读取                                                    | 主要写入/返回                                   |
| ---------- | ----------------------------------------------------------- | ----------------------------------------------- |
| 配置装载   | `config_manifest` + 13受管配置 + 旧基础配置               | `DialogueConfig`                              |
| A1         | plan、scenario blueprint、dialogue scenarios、unit views    | frozen scenario task                            |
| Controller | interview policy、measurement units、frozen facts、turn结果 | state、question task、coverage                  |
| A2         | question task + history                                     | question                                        |
| A3         | question task + answer + history + rule/variable/item白名单 | candidate observations/background               |
| 程序校验   | candidate + task + config                                   | validated turn/evidence、coverage资格           |
| Profile    | validated evidence + variable scoring + evidence quality    | `profile.json`                                |
| A4         | profile + risk association/scoring/confidence               | `risk_model_input.json`、`risk_result.json` |
| A5         | profile + risk result + report policy                       | `report_narrative.json`、`report.md`        |

## 9. 维护与扩展指南

### 9.1 修改量表/心理变量

优先修改 `psychological_variable.json` 与 `questionnaire_mapping.json`，随后同步检查 `scenario_blueprint.json → measurement_units.json → dialogue_rubric.json → risk_profile_rules.json/risk_scoring.json`。因为这些文件受CFG管理，**不能只改一个JSON继续沿用CFG_004**；应创建新的 `config_set_id`，更新manifest并重新导出Schema/Fixtures/Examples/测试。

### 9.2 新增测量单元或追问

应在 `measurement_units.json` 明确 source items、target variables、reference frame、required slots、applicability、rule_ids 和 interpretation boundary；再在 `dialogue_rubric.json` 添加对应证据规则。不要把“追问逻辑”硬写进LLM Prompt来绕开MeasurementController。

### 9.3 新增情境

按“blueprint → executable scenario → plan entry”三层扩展。事实条件必须可用于适用性判断；A1只负责自然化文本。新增情境后应增加fixture/replay和覆盖测试，尤其验证身体/言语/关系形式标签、关系类型、意图清晰度、joking/group pressure等条件。

### 9.4 替换真实A4风险模型

推荐保留 `risk_model_input.json` 和 `risk_prediction.schema.json` 作为稳定边界，只替换A4实现或通过external prediction adapter接入。正式模型需要至少明确：预测目标（当前卷入/未来卷入）、时间窗口、训练标签定义、模型版本、概率校准、独立验证、缺失处理与不确定性。不要直接让通用LLM根据画像文字生成概率。

### 9.5 修改置信度

当前 `confidence_policy.json` 的1.0只是流程测试。后续应把“覆盖充分度、A3抽取可靠度、测量可靠度、A4模型不确定性”分开建模，避免用一个confidence字段混合四种含义。

### 9.6 接入产品后端

建议保持本项目接口相对独立：会话服务负责session/task/turn/checkpoint；证据服务保存validated evidence；画像服务消费已校验证据；风险服务只消费risk_model_input；报告服务只消费profile+risk_result。数据库层不要让业务表直接依赖LLM原始JSON结构。

## 10. 当前版本完成度与未完成项

| 项目                  | 状态               | 交接说明                                    |
| --------------------- | ------------------ | ------------------------------------------- |
| 6情境多轮访谈         | 已实现             | 有五套plan、覆盖/槽位/预算/skip/stop/resume |
| A1—A3链路            | 已实现             | A2/A3可用LLM，A3结果必须程序校验            |
| 十变量画像            | 已实现（工程测试） | 数值是方向组均值，不是心理量表已验证得分    |
| A4三角色总体风险      | 已实现（未校准）   | 默认等权测试，只用于打通接口                |
| A4三种霸凌形式        | 已实现（未校准）   | 身体/言语/关系分项有输出位置                |
| 外部风险模型适配      | 已实现接口         | 尚无经过训练/校准的正式模型                 |
| A5模板/LLM解释        | 已实现             | 只读、带引用校验与人工复核警告              |
| confidence机制        | 临时实现           | 固定1.0，后续需人工/统计校验                |
| 风险等级阈值          | 未实现             | 当前没有依据，不应任意设高/中/低阈值        |
| 现实经历正式访谈      | 待扩展             | 尚需重复性、持续时间、力量差异等结构化设计  |
| 后端/数据库/权限/前端 | 不在本工程         | 应作为产品层单独开发                        |
| 自动干预              | 不在本工程         | 当前报告明确禁止自动干预/诊断               |

## 11. 验证结果与交接建议

本次重新执行：

```text
python -m unittest discover -s tests -q
Ran 112 tests in 2.046s
OK
```

这说明当前压缩包在本地环境下的代码级回归是一致的，但**不等同于心理测量效度、A3语义准确率或风险模型预测效度已得到验证**。合成fixture的用途是验证接口和程序边界。

交接给下一位开发者时建议按以下顺序阅读：

1. `README.md` → `docs/multiturn_usage.md` → `docs/agent_interfaces.md`；
2. `config/config_manifest.json` → `measurement_units.json` → `dialogue_rubric.json` → `risk_scoring.json`；
3. `measurement_controller.py` → `dialogue_contracts.py` → `dialogue_runner.py`；
4. `profile.py` → `risk_engine.py` → `risk_reporter.py`；
5. `examples/dialogue_full/` 对照真实输出；
6. 最后再阅读 `config.py/extractor.py/evidence.py/aggregate.py` 与历史docs，理解兼容层，避免把旧设计带回主流程。

最关键的工程原则是：**LLM负责语言生成和候选语义抽取，测量边界、映射、状态、证据准入、画像聚合、风险计算接口和引用一致性由确定性代码控制。** 这也是0.4相对于早期“LLM直接做全链路判断”设计的核心结构性改进。

---

报告基于 `psych_agent_round0.4.zip` 当前内容生成；建议将本文件随该代码包一同归档。
