"""Check saved labels against teams, mixture moments, event denominators and summaries."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
D=ROOT/'research/workers/personnel_d10_formation_sensitivity_20261024';F=ROOT/'research/fusion/fusion_common_panel_20261024';C=D.parent/'personnel_mixture_comparison_20261022/configurations';S=D.parent/'personnel_v3_20261021/raw_answer_evidence/taxonomy'
def read(p):return pd.read_csv(p,low_memory=False)
def eq(a,b):np.testing.assert_allclose(np.asarray(a,float),np.asarray(b,float),atol=1e-8,rtol=1e-8,equal_nan=True)
def names(s):return s.split('|')
def vec(ws,labels):
 counts=Counter(labels[w] for w in ws);return '|'.join(f'{c}:{counts[c]}' for c in sorted(counts))
old=read(S/'JOINT_LABELS_LOBO.csv.gz').assign(formation_arm='B8L2_original');new=read(D/'D10_LABELS_FIXED_AND_RESELECTED.csv.gz');new=new[new.heldout_building!='ALL'].assign(formation_arm=lambda x:'D10_'+x.formation_arm)
labels=pd.concat([old,new]);roster={k:g.set_index('worker_id') for k,g in labels.groupby(['condition','heldout_building','formation_arm'])}
panels=read(C/'PANELS_USED.csv').set_index('panel_id');pt=read(C/'PANEL_TEAMS.csv.gz');by_panel={k:g for k,g in pt.groupby('panel_id')}
ep=pd.concat([read(C/f'ENDPOINT_OUTCOMES_{c}.csv.gz') for c in ['manual','semi']]).set_index('team_key',verify_integrity=True)
links=read(D/'COMPOSITION_TEAM_LINKS.csv.gz');expected={};stats=[]
for (p,arm,tier),g in links.groupby(['panel_id','formation_arm','tier'],sort=False):
 panel=panels.loc[p];lab=roster[panel.condition,panel.building,arm][tier+'_label'].to_dict();background=names(panel.background_workers)
 team=by_panel[p];assert len(g)==len(team)==924
 mapping={r.team_key:vec(background+names(r.selected_variable_workers),lab) if all(lab[w]!='unknown' for w in background+names(r.selected_variable_workers)) else None for r in team.itertuples()}
 obs=g.team_key.map(mapping);assert obs.fillna('').equals(g.class_counts.fillna(''))
 expected[p,arm,tier]=mapping
print('All composition vectors matched labels',len(links),flush=True)
# Direct team-level total squares, not author cell-variance combination.
saved=read(D/'COMPOSITION_COMMON_PANEL_SUMMARY.csv')
for r in saved.itertuples():
 other='B8L2_original' if r.formation_arm==r.compared_arm else r.compared_arm
 first=expected[r.panel_id,r.formation_arm,r.tier];second=expected[r.panel_id,other,r.tier]
 keys=[k for k in first if first[k] is not None and second[k] is not None]
 assert len(keys)==r.matched_teams and ep.loc[keys,'failure'].sum()==r.failed
 for metric in ['B8L2','D10']:
  v=ep.loc[keys,metric].dropna();cats=pd.Series({k:first[k] for k in v.index});mean=v.groupby(cats).transform('mean');total=((v-v.mean())**2).sum();between=((mean-v.mean())**2).sum()
  eq(between/total if total>len(v)*1e-20 else np.nan,getattr(r,metric+'_eta2'))
abc=read(D/'ABC_EVENTS.csv.gz')
for (p,arm,tier),g in abc.groupby(['panel_id','formation_arm','tier'],sort=False):
 teams=by_panel[p].set_index('team_key');mapping=expected[p,arm,tier]
 for side in 'ABC':
  assert g['team_'+side].map(mapping).equals(g[side+'_class_counts'])
  assert g['team_'+side].map(teams.selected_variable_workers).map(lambda s:'|'.join(sorted(names(s)))).equals(g[side+'_selected_workers'])
# Recover every preregistered attempt; count qualification with missing labels intact.
coverage=read(D/'ABC_COVERAGE.csv');attempts=0
for (p,m,tier),savedg in coverage.groupby(['panel_id','m','tier']):
 candidate=names(panels.loc[p,'variable_workers']);team=by_panel[p];lookup={tuple(sorted(names(r.selected_variable_workers))):r.team_key for r in team.itertuples()}
 rng=np.random.default_rng(int.from_bytes(hashlib.sha256(f'{p}|m{m}'.encode()).digest()[:8],'big'));ct=Counter()
 for i in range(128):
  w=list(rng.permutation(candidate));common=w[:6-m];blocks=(w[6-m:6],w[6:6+m],w[6+m:6+2*m]);keys=[lookup[tuple(sorted(common+b))] for b in blocks];status=[]
  for arm in ['B8L2_original','D10_fixed_old_model','D10_reselected']:
   v=[expected[p,arm,tier][k] for k in keys];c=Counter(v)
   status.append('unknown_labels' if None in v else 'strict_ABC' if sorted(c.values())==[1,2] else 'all_same' if len(c)==1 else 'all_different')
  ct[tuple(status)]+=1
 expected_ct=Counter({(r.B8L2_original_status,r.D10_fixed_old_model_status,r.D10_reselected_status):r.attempts for r in savedg.itertuples()});assert ct==expected_ct
 attempts+=128
print('ABC qualifications and member vectors passed',attempts,flush=True)
keys=['panel_id','image','building','condition','difficulty','source_domain','n','m','formation_arm','tier']
rows=[]
for metric in ['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','fusion_turn_n','fusion_short_turn_edges']:
 g=abc.groupby(keys,dropna=False).agg(attempts=('attempt','size'),scored=(metric+'_extra_abs','count'),extra_abs=(metric+'_extra_abs','mean'),net_C_minus_B=(metric+'_net_C_minus_B','mean'),B_failures=('B_failure','sum'),C_failures=('C_failure','sum')).reset_index();g['metric']=metric;rows.append(g)
calc=pd.concat(rows).set_index(keys+['metric']).sort_index();savedp=read(D/'ABC_PANEL_EFFECTS.csv').set_index(keys+['metric']).sort_index();savedp=savedp.loc[calc.index]
for c in calc: eq(calc[c],savedp[c])
# All common fusion aggregate cells, including low tails and negative images.
pairs=read(F/'COMMON_TEAM_METRICS.csv');keys=['condition','layer','difficulty','n','comparison','support_domain','metric']
im=pairs.groupby(keys+['image','building']).agg(teams=('team_key','size'),left_value=('left_value','mean'),right_value=('right_value','mean'),delta=('delta','mean')).reset_index()
s=read(F/'COMMON_SCENE_SUMMARY.csv').set_index(keys)
for k,g in im.groupby(keys):
 r=s.loc[k]
 for col,v in [('images',g.image.nunique()),('buildings',g.building.nunique()),('teams',g.teams.sum()),('left_mean',g.left_value.mean()),('right_mean',g.right_value.mean()),('left_p10',g.left_value.quantile(.1)),('right_p10',g.right_value.quantile(.1)),('mean_delta',g.delta.mean()),('positive_images',g.delta.gt(1e-9).sum()),('negative_images',g.delta.lt(-1e-9).sum())]:eq(r[col],v)
structure=read(D/'STRUCTURE_HIGHQ_ROLE_PAIRED.csv');valid=structure[structure.available_B8&structure.available_D10];assert valid.team_key_B8.eq(valid.team_key_D10).all();assert valid.highq_structure_class_B8.eq(valid.highq_structure_class_D10).all()
print(json.dumps({'composition_team_vectors':len(links),'common_composition_panels':len(saved),'preregistered_attempts_across_tiers':attempts,'abc_metric_panel_cells':len(calc),'fusion_summary_cells':len(s),'structure_available_unique_panels':valid.panel_id.nunique()},indent=2),flush=True)
