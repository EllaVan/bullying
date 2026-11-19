"""A3 多次抽取方向一致率的纯函数（无 LLM）。"""
from collections import Counter, defaultdict


def evidence_direction_rows(profile: dict):
    rows = []
    for e in profile.get('evidence_ledger') or []:
        key = (e.get('turn_id'), e.get('variable_id'), e.get('unit_id'))
        rows.append({'key': key, 'direction': e.get('direction'),
                     'rule_id': e.get('rule_id'), 'quote': e.get('quote')})
    return rows


def pairwise_agreement(direction_lists):
    """多轮结果：对每个键，若所有运行方向一致则 stable。

    direction_lists: list[list[{key, direction, ...}]]
    """
    if not direction_lists:
        return {'keys': 0, 'agree': 0, 'rate': None, 'per_key': []}
    key_to_runs = defaultdict(list)
    for run_rows in direction_lists:
        seen = {}
        for row in run_rows:
            key = row['key']
            seen.setdefault(key, []).append(row['direction'])
        for key, dirs in seen.items():
            majority = Counter(dirs).most_common(1)[0][0]
            key_to_runs[key].append(majority)
    per_key = []
    agree = 0
    n_runs = len(direction_lists)
    for key, dirs in sorted(key_to_runs.items()):
        ok = len(set(dirs)) == 1 and len(dirs) == n_runs
        if ok:
            agree += 1
        per_key.append({
            'turn_id': key[0], 'variable_id': key[1], 'unit_id': key[2],
            'directions_by_run': dirs,
            'stable': ok,
        })
    n = len(per_key)
    return {
        'keys': n,
        'agree': agree,
        'rate': (agree / n) if n else None,
        'per_key': per_key,
        'note': 'stable=所有成功运行对该键方向一致；仅在至少一次运行出现过的键上统计。',
    }
