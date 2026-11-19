"""多轮行为与边界测试；合成输入不用于声称模型或量表准确率。"""
import copy
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psych_agent.agent_transport import JsonTransport
from psych_agent.cli import main
from psych_agent.dialogue_config import digest, load_dialogue_config
from psych_agent.dialogue_contracts import validate_turn
from psych_agent.dialogue_runner import Agents, ReplayBundle, run_session
from psych_agent.interviewer import LLMInterviewer, TemplateInterviewer
from psych_agent.io_utils import ValidationError, read_json
from psych_agent.measurement_controller import MeasurementController, coverage_report
from psych_agent.profile import build_profile, validate_profile
from psych_agent.risk_engine import EvidenceRiskEngine, ExternalPredictionRiskEngine, model_input
from psych_agent.risk_reporter import LLMRiskReporter, TemplateRiskReporter, validate_narrative
from psych_agent.scenario_agent import LLMScenarioGenerator, TemplateScenarioGenerator
from psych_agent.turn_extractor import LLMTurnExtractor

ROOT=Path(__file__).resolve().parents[1]


def candidate(task, uid, quote, direction='higher', frame=None, subject='self', slot_ids=None):
    unit=next(u for u in task['allowed_units'] if u['unit_id']==uid)
    frame=frame or unit['reference_frame']
    ids=slot_ids if slot_ids is not None else [s['slot_id'] for s in unit['required_slots']]
    rules=[r for r in unit['rule_ids'] if r.endswith('_'+direction.upper())]
    return {'unit_id':uid,'status':'covered' if len(ids)==len(unit['required_slots']) else 'partial',
            'quote':quote,'reference_frame':frame,'subject':subject,'context_turn_ids':[],
            'slots':[{'slot_id':s,'value':quote,'quote':quote} for s in ids],
            'evidence':[{'rule_id':r,'quote':quote,'rationale':'本测试预先给定的观察。'} for r in rules],
            'reason':'本测试明确给定所需信息。'}


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.cfg=load_dialogue_config(ROOT)

    def controller(self, plan='s01', maximum=None):
        c=MeasurementController(self.cfg,plan,'TEST_SESSION',True,maximum)
        action=c.next_action()
        c.set_scenario(TemplateScenarioGenerator().generate(action['task']))
        return c

    def begin(self, c, answer):
        task=c.next_action()['task']
        c.record_question({'question':task['question_template']})
        c.record_answer(answer)
        return task

    def commit(self, c, task, observations, background=None):
        return c.commit({'turn_id':task['turn_id'],'observations':observations,'background':background or []})

    def sample_profile(self):
        c=self.controller(maximum=1)
        task=self.begin(c,'我会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')])
        c.next_action()
        return build_profile(c.snapshot(),self.cfg)

    def prediction(self, profile):
        return {'schema_version':'0.3.0','session_id':profile['session_id'],'input_hash':model_input(profile)['input_hash'],
                'synthetic':True,'model_id':'synthetic_contract_test','assessment_target':{'kind':'future_involvement','time_window':'模拟未来一个月'},
                'role_semantics':'marginal_with_joint','probabilities':{'bully':0.3,'victim':0.4,'bully_victim':0.2},
                'confidence':dict.fromkeys(('bully','victim','bully_victim')),'validation_status':'synthetic_only'}

    def test_all_core_items_have_units_and_f_items_are_separate(self):
        sources={i for u in self.cfg.units.values() for i in u['source_item_ids']}
        self.assertEqual(len(sources),26)
        self.assertFalse(any(i.startswith('F') for i in sources))
        self.assertEqual(set(self.cfg.scenarios),{'S01','S02','S03','S04','S05','S06'})

    def test_original_s01_scope_excludes_extensions(self):
        units=self.cfg.unit_views(self.cfg.plans['s01']['entries'][0])
        self.assertNotIn('U_E02_EXPRESSION',units)
        self.assertNotIn('U_E03_BARRIER',units)
        self.assertNotIn('U_D04_REPAIR',units)

    def test_partial_mapping_keeps_d04_pv10_only_in_s01(self):
        views=self.cfg.unit_views(self.cfg.plans['s01_friend']['entries'][0])
        self.assertEqual(views['U_D04_REPAIR']['target_variable_ids'],['PV10'])
        self.assertTrue(all(self.cfg.rules[r]['variable_id']=='PV10' for r in views['U_D04_REPAIR']['rule_ids']))

    def test_friendship_applicability_skips_d04_without_question(self):
        c=self.controller('s01_extended')
        row=c.snapshot()['entries'][0]['units']['U_D04_REPAIR']
        self.assertEqual(row['status'],'not_applicable')
        self.assertNotIn('U_D04_REPAIR',[u['unit_id'] for u in c.next_action()['task']['allowed_units']])

    def test_known_help_channel_does_not_complete_other_pv10_facets(self):
        c=self.controller('s01_friend')
        task=self.begin(c,'我会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')])
        states=c.snapshot()['entries'][0]['units']
        self.assertEqual(states['U_E01_CHANNEL']['status'],'covered')
        self.assertEqual(states['U_E03_BARRIER']['status'],'not_asked')
        self.assertEqual(states['U_E02_EXPRESSION']['status'],'not_asked')
        self.assertNotEqual(c.next_action()['task']['target_unit_id'],'U_E01_CHANNEL')

    def test_explicit_no_channel_is_covered_with_lower_direction(self):
        c=self.controller()
        task=self.begin(c,'我不知道能找谁商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我不知道能找谁商量。','lower')])
        state=c.snapshot()
        self.assertEqual(state['entries'][0]['units']['U_E01_CHANNEL']['status'],'covered')
        self.assertEqual(state['turns'][0]['validated_evidence'][0]['direction'],'lower')

    def test_partial_slots_merge_before_completion(self):
        cfg=self.cfg
        cfg.plans['protection']={'plan_id':'protection','description':'边界测试','entries':[
            {**cfg.plans['full']['entries'][1],'unit_ids':['U_E05_PROTECTION'],'max_turns':4}], 'max_total_turns':4}
        c=self.controller('protection')
        task=self.begin(c,'我会请老师来帮助同学。')
        self.commit(c,task,[candidate(task,'U_E05_PROTECTION','我会请老师来帮助同学。',slot_ids=['help_action'])])
        self.assertEqual(c.snapshot()['entries'][0]['units']['U_E05_PROTECTION']['status'],'partial')
        task=self.begin(c,'我会保持距离，不冲进人群。')
        self.assertEqual([s['slot_id'] for s in task['missing_slots']],['self_protection'])
        self.assertNotIn('怎样帮助',task['question_template'])
        self.commit(c,task,[candidate(task,'U_E05_PROTECTION','我会保持距离，不冲进人群。',slot_ids=['self_protection'])])
        self.assertEqual(c.snapshot()['entries'][0]['units']['U_E05_PROTECTION']['status'],'covered')

    def test_wrong_reference_frame_is_preserved_but_not_used_for_coverage(self):
        c=self.controller()
        task=self.begin(c,'上星期我找老师商量过。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','上星期我找老师商量过。',frame='real_event_self_report')])
        state=c.snapshot()
        self.assertEqual(state['entries'][0]['units']['U_E01_CHANNEL']['status'],'not_asked')
        e=state['turns'][0]['validated_evidence'][0]
        self.assertEqual(e['reference_frame'],'real_event_self_report')
        self.assertNotEqual(e['event_id'],task['event_id'])

    def test_third_party_is_not_self_coverage_or_risk(self):
        c=self.controller()
        task=self.begin(c,'朋友说他会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','朋友说他会找老师商量。',subject='other')])
        profile=build_profile(c.snapshot(),self.cfg)
        self.assertFalse(profile['evidence_ledger'])
        self.assertTrue(profile['excluded_evidence'])
        self.assertEqual(c.snapshot()['entries'][0]['units']['U_E01_CHANNEL']['status'],'not_asked')

    def test_quote_from_question_is_rejected_and_state_does_not_advance(self):
        c=self.controller()
        task=self.begin(c,'我不确定。')
        bad=candidate(task,'U_E01_CHANNEL','不存在于回答的文字')
        before=c.snapshot()
        with self.assertRaises(ValidationError): self.commit(c,task,[bad])
        self.assertEqual(c.snapshot(),before)

    def test_unknown_unit_is_rejected(self):
        c=self.controller()
        task=self.begin(c,'我会找老师商量。')
        bad=candidate(task,'U_E01_CHANNEL','我会找老师商量。')
        bad['unit_id']='U_UNKNOWN'
        with self.assertRaises(ValidationError): self.commit(c,task,[bad])

    def test_d04_other_variable_rule_is_rejected(self):
        c=self.controller('s01_friend')
        task=self.begin(c,'我觉得关系可以修复。')
        bad=candidate(task,'U_D04_REPAIR','我觉得关系可以修复。')
        bad['evidence'][0]['rule_id']='DR_D04_REPAIR_PV08_HIGHER'
        with self.assertRaises(ValidationError): self.commit(c,task,[bad])

    def test_covered_requires_all_slots(self):
        c=self.controller('full')
        task=self.begin(c,'我会找老师商量。')
        bad=candidate(task,'U_E01_CHANNEL','我会找老师商量。')
        bad['slots']=[]
        with self.assertRaises(ValidationError): self.commit(c,task,[bad])

    def test_unknown_context_turn_is_rejected(self):
        c=self.controller()
        task=self.begin(c,'那就还是找老师。')
        bad=candidate(task,'U_E01_CHANNEL','那就还是找老师。')
        bad['context_turn_ids']=['T999']
        with self.assertRaises(ValidationError): self.commit(c,task,[bad])

    def test_anaphora_keeps_current_quote_and_prior_turn_reference(self):
        c=self.controller()
        task=self.begin(c,'我会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')])
        task=self.begin(c,'那就还是这样做。')
        obs=candidate(task,'U_E01_CHANNEL','那就还是这样做。')
        obs['context_turn_ids']=['T001']
        self.commit(c,task,[obs])
        e=c.snapshot()['turns'][1]['validated_evidence'][0]
        self.assertEqual(e['quote'],'那就还是这样做。')
        self.assertEqual(e['context_turn_ids'],['T001'])

    def test_repeated_evidence_keeps_one_group_with_no_score(self):
        c=self.controller()
        for answer in ['我会找老师商量。','我还是会找老师商量。']:
            task=self.begin(c,answer)
            self.commit(c,task,[candidate(task,'U_E01_CHANNEL',answer)])
        profile=build_profile(c.snapshot(),self.cfg)
        pv=next(v for v in profile['variables'] if v['variable_id']=='PV10')
        self.assertEqual(len(pv['groups']),1)
        self.assertEqual(len(pv['groups'][0]['evidence_ids']),2)
        self.assertIsNone(pv['value'])
        self.assertIsNone(pv['confidence'])

    def test_conditions_remain_distinct_with_shared_event_link(self):
        a=copy.deepcopy(self.cfg.plans['s01']['entries'][0]); a['max_turns']=1
        b=copy.deepcopy(a); b['condition_id']='friend_conflict'
        self.cfg.plans['conditions']={'plan_id':'conditions','description':'条件测试','entries':[a,b],'max_total_turns':2}
        c=self.controller('conditions')
        task=self.begin(c,'我会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')])
        action=c.next_action()
        c.set_scenario(TemplateScenarioGenerator().generate(action['task']))
        task=self.begin(c,'我不知道能找谁商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我不知道能找谁商量。','lower')])
        profile=build_profile(c.snapshot(),self.cfg)
        groups=next(v for v in profile['variables'] if v['variable_id']=='PV10')['groups']
        self.assertEqual(len(groups),2)
        self.assertEqual(len({g['event_id'] for g in groups}),1)
        self.assertEqual({g['condition_id'] for g in groups},{'base','friend_conflict'})

    def test_background_does_not_enter_model_input(self):
        c=self.controller()
        answer='我会找老师商量。家里有人愿意听我说。'
        task=self.begin(c,answer)
        bg={'item_id':'F01','quote':'家里有人愿意听我说。','description':'家庭倾听',
            'reference_frame':'habitual_self_report','subject':'self'}
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')],[bg])
        profile=build_profile(c.snapshot(),self.cfg)
        self.assertEqual(len(profile['context']),1)
        wire=json.dumps(model_input(profile),ensure_ascii=False)
        self.assertNotIn('F01',wire)
        self.assertNotIn('家庭倾听',wire)

    def test_refusal_does_not_repeat_target(self):
        c=self.controller()
        task=self.begin(c,'暂时没有想法。')
        self.commit(c,task,[])
        task=c.next_action()['task']
        uid=task['target_unit_id']
        c.record_question({'question':task['question_template']})
        c.decline_current()
        self.assertEqual(c.snapshot()['entries'][0]['units'][uid]['status'],'declined')
        self.assertNotEqual(c.next_action()['task']['target_unit_id'],uid)

    def test_total_budget_stops_with_missing_units(self):
        c=self.controller(maximum=1)
        task=self.begin(c,'暂时没有想法。')
        self.commit(c,task,[])
        self.assertEqual(c.next_action()['kind'],'done')
        coverage=coverage_report(c.snapshot(),self.cfg)
        self.assertEqual(coverage['stop_reason'],'total_budget_reached')
        self.assertGreater(coverage['counts']['not_asked'],0)

    def test_unit_attempt_budget_prevents_endless_ambiguous_questions(self):
        c=self.controller()
        asked=[]
        while c.next_action()['kind']=='question':
            task=self.begin(c,'我还不清楚。')
            asked.append(task['target_unit_id'])
            self.commit(c,task,[])
        self.assertLessEqual(max(asked.count(uid) for uid in set(asked)),2)

    def test_a1_cannot_change_immutable_facts(self):
        c=MeasurementController(self.cfg,'s01','TEST')
        action=c.next_action()
        output=TemplateScenarioGenerator().generate(action['task'])
        output['facts']['intent_clarity']='explicit'
        with self.assertRaises(ValidationError): c.set_scenario(output)

    def test_controller_snapshot_is_a_copy(self):
        c=self.controller()
        snap=c.snapshot()
        snap['entries'][0]['instance']['facts']['relationship']='friend'
        self.assertEqual(c.snapshot()['entries'][0]['instance']['facts']['relationship'],'classmate')

    def test_restore_each_checkpoint_phase(self):
        c=MeasurementController(self.cfg,'s01','RESTORE',True)
        snapshots=[c.snapshot()]
        a=c.next_action(); c.set_scenario(TemplateScenarioGenerator().generate(a['task']))
        snapshots.append(c.snapshot())
        task=c.next_action()['task']; snapshots.append(c.snapshot())
        c.record_question({'question':task['question_template']}); snapshots.append(c.snapshot())
        c.record_answer('我会找老师商量。'); snapshots.append(c.snapshot())
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')]); snapshots.append(c.snapshot())
        for state in snapshots:
            with self.subTest(pending=state['pending']):
                restored=MeasurementController.restore(self.cfg,state)
                self.assertEqual(restored.snapshot(),state)

    def test_restore_rejects_changed_coverage_or_configuration(self):
        c=self.controller()
        task=self.begin(c,'我会找老师商量。')
        self.commit(c,task,[candidate(task,'U_E01_CHANNEL','我会找老师商量。')])
        altered=c.snapshot(); altered['entries'][0]['units']['U_A01_RECOVERY']['status']='covered'
        with self.assertRaises(ValidationError): MeasurementController.restore(self.cfg,altered)
        altered=c.snapshot(); altered['config_hashes']['config/measurement_units.json']='changed'
        with self.assertRaises(ValidationError): MeasurementController.restore(self.cfg,altered)

    def test_api_failure_keeps_answer_and_resume_does_not_ask_again(self):
        c=self.controller(maximum=1)
        class Fail:
            calls=0
            def extract(self,task,turn,history):
                self.calls+=1
                raise ValidationError('模拟网络故障')
        failing=Fail()
        agents=Agents(TemplateScenarioGenerator(),TemplateInterviewer(),failing,EvidenceRiskEngine(self.cfg),TemplateRiskReporter())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValidationError): run_session(c,agents,lambda t,q:'我会找老师商量。',tmp)
            self.assertEqual(failing.calls,1)
            saved=read_json(Path(tmp)/'dialogue_state.json')
            self.assertEqual(saved['pending']['answer'],'我会找老师商量。')
            restored=MeasurementController.restore(self.cfg,saved)
            class Good:
                def extract(self,task,turn,history):
                    return {'turn_id':task['turn_id'],'observations':[candidate(task,'U_E01_CHANNEL',turn['answer'])],'background':[]}
            agents.extractor=Good()
            def unexpected(*args): raise AssertionError('不应重复问已保存的回答')
            run_session(restored,agents,unexpected,tmp)
            self.assertEqual(len(restored.snapshot()['turns']),1)
            self.assertTrue((Path(tmp)/'report.md').is_file())

    def test_five_replays_are_complete_and_full_covers_all_variables(self):
        for pid in self.cfg.plans:
            bundle=ReplayBundle(read_json(ROOT/'fixtures/dialogue'/f'{pid}.json'),self.cfg)
            c=MeasurementController(self.cfg,pid,'DEMO_'+pid.upper(),True)
            while True:
                action=c.next_action()
                if action['kind']=='done': break
                if action['kind']=='scenario':
                    c.set_scenario(TemplateScenarioGenerator().generate(action['task'])); continue
                task=action['task']
                question=task['question_template']
                c.record_question({'question':question}); c.record_answer(bundle.answer(task,question))
                c.commit(bundle.extract(task,c.pending_turn(),c.history(task['entry_index'])))
            self.assertEqual(len(c.snapshot()['turns']),len(bundle.bundle['turns']))
            self.assertEqual(MeasurementController.restore(self.cfg,c.snapshot()).snapshot(),c.snapshot())
            if pid=='full':
                profile=build_profile(c.snapshot(),self.cfg)
                self.assertTrue(all(v['groups'] for v in profile['variables']))
                self.assertEqual(profile['coverage']['counts']['not_asked'],0)

    def test_replay_rejects_different_answer(self):
        bundle=ReplayBundle(read_json(ROOT/'fixtures/dialogue/s01.json'),self.cfg)
        c=self.controller()
        task=self.begin(c,'这不是预设回答。')
        with self.assertRaises(ValidationError): bundle.extract(task,c.pending_turn(),[])

    def test_all_four_llm_adapters_run_with_injected_clients(self):
        calls=[]
        def client(messages,settings):
            calls.append(settings['model'])
            data=json.loads(messages[-1]['content'])
            role=settings['model']
            if role=='a1': output={'text':data['template_text'],'facts':data['facts']}
            elif role=='a2': output={'question':data['task']['question_template']}
            elif role=='a3':
                turn=data['current_turn']
                task=c.snapshot()['pending']['task']
                output={'turn_id':turn['turn_id'],'observations':[candidate(task,'U_E01_CHANNEL',turn['answer'])],'background':[]}
            else: output=TemplateRiskReporter().report(data['profile'],data['risk'])
            return '```json\n'+json.dumps(output,ensure_ascii=False)+'\n```'
        c=MeasurementController(self.cfg,'s01','MOCKED',True,max_total_turns=1)
        with tempfile.TemporaryDirectory() as tmp:
            transport=lambda r:JsonTransport({'model':r},r,Path(tmp)/'audit',client)
            agents=Agents(LLMScenarioGenerator(self.cfg,transport('a1')),LLMInterviewer(self.cfg,transport('a2')),
                          LLMTurnExtractor(self.cfg,transport('a3')),EvidenceRiskEngine(self.cfg),LLMRiskReporter(self.cfg,transport('a4')))
            run_session(c,agents,lambda t,q:'我会找老师商量。',tmp)
            self.assertEqual(calls,['a1','a2','a3','a4'])
            self.assertEqual(len(list((Path(tmp)/'audit').rglob('raw_response.txt'))),4)

    def test_default_risk_has_no_invented_numbers(self):
        profile=self.sample_profile()
        risk=EvidenceRiskEngine(self.cfg).assess(profile)
        self.assertEqual([r['role'] for r in risk['roles']],['bully','victim','bully_victim'])
        self.assertTrue(all(r['probability'] is None and r['confidence'] is None for r in risk['roles']))

    def test_external_joint_probability_need_not_sum_to_one(self):
        profile=self.sample_profile()
        risk=ExternalPredictionRiskEngine(self.cfg,self.prediction(profile)).assess(profile)
        self.assertEqual([r['probability'] for r in risk['roles']],[0.3,0.4,0.2])

    def test_external_probability_must_obey_joint_bounds(self):
        profile=self.sample_profile()
        p=self.prediction(profile); p['probabilities']['bully_victim']=0.5
        with self.assertRaises(ValidationError): ExternalPredictionRiskEngine(self.cfg,p).assess(profile)
        p=self.prediction(profile); p['probabilities']={'bully':0.9,'victim':0.8,'bully_victim':0.1}
        with self.assertRaises(ValidationError): ExternalPredictionRiskEngine(self.cfg,p).assess(profile)

    def test_external_prediction_cannot_cross_session_or_synthetic_boundary(self):
        profile=self.sample_profile()
        p=self.prediction(profile); p['session_id']='OTHER'
        with self.assertRaises(ValidationError): ExternalPredictionRiskEngine(self.cfg,p).assess(profile)
        p=self.prediction(profile); p['synthetic']=False
        with self.assertRaises(ValidationError): ExternalPredictionRiskEngine(self.cfg,p).assess(profile)

    def test_external_prediction_rejects_nonfinite_or_boolean_probability(self):
        profile=self.sample_profile()
        for bad in (float('nan'),float('inf'),True,-0.1,1.2):
            p=self.prediction(profile); p['probabilities']['bully']=bad
            with self.assertRaises(ValidationError): ExternalPredictionRiskEngine(self.cfg,p).assess(profile)

    def test_a4_cannot_reference_unknown_or_other_variable_evidence(self):
        profile=self.sample_profile(); risk=EvidenceRiskEngine(self.cfg).assess(profile)
        notes=TemplateRiskReporter().report(profile,risk)
        notes['variable_notes'][0]['evidence_ids']=[profile['evidence_ledger'][0]['evidence_id']]
        with self.assertRaises(ValidationError): validate_narrative(notes,profile,risk)

    def test_profile_hash_detects_accidental_edits(self):
        profile=self.sample_profile(); profile['session_id']='changed'
        with self.assertRaises(ValidationError): validate_profile(profile,self.cfg)

    def test_cli_offline_validation_does_not_use_api(self):
        with patch('psych_agent.llm_client.call_chat') as chat,patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(main(['dialogue-validate']),0)
            chat.assert_not_called()


if __name__=='__main__':
    unittest.main()
