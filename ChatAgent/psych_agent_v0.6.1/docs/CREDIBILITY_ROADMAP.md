# 可信度提升路线图（v0.6.1）

目标：在**无标注者**条件下，提高对话风险画像的证据可信度与心理学可解释性。  
本轮已落地阶段 1（证据层）+ 阶段 2（文献定权/阈值）；阶段 3+ 仍为后续。

```text
文献/问卷 ──► PSYCH_WEIGHT_THRESHOLDS ──► risk_scoring.json
A3 fallback / 规则语义 / 一致率 ──► 证据可信
```

---

## 阶段 1：证据层（已实施）

| 项 | 做法 | 入口 |
| --- | --- | --- |
| Fallback 不计分 | `a3_fallback_used` 轮次证据不进核心 ledger；commit 时空观察 | `measurement_controller` / `profile`；报告 §5 |
| 规则语义 | B03 停止玩笑 ≠ 道德脱离↑；固定答句回归 | `dialogue_rubric` + `tests/test_rubric_semantics.py` |
| 一致率 | 同一轨迹多次 A3，统计方向一致率 | `scripts/measure_a3_consistency.py` |

---

## 阶段 2：文献定权（已实施，替代专家标注）

见 [PSYCH_WEIGHT_THRESHOLDS.md](PSYCH_WEIGHT_THRESHOLDS.md)。

- 阈值：bully/victim/bystander `[45,70]`；bully_victim `[50,75]`（Olweus 频次思想）。
- 权重：MD/攻击/SIP/共情/排斥敏感等相对效应量启发式；`calibration_status=literature_heuristic_v1`。

---

## 阶段 3+（未实施）

- 人工复核工作流、标注校准集
- 隐私与权限、紧急风险处置通道
- 本校样本 ROC / 常模（若未来有标注）

---

## 验收清单

1. `python run.py dialogue-validate`
2. `python -m unittest tests.test_dialogue tests.test_conflict_resolver tests.test_conflict_confidence tests.test_evidence_labels_and_gates tests.test_rubric_semantics`
3. `python scripts/recompute_profile_risk.py --profile-file outputs/recompute_69db8d61/profile.json --output outputs/recompute_69db8d61`（或新目录后拷回样例）
4. 一致率（需 LLM）：`python scripts/measure_a3_consistency.py --repeats 3 --max-turns 8`

## 边界

输出仍是未校准工程指数；不得替代诊断或处分。密钥勿入库。
