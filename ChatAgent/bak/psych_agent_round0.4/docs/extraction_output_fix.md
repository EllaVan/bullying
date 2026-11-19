**模型输出解析与gaps越界修复说明（0.2.2）**

本次处理`extract`已收到模型文本后的两个问题：JSON包装格式与心理变量范围校验。

**两次报错的关系**

“JSON格式错误，第1行第1列”发生在文本解析阶段。若模型用Markdown围栏包住JSON，严格解析器会在起始反引号处失败。移除该包装后出现“gaps使用了本轮未允许的变量”，说明本次JSON已经解析成功，但至少一条`gaps.variable_id`不属于当前scope。编号写错、输出变量名、额外带入背景变量等情况都可能触发同一个检查；实际越界值必须查看响应。

当前默认配置的范围：

| 用途 | 变量 | 可进入gaps |
|---|---|---|
| 本轮核心测量 | PV01、PV02、PV03、PV10 | 可以，但只填写当前回答确有的信息缺口 |
| F类背景规则补充定义 | PV05、PV08 | 不可以；有明确背景原话时按对应背景规则提取证据 |

旧提示词把上述两类定义放在同一个`variables`列表，输出schema中的`gaps.variable_id`又只有字符串类型限制。这是一个容易诱发模型混淆的设计缺口。尚未看到用户真实响应，不能据此断定本次一定是PV05或PV08越界。

**修复内容与模块边界**

| 文件 | 本次职责 |
|---|---|
| `psych_agent/model_output.py` | 兼容完整的外层JSON代码围栏；内部仍调用严格JSON解析 |
| `psych_agent/extractor.py` | 分别提供核心变量和背景变量，按当前scope为gaps生成明确的允许列表及schema枚举 |
| `prompts/evidence_extractor.md` | 明确背景定义不会扩大gaps范围；逐条检查编号 |
| `psych_agent/evidence.py` | 检查候选变量范围，错误显示全部越界位置、原编号和允许列表 |
| `psych_agent/cli.py` | 保留原始响应与解析候选，区分解析和证据校验的失败阶段，并显示输出路径 |

`strip_json_markdown`采用`fullmatch`匹配整个响应。原先使用只有起始约束的正则可能丢掉代码块后的额外文本；本次格式适配仅接受纯JSON或完整JSON/无语言代码围栏。前后说明、多代码块、残缺JSON、重复键与NaN继续被拒绝。该函数不用于读取量表配置，也不会替换变量编号或删除gaps。

动态枚举来自`cfg.scope['active_variable_ids']`，没有把四个编号写死到通用schema文件中。模型仍可能不遵守提示词，因此程序继续做独立范围检查，保留不合格输出供审阅。

**安装本次补丁**

把补丁压缩包内的`psych_agent`、`prompts`、`tests`和`docs`目录合并到原项目同名目录。必须复制新增的`model_output.py`，并同步更新`extractor.py`与提示词。补丁中没有量表配置、API配置、运行数据或模型客户端文件。

核心改动可用以下命令验证：

```bash
python -m unittest discover -s tests -p test_model_output.py -v
```

**先检查已有响应**

将下方路径替换为上次失败运行的真实目录。该命令读取已有模型响应，不再调用API：

```bash
python run.py extract --case-file data/single_case.json --response-json "outputs/上次失败目录/raw_response.txt"
```

如果旧响应仍含越界编号，检查失败是预期结果。新版会显示类似下例的信息：

```text
gaps使用了本轮未允许的变量：gaps[2].variable_id='PV08'；本轮允许：PV01, PV02, PV03, PV10
```

这是模拟示例，索引从0开始。程序同时显示新运行的输出目录，其中：

- `raw_response.txt`：原始模型文本，包含原来的围栏。
- `parsed_response.json`：移除包装并成功解析后的候选，仍保留越界项。
- `error.json`：具体错误、失败阶段及当前允许变量。

不要为了消除这条错误而扩大`active_variable_ids`或直接过滤gaps。是否扩大测量范围需由量表、情境和规则设计共同决定。

**再用更新后的提示词抽取**

```bash
python run.py extract --case-file data/single_case.json --llm-config config/llm.local.json
```

成功时才生成已校验证据与汇总；若模型继续越界，请查看新报告中列出的具体编号和该次`messages.json`中的`gaps_allowed_variable_ids`。发送`parsed_response.json`的gaps部分即可进一步分析，不需要API密钥。

验证结果：新增10项测试通过，完整项目69项测试通过。API返回在测试中使用模拟数据；目前没有用户真实模型输出的语义评阅结果。
