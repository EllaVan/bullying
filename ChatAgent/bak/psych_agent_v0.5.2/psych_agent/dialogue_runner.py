"""本地多轮编排。依赖协议注入，逐步保存；无网络重试、数据库或Web后端。"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .config import require
from .io_utils import ValidationError, write_json
from .measurement_controller import coverage_report
from .profile import build_profile
from .risk_engine import model_input, validate_risk_result
from .risk_reporter import render_report, validate_narrative


@dataclass
class Agents:
    scenario: object
    interviewer: object
    extractor: object
    risk: object      # A4：风险计算
    reporter: object  # A5：只读报告解释


def atomic_text(path, text):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                         prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            name=stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def checkpoint(controller, dest, publish=False):
    dest=Path(dest)
    state=controller.snapshot()
    if not publish and state['synthetic']:
        return  # 回放没有等待学生/API的中间阶段；每轮输入输出另有独立文件。
    # 不反复覆盖同一个保存点。目录中的序号也可在进程被强制终止后恢复。
    snapshots=dest/'checkpoints'
    snapshots.mkdir(parents=True,exist_ok=True)
    sequence=max((int(p.stem) for p in snapshots.glob('*.json') if p.stem.isdigit()),default=0)+1
    atomic_text(snapshots/f'{sequence:06d}.json',json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    if not publish:
        return
    atomic_text(dest/'dialogue_state.json',json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    trace=[{k:t[k] for k in ('turn_id','question_id','scenario_id','condition_id','scenario_instance_id',
                            'target_unit_id','question_reference_frame','question','answer')} for t in state['turns']]
    atomic_text(dest/'conversation_trace.jsonl',''.join(json.dumps(t,ensure_ascii=False,allow_nan=False)+'\n' for t in trace))
    write_json(dest/'coverage_report.json',coverage_report(state,controller.cfg))
    write_json(dest/'run_manifest.json',{'schema_version':'0.5.2','saved_at_utc':datetime.now(timezone.utc).isoformat(),
        'session_id':state['session_id'],'plan_id':state['plan_id'],'synthetic':state['synthetic'],
        'status':state['status'],'stop_reason':state['stop_reason'],
        'config_set_id':state['config_set_id'],'config_manifest_path':'config/config_manifest.json',
        'note':'本地功能实验记录；未将API密钥写入输出。'})


def save_results(controller, agents, dest):
    checkpoint(controller,dest,publish=True)
    state=controller.snapshot()
    profile=build_profile(state,controller.cfg)
    write_json(dest/'profile.json',profile)
    write_json(dest/'experience.json',profile['experience'])
    write_json(dest/'risk_model_input.json',model_input(profile))
    write_json(dest/'validated_evidence.json',{'schema_version':'0.5.2','session_id':state['session_id'],
                    'profile_id':profile['profile_id'],'config_set_id':state['config_set_id'],
                    'evidence':[e for t in state['turns'] for e in t['validated_evidence']],
                    'background':profile['context']})
    risk=validate_risk_result(agents.risk.assess(profile),profile)
    write_json(dest/'risk_result.json',risk)
    narrative=validate_narrative(agents.reporter.report(profile,risk),profile,risk)
    write_json(dest/'report_narrative.json',narrative)
    (dest/'report.md').write_text(render_report(profile,risk,narrative),encoding='utf-8')
    return profile,risk


def run_session(controller, agents, answer_provider, dest, on_scenario=None, on_turn=None):
    dest=Path(dest)
    dest.mkdir(parents=True,exist_ok=True)
    stage='prepare'
    checkpoint(controller,dest)
    try:
        while True:
            action=controller.next_action()
            checkpoint(controller,dest)
            if action['kind']=='done':
                break
            if action['kind']=='scenario':
                stage='a1_scenario'
                generated=agents.scenario.generate(action['task'])
                instance=controller.set_scenario(generated)
                write_json(dest/'scenarios'/f'{instance["scenario_instance_id"]}.json',instance)
                checkpoint(controller,dest)
                if on_scenario:
                    on_scenario(instance)
                continue
            task=action['task']
            turn_dir=dest/'turns'/task['turn_id']
            write_json(turn_dir/'task.json',task)
            write_json(turn_dir/'history.json',controller.history(task['entry_index']))
            pending=controller.snapshot()['pending']
            if pending['question'] is None:
                stage='a2_question'
                controller.record_question(agents.interviewer.ask(deepcopy(task),controller.history(task['entry_index'])))
                checkpoint(controller,dest)
            pending=controller.snapshot()['pending']
            if pending['answer'] is None:
                stage='student_answer'
                answer=answer_provider(deepcopy(task),pending['question'])
                if answer.strip() in controller.cfg.policy['stop_commands']:
                    controller.stop('student_requested_stop')
                    checkpoint(controller,dest)
                    break
                controller.record_answer(answer)
                checkpoint(controller,dest)
            turn=controller.pending_turn()
            write_json(turn_dir/'input.json',turn)
            if turn['answer'] in controller.cfg.policy['skip_commands']:
                stage='skip_question'
                completed=controller.decline_current()
            else:
                stage='a3_extract'
                result=agents.extractor.extract(deepcopy(task),deepcopy(turn),controller.history(task['entry_index']))
                write_json(turn_dir/'candidate_result.json',result)
                diagnostic=getattr(agents.extractor,'last_diagnostic',None)
                if diagnostic:
                    write_json(turn_dir/'a3_diagnostic.json',diagnostic)
                stage='validate_turn'
                completed=controller.commit(result,extraction_fallback=bool(diagnostic and diagnostic.get('fallback_used')))
            write_json(turn_dir/'validated_turn.json',completed)
            checkpoint(controller,dest)
            if on_turn:
                on_turn(completed)
        stage='profile_and_report'
        return save_results(controller,agents,dest)
    except (EOFError,KeyboardInterrupt):
        controller.stop('paused')
        checkpoint(controller,dest,publish=True)
        # 暂停时不再发A4请求。可从快照续跑，也可独立生成现有画像。
        return None
    except (ValidationError,OSError,KeyError,TypeError,ValueError) as exc:
        checkpoint(controller,dest,publish=True)
        note=('对话和已有画像已保存；修复问题后可用report或dialogue-profile命令独立生成A5报告。'
              if stage=='profile_and_report' else
              '网络失败不自动重试；A3结构问题会先规范化上下文并最多修复一次，仍失败则安全提交空观察。其他错误保留当前问题和回答，可显式续跑。')
        error={'stage':stage,'message':str(exc),'state_file':str(dest/'dialogue_state.json'),'note':note}
        errors=dest/'errors'
        errors.mkdir(exist_ok=True)
        write_json(errors/f'{len(list(errors.glob("*.json")))+1:03d}.json',error)
        write_json(dest/'error.json',error)
        raise ValidationError(f'{stage}：{exc}\n输出：{dest}') from exc


class ReplayBundle:
    """固定回答与固定A3结果一一配对；不按关键词抽取，也不将回放声称为模型推理。"""
    def __init__(self, bundle, cfg):
        require(bundle.get('schema_version')=='0.5.2' and bundle.get('config_set_id')==cfg.config_set_id
                and bundle.get('synthetic') is True, '回放必须属于当前0.4配置集合并明确标记为合成开发数据')
        require(bundle.get('plan_id') in cfg.plans, '回放计划不存在')
        require(isinstance(bundle.get('turns'),list) and bundle['turns'], '回放轮次为空')
        references=bundle.get('scenario_references')
        require(isinstance(references,list) and references, '回放缺少情境编号引用')
        for reference in references:
            exact={'scenario_id','condition_id'}
            require(isinstance(reference,dict) and set(reference)==exact, '回放情境引用字段无效')
            actual=cfg.condition(reference)
            require(actual['condition_id']==reference['condition_id'], '回放引用未知情境条件')
        self.bundle=bundle

    def row(self, task):
        index=int(task['turn_id'][1:])-1
        require(index<len(self.bundle['turns']), '回放已无对应回答；控制器任务与固定样例不匹配')
        row=self.bundle['turns'][index]
        expected={k:task[k] for k in ('scenario_id','condition_id','target_unit_id','mode')}
        require(row['expected_task']==expected, '控制器任务与回放记录不同，拒绝套用预制结果')
        return row

    def answer(self, task, question):
        row=self.row(task)
        require(question==row['question'], '回放问题文本与固定案例不匹配')
        return row['answer']

    def extract(self, task, turn, history):
        row=self.row(task)
        require(turn['answer']==row['answer'] and turn['question']==row['question'], '回放结果不属于当前问答')
        return deepcopy(row['result'])
