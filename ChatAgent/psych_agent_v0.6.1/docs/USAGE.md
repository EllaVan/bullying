# 使用说明 0.6.1

## 1. 环境

- Python 3.8+（类型注解已兼容 3.8；建议 3.10+）。
- 依赖：见根目录 `requirements.txt`（`jsonschema`、`pytest`；主路径单测以 `unittest` 为主）。
- 工作目录：必须在 `psych_agent_v0.6.1/` 下执行 `python run.py ...`。

```bash
cd psych_agent_v0.6.1
pip install -r requirements.txt
```

## 2. 配置 LLM（联机访谈）

1. 复制 `config/llm.local.example.json` → `config/llm.local.json`。
2. 填写 `endpoint`、`model`；密钥优先放环境变量（`api_key_env`），或临时写在 `api_key`（勿提交）。
3. 可选：复制 `config/agents.example.json` → `config/agents.json`，为 A1/A2/A3/A5 分别指定 backend。

连通性检查（不跑访谈）：

```bash
python run.py doctor --llm-config config/llm.local.json
python run.py doctor --llm-config config/llm.local.json --connect
```

## 3. 主路径命令

查看全部子命令：`python run.py --help`。

### 3.1 校验配置（不调 API）

```bash
python run.py dialogue-validate
```

检查测量单元、多轮规则、计划、Facet、风险权重等是否自洽。

### 3.2 离线回放（合成 fixture，不调 LLM）

```bash
# 省略 --output：自动生成 outputs/YYYYMMDDTHHMMSS_dialogue_replay_<id>/
python run.py dialogue-replay --plan s01
python run.py dialogue-replay --plan full
```

计划 ID 见 `config/interview_policy.json`（如 `s01`、`balanced`、`full`）。回放数据在 `fixtures/dialogue/`。

### 3.3 真实交互访谈

```bash
# 省略 --output：自动生成 outputs/YYYYMMDDTHHMMSS_interview_<id>/
python run.py interview --plan full --llm-config config/llm.local.json
```

常用参数：

| 参数 | 含义 |
| --- | --- |
| `--plan` | 访谈计划 |
| `--llm-config` | 全局 LLM 配置 |
| `--agents-config` | 分 Agent 配置 |
| `--session-id` | 指定会话 ID |
| `--max-turns` | 总轮数预算上限（不降低测量充分性定义） |
| `--resume` | 从 `dialogue_state.json` 或运行目录续跑 |
| `--output` | 输出目录；**省略则按本地时间自动建** `outputs/<时间戳>_<命令>_<8位>/` |

会话中：`/skip` 跳过当前题，`/stop` 结束；Ctrl+C 暂停并保留检查点。

### 3.4 从状态重算画像 / 风险 / 报告

```bash
python run.py dialogue-profile --state-file outputs/my_session/dialogue_state.json --output outputs/my_session
python run.py risk --profile-file outputs/my_session/profile.json --output outputs/my_session
python run.py report --profile-file outputs/my_session/profile.json --risk-file outputs/my_session/risk_result.json --output outputs/my_session
```

输出含 `report.md`（完整审计，证据为可读标签）与 `report_brief.md`（结论+关键原话+限制）。内部 `DEV_` hash 仅在完整报告附录对照。

外部 A4 预测（须符合 `schemas/risk_prediction.schema.json`）：

```bash
python run.py risk --profile-file .../profile.json --prediction-file path/to/prediction.json --output ...
```

### 3.5 Agent 单测入口（调试）

| 命令 | 作用 |
| --- | --- |
| `scenario` | 只跑 A1 |
| `ask` | 只跑 A2（需 task JSON） |
| `observe` | 只跑 A3（需 task + turn；可给 `--response-json` 离线） |

## 4. 遗留路径命令（非产品主路径）

用于早期单案例抽取链路，规则为 `evidence_rubric.json`：

```bash
python run.py validate
python run.py replay --all --output outputs/legacy_replay
python run.py extract --case-file data/single_case.json --response-json path/to/a3.json --output outputs/legacy
python run.py aggregate --case-file ... --response-json ... --output ...
python run.py prepare-prompt --case-file ... --output ...
```

二次开发默认扩展主路径，勿把遗留命令当作发布接口。

## 5. 测试

