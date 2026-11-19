"""生成固定的合成开发回放。答案与证据为人工编写示例，不是LLM输出或评价金标准。

运行时A3不读取这里的答案表。此脚本只把这些已配对内容按测量控制器的任务顺序封装。
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.io_utils import write_json
from psych_agent.measurement_controller import MeasurementController

# 每条内容为明确编写的模拟回答及所选方向，不能用来推断任意新回答。
SAMPLES={
 'U_A01_RECOVERY':('平时我先走开缓一会儿，心情会慢慢平静，之后就能做别的事情。','higher'),
 'U_A02_ATTRIBUTION':('我还不能确定，也可能他没注意，我不会马上认定他是故意的。','lower'),
 'U_A02_RUMINATION':('平时如果我认定有人针对我，后来会反复想着那件事，过了很久还在想。','higher'),
 'U_A03_REVENGE':('我不希望他也受到伤害，我不打算报复他。','lower'),
 'U_A04_PAUSE':('我会先暂停，等自己平静一些再决定接下来怎么做。','higher'),
 'U_B01_EMOTION':('我会看看他的表情，再问问他是不是觉得不舒服，表面笑着也可能心里难受。','higher'),
 'U_B02_CONCERN':('虽然我平时不太喜欢他，但看到他被围着针对，我还是会觉得难受。','higher'),
 'U_B03_HARM':('我会注意他是不是勉强笑，也会问他是否愿意继续这种玩笑。','higher'),
 'U_B03_JUSTIFICATION':('只要对方不愿意或者已经难受，就应该停下来，不能用大家觉得好笑当理由。','lower'),
 'U_B04_RESPONSIBILITY':('每个人都应该对自己做的部分负责，人多也不会让个人责任变少。','lower'),
 'U_B05_CONSEQUENCES':('没有身体受伤也可能心里很难受，这样的影响不能因为没动手就忽略。','lower'),
 'U_C01_VOICE':('我非常在意自己的意见在朋友中有没有分量，希望大家认真考虑。','higher'),
 'U_C02_REFUSAL':('我可以接受朋友不采纳我的意见，他们也可以有自己的选择。','lower'),
 'U_C03_DETERRENCE':('我不认可通过让别人害怕我来维持关系。','lower'),
 'U_C04_DISSENT':('就算几个朋友意见一样，我也会平静说出自己不同的想法。','lower'),
 'U_C05_CONFORMITY':('即使担心被疏远，我也不会因为这个就跟着做自己不认可的事情。','lower'),
 'U_C05_REJECTION':('我会担心朋友因为这件事疏远我。','higher'),
 'U_D01_EXCLUSION':('我会担心下一次活动不再邀请我。','higher'),
 'U_D02_NO_RESPONSE':('可能他们暂时在忙，我不会马上觉得他们对我有意见。','lower'),
 'U_D03_PEER_SUPPORT':('平时我有一位可以放心说心事的同学。','higher'),
 'U_D04_REPAIR':('我觉得这次虽然有矛盾，我们之后还是能说开，关系可以修复。','higher'),
 'U_E01_CHANNEL':('我可以找信任的老师商量。','higher'),
 'U_E02_EXPRESSION':('老师，我想说明刚才同学之间发生的事情，请您听听大家的说法，帮忙一起理清楚。','higher'),
 'U_E03_BARRIER':('我担心告诉老师或家长以后，对方知道了会让事情更麻烦。','lower'),
 'U_E04_DEESCALATION':('我会先离开，让争执暂停，也让自己冷静下来，避免越来越激烈。','higher'),
 'U_E05_PROTECTION':('我会找老师来帮助那位同学，自己保持距离，不直接冲进推搡的人群。','higher'),
 'U_G01_FORCE':('我不赞成用推打来解决冲突，这可能使事情更糟。','lower'),
 'U_G02_VERBAL':('我不认可用伤人的尖锐话回击，这样不见得更有效。','lower'),
 'U_G03_ALLIANCE':('我希望朋友听我说说，但他们可以有不同意见，我不会强迫他们站队。','lower'),
 'U_G03_GROUP':('即使朋友们站在同一边，我也会先弄清事情，保留自己的判断。','lower')}


def observation(cfg, view, answer, direction):
    matches=[cfg.rules[r] for r in view['rule_ids'] if cfg.rules[r]['direction']==direction]
    return {'unit_id':view['unit_id'],'status':'covered','quote':answer,
            'reference_frame':view['reference_frame'],'subject':'self','context_turn_ids':[],
            'slots':[{'slot_id':s['slot_id'],'value':answer,'quote':answer} for s in view['required_slots']],
            'evidence':[{'rule_id':r['rule_id'],'quote':answer,'rationale':'合成开发示例：'+r['criterion']} for r in matches],
            'reason':'预先编写的开发输入，明确提供了此单元要求的信息。'}


def build():
    cfg=load_dialogue_config(ROOT)
    for pid in cfg.plans:
        c=MeasurementController(cfg,pid,'DEMO_'+pid.upper(),synthetic=True)
        rows=[]
        while True:
            action=c.next_action()
            if action['kind']=='done':
                break
            if action['kind']=='scenario':
                task=action['task']
                c.set_scenario({'text':task['template_text'],'facts':task['facts']})
                continue
            task=action['task']
            views={u['unit_id']:u for u in task['allowed_units']}
            background=[]
            if task['target_unit_id']:
                uid=task['target_unit_id']
                answer,direction=SAMPLES[uid]
                observations=[observation(cfg,views[uid],answer,direction)]
            elif task['scenario_id']=='S01':
                answer='我会先离开，让争执暂停，等自己冷静再决定，然后找老师商量。家里也有人愿意听我说学校的事。'
                quote='我会先离开，让争执暂停，等自己冷静再决定，然后找老师商量。'
                observations=[observation(cfg,views[uid],quote,'higher') for uid in ('U_A04_PAUSE','U_E01_CHANNEL','U_E04_DEESCALATION') if uid in views]
                background=[{'item_id':'F01','quote':'家里也有人愿意听我说学校的事。','description':'合成样例中的家庭倾听背景。',
                             'reference_frame':'habitual_self_report','subject':'self'}]
            else:
                answer='我想先看看发生了什么，再想接下来怎么做。'
                observations=[]
            result={'turn_id':task['turn_id'],'observations':observations,'background':background}
            c.record_question({'question':task['question_template']})
            c.record_answer(answer)
            c.commit(result)
            rows.append({'expected_task':{k:task[k] for k in ('scenario_id','condition_id','target_unit_id','mode')},
                         'question':task['question_template'],'answer':answer,'result':result})
        references=[]
        for entry in cfg.plans[pid]['entries']:
            reference={'scenario_id':entry['scenario_id'],'condition_id':entry['condition_id']}
            if reference not in references:
                references.append(reference)
        write_json(ROOT/'fixtures/dialogue'/f'{pid}.json',{'schema_version':'0.4.0','config_set_id':cfg.config_set_id,
                    'synthetic':True,'plan_id':pid,'not_evaluation_gold':True,
                    'scenario_references':references,'turns':rows})
        print(f'{pid}: {len(rows)}轮固定问答')


if __name__=='__main__':
    build()
