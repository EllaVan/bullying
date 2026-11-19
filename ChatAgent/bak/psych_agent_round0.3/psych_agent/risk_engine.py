"""风险端的独立接口。默认组织原表相关因素；可导入外部模型的两边际概率及联合概率。"""
from copy import deepcopy
import math

from .config import require
from .dialogue_config import digest, exact_keys

ROLES = ('bully','victim','bully_victim')


def model_input(profile):
    # F类、第三方转述和未知来源始终不进入提供给风险模型的标准输入。
    data={'schema_version':'0.3.0','session_id':profile['session_id'],'synthetic':profile['synthetic'],
          'features':[{'variable_id':v['variable_id'],'groups':deepcopy(v['groups'])} for v in profile['variables']],
          'evidence':deepcopy(profile['evidence_ledger']),
          'coverage':deepcopy(profile['coverage']),
          'scenario_conditions':[{'scenario_id':s['scenario_id'],'condition_id':s['condition_id'],'facts':s['facts']}
                                 for s in profile['scenario_instances']]}
    return {**data,'input_hash':digest(data)}


class EvidenceRiskEngine:
    def __init__(self, cfg):
        self.cfg=cfg

    def assess(self, profile):
        factors=[]
        for variable in profile['variables']:
            vid=variable['variable_id']
            for group in variable['groups']:
                if not group['evidence_ids']:
                    continue
                factors.append({'factor_id':'RF_'+digest([profile['session_id'],group['group_id']])[:20],
                                'variable_id':vid,'group_id':group['group_id'],'facet':group['facet'],
                                'directions':group['directions'],'reference_frame':group['reference_frame'],
                                'scenario_ids':group['scenario_ids'],'condition_id':group['condition_id'],
                                'evidence_ids':group['evidence_ids'],
                                'source_association':variable['source_risk_role']})
        shared=[f['factor_id'] for f in factors if f['variable_id'] in self.cfg.risk_rules['shared_variables']]
        roles=[]
        for role in ROLES:
            selected=self.cfg.risk_rules['role_variables'][role]
            roles.append({'role':role,'status':'not_estimated','probability':None,'confidence':None,
                          'factor_ids':[f['factor_id'] for f in factors if f['variable_id'] in selected],
                          'shared_factor_ids':shared})
        return {'schema_version':'0.3.0','session_id':profile['session_id'],'synthetic':profile['synthetic'],
                'input_hash':model_input(profile)['input_hash'],'status':'evidence_profile_only',
                'assessment_target':{'kind':'scenario_associated_profile','time_window':None},
                'role_semantics':'marginal_with_joint','model_id':None,'roles':roles,'factors':factors,
                'note':'原量表相关因素按角色整理；没有配置风险模型，不输出虚构概率或高/中/低等级。'}


def validate_prediction(prediction, profile):
    fields=['schema_version','session_id','input_hash','synthetic','model_id','assessment_target',
            'role_semantics','probabilities','confidence','validation_status']
    exact_keys(prediction,fields,'外部风险模型输出')
    require(prediction['schema_version']=='0.3.0', '外部模型接口版本无效')
    require(prediction['session_id']==profile['session_id'] and prediction['input_hash']==model_input(profile)['input_hash'], '风险模型结果不属于当前画像输入')
    require(type(prediction['synthetic']) is bool and prediction['synthetic']==profile['synthetic'], '模拟模型结果不能套用到真实访谈')
    require(isinstance(prediction['model_id'],str) and prediction['model_id'].strip(), '外部模型缺少来源标识')
    require(prediction['role_semantics']=='marginal_with_joint', '接口要求施暴/受害边际概率及两者兼有联合概率')
    target=prediction['assessment_target']
    exact_keys(target,['kind','time_window'],'模型评估目标')
    require(target['kind'] in ('current_involvement','future_involvement'), '必须明确现实卷入或未来卷入目标')
    require(isinstance(target['time_window'],str) and target['time_window'].strip(), '模型必须明确观察或预测时间范围')
    require(isinstance(prediction['validation_status'],str) and prediction['validation_status'], '模型缺少验证状态声明')
    exact_keys(prediction['probabilities'],ROLES,'角色概率')
    exact_keys(prediction['confidence'],ROLES,'角色置信度')
    for values in (prediction['probabilities'],prediction['confidence']):
        for value in values.values():
            require(value is None or (type(value) in (int,float) and math.isfinite(value) and 0<=value<=1), '概率/置信度必须为0—1的有限数值或null')
    p=prediction['probabilities']
    require(all(p[r] is not None for r in ROLES), '外部模型需同时给出两项边际概率及联合概率')
    require(max(0,p['bully']+p['victim']-1)-1e-10 <= p['bully_victim'] <= min(p['bully'],p['victim'])+1e-10,
            '两者兼有的联合概率与施暴/受害边际概率不相容')
    require(bool(profile['evidence_ledger']), '没有核心证据时不能把此接口的模型结果作为已评估输出')
    return prediction


class ExternalPredictionRiskEngine:
    """接收外部小模型已计算的结果。自行训练/部署的模型也可直接实现RiskEngine协议。"""
    def __init__(self, cfg, prediction):
        self.cfg,self.prediction=cfg,deepcopy(prediction)

    def assess(self, profile):
        prediction=validate_prediction(self.prediction,profile)
        result=EvidenceRiskEngine(self.cfg).assess(profile)
        result.update(status='external_model_result',model_id=prediction['model_id'],
                      assessment_target=prediction['assessment_target'],validation_status=prediction['validation_status'],
                      note='数值来自指定外部模型；本项目校验接口及概率一致性，不代替该模型的有效性验证。')
        for role in result['roles']:
            role.update(status='estimated_by_external_model',probability=prediction['probabilities'][role['role']],
                        confidence=prediction['confidence'][role['role']])
        return result


def validate_risk_result(result, profile):
    require(isinstance(result,dict) and result.get('schema_version')=='0.3.0', '风险结果版本无效')
    require(result.get('session_id')==profile['session_id'] and result.get('input_hash')==model_input(profile)['input_hash'], '风险结果输入指纹不符')
    require(result.get('synthetic')==profile['synthetic'], '风险结果模拟标记不符')
    require(result.get('role_semantics')=='marginal_with_joint', '角色概率含义不符')
    roles=result.get('roles',[])
    require([r['role'] for r in roles]==list(ROLES), '风险结果必须按约定输出三个角色')
    evidence={e['evidence_id']:e for e in profile['evidence_ledger']}
    factors={f['factor_id']:f for f in result['factors']}
    require(len(factors)==len(result['factors']), '风险因素ID重复')
    for f in factors.values():
        require(bool(f['evidence_ids']) and all(e in evidence and evidence[e]['variable_id']==f['variable_id'] for e in f['evidence_ids']), '风险因素引用未知或不同变量的证据')
    for r in roles:
        require(set(r['factor_ids']+r['shared_factor_ids']).issubset(factors), '角色结果引用未知因素')
    if result['status']=='evidence_profile_only':
        require(all(r['probability'] is None and r['confidence'] is None for r in roles), '未配置模型时禁止生成概率和置信度')
    else:
        require(result['status']=='external_model_result', '未知风险结果状态')
        validate_prediction({'schema_version':'0.3.0','session_id':result['session_id'],'input_hash':result['input_hash'],
                             'synthetic':result['synthetic'],'model_id':result['model_id'],'assessment_target':result['assessment_target'],
                             'role_semantics':result['role_semantics'],'probabilities':{r['role']:r['probability'] for r in roles},
                             'confidence':{r['role']:r['confidence'] for r in roles},'validation_status':result['validation_status']},profile)
    return result
