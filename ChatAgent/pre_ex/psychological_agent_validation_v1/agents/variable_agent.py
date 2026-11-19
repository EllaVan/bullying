class VariableAgent:
    def estimate(self,questionnaire_profile,evidence_profile,history_profile):
        result={}
        for source in [questionnaire_profile,evidence_profile,history_profile]:
            for k,v in source.items():
                value=v.get("score",v.get("value",0.5)) if isinstance(v,dict) else v
                result[k]={"value":value,"confidence":0.8}
        return {"psychological_profile":result}
