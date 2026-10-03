"""Independent saved-field and prefix geometry checks; never changes source inputs."""
import independent_verify as a
import numpy as np
import math,time,warnings
from collections import Counter,defaultdict
from shapely.ops import unary_union
from shapely.geometry import Polygon
D=a.D;O=a.O
rows=a.readc(D/'curves.csv');idx={(r['image'],r['method'],r['version'],int(r['k'])):r for r in rows}
data=a.readj(D/'input.json');out=[];geo=[];notices=[]
for im in data['images']:
 rs=sorted([r for r in im['annotations'] if a.eligible(r)],key=lambda x:x['id']);n=len(rs)
 refs={r['version']:Polygon(r['footprint']) for r in im['references'] if r['footprint'] is not None};polys=[Polygon(r['footprint']) for r in rs]
 with warnings.catch_warnings(record=True) as caught:
  warnings.simplefilter('always');basis=a.make_basis(polys,refs);p,area,overlap,_=basis;s=np.array([int(x).bit_count() for x in p]);denom={k:math.comb(n,k) for k in range(1,n+1)}
  for k in range(1,n+1):
   for method in a.METHODS:
    t=(k+1)//2 if method=='mv50' else k//2+1
    q={v:sum(math.comb(int(v),j)*math.comb(n-int(v),k-j) for j in range(max(t,k-n+int(v)),min(k,int(v))+1))/denom[k] for v in set(s)}
    qq=np.array([q[v] for v in s]);ar=area@qq
    for v,g in refs.items():
     it=overlap[v]@qq;r=idx[im['code'],method,v,k];fields=dict(expected_area_h2=ar,expected_intersection_h2=it,expected_omission_h2=g.area-it,expected_extension_h2=ar-it)
     for field,value in fields.items():out.append(dict(image=im['code'],k=k,method=method,version=v,field=field,error=float(value)-float(r[field])))
  # four representative prefixes and an additional seeded arbitrary subset, independently re-cut.
  subsets=[list(range(k)) for k in sorted({1,min(2,n),max(1,n//2),n})]
  if n>9:subsets.append(sorted(np.random.default_rng(n+10603).choice(n,8,replace=False)))
  for js in subsets:
   k=len(js);small=a.make_basis([polys[j] for j in js],refs);off=a.scores(basis,refs,np.array([sum(1<<int(j) for j in js)],np.uint32),k);direct=a.scores(small,refs,np.array([(1<<k)-1],np.uint32),k)
   geo.append(dict(image=im['code'],k=k,subset=','.join(map(str,js)),max_iou_difference=max(float(abs(off[key][0]-direct[key][0])) for key in off)))
 notices.extend(dict(image=im['code'],message=str(w.message)) for w in caught)
a.writec('area_field_checks.csv',out);a.writec('prefix_recut_checks.csv',geo);a.writej('additional_checks_summary.json',dict(area_field_comparisons=len(out),area_field_max_abs_error=max(abs(x['error']) for x in out),prefix_subsets=len(geo),prefix_max_iou_difference=max(x['max_iou_difference'] for x in geo),warnings=notices))
# Fixed33 image and building heterogeneity: descriptive only, no population test.
means=a.readc(O/'paired_contrast_per_image.csv');meta={im['code']:im for im in data['images']};stats=[]
for method in a.METHODS:
 vals=[r for r in means if r['seed']=='new' and r['method']==method];bs=defaultdict(list)
 for r in vals:bs[meta[r['image']]['building']].append(float(r['mean_gain']))
 stats.append(dict(method=method,image_positive=sum(float(r['mean_gain'])>0 for r in vals),image_negative=sum(float(r['mean_gain'])<0 for r in vals),image_min=min(float(r['mean_gain']) for r in vals),image_max=max(float(r['mean_gain']) for r in vals),building_equal_weight_mean=float(np.mean([np.mean(x) for x in bs.values()])),building_means={b:dict(images=len(v),mean=float(np.mean(v))) for b,v in bs.items()}))
a.writej('fixed33_heterogeneity.json',stats)
print((O/'additional_checks_summary.json').read_text())
