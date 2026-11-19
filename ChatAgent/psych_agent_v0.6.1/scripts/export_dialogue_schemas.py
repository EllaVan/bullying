"""导出公开JSON接口的结构说明。跨文件范围、引用和状态转移另由运行时验证。"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from psych_agent.dialogue_contracts import observation_schema
from psych_agent.io_utils import write_json


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def array(items):
    return {'type':'array','items':items}


S={'type':'string'}
I={'type':'integer','minimum':0}
N={'type':['string','null']}
D={'type':'object'}
STRINGS=array(S)


def build():
    title={'$schema':'https://json-schema.org/draft/2020-12/schema'}
    write_json(ROOT/'schemas/turn_observation.schema.json',{**title,**observation_schema()})
    task=obj({
        'task_id':S,'plan_id':S,'config_set_id':S,'config_manifest_path':S,'session_id':S,'entry_index':I,'turn_id':S,
        'question_id':S,'scenario_id':S,'scenario_instance_id':S,'condition_id':S,'event_id':S,
        'scenario_text':S,'facts':{'type':'object','additionalProperties':S},
        'mode':{'enum':['opening','probe','clarify']},'target_unit_id':N,
        'reference_frame':S,'question_template':S,'missing_slots':array(obj({'slot_id':S,'description':S})),
        'allowed_units':array(D),'already_covered':STRINGS})
    write_json(ROOT/'schemas/question_task.schema.json',{**title,**task,
               'description':'allowed_units必须与指定plan/entry的当前配置投影完全一致，由运行时再次验证。'})
    status=obj({'status':{'enum':['not_asked','partial','covered','ambiguous','declined','not_applicable']},
                'attempts':I,'slots':D,'observation_ids':STRINGS,'evidence_ids':STRINGS,'completion_reason':N})
    entry=obj({'entry':D,'instance':{'type':['object','null']},'opened':{'type':'boolean'},
               'turn_count':I,'stop_reason':N,'units':{'type':'object','additionalProperties':status}})
    pending={'anyOf':[{'type':'null'},obj({'task':task,'question':N,'answer':N})]}
    state=obj({'schema_version':{'const':'0.6.1'},'config_set_id':S,'config_manifest_path':S,
               'session_id':S,'plan_id':S,'plan':D,'synthetic':{'type':'boolean'},
               'status':{'enum':['running','paused','stopped','completed']},'stop_reason':N,
               'entries':array(entry),'turns':array(D),'pending':pending})
    write_json(ROOT/'schemas/dialogue_state.schema.json',{**title,**state,
               'description':'快照恢复时逐轮重算并核对原题映射、原话、证据和覆盖状态，不能仅依赖此结构schema。'})
    score={'type':'number','minimum':0,'maximum':100}
    nullable_score={'anyOf':[score,{'type':'null'}]}
    prediction=obj({'schema_version':{'const':'0.6.1'},'session_id':S,'profile_id':S,'model_input_id':S,
                    'config_set_id':S,'synthetic':{'type':'boolean'},
                    'model_id':S,'assessment_target':obj({'kind':{'enum':['current_involvement','future_involvement']},'time_window':S}),
                    'role_semantics':{'const':'independent_risk_scores_0_100'},
                    'scores':obj({r:score for r in ('bully','victim','bully_victim')}),
                    'confidence':obj({r:nullable_score for r in ('bully','victim','bully_victim')}),
                    'validation_status':S})
    write_json(ROOT/'schemas/risk_prediction.schema.json',{**title,**prediction})
    nullable_number={'anyOf':[score,{'type':'null'}]}
    variable=obj({'variable_id':S,'name':S,'status':S,'value':nullable_number,'confidence':score,
                  'confidence_mode':S,'feature_weight':score,'scoring_status':S,'source_risk_role':S,
                  'interpretation_boundary':S,'groups':array(D),'coverage_units':array(D)})
    profile=obj({'schema_version':{'const':'0.6.1'},'profile_id':S,'purpose':S,'config_set_id':S,
                 'config_manifest_path':S,'source_state_file':S,'session_id':S,'plan_id':S,
                 'synthetic':{'type':'boolean'},'session_status':S,'stop_reason':N,'coverage':D,
                 'variables':array(variable),'evidence_ledger':array(D),'excluded_evidence':array(D),'experience':D,
                 'context':array(D),'scenario_instances':array(D),'test_scoring_notice':S,'note':S})
    write_json(ROOT/'schemas/profile.schema.json',{**title,**profile})
    model_feature=obj({'variable_id':S,'value':nullable_number,'confidence':score,'confidence_mode':S,
                       'feature_weight':score,'scoring_status':S,'groups':array(D)})
    model=obj({'schema_version':{'const':'0.6.1'},'model_input_id':S,'profile_id':S,
               'source_profile_file':S,'config_set_id':S,'session_id':S,'synthetic':{'type':'boolean'},
               'features':array(model_feature),'evidence':array(D),'coverage':D,
               'scenario_conditions':array(D)})
    write_json(ROOT/'schemas/risk_model_input.schema.json',{**title,**model})
    role=obj({'role':{'enum':['bully','victim','bully_victim']},'status':S,
              'score':nullable_score,'confidence':nullable_score,'confidence_mode':S,
              'observed_feature_count':I,'configured_feature_count':I,'factor_ids':STRINGS,
              'form_scores':obj({form:nullable_score for form in ('physical','verbal','relational')})})
    risk=obj({'schema_version':{'const':'0.6.1'},'risk_result_id':S,'profile_id':S,'model_input_id':S,
              'source_profile_file':S,'source_model_input_file':S,'config_set_id':S,'session_id':S,
              'synthetic':{'type':'boolean'},'agent_id':{'const':'A4'},'status':S,
              'assessment_target':D,'role_semantics':{'const':'independent_risk_scores_0_100'},'model_id':S,
              'roles':array(role),'factors':array(D),
              'validation_status':S,'note':S})
    write_json(ROOT/'schemas/risk_result.schema.json',{**title,**risk})


if __name__=='__main__':
    build()
