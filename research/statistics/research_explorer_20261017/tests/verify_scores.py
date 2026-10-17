import argparse,csv,math,json,hashlib,collections,statistics
from pathlib import Path
parser=argparse.ArgumentParser(description='Verify saved quality measurements; this does not rerun geometry.')
parser.add_argument('--source-dir',type=Path,default=Path(__file__).resolve().parents[4])
a=parser.parse_args()
p=a.source_dir/'research/quality/quality_b8l2_d10_20261017'
r=list(csv.DictReader((p/'quality_records.csv').open(encoding='utf-8-sig')))
def q(x,c):
 I,S,D,Hm,Hc=map(lambda k:float(x[k]),['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'])
 if I<=0:return 0
 F=1/I-1+S*S/32; d=1.5*D*D/(D*D+c*c)
 return 100/(1+math.hypot(F,d)+(Hm/.8)**2+(Hc/.25)**2)
delta=[float(x['D10'])-float(x['B8L2']) for x in r]
out={'source_commit':'090883fab97298fb18033638487b0f4a84bf0d54','rows':len(r),'unique_object_ids':len({x['object_id'] for x in r}),'images':len({x['image_id'] for x in r}),'workers':len({x['worker_id'] for x in r}),'condition':dict(collections.Counter(x['condition'] for x in r)),'quality_use':dict(collections.Counter(x['quality_use'] for x in r)),'max_B8L2_recomposition_error':max(abs(q(x,8)-float(x['B8L2'])) for x in r),'max_D10_recomposition_error':max(abs(q(x,10)-float(x['D10'])) for x in r),'D10_delta':{'mean':statistics.mean(delta),'median':statistics.median(delta),'max':max(delta),'min':min(delta)},'quality_all_explicit_true':all(x['quality_usable'].lower()=='true' for x in r),'OOS_count':sum(x['is_oos'].lower()=='true' for x in r),'source_time_n':sum(x['source_active_time_seconds']!='' for x in r),'target_time_n':sum(x['target_matched_time_seconds']!='' for x in r),'new_batch_count':sum(x['new_batch'].lower()=='true' for x in r),'new_batch_target_time_n':sum(x['new_batch'].lower()=='true' and x['target_matched_time_seconds']!='' for x in r),'source_sha256':hashlib.sha256((p/'quality_records.csv').read_bytes()).hexdigest(),'scope':'Independent algebra/count check of saved measurements; not a new geometry/loader rerun'}
expected=json.loads((Path(__file__).resolve().parents[1]/'verification/root-score-checks.json').read_text())
assert out==expected, 'Quality source/count/score check differs from the pinned snapshot'
print(json.dumps(out,ensure_ascii=False,indent=2))
