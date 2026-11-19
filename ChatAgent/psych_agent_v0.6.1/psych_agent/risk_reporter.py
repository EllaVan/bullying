"""A5只解释固定画像和A4风险结果。数值由A4传入，展示由确定性代码负责。"""
from .config import require
from .dialogue_config import exact_keys
from .evidence_labels import ensure_profile_refs, refs_for
from .risk_engine import ROLES, validate_risk_result

ROLE_NAMES={'bully':'施暴相关','victim':'受害相关','bully_victim':'施暴与受害兼有相关','bystander':'旁观相关'}
FRAME_NAMES={'hypothetical_intent':'假设意向','habitual_self_report':'通常自述',
             'real_event_self_report':'具体经历自述','general_belief':'一般信念',
             'task_performance':'模拟任务表现','unclear':'来源不明'}
STATUS_NAMES={'not_asked':'未问','partial':'部分覆盖','covered':'已覆盖','ambiguous':'含糊',
              'declined':'拒答','not_applicable':'不适用'}


class TemplateReportAgent:
    def report(self, profile, risk):
        notes=[]
        for v in profile['variables']:
            refs=sorted({e for g in v['groups'] for e in g['evidence_ids']})
            text=('本次尚无这一变量的可汇总观察。' if not v['groups'] else
                  '本次记录了'+ '、'.join(dict.fromkeys(g['facet'] for g in v['groups']))+'。各项来源和条件分别保留。')
            notes.append({'variable_id':v['variable_id'],'text':text,'evidence_ids':refs})
        return {'variable_notes':notes,
                'role_notes':[{'role':r['role'],'text':'以下解释独立的工程风险分数及证据来源；低覆盖度不发布分数。',
                               'factor_ids':r['factor_ids']} for r in risk['roles']]}


class LLMReportAgent:
    def __init__(self, cfg, transport):
        self.cfg,self.transport=cfg,transport

    def report(self, profile, risk):
        system=(self.cfg.root/'prompts/report_agent.md').read_text(encoding='utf-8')
        return self.transport.request(system,{'profile':profile,'risk':risk},profile['session_id'])


def validate_narrative(narrative, profile, risk):
    validate_risk_result(risk,profile)
    exact_keys(narrative,['variable_notes','role_notes'],'A5输出')
    require(isinstance(narrative['variable_notes'],list) and isinstance(narrative['role_notes'],list), 'A5说明必须为数组')
    vids=[n['variable_id'] for n in narrative['variable_notes']]
    require(len(vids)==len(set(vids)) and set(vids)=={v['variable_id'] for v in profile['variables']}, 'A5须逐变量说明，不能遗漏或添加变量')
    evid={e['evidence_id']:e for e in profile['evidence_ledger']}
    for note in narrative['variable_notes']:
        exact_keys(note,['variable_id','text','evidence_ids'],'变量说明')
        require(isinstance(note['text'],str) and note['text'].strip(), '变量说明为空')
        require(isinstance(note['evidence_ids'],list) and all(e in evid and evid[e]['variable_id']==note['variable_id'] for e in note['evidence_ids']), 'A5引用了不存在或不同变量的证据')
    require([n['role'] for n in narrative['role_notes']]==list(ROLES), 'A5必须按约定说明四个角色（含旁观）')
    by_role={r['role']:r for r in risk['roles']}
    for note in narrative['role_notes']:
        exact_keys(note,['role','text','factor_ids'],'角色说明')
        require(isinstance(note['text'],str) and note['text'].strip(), '角色说明为空')
        role=by_role[note['role']]
        require(isinstance(note['factor_ids'],list) and set(note['factor_ids']).issubset(role['factor_ids']), 'A5角色说明引用越界因素')
    return narrative


def _cell(value):
    return str(value).replace('|','\\|').replace('\n',' ')


LEVELS={'low':'低分区','attention':'关注','high':'重点关注','insufficient':'无法判断'}
REASONS={'plan_coverage_below_minimum':'计划覆盖率不足',
         'role_weight_coverage_below_minimum':'该角色可用变量权重不足',
         'too_few_observed_variables':'该角色有效变量数不足'}


def _join_refs(ids, id_to_ref):
    return ', '.join(refs_for(ids, id_to_ref)) if ids else '无'


