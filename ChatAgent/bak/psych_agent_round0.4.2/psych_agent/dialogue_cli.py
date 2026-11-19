"""多轮与单Agent实验命令；旧CLI只转发这些新命令。"""
from dataclasses import asdict
from pathlib import Path
import uuid

from .agent_transport import JsonTransport
from .config import require
from .dialogue_config import exact_keys, load_dialogue_config
from .dialogue_contracts import validate_question, validate_turn
from .dialogue_runner import Agents, ReplayBundle, checkpoint, run_session, save_results
from .interviewer import LLMInterviewer, TemplateInterviewer
from .io_utils import read_json, write_json
from .llm_client import inspect_settings
from .measurement_controller import MeasurementController
from .profile import build_profile, validate_profile
from .risk_engine import ExternalPredictionRiskScoringAgent, TestRiskScoringAgent, model_input, validate_risk_result
from .risk_reporter import LLMReportAgent, TemplateReportAgent, render_report, validate_narrative
from .scenario_agent import LLMScenarioGenerator, TemplateScenarioGenerator, build_scenario_task, freeze_scenario
from .turn_extractor import LLMTurnExtractor

COMMANDS={'dialogue-validate','dialogue-replay','interview','dialogue-profile','risk','report','scenario','ask','observe'}


def add_commands(sub):
    sub.add_parser('dialogue-validate',help='检查全部量表派生的多轮配置，不调用API')
    replay=sub.add_parser('dialogue-replay',help='完整回放预设多轮问答；不调用LLM')
    replay.add_argument('--plan',default='s01')
    replay.add_argument('--fixture',help='指定与计划对应的合成回放文件')
    replay.add_argument('--output')
    interview=sub.add_parser('interview',help='通过已配置LLM进行真实交互式多轮访谈')
    interview.add_argument('--plan',default=None)
    interview.add_argument('--llm-config')
    interview.add_argument('--agents-config',help='每个Agent独立选择backend及LLM配置')
    interview.add_argument('--session-id')
    interview.add_argument('--max-turns',type=int,help='本次总轮数预算；不会改变测量充分性要求')
    interview.add_argument('--resume',help='已有dialogue_state.json或运行目录；从最近保存点继续')
    interview.add_argument('--output')
    profile=sub.add_parser('dialogue-profile',help='从多轮快照重算画像、角色线索和模板报告')
    profile.add_argument('--state-file',required=True)
    profile.add_argument('--output')
    risk=sub.add_parser('risk',help='独立生成角色相关线索，或接入外部风险模型结果')
    risk.add_argument('--profile-file',required=True)
    risk.add_argument('--prediction-file')
    risk.add_argument('--output')
    report=sub.add_parser('report',help='A5独立解释已有画像与A4风险结果')
    report.add_argument('--profile-file',required=True)
    report.add_argument('--risk-file',required=True)
    report.add_argument('--llm-config',help='不指定时使用确定性的中文模板')
    report.add_argument('--output')
    scenario=sub.add_parser('scenario',help='A1独立实例化一个计划内情境')
    scenario.add_argument('--plan',default='s01')
    scenario.add_argument('--entry-index',type=int,default=0)
    scenario.add_argument('--llm-config',help='不指定时使用蓝图模板')
    scenario.add_argument('--output')
    ask=sub.add_parser('ask',help='A2独立处理已导出的提问任务')
    ask.add_argument('--task-file',required=True)
    ask.add_argument('--history-file',help='JSON数组；不提供时使用空历史')
    ask.add_argument('--llm-config')
    ask.add_argument('--output')
    observe=sub.add_parser('observe',help='A3独立处理单轮任务、回答和上下文')
    observe.add_argument('--task-file',required=True)
    observe.add_argument('--turn-file',required=True)
    observe.add_argument('--history-file')
    source=observe.add_mutually_exclusive_group(required=True)
    source.add_argument('--response-json')
    source.add_argument('--llm-config')
    observe.add_argument('--output')


def _path(root, value):
    path=Path(value)
    return path.resolve() if path.is_absolute() else (root/path).resolve()


def _transport(root, value, role, dest):
    require(value is not None, f'{role}缺少LLM配置路径')
    settings=read_json(_path(root,value))
    inspect_settings(settings)
    return JsonTransport(settings,role,dest/'llm_calls')


def resume_source(path):
    """运行目录/总快照取最新不可变保存点；具体checkpoints文件可显式选择。"""
    directory=path if path.is_dir() else path.parent
    if path.is_dir() or path.name=='dialogue_state.json':
        candidates=sorted(p for p in (directory/'checkpoints').glob('*.json') if p.stem.isdigit())
        if candidates:
            return candidates[-1],directory
    return path,directory


