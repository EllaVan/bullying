# recompute 报告七问：逐条解答

依据：当前代码（锚定包 `olweus_dbvs_bpbq_v1`）与终版样例 `outputs/recompute_69db8d61/report.md`。  
发表量表计分逻辑映射见 [SCALE_RULES_SOURCE.md](SCALE_RULES_SOURCE.md)。

---

## 1. 工程置信指标如何设定？

角色表「工程置信指标」**不是**测量信度或抽取准确率。**分数轴与置信轴分离**：可出现「关注档分数 + 低/中·冲突」标签。

公式（`psych_agent/risk_engine.py`）：

```
base = weight_coverage × quality_factor × (各变量 confidence 加权均值)
conflict_factor = 1 − conflict_penalty × conflict_share
confidence = base × conflict_factor
```

| 因子 | 含义 |
| --- | --- |
| `weight_coverage` | 该角色已观测变量权重 / 配置总权重 |
| `quality_factor` | `confidence_policy`：`(1−0.5×低信息率)×(1−0.5×A3_fallback率)` |
| 变量 confidence | 画像层 facet 有效权重覆盖 |
| `conflict_share` | 该角色已观测 facet 中 `resolved_conflict` 权重占比 |
| `conflict_penalty` | 默认 0.35（`confidence_policy.json`） |

报告「置信标签」：按阈值映射为高/中/低；若 `conflict_share>0` 追加「·冲突」。  
**冲突须写明原因**（见报告第8节 `cause`）；**不因冲突降低风险分计分权重**（`conflict_weight_factor=1.0`），只降工程置信。

---

## 2. 判定阈值怎么来的？有没有实际量表规则？

**当前（锚定包后）**来自 `config/risk_scoring.json`：

| 角色 | 关注下界 | 重点关注下界 |
| --- | --- | --- |
| bully / victim / bystander | 45 | 70 |
| bully_victim | 50 | 75 |

等级由 `level_for` 半开区间划分。报告第 3 节写明 OLV-4 / literature_heuristic_v1 来源说明。

**性质**：Solberg & Olweus「每月 2–3 次」慢性卷入思想的**工程近似**，**不是**本校常模或 ROC 校准（`calibration_status=literature_heuristic_v1`）。详表见 [PSYCH_WEIGHT_THRESHOLDS.md](PSYCH_WEIGHT_THRESHOLDS.md)。

配套约束在 `config/scale_constraints.json` + `psych_agent/scale_gates.py`：假设占比封顶、无真实/习惯不可重点关注、兼有需双侧卷入等（OLV-1/2/3、BPB-3）。细则见 [SCALE_RULES_SOURCE.md](SCALE_RULES_SOURCE.md)。

---

## 3. 第 4 项「兼有 × 关系 = 未估计」原因？

形式分只统计 `scenario.facts.form == relational`（S05/S06）下的可计分变量，且需同时满足：

- 该形式下可用变量数 ≥ 2  
- 权重覆盖 ≥ 0.4  

（DBVS 分维思想：不足不报。）

对 `bully_victim`（现含 PV03/PV02/PV09/PV05/PV01/PV10）在关系情境下：多数变量无关系组；PV10 关系侧主要落到 `variable_facets.json` 中 **weight=0** 的 `U_E03_BARRIER` facet → 形式变量值仍为空；可计分维仍常不足 → **未估计**。属规则性不发分，不是漏算。

---

## 4. 第 6 / 7 项：权重、变量值、风险支持、Facet 计分权重

### 第 6 节（角色因素）

| 列 | 含义 | 来源 |
| --- | --- | --- |
| 配置权重 | 该 PV 在该角色公式中的权重 | `risk_scoring.roles.*`（文献启发式；旁观 BPB-1：PV07/PV05/PV04/PV10 = 0.30/0.25/0.25/0.20） |
| 变量值 0–1 | 画像汇总后的潜变量水平 | facet 加权 + 冲突软消解 + 强度 |
| 风险支持 | 计入角色分的量 | 风险正向=`value`；保护反向=`1−value`（`_risk_support`） |
| 角色分 | 0–100 工程指数 | `100×加权均值` → 经历小幅 boost → `scale_gates` |

