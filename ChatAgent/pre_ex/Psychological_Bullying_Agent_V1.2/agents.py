
import json
from models.llm_client import call_llm


class Agent1Scenario:

    def run(self,variables):
        return json.loads(call_llm(
        "你是情景生成Agent，只生成校园情境，不分析风险。",
        json.dumps({"variables":variables},ensure_ascii=False)))


class Agent2Interview:

    def run(self,scenario,answer):
        return json.loads(call_llm(
        "你是访谈Agent，只判断是否需要追问。",
        json.dumps({"scenario":scenario,"answer":answer},ensure_ascii=False)))


class Agent3Evidence:

    def run(self,scenario,answer):
        return json.loads(call_llm(
        "你是Evidence抽取Agent，输出心理变量证据，不判断风险。",
        json.dumps({"scenario":scenario,"answer":answer},ensure_ascii=False)))


class Agent4Reasoning:

    def run(self,evidence):
        return json.loads(call_llm(
        "你是风险推理Agent，根据Evidence输出四类风险。",
        json.dumps(evidence,ensure_ascii=False)))
