"""有意义的边界检查：来源、映射、去重、背景隔离与API边界。

这些测试不评价LLM语义准确率；replay数据与规则均是待人工审阅草案。
"""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from psych_agent.aggregate import aggregate
from psych_agent.cli import main
from psych_agent.config import load_config
from psych_agent.contracts import check_schema
from psych_agent.evidence import validate_extraction, validate_case
from psych_agent.extractor import build_messages
from psych_agent.io_utils import ValidationError, read_json, read_jsonl, parse_json
from psych_agent.llm_client import call_chat

ROOT = Path(__file__).resolve().parents[1]


class EvidenceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(ROOT)
        cls.cases = {c['case_id']:c for c in read_jsonl(ROOT/'data/cases.dev.jsonl')}

    def pair(self, cid='S01_001'):
        return copy.deepcopy(self.cases[cid]), read_json(ROOT/'fixtures/replay'/f'{cid}.json')

    def summary(self, cid):
        case, result = self.pair(cid)
        return aggregate(validate_extraction(case,result,self.cfg),self.cfg)

    def test_source_counts_and_background(self):
        self.assertEqual((len(self.cfg.variables),len(self.cfg.items),len(self.cfg.scenarios)),(10,30,6))
        self.assertEqual([i for i,r in self.cfg.items.items() if r['context_only']],['F01','F02','F03','F04'])
        # 原文内容作为独立依据，禁止制备时悄悄改写题干或变量对应。
        source=(ROOT/'source/心理Agent+量表与心理变量.md').read_text(encoding='utf-8')
        for iid,item in self.cfg.items.items():
            self.assertIn(iid+' '+item['text'],source)

    def test_all_fixture_formats_are_accepted_without_scores(self):
        for cid in self.cases:
            with self.subTest(case=cid):
                s=self.summary(cid)
                self.assertIsNone(s['risk_result'])
                self.assertTrue(all(v['value'] is None and v['confidence'] is None for v in s['variables']))

    def test_quote_not_in_answer_is_rejected(self):
        case,result=self.pair()
        result['evidence'][0]['quote']='我经常打人'
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_question_cannot_be_used_as_student_evidence(self):
        case,result=self.pair()
        result['evidence'][0]['quote']=case['turns'][0]['question']
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_invented_rule_is_rejected(self):
        case,result=self.pair()
        result['evidence'][0]['rule_id']='R_SELF_ESTEEM_HIGH'
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_agent_cannot_override_mapping_or_direction(self):
        case,result=self.pair()
        result['evidence'][0]['direction']='higher'
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_case_and_turn_must_match(self):
        for field,value in [('case_id','S01_other'),('turn_id','T99')]:
            case,result=self.pair()
            if field=='case_id': result[field]=value
            else: result['evidence'][0][field]=value
            with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_hypothetical_cannot_be_reported_as_past_fact(self):
        case,result=self.pair()
        result['evidence'][0]['source_kind']='self_report'
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_third_party_does_not_enter_students_profile(self):
        s=self.summary('S01_011')
        self.assertEqual(len(s['excluded_subject_or_source_evidence']),1)
        self.assertTrue(all(v['status']=='insufficient_evidence' for v in s['variables']))

    def test_third_party_subject_cannot_be_self(self):
        case,result=self.pair('S01_011')
        result['evidence'][0]['subject']='self'
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_background_is_retained_but_not_scored(self):
        s=self.summary('S01_013')
        self.assertEqual(len(s['context_evidence']),1)
        self.assertEqual([v['variable_id'] for v in s['variables']],['PV01','PV02','PV03','PV10'])
        self.assertTrue(all(v['observation_group_count']==0 for v in s['variables']))

    def test_sample_one_does_not_invent_aggression_or_hostility(self):
        s=self.summary('S01_001')
        byid={v['variable_id']:v for v in s['variables']}
        self.assertEqual(byid['PV02']['status'],'insufficient_evidence')
        self.assertEqual(byid['PV03']['status'],'insufficient_evidence')
        self.assertEqual(byid['PV10']['observation_group_count'],1)
        self.assertEqual(s['context_evidence'],[])

    def test_duplicate_candidate_is_removed(self):
        case,result=self.pair()
        result['evidence'].append(copy.deepcopy(result['evidence'][0]))
        batch=validate_extraction(case,result,self.cfg)
        self.assertEqual(batch.duplicate_candidates_removed,1)
        self.assertEqual(len(batch.evidence),3)

    def test_same_event_repeated_turns_remain_one_group(self):
        case,result=self.pair('S01_004')
        turn=copy.deepcopy(case['turns'][0]); turn['turn_id']='T2'
        case['turns'].append(turn)
        e=copy.deepcopy(result['evidence'][0]); e['turn_id']='T2'
        result['evidence'].append(e)
        s=aggregate(validate_extraction(case,result,self.cfg),self.cfg)
        v=next(v for v in s['variables'] if v['variable_id']=='PV02')
        self.assertEqual(v['observation_group_count'],1)
        self.assertEqual(len(v['observations'][0]['evidence_ids']),2)

    def test_distinct_events_are_not_merged(self):
        case,result=self.pair('S01_004')
        turn=copy.deepcopy(case['turns'][0]); turn.update(turn_id='T2',event_id='E_second')
        case['turns'].append(turn)
        e=copy.deepcopy(result['evidence'][0]); e['turn_id']='T2'; result['evidence'].append(e)
        s=aggregate(validate_extraction(case,result,self.cfg),self.cfg)
        self.assertEqual(next(v for v in s['variables'] if v['variable_id']=='PV02')['observation_group_count'],2)

    def test_real_and_hypothetical_are_separate_groups(self):
        case,result=self.pair('S01_004')
        turn=copy.deepcopy(case['turns'][0]); turn.update(turn_id='T2',response_context='real_event')
        case['turns'].append(turn)
        e=copy.deepcopy(result['evidence'][0]); e.update(turn_id='T2',source_kind='self_report'); result['evidence'].append(e)
        s=aggregate(validate_extraction(case,result,self.cfg),self.cfg)
        self.assertEqual(next(v for v in s['variables'] if v['variable_id']=='PV02')['observation_group_count'],2)

    def test_opposing_directions_are_retained(self):
        v=next(v for v in self.summary('S01_016')['variables'] if v['variable_id']=='PV02')
        self.assertEqual(v['status'],'multiple_directions_observed')
        self.assertEqual(v['observations'][0]['directions'],['higher','lower'])
        self.assertIsNone(v['value'])

    def test_ambiguous_force_is_not_explicit_aggression(self):
        v=next(v for v in self.summary('S01_005')['variables'] if v['variable_id']=='PV02')
        self.assertEqual(v['status'],'ambiguous_evidence')

    def test_unknown_and_refusal_are_missing_not_zero(self):
        s=self.summary('S01_014')
        self.assertTrue(all(v['value'] is None and v['status']=='insufficient_evidence' for v in s['variables']))

    def test_unique_quote_required(self):
        case,result=self.pair('S01_004')
        case['turns'][0]['answer']*=2
        with self.assertRaises(ValidationError): validate_extraction(case,result,self.cfg)

    def test_case_ids_cannot_escape_output_directory(self):
        case,_=self.pair(); case['case_id']='../../elsewhere'
        with self.assertRaises(ValidationError): validate_case(case,self.cfg)

    def test_functions_do_not_modify_inputs(self):
        case,result=self.pair(); before=copy.deepcopy((case,result))
        aggregate(validate_extraction(case,result,self.cfg),self.cfg)
        self.assertEqual((case,result),before)

    def test_prompt_keeps_answer_in_data_and_omits_risk_roles(self):
        case,_=self.pair(); case['turns'][0]['answer']='UNTRUSTED_INPUT_CANARY'
        messages=build_messages(case,self.cfg)
        self.assertNotIn('UNTRUSTED_INPUT_CANARY',messages[0]['content'])
        self.assertIn('UNTRUSTED_INPUT_CANARY',messages[1]['content'])
        self.assertNotIn('source_risk_role',messages[0]['content'])
        self.assertNotIn('expected_rule_ids',str(messages))