### 第 7 节（Facet）

| 列 | 含义 | 来源 |
| --- | --- | --- |
| 值 | 该测量方面 0–1 | `conflict_resolver.resolve_facet` |
| 计分权重 | 配置权重 × score_weight_factor | `variable_facets.json` 的 weight（如 E03=0）；冲突面终版因子=1.0 |

量表相关：题号/构念边界来自 `dialogue_rubric` 与 `source/心理Agent+量表与心理变量.md`；**数值权重不是**发表量表因子载荷表。

---

## 5. 冲突如何判断与消解？有无心理学量表规则？

**判断**：同 facet 内出现相反方向 → `same_group_bidirectional` / `cross_frame` / `cross_scenario` / `cross_context`。

**消解**（工程启发式，见 `psych_agent/conflict_resolver.py` + `variable_scoring.conflict_policy`）：

1. 方向 × intensity → support（缺省按框架：真实 5 … 假设 1）  
2. 优先更高参照框架，否则框架加权均值  
3. 冲突面 `status=resolved_conflict`，写入可读 `cause` / `resolution_cause`；消解值以**满分权重**计入风险分  
4. 证据全留，写入 `conflict_audit` / `profile.conflict_resolutions`

**没有**某临床量表规定的「冲突题专用计分法」；目的是避免 0.5.2「冲突面剔除导致剩余面极端化」。

冲突还会在角色层生成**置信标签**（如「中·冲突」）：`conflict_share` 折减工程置信；**不得**用冲突作为放松风险分计算的理由。见 §1 与报告第8节。

---

## 6. 为何像「一条 evidence 对应多个标签」？

实际是 **1 `evidence_id` ↔ 1 `evidence_ref`**（`psych_agent/evidence_labels.py`）。

易误读两点：

1. 表格单元格里逗号分隔的多个标签 = **该变量/Facet 下多条证据**，不是一条 id 多个标签。  
2. 格式 `E024｜T024｜G02｜PV02↑` 中第三段是**源题号**；题号也可为 `E03`，与序号 `E024` 撞形，看起来像两个「E」。

内部 `DEV_` hash 仅在报告附录与 `evidence_ref` 对照。

---

## 7. 若要与真人问答印象更相符，应着重改什么？

优先（锚定包已部分落地，可继续拧）：

1. `config/scale_constraints.json` / `psych_agent/scale_gates.py` — 假设封顶、卷入门槛  
2. `config/risk_scoring.json` — 角色权重、阈值  
3. `config/variable_scoring.json` / `confidence_policy.json` — 强度、冲突策略、置信标签  
4. `config/variable_facets.json` — facet 权重（含 weight=0 面）

抽取层（改后需重跑 LLM）：`config/dialogue_rubric.json`、`prompts/turn_extractor.md`，用 `scripts/rerun_llm_from_trace.py`。

验收：`scripts/recompute_profile_risk.py` 或全量轨迹重抽。样例已从施暴 **61.29 → 55.22**（仍为关注），主要来自强度/冲突，非门控硬砍。

---

## 相关文件索引

| 路径 | 用途 |
| --- | --- |
| `docs/SCALE_RULES_SOURCE.md` | 发表量表逻辑 → 配置字段 |
| `config/risk_scoring.json` | 角色权重与阈值 |
| `config/scale_constraints.json` | A4 后置门控 |
| `config/variable_scoring.json` | 强度与冲突策略 |
| `config/confidence_policy.json` | 工程置信惩罚系数 |
| `psych_agent/risk_engine.py` | A4 计分 |
| `psych_agent/scale_gates.py` | 门控执行 |
| `psych_agent/conflict_resolver.py` | 冲突软消解 |
| `psych_agent/evidence_labels.py` | 可读证据标签 |
| `outputs/recompute_69db8d61/` | 终版对照样例（锚定包+冲突置信+冲突证据） |
