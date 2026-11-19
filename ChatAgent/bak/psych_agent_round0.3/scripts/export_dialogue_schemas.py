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
        'task_id':S,'plan_id':S,'measurement_config_hash':S,'session_id':S,'entry_index':I,'turn_id':S,
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
    state=obj({'schema_version':{'const':'0.3.0'},'session_id':S,'plan_id':S,'plan':D,
               'config_hashes':{'type':'object','additionalProperties':S},'synthetic':{'type':'boolean'},
               'status':{'enum':['running','paused','stopped','completed']},'stop_reason':N,
               'entries':array(entry),'turns':array(D),'pending':pending})
    write_json(ROOT/'schemas/dialogue_state.schema.json',{**title,**state,
               'description':'快照恢复时逐轮重算并核对原题映射、原话、证据和覆盖状态，不能仅依赖此结构schema。'})
    probability={'type':'number','minimum':0,'maximum':1}
    nullable_probability={'anyOf':[probability,{'type':'null'}]}
    prediction=obj({'schema_version':{'const':'0.3.0'},'session_id':S,'input_hash':S,'synthetic':{'type':'boolean'},
                    'model_id':S,'assessment_target':obj({'kind':{'enum':['current_involvement','future_involvement']},'time_window':S}),
                    'role_semantics':{'const':'marginal_with_joint'},
                    'probabilities':obj({r:probability for r in ('bully','victim','bully_victim')}),
                    'confidence':obj({r:nullable_probability for r in ('bully','victim','bully_victim')}),
                    'validation_status':S})
    write_json(ROOT/'schemas/risk_prediction.schema.json',{**title,**prediction})


if __name__=='__main__':
    build()
