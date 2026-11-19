"""A4风险计算接口：默认等权流程测试；正式环境可导入已校准外部模型结果。"""
from copy import deepcopy
import math

from .config import require
from .dialogue_config import exact_keys

ROLES = ('bully','victim','bully_victim')
FORMS = ('physical','verbal','relational')


def model_input(profile):
    """生成A4只读输入。F类、第三方和未知来源已经由画像边界排除。"""
    return {'schema_version':'0.4.0','model_input_id':'MODEL_INPUT_'+profile['session_id'],
            'profile_id':profile['profile_id'],'source_profile_file':'profile.json',
            'config_set_id':profile['config_set_id'],'session_id':profile['session_id'],
            'synthetic':profile['synthetic'],
            'features':[{'variable_id':v['variable_id'],'value':v['value'],'confidence':v['confidence'],
                         'confidence_mode':v['confidence_mode'],'feature_weight':v['feature_weight'],
                         'scoring_status':v['scoring_status'],'groups':deepcopy(v['groups'])}
                        for v in profile['variables']],
            'evidence':deepcopy(profile['evidence_ledger']),'coverage':deepcopy(profile['coverage']),
            'scenario_conditions':[{'scenario_id':s['scenario_id'],'condition_id':s['condition_id'],'facts':s['facts']}
                                   for s in profile['scenario_instances']],
            'human_review_required':True}


def _risk_support(value, effect):
    if value is None:
        return None
    return value if effect=='risk_increasing' else 1.0-value


def _mean(values, digits):
    values=[v for v in values if v is not None]
    return round(sum(values)/len(values),digits) if values else None


def _group_form_values(profile, variable_id):
    forms={s['scenario_id']:s['facts']['form'] for s in profile['scenario_instances']}
    variable=next(v for v in profile['variables'] if v['variable_id']==variable_id)
    result={form:[] for form in FORMS}
    for group in variable['groups']:
        for scenario_id in group['scenario_ids']:
            form=forms.get(scenario_id)
            if form and group['test_value'] is not None:
                result[form].append(group['test_value'])
    return result


