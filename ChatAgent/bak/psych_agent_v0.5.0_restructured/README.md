# psych_agent_v0.5.0

量表驱动的校园情境多轮心理测量原型。项目保留0.4的严格任务—回答—Evidence—画像—风险—报告组织结构，并加入facet画像、真实经历区分、动态追问、风险方向修正和预警阈值。输出是未校准的流程测试值，不是诊断或临床概率。

## 快速开始

```bash
python run.py dialogue-validate
python run.py dialogue-replay --plan s01 --output outputs/demo_s01
python run.py dialogue-replay --plan full --output outputs/demo_full
python run.py interview --plan s01 --llm-config config/llm.local.json
```

完整命令、恢复、A1—A5接口和输出文件说明见 `docs/multiturn_usage.md`、`docs/agent_interfaces.md` 和 `docs/PROJECT_HANDOVER_v0.5.md`。配置由 `config/config_manifest.json` 统一管理；修改配置必须升级 `config_set_id`。

## 输出目录

每次完整运行生成 `dialogue_state.json`、`conversation_trace.jsonl`、`coverage_report.json`、`validated_evidence.json`、`profile.json`、`risk_model_input.json`、`risk_result.json`、`report_narrative.json` 和详细 `report.md`，每一轮任务、问题、回答、候选结果和校验结果保存在 `turns/Txxx/`。
