"""Restore the audited one-image seed; never synthesize C/D or top boundaries."""
from pathlib import Path
import json, shutil, hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 raw=(ROOT/'inputs/library/quality_review30_receipt.json').read_bytes()
 assert len(raw)==11986 and hashlib.sha256(raw).hexdigest()=='8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c'
 x=json.loads((ROOT/'inputs/editor_seed_data.json').read_text());c=x['images'][0]
 assert len(x['images'])==1 and c['image_code']=='uNb9QFRL6hY-88'
 assert c['baseline_spaces']['C'] is None and c['baseline_spaces']['D'] is None
 assert x['room_review_batch_policy'] is None
 assert x['historical_feedback']==json.loads(raw) and x['feedback_binding']['original_bytes_verified']
 assert len(c['annotations'])==20 and len({a['record_id'] for a in c['annotations']})==20
 assert any(a['record_id']=='R02962' and a['object_id']=='new_93_3608_7113_W006' for a in c['annotations'])
 for a in c['annotations']:
  encoded=json.dumps(a['points'],separators=(',',':')).encode()
  assert hashlib.sha256(encoded).hexdigest()==a['current_points_sha256'],a['record_id']
 dst=ROOT/'user/editor';dst.mkdir(parents=True,exist_ok=True)
 (dst/'data.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
 for name in ['geometry.js','review-state.js','catalogue.js']:shutil.copy2(ROOT/'vendor/v3.4.2/dist'/name,dst/name)
 shutil.copy2(ROOT/'code/four-space-state.js',dst/'four-space-state.js')
 print('Audited one-image seed and 20 current answer coordinates restored; C/D remain empty')
if __name__=='__main__':main()
