import os
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

from agents.pipeline import scenario, interview, evidence, reasoning

s=scenario()
print("情景:")
print(s)

a=input("回答:")
i=interview(s,a)

e=evidence(s,a)

print("Evidence:")
print(e)

r=reasoning(e)

print("Risk:")
print(r)
