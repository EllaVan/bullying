# 文献启发式权重与阈值（literature_heuristic_v1）

**性质**：在缺少标注者/本校常模时，用发表问卷与元分析的**相对效应量与频次切点思想**指定工程权重与阈值，便于心理学可解释。  
**不是**：ROC 校准、本校常模、诊断切点、处分依据。

配置入口：`config/risk_scoring.json`（`assessment_target.calibration_status = literature_heuristic_v1`）。  
构念门控仍见 [SCALE_RULES_SOURCE.md](SCALE_RULES_SOURCE.md)。

---

## 1. 阈值（角色工程分 0–100）

### 文献依据

- **Solberg & Olweus (2003)**：全球卷入题以「每月 2–3 次」作为慢性欺凌/受害下界；更高档为约每周一次或更频。
- 对话路径无原题频次 Likert，用 **intensity / 参照框架** 近似：偶发或纯假设 ≈ 低区；达重复标准 ≈ 关注；每周级真实/习惯 ≈ 重点关注（仍受 `scale_constraints` 门控）。

### 工程映射

| 档 | Olweus 频次含义 | intensity / 框架近似 | 工程分 |
| --- | --- | --- | --- |
| 低分区 | 无或偶发（once/twice） | 1–2 或纯假设 | score &lt; 45 |
| 关注 | ≈每月 2–3 次 | ≥3 或习惯/真实 | 45 ≤ score &lt; 70 |
| 重点关注 | 每周级反复 | ≥4 且真实/习惯 | score ≥ 70 |

| 角色 | `thresholds` [attention, high] | 说明 |
| --- | --- | --- |
| bully / victim / bystander | **[45, 70]** | 关注档对齐「达重复标准」 |
| bully_victim | **[50, 75]** | 双角色更严；两侧卷入靠门控 OLV-3 |

OBVQ 等连续分带（如 14–70 上 Low/Occasional/Frequent）仅作对照，**不**直接当本系统切点（题量/量纲不同）。

---

## 2. 角色权重（各角色内和为 1.0）

原则：元分析/问卷构念的相对重要性 → 相对权重；保护因素 `protective` 在 A4 按 `1−value` 计入风险支持；旁观对齐 BPBQ（从众/合理化 vs 共情/求助）。

| 构念 | 变量 | 文献要点 | 用途 |
| --- | --- | --- | --- |
| 道德脱离 | PV05 | MD–欺凌约 r≈0.31（Killer et al. meta） | bully / bystander 加重 |
| 攻击 | PV02 | IBS bullying + fighting 核心行为 | bully 加重 |
| 敌意归因 | PV03 | SIP 施暴/双角色路径 | bully、bully_victim |
| 共情 | PV04 | 与欺凌负相关 / 保护 | bully、bystander、victim 保护 |
| 排斥敏感 | PV09 | 受害相关 | victim、bully_victim |
| 同伴支持 | PV08 | 受害缓冲 | victim 保护 |
| 求助/干预 | PV10 | 受害与旁观保护者 | victim / bystander 保护 |
| 从众 | PV07 | 关系欺凌/助推旁观 | bystander、轻度 bully |
| 支配 | PV06 | 权力/关系型施暴 | bully 中等 |
| 情绪调节 | PV01 | 冲突升级缓冲 | 各角色轻度保护 |

### bully

| 变量 | effect | weight |
| --- | --- | --- |
| PV05 | risk_increasing | 0.25 |
| PV02 | risk_increasing | 0.25 |
| PV03 | risk_increasing | 0.20 |
| PV06 | risk_increasing | 0.12 |
| PV07 | risk_increasing | 0.10 |
| PV01 | protective | 0.08 |

### victim

| 变量 | effect | weight |
| --- | --- | --- |
| PV09 | risk_increasing | 0.28 |
| PV08 | protective | 0.25 |
| PV10 | protective | 0.22 |
| PV01 | protective | 0.15 |
| PV04 | protective | 0.10 |

### bully_victim

| 变量 | effect | weight |
| --- | --- | --- |
| PV03 | risk_increasing | 0.22 |
| PV02 | risk_increasing | 0.22 |
| PV09 | risk_increasing | 0.22 |
| PV05 | risk_increasing | 0.14 |
| PV10 | protective | 0.12 |
| PV01 | protective | 0.08 |

相对旧配置增加 PV05，体现双角色攻击 + 合理化；两侧卷入仍靠 OLV-3 门控。`risk_profile_rules.role_variables` 须同步含 PV05。

### bystander

| 变量 | effect | weight |
| --- | --- | --- |
| PV07 | risk_increasing | 0.30 |
| PV05 | risk_increasing | 0.25 |
| PV04 | protective | 0.25 |
| PV10 | protective | 0.20 |

说明：MD meta 对「纯旁观」关联常不显著，但对助推/冷漠合理化仍保留中高 PV05 权重（BPBQ 消极参与思想）。

---

## 3. 主要文献线索（非穷尽）

- Solberg, M. E., & Olweus, D. (2003). Prevalence estimation of school bullying with the Olweus Bully/Victim Questionnaire. *Aggressive Behavior*.
- Killer, B., et al. meta-analysis：道德脱离与欺凌相关。
- IBS / DBVS / BPBQ：行为卷入、身体–言语–关系分维、旁观参与类型（见 SCALE_RULES_SOURCE）。
- 社会信息加工（SIP）、共情与同伴支持作为受害/干预保护因素的综述传统。

---

## 4. 免责

本包为**可解释启发式**。更换权重/阈值时：同步本文件、`SCALE_RULES_SOURCE.md`、`risk_scoring.json` / `risk_profile_rules.json`，并重跑 `dialogue-validate` 与样例重算。
