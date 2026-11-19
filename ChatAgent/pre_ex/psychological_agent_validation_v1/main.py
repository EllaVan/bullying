from agents.scenario_agent import ScenarioAgent
from agents.interview_agent import InterviewAgent
from agents.evidence_agent import EvidenceAgent
from agents.variable_agent import VariableAgent
from agents.risk_agent import RiskAgent

class PsychologicalAgentPipeline:
    def __init__(self):
        self.scenario_agent=ScenarioAgent()
        self.interview_agent=InterviewAgent()
        self.evidence_agent=EvidenceAgent()
        self.variable_agent=VariableAgent()
        self.risk_agent=RiskAgent()

    def run(self):
        scenario=self.scenario_agent.generate(["PV02","PV03"])
        conversation=self.interview_agent.chat(scenario)
        evidence=self.evidence_agent.extract(conversation)
        profile=self.variable_agent.estimate({}, {}, {})
        return self.risk_agent.predict(profile)

if __name__=="__main__":
    print(PsychologicalAgentPipeline().run())
