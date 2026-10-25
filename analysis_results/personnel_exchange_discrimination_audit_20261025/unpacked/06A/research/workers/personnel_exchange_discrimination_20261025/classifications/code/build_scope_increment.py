#!/usr/bin/env python3
"""Add the supported scope response domain to the Manual/Semi geometry family."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
import build_condition_response_classes as core

def main(a):
 out=Path(a.output)
 h=pd.read_csv(a.features);s=pd.read_csv(a.scope)
 f=h.merge(s,on=['worker_id','heldout_building'],how='left',validate='one_to_one')
 f['scope_joint_supported']=f.scope_supported.fillna(False)&f.scope_hard_supported.fillna(False)&f.scope_easy_supported.fillna(False)
 core.DOMAINS['SCOPE_RESPONSE']=['scope_centered_rejection','scope_hard_minus_easy']
 core.FAMILIES['MSDGEOM_SCOPE']=dict(domains=['M_STRUCTURE_HARD','M_BOUNDARY_HARD','S_STRUCTURE','S_BOUNDARY','SCOPE_RESPONSE'],
    required=['manual_geometry','semi_geometry','scope_joint_supported'],input_conditions='manual|semi|scope',
    distinction='Adds source/image/condition-centered scope answering tendency and hard-minus-easy response to MSDGEOM; scope is not correctness.',
    sort=['m_hard_turn_n','s_all_turn_n','scope_centered_rejection'])
 ll=[];cc=[];rr=[];params={};axis_l=[];axis_c=[];axis_p=[]
 for heldout,g in f.groupby('heldout_building',sort=False):
  g=g.reset_index(drop=True)
  labs,centers,reg,scales=core.fit_one(g,'MSDGEOM_SCOPE')
  ll.append(labs);cc.append(centers);rr.append(reg);params[heldout]=scales
  spec=core.FAMILIES['MSDGEOM_SCOPE'];need=[c for d in spec['domains'] for c in core.DOMAINS[d]]
  gg=g[g[spec['required']].all(axis=1)&g[need].notna().all(axis=1)].copy()
  x,tr=core.domain_matrix(gg,spec['domains']);pc=PCA(n_components=1,svd_solver='full');score=pc.fit_transform(x).ravel()
  sign=1 if np.cov(score,gg.m_hard_turn_n.to_numpy())[0,1]>=0 else -1;score*=sign
  threshold=float(np.median(score));mapping=dict(zip(gg.worker_id,np.where(score>threshold,'C2','C1')))
  z=labs[labs.k.eq(2)].copy();z['method']='MSDGEOM_SCOPE_AXIS2';z['family']='MSDGEOM_SCOPE_AXIS';z['class_id']=z.worker_id.map(mapping).fillna('unknown');z['coarse_label']=z.class_id;z['fine_label']=z.class_id
  z['axis_score']=z.worker_id.map(dict(zip(gg.worker_id,score)));z['axis_threshold']=threshold;axis_l.append(z)
  for cl in ['C1','C2']:
   gc=gg[gg.worker_id.isin([w for w,v in mapping.items() if v==cl])]
   row=dict(method='MSDGEOM_SCOPE_AXIS2',family='MSDGEOM_SCOPE_AXIS',k=2,heldout_building=heldout,class_id=cl,
            members='|'.join(gc.worker_id),people=len(gc),new_people=int(gc.origin.eq('new').sum()),old_people=int(gc.origin.eq('v1').sum()),axis_threshold=threshold)
   row.update({c:float(gc[c].mean()) for c in need});axis_c.append(row)
  axis_p.append(dict(method='MSDGEOM_SCOPE_AXIS2',heldout_building=heldout,threshold=threshold,known_workers=len(gg),lower_members=int(sum(score<=threshold)),higher_members=int(sum(score>threshold)),
    selected_on_target_fusion=False,domains='|'.join(spec['domains']),transform_json=json.dumps(dict(domain_transform=tr,pca_component=(pc.components_[0]*sign).tolist(),orientation='m_hard_turn_n'),ensure_ascii=False)))
 ls=pd.concat(ll+axis_l,ignore_index=True);cs=pd.concat(cc+[pd.DataFrame(axis_c)],ignore_index=True);rs=pd.concat(rr+[pd.DataFrame(axis_p)],ignore_index=True)
 core.save_csv(f,Path(a.feature_output)/'HISTORY_FEATURES_WITH_SCOPE_ALL_LOBO.csv.gz')
 core.save_csv(ls,out/'SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz');core.save_csv(cs,out/'SCOPE_INCREMENT_CLASS_DEFINITIONS_ALL_LOBO.csv.gz');core.save_csv(cs[cs.heldout_building.eq('ALL')],out/'SCOPE_INCREMENT_CLASS_DEFINITIONS_ALL.csv');core.save_csv(rs,out/'SCOPE_INCREMENT_CANDIDATE_REGISTRY.csv');core.save_json(params,out/'SCOPE_TRANSFORMS_ALL_LOBO.json')
 core.save_json(dict(scope_source=a.scope,scope_sha256=core.sha(a.scope),features_source=a.features,methods=list(ls.method.unique()),
     no_target_fusion_selection=True,underlying_data_version='v2',scope_input_note='Latest v2 ledger plus 286 exact historical oos-string response restorations; feature-only recovery, frozen qualification/quality unchanged.',
     scope_meaning='Relative answer rejection tendency and difficulty contrast, not an adjudicated correctness score.'),out/'SCOPE_INCREMENT_RECEIPT.json')
 print(rs[rs.heldout_building.eq('ALL')][['method','known_workers','class_size_vector','lower_members','higher_members']].to_string(index=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--features',required=True);p.add_argument('--scope',required=True);p.add_argument('--output',required=True);p.add_argument('--feature-output',required=True);main(p.parse_args())
