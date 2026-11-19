"""维护者工具：从逐项编写的测量设计生成多轮配置；应用运行时不执行本文件。

题目原文和变量定义始终读取原有两份配置。本文件不包含量表计分、风险阈值或模型权重。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def save(name, value):
    (ROOT / 'config' / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build():
    items = {r['item_id']: r for r in json.loads((ROOT/'config/questionnaire_mapping.json').read_text())['items']}
    units, rules = [], []

    def unit(code, sources, facet, frame, question, slots, criteria, boundary, requires=None):
        uid = 'U_' + code
        vids = list(criteria)
        row = dict(unit_id=uid, source_item_ids=sources.split(), target_variable_ids=vids,
                   facet=facet, reference_frame=frame, reference_period='unspecified',
                   question_template=question, required_slots=[{'slot_id': k, 'description': v} for k, v in slots],
                   applicability=requires or {}, rule_ids=[], interpretation_boundary=boundary,
                   completion_rule='同一参照方式下，自我回答明确提供全部槽位；明确不存在或否认也可填槽。未提及不等于否认。',
                   validation_status='engineering_draft_not_psychometrically_validated')
        for vid, directions in criteria.items():
            for direction, criterion in directions.items():
                rid = f'DR_{code}_{vid}_{direction.upper()}'
                row['rule_ids'].append(rid)
                rules.append(dict(rule_id=rid, unit_id=uid, item_ids=[i for i in row['source_item_ids'] if vid in items[i]['variable_ids']],
                                  variable_id=vid, direction=direction, context_only=False,
                                  criterion=criterion, do_not_infer_when=boundary,
                                  review_status='engineering_draft_requires_review'))
        units.append(row)

    H = 'hypothetical_intent'
    S = 'habitual_self_report'
    B = 'general_belief'
    unit('A01_RECOVERY', 'A01', '情绪恢复过程', S,
         '像这种让你不舒服的事情，平时你的心情通常会怎样慢慢平静下来？',
         [('recovery', '恢复过程或恢复困难；不能只记录是否生气')],
         {'PV01': {'higher': '明确自述通常能逐渐恢复平静，并说明恢复过程。', 'lower': '明确自述通常长时间难以平静或恢复困难。'}},
         '只说生气或先忍住不足以判断恢复；不设置未经依据的分钟阈值。')
    unit('A02_ATTRIBUTION', 'A02 A03', '对他人意图的解释', H,
         '你会怎样理解对方刚才的举动？', [('interpretation', '对他人意图的解释及是否保留其他可能')],
         {'PV03': {'higher': '在意图未明确的情境中断定对方故意针对自己。', 'lower': '明确保留非敌意的解释可能，不急于认定恶意。'}},
         '来源包含原设计 A03→PV03 的归因方面；报复本身不构成归因。明确恶意情境不测归因偏向。', {'intent_clarity': ['ambiguous']})
    unit('A02_RUMINATION', 'A02', '认为被针对后的反复思考', S,
         '平时当你觉得有人在针对你时，之后这件事通常会怎样留在你的脑海里？', [('thinking', '认为被针对之后的思考持续情况')],
         {'PV03': {'higher': '明确自述认为被针对后会持续、反复想着这件事。', 'lower': '明确自述在这种条件下通常不会持续反复想着。'}},
         '记录条件下的反复思考；不据此断言对方真实恶意或新增一个心理变量。')
    unit('A03_REVENGE', 'A03', '报复意向', H,
         '接下来你希望对方经历什么，或者有什么变化？', [('desired_outcome', '希望对方受到的影响或明确不希望其受损')],
         {'PV02': {'higher': '明确希望报复，使对方也受损或难受。', 'lower': '明确拒绝报复或不希望对方受到伤害。'}},
         '表达不公平、生气不等于报复；本单元只选 PV02，PV03 由独立归因单元处理。')
    unit('A04_PAUSE', 'A04', '暂停后再决策', H,
         '如果这时你很生气，在决定下一步之前，你会怎么做？', [('pause', '是否暂停或延迟行动，以及与决策的关系')],
         {'PV01': {'higher': '明确先暂停或平静，再决定行动。', 'lower': '明确表示生气时无法暂停便直接行动。'},
          'PV10': {'higher': '明确把暂停再决定作为冲突应对方法。', 'lower': '明确表示在冲突中难以采取暂停再决定的办法。'}},
         '仅忍住不代表平静；意向不能标为实际能力。')
    unit('B01_EMOTION', 'B01', '识别他人情绪', H,
         '你会怎样了解那位同学此刻的感受？', [('emotion_clues', '注意到的情绪线索或确认感受的方法')],
         {'PV04': {'higher': '明确关注他人可能隐藏的不适，并说明观察或确认感受的方法。', 'lower': '明确表示即使注意到线索也不关注对方感受。'}},
         '没有提及感受不等于缺乏共情；判断正确与否需任务依据。')
    unit('B02_CONCERN', 'B02', '对不亲近同学的痛苦关注', H,
         '看到大家这样对待那位你平时不太合得来的同学，你会有什么感受？', [('concern', '对他人受针对的感受')],
         {'PV04': {'higher': '明确即使不喜欢对方仍关心其痛苦或对其被针对感到不舒服。', 'lower': '明确因不喜欢对方而对其痛苦漠不关心或感到愉快。'}},
         '必须有不亲近或不合得来这一前提；不能由沉默推断。', {'affinity': ['not_close']})
    unit('B03_HARM', 'B03', '玩笑中的感受与伤害', H,
         '你会怎样判断那位同学是不是也觉得这件事好笑？', [('perspective', '如何考虑被开玩笑者的体验')],
         {'PV04': {'higher': '明确考虑被开玩笑者是否真的觉得好笑、可能受伤或需要确认。', 'lower': '明确否认需要考虑被开玩笑者的感受。'}},
         '本单元仅测 PV04；不能自动反向推算 PV05。', {'joking': ['present']})
    unit('B03_JUSTIFICATION', 'B03', '玩笑是否可以继续的判断', B,
         '你觉得大家在什么情况下应该停止这种玩笑？', [('boundary', '停止玩笑的界线及理由')],
         {'PV05': {'higher': '明确以大家觉得好笑等理由合理化继续让对方难受。', 'lower': '明确认为对方不愿意或受到伤害就不能以玩笑为由继续。'}},
         '需明确的合理化或反对理由；只识别伤害不自动产生道德脱离反分。', {'joking': ['present']})
    unit('B04_RESPONSIBILITY', 'B04', '群体责任判断', B,
         '好几个人一起参与这件事时，你觉得每个人应当怎样承担责任？', [('responsibility', '个人责任是否因参与者多而减少')],
         {'PV05': {'higher': '明确认为参与者多会减少个人应承担的责任。', 'lower': '明确认为大家一起参与也不减少个人责任。'}},
         '班级规范与个人的责任判断分开。')
    unit('B05_CONSEQUENCES', 'B05', '无身体伤害时的后果判断', B,
         '如果这样的玩笑没有让身体受伤，你会怎样看待它造成的影响？', [('consequence', '对非身体后果的评价')],
         {'PV05': {'higher': '明确因没有身体伤害而轻视过分玩笑的其他伤害。', 'lower': '明确认为没有身体受伤仍可能造成严重的其他伤害。'}},
         '描述结果与认可伤害分开；不能凭没提身体伤害推断。', {'joking': ['present']})
    unit('C01_VOICE', 'C01', '对意见分量的重视', H,
         '在大家讨论怎么安排时，你希望自己的意见起到怎样的作用？', [('voice', '对意见分量的期待')],
         {'PV06': {'higher': '明确非常重视自己的意见是否在群体中有分量。', 'lower': '明确较少在意自己意见是否有分量。'}},
         '仅记录话语分量的关注，正常领导或被尊重的需要不等于强制控制。')
    unit('C02_REFUSAL', 'C02', '面对意见被拒绝', H,
         '如果大家没有采纳你的意见，你会怎样面对这件事？', [('refusal', '对不被采纳的接受情况及反应')],
         {'PV06': {'higher': '明确难以接受别人不听自己的意见，或要求别人服从。', 'lower': '明确允许别人不采纳自己的意见。'}},
         '失望本身不等于控制行为。')
    unit('C03_DETERRENCE', 'C03', '威慑认知', B,
         '你觉得让别人知道自己不好惹，会怎样影响以后和同学的相处？', [('deterrence', '是否认可用威慑减少麻烦')],
         {'PV06': {'higher': '明确认可通过让他人畏惧自己来减少麻烦或建立位置。', 'lower': '明确不认可用让他人畏惧的方式维持关系。'}},
         '自我保护与威慑控制分开；不得补出已实施威胁。')
    unit('C04_DISSENT', 'C04', '群体中表达不同意见', H,
         '如果你的想法和几个朋友都不一样，你会怎样表达？', [('dissent', '表达不同意见的方式或困难')],
         {'PV07': {'higher': '明确因朋友意见一致而难以表达不同意见或跟随。', 'lower': '明确能在群体意见一致时表达不同判断。'}},
         '一般合群不等于从众风险；保留行为内容。')
    unit('C05_CONFORMITY', 'C05', '因关系压力而顺从', H,
         '如果你担心提出不同意见会让朋友疏远你，这会怎样影响你的选择？', [('choice', '排斥担忧如何影响是否跟随群体')],
         {'PV07': {'higher': '明确因害怕被疏远而跟随群体行为。', 'lower': '明确即使担心被疏远仍不因此跟随不认可的行为。'}},
         '这是设定条件下的选择，不能据此宣称学生平时一直害怕被疏远。')
    unit('C05_REJECTION', 'C05', '对关系疏远的担忧', H,
         '在这种相处中，你对自己和朋友之后的关系有什么担心吗？', [('rejection_worry', '是否存在被朋友疏远的担忧')],
         {'PV09': {'higher': '明确表达担心自己因关系或意见变化被朋友疏远。', 'lower': '明确表示在此情境中不担心因此被朋友疏远。'}},
         '记录情境担忧，不能直接推为稳定人格。', {'relationship': ['friend']})
    unit('D01_EXCLUSION', 'D01', '被排除在活动外的担忧', H,
         '这件事之后，你对自己能否参加同学们的活动会有什么想法？', [('exclusion', '是否担心被排除在活动之外')],
         {'PV09': {'higher': '明确担心自己被朋友排除在活动之外。', 'lower': '明确表示不担心被排除，并保留情境依据。'}},
         '对实际排斥的合理担忧不能直接推为过度敏感。')
    unit('D02_NO_RESPONSE', 'D02', '对未获回应的解释', H,
         '朋友暂时没有回应时，你会怎样理解？', [('interpretation', '如何解释未获回应及其带来的担忧')],
         {'PV09': {'higher': '明确因未获回应而担心对方对自己有意见。', 'lower': '明确考虑忙碌等解释而不急于担心被针对。'}},
         '不推断他人实际态度；仅记录学生的解释。', {'no_response': ['present']})
    unit('D03_PEER_SUPPORT', 'D03', '同伴交流资源', S,
         '平时有心事时，你和哪些同龄人说起来比较放心？没有这样的人也可以直接说。', [('peer_resource', '可以放心交流的同伴或明确缺乏这种资源')],
         {'PV08': {'higher': '明确自述有可以放心交流的同伴。', 'lower': '明确自述没有可以放心交流的同伴。'}},
         '家长和教师不替代同伴资源；不要求说出真实姓名。')
    unit('D04_REPAIR', 'D04', '朋友关系修复预期', H,
         '这次和朋友有了矛盾之后，你觉得你们的关系接下来会怎样？', [('repair_expectation', '对朋友关系能否修复的预期')],
         {'PV08': {'higher': '明确相信与朋友发生矛盾后关系仍能修复。', 'lower': '明确认为此次朋友关系难以修复。'},
          'PV10': {'higher': '明确表达朋友冲突后的关系修复预期。', 'lower': '明确表达在此朋友冲突中难以修复关系的预期。'}},
         '预期不等于实际修复能力；一般同学冲突不自动适用。', {'relationship': ['friend']})
    unit('E01_CHANNEL', 'E01', '求助渠道认知', H,
         '遇到这种情况，你会找谁商量？如果暂时想不到，也可以直接说。', [('channel', '具体求助对象、对象类别或明确没有渠道')],
         {'PV10': {'higher': '明确知道一个可商量的对象或渠道。', 'lower': '明确不知道可以找谁，或明确没有可信渠道。'}},
         '只是不想找某个人不等于没有其他渠道；渠道不等于帮助已经成功。')
    unit('E02_EXPRESSION', 'E02', '向成年人说明情况', 'task_performance',
         '假设你准备向一位信任的成年人说明这件事，你会怎样开口？可以试着说一小段。', [('explanation', '模拟说明人物、发生的事或希望获得的帮助')],
         {'PV10': {'higher': '在本次模拟表达中能够说明发生的事情或所需帮助。', 'lower': '明确表示本次无法向信任成年人说明情况。'}},
         '这是表达模拟，不等于已经实际求助或在真实情况下必然做到。')
    unit('E03_BARRIER', 'E03', '向老师家长求助的顾虑', H,
         '哪些因素会影响你是否把这件事告诉老师或家长？', [('barrier', '求助顾虑、阻碍，或明确没有这类顾虑')],
         {'PV10': {'lower': '明确担心告诉老师或家长使事情更麻烦。', 'higher': '明确表示没有担心告诉老师家长会使事情更麻烦这一顾虑。'}},
         '没有顾虑只描述这个方面，不能证明整体求助能力；合理安全顾虑不归责学生。')
    unit('E04_DEESCALATION', 'E04', '避免争执升级', H,
         '争执已经越来越激烈时，你接下来会怎么做？', [('deescalation', '离开或暂停的选择及其应对目的')],
         {'PV01': {'higher': '明确通过离开或暂停让自己平静。', 'lower': '明确描述在激烈争执中无法暂停情绪化反应。'},
          'PV10': {'higher': '明确通过离开或暂停避免争执升级。', 'lower': '明确表示无法采取离开或暂停等避免升级的办法。'}},
         '仅说离开不能自动补出调节目的；假设中的策略与执行能力分开。', {'conflict_stage': ['escalating']})
    unit('E05_PROTECTION', 'E05', '帮助他人与自我保护', H,
         '如果你想帮助那位同学，你会怎样做，同时照顾好自己的安全？',
         [('help_action', '帮助他人的行动或明确无法提供帮助'), ('self_protection', '同时保护自己的办法或困难')],
         {'PV04': {'higher': '明确关注受影响同学并提出帮助意向。'},
          'PV10': {'higher': '明确说明帮助同学同时保护自己的办法。', 'lower': '明确表示无法兼顾帮助与自我保护。'}},
         '未采取行动不直接证明没有共情；不把危险介入当成更高分的保护行为。')
    unit('G01_FORCE', 'G01', '强制或身体伤害的解决倾向', B,
         '你觉得用更强硬的行动处理这种冲突会有什么作用？你说的行动具体是什么？', [('action', '具体行动及是否认可用它解决冲突')],
         {'PV02': {'higher': '明确认可用推打等伤害性行动解决或报复。', 'lower': '明确拒绝用身体伤害解决冲突。', 'unclear': '说到强硬却未说明具体行为，保留歧义。'}},
         '强硬不自动等于伤害；对作用的描述不等于认可。')
    unit('G02_VERBAL', 'G02', '尖锐语言回击的效用判断', B,
         '你觉得用尖锐的话回击对方，会怎样影响接下来的事情？', [('verbal_response', '是否认可尖锐回击更有效及其理由')],
         {'PV02': {'higher': '明确认可用伤害性的尖锐语言回击更有效。', 'lower': '明确不认可或拒绝以伤害性语言回击。'}},
         '坚定表达边界不等于语言攻击。')
    unit('G03_ALLIANCE', 'G03', '朋友支持与关系控制', H,
         '这时你希望朋友怎样支持你？如果朋友有不同看法，你会怎么办？', [('alliance', '期待的支持方式及是否强迫站队')],
         {'PV06': {'higher': '明确要求朋友必须站队，或以排斥等方式控制关系。', 'lower': '明确允许朋友有不同意见，不强迫朋友站队。', 'unclear': '仅希望朋友支持自己，没有说明控制或强迫。'}},
         '正常寻求支持不等于关系攻击。')
    unit('G03_GROUP', 'G03', '朋友站队时的群体影响', H,
         '如果朋友们决定站在同一边，这会怎样影响你自己的判断？', [('group_influence', '群体站队对个人判断的影响')],
         {'PV07': {'higher': '明确因群体站队而放弃自己的判断并跟随。', 'lower': '明确在朋友站队时仍保留自己的判断。'}},
         '本单元选择原 G03 的 PV07 方面，不凭想要支持自动认定从众。')

    save('measurement_units.json', {'version': '0.3.0', 'source_file': 'source/心理Agent+量表与心理变量.md',
         'units': units, 'background_item_ids': ['F01','F02','F03','F04'],
         'note': '26道核心题拆成具体内容；F类仅接收自发背景。多题来源表示同一具体内容的来源关联，不表示必须逐题提问。'})
    save('dialogue_rubric.json', {'version': '0.3.0', 'rules': rules,
         'note': '多轮测量单元专用规则；保留旧 evidence_rubric.json 和旧 extract 行为。方向不是量表分数。'})

    specs = {
      'S01': ('physical','involved','classmate','ambiguous','absent','escalating','close','absent','absent',
              '课间走廊里，一位同学从你身边经过时碰到了你，你手里的本子掉在地上。你还不知道对方是不是故意的。你请对方注意，两个人说话的声音越来越大，旁边有同学在看。',
              'A01 A02 A03 A04 E01 E02 E03 E04 D04 G01'),
      'S02': ('physical','observer','classmate','explicit','present','escalating','not_close','absent','absent',
              '课间，你看到几位同学围着另一位同学推搡，说话声越来越大。被围住的是一位你平时不太合得来的同学。你在旁边，还没有加入他们的行动。',
              'B01 B02 B04 E01 E02 E03 E05'),
      'S03': ('verbal','group','friend','explicit','present','stable','not_close','present','absent',
              '几位朋友在聊天时，反复用一个同学不喜欢的外号取笑他。那位同学已经说了不喜欢，但大家还在笑，也有人看着你，等你接话。整个过程没有身体接触。',
              'B03 B04 B05 C04 C05 G02 G03'),
      'S04': ('verbal','target','classmate','ambiguous','present','escalating','close','absent','absent',
              '你在班里发言后，有几位同学模仿你刚才说话的声音。你还不清楚他们是随口模仿还是有意让你难堪。你请他们停下来，双方说话声越来越大。',
              'A01 A02 A03 A04 C05 D01 E01 E02 E03 E04'),
      'S05': ('relational','group','friend','explicit','present','stable','close','present','absent',
              '几位朋友商量周末的小组活动，有人提议不要邀请其中一位同学，还把排除他的事当玩笑讲。那位同学想一起参加。朋友们正在等你说自己的想法。',
              'B01 B03 B04 B05 C01 C02 C03 C04 C05 G03'),
      'S06': ('relational','target','friend','ambiguous','present','stable','close','absent','present',
              '你和几位朋友最近在一次活动安排上有过分歧。后来他们又在商量活动，你暂时没收到邀请。你发消息询问，一时还没有人回复，你还不清楚原因。',
              'C05 D01 D02 D03 D04 E01 E02 E03')}
    blueprint = json.loads((ROOT/'config/scenario_blueprint.json').read_text())
    scenarios = []
    for sid, values in specs.items():
        form,perspective,relationship,intent,pressure,stage,affinity,joking,no_response,text,item_string = values
        original = next(s for s in blueprint['scenarios'] if s['scenario_id']==sid)
        ids = item_string.split()
        bindings = [{'item_id': i, 'target_variable_ids': [v for v in items[i]['variable_ids'] if v in original['variable_ids']],
                     'use_condition': '由measurement_units的适用条件和当前访谈计划共同约束；仅启用所选变量方面。'} for i in ids]
        # 保留 S01 已编写的精确使用条件与目标选择，补入新准备的 E02。
        prior = {b['item_id']: b for b in original['item_bindings']}
        bindings = [prior.get(b['item_id'], b) for b in bindings]
        original.update(item_ids=ids, item_bindings=bindings, item_mapping_status='engineering_draft')
        facts = dict(form=form,perspective=perspective,relationship=relationship,intent_clarity=intent,
                     group_pressure=pressure,conflict_stage=stage,affinity=affinity,joking=joking,no_response=no_response)
        conditions = [{'condition_id':'base','parent_condition_id':None,'facts':facts,'text':text}]
        if sid=='S01':
            conditions.append({'condition_id':'friend_conflict','parent_condition_id':'base',
                               'facts':{**facts,'relationship':'friend'},
                               'text':text.replace('一位同学从你身边经过时','一位朋友从你身边经过时')})
        scenarios.append(dict(scenario_id=sid,conditions=conditions,
                              opening_question='遇到这种情况，你会有什么想法，接下来会怎么做？'))
    blueprint['version'] = '0.3.0'
    save('scenario_blueprint.json', blueprint)
    save('dialogue_scenarios.json', {'version':'0.3.0','scenarios':scenarios})

    by_item = lambda chosen: [u['unit_id'] for u in units if set(u['source_item_ids']) & set(chosen)]
    def entry(sid, selected=None, maximum=10, condition='base'):
        s=next(s for s in blueprint['scenarios'] if s['scenario_id']==sid)
        selected=selected or s['item_ids']
        bound={b['item_id']:b['target_variable_ids'] for b in s['item_bindings']}
        enabled=[u['unit_id'] for u in units if set(u['source_item_ids']) & set(selected)
                 and any(set(u['target_variable_ids']) & set(bound.get(i,[])) for i in set(u['source_item_ids']) & set(selected))]
        return {'scenario_id':sid,'condition_id':condition,'active_item_ids':selected,'unit_ids':enabled,'max_turns':maximum}
    plans=[
      {'plan_id':'s01','description':'原S01七题的多轮验证，保持原变量范围。','entries':[entry('S01','A01 A02 A03 A04 E01 E04 G01'.split(),12)],'max_total_turns':12},
      {'plan_id':'s01_extended','description':'S01扩展E02/E03/D04；普通同学条件下D04自动不适用。','entries':[entry('S01',maximum=15)],'max_total_turns':15},
      {'plan_id':'s01_friend','description':'显式朋友条件，验证D04仅启用PV10。','entries':[entry('S01',maximum=15,condition='friend_conflict')],'max_total_turns':15},
      {'plan_id':'balanced','description':'身体、言语、关系四情境，覆盖十变量；预算结束保留测量缺口。',
       'entries':[entry(s,maximum=7) for s in ['S01','S03','S05','S06']],'max_total_turns':28},
      {'plan_id':'full','description':'六情境完整功能实验，可能较长；不作为推荐施测时长。',
       'entries':[entry(s,maximum=18) for s in specs],'max_total_turns':108}]
    save('interview_policy.json', {'version':'0.3.0','default_plan_id':'balanced','max_attempts_per_unit':2,
         'plans':plans,'stop_commands':['/stop','结束访谈'],'skip_commands':['/skip','跳过此题'],
         'background_policy':'spontaneous_only_excluded_from_core_and_risk',
         'note':'预算为工程参数，覆盖率不是心理信度；拒答不强制补问，不使用风险结果决定下一问。'})
    save('risk_profile_rules.json', {'version':'0.3.0','mode':'source_association_only',
         'role_variables':{'bully':['PV02','PV04','PV05','PV06','PV07'], 'victim':['PV08','PV09'],
                           'bully_victim':['PV01','PV03','PV09']}, 'shared_variables':['PV10'],
         'note':'依据变量原表主要风险作用组织相关线索；不是分类权重、概率或经标定的风险等级。F类不参与。'})
    save('agents.example.json', {'version':'0.3.0','agents':{
         'a1':{'backend':'template','llm_config':None},'a2':{'backend':'llm','llm_config':'config/llm.local.json'},
         'a3':{'backend':'llm','llm_config':'config/llm.local.json'},'a4':{'backend':'template','llm_config':None}},
         'note':'路径相对项目根目录；每个Agent可指向不同LLM配置。此文件不存密钥。'})
    print(f'已生成 {len(units)} 个测量单元、{len(rules)} 条多轮规则、6 类情境和 {len(plans)} 个访谈计划。')


if __name__ == '__main__':
    build()
