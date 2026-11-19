"""各命令独立运行；中间结果落盘便于比较。"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic
import uuid

from .aggregate import aggregate
from .config import load_config, require
from .evidence import validate_case, validate_extraction
from .extractor import build_messages, extract_text
from .io_utils import ValidationError, read_json, read_jsonl, write_json
from .llm_client import call_chat, inspect_settings
from .model_output import parse_model_json


def run_dir(root, mode, requested=None):
    if requested:
        dest = Path(requested).resolve()
        if dest.exists() and any(dest.iterdir()):
            raise ValidationError('输出目录已存在且非空，请指定新的目录以保留已有运行记录')
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        dest = root/'outputs'/f'{stamp}_{mode}_{uuid.uuid4().hex[:8]}'
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def manifest(cfg, mode):
    paths = sorted((cfg.root/'config').glob('*.json')) + sorted((cfg.root/'schemas').glob('*.json')) + [cfg.root/'prompts/evidence_extractor.md']
    # 排除用户的本地API配置，只记录测量配置与示例配置的哈希。
    paths = [p for p in paths if p.name != 'llm.local.json']
    return {'created_at_utc':datetime.now(timezone.utc).isoformat(), 'mode':mode,
            'api_mode_requested':mode == 'llm',
            'semantic_accuracy_validated':False,
            'effective_scope':cfg.scope,
            'note':'replay仅回放预制候选输出，不测试LLM理解能力；LLM结果也需人工评阅。',
            'config_hashes':{str(p.relative_to(cfg.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def save_processed(case, response, cfg, dest):
    batch = validate_extraction(case,response,cfg)
    write_json(dest/'input.json',case)
    write_json(dest/'extraction.json',response)
    write_json(dest/'validated_evidence.json',asdict(batch))
    summary = aggregate(batch,cfg)
    write_json(dest/'summary.json',summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='心理Agent第一轮：配置、A3候选证据及纯Python汇总')
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--scope-config',help='选择本轮范围配置，例如config/round1_extended.example.json')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('validate',help='校验全部配置和案例输入，不调用API')
    doctor=sub.add_parser('doctor',help='独立检查LLM配置；默认不联网')
    doctor.add_argument('--llm-config',default='config/llm.local.json')
    doctor.add_argument('--connect',action='store_true',help='向已配置服务发送最小请求，检查连通性')
    doctor.add_argument('--direct',action='store_true',help='仅本次诊断使用直连，用于与系统代理对比')
    doctor.add_argument('--disable-thinking',action='store_true',help='仅本次诊断发送thinking.type=disabled，需模型支持')
    replay = sub.add_parser('replay',help='回放预制候选输出，验证程序链路，不评价LLM能力')
    replay.add_argument('--case',default='S01_001')
    replay.add_argument('--all',action='store_true')
    replay.add_argument('--output')
    prompt = sub.add_parser('prepare-prompt',help='导出某案例的A3请求，不调用API')
    prompt.add_argument('--case-file',required=True)
    prompt.add_argument('--output')
    extract = sub.add_parser('extract',help='从外部模型输出或真实API获得候选证据并校验汇总')
    extract.add_argument('--case-file',required=True)
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument('--response-json',help='已有A3输出JSON，本地处理')
    source.add_argument('--llm-config',help='显式调用此配置中的远程或本地模型')
    extract.add_argument('--output')
    summarizer = sub.add_parser('aggregate',help='独立校验、汇总已有候选证据，不调用LLM')
    summarizer.add_argument('--case-file',required=True)
    summarizer.add_argument('--response-json',required=True)
    summarizer.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        if args.command=='doctor':
            settings=read_json(args.llm_config)
            if not isinstance(settings,dict):
                raise ValidationError('LLM配置必须是JSON对象')
            # 命令行选项只影响本次最小请求，不写回本地配置或修改A3请求。
            if args.direct:
                settings={**settings,'proxy_mode':'direct'}
            if args.disable_thinking:
                settings={**settings,'thinking':{'type':'disabled'}}
            report=inspect_settings(settings)
            if args.connect:
                diagnostic_settings={**settings,'json_object_mode':False}
                report.update(network_test_performed=True,diagnostic_json_object_mode=False)
                started=monotonic()
                try:
                    call_chat([{'role':'user','content':'请只回复OK。'}],diagnostic_settings)
                except ValidationError as exc:
                    report.update(status='api_request_failed',elapsed_seconds=round(monotonic()-started,2),
                                  error=str(exc),note='已尝试一次最小请求；请按具体错误定位，没有自动重复请求。')
                    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
                    return 2
                report.update(status='api_connected',network_test_performed=True,
                              elapsed_seconds=round(monotonic()-started,2),
                              note='普通对话请求成功；不表示心理证据JSON输出已通过验证。')
            print(json.dumps(report,ensure_ascii=False,indent=2))
            return 0
        cfg = load_config(args.project_root,args.scope_config)
        if args.command == 'validate':
            cases = read_jsonl(cfg.root/'data/cases.dev.jsonl')
            ids = []
            for case in cases:
                validate_case(case,cfg)
                ids.append(case['case_id'])
            require(len(ids) == len(set(ids)), '开发样例包含重复case_id')
            print(f'配置校验通过：{len(cfg.variables)}个变量，{len(cfg.items)}道题，{len(cfg.scenarios)}类情境，{len(cfg.rules)}条草案规则，{len(cases)}个合成案例。')
            return 0
        if args.command == 'replay':
            cases = read_jsonl(cfg.root/'data/cases.dev.jsonl')
            selected = cases if args.all else [c for c in cases if c['case_id']==args.case]
            require(bool(selected), '找不到指定case_id')
            dest = run_dir(cfg.root,'replay',args.output)
            write_json(dest/'run_manifest.json',manifest(cfg,'replay'))
            for case in selected:
                validate_case(case,cfg)
                response = read_json(cfg.root/'fixtures/replay'/f"{case['case_id']}.json")
                save_processed(case,response,cfg,dest/case['case_id'])
            print(f'已回放{len(selected)}个合成案例。此结果只验证链路，不代表LLM抽取准确率。\n输出：{dest}')
            return 0
        case = read_json(args.case_file)
        validate_case(case,cfg)
        if args.command == 'prepare-prompt':
            dest = run_dir(cfg.root,'prompt',args.output)
            write_json(dest/'messages.json',build_messages(case,cfg))
            write_json(dest/'run_manifest.json',manifest(cfg,'prompt'))
            print(f'已导出请求，未调用API。\n输出：{dest}')
            return 0
        mode = 'llm' if args.command=='extract' and args.llm_config else 'file'
        # 先检查文件/配置，再建立本次运行目录。
        settings = read_json(args.llm_config) if mode=='llm' else None
        raw_text = None if mode=='llm' else Path(args.response_json).read_text(encoding='utf-8-sig')
        dest = run_dir(cfg.root,mode,args.output)
        write_json(dest/'run_manifest.json',manifest(cfg,mode))
        write_json(dest/'input.json',case)
        if mode == 'llm':
            write_json(dest/'messages.json',build_messages(case,cfg))
            try:
                raw_text = extract_text(case,cfg,settings)
            except ValidationError as exc:
                write_json(dest/'error.json',{'stage':'llm_request','message':str(exc)})
                raise
        (dest/'raw_response.txt').write_text(raw_text,encoding='utf-8')
        stage = 'parse_response'
        try:
            response = parse_model_json(raw_text)
            write_json(dest/'parsed_response.json',response)
            stage = 'validate_extraction'
            save_processed(case,response,cfg,dest)
        except ValidationError as exc:
            write_json(dest/'error.json',{'stage':stage,'message':str(exc),
                                         'active_variable_ids':cfg.scope['active_variable_ids']})
            raise ValidationError(f'{exc}\n输出：{dest}') from exc
        print(f'已完成候选证据校验与变量汇总。语义准确性尚需人工评阅。\n输出：{dest}')
        return 0
    except (ValidationError,OSError) as exc:
        print(f'运行未完成：{exc}',file=sys.stderr)
        return 2
