from pathlib import Path
import pandas as pd,numpy as np,json
P=Path('/workspace/shared/composition_audit_20261019/extracted/personnel_composition_study_20261019/analysis/composition');O=Path(__file__).parent
I=pd.read_csv(P/'frozen_grid_results/frozen_contrasts_per_image.csv.gz'); A=pd.read_csv(P/'frozen_grid_results/frozen_contrasts_aggregate.csv.gz');errors=[]
for r in A.to_dict('records'):
 g=I[(I.stage==r['stage'])&(I.contrast_id==r['contrast_id'])]
 if r['reported_difficulty']!='all':g=g[g.difficulty==r['reported_difficulty']]
 b=g.groupby('building').B8L2_mean_change.mean()
 checks={'paired_images':len(g),'quality_paired_images':g.B8L2_mean_change.notna().sum(),'paired_buildings':g.building.nunique(),'building_B8L2_change_mean':b.mean(),'image_B8L2_change_mean':g.B8L2_mean_change.mean(),'positive_gt0_images':(g.B8L2_mean_change>0).sum(),'negative_ltminus0_images':(g.B8L2_mean_change<0).sum(),'positive_buildings':(b>0).sum(),'negative_buildings':(b<0).sum()}
 for c,v in checks.items():
  if not np.isclose(v,r[c],rtol=1e-8,atol=1e-8,equal_nan=True):errors.append(dict(stage=r['stage'],contrast=r['contrast_id'],field=c,expected=float(v),reported=r[c]))
N=[];nerrors=[]
for phase in ['discovery','validation']:
 p=pd.read_csv(P/f'nested_{phase}/nested_points.csv.gz');t=pd.read_csv(P/f'nested_{phase}/nested_transitions.csv.gz');s=pd.read_csv(P/f'nested_{phase}/nested_summary.csv');points=p.set_index(['chain_id','team_key'])
 for r in t.to_dict('records'):
  a=points.loc[(r['chain_id'],r['before_team'])];b=points.loc[(r['chain_id'],r['after_team'])];aw=set(a.member_workers.split('|'));bw=set(b.member_workers.split('|'))
  if not aw<bw or len(bw-aw)!=1:nerrors.append('not_nested')
  if not np.isclose(b.B8L2-a.B8L2,r['Q_change'],atol=1e-8,equal_nan=True):nerrors.append('Q_difference')
  if r['threshold_increase']!=b.minimum_support-a.minimum_support:nerrors.append('threshold_delta')
 for r in s.to_dict('records'):
  g=t[(t.method_id==r['method_id'])&(t.domain==r['domain'])&(t.fixed_n==r['fixed_n'])&(t.tag==r['tag'])];val=g.groupby(['building','image']).Q_change.mean().groupby(level=0).mean().mean()
  if not np.isclose(val,r['Q_change_building_mean'],atol=1e-8,equal_nan=True):nerrors.append('mean')
  if r['tag']=='critical_2m_to_2m1':N.append(dict(phase=phase,method=r['method_id'],m=r['fixed_n'],images=r['images'],buildings=r['buildings'],effect=val,transitions=len(g),positive=int((g.Q_change>0).sum()),negative=int((g.Q_change<0).sum()),Q_missing=int(g.Q_change.isna().sum()),threshold_increases=g.threshold_increase.unique().tolist()))
result=dict(aggregate_rows_checked=len(A),aggregate_errors=errors,duplicate_image_contrasts=int(I.duplicated(['stage','contrast_id','image']).sum()),nested_errors=nerrors,nested_critical=N)
(O/'full_table_checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,indent=2,ensure_ascii=False))
