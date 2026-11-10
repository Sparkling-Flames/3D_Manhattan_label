"""Summarize the replacement questionnaire; old responses are never read."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality/questionnaire_20261111'
RANK = {'poor': 0, 'medium': 1, 'good': 2}
def rho(a,b):
    ok=pd.DataFrame({'a':a,'b':b}).dropna()
    return float(spearmanr(ok.a,ok.b).statistic) if len(ok)>2 and ok.a.nunique()>1 and ok.b.nunique()>1 else None
def main():
    source=OUT/'问卷收集.json'
    answers=json.loads(source.read_text(encoding='utf-8-sig'))
    base=ROOT/'research/quality/validation_followup_20261107/human_review/returned_20261107'
    metrics=pd.read_csv(base/'ITEM_MEANS.csv')[['case_id','side','Q','D10','IoU','image','difficulty']]
    components=pd.read_csv(base/'DEFECT_COMPONENTS.csv')
    keys=set(metrics.case_id)
    rows=[]
    for reviewer,cases in answers.items():
        assert set(cases)==keys, (reviewer,'case coverage')
        for cid,a in cases.items():
            assert set(a['grades'])=={'left','right'}
            for side in ['left','right']:
                grade=a['grades'][side]; assert grade in {*RANK,'unknown'}
                ds=a['defects'][side]; assert isinstance(ds,list) and len(ds)==len(set(ds))
                rows.append(dict(reviewer=reviewer,case_id=cid,side=side,grade=grade,human=RANK.get(grade,np.nan),defects=json.dumps(ds),reason=a.get('reason','')))
    r=pd.DataFrame(rows).merge(metrics,on=['case_id','side'],validate='many_to_one')
    assert not r.duplicated(['reviewer','case_id','side']).any()
    valid=r.dropna(subset=['human'])
    items=r.groupby(['case_id','side']).agg(human=('human','mean'),raters=('human','count'),Q=('Q','first'),D10=('D10','first'),IoU=('IoU','first'),image=('image','first')).reset_index()
    pairs=[]
    for (rev,cid),g in r.groupby(['reviewer','case_id']):
        g=g.set_index('side')
        row=dict(reviewer=rev,case_id=cid,human_delta=g.loc['right','human']-g.loc['left','human'])
        for m in ['Q','IoU','D10']:row[m+'_delta']=g.loc['right',m]-g.loc['left',m]
        pairs.append(row)
    pairs=pd.DataFrame(pairs); complete=pairs.dropna(subset=['human_delta']);direction=complete[complete.human_delta!=0]
    imagepairs=complete.groupby('case_id').agg(human_delta=('human_delta','mean'),paired_raters=('reviewer','count'),Q_delta=('Q_delta','first'),IoU_delta=('IoU_delta','first'),D10_delta=('D10_delta','first')).reset_index()
    ip=imagepairs[imagepairs.human_delta!=0]
    per=[]
    for rev,g in r.groupby('reviewer'):
        per.append(dict(reviewer=rev,valid=int(g.human.notna().sum()),unknown=int(g.human.isna().sum()),poor=int((g.grade=='poor').sum()),medium=int((g.grade=='medium').sum()),good=int((g.grade=='good').sum()),rho_Q=rho(g.human,g.Q),rho_IoU=rho(g.human,g.IoU)))
    summary=dict(reviewers=len(answers),submitted_ratings=len(r),valid_ratings=len(valid),unknown_ratings=int(r.human.isna().sum()),images=r.case_id.nunique(),items=len(items),buildings=r.image.str.split('-').str[0].nunique(),grade_counts=r.grade.value_counts().to_dict(),complete_pairs=len(complete),tied_pairs=int((complete.human_delta==0).sum()),directional_pairs=len(direction),directional_images=len(ip),item_mean_spearman={m:rho(items.human,items[m]) for m in ['Q','IoU','D10']},pooled_spearman={m:rho(valid.human,valid[m]) for m in ['Q','IoU','D10']},pair_direction_matches={m:int((direction.human_delta*direction[m+'_delta']>0).sum()) for m in ['Q','IoU','D10']},image_direction_matches={m:int((ip.human_delta*ip[m+'_delta']>0).sum()) for m in ['Q','IoU','D10']})
    dsrows=[]; labels=sorted({x for v in r.defects for x in json.loads(v)})
    for (cid,side),g in r.groupby(['case_id','side']):
        lists=[json.loads(x) for x in g.defects]; known=[x for x in lists if x and 'unknown' not in x]
        row=dict(case_id=cid,side=side,known_defect_raters=len(known),unknown_defect_raters=sum('unknown' in x for x in lists),none_conflicts=sum('none' in x and len(x)>1 for x in lists))
        for label in labels:
            row[label+'_votes']=sum(label in x for x in known)
            row[label+'_rate']=row[label+'_votes']/len(known) if known else np.nan
        dsrows.append(row)
    defects=pd.DataFrame(dsrows)
    metriccols=['missing_turns','extra_turns','floor_omission','floor_extension','S_bottom_deg','dir','Hmean','Hcenter','height_loss']
    defects=defects.merge(components[['case_id','side']+metriccols],on=['case_id','side'],validate='one_to_one')
    relations=[]
    for label,m in [('missing','missing_turns'),('missing','floor_omission'),('floor_omission','floor_omission'),('extra','extra_turns'),('extra','floor_extension'),('position','S_bottom_deg'),('position','dir'),('height','Hmean'),('height','Hcenter'),('height','height_loss')]:
        relations.append(dict(defect=label,metric=m,items=len(defects),spearman=rho(defects[label+'_rate'],defects[m])))
    outputs={'RATINGS':r,'ITEM_MEANS':items,'PAIR_JUDGMENTS':pairs,'IMAGE_DIRECTIONS':imagepairs,'PER_REVIEWER':pd.DataFrame(per),'DEFECT_COMPONENTS':defects,'DEFECT_RELATIONS':pd.DataFrame(relations),'UNKNOWN_RATINGS':r[r.human.isna()]}
    for name,frame in outputs.items():frame.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    summary['defect_none_conflicts']=int(defects.none_conflicts.sum())
    assert len(complete)+int(pairs.human_delta.isna().sum())==len(answers)*len(keys)
    assert len(direction)+summary['tied_pairs']==len(complete)
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
