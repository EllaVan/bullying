import json

class KnowledgeBase:
    def __init__(self, data_path="data"):
        self.data_path=data_path
        self.mapping=self.load(f"{data_path}/variable_mapping.json")
        self.questions=self.load(f"{data_path}/questionnaire_library.json")

    def load(self,path):
        with open(path,encoding="utf-8") as f:
            return json.load(f)
