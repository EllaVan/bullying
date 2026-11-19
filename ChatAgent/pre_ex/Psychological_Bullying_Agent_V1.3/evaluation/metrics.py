
def evidence_precision(pred,gold):
    return len(set(pred)&set(gold))/max(len(pred),1)

def evidence_recall(pred,gold):
    return len(set(pred)&set(gold))/max(len(gold),1)


def report(metrics):
    return {
        "evaluation_cases":len(metrics),
        "purpose":"评价Evidence抽取一致性"
    }
