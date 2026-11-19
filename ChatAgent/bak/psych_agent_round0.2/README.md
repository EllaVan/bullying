**心理Agent代码验证(v0.2))**

依据《心理Agent+量表与心理变量.md》，验证S01中的“固定问答 → A3候选证据 → 证据校验 → 心理变量描述”。

配置保留全部10个变量、30道题和6类情境。本轮启用S01的PV01、PV02、PV03、PV10，以及A01、A02、A03、A04、E01、E04、G01七道核心题。F01—F04只接收自发出现的背景信息。本轮不增加F类提问，不将背景合入变量得分。

全局规则库包含19条规则：默认首轮17条，另含E03/D04两条扩展草案。16个原有案例及新增扩展示例均为合成开发数据；规则和案例尚未经心理测量专家审阅。`fixtures/replay/`是预制的模拟模型响应，不是一个已经验证有效的抽取模型；离线回放通过不代表LLM准确率达标。

**打开psych_agent_round0.2文件夹，在终端按顺序运行：**

```bash
python run.py validate
python run.py replay --all
python -m unittest discover -s tests -v
```

第一条检查配置与题目映射。第二条逐个回放16个预制候选响应。第三条运行代码边界测试。三个命令都不需要API密钥，也不会调用网络。

每次回放的结果放在新的`outputs/时间_模式_编号/`目录。每个案例都有`input.json`、`extraction.json`、`validated_evidence.json`和`summary.json`。运行清单记录配置哈希，便于比较修改规则前后的结果。这是实验复现记录，不是系统后端或数据库设计。

**如果只查看第一个案例，可以运行：**

```bash
python run.py replay --case S01_001
```

预期看到PV01、PV10的相关表达记录，PV02、PV03为`insufficient_evidence`。所有变量的`value`和`confidence`为`null`，`risk_result`也是`null`，因为本轮没有标定分数和风险模型。

**A3与变量汇总也能分别运行。**

先导出给模型的请求，查看测量配置是否正确进入提示词：

```bash
python run.py prepare-prompt --case-file data/single_case.json
```

独立处理一个已有候选响应：

```bash
python run.py aggregate --case-file data/single_case.json --response-json fixtures/replay/S01_001.json
```

将自行获取的A3输出另存为JSON后，可以用同一命令处理。必须使用对应的案例输入；不能将其他学生或其他情境的输出套用进来。程序拒绝不存在的原话、未知规则、错误case_id、假设回答被标为已发生经历等可机械检查的问题。

**需要接真实LLM时，再配置可选适配器。**

复制`config/llm.example.json`为`config/llm.local.json`，填写账号实际可用的`model`。示例endpoint采用智谱普通对话补全接口；如果使用其他服务，需确认兼容非流式`messages`请求和`choices[0].message.content`响应。JSON模式仅在该模型支持时打开。[智谱对话补全文档](https://docs.bigmodel.cn/api-reference/模型-api/对话补全)、[结构化输出说明](https://docs.bigmodel.cn/cn/guide/capabilities/struct-output)

0.2支持两种密钥来源：环境变量`PSYCH_LLM_API_KEY`，或者只保存在自己电脑的`llm.local.json`中的`api_key`。环境变量非空时优先；`api_key_env`填写的是变量名。诊断会显示来源而不显示密钥。本地密钥配置不进入交付包。也可在终端中用隐藏输入设置环境变量并启动测试：

```bash
python -c "import os,getpass; from psych_agent.cli import main; os.environ['PSYCH_LLM_API_KEY']=getpass.getpass('API key: '); raise SystemExit(main(['extract','--case-file','data/single_case.json','--llm-config','config/llm.local.json']))"
```

如果当前终端已经配置好环境变量，则直接运行：

```bash
python run.py extract --case-file data/single_case.json --llm-config config/llm.local.json
```

真实调用会向你配置的模型服务发送当前案例与测量配置，应先使用包内合成数据。适配器在本次只进行了模拟响应测试，未使用真实API密钥连通任何模型，不保证账号中的任意模型都支持全部示例参数。

更多说明见`docs/file_organization.md`（准备文件）、`docs/data_contract.md`（输入输出）、`docs/measurement_decisions.md`（测量边界）、`docs/verification.md`（本次验证记录）。下一步优先人工审阅规则与案例，再用独立回答测试A3；A1、A2、A4和风险规则暂未实现。

**0.2新增的部分映射与诊断命令。**

S01蓝图增加`item_bindings`，E03→PV10，D04在S01仅选择PV10。原题D04→PV08/PV10保持不变。默认七题不变，按需使用单独的扩展范围：

```bash
python run.py --scope-config config/round1_extended.example.json aggregate --case-file examples/E03_D04.case.json --response-json examples/E03_D04.extraction.json
```

先独立检查API，再执行A3：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py doctor --llm-config config/llm.local.json --connect
```

第一条不联网；第二条只发送一个最小普通对话请求。只有当你运行带`--connect`的命令时才调用服务。完整的题目绑定、证据规则编写、ID区分、API排查和下一步见`docs/followup_0_2.md`。
