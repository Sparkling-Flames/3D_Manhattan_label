import concurrent.futures,gzip,hashlib,json,pathlib,tarfile,io,time,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent; OUT=ROOT/'restored';CACHE=ROOT/'download_cache';CACHE.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
COMMIT='e572eb73bedc4fe9056df838e458bab83c3fa423';A='research/workers/personnel_type_discovery_next_20261019/';OLD='research/workers/pro_personnel_v2_archive_20261019/'
rows=json.loads((ROOT/'repo'/A/'ARCHIVE_FILE_MAP.json').read_text());bundles=json.loads((ROOT/'repo'/A/'PAYLOAD_BUNDLES.json').read_text())
def checked(b,r):
 assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path'];return b
def fetch(commit,path,check=None):
 key=hashlib.sha256((commit+path).encode()).hexdigest();p=CACHE/key
 if p.exists():b=p.read_bytes()
 else:
  url='https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+commit+'/'+urllib.parse.quote(path)
  for attempt in range(3):
   try:
    b=urllib.request.urlopen(url,timeout=120).read()
    if b.startswith(b'version https://git-lfs.github.com/spec/v1'):
     b=urllib.request.urlopen('https://media.githubusercontent.com/media/Sparkling-Flames/3D_Manhattan_label/'+commit+'/'+urllib.parse.quote(path),timeout=180).read()
    if check:checked(b,check)
    p.write_bytes(b);break
   except Exception:
    if attempt==2:raise
    time.sleep(2)
 if check:checked(b,check)
 return b
def save(b,r):
 checked(b,r);p=OUT/r['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
def direct(r):
 p=OUT/r['path']
 if p.exists():checked(p.read_bytes(),r);return
 mode=r['disposition']
 if mode=='reuse_repository_source':b=fetch(r['source_commit'],r['source_path'],r)
 elif mode=='reuse_previous_archive':
  e=r['previous_entry'];b=b''.join(fetch(COMMIT,OLD+x) for x in (e.get('stored_parts') or [e['stored_path']]))
  if e.get('encoding')=='gzip':b=gzip.decompress(b)
 else:
  b=b''.join(fetch(COMMIT,A+x['path'],x) for x in r['parts'])
  if r.get('encoding')=='gzip':b=gzip.decompress(b)
 save(b,r)
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
 directrows=[r for r in rows if r['disposition']!='retained_in_bundle']
 for i,_ in enumerate(ex.map(direct,directrows)):
  if i%50==0:print('direct',i,'/',len(directrows),flush=True)
 for bundle in bundles:
  print('bundle',bundle['id'],flush=True)
  parts=list(ex.map(lambda p:fetch(COMMIT,A+p['path'],p),bundle['parts']))
  mapping={r['path']:r for r in rows if r.get('bundle')==bundle['id']}
  with tarfile.open(fileobj=io.BytesIO(b''.join(parts)),mode='r:gz') as tar:
   for m in tar:save(tar.extractfile(m).read(),mapping[m.name])
for r in rows:checked((OUT/r['path']).read_bytes(),r)
receipt={'files_verified':len(rows),'bytes_verified':sum(r['bytes'] for r in rows),'manifest_sha256':hashlib.sha256((ROOT/'repo'/A/'ARCHIVE_FILE_MAP.json').read_bytes()).hexdigest(),'method':'Pinned raw/media GitHub reads, per-file original archive hash verification; no refit'}
(OUT/'RESTORATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(receipt,flush=True)
