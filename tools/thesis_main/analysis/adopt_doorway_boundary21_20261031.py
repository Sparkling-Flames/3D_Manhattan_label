"""Adopt the returned boundary decisions and count distinct workers per image."""
import copy
import json
from collections import Counter
from tools.thesis_main.analysis.adopt_doorway_expanded_review_20261031 import BASE, OUT, read, write


def main():
    received=read(OUT/'USER_REVIEW_RECEIVED.json')
    expected={r['object_id']:r for r in read(OUT/'PENDING_USER_REVIEW.json')}
    assert received['schema']=='doorway-expanded-boundary21-20261031-v1'
    assert set(received['decisions'])==set(expected) and len(expected)==21
    prior=read(OUT/'EFFECTIVE_SCREENING_LEDGER.json')['records']
    records=copy.deepcopy(prior); byid={r['object_id']:r for r in records}
    changes=[]
    for oid,r in received['decisions'].items():
        for field in ['object_id','image','worker','previous_scope','points','spaces']:
            assert r[field]==expected[oid][field],(oid,field)
        assert r['scope'] in ['空间1','空间2','全部','都不符合（看不懂）']
        assert r['eligibility'] in ['保留','排除','待定']
        old=byid[oid]; assert old['review_status']=='pending_user_review_preserve_prior'
        changes.append(dict(object_id=oid,image=r['image'],worker=r['worker'],before=copy.deepcopy(old),after_scope=r['scope'],after_eligibility=r['eligibility']))
        old.update(scope=r['scope'],eligibility=r['eligibility'],decision_source='user_boundary21_20261031',review_status='user_review_completed',user_review_updated_at=r['updated_at'],prior_boundary_record=copy.deepcopy(old))
    assert len(records)==len(byid)==584
    assert Counter(r['eligibility'] for r in received['decisions'].values())=={'保留':16,'排除':5}
    assert Counter(r['eligibility'] for r in records)=={'保留':439,'排除':145}
    # One answer per image/worker in this candidate panel; counts are people, not duplicate submissions.
    assert len({(r['image'],r['worker']) for r in records})==584
    holds={r['object_id'] for r in read(BASE/'pro_delivery_independent_audit_20261031/INDEPENDENT_HOLDS_13.json')}
    counts=[]
    for image in sorted({r['image'] for r in records}):
        group=[r for r in records if r['image']==image]
        kept=[r for r in group if r['eligibility']=='保留'];scopes=Counter(r['scope'] for r in kept)
        counts.append(dict(image=image,base_workers=len(group),retained_workers=len(kept),excluded_workers=sum(r['eligibility']=='排除' for r in group),pending_workers=sum(r['eligibility']=='待定' for r in group),space1=scopes['空间1'],space2=scopes['空间2'],whole=scopes['全部'],other_scope=len(kept)-scopes['空间1']-scopes['空间2']-scopes['全部'],retained_historical_holds=sum(r['object_id'] in holds for r in kept)))
    assert len(counts)==17 and sum(r['retained_workers'] for r in counts)==439
    write('FINAL_SCREENING_LEDGER.json',dict(schema='doorway_screening_after_boundary21_v1',calculation_status='not_recomputed_after_final_screening',records=records))
    write('ADOPTED_USER_REVIEW.json',dict(schema=received['schema'],decisions=received['decisions'],changes=changes,counts=dict(reviewed=21,kept=16,excluded=5,pending=0,base=584,final_retained=439,final_excluded=145)))
    unresolved=[{k:r[k] for k in ['object_id','image','worker','scope']} for r in records if r['eligibility']=='保留' and r['scope'] not in ['空间1','空间2','全部']]
    write('PER_IMAGE_COUNTS.json',dict(schema='doorway_per_image_workers_v1',population='17-image 584-candidate doorway panel; OOS and pending image q9-24 excluded',count_unit='distinct image-worker; one record per worker per image verified',records=counts,unassigned_scope_records=unresolved,retained_historical_holds=sum(r['retained_historical_holds'] for r in counts)))
    lines=['# 门洞逐图标注人数（最新21份人工裁决接入后）','','21份复核：16保留、5排除、0待定。基础候选584份，累计排除145份，保留439份。每张图内人员去重核对通过；不同图片的同一人可重复出现，因此439是作答份数，不能称为439名不同参与者。','','| 图片 | 筛前人数 | 筛后人数 | 累计排除 | 空间1 | 空间2 | 全部 | 其他/归属未定 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in counts:
        lines.append('| '+' | '.join(str(r[k]) for k in ['image','base_workers','retained_workers','excluded_workers','space1','space2','whole','other_scope'])+' |')
    lines+=['','筛前指已确定的584份门洞基础候选，不是原始708份库存。OOS图片和保持疑似的q9-24不混入本表。空间分类是互斥原答归属，不是允许“全部”参与单侧组队后的兼容池人数。',f'','439份中仍有'+str(sum(r['retained_historical_holds'] for r in counts))+'份保留历史资格标记；本表统计筛后标注人数，不据此解除其正式质量资格。原始点、环序、GT和切分未改。本表只记录筛选人数，曲线计算状态以当前结果入口为准。']
    lines+=['',f'另有{len(unresolved)}份保留记录沿用历史空空间归属，已在JSON逐条列出；计入保留总数，暂不强行归入空间1、空间2或全部。后续分空间计算须先核清这些归属。']
    (OUT/'PER_IMAGE_COUNTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(counts,ensure_ascii=True))


if __name__=='__main__':
    main()
