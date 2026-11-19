
from models.scoring import build_profile,calculate_risk

evidence=[
{"variable":"PV02","value":"high"},
{"variable":"PV07","value":"high"},
{"variable":"PV09","value":"medium"}
]

profile=build_profile(evidence)

print("心理变量画像:")
print(profile)

print("风险:")
print(calculate_risk(profile))
