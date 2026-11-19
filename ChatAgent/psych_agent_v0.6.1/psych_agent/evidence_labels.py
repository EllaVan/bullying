"""为人读报告生成稳定、可复现的 evidence_ref；内部仍保留 DEV_ hash id。"""

ARROW = {'higher': '↑', 'lower': '↓', 'unclear': '·'}


def _sort_key(evidence):
    turn = evidence.get('turn_id') or ''
    return (turn, evidence.get('variable_id') or '', evidence.get('evidence_id') or '')


def assign_evidence_refs(evidence_list):
    """按 turn/variable/id 排序后赋予 E001… 标签；就地写入 evidence_ref，并返回 id→ref 映射。"""
    ordered = sorted(evidence_list, key=_sort_key)
    mapping = {}
    for index, evidence in enumerate(ordered, start=1):
        items = evidence.get('source_item_ids') or []
        item = items[0] if items else '—'
        arrow = ARROW.get(evidence.get('direction'), '·')
        variable = evidence.get('variable_id') or 'PV??'
        turn = evidence.get('turn_id') or 'T???'
        ref = f'E{index:03d}｜{turn}｜{item}｜{variable}{arrow}'
        evidence['evidence_ref'] = ref
        mapping[evidence['evidence_id']] = ref
    return mapping


def refs_for(ids, id_to_ref):
    return [id_to_ref.get(i, i) for i in ids]


def ensure_profile_refs(profile):
    """若画像尚未带 evidence_ref，则补全 ledger 与映射。"""
    ledger = profile.get('evidence_ledger') or []
    if ledger and all(e.get('evidence_ref') for e in ledger):
        mapping = {e['evidence_id']: e['evidence_ref'] for e in ledger}
        if 'evidence_ref_index' not in profile:
            profile['evidence_ref_index'] = [{'evidence_id': eid, 'evidence_ref': ref}
                                            for eid, ref in mapping.items()]
        return mapping
    mapping = assign_evidence_refs(ledger)
    for e in profile.get('excluded_evidence') or []:
        if not e.get('evidence_ref'):
            items = e.get('source_item_ids') or []
            item = items[0] if items else '—'
            arrow = ARROW.get(e.get('direction'), '·')
            e['evidence_ref'] = f'EX｜{e.get("turn_id", "T???")}｜{item}｜{e.get("variable_id", "PV??")}{arrow}'
    profile['evidence_ref_index'] = [{'evidence_id': eid, 'evidence_ref': ref} for eid, ref in mapping.items()]
    return mapping
