"""Publish only the authorized pa4-11 grade revision, preserving frozen evidence."""
import copy
import json
from collections import Counter
import pandas as pd
from .current_annotation_context_20261017 import ROOT

OUT=ROOT/'research/difficulty/difficulty_user_revision_20261028'
OLD=ROOT/'research/difficulty/difficulty_user_revision_20261018'
IID='pa4otMbVnkk_4fbdfc08c934474ea9a04977f9081d0e'


def write(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    old=json.loads((OLD/'current_261.json').read_text(encoding='utf-8'))
    before=next(r for r in old['records'] if r['image_id']==IID)
    assert before['current_class']=='简单'
    receipt=dict(version='difficulty_user_revision_20261028',status='user_confirmed',date='2026-10-28',user_statement='pa4otMbVnkk-11改为中等，其他难度不变',records=[dict(image='pa4otMbVnkk-11',image_id=IID,old_class='简单',new_class='中等',target_version_unchanged=before['target_version'])])
    write('RECEIPT.json',receipt)
    for name in ['current_259.json','current_261.json']:
        data=json.loads((OLD/name).read_text(encoding='utf-8'));original=copy.deepcopy(data)
        for r in data['records']:
            if r['image_id']==IID:r.update(current_class='中等',conditional_difficulty='中等')
        changed=[r['image_id'] for r,o in zip(data['records'],original['records']) if r!=o]
        assert changed==[IID]
        data['version']=receipt['version']
        if 'summary' in data:
            data['previous_version_summary']=data['summary']
            data['summary']=dict(version=receipt['version'],reviewed=len(data['records']),counts=dict(Counter(r['current_class'] for r in data['records'])),changed_in_this_version=1)
        write(name,data)
    for name in ['current_259.csv','analysis_eligible.csv']:
        d=pd.read_csv(OLD/name);mask=d.image_id.eq(IID);assert mask.sum()==1
        d.loc[mask,['current_class','conditional_difficulty']]='中等';d.to_csv(OUT/name,index=False,encoding='utf-8')
    pointerpath=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
    pointer=json.loads(pointerpath.read_text(encoding='utf-8'))
    if not (OUT/'previous_pointer.json').exists():write('previous_pointer.json',pointer)
    pointer.update(version=receipt['version'],**{k:str(v).replace('difficulty_user_revision_20261018','difficulty_user_revision_20261028') for k,v in pointer.items() if k in ['table','details','review','analysis_table']},
        context_details='research/difficulty/difficulty_user_revision_20261028/current_261.json',
        override_receipts=['research/difficulty/difficulty_user_revision_20261018/RECEIPT.json','research/difficulty/difficulty_user_revision_20261028/RECEIPT.json'],status='用户确认pa4-11中等，其余标签不变；冻结历史统计不追改')
    pointerpath.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8')
    from .build_research_workbench_20261017 import OUT as DISPLAY, write as write_display
    index=json.loads((DISPLAY/'index.json').read_text(encoding='utf-8'))
    item=next(r for r in index['images'] if r['image_id']==IID)
    detailpath=DISPLAY/item['detail']
    detail=json.loads(detailpath.read_text(encoding='utf-8'))
    assert detail['image_id']==IID
    for r in [item,detail]:
        assert r['difficulty']['label'] in ('简单','中等')
        r['difficulty']['label']='中等';r['scene']['conditional_difficulty']='中等'
        note='2026-10-28用户确认pa4-11中等；历史统计保持原版本。'
        if note not in r['notes']:r['notes'].append(note)
    write_display(detailpath,detail);write_display(DISPLAY/'index.json',index)
    write('CHECKS.json',dict(changed_image_ids=[IID],other_records_unchanged=True,reference_and_eligibility_unchanged=True,historical_scores_modified=False))
    print('Published one-image revision:',IID)


if __name__=='__main__':main()
