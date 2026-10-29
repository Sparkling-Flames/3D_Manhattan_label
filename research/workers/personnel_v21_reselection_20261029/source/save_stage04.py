#!/usr/bin/env python3
"""Package only merged phase04 evidence, then actually read ZIP/gzip CSVs."""
from pathlib import Path
import csv,gzip,hashlib,io,json,os,zipfile
import pandas as pd
W=Path(__file__).resolve().parents[1]
R=W/'raw_similarity';S=W/'stage04';D=W/'deliverables';D.mkdir(exist_ok=True)
names=['AGGREGATION_PARITY_CHECK.json','COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz','COMMON45_BASELINE_PAIRED_SUMMARY.csv','COMMON45_KNOWN_WORKERS_BY_FOLD.csv','COMPLETION.json','DELIVERY_READ_CHECK.json','MAIN_RAW_SAME_COUNT_COMPARISON.csv','MANUAL_COMMON45_ALL_METHOD_RESULTS.csv','PAIR_COMPLETION.json','PAIR_POOL_INVENTORY.csv','RAW_ANSWER_SIMILARITY_ZH.md','RAW_CLASS_DISTANCE_BY_IMAGE.csv.gz','RAW_CLASS_DISTANCE_BY_POOL.csv.gz','RAW_CLASS_DISTANCE_SUMMARY.csv.gz','RAW_CLASS_DISTANCE_UNESTIMABLE.csv.gz','RAW_MAIN_DIFFICULTY_TABLE.csv','RAW_PAIR_DISTANCES.csv.gz','RAW_SAME_COUNT_FAMILY_COMPARISON.png','RAW_SAME_COUNT_FAMILY_COMPARISON.pdf']
files=[R/name for name in names]+sorted((R/'code').glob('*.py'))
files += [W/name for name in ['classification/MAIN45_LABELS_ALL_LOBO.csv.gz','classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz','targets/POOL_TARGET_CONDITIONS.csv','cases/source/FONT_SOURCE.json','source/save_stage04.py','stage04/README.md','stage04/INPUT_SOURCE_REFERENCES.csv','stage04/RUNTIME_VERSIONS.json']]
manifest=[]
for p in files:
 assert p.is_file(),p
 manifest.append({'path':str(p.relative_to(W)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
pd.DataFrame(manifest).to_csv(S/'FILE_MANIFEST.csv',index=False,encoding='utf-8-sig');files.append(S/'FILE_MANIFEST.csv')
archive=D/'HOHONET_v21_阶段04_45法原答相似性完整证据_20261029.zip';tmp=archive.with_name(archive.name+'.writing')
with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for p in sorted(files):
  z.write(p,str(p.relative_to(W)),compress_type=zipfile.ZIP_STORED if p.suffix in ['.gz','.png','.pdf'] else zipfile.ZIP_DEFLATED)
with tmp.open('rb') as f:os.fsync(f.fileno())
tmp.replace(archive)
expected={
 'raw_similarity/RAW_PAIR_DISTANCES.csv.gz':134197,
 'raw_similarity/RAW_CLASS_DISTANCE_BY_POOL.csv.gz':46362,
 'raw_similarity/RAW_CLASS_DISTANCE_BY_IMAGE.csv.gz':182998,
 'raw_similarity/RAW_CLASS_DISTANCE_SUMMARY.csv.gz':94588,
 'raw_similarity/RAW_CLASS_DISTANCE_UNESTIMABLE.csv.gz':6378,
 'raw_similarity/COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz':269742,
 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz':64170,
 'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz':8385,
}
read_rows=[]
with zipfile.ZipFile(archive) as z:
 bad=z.testzip();assert bad is None,bad
 for name,n in expected.items():
  with z.open(name) as member,gzip.GzipFile(fileobj=member) as decoded,io.TextIOWrapper(decoded,encoding='utf-8-sig',newline='') as text:
   reader=csv.reader(text);header=next(reader);count=sum(1 for row in reader)
  assert count==n,(name,count,n)
  read_rows.append({'file':name,'rows':count,'columns':len(header),'actual_zip_and_gzip_read':True})
 # Check ZIP manifest against actual ZIP members, including all standalone code/report artifacts.
 for row in manifest:
  b=z.read(row['path']);assert len(b)==row['bytes'];assert hashlib.sha256(b).hexdigest()==row['sha256']
receipt={'file':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(files),'zip_crc_pass':True,'manifest_members_sha256_pass':True,'actual_decoded_csv_reads':read_rows,'included':'merged evidence, actual code, frozen small inputs and source refs','excluded':'duplicate shards, logs, environment, original-image collection, full fusion caches','no_upload_performed':True}
(D/'STAGE04_READ_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
independent=[('完整证据包',archive),('中文原答相似性报告',R/'RAW_ANSWER_SIMILARITY_ZH.md'),('Manual完整45法小表',R/'MANUAL_COMMON45_ALL_METHOD_RESULTS.csv'),('共同目标基线配对汇总',R/'COMMON45_BASELINE_PAIRED_SUMMARY.csv'),('代表同点数对照',R/'MAIN_RAW_SAME_COUNT_COMPARISON.csv'),('难度解释小表',R/'RAW_MAIN_DIFFICULTY_TABLE.csv'),('关键对照图',R/'RAW_SAME_COUNT_FAMILY_COMPARISON.png'),('完整分类比较汇总',R/'RAW_CLASS_DISTANCE_SUMMARY.csv.gz'),('阶段索引',S/'README.md'),('实际解压读取回执',D/'STAGE04_READ_CHECK.json')]
pd.DataFrame([{'description':name,'local_path':str(p),'bytes':p.stat().st_size,'exists':p.is_file()}for name,p in independent]).to_csv(D/'STAGE04_INDEPENDENT_DOWNLOADS.csv',index=False,encoding='utf-8-sig')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files),'decoded_read_rows':sum(r['rows']for r in read_rows),'independent_entries':len(independent),'zip_crc_pass':True},ensure_ascii=False),flush=True)
