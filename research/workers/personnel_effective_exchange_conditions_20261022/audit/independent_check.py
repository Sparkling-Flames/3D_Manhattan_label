from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,argparse
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,default=ROOT/'sources/expansion/expanded_blocks/analysis');args=ap.parse_args();SRC=args.source_dir
def delivered(name):
 p=SRC/(name+'.csv')
 return p if p.exists() else SRC/(name+'.csv.gz')
p=pd.read_csv(delivered('PANEL_COMPLETE_RESULTS_FINAL_COMPLETE'),low_memory=False)
s=pd.read_csv(delivered('FINAL_CORE_SUMMARY'),low_memory=False)
errors=[]; checks=0; maximum=0.; numerical=[]
for sid,g in s.groupby('summary_id'):
 r=g.iloc[0];x=p.copy()
 for key in ['condition','layer','method_id','tier','source_domain','n','m','parent_fixed']:
  x=x[x[key].fillna('<NA>').eq(r[key] if pd.notna(r[key]) else '<NA>')]
 if r.cohort!='all_images':x=x[x.seed_cohort.eq(r.cohort)]
 if r.difficulty_stratum!='ALL':x=x[x.difficulty.eq(r.difficulty_stratum)]
 if r['view']=='class_direction':
  direct=np.where(x.method_id.str.startswith('V3_'),x.source_role+' -> '+x.target_role,x.source_class+' -> '+x.target_class);x=x[direct==r.direction]
 elif r['view']=='training_turn_direction':x=x[x.training_turn_direction.fillna('unknown').eq(r.direction)]
 elif r['view']=='family_and_turn':x=x[(x.selected_family.fillna('legacy_fixed_method')+' / '+x.training_turn_direction.fillna('unknown')).eq(r.direction)]
 metrics=list(g.metric); bg=x.groupby(['building','image','background_id'],dropna=False)[metrics].mean(); im=bg.groupby(level=['building','image']).mean(); bd=im.groupby(level=['building']).mean()
 support={'complete_panels':len(x),'complete_events':x.events.sum(),'complete_images':x.image.nunique(),'complete_buildings':x.building.nunique(),'complete_backgrounds':x.background_id.nunique()}
 for _,row in g.iterrows():
  met=row.metric; vals={**support}
  for prefix,frame in [('background',bg),('image',im),('building',bd)]:
   v=frame[met].dropna();vals.update({prefix+'_mean':v.mean(),prefix+'_median':v.median(),'valid_'+prefix+'s':len(v),'positive_'+prefix+'s':(v>1e-10).sum(),'negative_'+prefix+'s':(v< -1e-10).sum(),'zero_'+prefix+'s':(v.abs()<=1e-10).sum()})
  n=x[met+'__valid'].fillna(0);ok=x[met].notna()&(n>0)
  vals['valid_events']=n[ok].sum();vals['event_weighted_mean']=(x.loc[ok,met]*n[ok]).sum()/n[ok].sum() if ok.any() else np.nan
  for field,v in vals.items():
   expected=row[field];checks+=1
   if pd.isna(expected) and pd.isna(v):continue
   err=abs(float(expected)-float(v));maximum=max(maximum,err)
   if not np.isfinite(err) or err>1e-9:errors.append([sid,met,field,float(v),float(expected)])
  numerical.append({'summary_id':sid,'metric':met,'independent_building_mean':vals['building_mean']})
res={'scope':'Independent reaggregation of all delivered expanded panel summaries; no fusion/scoring refit or all-raw-event recomputation','panels':len(p),'cells':p.cell_id.nunique(),'oriented_events':int(p.events.sum()),'summary_metric_rows':len(s),'scalar_checks':checks,'max_absolute_error':maximum,'mismatches':errors}
(ROOT/'INDEPENDENT_EXPANSION_CHECK.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
pd.DataFrame(numerical).to_csv(ROOT/'independent_expansion_means.csv',index=False)
print(json.dumps({k:v for k,v in res.items() if k!='mismatches'},ensure_ascii=False), 'mismatches=',len(errors))
