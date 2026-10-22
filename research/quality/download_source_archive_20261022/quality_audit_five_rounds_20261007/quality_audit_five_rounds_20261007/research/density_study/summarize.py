from core import *
import pandas as pd
from collections import Counter
s=pd.read_csv(OUT/'round_c_fit_status.csv');r=pd.read_csv(OUT/'round_c_reference_comparisons.csv')
inputs=json.load(open(OUT/'round_c_inputs.json'));source={x['record']['id']:x for x in inputs};fits=json.load(open(OUT/'round_c_fit_artifacts.json'));fd={(x['expression_id'],m):v for x in fits for m,v in x['fits'].items()}
# Complete O/E fields from saved geometries, without changing fits or selection.
for i,row in r.iterrows():
 c=source[row.expression_id];g=next(x for x in c['references'] if x['id']==row.reference_id)
 try:
  _,gp=footprint(g);_,ap=footprint(c['record']);_,bp=footprint(fd[row.expression_id,row.method]['record'])
  a=comp.region_metrics(ap,gp);b=comp.region_metrics(bp,gp)
  for k in ['omission_ref','extension_ref']:
   r.at[i,'before_'+k]=a[k];r.at[i,'after_'+k]=b[k];r.at[i,'delta_'+k]=b[k]-a[k]
 except ValueError:pass
r.to_csv(OUT/'round_c_reference_comparisons.csv',index=False,encoding='utf-8-sig')
success=s[s.status=='ok'];both=success.groupby('expression_id').size();both=set(both[both==2].index)
summary=[]
metrics=[c for c in r if c.startswith('delta_')]
for scope,data in [('all_success',r),('matched_success',r[r.expression_id.isin(both)]),('expanded_beyond_prior_49',r[r.source_panel=='expanded_beyond_prior_49'])]:
 for (method,ref),x in data.groupby(['method','reference_version']):
  z=dict(scope=scope,method=method,reference_version=ref,n=len(x),images=x.image.nunique(),buildings=x.building.nunique(),longitude_n=int(x.delta_top_mae_deg.notna().sum()),longitude_images=x[x.delta_top_mae_deg.notna()].image.nunique(),iou_improved=int(sum(x.delta_iou>1e-4)),iou_worsened=int(sum(x.delta_iou < -1e-4)),top_worsened_gt01=int(sum(x.delta_top_mae_deg>.1)),bottom_worsened_gt01=int(sum(x.delta_bottom_mae_deg>.1)),iou_improve_top_worse=int(sum((x.delta_iou>1e-4)&(x.delta_top_mae_deg>.1))))
  for k in metrics:
   z['image_mean_'+k]=float(x.groupby('image')[k].mean().mean());z['building_mean_'+k]=float(x.groupby(['building','image'])[k].mean().groupby('building').mean().mean())
  summary.append(z)
save_csv('round_c_summary.csv',summary)
# Matched paired method difference, keeping each reference version distinct.
paired=[]
for ref,x in r[r.expression_id.isin(both)].groupby('reference_version'):
 left=x[x.method=='equal_node'].set_index(['image','building','expression_id']);right=x[x.method=='continuous_boundary'].set_index(['image','building','expression_id']);d=right[metrics]-left[metrics]
 d=d.reset_index();d['reference_version']=ref;paired.extend(d.to_dict('records'))
save_csv('round_c_matched_method_differences.csv',paired)
per_image=r.groupby(['method','reference_version','image','building'],dropna=False)[metrics].mean().reset_index();per_image.to_csv(OUT/'round_c_per_image.csv',index=False,encoding='utf-8-sig')
per_building=per_image.groupby(['method','reference_version','building'])[metrics].mean().reset_index();per_building.to_csv(OUT/'round_c_per_building.csv',index=False,encoding='utf-8-sig')
small=s[(s.status=='ok') & (s.max_endpoint_angle_move_deg<3)].sort_values('max_bottom_depth_move_h',ascending=False)
small.head(20).to_csv(OUT/'round_c_small_angle_large_depth.csv',index=False,encoding='utf-8-sig')
print('matched successes',len(both));print(pd.DataFrame(summary)[['scope','method','reference_version','n','images','longitude_n','iou_improved','iou_worsened','top_worsened_gt01','image_mean_delta_iou','image_mean_delta_top_mae_deg','image_mean_delta_bottom_mae_deg','image_mean_delta_top3d_symmetric_mean_h','image_mean_delta_floor3d_symmetric_mean_h']].to_string(index=False))
print('small-angle depth worst',small.head(6)[['image','expression_id','method','max_endpoint_angle_move_deg','max_bottom_depth_move_h']].to_string(index=False))
print('fit raw residual maxima',success.groupby('method')[['fit_direction_rms_deg','fit_flat_top_rms_deg']].max().to_dict())
print('preserved',success.nodes_preserved.all(),success.expression_preserved.all())
