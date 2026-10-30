"""Archive collector (optional): stream exact v2.1 event parts.

Packaged selected source tables are sufficient for all downstream reproduction;
if present, validate/read them and do not require the original Git archive.
"""
import gzip, hashlib, io, json, os, pathlib, subprocess
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
REPO=ROOT.parent/'repo'
SOURCE=ROOT/'source'
OUT=ROOT/'stage02_same_room'
ENV={**os.environ,'GIT_NO_LAZY_FETCH':'1'}
cache=OUT/'EXISTING_VALID_EVENT_SOURCE.csv.gz'; cached_app=OUT/'VALID_CLASS_RELATION_SOURCE.csv.gz'
if cache.exists() and cached_app.exists():
 d=pd.read_csv(cache,usecols=['event_id']);a=pd.read_csv(cached_app);assert d.event_id.is_unique and set(d.event_id)==set(a.event_id)
 print('PACKAGED_EVENT_SOURCE_VERIFIED',len(d),len(a),flush=True)
 raise SystemExit(0)
if not REPO.exists():raise FileNotFoundError('Missing packaged event source tables; archive collection requires frozen source Git blobs')
manifest=json.loads((SOURCE/'research/data/releases/v2.1/LARGE_FILES.json').read_text())
item=next(r for r in manifest['files'] if r['path'].endswith('current_results/large/results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz'))
tree=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','HEAD','research/data/releases/v2.1/large_file_parts/04_EVENT_Q_STRUCTURE_EFFECTS.csv.gz.parts'],env=ENV,text=True)
shas={line.split('\t')[1]:line.split()[2] for line in tree.splitlines()}
receipts=[]
class Parts(io.RawIOBase):
 def __init__(self):self.i=0;self.buf=b'';self.offset=0;self.total=hashlib.sha256()
 def readable(self):return True
 def readinto(self,out):
  if self.offset==len(self.buf):
   if self.i>=len(item['parts']):return 0
   p=item['parts'][self.i];self.i+=1
   self.buf=subprocess.check_output(['git','-C',str(REPO),'cat-file','blob',shas[p['path']]],env=ENV)
   assert len(self.buf)==p['bytes'] and hashlib.sha256(self.buf).hexdigest()==p['sha256'],p['path']
   self.total.update(self.buf);self.offset=0;receipts.append(dict(**p,git_blob=shas[p['path']]))
  n=min(len(out),len(self.buf)-self.offset);out[:n]=self.buf[self.offset:self.offset+n];self.offset+=n;return n
app=pd.read_csv(SOURCE/'research/data/releases/v2.1/final_classification_downstream/OLD_ABC_APPLICABILITY.csv.gz')
app=app[app.stage.eq('same_room')&app.status.eq('当前适用')]
print('Applicability stages',app.shape,flush=True)
if app.empty:raise ValueError('check stage name')
ids=set(app.event_id);reader=Parts();chunks=[];seen=0
with gzip.GzipFile(fileobj=io.BufferedReader(reader)) as f:
 for c in pd.read_csv(f,chunksize=1500,low_memory=False):
  seen+=len(c);chunks.append(c[c.event_id.isin(ids)])
assert reader.total.hexdigest()==item['sha256']
d=pd.concat(chunks,ignore_index=True)
assert d.event_id.is_unique and set(d.event_id)==ids
d.to_csv(OUT/'EXISTING_VALID_EVENT_SOURCE.csv.gz',index=False)
app.to_csv(OUT/'VALID_CLASS_RELATION_SOURCE.csv.gz',index=False)
(OUT/'EVENT_SOURCE_RECEIPT.json').write_text(json.dumps(dict(source_commit='13a7861334749805a86dc19e9ea79fcaa71020c0',source_path=item['path'],source_sha256=item['sha256'],source_total_rows=seen,retained_unique_events=len(d),retained_class_projections=len(app),columns=list(d),parts=receipts,new_fusion_calls=0),ensure_ascii=False,indent=2))
print('EVENT_SOURCE_COMPLETE',seen,len(d),len(app),len(d.columns),flush=True)