```bash
# 主路径推荐
python -m unittest tests.test_dialogue tests.test_conflict_resolver tests.test_dialogue_cli

# 冲突消解专项
python -m unittest tests.test_conflict_resolver -v

# 发现全部测试（含遗留 round1；部分依赖旧数据/环境，失败时先看主路径）
python -m unittest discover -s tests
```

## 6. 常见问题

| 现象 | 排查 |
| --- | --- |
| `配置清单版本无效` / `版本不是0.6.1` | 确认在 v0.6.1 目录且 `config/*` 的 `version`/`config_set_id` 为 `0.6.1`/`CFG_008` |
| `缺少配置文件：evidence_rubric.json` | 遗留 `load_config` 仍需要该文件；勿删 |
| A3 大量 fallback | 看 `outputs/.../llm_calls/a3/` 与 `coverage_report`；结构错误会空观察继续 |
| 分数为 null | 覆盖率/角色权重覆盖/有效变量数未达 `risk_scoring.json` 门槛 |
| 联机 401/超时 | `doctor --connect`；检查密钥与代理（`proxy_mode`） |
| 报告角色只有三类 | 确认跑的是 0.6.1 代码与 `CFG_008`，且 A5 使用更新后的 `report_agent.md` |

## 7. 量表锚定与文献定权

计分门槛与门控的发表量表映射见 [SCALE_RULES_SOURCE.md](SCALE_RULES_SOURCE.md)。  
无标注者时的角色权重/阈值启发式见 [PSYCH_WEIGHT_THRESHOLDS.md](PSYCH_WEIGHT_THRESHOLDS.md)（`literature_heuristic_v1`）。  
可信度阶段（fallback 不计分、规则语义、一致率）见 [CREDIBILITY_ROADMAP.md](CREDIBILITY_ROADMAP.md)。  
报告字段含义见 [REPORT_SCORING_AUDIT.md](REPORT_SCORING_AUDIT.md)。  
配置入口：`config/scale_constraints.json`、`config/risk_scoring.json`、`config/variable_scoring.json`、`config/confidence_policy.json`。  
对照样例：`outputs/recompute_69db8d61/`（锚定包 + 文献定权 + 冲突置信标签）。  
对已有 `profile.json` 按当前规则重算（无需 dialogue_state）：

```bash
python scripts/recompute_profile_risk.py \
  --profile-file outputs/recompute_69db8d61/profile.json \
  --output outputs/recompute_rerun
```

## 8. 基于真人会话快速重跑（LLM）

用既有 `conversation_trace.jsonl`（或会话目录 / `dialogue_state.json`）自动填答，不必再手输。默认 **冻结原问题**（`frozen-qa`），只对 A3 调 LLM 重抽取；A1/A5 默认模板。内置轨迹：`fixtures/real/20260914_69db8d61_trace.jsonl`（61 轮，来自 v0.5.2 真人访谈）。

```bash
# 冒烟（截断轮数）；省略 --output 时自动按时间建目录
python scripts/rerun_llm_from_trace.py --max-turns 8

# 全量重跑（耗时与 API 费用随轮数增长）
python scripts/rerun_llm_from_trace.py \
  --source fixtures/real/20260914_69db8d61_trace.jsonl \
  --plan full --llm-config config/llm.local.json

# A2 也现场出题（仅自动答；可能与原答语义错位，适合压测）
python scripts/rerun_llm_from_trace.py --mode answers-only --max-turns 8
```

输出目录形如 `outputs/20261105T142530_llm_rerun_a1b2c3d4/`，含 `rerun_manifest.json`、`report.md`、`report_brief.md`、`llm_calls/`。标记 `synthetic=true`（回答来自轨迹，非现场手输）。

## 9. 脚本（维护用）

| 脚本 | 用途 |
| --- | --- |
| `scripts/recompute_profile_risk.py` | 已有 profile 按当前量表规则重算（见 §7） |
| `scripts/rerun_llm_from_trace.py` | 真人轨迹自动重跑（见 §8） |
| `scripts/measure_a3_consistency.py` | 同一轨迹多次 A3，输出方向一致率 |
| `scripts/build_measurement_config.py` | 从源文档重建测量配置（改后需人工核对） |
| `scripts/build_dialogue_fixtures.py` | 生成/刷新 `fixtures/dialogue` |
| `scripts/export_dialogue_schemas.py` | 导出对话相关 JSON Schema |

改配置后务必再跑 `dialogue-validate` 与主路径单测。
