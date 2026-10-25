#!/usr/bin/env python3
"""Finite training-side axis discretization controls for large-block capacity."""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from build_condition_response_classes import save_csv,save_json,domain_matrix,DOMAINS,ST,BD,cols

AXES={
 'DSTRUCT_AXIS2': dict(kind='scalar',field='m_hard_turn_n',support='manual_geometry',
       description='Current difficult-image nonredundant turn response, median split; turn_n already removes near-collinear redundancy.'),
 'DBOUNDARY_AXIS2': dict(kind='pca',domains=['M_BOUNDARY_HARD'],support='manual_geometry',
       orient='m_hard_matched_bottom_bias_deg',
       description='Dominant difficult-image signed top/bottom/scale response axis, median split.'),
 'Q_MEDIAN2':dict(kind='scalar',field='m_all_B8L2',support='manual_geometry',
       description='Simple Q baseline on exactly the Manual geometry-supported roster, median split.'),
 'Q_HARD_MEDIAN2':dict(kind='scalar',field='m_hard_B8L2',support='manual_geometry',
       description='Difficulty-conditional Q baseline, median split; compare with overall Q.'),
}

def main(a):
 p=Path(a.output);h=pd.read_csv(a.features);labels=[];centers=[];params=[]
 for heldout,hh in h.groupby('heldout_building',sort=False):
  for method,spec in AXES.items():
   fields=[spec['field']] if spec['kind']=='scalar' else list(dict.fromkeys(c for d in spec['domains'] for c in DOMAINS[d]))
   g=hh[hh[spec['support']] & hh[fields].notna().all(axis=1)].copy()
   if spec['kind']=='scalar':
    score=g[spec['field']].to_numpy();weights={spec['field']:1.}
   else:
    x,transform=domain_matrix(g,spec['domains']);pc=PCA(n_components=1,svd_solver='full');score=pc.fit_transform(x).ravel()
    cov=np.cov(score,g[spec['orient']].to_numpy())[0,1];sign=1 if cov>=0 else -1;score*=sign
    weights=dict(domain_transform=transform,pca_component=(pc.components_[0]*sign).tolist(),orientation=spec['orient'])
   threshold=float(np.median(score));higher=score>threshold
   # No random tie splitting: ties belong to the lower-response class.
   mapping=dict(zip(g.worker_id,np.where(higher,'C2','C1')))
   z=hh[['worker_id','origin','heldout_building']].copy();z['method']=method;z['family']=method.removesuffix('2');z['class_id']=z.worker_id.map(mapping).fillna('unknown')
   z['known']=z.class_id.ne('unknown');z['missing_reason']=np.where(z.known,'','insufficient_manual_difficulty_history')
   z['input_conditions']='manual';z['evaluation_condition']='manual_and_semi_separately';z['condition']='manual';z['coarse_label']=z.class_id;z['fine_label']=z.class_id;z['k']=2
   z['underlying_data_version']='v2';z['label_stage']='all_data_descriptive' if heldout=='ALL' else 'both_conditions_target_building_excluded'
   z['axis_score']=z.worker_id.map(dict(zip(g.worker_id,score)));z['axis_threshold']=threshold
   labels.append(z)
   semantic=list(dict.fromkeys(fields + cols('m','all',ST+BD+['B8L2','log_time'])+cols('m','hard',ST+BD+['B8L2','log_time'])))
   for cl in ['C1','C2']:
    gg=g[g.worker_id.isin([w for w,v in mapping.items() if v==cl])]
    row=dict(method=method,family=z.family.iloc[0],k=2,heldout_building=heldout,class_id=cl,
       members='|'.join(gg.worker_id),people=len(gg),new_people=int(gg.origin.eq('new').sum()),old_people=int(gg.origin.eq('v1').sum()),
       axis_threshold=threshold,axis_direction='at_or_below_training_median' if cl=='C1' else 'above_training_median',description=spec['description'])
    row.update({c:float(gg[c].mean()) for c in semantic});centers.append(row)
   params.append(dict(method=method,heldout_building=heldout,k=2,threshold=threshold,known_workers=len(g),
       lower_members=sum(~higher),higher_members=sum(higher),features='|'.join(fields),
       selected_on_target_fusion=False,description=spec['description'],transform_json=json.dumps(weights,ensure_ascii=False)))
 ls=pd.concat(labels,ignore_index=True);cs=pd.DataFrame(centers);rs=pd.DataFrame(params)
 save_csv(ls,p/'AXIS_METHOD_LABELS_ALL_LOBO.csv.gz');save_csv(cs,p/'AXIS_CLASS_DEFINITIONS_ALL_LOBO.csv.gz');save_csv(cs[cs.heldout_building.eq('ALL')],p/'AXIS_CLASS_DEFINITIONS_ALL.csv');save_csv(rs,p/'AXIS_CANDIDATE_REGISTRY.csv')
 print(rs[rs.heldout_building.eq('ALL')][['method','known_workers','lower_members','higher_members','threshold']].to_string(index=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--features',required=True);p.add_argument('--output',required=True);main(p.parse_args())
