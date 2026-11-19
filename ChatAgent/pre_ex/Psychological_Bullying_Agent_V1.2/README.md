
# Psychological Bullying Agent V1.2

完整量表驱动版校园欺凌心理Agent原型。

目标：
基于心理变量(PV01-PV10)、量表题目、Evidence库和情景库，
实现：

量表维度
 -> Agent1情景生成
 -> Agent2心理访谈
 -> Agent3 Evidence抽取
 -> 心理变量融合
 -> Agent4风险推理
 -> 心理画像输出


## 运行

python -m venv venv

pip install -r requirements.txt

复制.env.example为.env，填写OPENAI_API_KEY

python main.py


## 当前版本特点

1. 完整心理变量配置
2. 量表题目结构化保存
3. Evidence标准库
4. S01-S06多情景循环测评
5. 心理画像JSON输出


当前不包含：
- 数据库
- 前端
- 用户系统
- 机器学习模型

用于Agent功能验证。
