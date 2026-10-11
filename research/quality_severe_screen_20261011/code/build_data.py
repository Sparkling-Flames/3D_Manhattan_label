import pathlib,json,csv,random,zipfile,io,hashlib,math,collections
from PIL import Image
P=pathlib.Path('pro_return_review_20261011/extracted/quality_calibration_research_20261011');B=P/'inputs_extracted/quality_cloud_compute_review_20261010';O=pathlib.Path('severe_review_20261011');D=O/'site/dist';(D/'photos').mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text());rows=read(B/'results/current_components.json');objs={x['object_id']:x for x in read(B/'inputs/current_formal_loader_data.json')['objects']};geo=read(B/'inputs/current_geometry_compact.json')['geometries'];line={r['record_id']:r for r in csv.DictReader((P/'work_metrics/lineage/all3152_eligibility_lineage.csv').open(encoding='utf-8-sig'))}
archives=[zipfile.ZipFile(p) for p in (O/'source_images').rglob('*.zip')];photos={}
for z in archives:
 for n in z.namelist():
  if n.lower().endswith(('.png','.jpg','.jpeg')) and '__' in n:photos[pathlib.Path(n).name.split('__')[0]]=(z,n)
# Exclude all scope-review image IDs, as some alternate top boundaries remain unconfirmed.
scope=read(P/'work_reference/inputs/scope_source/inputs/scope/normalized_confirmation_overlay.json');scope_text=json.dumps(scope)
scoped={r['image_id'] for r in rows if r['image_id'] in scope_text}
def geomgood(g):return g and all(isinstance(g.get(k),list) and len(g[k])>=3 and all(len(v)==3 and all(math.isfinite(x) for x in v) for v in g[k]) for k in ['top3d','bottom3d'])
def eligible(r):
 return line[r['record_id']]['group_split']=='development' and r['image_code'] in photos and r['image_id'] not in scoped and not r['reference_strict_reasons'] and not r['reference_restrictions'] and geomgood(geo.get(r['reference_object_id'])) and r.get('condition')=='manual'
ex=[r for r in rows if eligible(r) and r['worker_quality_gate']=='excluded' and (objs[r['object_id']].get('original_export_points') or geomgood(geo.get(r['object_id'])))]
# First pass includes all eligible historical exclusions, and 36 scored comparison examples across Q ranges.
controls=[];rng=random.Random(202610111115)
for low,hi in [(0,35),(35,65),(65,85),(85,101)]:
 a=[r for r in rows if eligible(r) and r['primary_included'] and r['Q'] is not None and low<=r['Q']<hi];rng.shuffle(a);controls.extend(a[:9])
selected=ex+controls;rng.shuffle(selected)
def compact(g):return {k:g[k] for k in ['top3d','bottom3d']}
def auto(raw):
 if not raw or len(raw)%2 or len(raw)<6:return None
 pp=[]
 for a,b in zip(raw[::2],raw[1::2]):
  t,f=sorted([a,b],key=lambda p:p[1]);dx=(f[0]-t[0]+512)%1024-512
  if not all(math.isfinite(x) for p in [a,b] for x in p) or abs(dx)>64 or not 0<t[1]<256<f[1]<512:return None
  x=(t[0]+dx/2)%1024;u=(x/1024-.5)*2*math.pi;v=(f[1]/512-.5)*math.pi;r=1/math.tan(v);h=r*math.tan((.5-t[1]/512)*math.pi)
  if max(abs(r),abs(h))>100:return None
  pp.append((x,[r*math.sin(u),-1,-r*math.cos(u)],[r*math.sin(u),h,-r*math.cos(u)]))
 pp.sort(key=lambda a:a[0]);return {'bottom3d':[p[1] for p in pp],'top3d':[p[2] for p in pp]}
public=[];private=[];copied={}
for i,r in enumerate(selected,1):
 o=objs[r['object_id']];cid=f'S{i:03d}';raw=o.get('original_export_points') or o.get('points_1024x512');g=geo.get(r['object_id']);mode='frozen_geometry' if geomgood(g) else 'automatic_preview'
 if mode=='automatic_preview':g=auto(raw)
 if not g:mode='raw_points_only'
 code=r['image_code'];z,n=photos[code]
 if code not in copied:
  b=z.read(n);im=Image.open(io.BytesIO(b)).convert('RGB');assert im.width==im.height*2;im.resize((1536,768)).save(D/'photos'/f'{code}.jpg',quality=88);copied[code]={'archive':pathlib.Path(z.filename).name,'entry':n,'source_sha256':hashlib.sha256(b).hexdigest()}
 public.append({'id':cid,'image':f'photos/{code}.jpg','annotation':compact(g) if g else None,'reference':compact(geo[r['reference_object_id']]),'raw':raw,'mode':mode})
 private.append({'id':cid,'record_id':r['record_id'],'object_id':r['object_id'],'worker_id':r['worker_id'],'image_code':code,'reference_object_id':r['reference_object_id'],'original_eligibility':r['worker_quality_gate'],'comparison_control':r in controls,'mode':mode,'not_formal_analysis':True,'raw_annotation_sha256':hashlib.sha256(json.dumps(raw).encode()).hexdigest(),'photo':copied[code]})
dataset=hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest();(D/'data.json').write_text(json.dumps({'dataset_id':dataset,'cases':public},separators=(',',':')));(O/'selection_private.json').write_text(json.dumps({'dataset_id':dataset,'cases':private,'counts':{'total':len(public),'W019':sum(r['worker_id']=='W019' for r in private),'excluded':len(ex),'controls':len(controls),'modes':dict(collections.Counter(r['mode'] for r in private))},'policy':'development only; reference restrictions and scope-review images excluded; raw data/gates/scores unchanged; no human grades assigned; automatic preview not accepted geometry'},ensure_ascii=False,indent=2));print((O/'selection_private.json').read_text()[-850:])
