"""DINO输入空间描述性检查；不读取真人结果，不用于选层或推断收敛。"""
import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[4]/'analysis_results/image_portrait_20260914_v1'
rows=[json.loads(s) for s in (root/'metadata/images.jsonl').read_text(encoding='utf8').splitlines()]
layers=(3,6,9,11,12)
features={str(n):[] for n in layers}; cube=[]; cls=[]
for row in rows:
 with np.load(root/'models/dinov3'/f"{row['image_id']}.features.npz",allow_pickle=False) as z:
  assert z['image_ids'].tolist()==[row['image_id']]
  for n in layers: features[str(n)].append(z[f'panorama_block{n}_patch_global'][:768])
  faces=np.stack([z[f'{f}_block12_patch_global'][:768] for f in ('front','right','back','left','up','down')])
  faces=faces/np.linalg.norm(faces,axis=1,keepdims=True)
  cube.append(faces.mean(0)); cls.append(z['panorama_block12_cls_global'])
features.update(cube12=cube,cls12=cls)
near={}; report={}
buildings=np.array([r['building'] for r in rows])
for name,values in features.items():
 x=np.asarray(values,dtype=np.float64)
 assert x.shape==(648,768) and np.isfinite(x).all()
 norms=np.linalg.norm(x,axis=1); assert (norms>0).all()
 x=x/norms[:,None]
 s=x@x.T; np.fill_diagonal(s,-np.inf)
 nn=np.argsort(-s,axis=1,kind='stable')[:,:5]; near[name]=nn
 pairs=s[np.triu_indices(648,1)]
 report[name]=dict(pairwise_cosine_quantiles=np.quantile(pairs,[.1,.5,.9]).tolist(),same_building_top5_fraction=float((buildings[nn]==buildings[:,None]).mean()))
for name in features:
 report[name]['top5_overlap_with_panorama_block12']=float(np.mean([len(set(a)&set(b))/5 for a,b in zip(near[name],near['12'])]))
counts=np.unique(buildings,return_counts=True)[1]
result=dict(status='descriptive_only',images=648,building_ids=len(counts),same_building_random_other_image_probability=float(sum(counts*(counts-1))/(648*647)),
 method='All 648 inputs, no human outcomes. Cosine nearest5 excluding self. Panorama patch channel means only (first768 of global), not std or local16. cube12 averages six individually L2-normalized face means, then normalizes aggregate. No fitted PCA/scaler. This is post-first-Pro descriptive exploration, not predictive validation or candidate selection.',
 warning='Nearest-neighbor agreement describes representation differences, not geometric truth, uncertainty, or convergence. Building enrichment also mixes room identity, visual context and dataset sampling.',representations=report)
(root/'models/dinov3/descriptive_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
print(json.dumps(result,ensure_ascii=False))
