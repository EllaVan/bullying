"""A5只解释固定画像和A4风险结果。数值由A4传入，展示由确定性代码负责。"""
from .config import require
from .dialogue_config import exact_keys
from .risk_engine import ROLES, validate_risk_result

ROLE_NAMES={'bully':'施暴相关','victim':'受害相关','bully_victim':'施暴与受害兼有相关'}
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
    require([n['role'] for n in narrative['role_notes']]==list(ROLES), 'A5必须按约定说明三个角色')
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

def render_report(profile, risk, narrative):
    """数值、等级、阈值由A4唯一提供；A5解释不能另造分数。"""
    validate_narrative(narrative,profile,risk)
    coverage=profile['coverage']; quality=coverage['response_quality']; policy=risk['scoring_policy']
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
           '本报告的数值为0—100独立风险分数，不是发生概率；三类分数不要求合计100。'
           '施暴与受害兼有分数描述规则中的冲突循环相关表现，不能据此确定现实身份。','',
           '## 2. 三类角色风险分数','',
           '| 角色 | 分数 /100 | 等级 | 工程置信指标 | 有效变量数 | 变量权重覆盖 |','| --- | --- | --- | --- | --- | --- |']
    for row in risk['roles']:
        lines.append(f'| {ROLE_NAMES[row["role"]]} | {show(row["score"])} | {LEVELS[row["level"]]} | {show(row["confidence"])} | {row["observed_feature_count"]}/{row["configured_feature_count"]} | {percent(row["weight_coverage"])} |')
        if row['unavailable_reasons']:
            lines.extend(['',f'{ROLE_NAMES[row["role"]]}不可判定原因：'+ '；'.join(REASONS.get(r,r) for r in row['unavailable_reasons'])+'。',''])
    lines.extend(['', '## 3. 判定阈值与计分规则','',
                  '| 角色 | 低分区 | 关注 | 重点关注 |','| --- | --- | --- | --- |'])
    for row in risk['roles']:
        a,b=row['thresholds']
        lines.append(f'| {ROLE_NAMES[row["role"]]} | 0 ≤ 分数 < {a:g} | {a:g} ≤ 分数 < {b:g} | {b:g} ≤ 分数 ≤ 100 |')
    lines.extend(['',
        '上表由本次A4实际使用的配置生成，等于边界时进入右侧等级。阈值属于未校准工程建议值。',
        f'发布分数的门槛：计划覆盖率 ≥ {policy["minimum_coverage_for_score"]:.0%}，角色有效变量权重覆盖 ≥ {policy["minimum_role_weight_coverage"]:.0%}，有效变量数 ≥ {policy["minimum_observed_features"]}。不达标则score=null，不显示低分区。',
        '计分：风险变量取value，保护变量取1−value；将可用变量的风险支持值按配置权重加权平均，再乘100。缺失变量不填0或0.5，不进入分母。',
        'Facet按测量方面汇总；同方面重复不增权。相反方向保留为conflict且该facet不计分。不同方面/不同事件的原话仍全部保留。求助顾虑描述不直接降低渠道认知。',
        '变量confidence为可计分facet的权重覆盖率；角色confidence再结合角色权重覆盖、低信息比例和A3故障比例折减。它不是模型准确率或统计置信概率。','',
        '## 4. 身体、言语、关系形式分数','',
        '| 角色 | 身体 | 言语 | 关系 |','| --- | --- | --- | --- |'])
    for row in risk['roles']:
        lines.append('| '+ROLE_NAMES[row['role']]+' | '+' | '.join(show(row['form_scores'][f]) for f in ('physical','verbal','relational'))+' |')
    lines.extend(['','形式分数只使用相应情境下的测量组；形式覆盖不足仍为未估计，不能从总体分数复制。','',
                  '## 5. 回答质量与系统异常','',
                  '| 指标 | 本次结果 |','| --- | --- |',
                  f'| 可统计回答 | {quality["eligible_response_turns"]} |',
                  f'| 简略回答（≤{quality["brief_response_max_characters"]}字） | {quality["brief_response_turns"]}；{percent(quality["brief_response_rate"])} |',
                  f'| 低信息回答 | {quality["low_information_turns"]} |',
                  f'| 显式跳题 | {quality["explicit_skip_turns"]} |',
                  f'| 安排换角度追问 | {quality["alternate_probe_scheduled_turns"]} |',
                  f'| A3结构故障降级 | {quality["a3_fallback_turns"]} |','',
                  ('**回答简略度超过50%，信息完整度可能受限。**' if quality['warning_triggered'] else '回答简略度未超过50%提示阈值。'),
                  '短回答可能是有效答案；不能用于判断被试的动机或态度。模型结构故障与学生低信息回答分开统计。','',
                  '## 6. 各角色因素与权重',''])
    factors={f['factor_id']:f for f in risk['factors']}
    for note in narrative['role_notes']:
        lines.extend(['### '+ROLE_NAMES[note['role']],'',_cell(note['text']),'',
                      '| 变量 | 配置权重 | 变量值0—1 | 风险方向 | 风险支持0—1 | Evidence |','| --- | --- | --- | --- | --- | --- |'])
        for fid in note['factor_ids']:
            f=factors[fid]
            lines.append(f'| {f["variable_id"]} | {f["weight"]:.3f} | {show(f["variable_value"])} | {"保护反向" if f["effect"]=="protective" else "风险正向"} | {show(f["risk_support"])} | {_cell(", ".join(f["evidence_ids"]) or "无")} |')
        lines.append('')
    notes={n['variable_id']:n for n in narrative['variable_notes']}
    lines.extend(['## 7. 十变量与Facet明细',''])
    for var in profile['variables']:
        lines.extend([f'### {var["variable_id"]} {var["name"]}','',_cell(notes[var['variable_id']]['text']),
                      f'变量值：{show(var["value"])}；工程覆盖指标：{show(var["confidence"])}。',
                      '解释边界：'+_cell(var['interpretation_boundary']),'',
                      '| Facet | 值 | 状态 | 计分权重 | 来源题 | Evidence |','| --- | --- | --- | --- | --- | --- |'])
        for f in var['facets']:
            lines.append(f'| {_cell(f["name"])} | {show(f["value"])} | {f["status"]} | {f["weight"]:g} | {", ".join(f["source_item_ids"]) or "未观察"} | {", ".join(f["evidence_ids"]) or "无"} |')
        lines.extend(['','测量组原文与来源：',''])
        for g in var['groups']:
            desc='；'.join(dict.fromkeys(s['value'] for s in g['slot_observations']))
            lines.append(f'- {_cell(g["facet"])}；{FRAME_NAMES[g["reference_frame"]]}；{", ".join(g["scenario_ids"])}；题目{", ".join(g["source_item_ids"])}：{_cell(desc)}')
        if not var['groups']:lines.append('暂无可用观察，保持未知。')
        lines.append('')
    lines.extend(['## 8. 真实经历与第三方叙述','',profile['experience']['note'],''])
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
    lines.extend(['## 9. 测量覆盖及未完成原因','',
                  '| 情境/条件 | 单元 | 原题 | 状态 | 尝试次数 | 缺失槽位/原因 |','| --- | --- | --- | --- | --- | --- |'])
    for r in coverage['units']:
        lines.append(f'| {r["scenario_id"]}/{r["condition_id"]} | {r["unit_id"]} | {", ".join(r["source_item_ids"])} | {STATUS_NAMES[r["status"]]} | {r["attempts"]} | {_cell(", ".join(r["missing_slots"]) or r["unfinished_reason"] or "—")} |')
    lines.extend(['','## 10. 原始Evidence与排除记录','',
                  '| Evidence | 轮次 | 变量/原题 | 来源 | 方向 | 原话 |','| --- | --- | --- | --- | --- | --- |'])
    for e in profile['evidence_ledger']:
        lines.append(f'| {e["evidence_id"]} | {e["turn_id"]} | {e["variable_id"]}/{", ".join(e["source_item_ids"])} | {FRAME_NAMES[e["reference_frame"]]} | {e["direction"]} | {_cell(e["quote"])} |')
    lines.extend(['',f'排除核心评分的Evidence：{len(profile["excluded_evidence"])}条。',''])
    for e in profile['excluded_evidence']: lines.append(f'- {e["evidence_id"]}：主体{e["subject"]}；来源{e["reference_frame"]}；{_cell(e["quote"])}')
    lines.extend(['','## 11. 自发背景','', 'F01—F04单列，不进入核心变量和风险评分。',''])
    for c in profile['context']:lines.append(f'- {c["item_id"]} / {c["turn_id"]}：{_cell(c["quote"])}')
    if not profile['context']:lines.append('未记录到自发背景。')
    lines.extend(['','## 12. 文件追溯与适用限制','',
                  '- 原始对话：conversation_trace.jsonl；每轮任务和校验结果：turns/Txxx/。',
                  '- 状态与恢复：dialogue_state.json、checkpoints/；覆盖：coverage_report.json。',
                  '- 画像与经历：profile.json、experience.json；评分输入及结果：risk_model_input.json、risk_result.json。',
                  '- Evidence：validated_evidence.json；A5解释：report_narrative.json。',
                  '- 结构测试和合成回放不代表真实LLM语义准确率；单一个案不能用来校准权重和阈值。',
                  '- 本版本不包含紧急风险处理、人工复核工作流、隐私权限系统。',''])
    return '\n'.join(lines)

TemplateRiskReporter = TemplateReportAgent
LLMRiskReporter = LLMReportAgent
