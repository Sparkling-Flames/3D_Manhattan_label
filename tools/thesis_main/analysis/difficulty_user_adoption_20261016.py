"""采用用户复核等级，保留旧判断和既有排除；不拟合机器阈值。"""
import copy
import csv
import json
import os
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/difficulty/difficulty_review_update_20261015'
OUT=ROOT/'research/difficulty/difficulty_user_adoption_20261016'
VERSION='scope_preferred_difficulty_user_adopted_20261016_v4'


def adopt(r):
    r['class_before_user_adoption']=r['current_class']
    r['evidence_before_user_adoption']=r['evidence']
    r['basis_before_user_adoption']=r['classification_basis']
    r['user_grade_adopted']=False
    v=r['latest_user_review']
    if not v or not v['grade']:return
    if v['image_id']!=r['image_id'] or v['target_version']!=r['target_version']:
        raise ValueError('review_target_mismatch')
    if r['gt_error_excluded']:return
    grade=v['grade']
    if grade=='认可建议':grade=v['proposed_class']
    if grade=='特殊场景需单独讨论':grade='单列'
    if grade not in {'简单','中等','困难','单列','待复核'}:raise ValueError('unknown_review_grade')
    r.update(current_class=grade,user_grade_adopted=True,
        classification_basis='user_review_adopted_20261016',
        evidence='按用户2026-10-16指示采用其复核等级；旧几何及视觉依据保留供解释，不据本次标签反推阈值。')
    if grade in {'简单','中等','困难'}:r['conditional_difficulty']=grade
    else:
        r['difficulty_analysis_eligible']=False
        r['difficulty_analysis_exclusion']=r['difficulty_analysis_exclusion'] or 'special_or_pending'


def main():
    base=json.loads((BASE/'current_259.json').read_text(encoding='utf-8'))
    rows=copy.deepcopy(base['records']);OUT.mkdir(exist_ok=True)
    migrations=json.loads((ROOT/'research/catalog/MIGRATION_MAP.json').read_text(encoding='utf-8'))['migrations']
    for r in rows:
        adopt(r)
        for k in ['card','old_card','scope_comparison']:
            if r.get(k):
                # v3图卡仍含迁移前相对路径，按登记映射定位，不修改历史快照。
                target=(BASE/r[k]).resolve()
                if not target.exists():
                    target=(ROOT/'research/difficulty_review_update_20261015'/r[k]).resolve()
                    for m in migrations:
                        old=ROOT/m['source_path']
                        if target.is_relative_to(old):
                            target=ROOT/m['current_path']/target.relative_to(old)
                            break
                assert target.exists(),(r['image'],k,target)
                r[k]=Path(os.path.relpath(target,OUT)).as_posix()
    assert len(rows)==259
    assert all(r['target_version']==old['target_version'] and r['selected']==old['selected'] for r,old in zip(rows,base['records']))
    assert all(not r['difficulty_analysis_eligible'] for r,old in zip(rows,base['records']) if not old['difficulty_analysis_eligible'])
    eligible=[r for r in rows if r['difficulty_analysis_eligible']]
    changes=[r for r in rows if r['current_class']!=r['class_before_user_adoption']]
    summary=dict(base['summary'],version=VERSION,counts=dict(Counter(r['current_class'] for r in rows)),
        analysis_counts=dict(Counter(r['current_class'] for r in eligible)),
        user_grades_adopted=sum(r['user_grade_adopted'] for r in rows),changed_in_this_version=len(changes),
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        new_visual_review_count=0,note='用户复核等级作为当前工作标签；未重看图、未改空间、未拟合阈值、既有排除不解除。')
    result=dict(version=VERSION,base_version=base['version'],summary=summary,records=rows)
    (OUT/'current_259.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    fields=['image','image_id','target_version','current_class','conditional_difficulty','class_before_user_adoption',
        'user_grade_adopted','classification_basis','N_turn','H','inference_burden','reference_status',
        'gt_error_excluded','difficulty_analysis_eligible','difficulty_analysis_exclusion','evidence','evidence_before_user_adoption']
    for name,records in [('current_259',rows),('analysis_eligible',eligible),('changes',changes),('excluded',[r for r in rows if not r['difficulty_analysis_eligible']])]:
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(records)
    page=(BASE/'review.html').read_text(encoding='utf-8');a=page.index('const DATA=')+len('const DATA=');b=page.index(';const rows=DATA.records',a)
    page=page[:a]+json.dumps(result,ensure_ascii=False).replace('</','<\\/')+page[b:]
    page=page.replace('<nav id="filters">','<p><b>v4：采用你的复核等级；GT错误、既有排除继续保留。原规则意见仅供对照，不代表新等级由机器自动产生。</b></p><nav id="filters">')
    page=page.replace('推断负担 ${esc(r.inference_burden)}','旧版推断负担记录 ${esc(r.inference_burden)}')
    page=page.replace('<b>我的判断：</b>${esc(r.evidence)}','<b>当前采用依据：</b>${esc(r.evidence)}</p><p>采用前等级：${esc(r.class_before_user_adoption)}；旧依据：${esc(r.evidence_before_user_adoption)}')
    (OUT/'review.html').write_text(page,encoding='utf-8')
    prefix='../../research/difficulty/difficulty_user_adoption_20261016/'
    pointer=dict(version=VERSION,table=prefix+'current_259.csv',details=prefix+'current_259.json',review=prefix+'review.html',
        analysis_table=prefix+'analysis_eligible.csv',status='user grades adopted; prior exclusions retained; historical quality summaries not regrouped')
    (ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