def live_agents(cfg, args, dest):
    specification={'a1':{'backend':'template','llm_config':None},'a2':{'backend':'llm','llm_config':None},
                   'a3':{'backend':'llm','llm_config':None},
                   'a4':{'backend':'test_equal_weight','config':'config/risk_scoring.json'},
                   'a5':{'backend':'template','llm_config':None}}
    if args.agents_config:
        document=read_json(_path(cfg.root,args.agents_config))
        require(document.get('version')=='0.4.2' and document.get('config_set_id')==cfg.config_set_id, 'Agent配置版本或配置集合不符')
        specification=document['agents']
    exact_keys(specification,['a1','a2','a3','a4','a5'],'Agent配置')
    exact_keys(specification['a4'],['backend','config'],'a4配置')
    require(specification['a4']['backend']=='test_equal_weight', '交互访谈的A4只允许等权流程测试；外部模型结果请使用risk命令导入')
    require(read_json(_path(cfg.root,specification['a4']['config']))==cfg.risk_scoring, 'A4引用的风险配置与当前配置集合不一致')
    factories={'a1':(TemplateScenarioGenerator,LLMScenarioGenerator), 'a2':(TemplateInterviewer,LLMInterviewer),
               'a3':(None,LLMTurnExtractor),'a5':(TemplateReportAgent,LLMReportAgent)}
    instances={}
    for role in ('a1','a2','a3','a5'):
        spec=specification[role]
        exact_keys(spec,['backend','llm_config'],role+'配置')
        require(spec['backend'] in ('template','llm'), f'{role}不支持此backend')
        template,llm=factories[role]
        if spec['backend']=='template':
            require(template is not None, 'A3没有基于模板或关键词的真实抽取模式；离线验证请使用dialogue-replay')
            instances[role]=template()
        else:
            path=spec['llm_config'] or args.llm_config or 'config/llm.local.json'
            instances[role]=llm(cfg,_transport(cfg.root,path,role,dest))
    return Agents(instances['a1'],instances['a2'],instances['a3'],TestRiskScoringAgent(cfg),instances['a5'])


def _checked_task(path, cfg):
    task=read_json(path)
    require(task.get('config_set_id')==cfg.config_set_id
            and task.get('config_manifest_path')=='config/config_manifest.json', '提问任务使用其他测量配置集合')
    require(task.get('plan_id') in cfg.plans, '提问任务的计划不存在')
    entries=cfg.plans[task['plan_id']]['entries']
    index=task.get('entry_index')
    require(type(index) is int and 0<=index<len(entries), '提问任务的情境索引无效')
    entry=entries[index]
    condition=cfg.condition(entry)
    require(task.get('scenario_id')==entry['scenario_id'] and task.get('condition_id')==entry['condition_id']
            and task.get('facts')==condition['facts'], '提问任务情境与计划不符')
    expected=[u for u in cfg.unit_views(entry).values() if cfg.applicable(u,condition['facts'])]
    require(task.get('allowed_units')==expected, '提问任务扩大或修改了允许的测量范围')
    require(task.get('target_unit_id') is None or task['target_unit_id'] in [u['unit_id'] for u in expected], '当前目标单元越界')
    return task


