from pathlib import Path
import pandas as pd,numpy as np,json,gzip,itertools,sys
root=Path(sys.argv[1]); data=root/'population'; pkg=root/'population_stage04D/research/workers/personnel_population_curves_v2_20261023'; out=root/'population_audit';out.mkdir(exist_ok=True)
metrics=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','reference_node_shortfall','floor_turn5_n','ref_top_pair_mean_deg','ref_bottom_pair_mean_deg','ref_edge_recall_5','source_time_total_seconds','source_time_known_n']
cols=['team_key','member_workers','member_object_ids','k','score_available','score_failure_nonpolicy','endpoint_origin']+metrics
s=pd.read_csv(data/'results/ENDPOINT_SCALARS.csv.gz',usecols=cols,low_memory=False)
l=pd.read_csv(data/'results/PREFIX_TEAM_LINKS.csv.gz');o=pd.read_csv(data/'design/EXACT_ORDER_DESIGN.csv.gz');ann=pd.read_csv(pkg/'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
assert len(s)==318816 and s.team_key.is_unique and len(l)==404082 and len(o)==12398
assert not l.duplicated(['path_id','k']).any() and o.path_id.is_unique
team=dict(zip(s.team_key,s.member_workers.map(lambda x:tuple(sorted(x.split('|'))))))
linkdict={(r.path_id,r.k):r.team_key for r in l.itertuples()}
orders=o.set_index('path_id');checked=0
for r in o.itertuples():
 seq=r.worker_order.split('|');assert len(seq)==len(set(seq))==r.pool_n
 if r.policy!='natural_random':
  b=orders.loc[r.base_path_id].worker_order.split('|');target=set(r.target_members.split('|'))
  assert seq==[w for w in b if w in target]+[w for w in b if w not in target]
 for k in range(1,len(seq)+1):
  assert team[linkdict[(r.path_id,k)]]==tuple(sorted(seq[:k]));checked+=1
print('exact_membership_verified',checked,flush=True)
meta=['path_id','pool_n','image','image_id','condition','layer','building','source_time_known_n']
d=l.merge(o[meta].rename(columns={'source_time_known_n':'pool_time_known'}),on='path_id',validate='many_to_one').merge(s.drop(columns=['k','member_workers','member_object_ids']),on='team_key',validate='many_to_one').merge(ann[['image','difficulty_coarse']],on='image',validate='many_to_one')
d.rename(columns={'difficulty_coarse':'difficulty'},inplace=True)
d.loc[d.source_time_known_n!=d.k,'source_time_total_seconds']=np.nan
assert d.B8L2.notna().equals(d.score_available)
natural=d[d.policy=='natural_random'].copy(); assert len(natural)==175032
door_full=natural[(natural.layer=='doorway_manual')&(natural.pool_n>=20)&(natural.k==natural.pool_n)]
assert door_full.groupby('pool_id').team_key.nunique().eq(1).all()
door_full=door_full.drop_duplicates('pool_id')[['pool_id','image','pool_n','team_key','score_available','B8L2']]
assert len(door_full)==17 and int((~door_full.score_available).sum())==6
door_full.to_csv(out/'DOORWAY_FULL_POOL.csv',index=False)
curves=natural.groupby(['pool_id','image','condition','layer','building','difficulty','pool_n','k'],dropna=False).agg(Q=('B8L2','mean'),SD=('B8L2','std'),P10=('B8L2',lambda x:x.quantile(.1)),failure=('score_available',lambda x:1-x.mean()),paths=('team_key','size')).reset_index()
v=pd.read_csv(data/'results/PREFIX_GEOMETRY_VARIATION.csv.gz');v=v[v.policy.eq('natural_random')]
curves=curves.merge(v[['pool_id','k','V_floor_mean']],on=['pool_id','k'],validate='one_to_one')
fixed=curves[curves.pool_n>=20]
table=fixed.groupby(['condition','layer','difficulty','k']).agg(images=('image','nunique'),Q=('Q','mean'),SD=('SD','mean'),P10=('P10','mean'),failure=('failure','mean'),V=('V_floor_mean','mean')).reset_index()
table.to_csv(out/'NATURAL_RECOMPUTED.csv',index=False)
print(table[table.k.isin([1,3,6,10,20])].to_string(index=False),flush=True)
changes=[]
for a,b in [(3,6),(3,20),(10,20)]:
 t=fixed[fixed.k==a].merge(fixed[fixed.k==b],on='pool_id',suffixes=('_a','_b'),validate='one_to_one');t['delta']=t.Q_b-t.Q_a
 for key,g in t.groupby(['condition_a','layer_a','difficulty_a']):
  changes.append(dict(zip(['condition','layer','difficulty'],key),start=a,end=b,images=len(g),q_delta=g.delta.mean(),up=int((g.delta>0).sum()),buildings=g.building_a.nunique(),buildings_up=int((g.groupby('building_a').delta.mean()>0).sum()),v_down=int((g.V_floor_mean_b<g.V_floor_mean_a).sum())))
pd.DataFrame(changes).to_csv(out/'NATURAL_INTERVAL_RECOMPUTED.csv',index=False)
print('intervals',pd.DataFrame(changes).query("difficulty=='困难'").to_dict('records'),flush=True)
# Exact paired strategy events independently reconstructed; no truncated event input is consumed.
b=natural[['path_id','k','team_key',*metrics,'score_available']].rename(columns={'path_id':'base_path_id','team_key':'natural_team_key',**{m:m+'_natural' for m in metrics+['score_available']}})
p=d[d.policy!='natural_random'].merge(b,on=['base_path_id','k'],validate='many_to_one')
for m in metrics:p[m+'_delta']=p[m]-p[m+'_natural']
p['logtime']=np.log(p.source_time_total_seconds/p.source_time_total_seconds_natural)
p['qt_q']=p.B8L2_delta.where(p.logtime.notna());p['qt_logtime']=p.logtime.where(p.B8L2_delta.notna())
assert len(p)==229050
f=p[p.k==p.pool_n];assert (f.team_key==f.natural_team_key).all() and (f.B8L2_delta.dropna()==0).all()
common=set(o[o.policy!='natural_random'].groupby('pool_id').policy.nunique().loc[lambda a:a==4].index)
x=p[p.pool_id.isin(common)&(p.pool_n>=20)&p.layer.str.startswith('ordinary')&p.k.between(3,p.pool_n//2)].copy()
gkeys=['condition','layer','pool_id','image','building','difficulty','policy','pool_n','pool_time_known','k']
mc=[m+'_delta' for m in metrics if m!='source_time_known_n']+['logtime','qt_q','qt_logtime']
per_k=x.groupby(gkeys,dropna=False)[mc].mean().reset_index()
# P10 is per-arm distribution, separately scored, as in report.
qq=x.groupby(gkeys,dropna=False)[['B8L2','B8L2_natural']].quantile(.1).reset_index();qq['p10_delta']=qq.B8L2-qq.B8L2_natural
per_k=per_k.merge(qq[gkeys+['p10_delta']],on=gkeys);mc+=['p10_delta']
pi=per_k.groupby(gkeys[:-1],dropna=False)[mc].mean().reset_index();pi.to_csv(out/'POLICY_PER_IMAGE_RECOMPUTED.csv',index=False)
rows=[]
for subset,fr in [('common',pi),('complete_time',pi[pi.pool_n==pi.pool_time_known])]:
 for key,g in fr.groupby(['condition','policy']):
  rows.append(dict(condition=key[0],policy=key[1],subset=subset,images=len(g),buildings=g.building.nunique(),q=g.B8L2_delta.mean(),up=int(g.B8L2_delta.gt(0).sum()),buildings_up=int(g.groupby('building').B8L2_delta.mean().gt(0).sum()),p10=g.p10_delta.mean(),qt_q=g.qt_q.mean(),time_pct=np.expm1(g.qt_logtime.mean())*100))
summary=pd.DataFrame(rows);summary.to_csv(out/'POLICY_RECOMPUTED.csv',index=False);print(summary.to_string(index=False),flush=True)
print('policy_difficulty',pi.groupby(['condition','difficulty','policy']).B8L2_delta.agg(['size','mean']).to_string(),flush=True)
# Bad-tail and failure uses all attempted paired prefixes.
q=x[(x.condition=='manual')&(x.policy=='joint_highq_first')]
print('highq_risks',len(q),int((~q.score_available_natural).sum()),int((~q.score_available).sum()),int(q.B8L2_delta.notna().sum()),int(q.B8L2_delta.lt(-5).sum()),flush=True)
# Persist a small, complete key/score audit table so missing delivery tail can be diagnosed without rerunning fusion.
p[['pool_id','path_id','base_path_id','policy','k','team_key','natural_team_key','B8L2','B8L2_natural','B8L2_delta']].to_csv(out/'POLICY_REBUILT_KEYS_AND_Q.csv.gz',index=False)
# Check label/role consumption against accepted local input without hashing or retraining.
for name in ['ALL_METHOD_LABELS_LOBO.csv.gz','FOLD_CLASS_DEFINITIONS.csv']:
 a=pd.read_csv(pkg/'inputs'/name);b=pd.read_csv(Path('research/workers/personnel_mixture_comparison_20261022/inputs/four_main')/name)
 pd.testing.assert_frame_equal(a,b);print('same_frozen_input',name,len(a),flush=True)
labels=pd.read_csv(pkg/'inputs/ALL_METHOD_LABELS_LOBO.csv.gz');definitions=pd.read_csv(pkg/'inputs/FOLD_CLASS_DEFINITIONS.csv');cap=pd.read_csv(pkg/'design/POLICY_POOL_CAPACITY.csv');roles=pd.read_csv(pkg/'design/LOBO_PRIORITY_ROLE_DEFINITIONS.csv')
specs={'structure_moreturn_first':('V3_BEHAVIOR','fine','turn_history_mean',False),'structure_dominant_first':('V3_BEHAVIOR','fine','people',False),'joint_highq_first':('V3_JOINT_QT','coarse','q_history_mean',False),'joint_fast_first':('V3_JOINT_QT','coarse','t_history_mean',True)}
for r in roles.itertuples():
 method,tier,col,asc=specs[r.policy];g=definitions[(definitions.method==method)&(definitions.tier==tier)&(definitions.condition==r.condition)&(definitions.heldout_building==r.heldout_building)].dropna(subset=[col]);cols2=[col,'class_id'] if col=='people' else [col,'people','class_id'];asc2=[asc,True] if col=='people' else [asc,False,True]
 assert g.sort_values(cols2,ascending=asc2).iloc[0].class_id==r.class_id
for r in cap.itertuples():
 method,tier,_,_=specs[r.policy];pool=set(o[o.pool_id==r.pool_id].iloc[0].worker_order.split('|'))
 lab=labels[(labels.method==method)&(labels.condition==r.condition)&(labels.heldout_building==r.building)&labels.known]
 target=pool&set(lab.loc[lab[tier+'_label']==r.target_class,'worker_id']);saved=set(str(r.target_members).split('|'))-{'nan',''};assert target==saved
print('role_and_capacity_verified',len(roles),len(cap),flush=True)
checks={'endpoints':len(s),'orders':len(o),'prefixes':len(l),'membership_verified':checked,'natural_prefixes':len(natural),'policy_prefixes':len(p),'full_pool_pairs':len(f),'label_rows':len(labels),'roles':len(roles),'capacity_rows':len(cap)}
(out/'CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
print('DONE',checks,flush=True)