class ConfigurationTests(unittest.TestCase):
    def broken_file(self, target, mutate):
        real=read_json
        def reader(path):
            value=real(path)
            if Path(path).name==target: mutate(value)
            return value
        with patch('psych_agent.config.read_json',side_effect=reader):
            with self.assertRaises(ValidationError): load_config(ROOT)

    def test_rule_cannot_cross_original_mapping(self):
        self.broken_file('evidence_rubric.json',lambda v:v['rules'][0].update(variable_id='PV05'))

    def test_background_flag_cannot_be_changed(self):
        self.broken_file('questionnaire_mapping.json',lambda v:next(i for i in v['items'] if i['item_id']=='F02').update(context_only=False))

    def test_unsupported_scoring_switch_is_rejected(self):
        self.broken_file('aggregation_rules.json',lambda v:v.update(numeric_scores_enabled=True))

    def test_unknown_schema_keywords_are_not_silently_ignored(self):
        with self.assertRaises(ValidationError): check_schema({'type':'string','pattern':'x'})

    def test_json_duplicate_keys_nan_and_code_fences_are_rejected(self):
        for text in ['{"x":1,"x":2}','{"x":NaN}','```json\n{}\n```']:
            with self.subTest(text=text):
                with self.assertRaises(ValidationError): parse_json(text)


