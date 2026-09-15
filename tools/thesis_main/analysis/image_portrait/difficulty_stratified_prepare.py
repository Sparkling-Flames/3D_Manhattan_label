"""Follow-up image-side analysis. Frozen arrays only; never loads images/weights.

Human difficulty tags are an independent named target, not measured convergence.
Semantic keyword mappings are explicit post-hoc exploratory representations.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, re, shutil
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'analysis_results/image_portrait_20260914_v1'
O=B/'cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7'
SEED=20260915
FACES=('front','right','back','left','up','down')
LABELS=['简单','中等','困难']
TRAITS=['floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast']
FUNCTIONS={
 'sleep':['卧室','主卧','睡眠','床头','床侧','床区','蓝床','蓝被床'],
 'bathroom':['卫浴','主卫','浴室','洗漱','洗手','梳妆','淋浴','沐浴','浴缸','马桶','厕间','镜台'],
 'kitchen':['厨房','炉灶','橱柜'], 'dining':['用餐','餐室','餐厅','餐桌'],
 'living':['起居','休闲','会客','客厅','沙发','休憩','钢琴'],
 'work':['工作','学习','书房','办公','会议','书桌'],
 'circulation':['通行','走道','走廊','过道','通道','楼梯','平台'],
 'storage':['储藏','家务','更衣','衣帽','衣柜'], 'special':['健身','按摩','儿童活动','特殊用途'],
 'empty':['空房','空置']}
POSITIONS={
 'entrance':['入口','门侧','靠门','门边','门一侧'], 'window':['窗侧','窗边','窗前','靠窗','法式窗'],
 'edge':['侧边','边缘','侧墙','靠侧','一端'], 'stair_landing':['楼梯','挑空','平台'],
 'shower_interior':['淋浴内部','淋浴间内'], 'bath_tub':['浴缸','沐浴'],
 'washing':['洗漱','洗手台','梳妆','镜台'], 'mirrored':['镜面','大镜'],
 'glass':['玻璃'], 'fireplace':['壁炉'], 'empty':['空房','空置'], 'shared_focus':['共同','并重','交汇']}

def load(p):
 p=Path(p)
 if p.suffix=='.gz':
  with gzip.open(p,'rt',encoding='utf-8-sig') as f:return [json.loads(s) for s in f if s.strip()]
 if p.suffix=='.jsonl':return [json.loads(s)for s in p.read_text(encoding='utf-8-sig').splitlines()if s.strip()]
 return json.loads(p.read_text(encoding='utf-8-sig'))
def savej(p,x):
 p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.item()if isinstance(a,np.generic)else str(a))+'\n',encoding='utf-8')
def csv(p,x):
 p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
 d=x if isinstance(x,pd.DataFrame)else pd.DataFrame(x)
 if not len(d.columns):d=pd.DataFrame(columns=['status'])
 d.to_csv(p,index=False,float_format='%.12g');return d

def first_clause(t):
 # Keep the literal main clause; do not reassign a scene from outcome notes.
 return re.split(r'[；;，,]',str(t))[0]
def keyword_vector(t,mapping):return {k:int(any(w in t for w in words))for k,words in mapping.items()}
def metadata():
 tags=load(O/'inputs/image_tags.jsonl');s={r['image_id']:r for r in load(B/'metadata/spatial_history.jsonl.gz')};v={r['image_id']:r for r in load(B/'visual/visual_traits.json')};rr={r['image_id']:r for r in load(B/'visual/resolution_recheck.json')['images']}
 rooms={i:(r['room_id'],r['status'])for r in load(B/'evaluation/room_components.jsonl')for i in r['image_ids']}
 allrows=[];conf=[]
 for t in tags:
  i=t['image_id'];a=s[i];c=a.get('spatial_classification')or{};nr=a.get('new_spatial_review')or{};selection=a.get('latest_selection_record')or{}
  assert selection.get('difficulty')==t.get('difficulty_tag'),(i,'source label mismatch')
  text=nr.get('main_space')or a.get('main_visual_space')or''
  tainted=any(w in text for w in ['难','标注','共识','人数','采用','歧义'])
  if tainted:conf.append(dict(image_id=i,field='main_space',raw=text,action='excluded_from_text_features; original retained'))
  x=dict(t,main_space_raw=text,main_space_safe=''if tainted else text,main_space_source='AI_new_spatial_review',main_space_basis=nr.get('review_basis','unknown'),main_space_human=c.get('focus'),main_space_human_source=(a.get('spatial_field_sources')or{}).get('focus','unknown'),fine_human=c.get('functions'),fine_ai='|'.join(sorted(nr.get('functional_regions')or[])),doorway=(a.get('doorway_reconciliation')or{}).get('current_working_label','unknown'),room_id=rooms.get(i,('unresolved:'+i,''))[0],room_status=rooms.get(i,('','not_in_supported_component'))[1])
  x.update({k:v[i][k]for k in TRAITS});x.update({k+'_recheck':rr[i]['reviewed_traits'][k]if i in rr else v[i][k]for k in TRAITS});x['resolution_rechecked']=i in rr
  f=keyword_vector(first_clause(x['main_space_safe']),FUNCTIONS);p=keyword_vector(first_clause(x['main_space_safe']),POSITIONS)
  x.update({'main_'+k:val for k,val in f.items()});x.update({'position_'+k:val for k,val in p.items()})
  # Functional main space is not inferred from the complete description, where adjacent rooms may occur.
  x['main_semantic_key']='+'.join(k for k,val in f.items()if val)or'unknown'
  x['main_semantic_coarse']=x['main_semantic_key']
  matches=[(first_clause(x['main_space_safe']).find(w),k)for k,words in FUNCTIONS.items()for w in words if w in first_clause(x['main_space_safe'])]
  x['main_function_primary']=min(matches)[1]if matches else 'unknown'
  if re.search(r'外.*(走道|通道|入口)',first_clause(x['main_space_safe'])):x['main_function_primary']='circulation'
  x['main_function_primary_source']='explicit first-clause keyword derivation; not human/adjudicated semantics'
  allrows.append(x)
 d=csv('images/metadata_all648.csv',allrows);lab=d[d.difficulty_status=='labelled'].copy();lab['y']=lab.difficulty_tag.map(dict(zip(LABELS,range(3))));lab=lab.sort_values('image_id').reset_index(drop=True);csv('images/labels106.csv',lab);csv('audit/leakage_text_screen.csv',conf)
 assert len(lab)==106 and lab.difficulty_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16}
 rows=[]
 for field in ['scene_category','main_function_primary','main_semantic_key','fine_ai','main_space_human','building','selection_display_group','room_status']:
  for value,g in d.groupby(field,dropna=False):
   z=g[g.difficulty_status=='labelled'];rows.append(dict(field=field,value=value,n_pool=len(g),n_labelled=len(z),n_buildings=z.building.nunique(),simple=int((z.y==0).sum())if'y'in z else int((z.difficulty_tag=='简单').sum()),medium=int((z.difficulty_tag=='中等').sum()),hard=int((z.difficulty_tag=='困难').sum())))
 csv('images/stratum_coverage.csv',rows)
 savej('method/semantic_mapping.json',dict(function_keywords=FUNCTIONS,position_keywords=POSITIONS,main_scope='first text clause; no inferred physical region; AI source separate from human focus',prohibition='do not use outcome/difficulty notes, collection targets, group ID, building ID or image number as predictors'))
 return lab

def pool(a,keys):return np.mean([a[k]for k in keys],axis=0,dtype=np.float64).astype(np.float32)
def extraction():
 ids=pd.read_csv(O/'images/labels106.csv').image_id.tolist();feat=collections.defaultdict(list);audit=[];fail=[];dims={}
 for model in ['hohonet','bilayout','ulayout','dinov3','da3']:
  for image in ids:
   suffix='.npz'if model in ['hohonet','bilayout']else'.features.npz';p=B/'models'/model/(image+suffix)
   try:
    with np.load(p,allow_pickle=False)as z:a={k:z[k]for k in z.files}
    if 'image_ids'in a:assert a['image_ids'].tolist()==[image]
    assert all(np.isfinite(x).all()for k,x in a.items()if k!='image_ids')
    f={}
    if model in ['hohonet','bilayout']:
     st=load(B/'models'/model/(image+'.json'));assert st['status']=='ok' and all(q['status']=='ok'for q in st['phases'])
     layers=['encoder_stage2','encoder_stage4','compressed','refined','shared']if model=='hohonet'else['fc','fg_enclosed','fg_extended']
     for layer in layers:
      for typ in ['global','regions']:f[f'{model}__{layer}__{typ}']=pool(a,[f'yaw{y}__{layer}__{typ}'for y in (0,90,180,270)]).ravel()
     if model=='hohonet':f['hohonet__legacy_current']=a['legacy_single_phase_mean']
    elif model=='ulayout':
     for layer in ['compressed','transformer']:
      for typ in ['global','local16']:f[f'ulayout__{layer}__{typ}']=pool(a,[f'yaw{y}_{layer}_{typ}'for y in (0,90,180,270)]).ravel()
    elif model=='dinov3':
     for l in [3,6,9,11,12]:
      for typ in ['global','local16']:f[f'dinov3__block{l}__panorama_{typ}']=a[f'panorama_block{l}_patch_{typ}'].ravel()
      f[f'dinov3__block{l}__panorama_mean']=a[f'panorama_block{l}_patch_global'][:768]
      f[f'dinov3__block{l}__faces_global']=pool(a,[f'{face}_block{l}_patch_global'for face in FACES])
      f[f'dinov3__block{l}__faces_local16']=pool(a,[f'{face}_block{l}_patch_local16'for face in FACES]).ravel()
      f[f'dinov3__block{l}__faces_concat']=np.concatenate([a[f'{face}_block{l}_patch_global']for face in FACES])
     f['dinov3__cls__panorama']=a['panorama_block12_cls_global'];f['dinov3__cls__faces_global']=pool(a,[f'{face}_block12_cls_global'for face in FACES]);f['dinov3__cls__faces_concat']=np.concatenate([a[f'{face}_block12_cls_global']for face in FACES])
    else:
     assert int(a['feature_schema_version'])==2
     for l in [5,7,9,11]:
      f[f'da3__layer{l}__faces_global']=pool(a,[f'{face}_view0_out_layer_{l}_global'for face in FACES])
      f[f'da3__layer{l}__faces_local16']=pool(a,[f'{face}_view0_out_layer_{l}_local16'for face in FACES]).ravel()
      f[f'da3__layer{l}__faces_concat']=np.concatenate([a[f'{face}_view0_out_layer_{l}_global']for face in FACES])
    for k,x in f.items():
     assert x.ndim==1 and np.isfinite(x).all();feat[k].append(x);dims[k]=x.size
    audit.append(dict(image_id=image,model=model,path=str(p.relative_to(ROOT)),file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),status='loaded_finite_required_keys',arrays=len(a),features=len(f)))
   except Exception as e:
    fail.append(dict(image_id=image,model=model,error=repr(e)));raise
  print('EXTRACT',model,flush=True)
 (O/'cache').mkdir(parents=True,exist_ok=True)
 for k,x in feat.items():
  assert len(x)==len(ids);np.save(O/'cache'/f'{k}.npy',np.asarray(x,dtype=np.float32))
 csv('audit/loaded_model_files.csv',audit);csv('audit/model_failures.csv',fail)
 csv('models/feature_inventory.csv',[dict(feature=k,dimension=v,n_images=len(ids),model=k.split('__')[0],pooling='face means/ordered concat are declared numeric pooling, not additional captures',candidate_kind='new_pool_exploration'if any(w in k for w in ['faces_concat','panorama_mean'])else'prespecified_layer_numeric_pool')for k,v in dims.items()])
 savej('cache/image_ids.json',ids)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['metadata','features']);a=p.parse_args();O.mkdir(parents=True,exist_ok=True)
 metadata()if a.mode=='metadata'else extraction()
