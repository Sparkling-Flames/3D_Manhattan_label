"""Read each final bridge/funnel artifact fully; no data recomputation."""
from pathlib import Path
import csv,gzip,hashlib,json

OUT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
def main():
 receipts=['FUNNEL_AND_STRICT_BRIDGE_RECEIPT.json','OUTPUT_STATE_TRANSITION_RECEIPT.json','STRICT66_BACKGROUND_EFFECTS_RECEIPT.json']
 for name in receipts:assert json.loads((OUT/name).read_text())['complete'],name
 skip={'FINAL_STAGE05_MANIFEST.csv','STAGE05_FILE_READABILITY_RECEIPT.json'}
 rows=[]
 for p in sorted(OUT.rglob('*')):
  if not p.is_file() or p.name in skip or '__pycache__' in p.parts or any(x.startswith('partial_') for x in p.parts):continue
  assert not p.name.endswith('.partial'),p
  rr={'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p),'rows':'','columns':'','verification':''}
  if p.name.endswith('.csv') or p.name.endswith('.csv.gz'):
   with (gzip.open(p,'rt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(p,'r',encoding='utf-8-sig',newline='')) as f:
    r=csv.reader(f);header=next(r);assert len(header)==len(set(header)),p;n=0
    for line in r:assert len(line)==len(header),(p,n);n+=1
   rr.update(rows=n,columns=len(header),verification='gzip_crc_and_csv_to_EOF' if p.name.endswith('.gz') else 'csv_to_EOF')
  elif p.name.endswith('.json'):
   json.loads(p.read_text(encoding='utf-8-sig'));rr['verification']='json_full_parse'
  elif p.name.endswith('.json.gz'):
   with gzip.open(p,'rt',encoding='utf-8-sig') as f:json.load(f)
   rr['verification']='gzip_crc_and_json_full_parse'
  else:
   text=p.read_text(encoding='utf-8-sig')
   if p.suffix=='.py':compile(text,str(p),'exec');rr['verification']='python_compile'
   else:rr['verification']='utf8_full_read'
  rows.append(rr)
 with open(OUT/'FINAL_STAGE05_MANIFEST.csv','w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 observed={x['path']:x['rows'] for x in rows}
 assert observed['STRICT_NORMALIZED_EVENTS.csv.gz']==18847
 assert observed['STRICT_EXACT_AC_BC_PAIR_INDEX.csv.gz']==37694
 assert observed['STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz']==120
 assert observed['STRICT66_F_VS_B_BACKGROUND_CONDITION_COVERAGE.csv']==66
 sr=json.loads((OUT/'OUTPUT_STATE_TRANSITION_RECEIPT.json').read_text())
 assert sr['method_events']==471758 and sr['unique_teams']==478012 and sr['measured_target_pools']==258
 fr=json.loads((OUT/'FUNNEL_AND_STRICT_BRIDGE_RECEIPT.json').read_text())
 assert fr['registered_equal_pure_manual_events']==311640 and fr['registered_equal_pure_manual_pools']==226
 proof={'status':'passed','files':len(rows),'bytes':sum(r['bytes'] for r in rows),
  'all_final_csv_to_EOF':True,'all_gzip_crc_checked':True,'all_json_fully_parsed':True,'all_python_compiled':True,
  'csv_unique_headers_and_widths_checked':True,'complete_receipts_checked':receipts,
  'final_status_matches_registered_events_teams_pools':True,'final_manual_funnel_matches_registered_subset':True,
  'diagnostic_previews_excluded':['partial_preview','partial_status_preview'],'source_data_not_modified':True,
  'archive_internal_readability_not_claimed_here':True}
 (OUT/'STAGE05_FILE_READABILITY_RECEIPT.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(proof,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