class TestRiskScoringAgent:
    """用于打通产品流程的A4；数值是等权启发式测试值，不是已标定概率。"""
    def __init__(self, cfg):
        self.cfg=cfg

    def assess(self, profile):
        variables={v['variable_id']:v for v in profile['variables']}
        scoring=self.cfg.risk_scoring
        digits=scoring['probability_round_digits']
        factors=[]
        for role in ROLES:
            for spec in scoring['roles'][role]:
                variable=variables[spec['variable_id']]
                support=_risk_support(variable['value'],spec['effect'])
                factors.append({'factor_id':f'RF_{role}_{spec["variable_id"]}',
                                'role':role,'variable_id':spec['variable_id'],'effect':spec['effect'],
                                'weight':spec['weight'],'variable_value':variable['value'],
                                'risk_support':None if support is None else round(support,digits),
                                'confidence':variable['confidence'],
                                'evidence_ids':sorted({eid for group in variable['groups'] for eid in group['evidence_ids']}),
                                'source_item_ids':sorted({iid for group in variable['groups'] for iid in group['source_item_ids']})})
        by_role={role:[f for f in factors if f['role']==role] for role in ROLES}
        roles=[]
        for role in ROLES:
            available=[f for f in by_role[role] if f['risk_support'] is not None]
            probability=(_mean([f['risk_support'] for f in available],digits)
                         if len(available)>=scoring['minimum_observed_features'] else None)
            form_probabilities={}
            for form in FORMS:
                form_values=[]
                for spec in scoring['roles'][role]:
                    values=_group_form_values(profile,spec['variable_id'])[form]
                    value=_mean(values,digits)
                    support=_risk_support(value,spec['effect'])
                    if support is not None:
                        form_values.append(support)
                form_probabilities[form]=_mean(form_values,digits)
            roles.append({'role':role,'status':'test_probability_human_review_required',
                          'probability':probability,
                          'confidence':self.cfg.confidence_policy['role_confidence'] if probability is not None else None,
                          'confidence_mode':self.cfg.confidence_policy['mode'],
                          'observed_feature_count':len(available),
                          'configured_feature_count':len(by_role[role]),
                          'factor_ids':[f['factor_id'] for f in by_role[role]],
                          'form_probabilities':form_probabilities})
        values={r['role']:r['probability'] for r in roles}
        if all(values[r] is not None for r in ROLES):
            lower=max(0.0,values['bully']+values['victim']-1.0)
            upper=min(values['bully'],values['victim'])
            joint=min(max(values['bully_victim'],lower),upper)
            next(r for r in roles if r['role']=='bully_victim')['probability']=round(joint,digits)
        for form in FORMS:
            per_form={r['role']:r['form_probabilities'][form] for r in roles}
            if all(per_form[r] is not None for r in ROLES):
                lower=max(0.0,per_form['bully']+per_form['victim']-1.0)
                upper=min(per_form['bully'],per_form['victim'])
                joint=min(max(per_form['bully_victim'],lower),upper)
                next(r for r in roles if r['role']=='bully_victim')['form_probabilities'][form]=round(joint,digits)
        result={'schema_version':'0.4.0','risk_result_id':'RISK_'+profile['session_id'],
                'profile_id':profile['profile_id'],'model_input_id':'MODEL_INPUT_'+profile['session_id'],
                'source_profile_file':'profile.json','source_model_input_file':'risk_model_input.json',
                'config_set_id':profile['config_set_id'],'session_id':profile['session_id'],
                'synthetic':profile['synthetic'],'agent_id':'A4','status':'test_probability_only',
                'assessment_target':deepcopy(scoring['assessment_target']),
                'role_semantics':scoring['role_semantics'],'model_id':scoring['model_id'],
                'roles':roles,'factors':factors,'human_review_required':True,
                'validation_status':'uncalibrated_flow_test',
                'note':scoring['note']+' '+self.cfg.confidence_policy['display_warning']}
        return result


def validate_prediction(prediction, profile):
    fields=['schema_version','session_id','profile_id','model_input_id','config_set_id','synthetic','model_id',
            'assessment_target','role_semantics','probabilities','confidence','validation_status']
    exact_keys(prediction,fields,'外部风险模型输出')
    require(prediction['schema_version']=='0.4.0', '外部模型接口版本无效')
    require(prediction['session_id']==profile['session_id']
            and prediction['profile_id']==profile['profile_id']
            and prediction['model_input_id']=='MODEL_INPUT_'+profile['session_id']
            and prediction['config_set_id']==profile['config_set_id'], '风险模型结果不属于当前画像输入')
    require(type(prediction['synthetic']) is bool and prediction['synthetic']==profile['synthetic'], '模拟模型结果不能套用到真实访谈')
    require(isinstance(prediction['model_id'],str) and prediction['model_id'].strip(), '外部模型缺少来源标识')
    require(prediction['role_semantics']=='marginal_with_joint', '接口要求施暴/受害边际概率及两者兼有联合概率')
    target=prediction['assessment_target']
    exact_keys(target,['kind','time_window'],'模型评估目标')
    require(target['kind'] in ('current_involvement','future_involvement'), '外部模型必须明确现实卷入或未来卷入目标')
    require(isinstance(target['time_window'],str) and target['time_window'].strip(), '外部模型必须明确观察或预测时间范围')
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
    require(bool(profile['evidence_ledger']), '没有核心证据时不能把模型结果作为已评估输出')
    return prediction


