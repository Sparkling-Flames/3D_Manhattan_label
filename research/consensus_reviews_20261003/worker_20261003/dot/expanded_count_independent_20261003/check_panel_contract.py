import independent_verify as a
from collections import Counter
import numpy as np
ims=a.readj(a.D/'input.json')['images'];meta={x['code']:x for x in ims};counts={x['code']:sum(a.eligible(r) for r in x['annotations']) for x in ims};paired={x['code'] for x in ims if any(r['version']=='manual_revision' and r['footprint'] is not None for r in x['references'])}
rows=a.readc(a.D/'curves.csv');index={(r['image'],r['method'],r['version'],int(r['k'])):r for r in rows};assert len(index)==len(rows)
for x in ims:
 for v in [r['version'] for r in x['references'] if r['footprint'] is not None]:
  for m in a.METHODS:assert {int(r['k']) for r in rows if (r['image'],r['method'],r['version'])==(x['code'],m,v)}==set(range(1,counts[x['code']]+1))
summary=a.readc(a.D/'fixed_panel_curves.csv');maxerr=0;series={}
for r in summary:
 lim=int(r['panel_max_k']);p={i for i,n in counts.items() if n>=lim};c=r['cohort'];ds=('简单','中等','困难','未定','未记录')
 if c=='全部':expected=p
 elif c=='已标三档':expected={i for i in p if meta[i]['difficulty'] in ds[:3]}
 elif c=='非困难（已标）':expected={i for i in p if meta[i]['difficulty'] in ds[:2]}
 elif c=='双参考配对':expected=p & paired
 elif c in ds:expected={i for i in p if meta[i]['difficulty']==c}
 elif c.startswith('uNb内_'):expected={i for i in p if meta[i]['building']=='uNb9QFRL6hY' and meta[i]['difficulty']==c.split('_')[1]}
 else:raise ValueError(c)
 assert sorted(expected)==r['images'].split('|') and len(expected)==int(r['image_n'])
 assert len({meta[i]['building'] for i in expected})==int(r['building_n'])
 sk=(lim,c,r['version'],r['method']);series.setdefault(sk,set()).add(int(r['k']))
 kk=int(r['k']);vals=[index[i,r['method'],r['version'],kk] for i in sorted(expected)]
 base=[index[i,r['method'],r['version'],1] for i in sorted(expected)]
 def mean(field):return np.mean([float(v[field]) for v in vals])
 tested=dict(iou_mean=mean('iou_mean'),gain_from_one=mean('iou_mean')-np.mean([float(v['iou_mean']) for v in base]),mc_error_bound=mean('mc_error_bound'),gain_mc_error_bound=mean('mc_error_bound'))
 for field in ('omission','extension'):
  tested[field+'_fraction']=np.mean([float(v['expected_'+field+'_h2'])/(float(v['expected_omission_h2'])+float(v['expected_intersection_h2'])) for v in vals])
 maxerr=max(maxerr,max(abs(x-float(r[k])) for k,x in tested.items()))
assert all(ks==set(range(1,sk[0]+1)) for sk,ks in series.items())
b=[r for r in summary if r['panel_max_k']=='20' and r['cohort']=='全部' and r['method']=='mv50' and r['k'] in ('8','20')];bound=sum(float(x['mc_error_bound']) for x in b)
a.writej('fixed_panel_contract_checks.json',dict(curve_keys=len(index),fixed_panel_rows=len(summary),fixed_series=len(series),all_expected_images_match=True,all_denominators_constant=True,max_abs_field_difference=float(maxerr),source_fixed33_8_to_20_bound=bound))
print((a.O/'fixed_panel_contract_checks.json').read_text())
