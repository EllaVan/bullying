"""Facet聚合：同一方面跨轮重复不增权，unknown与冲突不补成中分。"""
from .config import require


def summarize(groups, variable_id, cfg):
    rows = []
    definitions = cfg.facet_config['variables'][variable_id]
    for spec in definitions:
        selected = [g for g in groups if g['unit_id'] in spec['unit_ids']]
        directions = {d for g in selected for d in g['directions'] if d != 'unclear'}
        value = None
        status = 'unknown'
        if len(directions) > 1:
            status = 'conflict'
        elif len(directions) == 1:
            status = 'observed'
            value = cfg.variable_scoring['direction_values'][next(iter(directions))]
        elif selected:
            status = 'descriptive_only'
        rows.append({**spec, 'status': status, 'value': value,
                     'group_ids': [g['group_id'] for g in selected],
                     'source_item_ids': sorted({i for g in selected for i in g['source_item_ids']}),
                     'evidence_ids': sorted({e for g in selected for e in g['evidence_ids']}),
                     'reference_frames': sorted({g['reference_frame'] for g in selected})})
    available = [r for r in rows if r['value'] is not None and r['weight'] > 0]
    total = sum(r['weight'] for r in available)
    value = round(sum(r['value'] * r['weight'] for r in available) / total, 4) if total else None
    expected = sum(r['weight'] for r in rows)
    confidence = round(total / expected, 4) if expected else 0.0
    return rows, value, confidence


def validate_config(document, cfg):
    require(set(document['variables']) == set(cfg.base.variables), 'Facet变量全集不符')
    for vid, rows in document['variables'].items():
        ids = [r['facet_id'] for r in rows]
        require(len(ids) == len(set(ids)), 'facet_id重复')
        for row in rows:
            require(type(row['weight']) in (int,float) and 0 <= row['weight'] <= 1, 'Facet权重无效')
            require(all(u in cfg.units and vid in cfg.units[u]['target_variable_ids'] for u in row['unit_ids']), 'Facet引用越界')