def format_confidence_label(row, policy=None):
    """可读置信标签：高 / 中·冲突 / 低·冲突。"""
    names = (policy or {}).get('conflict_label_names') or {'high': '高', 'medium': '中', 'low': '低'}
    label = row.get('confidence_label') or 'low'
    text = names.get(label, label)
    if row.get('confidence_tag') == 'conflict':
        return f'{text}·冲突'
    return text


def render_report(profile, risk, narrative):
    """数值、等级、阈值由A4唯一提供；A5解释不能另造分数。展示使用 evidence_ref。"""
    validate_narrative(narrative,profile,risk)
    id_to_ref = ensure_profile_refs(profile)
    coverage=profile['coverage']; quality=coverage['response_quality']; policy=risk['scoring_policy']
    conf_names = {'high': '高', 'medium': '中', 'low': '低'}
    show=lambda v:'未估计' if v is None else f'{v:.2f}'
    percent=lambda v:'不可计算' if v is None else f'{v:.1%}'
    lines=['# 校园情境对话风险画像报告','',
           '## 1. 本次测评概况','',
           '| 项目 | 内容 |','| --- | --- |',
           f'| 版本 / 配置集合 | {profile["schema_version"]} / {profile["config_set_id"]} |',
           f'| 访谈 / 计划 | {profile["session_id"]} / {profile["plan_id"]} |',
           f'| 数据性质 | {"合成回放（非真人推理结果）" if profile["synthetic"] else "真实交互访谈"} |',
           f'| 结束状态 / 原因 | {profile["session_status"]} / {profile["stop_reason"]} |',
           f'| 已回答轮次 | {coverage["answered_turns"]} |',
           f'| 计划内测量单元实例 | {coverage["planned_unit_instances"]} |',
           f'| 槽位完成覆盖率 | {percent(coverage["coverage_fraction"])} |','',
           '**'+profile['test_scoring_notice']+'**','',
           '本报告的数值为0—100独立风险分数，不是发生概率；四类分数（含旁观）不要求合计100。'
           '施暴与受害兼有分数描述规则中的冲突循环相关表现；旁观描述目击/不干预/从众助推相关表现，均不能据此确定现实身份。'
           '证据在正文使用可读标签（如 E017｜T061｜E03｜PV10↓）；内部 hash 仅见附录对照。'
           '分数与工程置信分轴：冲突须写明原因；冲突不降低风险分的计分严格性（消解值满分权重计入），仅降低工程置信并打标签。','',
           '## 2. 四类角色风险分数','',
           '| 角色 | 分数 /100 | 等级 | 工程置信指标 | 置信标签 | 有效变量数 | 变量权重覆盖 |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for row in risk['roles']:
        tag = format_confidence_label(row, {'conflict_label_names': conf_names})
        lines.append(f'| {ROLE_NAMES[row["role"]]} | {show(row["score"])} | {LEVELS[row["level"]]} | {show(row["confidence"])} | {tag} | {row["observed_feature_count"]}/{row["configured_feature_count"]} | {percent(row["weight_coverage"])} |')
        if row.get('experience_boost'):
            b=row['experience_boost']
            lines.append(f'| ↳ 经历线索上浮 | {b["from_score"]:.2f} → {b["to_score"]:.2f}（+{b["boost"]:.0%}） | — | — | — | — | — |')
        if row.get('gate_applied'):
            g=row['gate_applied']
            codes='；'.join(a.get('detail') or a.get('code','') for a in g.get('actions') or []) or '量表门控'
            lines.append(f'| ↳ 量表门控 | {g["from_score"]:.2f} → {g["to_score"]:.2f}：{_cell(codes)} | — | — | — | — | — |')
        if row['unavailable_reasons']:
            lines.extend(['',f'{ROLE_NAMES[row["role"]]}不可判定原因：'+ '；'.join(REASONS.get(r,r) for r in row['unavailable_reasons'])+'。',''])
    if any(r.get('confidence_tag') == 'conflict' for r in risk['roles']):
        lines.extend(['',
            '说明：置信标签含「冲突」表示存在回答冲突面（原因见第8节）；冲突只降低工程置信，'
            '不降低风险分计分权重，也不单独改写分数等级。',''])
    lines.extend(['', '## 3. 判定阈值与计分规则','',
                  '| 角色 | 低分区 | 关注 | 重点关注 |','| --- | --- | --- | --- |'])
    for row in risk['roles']:
        a,b=row['thresholds']
        lines.append(f'| {ROLE_NAMES[row["role"]]} | 0 ≤ 分数 < {a:g} | {a:g} ≤ 分数 < {b:g} | {b:g} ≤ 分数 ≤ 100 |')
    anchor = (risk.get('scale_constraints') or {}).get('anchor_package') or (
        (policy.get('assessment_target') or {}).get('anchor_package'))
    threshold_note = policy.get('threshold_source_note') or '阈值属于未校准工程建议值。'
    lines.extend(['',
        '上表由本次A4实际使用的配置生成，等于边界时进入右侧等级。' + threshold_note,
        (f'锚定包：`{anchor}`（Olweus 卷入切点 + DBVS 形式维 + BPBQ 旁观构念的工程近似；见 docs/SCALE_RULES_SOURCE.md）。'
         if anchor else '阈值未经发表量表常模标定。'),
        f'发布分数的门槛：计划覆盖率 ≥ {policy["minimum_coverage_for_score"]:.0%}，角色有效变量权重覆盖 ≥ {policy["minimum_role_weight_coverage"]:.0%}，有效变量数 ≥ {policy["minimum_observed_features"]}。不达标则score=null，不显示低分区。',
        '计分：风险变量取value，保护变量取1−value；加权平均×100后，再经 scale_constraints 量表门控/封顶。',
        'Facet按测量方面汇总；同方面重复不增权。回答冲突先写明原因并软消解为单一值，再以满分权重计入风险分；不确定性只进置信标签。','',
        '## 4. 身体、言语、关系形式分数','',
        '| 角色 | 身体 | 言语 | 关系 |','| --- | --- | --- | --- |'])
    for row in risk['roles']:
        lines.append('| '+ROLE_NAMES[row['role']]+' | '+' | '.join(show(row['form_scores'][f]) for f in ('physical','verbal','relational'))+' |')
    form_note = ((risk.get('scale_constraints') or {}).get('form_policy') or {}).get('report_note') or (
        '形式分数只使用相应情境下的测量组；形式覆盖不足仍为未估计。')
    lines.extend(['', form_note, '',
                  '## 5. 回答质量与系统异常','',
                  '| 指标 | 本次结果 |','| --- | --- |',
                  f'| 可统计回答 | {quality["eligible_response_turns"]} |',
                  f'| 简略回答（≤{quality["brief_response_max_characters"]}字） | {quality["brief_response_turns"]}；{percent(quality["brief_response_rate"])} |',
                  f'| 低信息回答 | {quality["low_information_turns"]} |',
                  f'| 显式跳题 | {quality["explicit_skip_turns"]} |',
                  f'| 安排换角度追问 | {quality["alternate_probe_scheduled_turns"]} |',
                  f'| A3结构故障降级 | {quality["a3_fallback_turns"]} |','',
                  ('**回答简略度超过50%，信息完整度可能受限。**' if quality['warning_triggered'] else '回答简略度未超过50%提示阈值。'),
                  '短回答可能是有效答案；不能用于判断被试的动机或态度。模型结构故障与学生低信息回答分开统计。',
                  '**A3 结构降级轮次的证据默认不进入核心计分**（`exclusion_reason=a3_extraction_fallback`）；仅计入质量审计。','',
                  '## 6. 各角色因素与权重',''])
    factors={f['factor_id']:f for f in risk['factors']}
    for note in narrative['role_notes']:
        lines.extend(['### '+ROLE_NAMES[note['role']],'',_cell(note['text']),'',
                      '| 变量 | 配置权重 | 变量值0—1 | 风险方向 | 风险支持0—1 | 证据标签 |','| --- | --- | --- | --- | --- | --- |'])
        for fid in note['factor_ids']:
            f=factors[fid]
            lines.append(f'| {f["variable_id"]} | {f["weight"]:.3f} | {show(f["variable_value"])} | {"保护反向" if f["effect"]=="protective" else "风险正向"} | {show(f["risk_support"])} | {_cell(_join_refs(f["evidence_ids"], id_to_ref))} |')
        lines.append('')
    notes={n['variable_id']:n for n in narrative['variable_notes']}
    lines.extend(['## 7. 十变量与Facet明细',''])
    for var in profile['variables']:
        lines.extend([f'### {var["variable_id"]} {var["name"]}','',_cell(notes[var['variable_id']]['text']),
                      f'变量值：{show(var["value"])}；工程覆盖指标：{show(var["confidence"])}。',
                      '解释边界：'+_cell(var['interpretation_boundary']),'',
                      '| Facet | 值 | 状态 | 计分权重 | 来源题 | 证据标签 |','| --- | --- | --- | --- | --- | --- |'])
        for f in var['facets']:
            if f.get('score_weight_factor') is not None and f.get('score_weight_factor') != 1:
                weight_note = f'{f["weight"]:g}×{f["score_weight_factor"]:.2f}'
            else:
                weight_note = f'{f["weight"]:g}'
            lines.append(f'| {_cell(f["name"])} | {show(f["value"])} | {f["status"]} | {weight_note} | {", ".join(f["source_item_ids"]) or "未观察"} | {_cell(_join_refs(f["evidence_ids"], id_to_ref))} |')
        lines.extend(['','测量组原文与来源：',''])
        for g in var['groups']:
            desc='；'.join(dict.fromkeys(s['value'] for s in g['slot_observations']))
            lines.append(f'- {_cell(g["facet"])}；{FRAME_NAMES[g["reference_frame"]]}；{", ".join(g["scenario_ids"])}；题目{", ".join(g["source_item_ids"])}：{_cell(desc)}')
        if not var['groups']:lines.append('暂无可用观察，保持未知。')
        lines.append('')
    conflicts = profile.get('conflict_resolutions') or []
    ledger = {e['evidence_id']: e for e in profile.get('evidence_ledger') or []}
    lines.extend(['## 8. 回答冲突消解','',
                  f'共记录 {len(conflicts)} 处 facet 级冲突。每处须写明冲突原因与冲突各方证据原文；两侧证据均保留。',
                  '消解后的值以配置权重**严格计入**风险分（不因冲突降权）；冲突仅反映在工程置信标签。','',
                  ])
    if conflicts:
        lines.extend(['| 变量 | Facet | 冲突原因 | 消解做法 | 消解值 | 计分权重因子 |',
                      '| --- | --- | --- | --- | --- | --- |'])
        for c in conflicts:
            cause = c.get('cause') or c.get('conflict_type') or ''
            how = c.get('resolution_cause') or c.get('resolution_method') or ''
            lines.append(f'| {c.get("variable_id","")} | {_cell(c.get("facet_id",""))} | {_cell(cause)} | '
                         f'{_cell(how)} | {show(c.get("resolved_value"))} | {c.get("score_weight_factor",1)} |')
        lines.append('')
        for c in conflicts:
            cause = c.get('cause') or c.get('conflict_type') or '原因未标注'
            lines.append(f'- **{c.get("variable_id")}/{c.get("facet_id")}**：{_cell(cause)}')
            how = c.get('resolution_cause') or c.get('resolution_method')
            if how:
                lines.append(f'  - 消解：{_cell(how)}')
            lines.append('  - 冲突证据：')
            for side in c.get('sides') or []:
                eid = side.get('evidence_id')
                ev = ledger.get(eid) or {}
                label = id_to_ref.get(eid, eid or '无')
                if ev.get('evidence_ref'):
                    label = ev['evidence_ref']
                frame = FRAME_NAMES.get(side.get('reference_frame') or ev.get('reference_frame'),
                                       side.get('reference_frame') or ev.get('reference_frame') or '—')
                quote = side.get('quote') or ev.get('quote') or '（无原话）'
                turn = side.get('turn_id') or ev.get('turn_id') or '—'
                items = side.get('source_item_ids') or ev.get('source_item_ids') or []
                item_txt = ','.join(items) if items else '—'
                scenarios = ','.join(side.get('scenario_ids') or []) or '—'
                lines.append(
                    f'    - **{_cell(label)}**｜轮次 {turn}｜题 {item_txt}｜情境 {scenarios}｜'
                    f'方向 {side.get("direction")}｜强度 {side.get("intensity")}｜框架 {frame}｜'
                    f'support {side.get("support")}'
                )
                lines.append(f'      原话：{_cell(quote)}')
        lines.append('')
    else:
        lines.extend(['本次无 facet 级方向冲突。',''])
    lines.extend(['## 9. 真实经历与第三方叙述','',profile['experience']['note'],''])
    for kind,name in [('events','本人经历'),('third_party_events','第三方内容')]:
        lines.extend(['### '+name,'','| 轮次 | 主体 | 角色线索 | 原话 |','| --- | --- | --- | --- |'])
        rows=profile['experience'][kind]
        for e in rows:
            lines.append(f'| {e["turn_id"]} | {e["subject"]} | {e["role"]} | {_cell(e["quote"])} |')
        if not rows:lines.append('| — | — | unknown | 无已校验记录，不等于没有经历 |')
        for e in rows:
            for d in e.get('details',[]):
                lines.append(f'- {e["experience_id"]} / {d["field"]}={_cell(d["value"])}，依据：{_cell(d["quote"])}')
        lines.append('')
    lines.extend(['## 10. 测量覆盖及未完成原因','',
                  '| 情境/条件 | 单元 | 原题 | 状态 | 尝试次数 | 缺失槽位/原因 |','| --- | --- | --- | --- | --- | --- |'])
    for r in coverage['units']:
        lines.append(f'| {r["scenario_id"]}/{r["condition_id"]} | {r["unit_id"]} | {", ".join(r["source_item_ids"])} | {STATUS_NAMES[r["status"]]} | {r["attempts"]} | {_cell(", ".join(r["missing_slots"]) or r["unfinished_reason"] or "—")} |')
    lines.extend(['','## 11. 原始Evidence与排除记录','',
                  '| 证据标签 | 轮次 | 变量/原题 | 来源 | 方向 | 强度 | 原话 |','| --- | --- | --- | --- | --- | --- | --- |'])
    for e in profile['evidence_ledger']:
        intensity = e.get('intensity')
        intensity_cell = '—' if intensity is None else str(intensity)
        lines.append(f'| {_cell(e.get("evidence_ref") or e["evidence_id"])} | {e["turn_id"]} | {e["variable_id"]}/{", ".join(e["source_item_ids"])} | {FRAME_NAMES[e["reference_frame"]]} | {e["direction"]} | {intensity_cell} | {_cell(e["quote"])} |')
    lines.extend(['',f'排除核心评分的Evidence：{len(profile["excluded_evidence"])}条。',''])
    for e in profile['excluded_evidence']:
        reason = e.get('exclusion_reason') or 'other'
        lines.append(f'- {_cell(e.get("evidence_ref") or e["evidence_id"])}：排除原因 {reason}；主体{e["subject"]}；来源{e["reference_frame"]}；{_cell(e["quote"])}')
    lines.extend(['','## 12. 自发背景','', 'F01—F04单列，不进入核心变量和风险评分。',''])
    for c in profile['context']:lines.append(f'- {c["item_id"]} / {c["turn_id"]}：{_cell(c["quote"])}')
    if not profile['context']:lines.append('未记录到自发背景。')
    lines.extend(['','## 13. 证据标签与内部ID对照（研发用）','',
                  '| 证据标签 | 内部 evidence_id |','| --- | --- |'])
    for e in profile['evidence_ledger']:
        lines.append(f'| {_cell(e.get("evidence_ref",""))} | {e["evidence_id"]} |')
    if not profile['evidence_ledger']:
        lines.append('| — | — |')
    lines.extend(['','## 14. 文件追溯与适用限制','',
                  '- 原始对话：conversation_trace.jsonl；每轮任务和校验结果：turns/Txxx/。',
                  '- 状态与恢复：dialogue_state.json、checkpoints/；覆盖：coverage_report.json。',
                  '- 画像与经历：profile.json、experience.json；评分：risk_model_input.json、risk_result.json。',
                  '- 简洁报告：report_brief.md；完整报告：report.md；A5：report_narrative.json。',
                  '- 冲突审计：profile.conflict_resolutions；量表门控：risk_result.scale_constraints。',
                  '- 本版本不包含紧急风险处理、人工复核工作流、隐私权限系统；分数未做统计校准。',''])
    return '\n'.join(lines)


def render_brief_report(profile, risk, narrative=None):
    """一线可读简洁版：结论、关键证据、必要限制。"""
    id_to_ref = ensure_profile_refs(profile)
    show=lambda v:'未估计' if v is None else f'{v:.2f}'
    ledger={e['evidence_id']:e for e in profile['evidence_ledger']}
    factors={f['factor_id']:f for f in risk['factors']}
    lines=['# 校园霸凌风险测评 · 简洁报告','',
           f'会话 `{profile["session_id"]}` · 计划 `{profile["plan_id"]}` · 配置 `{profile["config_set_id"]}`',
           '',
           '**本报告为未校准工程筛查结果，不是临床诊断或处分依据。**','',
           '## 1. 结论','',
           '| 角色 | 分数 | 等级 | 置信标签 |','| --- | --- | --- | --- |']
    impressions=[]
    conflict_roles=[]
    for row in risk['roles']:
        tag = format_confidence_label(row)
        lines.append(f'| {ROLE_NAMES[row["role"]]} | {show(row["score"])} | {LEVELS[row["level"]]} | {tag} |')
        if row['score'] is not None and row['level'] in ('attention','high'):
            impressions.append(f'{ROLE_NAMES[row["role"]]}为「{LEVELS[row["level"]]}」')
        if row.get('confidence_tag') == 'conflict':
            conflict_roles.append(ROLE_NAMES[row['role']])
    if impressions:
        lines.extend(['', '总体：本次访谈中' + '；'.join(impressions) + '。其余角色见上表。',''])
    else:
        lines.extend(['', '总体：各角色均未进入关注/重点关注，或证据不足无法判定。',''])
    if conflict_roles:
        lines.append('注意：' + '、'.join(conflict_roles)
                     + ' 含回答冲突（原因见完整报告第8节）。冲突不降低风险分计分权重；置信标签提示结论需人工复核。')
        lines.append('')
    gates=risk.get('scale_constraints',{}).get('gates') or []
    if gates:
        lines.append('量表门控已对部分角色分数封顶（详见完整报告）。')
        lines.append('')
    lines.extend(['## 2. 关键证据','',
                  '每角色最多列出若干条支持性原话（可读标签）。',''])
    for row in risk['roles']:
        lines.append(f'### {ROLE_NAMES[row["role"]]}')
        picked=[]
        for fid in row['factor_ids']:
            f=factors[fid]
            if f.get('risk_support') is None:
                continue
            for eid in f.get('evidence_ids') or []:
                e=ledger.get(eid)
                if not e:
                    continue
                picked.append(e)
                if len(picked) >= 4:
                    break
            if len(picked) >= 4:
                break
        if not picked:
            lines.append('暂无足够核心证据摘录。')
        else:
            for e in picked[:4]:
                ref=e.get('evidence_ref') or id_to_ref.get(e['evidence_id'], e['evidence_id'])
                lines.append(f'- **{_cell(ref)}**（{FRAME_NAMES.get(e["reference_frame"], e["reference_frame"])}）：{_cell(e["quote"])}')
        lines.append('')
    quality=profile['coverage']['response_quality']
    conflicts=profile.get('conflict_resolutions') or []
    lines.extend(['## 3. 必须知晓的限制','',
                  f'- 覆盖：已答 {profile["coverage"]["answered_turns"]} 轮；槽位完成 {profile["coverage"]["coverage_fraction"] or 0:.1%}。',
                  f'- A3 结构降级 {quality["a3_fallback_turns"]} 次（该轮证据不进核心计分）；facet 冲突消解 {len(conflicts)} 处。',
                  f'- 本人真实经历记录：{len(profile["experience"].get("events") or [])} 条（无记录≠无经历）。',
                  '- 情境假设回答不能直接等同已发生霸凌；分数经量表构念门控，仍属工程指数。权重/阈值为文献启发式，见 PSYCH_WEIGHT_THRESHOLDS。',
                  '- 完整因子表、Facet、冲突两侧与内部 ID 对照见 `report.md`。',''])
    return '\n'.join(lines)


TemplateRiskReporter = TemplateReportAgent
LLMRiskReporter = LLMReportAgent
