"""Prepare provenance and eligibility only; never run fusion or adopt automatic scope."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/doorway_review_20261030/curve_preparation_v21'
BASE=OUT.parent/'first_review_audit'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    data=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])
    original=json.loads((OUT.parent/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])
    machine_cuts={c['image_id']:c['cuts'] for c in original['cases']}
    review=read(OUT/'USER_REVIEW_FINAL_RECEIVED.json')
    inventory=read(ROOT/'research/data/releases/v2.1/quality_inventory.json')
    inv={r['object_id']:r for r in inventory}
    assert review['schema']=='doorway_review_v2'
    assert set(review['cases'])=={c['image_id'] for c in data['cases']}
    rows=[];images=[]
    for c in data['cases']:
        u=review['cases'][c['image_id']]
        assert (u['reference_id'],u['reference_version'])==(c['reference_id'],c['reference_version'])
        assert set(u['answers'])<={r['id'] for r in c['records']}
        oos=c['image'] in ['pRbA3pwrgk9-01','pRbA3pwrgk9-11']
        pending=c['image']=='q9vSo1VnCiC-24'
        images.append(dict(image=c['image'],image_id=c['image_id'],doorway_status='user_pending' if pending else c['status'],oos_excluded=oos,
            cuts=u['cuts'],parent_reference_id=c['reference_id'],parent_reference_version=c['reference_version'],
            target_reference_status='draft_floor_split_not_full_layout_adopted',
            special_note='勉强可标' if c['image']=='jtcxE69GiFV-12' else ''))
        for r in c['records']:
            v=inv[r['id']];a=u['answers'].get(r['id']);label=a['label'] if a else None
            if label:assert label in ['空间1','空间2','全部','都不符合（看不懂）']
            assert isinstance(v['pool_analysis_eligible'],bool)
            stale=bool(a and a['cuts']!=u['cuts'])
            reaffirmed=stale and c['image']=='B6ByNegPMKs-42' and r['worker'] in ['W034','W037','W118','W121','W107']
            machine=c['first_review'][r['id']]['machine_scope']
            automatic={'space1':'空间1','space2':'空间2','both':'全部'}.get(machine)
            auto_boundary_current=c['cuts']==u['cuts']
            adopted=label if a and (not stale or reaffirmed) else automatic if not a and auto_boundary_current else None
            adoption='user_reaffirmed' if reaffirmed else 'user_review' if a and not stale else 'automatic_provisional' if adopted else 'unresolved'
            blockers=[]
            if pending:blockers.append('user_pending_image')
            elif oos or v['is_oos']:blockers.append('oos_separate')
            if not v['pool_analysis_eligible']:blockers.append('inherited_pool_exclusion')
            if not r['points']:blockers.append('paired_geometry_unavailable')
            base_ok=not blockers
            rows.append(dict(object_id=r['id'],image=c['image'],image_id=c['image_id'],worker=r['worker'],condition=v['condition'],
                cleaning_disposition=v['cleaning_disposition'],inherited_pool_eligible=v['pool_analysis_eligible'],
                inherited_quality_eligible=v['current_quality_eligible'],inherited_quality_exclusion_reasons=v['quality_exclusion_reasons'],
                base_blockers=blockers,base_candidate=base_ok,user_label=label,user_label_stale=stale,
                user_updated_at=a.get('updated_at') if a else None,user_reaffirmed_current_cuts=reaffirmed,
                adopted_scope=adopted,machine_scope_candidate=machine,auto_boundary_current=auto_boundary_current,
                scope_adoption=adoption,first_reviewer_quality=c['first_review'][r['id']]['value'],
                all_answers_version_candidate=base_ok,
                screened_version_candidate=base_ok and adopted!='都不符合（看不懂）',
                ready_to_score=False,reference_id=c['reference_id'],reference_version=c['reference_version']))
    assert len(rows)==708 and len({r['object_id'] for r in rows})==708
    assert sum(r['user_label'] is not None for r in rows)==83
    assert sum(r['user_label_stale'] for r in rows)==5
    visual=read(OUT/'CONFLICT_VISUAL_DECISIONS.json')['records']
    adjudicated={r['object_id']:r for r in visual}
    assert len(adjudicated)==83
    for r in rows:
        r['pre_visual_scope']=r['adopted_scope']
        v=adjudicated.get(r['object_id'])
        if v:
            assert r['base_candidate'] and r['adopted_scope']==v['previous_scope']
            r['visual_review']=v
            if v['action']!='retain_user':
                r['adopted_scope']=v['adopted_scope']
                r['scope_adoption']='agent_visual_'+v['action']
        # Stored machine fractions bind to the initial cuts, not the first review's edited cuts.
        r['machine_cut_binding_current']=machine_cuts[r['image_id']]==review['cases'][r['image_id']]['cuts']
        if r['scope_adoption']=='automatic_provisional' and not r['machine_cut_binding_current']:
            r['adopted_scope']=None
            r['scope_adoption']='automatic_cut_stale'
        r['screened_version_candidate']=r['base_candidate'] and r['adopted_scope']!='都不符合（看不懂）'
    assert all(r['machine_cut_binding_current'] for r in rows if r['scope_adoption']=='automatic_provisional')
    assert sum(r['base_candidate'] and r['scope_adoption']=='automatic_cut_stale' for r in rows)==24
    assert sum(r['base_candidate'] and r['adopted_scope'] is None for r in rows)==85
    worker_audit=[]
    for worker in ['W019','W026']:
        records=[r for r in inventory if r['worker_id']==worker]
        assert all(r['cleaning_disposition']=='historical_not_accepted' and not r['pool_analysis_eligible'] for r in records)
        worker_audit.append(dict(worker=worker,inventory_records=len(records),all_excluded=True,
            doorway_records=[r for r in rows if r['worker']==worker]))
    summary=dict(inventory=708,images=20,user_labels=dict(Counter(r['user_label'] or '未审核' for r in rows)),
        oos_records=sum('oos_separate' in r['base_blockers'] for r in rows),
        pending_image_records=sum('user_pending_image' in r['base_blockers'] for r in rows),
        inherited_pool_exclusions=sum(not r['inherited_pool_eligible'] for r in rows),
        cleaning_status=dict(Counter(r['cleaning_disposition'] for r in rows)),
        base_candidates=sum(r['base_candidate'] for r in rows),
        adopted_scope_sources=dict(Counter(r['scope_adoption'] for r in rows if r['base_candidate'])),
        stale_review_records=sum(r['user_label_stale'] for r in rows),
        calculation_started=False,readiness='归属初判及冲突视觉复核已整理；未定归属单列，新目标完整参考尚待构建核验')
    write('RECORD_LEDGER.json',rows);write('IMAGE_TARGET_DRAFTS.json',images)
    write('WORKER_EXCLUSION_AUDIT.json',worker_audit)
    write('EXCLUDED_AND_PENDING.json',[r for r in rows if r['base_blockers']])
    write('AUTO_SCOPE_REVIEW_QUEUE.json',[r for r in rows if r['base_candidate'] and not r['user_label']])
    write('STALE_CUT_REVIEW.json',[r for r in rows if r['user_label_stale']])
    conflicts=[]
    for r in rows:
        if not r['base_candidate']:continue
        tags=[];first=r['first_reviewer_quality'];scope=r['pre_visual_scope']
        if first=='pass' and scope=='都不符合（看不懂）':tags.append('初审可用_用户看不懂')
        if first=='unsure' and scope in ['空间1','空间2','全部']:tags.append('初审无法判断_当前范围可辨')
        if first=='fix' and scope in ['空间1','空间2','全部']:tags.append('初审需修正_当前范围可辨_非直接矛盾')
        if r['user_label'] and {'space1':'空间1','space2':'空间2','both':'全部'}.get(r['machine_scope_candidate']) not in [None,r['user_label']]:tags.append('人工标签与程序初判不同')
        if tags:conflicts.append(dict(r,comparison_tags=tags))
    write('FIRST_REVIEW_COMPARISON.json',dict(note='pass/fix/unsure是质量判断，没有明确的二元排除字段；需修正不自动等于剔除。人工标签优先，自动归属保留来源。',
        counts=dict(Counter(tag for r in conflicts for tag in r['comparison_tags'])),records=conflicts))
    write('CHECKS.json',summary)
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
