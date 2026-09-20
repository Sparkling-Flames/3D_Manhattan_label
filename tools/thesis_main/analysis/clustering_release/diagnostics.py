"""Evidence-tiered development diagnostics and narrowly scoped correspondence review."""
from pathlib import Path
import collections,itertools,json,math,sys
import numpy as np,pandas as pd
from .release import prepare,cluster,frame,writejson

def run(root,out):
 src=root/'input/source';st,rows,rec,elig,_=prepare(root);cache=json.loads((out/'cache.json').read_text())
 pair=pd.read_csv(out/'pairwise.csv');mem=pd.read_csv(out/'memberships.csv')
 def key(iid,cond,a,b):return (iid,cond,*sorted([a,b]))
 # Row lookup kept explicit; IDs and point numbering are never derived from similarity.
 by={key(r['image_id'],r['condition'],r['id_a'],r['id_b']):r for r in pair.to_dict('records')}
 mby={(r['image_id'],r['condition'],r['id'],r['metric'],r['cut']):r['cluster'] for r in mem.to_dict('records')}
 evidence=[];P=src/'analysis_results/paired_split_research_received_20260920';L=src/'analysis_results/local_point_research_received_20260919'
 u12=json.loads((P/'inputs/user12_review.json').read_text())
 for k,d in u12['decisions'].items():
  iid,c,a,b=k.split('|');near=(d['Range']=='相近' and d['Detail']=='相近' and d['Position']=='接近') or '确实很接近' in d['Note']
  evidence.append(dict(image_id=iid,condition=c,id_a=a,id_b=b,level='U12_user',relation='near' if near else 'coverage_diff' if d['Range']=='不同' else 'unspecified',explicit_whole_partition=False,note=d['Note'],source='inputs/user12_review.json'))
 u6=json.loads((P/'inputs/user_six_review.json').read_text())
 for k,d in u6['decisions'].items():
  iid,c,a,b=k.split('|')
  evidence.append(dict(image_id=iid,condition=c,id_a=a,id_b=b,level='U6_user',relation='near' if d['Relation']=='可视为相近' else 'separate' if d['Relation']=='应分开保留差异' else 'unspecified',explicit_whole_partition=d['Relation']=='应分开保留差异',note=d.get('Note',''),source='inputs/user_six_review.json'))
 ai8=json.loads((P/'history_visual_review/selected_evidence.json').read_text());findings=json.loads((P/'history_visual_review/visual_findings.json').read_text())
 # selected_evidence is a list from the pinned package.
 if isinstance(ai8,dict):ai8=ai8.get('cases',ai8.get('selected',[]))
 for e in ai8:
  d=e.get('pair',e);code=d.get('code',e.get('code'));v=next((x for x in findings if x['code']==code),{})
  evidence.append(dict(image_id=d.get('image_id',e.get('image_id')),condition=d.get('condition',e.get('condition')),id_a=d.get('id_a',e.get('id_a')),id_b=d.get('id_b',e.get('id_b')),level='AI8_observation',relation='unadjudicated',explicit_whole_partition=False,note=v.get('observation',''),question=v.get('question',''),source='history_visual_review/visual_findings.json'))
 # Carry earlier focused AI observations WITHOUT turning them into expected labels.
 for e in json.loads((P/'received_results/focused_cases.json').read_text()):
  if e['source']=='user_confirmed_six':continue
  evidence.append({k:e.get(k,'') for k in ['image_id','code','condition','id_a','id_b','worker_a','worker_b','note']}|dict(level='AI_prior',relation='unadjudicated',explicit_whole_partition=False,source=e['source']))
 scored=[];known_pairs=set();known_images=set()
 for e in evidence:
  k=key(e['image_id'],e['condition'],e['id_a'],e['id_b']);known_pairs.add(k);known_images.add(e['image_id']);p=by.get(k,{})
  d={**e,**{a:p.get(a) for a in ['code','worker_a','worker_b','count_a','count_b','split_cyclic','split_fixed','split_free','bound_cyclic','ospa1']}}
  for metric,t in [('split_cyclic',6.),('split_cyclic',9.),('split_cyclic',12.),('split_fixed',9.),('bound_cyclic',9.),('split_free',9.),('ospa_gate',6.)]:
   ka=(*k[:2],e['id_a'],metric,t);kb=(*k[:2],e['id_b'],metric,t);tag=metric+str(int(t))
   d[tag+'_same']=bool(mby[ka]==mby[kb]) if ka in mby and kb in mby else None
   v=p.get(metric);d[tag+'_near']=bool(v<=t+1e-8) if v is not None and np.isfinite(v) else None
  scored.append(d)
 sd=frame(out,'evidence_diagnostics.csv',scored)
 scores=[]
 for level,d in sd.groupby('level'):
  for col in [c for c in sd if c.endswith('_same')]:
   same=d[col];near=d.relation.eq('near');sep=d.relation.eq('separate');cover=d.relation.eq('coverage_diff')
   scores.append(dict(level=level,method=col,near_n=int(near.sum()),near_together=int((same.eq(True)&near).sum()),near_unknown=int((same.isna()&near).sum()),explicit_separate_n=int(sep.sum()),separate_preserved=int((same.eq(False)&sep).sum()),coverage_different_n=int(cover.sum()),coverage_separate_descriptive=int((same.eq(False)&cover).sum())))
 frame(out,'evidence_scorecard.csv',scores)
 # The user supplied only one local group anchor. Evaluate it, never promote a swap to approved input.
 anchor=json.loads((src/'analysis_results/pro_next_round_20260920/uNb21_用户局部对应.json').read_text())
 a,b=rec[anchor['id_a']],rec[anchor['id_b']];v,maps=st.compare(a,b);ar=[];scenario={}
 for role,ix in [('top','up'),('bottom','dn')]:
  ai,bi=a[ix],b[ix];full=st.angular(a['p'][ai],b['p'][bi]);u=2;w=3
  orig=np.diag(full);swap=np.arange(len(ai));swap[[u,w]]=swap[[w,u]]
  residual=full[np.arange(len(ai)),swap]
  rest=np.delete(np.arange(len(ai)),u);target=np.delete(np.arange(len(ai)),w)
  lower,_=st.bottleneck(full[np.ix_(rest,target)])
  scenario[role]={'anchor_deg':float(full[u,w]),'fixed_max':float(orig.max()),'one_anchor_minimum_possible_full_max':float(max(full[u,w],lower)),'hypothetical_swap_max':float(residual.max()),'displaced_ordinal_unconfirmed':4,'swap_point_mapping':[[int(ai[i]+1),int(bi[swap[i]]+1)] for i in range(len(ai))]}
  for i in range(len(ai)):
   ar.append(dict(role=role,ordinal_a=i+1,point_a=int(ai[i]+1),fixed_ordinal_b=i+1,fixed_point_b=int(bi[i]+1),fixed_error_deg=orig[i],hypothetical_ordinal_b=int(swap[i]+1),hypothetical_point_b=int(bi[swap[i]]+1),hypothetical_error_deg=residual[i],evidence='user_group_anchor_projected_to_endpoint' if i==2 else 'unconfirmed_reciprocal' if i==3 else 'retained_nominal_not_user_confirmed'))
 writejson(out/'uNb21_partial_anchor.json',dict(original=anchor,side_results=scenario,automatic_full_patch_applied=False,baseline_score=v['split_cyclic']))
 frame(out,'uNb21_endpoint_scenarios.csv',ar)
 g=cache[anchor['image_id']+'|manual'];D=np.array(g['matrices']['split_cyclic']);i=g['ids'].index(a['id']);j=g['ids'].index(b['id']);dmax=max(x['hypothetical_swap_max'] for x in scenario.values());new=D.copy();new[i,j]=new[j,i]=dmax;z=[]
 for t in [6,9,12]:
  l=cluster(D,t);m=cluster(new,t);z.append(dict(cut=t,baseline_distance=D[i,j],hypothetical_distance=dmax,baseline_same=l[i]==l[j],hypothetical_same=m[i]==m[j],baseline_groups=len(set(l)),hypothetical_groups=len(set(m)),changed_relations=int(np.sum((l[:,None]==l[None,:])!=(m[:,None]==m[None,:]))//2),approval='NOT_APPLIED_one_pair_candidate_only'))
 frame(out,'uNb21_hypothetical_partition.csv',z)
 # Numerical trigger inventory; group IDs do not imply error.
 primary=mem[(mem.metric=='split_cyclic')&(mem.cut==9)]
 cmap={(r['image_id'],r['condition'],r['id']):r['cluster'] for r in primary.to_dict('records')}
 candidates=[]
 for p in pair.to_dict('records'):
  if not np.isfinite(p.get('split_cyclic',np.nan)):continue
  s=p['split_cyclic'];fr=p['split_free'];fx=p['split_fixed'];bc=p.get('bound_cyclic',np.nan)
  same=cmap[p['image_id'],p['condition'],p['id_a']]==cmap[p['image_id'],p['condition'],p['id_b']]
  triggers=[]
  if fx>9+1e-8 and s<=9+1e-8:triggers.append('cyclic_numbering_changes_compatibility')
  if s>9+1e-8 and fr<=9+1e-8:triggers.append('order_vs_free_correspondence')
  if np.isfinite(bc) and ((s<=9)!=(bc<=9)):triggers.append('bound_vs_split')
  if s<=4.5 and not same:triggers.append('close_pair_split_by_partition')
  if same and s>=6 and s>3*max(p['split_fixed_mean'],1e-9):triggers.append('within_cluster_local_concentration')
  if not triggers:continue
  known=key(p['image_id'],p['condition'],p['id_a'],p['id_b']) in known_pairs
  candidates.append({**{k:p[k] for k in ['image_id','code','condition','id_a','id_b','worker_a','worker_b','count_a','count_b','split_cyclic','split_fixed','split_free','bound_cyclic']},'reasons':';'.join(triggers),'pair_has_prior_evidence':known,'image_has_prior_evidence':p['image_id'] in known_images,'priority':1 if 'order_vs_free_correspondence' in triggers or 'bound_vs_split' in triggers else 2 if 'close_pair_split_by_partition' in triggers else 3,'gap':s-fr,'physical_judgment':'unconfirmed','final_cluster_decision':''})
 q=frame(out,'review_backlog.csv',candidates)
 # Extend known-image set to *all referenced* images in supplied queues; do not re-request old images.
 history=json.loads((P/'history_visual_review/all_history_queue.json').read_text())
 if isinstance(history,dict):history=history.get('queue',history.get('items',[]))
 for r in history:
  if r.get('seen_in_previous_materials') or r.get('in_previous_materials') or r.get('previously_referenced'):known_images.add(r.get('image_id'))
 # Also collect exact image_ids recursively from all user/evidence registries (no interpretation of text).
 def collect(x):
  if isinstance(x,dict):
   if 'image_id' in x:known_images.add(x['image_id'])
   for k,vv in x.items():
    if '|' in k and len(k.split('|')[0])>40:known_images.add(k.split('|')[0])
    collect(vv)
  elif isinstance(x,list):
   for vv in x:collect(vv)
 for f in list((src/'analysis_results/human_review_reconciliation_20260918').glob('*.json'))+[P/'inputs/new_six_evidence.json',P/'inputs/key39_source.json']:
  collect(json.loads(f.read_text()))
 fresh=q[~q.image_id.isin(known_images)].sort_values(['priority','gap','code'],ascending=[True,False,True])
 pick=fresh.drop_duplicates(['image_id']).head(6).copy()
 # Four deterministic unflagged image controls; no claim of false-negative validation until examined locally.
 flagged=set(q.image_id);controls=[]
 for p in pair.to_dict('records'):
  if p['image_id'] in known_images|flagged or not np.isfinite(p.get('split_cyclic',np.nan)):continue
  if len(cache[p['image_id']+'|'+p['condition']]['ids'])<3:continue
  if p['condition']!='manual' or not .5<=p['split_cyclic']<=4.5:continue
  controls.append(p)
 if controls:
  c=pd.DataFrame(controls);c['selection_hash']=c.image_id.map(lambda x:__import__('hashlib').sha256((x+'20260920').encode()).hexdigest());c=c.sort_values(['selection_hash','split_cyclic']).drop_duplicates('image_id').head(4)
  c['reasons']='unflagged_control_not_yet_validated';c['priority']=4;c['physical_judgment']='unconfirmed';pick=pd.concat([pick,c[pick.columns.intersection(c.columns)]],ignore_index=True)
 if len(pick):
  endpoints=pd.read_csv(out/'endpoint_correspondences.csv.gz')
  nums=[]
  for r in pick.to_dict('records'):
   sub=endpoints[(endpoints.id_a==r['id_a'])&(endpoints.id_b==r['id_b'])&(endpoints.metric=='split_cyclic')].sort_values('error_deg',ascending=False).head(2)
   nums.append('; '.join(f"{v.role}:原点{v.point_a}→{v.point_b}={v.error_deg:.3f}°" for v in sub.itertuples()))
  pick['point_focus']=nums
 frame(out,'minimal_local_check.csv',pick)
 frame(out,'human_correspondence_template.csv',pd.DataFrame(columns=['image_id','condition','id_a','id_b','role','point_a_1based','point_b_1based','status','reviewer','evidence_source','point_payload_sha_a','point_payload_sha_b','note']))
 writejson(out/'REVIEW_SCOPE.json',{'flagged_pairs':len(q),'flagged_units':q[['image_id','condition']].drop_duplicates().shape[0],'flagged_images':q.image_id.nunique(),'flagged_records':len(set(q.id_a)|set(q.id_b)),'selected_new_pairs':len(pick),'selected_new_images':pick.image_id.nunique(),'known_images_not_re_requested':len(known_images),'new_visual_review_performed':False,'sensitivity_is_not_error_rate':True,'trigger_counts':dict(collections.Counter(x for s in q.reasons for x in s.split(';')))})

if __name__=='__main__':
 r=Path(__file__).resolve().parents[1];run(r,r/'results/release')
