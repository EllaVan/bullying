**第一轮问题解答与0.2更新说明**

你已确认现有核心配置与解释边界。本次保持`psychological_variable.json`、`questionnaire_mapping.json`、`aggregation_rules.json`和默认`round1.json`的内容，增加部分变量绑定和独立API诊断。原先17条规则保留，新增E03、D04两条待审核草案。

**情境中的题目选择应记录“本次使用这道题的哪个方面”。**

0.1的S01七题是手动选出的最小实验集合，并非用变量全集做自动筛选。E03仅关联PV10，所以对S01不存在部分变量冲突；它只是没有进入初始七题。D04同时关联PV08和PV10，在S01可以只选择PV10，但回答语境应当涉及朋友冲突后的关系修复。

| 题目 | 原始变量 | S01选用 | 处理方式 |
|---|---|---|---|
| E03 | PV10 | PV10 | 针对求助后可能更麻烦的顾虑 |
| D04 | PV08、PV10 | PV10 | 仅记录关系修复预期，不自动带入PV08 |

选择必须同时满足：目标变量属于原题映射；目标变量属于情境测量范围；题意和情境中的回答适配。有交集只能让题目成为候选，不能代替语义审阅。题库内原始映射不因为一次实验的选择而被删掉。

`scenario_blueprint.json`增加`item_bindings`，`item_ids`保留为同一批题目的索引：

```json
{
  "item_id": "D04",
  "target_variable_ids": ["PV10"],
  "use_condition": "回答涉及与朋友冲突后的关系修复；一般身体冲突不自动启用该语义。"
}
```

运行时还与`round1.json`的启用变量、题目取交集。A3只收到本轮允许的规则。即使全局规则库将来存在D04→PV08规则，也不会在本轮被选入。`item_ids`是可用测量依据，不表示每道题都必须逐一向学生提问。

默认仍为原七题。用单独的扩展范围配置验证E03和D04，无需覆盖默认配置：

```bash
python run.py --scope-config config/round1_extended.example.json validate
python run.py --scope-config config/round1_extended.example.json aggregate --case-file examples/E03_D04.case.json --response-json examples/E03_D04.extraction.json
```

该示例仍是预制的合成候选响应，不代表LLM已正确理解这两道题。PV10可以同时出现求助顾虑和关系修复预期，两者属于不同方面，不自动说明回答矛盾。

**evidence_rubric的编写单位是“可由原话支持的一条判定”，不是关键词或风险标签。**

| 准则 | 具体要求 |
|---|---|
| 来源明确 | 从变量定义、题目测量意图、Evidence类别出发，不凭空新增构念 |
| 单一判定 | 每条规则只映射一个变量，并描述一个可以审阅的现象；多变量分别建立规则 |
| 必要条件具体 | 写清谁、在什么条件下、表达什么，才可判入；不能仅匹配“老师”“强硬”等词 |
| 反例足够近 | 提供表面相似但不应命中的回答，特别是条件句、否定、转述和合理应对 |
| 方向一致 | higher/lower描述该心理变量的含义，不直接代表总体风险高低 |
| 未知可表达 | 没有满足条件时不强行判入；未命中负向规则不等于有正向证据 |
| 主体与来源分开 | 假设意向、自述经历、一般观点和转述他人分别保留 |
| 不跨越证据强度 | 相信能修复不等于已经有修复技能；有求助意向不等于得到支持 |
| 可独立审核 | 保留rule_id、原题、理由、反例和审核状态；模型不自行宣布规则有效 |

E03示例：

| 回答 | 处理 |
|---|---|
| “我担心告诉老师或家长以后，事情反而更麻烦。” | 可匹配`R_E03_HELP_BARRIER`，记录感知求助阻碍 |
| “我先和对方沟通，解决不了再找老师。” | 不因此判定求助阻碍，表达的是分阶段应对 |
| “我不想告诉老师。” | 原因不清，不能自动套用“担心更麻烦”的规则 |
| “同学说告诉老师会更麻烦。” | 先识别为第三方观点，不能自动归给本人 |