class AdapterAndCliTests(unittest.TestCase):
    def settings(self):
        return {'endpoint':'https://example.invalid/chat/completions','model':'test-model',
                'api_key_env':'TEST_PSYCH_KEY','json_object_mode':True,'timeout_seconds':5}

    def test_missing_key_does_not_call_network(self):
        with patch.dict(os.environ,{},clear=True), patch('psych_agent.llm_client.build_opener') as factory:
            with self.assertRaises(ValidationError): call_chat([],self.settings())
            factory.assert_not_called()

    def test_protocol_adapter_with_mocked_response(self):
        content='{"case_id":"S01_001","evidence":[],"gaps":[]}'
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':content}}]}).encode()
        opener=MagicMock(); opener.open.return_value=response
        with patch.dict(os.environ,{'TEST_PSYCH_KEY':'synthetic-test-key'}), patch('psych_agent.llm_client.build_opener',return_value=opener):
            self.assertEqual(call_chat([{'role':'user','content':'test'}],self.settings()),content)
            request=opener.open.call_args.args[0]
            self.assertFalse(json.loads(request.data)['stream'])
            self.assertEqual(json.loads(request.data)['response_format'],{'type':'json_object'})

    def test_http_error_does_not_expose_key_or_response_body(self):
        opener=MagicMock()
        opener.open.side_effect=HTTPError('https://example.invalid',401,'synthetic-test-key',{},None)
        with patch.dict(os.environ,{'TEST_PSYCH_KEY':'synthetic-test-key'}),patch('psych_agent.llm_client.build_opener',return_value=opener):
            with self.assertRaises(ValidationError) as err: call_chat([],self.settings())
            self.assertNotIn('synthetic-test-key',str(err.exception))

    def test_remote_http_and_credentials_in_url_are_rejected(self):
        for endpoint in ['http://example.invalid/chat','https://key:secret@example.invalid/chat','https://example.invalid/chat?key=secret']:
            settings=self.settings(); settings['endpoint']=endpoint
            with self.assertRaises(ValidationError): call_chat([],settings)

    def test_replay_cli_is_offline_and_creates_inspectable_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch('psych_agent.llm_client.build_opener') as factory,redirect_stdout(io.StringIO()):
            dest=Path(tmp)/'run'
            self.assertEqual(main(['replay','--all','--output',str(dest)]),0)
            factory.assert_not_called()
            self.assertEqual(len(list(dest.glob('S01_*/summary.json'))),16)
            self.assertEqual(read_json(dest/'run_manifest.json')['mode'],'replay')

    def test_independent_aggregate_cli(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            dest=Path(tmp)/'run'
            self.assertEqual(main(['aggregate','--case-file',str(ROOT/'data/single_case.json'),
                '--response-json',str(ROOT/'fixtures/replay/S01_001.json'),'--output',str(dest)]),0)
            self.assertIsNone(read_json(dest/'summary.json')['risk_result'])


if __name__=='__main__':
    unittest.main()
