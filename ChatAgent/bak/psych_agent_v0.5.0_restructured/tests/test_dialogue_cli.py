"""命令行集成：真实HTTP适配链路使用本机模拟服务，绝不访问外部模型。"""
from contextlib import redirect_stdout,redirect_stderr
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from psych_agent.cli import main
from psych_agent.dialogue_cli import resume_source
from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.io_utils import read_json,write_json
from psych_agent.measurement_controller import MeasurementController
from psych_agent.profile import build_profile
from psych_agent.risk_reporter import TemplateReportAgent

ROOT=Path(__file__).resolve().parents[1]


class DialogueCliTests(unittest.TestCase):
    def command(self, args):
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(output):
            code=main(args)
        self.assertEqual(code,0,output.getvalue())
        return output.getvalue()

    def test_independent_commands_share_consistent_saved_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            run=root/'run'
            self.command(['dialogue-replay','--plan','s01','--output',str(run)])
            state=read_json(run/'dialogue_state.json')
            profile=read_json(run/'profile.json')
            self.assertEqual(state['status'],'completed')
            self.assertEqual(len(state['turns']),profile['coverage']['answered_turns'])
            self.command(['dialogue-profile','--state-file',str(run/'dialogue_state.json'),'--output',str(root/'recomputed')])
            self.assertEqual(profile,read_json(root/'recomputed/profile.json'))
            self.command(['scenario','--plan','s01','--output',str(root/'a1')])
            self.command(['ask','--task-file',str(run/'turns/T001/task.json'),'--output',str(root/'a2')])
            self.command(['observe','--task-file',str(run/'turns/T001/task.json'),'--turn-file',str(run/'turns/T001/input.json'),
                          '--response-json',str(run/'turns/T001/candidate_result.json'),'--output',str(root/'a3')])
            self.command(['risk','--profile-file',str(run/'profile.json'),'--output',str(root/'risk')])
            self.command(['report','--profile-file',str(run/'profile.json'),'--risk-file',str(root/'risk/risk_result.json'),
                          '--output',str(root/'a5')])
            self.assertTrue((root/'a5/report.md').is_file())

    def test_full_replay_final_snapshot_recomputes_identical_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'full'
            self.command(['dialogue-replay','--plan','full','--output',str(root)])
            cfg=load_dialogue_config(ROOT)
            state=read_json(root/'dialogue_state.json')
            c=MeasurementController.restore(cfg,state,resume=False)
            self.assertEqual(build_profile(c.snapshot(),cfg),read_json(root/'profile.json'))
            self.assertEqual(state,read_json(next((root/'checkpoints').glob('*.json'))))

    def test_resume_directory_selects_latest_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            write_json(p/'checkpoints/000001.json',{'turn':1})
            write_json(p/'checkpoints/000002.json',{'turn':2})
            write_json(p/'dialogue_state.json',{'turn':1})
            selected,dest=resume_source(p/'dialogue_state.json')
            self.assertEqual(selected,p/'checkpoints/000002.json')
            self.assertEqual(dest,p)

    def test_interview_a1_a2_a3_a5_through_http_and_a4_locally(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                payload=json.loads(body['messages'][-1]['content'])
                role=body['model']; calls.append(role)
                if role=='a1': response={'text':payload['template_text'],'facts':payload['facts']}
                elif role=='a2': response={'question':payload['task']['question_template']}
                elif role=='a3':
                    quote=payload['current_turn']['answer']
                    response={'turn_id':payload['current_turn']['turn_id'],'observations':[
                        {'unit_id':'U_E01_CHANNEL','status':'covered','quote':quote,'reference_frame':'hypothetical_intent',
                         'subject':'self','context_turn_ids':[],'slots':[{'slot_id':'channel','value':'可找老师商量','quote':quote}],
                         'evidence':[{'rule_id':'DR_E01_CHANNEL_PV10_HIGHER','quote':quote,'rationale':'本机模拟服务固定输入。'}],
                         'reason':'本机HTTP协议测试。'}], 'background':[]}
                else: response=TemplateReportAgent().report(payload['profile'],payload['risk'])
                data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response,ensure_ascii=False)}}]}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                agents={}
                for role in ('a1','a2','a3','a5'):
                    path=root/f'{role}.json'
                    write_json(path,{'endpoint':f'http://127.0.0.1:{server.server_port}/chat/completions',
                                     'model':role,'api_key_env':'','api_key':'','proxy_mode':'direct','timeout_seconds':5})
                    agents[role]={'backend':'llm','llm_config':str(path)}
                agents['a4']={'backend':'test_equal_weight','config':'config/risk_scoring.json'}
                write_json(root/'agents.json',{'version':'0.5.0','config_set_id':'CFG_006','agents':agents})
                with patch('builtins.input',return_value='我会找老师商量。'):
                    self.command(['interview','--plan','s01','--max-turns','1','--session-id','HTTP_TEST',
                                  '--agents-config',str(root/'agents.json'),'--output',str(root/'result')])
                self.assertEqual(calls,['a1','a2','a3','a5'])
                state=read_json(root/'result/dialogue_state.json')
                self.assertEqual(len(state['turns']),1)
                self.assertEqual(state['stop_reason'],'total_budget_reached')
                self.assertTrue((root/'result/report.md').is_file())
                risk=read_json(root/'result/risk_result.json')
                self.assertEqual(risk['agent_id'],'A4')
                self.assertEqual(risk['status'],'test_probability_only')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
