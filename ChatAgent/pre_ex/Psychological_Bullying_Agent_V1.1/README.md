
# Psychological_Bullying_Agent_V1.1

基于校园欺凌心理变量体系的LLM Agent测试项目。

核心链路：

情景生成Agent
 -> 心理访谈Agent
 -> Evidence抽取Agent
 -> 心理变量映射
 -> 风险推理Agent

本版本加入：
- PV01-PV10心理变量库
- 量表题目Evidence映射
- S01-S06情景库
- Evidence结构化输出
- 心理变量评分接口

运行：
1. pip install -r requirements.txt
2. 复制.env.example为.env
3. python main.py

