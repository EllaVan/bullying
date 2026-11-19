**LLM超时与网络错误排查（0.2.1）**

针对命令：

```bash
python run.py doctor --llm-config config/llm.local.json --connect
```

旧提示“LLM请求超时或网络连接失败”来自适配器的一组异常捕获，无法据此确定是DNS、代理、TLS证书、连接中断，还是等待模型响应超时。本地配置校验已通过，仅说明程序能读取配置与密钥字段，不代表服务已经认可密钥。

当前填写的智谱普通对话接口与模型名有官方文档依据；`api_key_env`为空时读取本地`api_key`。如果发来的`sk-`是脱敏展示，则保留电脑中的完整密钥；如果文件里确实只有这三个字符，需要在本地填入完整密钥。无需发送完整密钥。[智谱模型概览](https://docs.bigmodel.cn/cn/guide/start/model-overview)、[智谱HTTP调用说明](https://docs.bigmodel.cn/cn/guide/develop/http/introduction)

**更新代码。** 从0.2.1项目包复制`psych_agent/llm_client.py`和`psych_agent/cli.py`到原项目相同位置即可启用修复。`psych_agent/__init__.py`仅更新版本号，可一并复制。保留自己原有的`config/llm.local.json`；这个文件不在交付包中。需要运行新增测试时，再复制`tests/test_network_diagnostics.py`。本次修改集中在独立API适配器和诊断命令。

**先运行原命令。** 新版成功时显示`status: api_connected`；失败时退出码为2，并显示`status: api_request_failed`、`elapsed_seconds`和`error`等字段。失败报告也显示`credential_source`，但不显示密钥。以下是模拟报告字段示例，不能当作实际故障结论：

```json
{
  "status": "api_request_failed",
  "credential_source": "config_file",
  "network_test_performed": true,
  "elapsed_seconds": 45.01,
  "error": "LLM请求失败：请求超时；底层异常=TimeoutError；阶段=建立连接或等待响应头；耗时=45.01秒；套接字超时设置=45秒；代理模式=system；详情=timed out；没有自动重复请求"
}
```

**按具体错误选择下一步。**

| 结果 | 含义与下一步 |
|---|---|
| DNS解析失败 / gaierror | 目标主机或代理主机解析失败，检查当前电脑的DNS与代理设置；调整模型参数不能修复DNS |
| TLS证书校验失败 / SSLCertVerificationError | 检查系统时间、Python信任的证书和代理证书配置，保留证书校验 |
| 连接被拒绝、连接被中断 | 检查代理端口、网络策略与连接；可做一次直连对比 |
| 请求超时，阶段为建立连接或等待响应头 | 可能发生在建连、TLS、代理隧道、等待服务响应等环节；仅凭这个阶段不能断定是服务端推理慢 |
| 请求超时，阶段为读取响应正文 | 已取得响应头，接收完整响应时发生超时；网络传输或服务响应停顿仍需进一步区分 |
| HTTP响应传输失败 / IncompleteRead | 已收到的正文不完整，不能用于证据解析；检查连接稳定性 |
| HTTP状态码及业务码 | 按服务返回的认证、权限、模型或限流错误处理；此时不能继续当成单纯网络超时 |
| api_connected | 最小普通对话请求成功，可以进入单案例A3测试；尚未验证证据抽取质量 |

**如果是等待超时，单独对比关闭思考。** GLM-4.7系列默认开启Thinking，官方支持`thinking.type=disabled`以降低轻量任务的响应开销。这是待验证的超时因素，不是已确认的故障根因。[智谱思考模式](https://docs.bigmodel.cn/cn/guide/capabilities/thinking-mode)

```bash
python run.py doctor --llm-config config/llm.local.json --connect --disable-thinking
```

该选项只给本次最小请求附加`"thinking": {"type": "disabled"}`，不会自动改变A3抽取的思考设置。不要把它当作所有服务和模型的通用参数。

**如果怀疑代理，保持其余参数一致，做一次直连对比。** Python的urllib会读取代理环境变量，也可能读取Windows注册表或macOS系统代理，因此未在JSON配置代理也可能使用代理。`system_proxy_for_endpoint_scheme_present`只表示检测到配置；实际是否走代理还受绕过规则等影响。`direct`通过当前请求的空ProxyHandler禁止自动使用代理。[Python urllib文档](https://docs.python.org/3/library/urllib.request.html#urllib.request.ProxyHandler)

```bash
python run.py doctor --llm-config config/llm.local.json --connect --disable-thinking --direct
```

直连成功而使用系统代理失败，支持优先排查代理路径；两次都超时并不能证明密钥或模型有问题。网络本身要求代理时，应修正代理配置。每次运行只有一次请求，没有自动重试或自动切换模型。

**需要时再修改连接设置。** 0.2.1新增两个可选配置项，默认行为兼容旧配置：

| 字段 | 可填写值 | 作用 |
|---|---|---|
| `proxy_mode` | `"system"`（默认）或`"direct"` | 选择当前API调用是否使用自动检测到的代理 |
| `thinking` | `{"type":"enabled"}`或`{"type":"disabled"}`；也可不填 | 按配置附加模型支持的思考参数；不填时采用服务默认行为 |
| `timeout_seconds` | 1至300的数值；默认45 | urllib套接字阻塞操作的超时设置，并非完整请求的严格总时限 |

若已经排查网络、关闭思考后仍出现等待超时，可以在本地将`timeout_seconds`改为120进行单次对比。旧版上限是60，需要先更新代码。增加超时不会修复DNS、证书、认证或错误的代理配置。[Python超时参数说明](https://docs.python.org/3/library/urllib.request.html#urllib.request.urlopen)

只有当你确实希望A3也采用相同选项时，才把`proxy_mode`或`thinking`加入`llm.local.json`；doctor命令行选项不会写回文件。单案例调用：

```bash
python run.py extract --case-file data/single_case.json --llm-config config/llm.local.json
```

本次59项工程测试已通过，网络故障和成功响应使用模拟对象。没有使用你的真实密钥，也未验证你电脑与服务之间的连接。若仍失败，提供新版doctor的脱敏报告即可进一步定位；无需再提供密钥或整份配置。
