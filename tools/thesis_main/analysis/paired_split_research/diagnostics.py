"""Read-only diagnostics and tests for the two requested correspondence rules."""
from __future__ import annotations
from pathlib import Path
import argparse,collections,gzip,hashlib,itertools,json,math
import numpy as np,pandas as pd
from . import study as s
R=s.ROOT

def data(root):
 rows=[json.loads(l)for l in gzip.open(root/'inputs/responses.jsonl.gz','rt',encoding='utf-8')]
 audit=pd.read_csv(root/'inputs/prior_response_audit.csv').set_index('id')
 app=s.accepted_map(root/'inputs',rows)
 rec,ad=s.prepare(rows,audit,app,key39=json.loads((root/'inputs/key39_source.json').read_text(encoding='utf-8')))
 return rows,rec,ad

def run(root=R, output_root=None):
 output_root=Path(output_root) if output_root is not None else root/'local_recheck'
 out=output_root/'results';rows,rec,ad=data(root)
 pdf=pd.read_csv(out/'pairwise_rules.csv');mem=pd.read_csv(out/'memberships.csv')
 cache=json.loads((out/'cache.json').read_text(encoding='utf-8'));summ=[];each=[];details=[]
 d=json.loads((root/'inputs/user_six_review.json').read_text(encoding='utf-8-sig'))['decisions']
 cases=[]
 for e in json.loads((root/'inputs/pilot_evidence.json').read_text(encoding='utf-8')):
  cases.append(dict(code=e['code'],image_id=e['image_id'],condition=e['condition'],id_a=e['id_a'],id_b=e['id_b'],
   source='user_confirmed_six',relation=d[e['key']]['Relation'],note=d[e['key']]['Note']))
 for e in json.loads((root/'inputs/new_six_evidence.json').read_text(encoding='utf-8')):
  for p in e['pairs_detail']:
   cases.append(dict(code=e['code'],image_id=e['image_id'],condition=e['condition'],id_a=p['ids'][0],id_b=p['ids'][1],source='local_AI_unconfirmed',relation=None,note=e['observation']))
 # Prespecified previous local failure + point-order example + data-driven seam witness.
 for code,cond,wa,wb,reason in [
 ('e9zR4mvMWw7-16','semi','W006','W032','previous_local_shift'),
 ('X7HyMhZNoso-19','manual','W011','W015','previous_order_disagreement'),
 ('wc2JMjhGNzB-53','manual','W027','W029','new_numeric_seam_witness_no_image_review'),
 ('yqstnuAEVhm-31','manual','W006','W010','bound_vs_split_association_sensitivity')]:
  aa=next(a for a in rec.values()if a['audit']['code']==code and a['audit']['condition']==cond and a['audit']['worker']==wa)
  bb=next(a for a in rec.values()if a['audit']['code']==code and a['audit']['condition']==cond and a['audit']['worker']==wb)
  cases.append(dict(code=code,image_id=aa['row']['image_id'],condition=cond,id_a=aa['id'],id_b=bb['id'],source=reason,relation=None,note='not a new user adjudication'))
 for c in cases:
  a=rec[c['id_a']];b=rec[c['id_b']];v,maps=s.compare(a,b);q=dict(**c,worker_a=a['audit']['worker'],worker_b=b['audit']['worker'],count_a=len(a['p']),count_b=len(b['p']),**v)
  q['bound_source_a']=a['audit']['pairing_source'];q['bound_source_b']=b['audit']['pairing_source']
  for key in s.METRICS:
   z=mem[(mem.image_id==c['image_id'])&(mem.condition==c['condition'])&(mem.view==key)&(mem.cut==9)]
   za=z[z.id==c['id_a']];zb=z[z.id==c['id_b']]
   if len(za)==len(zb)==1:q[key+'_same_full_group9']=bool(za.iloc[0].cluster==zb.iloc[0].cluster)
  summ.append(q);obs=dict(**q,points_a=a['p'].tolist(),points_b=b['p'].tolist(),links_a=(a['links']+1).tolist()if a['links']is not None else None,links_b=(b['links']+1).tolist()if b['links']is not None else None,comparisons={})
  for method in ['split_fixed','bound_fixed','split_cyclic','bound_cyclic','split_free','bound_free']:
   points=[]
   for role in ['top','bottom']:
    if method+'_'+role not in maps:continue
    aa,bb=maps[method+'_'+role];dd=np.diag(s.angular(a['p'][aa],b['p'][bb]))
    for i,(ia,ib,err) in enumerate(zip(aa,bb,dd)):
     item=dict(method=method,role=role,ordinal=i+1,point_a=int(ia)+1,point_b=int(ib)+1,x_a=a['p'][ia,0],y_a=a['p'][ia,1],x_b=b['p'][ib,0],y_b=b['p'][ib,1],error_deg=float(err),dx_px=float((a['p'][ia,0]-b['p'][ib,0]+512)%1024-512),dy_px=float(a['p'][ia,1]-b['p'][ib,1]))
     each.append(dict(code=c['code'],condition=c['condition'],worker_a=q['worker_a'],worker_b=q['worker_b'],**item));points.append(item)
   obs['comparisons'][method]=points
  details.append(obs)
 pd.DataFrame(summ).to_csv(out/'focused_case_summary.csv',index=False)
 pd.DataFrame(each).to_csv(out/'focused_endpoint_comparisons.csv',index=False)
 s.dump(out/'focused_cases.json',details)
 both=pdf[pdf.status.eq('both_available')];report=[]
 for a,b in [('split_fixed','bound_fixed'),('split_fixed','split_cyclic'),('bound_fixed','bound_cyclic'),('split_cyclic','split_free'),('bound_cyclic','bound_free')]:
  row=dict(view_a=a,view_b=b,N_pairs=len(both),numeric_difference_gt1e_8=int((abs(both[a]-both[b])>1e-8).sum()))
  for t in s.CUTS:row[f'threshold_decision_changes_{int(t)}']=int(((both[a]<=t)!=(both[b]<=t)).sum())
  report.append(row)
 pd.DataFrame(report).to_csv(out/'correspondence_comparison_summary.csv',index=False)
 # Direct two-dimensional uncertainty readout (role determination is conditional).
 rol=[];valid=pdf[pdf.status.isin(['both_available','split_available'])]
 for t in s.CUTS:
  for cond,q in valid.groupby('condition'):
   T=q.top_fixed<=t;B=q.bottom_fixed<=t
   rol.append(dict(condition=cond,cut=t,pairs=len(q),both_close=int((T&B).sum()),only_top_close=int((T&~B).sum()),only_bottom_close=int((~T&B).sum()),neither_close=int((~T&~B).sum())))
 pd.DataFrame(rol).to_csv(out/'top_bottom_agreement_states.csv',index=False)
 # Worker descriptions on the same paired-eligible pool, not variable method coverage.
 wm=[];per=[]
 for g in cache.values():
  ix=np.array(g['bound_indices'],int);N=len(ix)
  if N<5:continue
  ids=[g['ids'][i]for i in ix];rr=[rec[cid]for cid in ids];cnt=np.array([len(a['p'])for a in rr]);cond=rr[0]['audit']['condition']
  for key in ['count_only','split_fixed','bound_fixed','split_cyclic','bound_cyclic','split_free','bound_free']:
   D=(cnt[:,None]!=cnt[None,:]).astype(float) if key=='count_only' else np.array(g['matrices'][key])[np.ix_(ix,ix)]
   for t in ((0.,) if key=='count_only' else [6.,9.,12.]):
    l=s.cluster(D,t);co=collections.Counter(l);sg=np.array([co[x]==1 for x in l],int);A=D<=t;np.fill_diagonal(A,False)
    for j,a in enumerate(rr):
     peer=(sg.sum()-sg[j])/(N-1);nc=int((cnt==cnt[j]).sum()-1)
     per.append(dict(id=a['id'],code=a['audit']['code'],image_id=a['row']['image_id'],building=a['row']['building_id'],condition=cond,stage=a['row']['stage'],worker=a['audit']['worker'],view=key,cut=t,N=N,
           singleton=int(sg[j]),peer_singleton_rate=peer,within_image_centered_singleton=float(sg[j]-peer),
           no_same_count_peer=nc==0,close_neighbors=int(A[j].sum()),singleton_despite_close_peer=bool(sg[j] and A[j].any())))
 wdf=pd.DataFrame(per);wdf.to_csv(out/'worker_same_image_observations.csv',index=False)
 for keys,g in wdf.groupby(['condition','view','cut','worker']):
  cond,key,t,w=keys
  wm.append(dict(condition=cond,view=key,cut=t,worker=w,images=g.image_id.nunique(),buildings=g.building.nunique(),singletons=int(g.singleton.sum()),rate=float(g.singleton.mean()),
       peer_centered_rate=float(g.within_image_centered_singleton.mean()),no_same_count_peer=int(g.no_same_count_peer.sum()),singletons_with_close_peer=int(g.singleton_despite_close_peer.sum())))
 pd.DataFrame(wm).to_csv(out/'worker_descriptive_summary.csv',index=False)
 # Paired worker comparisons use exact common target images and conditions.
 pairw=[]
 for (cond,key,t),g in wdf.groupby(['condition','view','cut']):
  if key not in ['count_only','split_fixed','bound_fixed']or (key!='count_only' and t!=9):continue
  for wa,wb in itertools.combinations(sorted(g.worker.unique()),2):
   a=g[g.worker==wa].set_index('image_id');b=g[g.worker==wb].set_index('image_id');common=a.index.intersection(b.index)
   if len(common)<5:continue
   aa=a.loc[common];bb=b.loc[common]
   pairw.append(dict(condition=cond,view=key,cut=t,worker_a=wa,worker_b=wb,common_images=len(common),common_buildings=aa.building.nunique(),rate_a=aa.singleton.mean(),rate_b=bb.singleton.mean(),mean_paired_difference=(aa.singleton-bb.singleton).mean()))
 pd.DataFrame(pairw).to_csv(out/'worker_matched_image_contrasts.csv',index=False)
 # Preserve input min-horizontal-association experiment as an explicit alternative,
 # not a replacement of the retained-link view.
 alt=output_root/'sensitivity_min_horizontal_results'
 if alt.exists():
  m=pd.read_csv(alt/'pairwise_rules.csv');j=both.merge(m,on=['id_a','id_b'],suffixes=('_legacy','_minx'))
  j=j[j.status_minx=='both_available'];sm=[]
  for col in ['bound_fixed','bound_cyclic','bound_free']:
   sm.append(dict(metric=col,N_common_pairs=len(j),numeric_changes=int((abs(j[col+'_legacy']-j[col+'_minx'])>1e-8).sum()),threshold9_changes=int(((j[col+'_legacy']<=9)!=(j[col+'_minx']<=9)).sum())))
  pd.DataFrame(sm).to_csv(out/'association_rule_sensitivity.csv',index=False)
  s.dump(out/'MIN_HORIZONTAL_CONTROL_SCOPE.json',json.loads((alt/'SCOPE.json').read_text(encoding='utf-8')))
 # A list of exact response IDs needing association review, not an exclusion list.
 ad[ad.paired_role_order_inversion.eq(True)|ad.exact_x_ties.fillna(0).gt(0)|ad.near_x_gaps_le1px.fillna(0).gt(0)].to_csv(out/'order_and_tie_review_queue.csv',index=False)
 print(pd.DataFrame(summ)[['code','worker_a','worker_b','source','split_fixed','bound_fixed','split_cyclic','bound_cyclic']].round(4).to_string(index=False))
 print('\nW037\n',pd.DataFrame(wm).query("worker=='W037' and condition=='manual' and (cut==9 or view=='count_only')").to_string(index=False))
 return rec,details

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=R);args=a.parse_args();run(args.root)
