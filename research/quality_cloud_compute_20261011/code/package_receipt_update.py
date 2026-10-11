"""Update two delivery ZIPs only; mathematical archives and every image stay unchanged."""
import hashlib,json,zipfile,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def write_zip(path,entries):
 manifest={name:{'bytes':len(data),'sha256':sha(data)} for name,data in sorted(entries.items())}
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,data in sorted(entries.items()):z.writestr(name,data)
  z.writestr('FILE_MANIFEST_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  for name,item in manifest.items():assert sha(z.read(name))==item['sha256']
 return {'file':str(path),'bytes':path.stat().st_size,'sha256':sha(path.read_bytes()),'files_including_manifest':len(entries)+1}
def main():
 user=ROOT/'blind_sample/user';previous=ROOT/'history/receipt_before_20261011/user_exact_ceff6990.zip'
 with zipfile.ZipFile(previous) as z:
  jpgs=[n for n in z.namelist() if n.endswith('.jpg')];assert len(jpgs)==16
  assert all(z.read(n)==(user/n).read_bytes() for n in jpgs)
  # Preserve original CSV data-field order, despite adding a version metadata row.
  import csv,io
  oldfields=next(csv.reader(io.StringIO(z.read('responses.csv').decode('utf-8-sig'))))
 blank=json.loads((user/'responses.json').read_text());assert blank['fields']==oldfields
 assert blank['case_ids']==['C01','C02','C03','C04','C05','C06','C07','X01']
 assert all(v=='' for row in blank['answers'] for k,v in row.items() if k not in ['case_id','case_type'])
 # Replace the obsolete legacy checksum list with current hashes; no image changes.
 manifest=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(user.iterdir()) if p.is_file() and p.name!='manifest_sha256.json']
 (user/'manifest_sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 userzip=Path('/workspace/quality_blind_sample_user_20261010.zip');user_result=write_zip(userzip,{p.name:p.read_bytes() for p in user.iterdir() if p.is_file()})
 answerzip=Path('/workspace/quality_blind_sample_answer_mapping_20261010.zip')
 with zipfile.ZipFile(answerzip) as z:entries={n:z.read(n) for n in z.namelist() if n!='FILE_MANIFEST_SHA256.json'}
 oldmapping=json.loads(entries['answer_mapping_private.json']);current=json.loads((ROOT/'blind_sample/answer_mapping_private.json').read_text())
 assert [c['case_id'] for c in oldmapping]==[c['case_id'] for c in current]
 for old,new in zip(oldmapping,current):
  expected=dict(new)
  if new['case_id'] in ['C02','C05']:
   assert new['case_use']=='general_quality_observation_only' and new['penalty_fitting_allowed'] is False
   expected.pop('case_use');expected.pop('penalty_fitting_allowed')
  baseline=dict(old)
  if new['case_id'] in ['C02','C05']:
   baseline.pop('case_use',None);baseline.pop('penalty_fitting_allowed',None)
  assert expected==baseline
 entries['answer_mapping_private.json']=(ROOT/'blind_sample/answer_mapping_private.json').read_bytes()
 answer_result=write_zip(answerzip,entries)
 result={'user':user_result,'answer_mapping':answer_result,'all_16_JPEGs_byte_identical':True,'case_order_and_13_fields_stable':True,'all_default_answers_blank':True,'numeric_archives_repacked':False,'C02_C05_general_observation_not_penalty_fit':True}
 (ROOT/'results/receipt_delivery_update.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
