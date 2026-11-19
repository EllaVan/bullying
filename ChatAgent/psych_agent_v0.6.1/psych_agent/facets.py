"""Facet聚合：同一方面跨轮重复不增权；冲突经 conflict_resolver 软消解后仍可计分。"""
from .config import require
from .conflict_resolver import summarize_with_conflicts


def summarize(groups, variable_id, cfg, evidence_by_id=None):
    return summarize_with_conflicts(groups, variable_id, cfg, evidence_by_id=evidence_by_id)


def validate_config(document, cfg):
    require(set(document['variables']) == set(cfg.base.variables), 'Facet变量全集不符')
    for vid, rows in document['variables'].items():
        ids = [r['facet_id'] for r in rows]
        require(len(ids) == len(set(ids)), 'facet_id重复')
        for row in rows:
            require(type(row['weight']) in (int, float) and 0 <= row['weight'] <= 1, 'Facet权重无效')
            require(all(u in cfg.units and vid in cfg.units[u]['target_variable_ids'] for u in row['unit_ids']), 'Facet引用越界')
