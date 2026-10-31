"""Apply explicit visual decisions; proximity never automatically excludes an answer."""
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030'
OUT=BASE/'similarity_review_20261031'

def read(path):return json.loads(path.read_text(encoding='utf8'))
def write(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    candidates=read(OUT/'CANDIDATES.json');visual=read(OUT/'VISUAL_DECISIONS.json')
    selected=read(OUT/'VISUAL_SELECTION.json');assert set(map(int,visual))==set(selected)
    previous=read(BASE/'scope_recheck40_20261031/EFFECTIVE_SCREENING_LEDGER.json')['records']
    byid={r['object_id']:r for r in previous}
    original={r['object_id']:r for r in read(BASE/'pro_delivery_independent_audit_20261031/CORRECTED_RECORD_LEDGER.json')}
    explicit={}
    for batch in ['scope_recheck_20261031','scope_recheck40_20261031']:
        explicit.update(read(BASE/batch/'ADOPTED_USER_REVIEW.json')['decisions'])
    holds={r['object_id'] for r in read(BASE/'pro_delivery_independent_audit_20261031/INDEPENDENT_HOLDS_13.json')}
    excluded=[];reviews=[]
    for index in selected:
        c=candidates[index];v=visual[str(index)];oid=c['object_id'];old=byid[oid]
        assert old['eligibility']=='保留' and oid not in explicit and not original[oid]['protected_adjudication']
        assert byid[c['reject_id']]['eligibility']=='排除'
        review=dict(c,**v,review_source='agent_original_panorama_and_original_pairs',scope_unchanged=old['scope']==v.get('scope',old['scope']),ring_unchanged=True,individual_quality_not_used=True,
                    evidence_file=f'original_annotation_check_{selected.index(index)//4}.jpg',evidence_row=selected.index(index)%4+1)
        reviews.append(review)
        if 'scope' in v:
            old.update(scope=v['scope'],decision_source=v['source'])
        if v['decision']=='排除':
            excluded.append(review)
            old.update(eligibility='排除',decision_source='agent_visual_similarity_20261031',exclusion_reason=v['reason'],excluded_template_id=c['reject_id'])
    assert len(excluded)==9 and len(reviews)==33
    for oid,r in explicit.items():assert byid[oid]['eligibility']==r['eligibility'] and byid[oid]['scope']==r['scope']
    assert sum(r['eligibility']=='排除' for r in previous)==60
    assert sum(r['eligibility']=='保留' for r in previous)==524
    write('VISUAL_REVIEW_RECORDS.json',reviews)
    write('ADOPTED_EXCLUSIONS.json',dict(schema='doorway_similar_exclusion_v1',authorization='用户要求按照已排除作答寻找相似作答并再次排除，随后截图澄清单侧保留与局部碎片排除',records=excluded,counts=dict(base=584,previous_excluded=51,new_excluded=9,excluded=60,retained=524),quality_results_used_to_choose_records=False,review_performed_after_533_aggregate_result=True))
    write('EFFECTIVE_SCREENING_LEDGER.json',dict(schema='doorway_screening_after_similarity_v1',calculation_status='not_recomputed_after_similarity_review',records=previous))
    write('CHECKS.json',dict(reviewed=33,new_excluded=9,retained_reviewed=24,base=584,excluded=60,retained=524,explicit_user_decisions_unchanged=len(explicit),new_user_scope_confirmations=4,historical_13_overlap_with_new_exclusions=sorted(holds.intersection(r['object_id'] for r in excluded)),retained_historical_holds=sum(r['object_id'] in holds and r['eligibility']=='保留' for r in previous),new_by_image=dict(Counter(r['image'] for r in excluded))))
    print(read(OUT/'CHECKS.json'))

if __name__=='__main__':main()
