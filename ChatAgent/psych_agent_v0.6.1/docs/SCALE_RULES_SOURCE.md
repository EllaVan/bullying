# 发表量表计分逻辑 → 本系统映射（锚定包 olweus_dbvs_bpbq_v1）

**性质**：只抽取公开文献中的**计分/判定思想**，映射到对话 Evidence 体系；**不是**量表全文、不是临床常模标定、不是发生概率。  
自研题库 A01–G03→PV 仍见 `source/心理Agent+量表与心理变量.md`。

## 锚定来源（逻辑层）

| 代号 | 量表/文献家族 | 本包采用的逻辑 |
| --- | --- | --- |
| Olweus | Olweus Bully/Victim 及中文改编问卷 | 按行为**频次/卷入**区分角色；偶发或假设不等于反复欺凌；双角色需两侧卷入 |
| DBVS | Delaware Bullying Victimization Scale（学生卷） | 身体 / 言语 / 关系**分维独立**报告；维上证据不足则不估计 |
| BPBQ | Bullying Participant Behaviors Questionnaire | 旁观含局外人/消极助推 vs 保护者；旁观分独立于施暴分 |

选用文献亦指出：角色临界值因研究目的而异（每周一次、均分+1SD、前15% 等）。本系统在配置中写死下列**工程近似**切点，并在报告中标注来源包。

## 规则表与系统字段

### A. Olweus 式角色卷入

| ID | 文献逻辑（近似） | 配置/代码 |
| --- | --- | --- |
| OLV-1 | 无稳定卷入不得标为严重角色 | `bullying_construct_gates.*.high_requires_real_or_habit` |
| OLV-2 | 假设/偶发 ≠ 反复欺凌 | `hypothesis_discount.min_hypo_fraction=0.70`；封顶 bully/victim/bystander=54.99，bully_victim=59.99 |
| OLV-3 | 双角色需两侧卷入 | `bully_victim.high_requires_dual_involvement` + 受害经历门槛 |
| OLV-4 | 等级切点可陈述 | `risk_scoring.thresholds`：bully/victim/bystander=[45,70]；bully_victim=[50,75]（见 PSYCH_WEIGHT_THRESHOLDS） |

### B. DBVS 形式维

| ID | 文献逻辑 | 配置/代码 |
| --- | --- | --- |
| DBV-1 | 分维独立 | 既有 `form_scores` physical/verbal/relational |
| DBV-2 | 不足不报 | `form_policy.explain_insufficient`；报告第4节固定说明 |
| DBV-3 | 关系维只用关系情境 | `risk_engine._form_value` 按 scenario form 过滤（既有） |

### C. BPBQ 旁观

| ID | 文献逻辑 | 配置/代码 |
| --- | --- | --- |
| BPB-1 | 消极旁观抬分、保护反向 | `roles.bystander`：PV07=0.30，PV05=0.25，PV04/PV10=0.25/0.20 protective |
| BPB-2 | 旁观≠施暴 | 四角色独立计分（既有） |
| BPB-3 | 无旁观线索限制重点关注 | `bystander.high_requires_real_or_habit=true` |

### D. 强度 Likert

| ID | 实现 |
| --- | --- |
| INT-1 | `frame_default_intensity`：hypothetical=1，general_belief=2 |
| INT-2 | 冲突消解后计分权重因子=1.0（不因冲突放松分数）；原因写入 `conflict_audit.cause`；不确定性进置信标签 |

## 权重与阈值细节

角色内权重表、Solberg & Olweus 频次映射及元分析出处见 [PSYCH_WEIGHT_THRESHOLDS.md](PSYCH_WEIGHT_THRESHOLDS.md)。可信度落地步骤见 [CREDIBILITY_ROADMAP.md](CREDIBILITY_ROADMAP.md)。

## 免责

输出为未校准工程指数；不得替代心理测量学常模解释或临床诊断。修改本文件对应配置时，须同步 `scale_constraints.anchor_package`、`PSYCH_WEIGHT_THRESHOLDS.md` 与报告说明。
