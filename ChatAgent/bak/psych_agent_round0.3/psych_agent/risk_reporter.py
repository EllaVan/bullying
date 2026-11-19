"""A4只解释固定画像和风险结果。数值由风险接口传入，展示由确定性代码负责。"""
from .config import require
from .dialogue_config import exact_keys
from .risk_engine import ROLES, validate_risk_result

ROLE_NAMES={'bully':'施暴相关','victim':'受害相关','bully_victim':'施暴与受害兼有相关'}
FRAME_NAMES={'hypothetical_intent':'假设意向','habitual_self_report':'通常自述',
             'real_event_self_report':'具体经历自述','general_belief':'一般信念',
             'task_performance':'模拟任务表现','unclear':'来源不明'}
STATUS_NAMES={'not_asked':'未问','partial':'部分覆盖','covered':'已覆盖','ambiguous':'含糊',
              'declined':'拒答','not_applicable':'不适用'}


class TemplateRiskReporter:
    def report(self, profile, risk):
        notes=[]
        for v in profile['variables']:
            refs=sorted({e for g in v['groups'] for e in g['evidence_ids']})
            text=('本次尚无这一变量的可汇总观察。' if not v['groups'] else
                  '本次记录了'+ '、'.join(dict.fromkeys(g['facet'] for g in v['groups']))+'。各项来源和条件分别保留。')
            notes.append({'variable_id':v['variable_id'],'text':text,'evidence_ids':refs})
        return {'variable_notes':notes,
                'role_notes':[{'role':r['role'],'text':'以下列出原设计关联的观察信息，不将线索数量换算成角色风险。',
                               'factor_ids':r['factor_ids']} for r in risk['roles']]}


class LLMRiskReporter:
    def __init__(self, cfg, transport):
        self.cfg,self.transport=cfg,transport

    def report(self, profile, risk):
        system=(self.cfg.root/'prompts/risk_reporter.md').read_text(encoding='utf-8')
        return self.transport.request(system,{'profile':profile,'risk':risk},profile['session_id'])


def validate_narrative(narrative, profile, risk):
    validate_risk_result(risk,profile)
    exact_keys(narrative,['variable_notes','role_notes'],'A4输出')
    require(isinstance(narrative['variable_notes'],list) and isinstance(narrative['role_notes'],list), 'A4说明必须为数组')
    vids=[n['variable_id'] for n in narrative['variable_notes']]
    require(len(vids)==len(set(vids)) and set(vids)=={v['variable_id'] for v in profile['variables']}, 'A4须逐变量说明，不能遗漏或添加变量')
    evid={e['evidence_id']:e for e in profile['evidence_ledger']}
    for note in narrative['variable_notes']:
        exact_keys(note,['variable_id','text','evidence_ids'],'变量说明')
        require(isinstance(note['text'],str) and note['text'].strip(), '变量说明为空')
        require(isinstance(note['evidence_ids'],list) and all(e in evid and evid[e]['variable_id']==note['variable_id'] for e in note['evidence_ids']), 'A4引用了不存在或不同变量的证据')
    require([n['role'] for n in narrative['role_notes']]==list(ROLES), 'A4必须按约定说明三个角色')
    by_role={r['role']:r for r in risk['roles']}
    for note in narrative['role_notes']:
        exact_keys(note,['role','text','factor_ids'],'角色说明')
        require(isinstance(note['text'],str) and note['text'].strip(), '角色说明为空')
        role=by_role[note['role']]
        require(isinstance(note['factor_ids'],list) and set(note['factor_ids']).issubset(role['factor_ids']+role['shared_factor_ids']), 'A4角色说明引用越界因素')
    return narrative


def _cell(value):
    return str(value).replace('|','\\|').replace('\n',' ')


