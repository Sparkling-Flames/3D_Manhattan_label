from pathlib import Path
import pandas as pd,numpy as np,json
B=Path(__file__).parent/'extracted/HOHONET_same_room_20261021'; out={}
def read(f):return pd.read_csv(B/f)
p=read('room_similarity/tables/direct_pair_similarity.csv');p=p[(p.condition=='manual')&(p.origin=='all')&(p.metric=='B8L2')&(p.layer=='ordinary')&p.scope_comparable&~p.substantive_conflict&(p.n_common>=4)]
out['scope']={'pairs':len(p),'images':len(set(p.image_a)|set(p.image_b)),'buildings':p.building_id.nunique(),'groups':len(set('|'.join(p.user_group_ids).split('|')))}
out['room_gaps_pair']=p[['actual_abs_gap','common_abs_gap']].mean().to_dict();out['room_gaps_building']=p.groupby('building_id')[['actual_abs_gap','common_abs_gap']].mean().mean().to_dict()
d=read('room_similarity/tables/direct_mean_prediction_values.csv.gz');d=d[d.metric=='B8L2'];out['mean_prediction']={}
for m in ['external_image_mean','outside_peer_roster_mean','source_mean','peer_adjusted_source']:
 x=d.assign(ae=(d[m]-d.actual).abs());out['mean_prediction'][m]=x.groupby(['building_id','target_image']).ae.mean().groupby('building_id').mean().mean()
s=read('personal_similarity/direct_pair_workers_with_class.csv.gz');s=s[(s.condition=='manual')&(s.layer=='ordinary')&s.scope_comparable&~s.substantive_conflict];w=1/(s.groupby('building').pair_id.transform('nunique')*s.groupby('pair_id').worker_id.transform('size')*s.building.nunique());out['person_scope']={'rows':len(s),'people':s.worker_id.nunique()};out['corr']={}
for pre in ['Q','relative','surprise']:
 a=np.r_[s[pre+'_a'],s[pre+'_b']];b=np.r_[s[pre+'_b'],s[pre+'_a']];ww=np.r_[w,w];ok=np.isfinite(a)&np.isfinite(b);a,b,ww=a[ok],b[ok],ww[ok];ww/=ww.sum();a-=ww@a;b-=ww@b;out['corr'][pre]=sum(ww*a*b)/np.sqrt(sum(ww*a*a)*sum(ww*b*b))
out['residual_identity_error']=max(abs(s.surprise_a-(s.relative_a-s.external_theta)).max(),abs(s.surprise_b-(s.relative_b-s.external_theta)).max())
d=read('personal_similarity/main_prediction_rows_wide.csv.gz');d=d[d.metric=='B8L2'];out['personal_prediction']={}
for budget,stage in [('single_direct','single'),('single_matched','single'),('majority','minimum_majority'),('majority','maximum_history')]:
 x=d[d.budget==budget].copy()
 if stage=='minimum_majority':x=x[x.m==x.N//2+1]
 if stage=='maximum_history':x=x[x.m==x.N-1]
 if x.empty:continue
 out['personal_prediction'][budget+'_'+stage]={}
 for m in ['external_abs','own_source','public_external','public_external_halfown','public_external_halfclass']:
  z=x.assign(ae=(x[m]-x.actual).abs());v=z.groupby(['building','target_image','group_id','worker_id','m']).ae.mean().groupby(['building','target_image','group_id','m']).mean().groupby(['building','target_image']).mean().groupby('building').mean().mean();out['personal_prediction'][budget+'_'+stage][m]=v
s=read('native_teams/SWAP_EVENTS.csv.gz');out['events']={'rows':len(s),'unique_event':s.event_id.nunique(),'net_definition_max_error':abs(s.net_B8L2-(s.C_B8L2-s.B_B8L2)).max()};out['swap']={}
x=s[(s.condition=='manual')&(s.layer=='ordinary_manual')&s.scope_comparable&(s.n==5)&(s.m==1)&(s.tier=='primary_coarse_class')]
for k,z in x.groupby(['design','outgoing_class','incoming_class']):out['swap']['|'.join(k)]=z.groupby(['building','image']).net_B8L2.mean().groupby('building').mean().mean()
x=read('room_similarity/tables/matched_unknown_directions.csv');out['matched']={}
for k,z in x[x.metric=='B8L2'].groupby(['subset','panel']):out['matched']['|'.join(k)]=z.groupby('building_id').gain.mean().mean()
x=read('native_teams/POLICY_BY_IMAGE.csv.gz');x=x[(x.condition=='manual')&(x.layer=='ordinary_manual')&x.scope_comparable&(x.n==5)];out['team']={}
for k,z in x.groupby(['domain','policy']):
 if k[1] in ['outside_Q','source_Q','outside_Q_outside_T_fast','outside_Q_source_T_fast']:out['team']['|'.join(k)]=z.groupby('building')[['B8L2','loss_over5','log_activity_ratio']].mean().mean().to_dict()
(Path(__file__).parent/'verified_numbers.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
