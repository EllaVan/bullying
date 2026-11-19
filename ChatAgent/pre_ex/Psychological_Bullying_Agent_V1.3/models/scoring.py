
def build_profile(evidence):
    profile={f"PV{i:02d}":0.0 for i in range(1,11)}

    mapping={"low":0.2,"medium":0.5,"high":0.8}

    for e in evidence:
        vars=e["variable"]
        if isinstance(vars,str):
            vars=[vars]
        for v in vars:
            profile[v]=max(profile[v],mapping.get(e.get("value"),0.5))

    return profile


def calculate_risk(profile):
    return {
        "bully_risk":round((profile["PV02"]+profile["PV05"]+profile["PV06"])/3,2),
        "victim_risk":round((profile["PV09"]+(1-profile["PV08"]))/2,2),
        "bystander_risk":round((profile["PV07"]+profile["PV05"])/2,2),
        "bully_victim_risk":round((profile["PV02"]+profile["PV09"])/2,2)
    }
