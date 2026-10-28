"""只整理既有逐目标难度来源，不采用标签或触发分析。"""
import json
from collections import Counter
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read

TARGET=OUT/'admitted_space_extension/difficulty_evidence'
BASE=ROOT/'analysis_results/image_difficulty_full_review_20261010'
GRADES={'简单','中等','困难'}


def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    pools=read(OUT/'admitted_space_extension/pools/INPUT_SNAPSHOT.json')['images']
    current={r['image']:r for r in read(OUT/'difficulty_records.json')['records']}
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    oldrefs={r['target_id']:r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    external={r['image']:r for r in read(BASE/'external_review_20261010/source_review.json')['records']}
    user={r['image']:r for r in read(BASE/'user_review_20261010/source_review.json')['records']}
    later={r['image']:r for r in read(ROOT/'research/difficulty/difficulty_review_update_20261015/user_review_receipt.json')['records']}
    visual={r['image']:r for r in read(BASE/'review_data.json')}
    rows=[]; chain=[]
    for p in pools:
        m=p['meta'];image=m['image'];tid=m['reference_id'];c=current[image];ext=external.get(image,{});u=user.get(image,{});l=later.get(image,{})
        v=visual.get(image,{});view=v.get('visual',{});exact=ext.get('gt_object_id')==tid
        assistant_exact=v.get('gt_object_id')==tid
        adopted=c.get('user_grade_adopted') and (c.get('latest_user_review') or {}).get('target_version')==tid and c['current_class'] in GRADES
        has_grade=(exact and ext.get('grade') in GRADES) or (assistant_exact and view.get('difficulty_recommendation') in GRADES)
        status='已确认且可继承' if adopted else '曾标需核查' if has_grade else '确实缺失_所查难度回执中'
        reason='当前明确采用回执与目标一致' if adopted else '第三方意见未获该旧目标最终采用' if exact else '有该目标Codex视觉建议，非研究者最终裁定' if assistant_exact else '现存分级指向另一目标，不能移用'
        if exact and ext.get('scope')!='目标基本一致':reason+='；旧审核另有范围或GT疑点'
        if u.get('gt_object_id')==tid and u.get('scope')=='范围明显不同':reason+='；后续用户针对不同范围评分，旧目标等级未确认'
        if l and l.get('target_version')!=tid:reason+='；10月15日人工采用属于另一目标'
        if image=='wc2JMjhGNzB-26':reason+='；历史审核是8点对导出GT，本池是6点对MP3D GT，非别名'
        old=oldrefs.get(tid,{})
        rows.append(dict(pool_id=p['pool_id'],image=image,condition=m['condition'],target_id=tid,pool_n=m['pool_n'],status=status,reason=reason,
            external_grade=ext.get('grade') if exact else None,external_scope=ext.get('scope') if exact else None,external_exact_target=exact,
            assistant_grade=view.get('difficulty_recommendation') if assistant_exact else None,assistant_needs_review=view.get('needs_user_review') if assistant_exact else None,
            user_1010_grade=u.get('grade') if u.get('gt_object_id')==tid else None,user_1010_scope=u.get('scope') if u.get('gt_object_id')==tid else None,
            user_1015_grade=l.get('grade'),user_1015_target=l.get('target_version'),user_1015_exact_target=l.get('target_version')==tid,
            current_reference_pairs=len(refs[tid].get('points_1024x512') or [])//2,
            historical_review_reference_pairs=len(refs.get(ext.get('gt_object_id'),{}).get('points_1024x512') or [])//2,
            current_target=c['target_version'],current_grade=c['current_class'],current_target_is_different=c['target_version']!=tid,
            full_reference_same_as_v2=bool(old and old.get('points_1024x512')==refs[tid].get('points_1024x512')),
            adopted_by_this_audit=False))
        chain.append(dict(pool_id=p['pool_id'],target_id=tid,external_review=ext,user_review_1010=u,user_review_1015=l,
            visual_review={k:view.get(k) for k in ['gt_object_id','reviewer_type','difficulty_recommendation','gt_target_confidence','visible_evidence','uncertainty_reason','needs_user_review']},
            current_selection_reason=c.get('selection_reason'),current_basis=c.get('classification_basis'),latest_user_review=c.get('latest_user_review')))
    frame=pd.DataFrame(rows);frame.to_csv(TARGET/'POOL_EVIDENCE.csv',index=False,encoding='utf-8-sig')
    targets=[]
    for tid,g in frame.groupby('target_id',sort=False):
        assert g.status.nunique()==1
        row=g.iloc[0].to_dict();row['pool_ids']='|'.join(g.pool_id);row['conditions']='|'.join(g.condition);row['records']=int(g.pool_n.sum())
        row['review_action']='确认已有意见是否适用于该目标' if row['status']=='曾标需核查' else '补该目标等级；不移用另一目标标签' if row['status'].startswith('确实缺失') else '仅登记可继承来源，不在本轮采用'
        targets.append(row)
    target=pd.DataFrame(targets);target.to_csv(TARGET/'MINIMAL_TARGET_REVIEW.csv',index=False,encoding='utf-8-sig')
    assert len(frame)==31 and len(target)==30 and int(frame.external_exact_target.sum())==23
    wc=frame[frame.image.eq('wc2JMjhGNzB-26')].iloc[0]
    assert wc.current_reference_pairs==6 and wc.historical_review_reference_pairs==8 and not wc.external_exact_target
    assert not frame.user_1015_exact_target.any() and not frame.adopted_by_this_audit.any()
    checks=dict(pools=len(frame),targets=len(target),images=int(frame.image.nunique()),pool_status=dict(Counter(frame.status)),target_status=dict(Counter(target.status)),exact_external_pool_matches=int(frame.external_exact_target.sum()),formal_labels_changed=False,eligibility_changed=False,downstream_recomputed=False)
    for name,data in [('EVIDENCE_CHAIN.json',chain),('CHECKS.json',checks)]:
        (TARGET/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(checks)


if __name__=='__main__':main()
