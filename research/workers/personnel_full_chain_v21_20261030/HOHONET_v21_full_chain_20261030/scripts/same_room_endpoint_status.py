"""Optional archive collector; packaged endpoint table is the replay input.

No original repository is required when the selected full endpoint table exists.
"""
from pathlib import Path
import io,gzip,json,hashlib,subprocess,os
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/abc';REPO=ROOT.parent/'repo';ENV={**os.environ,'GIT_NO_LAZY_FETCH':'1'}
e=pd.read_csv(OUT/'EVENT_IDENTITIES.csv.gz');keys=set(e[[f'team_{r}_{v}' for r in ['A','B','C'] for v in ['a','b']]].to_numpy().ravel())
cached=OUT/'EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz'
if cached.exists():
 d=pd.read_csv(cached,usecols=['team_key','score_status','B8L2']);assert d.team_key.is_unique and set(d.team_key)==keys
 print('PACKAGED_ENDPOINT_SOURCE_VERIFIED',len(d),flush=True)
 raise SystemExit(0)
if not REPO.exists():raise FileNotFoundError('Missing packaged abc/EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz; optional archive collector needs original Git blobs')
mf=json.loads((SRC/'research/data/releases/v2.1/LARGE_FILES.json').read_text());item=next(x for x in mf['files'] if x['path'].endswith('current_results/large/native/ENDPOINT_SCALARS.csv.gz'))
tr=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','HEAD','research/data/releases/v2.1/large_file_parts/03_ENDPOINT_SCALARS.csv.gz.parts'],env=ENV,text=True);shas={l.split('\t')[1]:l.split()[2] for l in tr.splitlines()};parts=[]
class Stream(io.RawIOBase):
 def __init__(self):self.i=0;self.buf=b'';self.pos=0;self.total=hashlib.sha256()
 def readable(self):return True
 def readinto(self,out):
  if self.pos==len(self.buf):
   if self.i==len(item['parts']):return 0
   p=item['parts'][self.i];self.i+=1;self.buf=subprocess.check_output(['git','-C',str(REPO),'cat-file','blob',shas[p['path']]],env=ENV);assert len(self.buf)==p['bytes'] and hashlib.sha256(self.buf).hexdigest()==p['sha256'];self.total.update(self.buf);self.pos=0;parts.append(p)
  n=min(len(out),len(self.buf)-self.pos);out[:n]=self.buf[self.pos:self.pos+n];self.pos+=n;return n
cols=['team_key','pool_id','member_workers','member_object_ids','k','image','image_id','building','condition','layer','reference_id','reference_version','complete_evaluable','score_status','geometry_status','geometry_reason','order_status','connection_available','geometry_available','geometry_state_pointer','reasons','policy_deferred','location_unresolved','below_four','incomplete_nonpolicy','score_failure_nonpolicy','score_available','recorded_time_eligible','time_source_kinds','recorded_time_total_seconds','B8L2','D10','WQ','A10','boundary_loss','direction_loss','height_loss','global_height_loss','local_height_loss','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','iou_2d','omission','extension','height_mean_ratio','node_supports','minimum_support']
s=Stream();n=0;chunks=[]
with gzip.GzipFile(fileobj=io.BufferedReader(s)) as f:
 for z in pd.read_csv(f,usecols=cols,chunksize=5000,low_memory=False):n+=len(z);chunks.append(z[z.team_key.isin(keys)])
assert s.total.hexdigest()==item['sha256'];d=pd.concat(chunks,ignore_index=True);assert d.team_key.is_unique and set(d.team_key)==keys
p=OUT/'EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz';tmp=p.with_name(p.name+'.tmp');d.to_csv(tmp,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0});tmp.replace(p)
d.groupby(['score_status','geometry_status'],dropna=False).agg(endpoints=('team_key','size'),quality_available=('B8L2','count'),complete=('complete_evaluable','sum')).reset_index().to_csv(OUT/'UNIQUE_ENDPOINT_STATUS_COUNTS.csv',index=False)
(OUT/'ENDPOINT_STATUS_SOURCE_RECEIPT.json').write_text(json.dumps(dict(source_commit='13a7861334749805a86dc19e9ea79fcaa71020c0',source=item['path'],source_sha256=item['sha256'],source_rows=n,selected_unique_endpoints=len(d),parts=parts,new_fusion_calls=0),indent=2))
print('STATUS_COMPLETE',n,len(d),d.score_status.value_counts(dropna=False).to_dict(),flush=True)
