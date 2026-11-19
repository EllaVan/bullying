class InterviewAgent:
    def chat(self,scenario):
        conversation=[]
        for q in scenario.get("questions",[]):
            conversation.append({"speaker":"agent","text":q})
            ans=input(q+"\n学生:")
            conversation.append({"speaker":"student","text":ans})
        return conversation
