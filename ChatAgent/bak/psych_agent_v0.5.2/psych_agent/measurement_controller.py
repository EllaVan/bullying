"""纯Python测量状态机。仅控制器拥有状态，Agent只能返回独立结果。"""
from copy import deepcopy
import re

from .config import require
from .dialogue_config import digest
from .dialogue_contracts import validate_question, validate_turn
from .scenario_agent import build_scenario_task, freeze_scenario


class MeasurementController:
    def __init__(self, cfg, plan_id, session_id, synthetic=False, max_total_turns=None):
        require(plan_id in cfg.plans, '未知访谈计划')
        require(isinstance(session_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',session_id), 'session_id仅允许1—64位字母、数字、下划线和短横线')
        self.cfg = cfg
        plan = deepcopy(cfg.plans[plan_id])
        if max_total_turns is not None:
            require(type(max_total_turns) is int and 1 <= max_total_turns <= 200, '总轮数必须在1—200之间')
            plan['max_total_turns'] = max_total_turns
        self._state = {'schema_version':'0.5.2','config_set_id':cfg.config_set_id,
                       'config_manifest_path':'config/config_manifest.json',
                       'session_id':session_id,'plan_id':plan_id,'plan':plan,'synthetic':bool(synthetic),
                       'status':'running','stop_reason':None,'entries':[],'turns':[],'pending':None}
        for entry in plan['entries']:
            views = cfg.unit_views(entry)
            statuses = {uid:{'status':'not_asked','attempts':0,'slots':{},'observation_ids':[],
                              'evidence_ids':[],'completion_reason':None} for uid in views}
            self._state['entries'].append({'entry':deepcopy(entry),'instance':None,'opened':False,
                                          'turn_count':0,'stop_reason':None,'units':statuses})

    def snapshot(self):
        return deepcopy(self._state)

    def history(self, index):
        return deepcopy([t for t in self._state['turns'] if t['entry_index']==index])

    def next_action(self):
        state = self._state
        if state['status'] != 'running':
            return {'kind':'done','stop_reason':state['stop_reason']}
        if state['pending']:
            return {'kind':'question','task':deepcopy(state['pending']['task'])}
        for index, record in enumerate(state['entries']):
            if record['stop_reason']:
                continue
            entry = record['entry']
            if record['instance'] is None:
                if len(state['turns']) >= state['plan']['max_total_turns']:
                    self.stop('total_budget_reached')
                    return {'kind':'done','stop_reason':state['stop_reason']}
                return {'kind':'scenario','entry_index':index,
                        'task':build_scenario_task(self.cfg,entry,state['session_id'],index)}
            if record['turn_count'] >= entry['max_turns']:
                record['stop_reason'] = 'scenario_budget_reached'
                continue
            pending_units = [(uid, s) for uid,s in record['units'].items()
                             if s['status'] not in ('covered','declined','not_applicable')
                             and s['attempts'] < self.cfg.policy['max_attempts_per_unit']]
            if not pending_units:
                record['stop_reason'] = ('required_units_resolved' if all(s['status'] in ('covered','declined','not_applicable')
                                         for s in record['units'].values()) else 'unit_attempts_exhausted')
                continue
            if len(state['turns']) >= state['plan']['max_total_turns']:
                self.stop('total_budget_reached')
                return {'kind':'done','stop_reason':state['stop_reason']}
            if not record['opened']:
                target, mode = None, 'opening'
            else:
                # 首先补充已开始而含糊/部分覆盖的单元，随后使用预先配置的顺序。
                started = [(uid,s) for uid,s in pending_units if s['status'] in ('partial','ambiguous')]
                target, status = (started or pending_units)[0]
                mode = 'clarify' if status['attempts'] else 'probe'
            task = self._make_task(index,target,mode)
            state['pending'] = {'task':task,'question':None,'answer':None}
            return {'kind':'question','task':deepcopy(task)}
        state['status'], state['stop_reason'] = 'completed', 'plan_finished'
        return {'kind':'done','stop_reason':'plan_finished'}

    def set_scenario(self, output):
        action = self.next_action()
        require(action['kind']=='scenario', '当前没有待生成的情境')
        record = self._state['entries'][action['entry_index']]
        instance = freeze_scenario(action['task'],output)
        record['instance'] = instance
        for uid, unit in self.cfg.unit_views(record['entry']).items():
            if not self.cfg.applicable(unit,instance['facts']):
                record['units'][uid].update(status='not_applicable',completion_reason='scenario_condition_not_met')
        return deepcopy(instance)

    def _make_task(self, index, target, mode):
        state = self._state
        record = state['entries'][index]
        entry, instance = record['entry'], record['instance']
        views = self.cfg.unit_views(entry)
        allowed = [u for uid,u in views.items() if self.cfg.applicable(u,instance['facts'])]
        number = len(state['turns'])+1
        missing = []
        frame = 'hypothetical_intent'
        question = self.cfg.scenarios[entry['scenario_id']]['opening_question']
        if target:
            unit, status = views[target], record['units'][target]
            frame = unit['reference_frame']
            missing = [s for s in unit['required_slots'] if s['slot_id'] not in status['slots']]
            question = unit['question_template']
            if target == 'U_E05_PROTECTION' and status['slots']:
                if [s['slot_id'] for s in missing] == ['self_protection']:
                    question = '按你刚才说的办法帮助同学时，你会怎样照顾自己的安全？'
                elif [s['slot_id'] for s in missing] == ['help_action']:
                    question = '考虑到你刚才说的安全问题，你希望怎样帮助那位同学？'
            elif mode=='clarify':
                question = self.cfg.policy['response_quality']['alternate_probe_prefix'] + question
        return {'task_id':f'TASK_{state["session_id"]}_{number:03d}',
                'plan_id':state['plan_id'],'config_set_id':self.cfg.config_set_id,
                'config_manifest_path':'config/config_manifest.json',
                'session_id':state['session_id'],'entry_index':index,'turn_id':f'T{number:03d}',
                'question_id':f'Q{number:03d}','scenario_id':entry['scenario_id'],
                'scenario_instance_id':instance['scenario_instance_id'],'condition_id':entry['condition_id'],
                'event_id':instance['event_id'],'scenario_text':instance['text'],'facts':deepcopy(instance['facts']),
                'mode':mode,'target_unit_id':target,'reference_frame':frame,
                'question_template':question,'missing_slots':missing,'allowed_units':allowed,
                'already_covered':[uid for uid,s in record['units'].items() if s['status']=='covered']}

    def record_question(self, result):
        pending = self._state['pending']
        require(pending is not None and pending['question'] is None, '本轮问题已经固定或尚未准备任务')
        pending['question'] = validate_question(result)

    def record_answer(self, answer):
        pending = self._state['pending']
        require(pending is not None and pending['question'] is not None and pending['answer'] is None, '回答必须对应当前已固定的问题，不能重复提交')
        require(isinstance(answer,str) and answer.strip() and len(answer)<=12000, '回答不能为空或超过12000字')
        pending['answer'] = answer.strip()

    def pending_turn(self):
        pending = self._state['pending']
        require(pending is not None and pending['answer'] is not None, '当前没有待抽取的回答')
        task = pending['task']
        fields = ('task_id','turn_id','question_id','scenario_id','scenario_instance_id','condition_id','event_id','entry_index')
        return {**{k:task[k] for k in fields},'question':pending['question'],'answer':pending['answer'],
                'target_unit_id':task['target_unit_id'],'mode':task['mode'],
                'question_reference_frame':task['reference_frame']}

    def commit(self, result, extraction_fallback=False):
        task = self._state['pending']['task']
        turn = self.pending_turn()
        validated = validate_turn(task,turn,self.history(task['entry_index']),result,self.cfg)
        # 在全部候选校验成功后才提交，失败不损失已输入回答且不推进覆盖状态。
        record = self._state['entries'][task['entry_index']]
        target = task['target_unit_id']
        if target:
            record['units'][target]['attempts'] += 1
        quality_policy = self.cfg.policy['response_quality']
        compact_answer = ''.join(turn['answer'].split())
        response_eligible = turn['answer'] not in self.cfg.policy['skip_commands']
        brief = response_eligible and len(compact_answer) <= quality_policy['brief_response_max_characters']
        useful = [obs for obs in validated.observations
                  if obs['coverage_eligible'] and (obs['slots'] or obs['evidence_ids'])]
        low_information = response_eligible and not useful and not validated.experiences and not extraction_fallback
        alternate_probe = bool(target and low_information
                               and record['units'][target]['attempts'] < self.cfg.policy['max_attempts_per_unit'])
        record['opened'] = True
        record['turn_count'] += 1
        turn.update(candidate_result=deepcopy(result),validated_observations=list(validated.observations),
                    validated_evidence=list(validated.evidence),background=list(validated.background),
                    validated_experiences=list(validated.experiences),
                    response_quality={'response_eligible':response_eligible,
                                      'answer_characters':len(compact_answer),
                                      'brief_response':brief,
                                      'low_information':low_information,
                                      'alternate_probe_scheduled':alternate_probe,
                                      'a3_fallback_used':bool(extraction_fallback)})
        self._state['turns'].append(turn)
        for obs in validated.observations:
            status = record['units'][obs['unit_id']]
            status['observation_ids'].append(obs['observation_id'])
            status['evidence_ids'].extend(obs['evidence_ids'])
            if not obs['coverage_eligible'] or status['status'] in ('declined','not_applicable'):
                continue
            if status['status']=='covered':
                continue  # 后续不同方向仍在证据中保留，不触发已覆盖问题的循环重问。
            if obs['status'] in ('declined','not_applicable'):
                status.update(status=obs['status'],completion_reason='explicit_student_response')
                continue
            status['slots'].update({s['slot_id']:{**s,'observation_id':obs['observation_id']} for s in obs['slots']})
            required = {s['slot_id'] for s in self.cfg.units[obs['unit_id']]['required_slots']}
            complete = required.issubset(status['slots']) and obs['status'] != 'ambiguous'
            status['status'] = 'covered' if complete else ('partial' if status['slots'] else 'ambiguous')
            if complete:
                status['completion_reason'] = 'required_information_obtained'
        if target and record['units'][target]['status']=='not_asked':
            record['units'][target]['status'] = 'ambiguous'
        self._state['pending'] = None
        return deepcopy(turn)

    def decline_current(self):
        pending = self._state['pending']
        task = pending['task']
        if pending['answer'] is None:
            self.record_answer('/skip')
        observations=[]
        if task['target_unit_id']:
            observations=[{'unit_id':task['target_unit_id'],'status':'declined','quote':pending['answer'],
                           'reference_frame':task['reference_frame'],'subject':'self','context_turn_ids':[],
                           'slots':[],'evidence':[],'reason':'学生通过跳过命令拒绝本题。'}]
        return self.commit({'turn_id':task['turn_id'],'observations':observations,'background':[]})

    def stop(self, reason='student_requested_stop'):
        require(reason in ('student_requested_stop','total_budget_reached','input_closed','paused'), '无效结束原因')
        self._state['status'] = 'paused' if reason in ('paused','input_closed') else 'stopped'
        self._state['stop_reason'] = reason

    @classmethod
    def restore(cls, cfg, saved, resume=True):
        require(isinstance(saved,dict) and saved.get('schema_version')=='0.5.2', '会话快照版本不兼容')
        require(saved.get('config_set_id')==cfg.config_set_id
                and saved.get('config_manifest_path')=='config/config_manifest.json',
                '会话快照使用其他配置集合；请使用对应配置，或开始新的访谈')
        controller = cls(cfg,saved['plan_id'],saved['session_id'],saved['synthetic'],saved['plan']['max_total_turns'])
        require(saved['plan']==controller._state['plan'], '快照中的计划与当前配置不一致')

        def action_with_instances(seek_question=True):
            action = controller.next_action()
            while action['kind']=='scenario':
                original = saved['entries'][action['entry_index']]['instance']
                if original is None:
                    break
                inst = controller.set_scenario({'text':original['text'],'facts':original['facts']})
                require(inst == original, '情境快照的事实或编号不一致')
                if not seek_question and controller._state['entries']==saved['entries']:
                    return {'kind':'checkpoint'}
                action = controller.next_action()
            return action

        for original in saved['turns']:
            action = action_with_instances()
            require(action['kind']=='question' and action['task']['task_id']==original['task_id'], '快照轮次顺序无效')
            controller.record_question({'question':original['question']})
            controller.record_answer(original['answer'])
            fallback=original.get('response_quality',{}).get('a3_fallback_used',False)
            rebuilt = controller.commit(original['candidate_result'],extraction_fallback=fallback)
            require(rebuilt==original, '快照证据与原始回答重算结果不一致')
        pending = saved['pending']
        if pending or controller._state['entries']!=saved['entries'] or saved['status']=='completed':
            action_with_instances(seek_question=bool(pending))
        if pending:
            require(controller._state['pending'] is not None and pending['task']==controller._state['pending']['task'], '快照待办任务与重算结果不一致')
            if pending['question'] is not None:
                controller.record_question({'question':pending['question']})
            if pending['answer'] is not None:
                controller.record_answer(pending['answer'])
        else:
            # 保存点可能位于刚完成一轮、尚未准备下一问的位置。
            controller._state['pending'] = None
        require(controller._state['entries']==saved['entries'], '覆盖状态与原始回答重算结果不一致')
        if saved['status'] in ('paused','running'):
            controller._state['status'],controller._state['stop_reason'] = 'running',None
        elif saved['status']=='stopped':
            controller.stop(saved['stop_reason'])
        else:
            require(saved['status']=='completed' and controller._state['status']=='completed', '结束状态无效')
        if not resume:
            controller._state['status'],controller._state['stop_reason']=saved['status'],saved['stop_reason']
        return controller


def coverage_report(state, cfg):
    records=[]
    for entry_record in state['entries']:
        entry = entry_record['entry']
        views=cfg.unit_views(entry)
        for uid, status in entry_record['units'].items():
            records.append({'scenario_id':entry['scenario_id'],'condition_id':entry['condition_id'],
                            'scenario_instance_id':entry_record['instance']['scenario_instance_id'] if entry_record['instance'] else None,
                            'unit_id':uid,'source_item_ids':views[uid]['source_item_ids'],
                            'target_variable_ids':views[uid]['target_variable_ids'],'reference_frame':views[uid]['reference_frame'],
                            'status':status['status'],'attempts':status['attempts'],
                            'missing_slots':[s['slot_id'] for s in views[uid]['required_slots'] if s['slot_id'] not in status['slots']],
                            'completion_reason':status['completion_reason'],
                            'unfinished_reason':None if status['status']=='covered' else (status['completion_reason'] or entry_record['stop_reason'] or state['stop_reason'] or 'not_yet_obtained'),
                            'observation_ids':list(status['observation_ids'])})
    counts={s:sum(r['status']==s for r in records) for s in ('not_asked','partial','covered','ambiguous','declined','not_applicable')}
    applicable=len(records)-counts['not_applicable']
    forms={f:{'visited':False,'answered_turns':0,'covered_units':0} for f in ('physical','verbal','relational')}
    for i, rec in enumerate(state['entries']):
        form=cfg.condition(rec['entry'])['facts']['form']
        forms[form]['visited'] |= rec['turn_count']>0
        forms[form]['answered_turns'] += rec['turn_count']
        forms[form]['covered_units'] += sum(s['status']=='covered' for s in rec['units'].values())
    quality_policy=cfg.policy['response_quality']
    quality_rows=[t['response_quality'] for t in state['turns']]
    eligible=[q for q in quality_rows if q['response_eligible']]
    brief_count=sum(q['brief_response'] for q in eligible)
    brief_rate=brief_count/len(eligible) if eligible else None
    response_quality={'eligible_response_turns':len(eligible),
                      'explicit_skip_turns':len(quality_rows)-len(eligible),
                      'brief_response_turns':brief_count,
                      'brief_response_rate':brief_rate,
                      'brief_response_max_characters':quality_policy['brief_response_max_characters'],
                      'warning_threshold':quality_policy['warning_threshold'],
                      'warning_triggered':brief_rate is not None and brief_rate > quality_policy['warning_threshold'],
                      'low_information_turns':sum(q['low_information'] for q in eligible),
                      'alternate_probe_scheduled_turns':sum(q['alternate_probe_scheduled'] for q in quality_rows),
                      'a3_fallback_turns':sum(q['a3_fallback_used'] for q in quality_rows),
                      'interpretation_boundary':quality_policy['interpretation_boundary']}
    return {'schema_version':'0.5.2','config_set_id':state['config_set_id'],
            'session_id':state['session_id'],'plan_id':state['plan_id'],
            'status':state['status'],'stop_reason':state['stop_reason'],'answered_turns':len(state['turns']),
            'planned_unit_instances':len(records),'counts':counts,
            'coverage_fraction':counts['covered']/applicable if applicable else None,'forms':forms,
            'response_quality':response_quality,'units':records,
            'note':'覆盖率仅表示本计划信息槽位完成情况，不是心理信度、风险概率或原量表完成率。'}