def run_command(args, root):
    from .cli import run_dir
    require(args.scope_config is None, '多轮命令使用--plan选择范围；--scope-config仅用于旧单案例命令')
    cfg=load_dialogue_config(root)
    if args.command=='dialogue-validate':
        print(f'多轮配置通过：{len(cfg.base.items)}道原题，{len(cfg.units)}个测量单元，{len(cfg.rules)}条多轮规则，{len(cfg.scenarios)}类情境。')
        print('计划：'+', '.join(cfg.plans))
        return 0
    if args.command=='dialogue-replay':
        bundle=ReplayBundle(read_json(_path(cfg.root,args.fixture or f'fixtures/dialogue/{args.plan}.json')),cfg)
        require(bundle.bundle['plan_id']==args.plan, '回放文件与指定计划不符')
        controller=MeasurementController(cfg,args.plan,'DEMO_'+args.plan.upper(),synthetic=True)
        dest=run_dir(cfg.root,'dialogue_replay',args.output)
        agents=Agents(TemplateScenarioGenerator(),TemplateInterviewer(),bundle,TestRiskScoringAgent(cfg),TemplateReportAgent())
        result=run_session(controller,agents,bundle.answer,dest)
        require(len(controller.snapshot()['turns'])==len(bundle.bundle['turns']), '回放结束但仍有未使用预制轮次')
        print(f'已完成{len(controller.snapshot()["turns"])}轮合成回放；未调用LLM。\n画像：{dest/"report.md"}\n输出：{dest}')
        return 0
    if args.command=='interview':
        if args.resume:
            require(args.output is None and args.plan is None and args.session_id is None and args.max_turns is None,
                    '续跑使用快照中的计划、编号、预算与输出目录；不要同时指定覆盖参数')
            source,dest=resume_source(_path(cfg.root,args.resume))
            saved=read_json(source)
            require(saved.get('status') in ('running','paused'), '已结束的访谈不能续跑；请开始新的访谈')
            controller=MeasurementController.restore(cfg,saved)
            require(controller.snapshot()['synthetic'] is False, '合成回放不能作为真实访谈续跑')
        else:
            controller=MeasurementController(cfg,args.plan or cfg.policy['default_plan_id'],
                         args.session_id or 'SESSION_'+uuid.uuid4().hex[:12],max_total_turns=args.max_turns)
            dest=run_dir(cfg.root,'interview',args.output)
        agents=live_agents(cfg,args,dest)
        print('开始情境访谈。输入 /skip 跳过当前问题，/stop 结束；Ctrl+C 暂停并保留续跑记录。',flush=True)
        if args.resume:
            pending=controller.snapshot()['pending']
            if pending:
                print('\n当前情境：'+pending['task']['scenario_text'],flush=True)
        def answer(task, question):
            while True:
                value=input('\n访谈：'+question+'\n你的回答：').strip()
                if value:
                    return value
                print('可以输入回答，或输入 /skip 跳过。',flush=True)
        result=run_session(controller,agents,answer,dest,
                           on_scenario=lambda s:print('\n情境：'+s['text'],flush=True))
        if result is None:
            print(f'已暂停。续跑文件：{dest/"dialogue_state.json"}')
        else:
            print(f'已生成本次对话画像。\n报告：{dest/"report.md"}\n输出：{dest}')
        return 0
    if args.command=='dialogue-profile':
        saved=read_json(_path(cfg.root,args.state_file))
        controller=MeasurementController.restore(cfg,saved,resume=False)
        dest=run_dir(cfg.root,'dialogue_profile',args.output)
        checkpoint(controller,dest)
        agents=Agents(None,None,None,TestRiskScoringAgent(cfg),TemplateReportAgent())
        save_results(controller,agents,dest)
    elif args.command in ('risk','report'):
        profile=validate_profile(read_json(_path(cfg.root,args.profile_file)),cfg)
        dest=run_dir(cfg.root,args.command,args.output)
        write_json(dest/'profile.json',profile)
        if args.command=='risk':
            engine=ExternalPredictionRiskScoringAgent(cfg,read_json(_path(cfg.root,args.prediction_file))) if args.prediction_file else TestRiskScoringAgent(cfg)
            risk=validate_risk_result(engine.assess(profile),profile)
            write_json(dest/'risk_model_input.json',model_input(profile))
            reporter=TemplateReportAgent()
        else:
            risk=validate_risk_result(read_json(_path(cfg.root,args.risk_file)),profile)
            reporter=LLMReportAgent(cfg,_transport(cfg.root,args.llm_config,'a5',dest)) if args.llm_config else TemplateReportAgent()
        write_json(dest/'risk_result.json',risk)
        narrative=validate_narrative(reporter.report(profile,risk),profile,risk)
        write_json(dest/'report_narrative.json',narrative)
        (dest/'report.md').write_text(render_report(profile,risk,narrative),encoding='utf-8')
    elif args.command=='scenario':
        require(args.plan in cfg.plans, '未知访谈计划')
        entries=cfg.plans[args.plan]['entries']
        require(0<=args.entry_index<len(entries), '情境索引超出计划')
        dest=run_dir(cfg.root,'a1',args.output)
        task=build_scenario_task(cfg,entries[args.entry_index],'A1_EXPERIMENT',args.entry_index)
        generator=LLMScenarioGenerator(cfg,_transport(cfg.root,args.llm_config,'a1',dest)) if args.llm_config else TemplateScenarioGenerator()
        write_json(dest/'scenario_task.json',task)
        write_json(dest/'scenario.json',freeze_scenario(task,generator.generate(task)))
    else:
        task=_checked_task(_path(cfg.root,args.task_file),cfg)
        history=read_json(_path(cfg.root,args.history_file)) if args.history_file else []
        require(isinstance(history,list), 'history-file必须是轮次对象组成的JSON数组')
        dest=run_dir(cfg.root,args.command,args.output)
        write_json(dest/'task.json',task)
        if args.command=='ask':
            agent=LLMInterviewer(cfg,_transport(cfg.root,args.llm_config,'a2',dest)) if args.llm_config else TemplateInterviewer()
            question=validate_question(agent.ask(task,history))
            write_json(dest/'question.json',{'question':question})
        else:
            turn=read_json(_path(cfg.root,args.turn_file))
            if args.response_json:
                candidate=read_json(_path(cfg.root,args.response_json))
            else:
                agent=LLMTurnExtractor(cfg,_transport(cfg.root,args.llm_config,'a3',dest))
                candidate=agent.extract(task,turn,history)
                if agent.last_diagnostic:
                    write_json(dest/'a3_diagnostic.json',agent.last_diagnostic)
            write_json(dest/'candidate_result.json',candidate)
            write_json(dest/'validated_turn.json',asdict(validate_turn(task,turn,history,candidate,cfg)))
    print(f'已完成 {args.command}。\n输出：{dest}')
    return 0
