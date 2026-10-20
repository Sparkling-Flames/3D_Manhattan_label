"""AST-isolated evaluator unit test, after static source review.
No learner import, fitting, filesystem/network actions from delivered code.
"""
import ast,json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
P=Path('/workspace/shared/interchangeability_audit_20261020/audit_learning/learn_corner_types.py');src=P.read_text();tree=ast.parse(src)
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Anchors')
METRICS=['distance','distance9','distance12','distance_valid','different_count','incomplete','high_angle','old_main','old_badwide']
def factor(f):
 codes,vals=pd.factorize(pd.MultiIndex.from_frame(f),sort=True);t=vals.to_frame(index=False);t.columns=f.columns;return codes,t
g={'np':np,'pd':pd,'factor':factor,'METRICS':METRICS};exec(compile(ast.Module(body=[node],type_ignores=[]),'<isolated reviewed Anchors>','exec'),g)
rows=[]
for bg in range(2):
 for same in [True,False]:
  r=dict(worker_a='a',worker_b='b' if same else 'c',building='B1',pool_id='P1',k=7,background_id='bg'+str(bg));r.update({x:0. for x in METRICS});r.update(distance=1. if same else 2.,distance9=1. if (same==(bg==0)) else np.nan,distance12=1. if bg==0 else np.nan,distance_valid=1.);rows.append(r)
f=pd.DataFrame(rows);a=g['Anchors'](f,['a','b','c']);lab=np.array([0,0,1]);z=a.evaluate(lab)[0];assert z['matched_anchors']==2;assert z['distance9_common_anchors']==0;assert pd.isna(z['within_distance9']) and pd.isna(z['between_distance9']);assert z['distance12_common_anchors']==1;assert z['distance_gap']==1
zz=a.paired(lab,np.array([0,1,0]))[0];assert zz['distance9_common_anchors']==0;assert pd.isna(zz['delta_distance9_gap']);assert zz['delta_distance_gap']==2
out=dict(source_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),asymmetric_angle_missingness_test='pass',primary_support_preserved='pass',candidate_baseline_common_angle_support='pass',no_model_execution=True)
Path(__file__).with_name('LEARNER_SUPPORT_TEST_RECEIPT.json').write_text(json.dumps(out,indent=2));print(out)
