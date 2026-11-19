
import json
from models.llm_client import call_llm

def run_agent(system,payload):
    return json.loads(call_llm(system,json.dumps(payload,ensure_ascii=False)))


AGENT1='''
你是情景生成Agent。
根据心理变量生成校园情境。
只输出scenario、question、variables。
禁止分析风险。
'''

AGENT2='''
你是心理访谈Agent。
根据学生回答判断是否需要追问。
禁止判断心理变量。
输出need_followup和question。
'''

AGENT3='''
你是Evidence抽取Agent。
从回答中抽取心理证据。
输出:
original_text,evidence_type,variable,value,confidence。
禁止风险判断。
'''

AGENT4='''
你是风险推理Agent。
根据Evidence估计:
bully_risk,victim_risk,bully_victim_risk,bystander_risk。
必须引用Evidence。
'''

def scenario():
    return run_agent(AGENT1,{"variables":["PV01","PV07"]})

def interview(scenario,answer):
    return run_agent(AGENT2,{"scenario":scenario,"answer":answer})

def evidence(scenario,answer):
    return run_agent(AGENT3,{"scenario":scenario,"answer":answer})

def reasoning(e):
    return run_agent(AGENT4,e)
