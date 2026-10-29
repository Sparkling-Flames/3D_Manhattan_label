"""Build offline doorway review from frozen evidence; no scoring or reference adoption."""
import gzip,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/doorway_review_20261030'
def build():
 r=ROOT/'research/data/releases/v2.1'
 read=lambda p:json.loads(p.read_text(encoding='utf8'))
 inventory=read(r/'quality_inventory.json')
 refs={x['target_id']:x for x in read(r/'reference_catalog.json')}
 with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz','rt',encoding='utf8') as f: evidence={x['object_id']:x for x in json.load(f)['records']}
 cases=[]
 for d in read(r/'difficulty_records.json')['records']:
  if 'doorway' not in d['scene']:continue
  ref=refs[d['target_version']]
  records=[]
  for x in inventory:
   if x['image_id']!=d['image_id']:continue
   e=evidence[x['object_id']]
   records.append(dict(id=x['object_id'],worker=x['worker_id'],points=e['points_1024x512'],status=x['geometry_status']))
  photo=Path(d['photo']);assert photo.is_file()
  cases.append(dict(image=d['image'],image_id=d['image_id'],status=d['doorway_status'],photo=Path(os.path.relpath(photo,OUT)).as_posix(),reference_id=ref['target_id'],reference_version=ref['reference_version'],points=ref['points_1024x512'],floor=ref['floor_xz_h'],records=records,cut=None))
 # Initial proposals after inspection of all 20 panoramas and reference footprints.
 # Two independent stop planes; unmeasured thickness is explicitly a draft offset.
 specifications=[(1,4,None),(0,0,None),(0,2,None),(1,2,3),(1,1,None),(0,3,None),(1,2,3),(0,1,None),(1,2,10),(0,1,None),(0,3,None),(0,2,8),(0,9,10),(0,3,4),(0,5,6),(0,9,10),(0,1,None),(1,2,5),(1,1,5),(1,1,None)]
 for c,(axis,v,w) in zip(cases,specifications):
  f=c['floor'];value=f[v][axis]
  if w is None:
   width=(max(p[axis] for p in f)-min(p[axis] for p in f))*.025
   stops=[value-width/2,value+width/2]
   note='已对照原图预切；原参考未明确表达门框两面，初始间距仅供调整，不是门框厚度测量。'
  else:
   stops=sorted([value,f[w][axis]])
   note='已对照原图预切；两条停止边取自参考中门口附近的转折位置，仍需检查门框对应。'
  def line(t):return [[t,-100],[t,100]] if axis==0 else [[-100,t],[100,t]]
  c['cuts']=[dict(line=line(stops[0]),side=1 if axis==0 else -1),dict(line=line(stops[1]),side=-1 if axis==0 else 1)]
  c['proposal_note']=note
 assert len(cases)==20 and sum(len(c['records']) for c in cases)==708
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'data.js').write_text('window.DOORWAY_DATA='+json.dumps(dict(schema='doorway_review_v2',cases=cases),ensure_ascii=False,allow_nan=False)+';',encoding='utf8')
 template=Path(__file__).with_suffix('.html').read_text(encoding='utf8')
 for key,path in [('VIEWER',ROOT/'research/statistics/research_explorer_v1_r2_20261017'),('OLD',ROOT/'analysis_results/difficulty/scope_workbench_recovered_20261015/quality_scope_review_complete_20261010/workbench_v3.4.2/dist')]:template=template.replace('__'+key+'__',Path(os.path.relpath(path,OUT)).as_posix())
 (OUT/'review.js').write_text(Path(__file__).with_suffix('.js').read_text(encoding='utf8'),encoding='utf8')
 (OUT/'index.html').write_text(template,encoding='utf8')
 print(len(cases),sum(len(c['records']) for c in cases))
if __name__=='__main__':build()
