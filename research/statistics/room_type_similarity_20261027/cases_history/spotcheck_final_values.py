#!/usr/bin/env python3
"""Read completed outputs only; small support/peer/weight consistency checks.

This does not refit or run a new experiment. Invoke only after final writers stop.
"""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd

def main():
    study=Path(__file__).resolve().parents[1];out=Path(__file__).resolve().parent
    inp=pd.read_csv(study/'inputs/annotations.csv.gz',low_memory=False)
    inp=inp[(inp.condition=='manual')&(inp.layer=='ordinary')&inp.formal_quality&inp.Q.notna()&inp.D10.notna()]
    p=study/'results/personal';P=pd.read_csv(p/'OOF_Q.csv.gz');S=pd.read_csv(p/'METHOD_SUMMARY.csv')
    base=P[P.method=='zero'];supports=[]
    for method,g in P.groupby('method'):
        assert set(g.object_id)==set(base.object_id)
        supports.append(dict(method=method,rows=len(g),images=g.image_key.nunique(),buildings=g.building.nunique()))
    z=base.merge(inp[['object_id','image_key','Q']],on=['object_id','image_key'],validate='one_to_one')
    n=z.groupby('image_key').Q.transform('count');s=z.groupby('image_key').Q.transform('sum')
    err=float(np.max(abs(z.Q-(s-z.Q)/(n-1)-z.actual_relative)));assert err<1e-9
    f=pd.read_csv(p/'FOLDS_Q.csv');assert all(r.held_out_building not in r.train_building_ids.split('|') for r in f.itertuples())
    c=pd.read_csv(p/'INNER_CV_Q.csv.gz');assert all(r.held_out_building not in r.training_buildings.split('|')+r.validation_buildings.split('|') and not set(r.training_buildings.split('|'))&set(r.validation_buildings.split('|')) for r in c.itertuples())
    values=[]
    for method,g in P.groupby('method'):
        im=g.groupby(['image_key','building']).absolute_error.mean().reset_index();b=im.groupby('building').absolute_error.mean();r=S[(S.outcome=='Q')&(S.method==method)].iloc[0]
        em=float(im.absolute_error.mean()-r.image_equal_mae);eb=float(b.mean()-r.building_equal_mae);assert max(abs(em),abs(eb))<1e-9
        values.append(dict(method=method,image_equal_mae=float(im.absolute_error.mean()),building_equal_mae=float(b.mean()),image_reaggregation_difference=em,building_reaggregation_difference=eb))
    result=dict(status='completed',scope='finite completed-output consistency only; no refit',personal_support=supports,other_person_baseline_max_difference=err,outer_and_inner_buildings_disjoint=True,personal_Q_values=values)
    ip=study/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz'
    if ip.exists():
        I=pd.read_csv(ip);b=I[(I.metric=='Q')&(I.method=='training_mean')]
        assert all(set(g.image_key)==set(b.image_key) for _,g in I.groupby(['metric','method']))
        result['image_all_methods_Q_D10_same_targets']=True;result['image_targets']=len(b)
    else:result['image_final_outputs']='not yet present; code reviewed only'
    result['source_code_sha256']={f:hashlib.sha256((study/'code'/f).read_bytes()).hexdigest() for f in ['personal.py','image_similarity.py']}
    (out/'FINAL_VALUES_SPOTCHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