class ExternalPredictionRiskScoringAgent:
    """A4外部模型适配器；模型训练和部署与本项目保持独立。"""
    def __init__(self, cfg, prediction):
        self.cfg,self.prediction=cfg,deepcopy(prediction)

    def assess(self, profile):
        prediction=validate_prediction(self.prediction,profile)
        base=TestRiskScoringAgent(self.cfg).assess(profile)
        base.update(status='external_model_result',model_id=prediction['model_id'],
                    assessment_target=prediction['assessment_target'],validation_status=prediction['validation_status'],
                    human_review_required=True,
                    note='数值来自指定外部模型；接口校验不代替该模型的有效性、标定和人工复核。')
        for role in base['roles']:
            role.update(status='estimated_by_external_model',probability=prediction['probabilities'][role['role']],
                        confidence=prediction['confidence'][role['role']],confidence_mode='external_model',
                        form_probabilities={form:None for form in FORMS})
        return base


def validate_risk_result(result, profile):
    require(isinstance(result,dict) and result.get('schema_version')=='0.4.0', '风险结果版本无效')
    require(result.get('session_id')==profile['session_id']
            and result.get('profile_id')==profile['profile_id']
            and result.get('model_input_id')=='MODEL_INPUT_'+profile['session_id']
            and result.get('config_set_id')==profile['config_set_id'], '风险结果输入引用不符')
    require(result.get('synthetic')==profile['synthetic'] and result.get('agent_id')=='A4', '风险结果来源标记不符')
    require(result.get('role_semantics')=='marginal_with_joint', '角色概率含义不符')
    roles=result.get('roles',[])
    require([r['role'] for r in roles]==list(ROLES), '风险结果必须按约定输出三个角色')
    require(all(set(r['form_probabilities'])==set(FORMS) for r in roles), 'A4必须保留三种霸凌形式的结果位置')
    factors={f['factor_id']:f for f in result.get('factors',[])}
    require(len(factors)==len(result.get('factors',[])), '风险因素ID重复')
    for role in roles:
        require(set(role['factor_ids']).issubset(factors), '角色结果引用未知因素')
        for value in [role['probability'],role['confidence'],*role['form_probabilities'].values()]:
            require(value is None or (type(value) in (int,float) and math.isfinite(value) and 0<=value<=1), '风险结果含无效数值')
    probability={r['role']:r['probability'] for r in roles}
    if all(probability[r] is not None for r in ROLES):
        require(max(0,probability['bully']+probability['victim']-1)-1e-10 <= probability['bully_victim']
                <= min(probability['bully'],probability['victim'])+1e-10, 'A4三角色概率关系不一致')
    for form in FORMS:
        values={r['role']:r['form_probabilities'][form] for r in roles}
        if all(values[r] is not None for r in ROLES):
            require(max(0,values['bully']+values['victim']-1)-1e-10 <= values['bully_victim']
                    <= min(values['bully'],values['victim'])+1e-10, 'A4分形式概率关系不一致')
    if result['status']=='test_probability_only':
        require(result.get('validation_status')=='uncalibrated_flow_test'
                and result.get('human_review_required') is True
                and all(r['confidence'] in (None,1.0) and r['confidence_mode']=='fixed_test_value' for r in roles),
                '测试风险结果缺少固定置信度或人工复核标记')
    else:
        require(result['status']=='external_model_result', '未知风险结果状态')
        validate_prediction({'schema_version':'0.4.0','session_id':result['session_id'],
                             'profile_id':result['profile_id'],'model_input_id':result['model_input_id'],
                             'config_set_id':result['config_set_id'],'synthetic':result['synthetic'],
                             'model_id':result['model_id'],'assessment_target':result['assessment_target'],
                             'role_semantics':result['role_semantics'],'probabilities':{r['role']:r['probability'] for r in roles},
                             'confidence':{r['role']:r['confidence'] for r in roles},'validation_status':result['validation_status']},profile)
    return result


# 兼容0.3代码中的类名；实际职责在0.4中均属于A4。
EvidenceRiskEngine = TestRiskScoringAgent
ExternalPredictionRiskEngine = ExternalPredictionRiskScoringAgent
