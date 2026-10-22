"""Rebuild stable-object-ID manual coding of existing exclusion evidence.

The frozen interpretation is in review_reason_adjudications_v1.json. Evidence
hashes stop silent application of a code to changed comments. This does not
perform new visual adjudication or change source eligibility.
"""
import hashlib,json
from pathlib import Path
import pandas as pd
from paths import ROOT,REPO,OUT,STUDY

def main():
 objects=json.loads((OUT/'validated_annotations.json').read_text())
 excluded=[o for o in objects if o['cleaning_disposition']=='excluded_by_review']
 coding=json.loads((Path(__file__).resolve().parent/'review_reason_adjudications_v1.json').read_text())
 decisions={r['object_id']:r for r in coding['decisions']}
 assert len(excluded)==85 and {o['object_id'] for o in excluded}==set(decisions)
 records=[]
 for o in excluded:
  e=o['review_evidence'];d=decisions[o['object_id']]
  fields=[('review_evidence.current_decision_comment',e.get('current_decision_comment','')),('review_evidence.current_comment',e.get('current_comment',''))]
  fields += [(f"review_evidence.review_history[{j}].record.comment",x['record'].get('comment','')) for j,x in enumerate(e.get('review_history',[]))]
  comments=[]
  for field,text in fields:
   if text:
    old=next((x for x in comments if x['text']==text),None)
    if old:old['source_fields'].append(field)
    else:comments.append(dict(text=text,source_fields=[field]))
  evidence=dict(comments=[x['text'] for x in comments],image_comment=e.get('image_comment'))
  digest=hashlib.sha256(json.dumps(evidence,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
  assert digest==d['source_comment_sha256'],(o['object_id'],'manual coding evidence changed')
  records.append(dict(**{k:o[k] for k in ['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition']},
   reviewer_unacceptable=True,**{k:d[k] for k in ['reason_code','error_type','strict_specific_personal_severe','reviewer_personal_nonacceptance','gt_concern_context','policy_ambiguous','reason']},
   comments=comments,image_comment=e.get('image_comment'),source_verdict=e['verdict'],current_decision_comment=e.get('current_decision_comment'),coding_evidence_sha256=digest))
 (OUT/'exclusion_reason_coding.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
 df=pd.DataFrame(records);df['comments']=df.comments.map(lambda v:json.dumps(v,ensure_ascii=False))
 df.to_csv(OUT/'exclusion_reason_candidates.csv',index=False,encoding='utf-8-sig')
 print(df.reason_code.value_counts().to_string())
 print('strict',int(df.strict_specific_personal_severe.sum()),'broader',int(df.reviewer_personal_nonacceptance.sum()))

if __name__=='__main__':main()
