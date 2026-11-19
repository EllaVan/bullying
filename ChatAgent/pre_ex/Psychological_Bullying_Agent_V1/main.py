
# 在所有import之前！！！
import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

from agents.agent1_scenario.agent import ScenarioAgent
from agents.agent2_interviewer.agent import InterviewAgent
from agents.agent3_evidence.agent import EvidenceAgent
from agents.agent4_reasoning.agent import ReasoningAgent


def main():

    print("=== Psychological Bullying Agent V1 ===")

    agent1 = ScenarioAgent()
    
    
    

    scenario = agent1.generate(
        target_variables=["PV01", "PV07"]
    )

    print("\n情景:")
    print(scenario["question"])

    history = []

    while True:
        answer = input("\n学生回答(q退出): ")

        if answer == "q":
            break

        agent2 = InterviewAgent()
        result = agent2.chat(
            scenario,
            answer,
            history
        )

        history.append({
            "scenario": scenario,
            "answer": answer
        })

        agent3 = EvidenceAgent()
        evidence = agent3.extract(
            scenario,
            answer
        )

        print("\nEvidence:")
        print(evidence)

        if not result["need_followup"]:
            break

        scenario["question"] = result["followup_question"]
        print("\n追问:")
        print(scenario["question"])


    agent4 = ReasoningAgent()
    risk = agent4.reason(
        evidence
    )

    print("\n风险推理:")
    print(risk)


if __name__ == "__main__":
    main()
