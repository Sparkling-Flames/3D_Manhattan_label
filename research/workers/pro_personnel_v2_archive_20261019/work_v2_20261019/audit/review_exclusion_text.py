#!/usr/bin/env python3
"""Transparent coding of existing exclusion text; never a new severity gold.

All 25 source records were read. The one explicit ambiguity exception is listed
by stable object ID. No geometry, eligibility, personnel class, or penalty is
modified. Latest adopted decision text is kept alongside earlier conditions.
"""
from pathlib import Path
from collections import Counter
import json
import pandas as pd
HERE=Path(__file__).resolve().parent

def main():
    source=json.loads((HERE/'PERSONAL_EXCLUSION_EVIDENCE_25.json').read_text());rows=[]
    for r in source:
        a=r['exclusion_attribution'];c=a['candidate_evidence'];code=c['reason_code'];oid=r['object_id']
        if oid=='f21c670566821ce7':
            state='scope_context_attribution_pending'
            why='现存历史意见含OOS与仅三对点，当前决定说明为空；保留剔除事实，暂不独立认定为适用任务下的个人严重错误。'
        elif code=='specific_personal_gross_deformation':
            state='explicit_reviewer_gross_deviation_not_calibrated_severity'
            why='保留人工明确偏离陈述；没有统一幅度阈值及新的独立severity裁定。'
        else:
            state='specific_defect_explicit_in_retained_review_text'
            why='现有最新逐条意见指向缺配对、点数不足或错误特征；仅核对文本来源，不声称本轮已视觉重审全部。'
        if r['image_code']=='rPc6DW4iMge-09':why+=' 当前决定明确直接排除，早期补点条件意见保留为历史，不覆盖较新的决定。'
        rows.append({'object_id':oid,'worker_id':r['worker_id'],'image_code':r['image_code'],'condition':r['condition'],
            'cleaning_disposition':r['cleaning_disposition'],'published_candidate_category':code,
            'legacy_explicit_person_error':a['legacy_explicit_person_error'],
            'latest_adopted_comment':c.get('current_decision_comment') or '',
            'unique_history_comments':json.dumps(list(dict.fromkeys(z.get('record',{}).get('comment') or '' for z in r['review_evidence'].get('review_history',[]))),ensure_ascii=False),
            'image_context':c.get('image_comment'),'independent_text_review_state':state,'interpretation_zh':why,
            'new_severe_error_gold':None,'population_exclusion_rate_identified':False,'used_in_Q_training_or_total_penalty':False})
    d=pd.DataFrame(rows);d.to_csv(HERE/'exclusion_text_review_25.csv',index=False)
    result={'scope':'Review of 25 candidate-record text/provenance, not a new visual severity audit. Frozen cleaning and quality eligibility unchanged. No change to registered personnel classes or selection.',
        'counts':dict(Counter(x['independent_text_review_state'] for x in rows)),'workers':d.worker_id.nunique(),
        'legacy_flags':int(d.legacy_explicit_person_error.sum()),'new_adjudicated_severe_count':None,
        'scope_pending_object':'f21c670566821ce7','reason_code_counts':dict(Counter(x['published_candidate_category'] for x in rows))}
    (HERE/'EXCLUSION_TEXT_REVIEW_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