def render_report(profile, risk, narrative):
    validate_narrative(narrative,profile,risk)
    coverage=profile['coverage']
    lines=['**校园情境多轮对话画像**','',f'访谈编号：{profile["session_id"]}；计划：{profile["plan_id"]}。',
           '本报告来自合成回放，用于功能验证。' if profile['synthetic'] else '本报告描述本次对话中的表达与情境反应。','',
           f'已完成回答 {coverage["answered_turns"]} 轮；计划含 {coverage["planned_unit_instances"]} 个测量单元实例，其中已覆盖 {coverage["counts"]["covered"]} 个、不适用 {coverage["counts"]["not_applicable"]} 个。',
           '未问、拒答、不适用和缺少证据分别记录，不视为低风险。','',
           '**角色相关画像**','','| 角色 | 概率 | 置信度 | 结果状态 |','| --- | --- | --- | --- |']
    for r in risk['roles']:
        value='未估计' if r['probability'] is None else f'{r["probability"]:.4f}'
        confidence='未提供' if r['confidence'] is None else f'{r["confidence"]:.4f}'
        status='未接入概率模型' if r['probability'] is None else '外部模型结果'
        lines.append(f'| {ROLE_NAMES[r["role"]]} | {value} | {confidence} | {status} |')
    lines.extend(['',risk['note'],''])
    factors={f['factor_id']:f for f in risk['factors']}
    for n in narrative['role_notes']:
        lines.append(f'**{ROLE_NAMES[n["role"]]}**：{n["text"]}')
        lines.append('')
        for fid in n['factor_ids']:
            f=factors[fid]
            lines.append(f'- {f["variable_id"]}／{f["facet"]}；{FRAME_NAMES[f["reference_frame"]]}；证据：'+', '.join(f['evidence_ids']))
        if not n['factor_ids']:
            lines.append('本次尚无对应的方向证据。')
        lines.append('')
    shared=sorted({fid for r in risk['roles'] for fid in r['shared_factor_ids']})
    if shared:
        lines.extend(['**共同的求助与冲突应对线索**','','这些内容依据原表与风险持续或升级相关，统一列出，避免在三个角色下重复。',''])
        for fid in shared:
            f=factors[fid]
            lines.append(f'- {f["variable_id"]}／{f["facet"]}；{FRAME_NAMES[f["reference_frame"]]}；证据：'+', '.join(f['evidence_ids']))
        lines.append('')
    notes={n['variable_id']:n for n in narrative['variable_notes']}
    for v in profile['variables']:
        lines.extend([f'**{v["variable_id"]} {v["name"]}**','',notes[v['variable_id']]['text'],
                      '解释边界：'+v['interpretation_boundary'],''])
        for g in v['groups']:
            descriptions=list(dict.fromkeys(s['value'] for s in g['slot_observations']))
            lines.append(f'- {g["facet"]}〔原题：'+', '.join(g['source_item_ids'])+f'〕（{FRAME_NAMES[g["reference_frame"]]}，'+', '.join(g['scenario_ids'])+
                         f'／{g["condition_id"]}）：'+'；'.join(descriptions))
        lines.append('')
    lines.extend(['**测量覆盖与未完成项**','','| 情境/条件 | 单元 | 来源题目 | 状态 | 缺失信息 |','| --- | --- | --- | --- | --- |'])
    for r in coverage['units']:
        lines.append(f'| {r["scenario_id"]}/{r["condition_id"]} | {r["unit_id"]} | {", ".join(r["source_item_ids"])} | {STATUS_NAMES[r["status"]]} | {_cell(", ".join(r["missing_slots"]) or "—")} |')
    lines.extend(['','**原始证据**','','| 证据ID | 轮次 | 变量/来源题目 | 原话 |','| --- | --- | --- | --- |'])
    for e in profile['evidence_ledger']:
        lines.append(f'| {e["evidence_id"]} | {e["turn_id"]} | {e["variable_id"]}/{", ".join(e["source_item_ids"])} | {_cell(e["quote"])} |')
    lines.extend(['','**自发背景信息**','','F类单独保存，没有进入核心变量或风险模型输入。',''])
    for c in profile['context']:
        lines.append(f'- {c["item_id"]}，{c["turn_id"]}：{c["quote"]}')
    if not profile['context']:
        lines.append('本次未记录到相关自发背景。')
    return '\n'.join(lines)+'\n'
