class RiskAgent:
    def predict(self,profile):
        pv=lambda x:profile.get(x,{"value":0.5})["value"]
        return {
        "risk_assessment":{
        "bully_risk":{"score":0.3*pv("PV02")+0.2*pv("PV06")},
        "victim_risk":{"score":0.4*pv("PV09")+0.2*(1-pv("PV08"))},
        "bystander_risk":{"score":0.4*pv("PV07")+0.3*pv("PV05")}
        }}
