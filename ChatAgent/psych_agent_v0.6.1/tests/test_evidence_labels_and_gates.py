"""证据可读标签与量表门控单元测试。"""
import unittest
from pathlib import Path

from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.evidence_labels import assign_evidence_refs, ensure_profile_refs
from psych_agent.scale_gates import apply_scale_constraints


ROOT = Path(__file__).resolve().parents[1]


class EvidenceLabelTests(unittest.TestCase):
    def test_assign_refs_are_stable_and_readable(self):
        rows = [
            {'evidence_id': 'DEV_b', 'turn_id': 'T002', 'variable_id': 'PV02', 'direction': 'higher',
             'source_item_ids': ['A03']},
            {'evidence_id': 'DEV_a', 'turn_id': 'T001', 'variable_id': 'PV01', 'direction': 'lower',
             'source_item_ids': ['A01']},
        ]
        mapping = assign_evidence_refs(rows)
        self.assertEqual(rows[1]['evidence_ref'], 'E001｜T001｜A01｜PV01↓')  # sorted by turn
        self.assertTrue(rows[0]['evidence_ref'].startswith('E002｜T002｜'))
        self.assertEqual(mapping['DEV_a'], rows[1]['evidence_ref'])


class ScaleGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_dialogue_config(ROOT)

    def _blank_profile(self, pv02_frame='hypothetical_intent'):
        profile = {
            'variables': [{
                'variable_id': 'PV02',
                'groups': [{'reference_frame': pv02_frame, 'evidence_ids': ['E1']}],
            }],
            'experience': {'events': []},
        }
        for vid in self.cfg.base.variables:
            if vid == 'PV02':
                continue
            profile['variables'].append({'variable_id': vid, 'groups': []})
        return profile

    def _role_shell(self, **scores):
        th = self.cfg.risk_scoring['thresholds']
        return {
            'scoring_policy': self.cfg.risk_scoring,
            'roles': [{
                'role': role,
                'score': scores.get(role, 20.0),
                'thresholds': list(th[role]),
                'level': 'high' if scores.get(role, 20) >= th[role][1] else 'low',
                'gate_applied': None,
            } for role in ('bully', 'victim', 'bully_victim', 'bystander')],
        }

    def test_hypothesis_cap_blocks_high(self):
        result = self._role_shell(bully=80.0)
        apply_scale_constraints(result, self._blank_profile(), self.cfg.scale_constraints)
        bully = next(r for r in result['roles'] if r['role'] == 'bully')
        self.assertLessEqual(bully['score'], 54.99)
        self.assertEqual(bully['level'], 'attention')
        self.assertIsNotNone(bully['gate_applied'])
        self.assertEqual(result['scale_constraints'].get('anchor_package'), 'olweus_dbvs_bpbq_v1')
        self.assertTrue(result['scale_constraints']['gates'])

    def test_bully_victim_dual_involvement_cap(self):
        result = self._role_shell(bully_victim=80.0)
        profile = self._blank_profile('habitual_self_report')
        apply_scale_constraints(result, profile, self.cfg.scale_constraints)
        row = next(r for r in result['roles'] if r['role'] == 'bully_victim')
        self.assertLessEqual(row['score'], 59.99)
        codes = {a['code'] for a in (row['gate_applied'] or {}).get('actions') or []}
        self.assertTrue(codes & {'high_needs_dual_involvement', 'high_needs_victim_experience'})


if __name__ == '__main__':
    unittest.main()
