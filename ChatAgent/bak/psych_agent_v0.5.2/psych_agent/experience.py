"""只从A3已经校验为真实事件的观察生成经历台账，不从情境事实补经历。"""
import re
from .dialogue_config import digest


def _literal_fields(quote):
    # 仅保留明确文本命中；这是辅助索引，不宣称完整语义识别。
    patterns = {'frequency': r'每天|每周|经常|总是|好几次|一次',
                'recency': r'今天|昨天|上周|上个月|去年|最近|以前|曾经',
                'current_status': r'还在发生|现在还有|已经停止|后来没有再',
                'form': r'嘲笑|辱骂|骂我|孤立|排斥|不让我参加|推我|打我|踢我|群里|网上'}
    return {key: [{'value':m.group(), 'quote':m.group(), 'start':m.start(), 'end':m.end()} for m in re.finditer(pat, quote)]
            for key, pat in patterns.items()}


def build_experience(state):
    events, non_real = [], []
    for turn in state['turns']:
        for event in turn.get('validated_experiences',[]):
            row = dict(event)
            row['event_id']=row['experience_id']
            row['role']='unknown'
            row['details']=list(event['details'])
            roles={d['value'] for d in event['details'] if d['field']=='role'}
            if len(roles)==1: row['role']=next(iter(roles))
            (events if event['subject']=='self' else non_real).append(row)
        for obs in turn['validated_observations']:
            if obs['reference_frame'] != 'real_event_self_report':
                continue
            # 保留每条观察原样，不按关键词猜测施暴者/受害者身份。
            quote = obs['quote']
            if any(e['turn_id']==turn['turn_id'] and quote in e['quote'] for e in events+non_real): continue
            key = digest([obs['event_id'], obs['turn_id'], quote, obs['subject']])[:16]
            row = {'experience_id':'EXP_'+key, 'event_id':obs['event_id'], 'turn_id':turn['turn_id'],
                   'observation_id':obs['observation_id'], 'source_item_ids':obs['source_item_ids'],
                   'subject':obs['subject'], 'reference_frame':obs['reference_frame'],
                   'role':'unknown', 'role_basis':'not_inferred_from_keywords', 'quote':quote,
                   'evidence_ids':obs['evidence_ids'], 'literal_fields':_literal_fields(quote),
                   'boundary':'频率、时间和形式为原话检索索引；否定、讽刺、转述仍须按整段原话理解，不直接计入角色风险。'}
            if obs['subject']=='self': events.append(row)
            else: non_real.append(row)
    return {'schema_version':'0.5.2','session_id':state['session_id'],'config_set_id':state['config_set_id'],
            'synthetic':state['synthetic'],'source':'validated_observations', 'events':events,
            'third_party_events':non_real, 'status':'recorded' if events else 'no_validated_self_event',
            'note':'没有经历记录不等于没有经历；不把假设或旁观叙述当作已实施/已受害事实。'}
