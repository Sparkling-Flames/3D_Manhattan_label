"""106-label image-side feedback only. No human reference is read."""
import itertools
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *
from tools.thesis_main.analysis.image_portrait.pro_models import archive,round_bounds,corners_bounds,pair_median
from tools.thesis_main.analysis.image_portrait.pro_core import _d_mask

def main():
 d=pd.read_csv(O/'images/labels106.csv');rows=[];fail=[]
 for image in d.image_id:
  try:
   h=archive(B/'models/hohonet'/f'{image}.npz');b=archive(B/'models/bilayout'/f'{image}.npz');u=archive(B/'models/ulayout'/f'{image}.geometry.npz')
   c={k:[]for k in ['hohonet','bi_enclosed','bi_extended','ulayout']};pcs={k:[]for k in list(c)[:3]};disp={k:[]for k in pcs};height=[]
   for yaw in [0,90,180,270]:
    c['hohonet'].append(round_bounds((h[f'yaw{yaw}__raw__bon']/np.pi+.5)*512-.5));c['ulayout'].append(round_bounds(u[f'yaw{yaw}_boundary_pixels_float']))
    r=float(b[f'yaw{yaw}__raw__ratio'][0]);xs=(np.arange(256)+.5)*4-.5
    for name,key in [('bi_enclosed','new_depth'),('bi_extended','depth')]:
     dep=b[f'yaw{yaw}__raw__{key}'];assert np.all(dep>0)and r>0
     bands=np.array([(np.arctan2(-r,dep)/np.pi+.5)*512-.5,(np.arctan2(1,dep)/np.pi+.5)*512-.5]);c[name].append(round_bounds(np.array([np.interp(np.arange(1024),xs,band,period=1024)for band in bands])))
    for name,arr in [('hohonet',h[f'yaw{yaw}__post__cor_id']),('bi_enclosed',b[f'yaw{yaw}__post__corners_enclosed']),('bi_extended',b[f'yaw{yaw}__post__corners_extended'])]:
     bounds,g=corners_bounds(arr);pcs[name].append(len(arr));disp[name].append(_d_mask(c[name][-1],bounds)if bounds is not None else np.nan)
    height.append(abs(float(b[f'yaw{yaw}__raw__height_enclosed'][0])-float(b[f'yaw{yaw}__raw__height_extended'][0])))
   z=dict(image_id=image)
   for name in c:z[name+'_rotation']=pair_median(c[name])
   for name in pcs:
    z[name+'_points']=np.mean(pcs[name]);z[name+'_topology_change']=int(len(set(pcs[name]))>1);z[name+'_post_displacement']=np.nanmedian(disp[name])
   for a,bb in itertools.combinations(c,2):z[a+'_vs_'+bb]=np.median([_d_mask(x,y)for x,y in zip(c[a],c[bb])])
   z['bi_height_disagreement']=np.mean(height);z['hohonet_warning_phases']=sum(bool(x.get('postprocess_warning'))for x in load(B/'models/hohonet'/f'{image}.json')['phases'])
   # Confidence and relative shape only; independent single-face depths have no common metric scale.
   da=archive(B/'models/da3'/f'{image}.geometry.npz');conf=[];spread=[]
   for face in FACES:
    dep=da[face+'_depth_stride8'];cf=da[face+'_depth_conf_stride8'];assert np.all(dep>0)
    ld=np.log(dep);spread.append(float(np.quantile(ld,.9)-np.quantile(ld,.1)));conf.append(float(np.median(cf)))
   z['da3_confidence_median']=np.median(conf);z['da3_confidence_face_variation']=np.std(conf);z['da3_log_shape_spread_median']=np.median(spread);z['da3_log_shape_face_variation']=np.std(spread)
   rows.append(z)
  except Exception as e:fail.append(dict(image_id=image,error=repr(e)));raise
 f=csv('models/numeric_feedback106.csv',rows);csv('models/feedback_failures.csv',fail)
 cols=[c for c in f if c!='image_id'];spec={'feedback__all':cols,'feedback__point_counts':[x for x in cols if x.endswith('_points')],'feedback__rotation':[x for x in cols if x.endswith('_rotation')],'feedback__between_models':[x for x in cols if '_vs_'in x],'feedback__bi_scope':[x for x in cols if x.startswith('bi_')and('_vs_bi_'in x or 'height_'in x)],'feedback__da3':[x for x in cols if x.startswith('da3_')]}
 inv=pd.read_csv(O/'models/feature_inventory.csv');extra=[]
 for name,cc in spec.items():
  assert cc and np.isfinite(f[cc].to_numpy(float)).all();np.save(O/'cache'/f'{name}.npy',f[cc].to_numpy(np.float32));extra.append(dict(feature=name,dimension=len(cc),n_images=len(f),model='numeric_feedback',pooling='explicit per-panorama summaries; not truth or convergence',candidate_kind='followup_feedback'))
 inv=inv[~inv.feature.str.startswith('feedback__')];csv('models/feature_inventory.csv',pd.concat([inv,pd.DataFrame(extra)],ignore_index=True));savej('method/feedback_columns.json',spec)
 print('FEEDBACK',len(f),len(spec),flush=True)
if __name__=='__main__':main()
