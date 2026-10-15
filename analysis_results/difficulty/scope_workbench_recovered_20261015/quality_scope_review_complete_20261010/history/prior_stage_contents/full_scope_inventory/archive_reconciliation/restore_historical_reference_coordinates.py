"""Read original/selected reference coordinates without changing chosen references."""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--queue',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rel='analysis_results/research_input_20260929/preprocessed_source.json'
raw=(a.repo/rel).read_bytes()
pointer=subprocess.check_output(['git','show','HEAD:'+rel],cwd=a.repo,text=True)
assert 'oid sha256:'+hashlib.sha256(raw).hexdigest() in pointer
b=json.loads(raw)
objs={o['object_id']:o for o in b['objects']}
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip()
rows=list(csv.DictReader(a.queue.open(encoding='utf-8-sig')));out=[]
for r in rows:
 o=objs[r['original_gt_object_id']];s=objs[r['selected_gt_object_id']]
 assert o['image_id']==s['image_id']==r['image_id']
 assert o['points_1024x512'] and s['points_1024x512']
 out.append({'image_code':r['image_code'],'image_id':r['image_id'],'original_gt_object_id':r['original_gt_object_id'],'selected_gt_object_id':r['selected_gt_object_id'],'original_points_1024x512':o['points_1024x512'],'selected_points_1024x512':s['points_1024x512'],'source_commit':sha,'note':'Historical original reference restored from hash-verified formal baseline. Does not change current selected reference or interpret which version historical comments referenced.'})
a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Restored',len(out),'reference pairs; current references unchanged.')