新增规则只是操作化草案，不是量表权重或风险阈值。正式评估前需独立人工标注正例、反例、歧义例，并检查标注者分歧。

**evidence_id与rule_id承担不同职责。**

| 字段 | 标识什么 | 是否需要一致 |
|---|---|---|
| `rule_id` | evidence_rubric中的判定规则 | validated_evidence中的同名字段必须引用现存规则 |
| `evidence_id` | 当前案例中的一次具体证据 | 不应与rule_id相同；同一规则可对应许多条证据 |
| `item_ids` | 此规则依据的题目 | 与规则配置对应 |
| `variable_id` | 此规则映射的变量 | 由代码根据规则查表生成 |

当前evidence_id由case、轮次、引用位置、rule_id、主体和来源生成确定性哈希；同一输入重复验证保持一致，不同案例对应不同实例。规则的来源通过rule_id追溯；实验使用的配置在run_manifest中记录哈希和实际范围。不要把同一规则命中的不同学生回答合并成同一个Evidence。

**API报错需要区分本地配置、服务请求和A3输出校验三个阶段。**

旧版只读取`api_key_env`指定的环境变量，忽略JSON中的`api_key`字段。把密钥本身填写到`api_key_env`也会导致失败。0.2支持环境变量和本地`api_key`两种来源，环境变量非空时优先；若只想使用文件密钥，将`api_key_env`设为空字符串。诊断只显示`credential_source`，不显示密钥。

本地配置示例（请在自己电脑上填写）：

```json
{
  "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
  "model": "填写账号实际可用的模型ID",
  "api_key_env": "",
  "api_key": "填写自己的API密钥",
  "timeout_seconds": 45,
  "json_object_mode": false
}
```

使用其他供应商时填写其完整、兼容的`/chat/completions`地址。当前适配器不接收只有base_url的地址，不自动拼接路径。JSON必须使用双引号、不能包含注释；文件应为UTF-8。

在项目根目录依次运行：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py doctor --llm-config config/llm.local.json --connect
python run.py extract --case-file data/single_case.json --llm-config config/llm.local.json
```

第一条只检查本地配置，不联网，也不依赖心理量表配置。第二条向所配置服务发送“请只回复OK”的最小请求，不发送量表或案例；只有显式使用--connect才执行此请求。第三条才发送当前合成案例及测量配置，验证A3的结构化输出。

本地诊断成功不代表密钥有效；连通性成功也不代表A3返回的JSON符合要求。`replay`和`prepare-prompt`始终不调用API，仅把文件命名为llm.local.json不会让它们变成真实模型调用。

智谱HTTP 400中的业务码1211表示模型不存在；HTTP 429既可能是余额问题（1113），也可能是速率限制（1302），应结合业务码判断。0.2会保留可解析的业务码和脱敏错误消息。[智谱错误码说明](https://docs.bigmodel.cn/cn/faq/api-code)

这次没有收到你电脑上的配置或完整报错，不能确定实际原因。需要进一步定位时，提供运行命令、完整错误文字或`error.json`，如提供配置请先删除密钥。当前交付没有实测你的账号或真实API。

**下一步先验证S01的真实A3调用，再扩展Agent。**

1. 完成本地doctor与最小连通性测试，区分配置错误和远程服务错误。
2. 对S01_001执行extract，检查raw_response、extraction、validated_evidence和summary四层结果。
3. 按规则人工核对16个合成案例，记录误提取、漏提取、主体错误和来源错误。合成样例用于开发，不将自身预制回放当作准确率。
4. 用扩展范围配置验证E03/D04，核对D04只产生PV10候选。
5. 建立独立的人工标注评估集，给A3留下未用于调Prompt的回答。
6. A3稳定后扩展其余变量/情境，再做A1情境生成和A2追问；风险数值与角色推断继续保持后置。

更新后的50项工程测试通过，包括部分变量过滤、主体与背景隔离、ID关系、文件密钥读取、环境变量优先级、业务码脱敏与独立诊断。该结果不等于心理测量有效性或真实LLM语义准确性验证。
