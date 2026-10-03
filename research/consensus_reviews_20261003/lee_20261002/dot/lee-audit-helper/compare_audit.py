"""Read-only comparison of fixed Lee input, published outputs and independent return."""
import csv, json, hashlib, math, sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'lee-audit-original'
OUT=ROOT/'lee-audit-helper'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvrows(p): return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
data=read(SOURCE/'research/lee_tile_stage1_20261002/input.json')
quality_path=ROOT/'audit-oct2-original/analysis_results/layout_3d_quality_probe_20261002/results.json'
raw=quality_path.read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='3809553a325c49baebb1a15a04da30017d98177d'
q=read(quality_path)
qobjects={(o['image'],o['record']['id']):o['record'] for o in q['objects']}
for r in q['real']:
 if r['b'] is not None: qobjects[r['image'],r['b']['id']]=r['b']
bindings=[]
for image in data['images']:
 for record in image['annotations']+image['references']:
  prior=qobjects[image['code'],record['id']]
  fields=list(prior)
  diff=[f for f in fields if prior[f]!=record.get(f)]
  bindings.append(dict(image=image['code'],id=record['id'],fields=fields,differences=diff))
dump('frozen_quality_210_bindings.json',dict(objects=len(bindings),different_objects=sum(bool(x['differences']) for x in bindings),fields_checked=sum(len(x['fields']) for x in bindings),records=bindings,scope='Fixed quality handoff comparison only; not a new full raw/current-manifest binding'))
ret=ROOT/'lee-audit-inputs/extracted/lee_stage1_independent_20261002'
sub=read(ret/'inputs/subset.json')
returnchecks=[]
for group in sub['groups']:
 image=next(i for i in data['images'] if i['code']==group['code'])
 records={r['id']:r for r in image['annotations']}
 for r in group['records']:
  a=records[r['id']]
  for key,value in r.items(): returnchecks.append(dict(id=r['id'],field=key,equal=value==a[key]))
  returnchecks.append(dict(id=r['id'],field='gate',equal=group['gate']==a['main_consensus_gate']['status']))
  returnchecks.append(dict(id=r['id'],field='condition',equal=group['condition']==a['condition']))
 for version,footprint in group['references'].items():
  candidates=[r for r in image['references'] if r['version']==version]
  actual=candidates[0]['footprint'] if candidates else None
  returnchecks.append(dict(id=group['code']+':'+version,field='footprint',equal=footprint==actual))
published=csvrows(SOURCE/'analysis_results/lee_tile_stage1_20261002/summary.csv')
bykey={(r['image'],r['method'],r['k']):r for r in published}
extracted=csvrows(ret/'inputs/published_summary_extract.csv')
cells=[]
for r in extracted:
 p=bykey[sub['groups'][0]['code'],r['method'],r['k']]
 for field,value in r.items():
  try: delta=abs(float(value)-float(p[field]));equal=delta==0
  except ValueError: delta=None;equal=value==p[field]
  cells.append(dict(method=r['method'],k=r['k'],field=field,equal=equal,delta=delta))
dump('independent_return_source_binding.json',dict(geometry_and_metadata_checks=returnchecks,summary_cells=len(cells),summary_cell_differences=[c for c in cells if not c['equal']],summary_cells_all=cells))
def compare_tables(p1,p2):
 a,b=csvrows(p1),csvrows(p2)
 assert len(a)==len(b),(p1,len(a),len(b))
 diffs=Counter();maxima={};nonnum=[]
 for idx,(x,y) in enumerate(zip(a,b)):
  assert x.keys()==y.keys()
  for k in x:
   if x[k]==y[k]:continue
   try:
    v,w=float(x[k]),float(y[k]); assert math.isfinite(v) and math.isfinite(w)
    diffs[k]+=1;maxima[k]=max(maxima.get(k,0),abs(v-w))
   except ValueError: nonnum.append(dict(row=idx,field=k,a=x[k],b=y[k]))
 return dict(rows=len(a),numeric_different_cells=dict(diffs),max_abs_difference=maxima,nonnumeric_differences=nonnum)
results={}
for dirname in ['lee-audit-recomputed','lee-audit-recomputed-old']:
 p=ROOT/dirname
 if not (p/'summary.csv').exists():continue
 old=SOURCE/'analysis_results/lee_tile_stage1_20261002'
 results[dirname]={name:compare_tables(old/name,p/name) for name in ['replay.csv','summary.csv']}
 results[dirname]['warnings']=dict(count=len(read(p/'warnings.json')),by_type={str(k):v for k,v in Counter((x['stage'],x['message']) for x in read(p/'warnings.json')).items()})
 results[dirname]['warnings_exact_equal']=read(old/'warnings.json')==read(p/'warnings.json')
 results[dirname]['coverage_exact_equal']=read(old/'coverage.json')==read(p/'coverage.json')
 results[dirname]['full_tiles']=len(read(p/'full_tiles.geojson')['features'])
dump('reproduction_comparison.json',results)
print(json.dumps(dict(binding_objects=len(bindings),binding_differences=sum(bool(x['differences']) for x in bindings),return_geometry_differences=sum(not x['equal'] for x in returnchecks),return_summary_cells=len(cells),return_summary_differences=sum(not x['equal'] for x in cells),reproduction=results),indent=2))
