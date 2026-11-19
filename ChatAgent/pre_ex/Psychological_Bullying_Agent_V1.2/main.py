import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

from agents import Agent1Scenario,Agent2Interview,Agent3Evidence,Agent4Reasoning

scenarios=[
["PV01","PV07"],
["PV02","PV05"],
["PV04","PV09"]
]

all_evidence=[]

for target in scenarios:

    s=Agent1Scenario().run(target)

    print("\n情景:")
    print(s)

    answer=input("回答:")

    follow=Agent2Interview().run(s,answer)

    if follow.get("need_followup"):
        print("追问:",follow.get("question"))

    e=Agent3Evidence().run(s,answer)

    all_evidence.append(e)

result=Agent4Reasoning().run(
    {"evidence":all_evidence}
)

print("\n心理画像与风险:")
print(result)
