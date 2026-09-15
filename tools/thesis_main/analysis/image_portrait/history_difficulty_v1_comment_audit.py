"""Audit original comments for explicit prior-outcome references.

Flags are conservative literal-text screens, not judgments about what a user
actually saw. Absence of a trigger is not proof of outcome blinding.
"""
import hashlib,html,json,re
import pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import OUT,js,csv


def run():
    tags=pd.read_csv(OUT/'expert/verified_nonempty_comments.csv',keep_default_na=False)
    outcome=r'历史|形成了|稳定\s*[一二两三四五六七八九十0-9]+\s*簇|semi标的不好'
    number=r'\d+\s*人'
    text=tags.actual_image_comment+' '+tags.group_comment
    tags['explicit_prior_outcome_reference']=text.str.contains(outcome,case=False,regex=True)
    tags['explicit_person_count_reference']=text.str.contains(number,regex=True)
    tags['blinding_status']=tags.explicit_prior_outcome_reference.map({True:'comment_refers_to_prior_responses_or_stable_modes',False:'not_proven_blinded_by_absence_of_comment'})
    csv('expert/comment_outcome_reference_audit.csv',tags)
    data=dict(tag_images=len(tags),tag_images_with_explicit_prior_outcome_reference=int(tags.explicit_prior_outcome_reference.sum()),distinct_groups_with_explicit_prior_outcome_reference=tags.loc[tags.explicit_prior_outcome_reference,'display_group'].nunique(),tag_images_with_person_count_reference=int(tags.explicit_person_count_reference.sum()),screening_regex=outcome,annotation='Literal source-text flag. No trigger does not establish blindness. Tags remain separate independent variables, not an independently blinded validation set.',effect_on_historical_tier_and_prediction='none; no expert tag/comment was used to generate historical tiers or image features')
    js('expert/COMMENT_OUTCOME_AUDIT.json',data)
    note='''## 补充来源审计：独立保存不等于历史结果盲评\n\n106张用户tag中，'''+str(data['tag_images_with_explicit_prior_outcome_reference'])+'张的逐图或组级原评论明确引用历史作答、稳定簇或Semi表现，涉及'+str(data['distinct_groups_with_explicit_prior_outcome_reference'])+'个展示组；另有'+str(data['tag_images_with_person_count_reference'])+'''张带人员数字的评论。人数文字可能是计划，不自动解释成已经观察的结果。\n\n例如G027的“这是形成了稳定2簇”、G109的“这图semi标的不好”，以及VFua案例的“这张图历史的分歧都有点大”，都不能一概包装成看图前的盲评预期。G002的“这个视角下难标”则是具体的视角判断线索，但仅凭文字没有历史词也不能证明盲评。\n\n因此本文的“独立对照”仅表示**独立来源/字段保存，不互相重写或用于拟合**，不表示两套判断在统计上独立、或用户对历史作答全程盲化。标签一致不能作为独立验证成功；不一致也不证明用户标签错误。进一步对照应分别展示明确历史知情、含计划人数、以及盲化状态未知的记录。\n\n原评论和逐图触发保存在`expert/comment_outcome_reference_audit.csv`。本项只改变解释，不改变任何历史粗类、预测输入、参数或结果。\n'''
    (OUT/'COMMENT_EVIDENCE_NOTE_ZH.md').write_text(note,encoding='utf-8')
    p=OUT/'REPORT_ZH.md';body=p.read_text(encoding='utf-8');marker='## 补充来源审计：独立保存不等于历史结果盲评'
    if marker not in body:
        js('execution/PRE_COMMENT_REPORT_VERSION.json',dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),reason='Append source interpretation audit, no numerical outcome changes'))
        p.write_text(body+'\n'+note,encoding='utf-8')
        h=OUT/'REPORT_ZH.html';text=h.read_text(encoding='utf-8');import markdown
        h.write_text(text.replace('</body>',markdown.markdown(note,extensions=['tables'])+'</body>'),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':run()
