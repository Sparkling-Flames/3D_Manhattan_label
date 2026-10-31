"""Execute missing corrected-scope teams with frozen native fusion and scoring."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import gzip
import json
import time
import zipfile
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse,WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
OUT=BASE/'computed_delta'
PREFIX='HOHONET_doorway_v21_20261031/'

def plain(value):
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [plain(v) for v in value]
    if isinstance(value,np.generic):return plain(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value

def run_image(image,requests,out=OUT):
    path=out/(image+'.jsonl')
    done=set()
    if path.exists():
        for line in path.read_text(encoding='utf8').splitlines():
            r=json.loads(line);done.add(tuple(r['members']))
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        records=json.loads(gzip.decompress(z.read(PREFIX+'stage04_computation/design/FROZEN_RECORDS.json.gz')))
        refs=json.loads(z.read(PREFIX+'stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json'))
    refs={r['target']:r for r in refs if r['image']==image}
    engine_dir=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
    start=time.monotonic();new=0
    with cached_matching(),scoring_engine(engine_dir/'measurement_engine.zip',engine_dir/'working_models.py') as (engine,models),path.open('a',encoding='utf8') as output:
        for request in requests:
            if tuple(request['members']) in done:continue
            assert request['k']==len(request['members'])>=2
            team=[records[x] for x in request['members']]
            assert len({r['worker'] for r in team})==len(team)
            state=fuse(team,gap=WORKING_GAP)['automatic']
            candidate=state['candidate'];nodes=len(state['node_consensus']['nodes'])
            complete=request['k']!=2 and nodes>=4 and candidate.get('geometry_status')=='ok'
            values={}
            for target in request['targets']:
                ref=refs[target]
                score=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
                finite=all(score.get(k) is not None and np.isfinite(score[k]) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'])
                score.update(dual_scores(score,models) if complete and finite else dict(B8L2=None,D10=None,IoU3D100=None))
                score['complete_evaluable']=complete and finite
                values[target]=score
            payload=dict(image=image,members=request['members'],k=request['k'],geometry=candidate,nodes=nodes,
                minimum_support=state['minimum_support'],complete_evaluable=complete,
                node_supports=[g['support'] for g in state['identity_groups'] if g['selected']],scores=values,
                input_version='Pro_frozen_points_with_user_ring_receipt_no_coordinate_changes',scope_version='doorway_visual_scope_20261031_r1')
            output.write(json.dumps(plain(payload),ensure_ascii=False,allow_nan=False)+'\n');output.flush()
            new+=1
            if new%100==0:print(image,new,'/',len(requests)-len(done),'seconds',round(time.monotonic()-start),flush=True)
    return dict(image=image,already_saved=len(done),new=new,seconds=time.monotonic()-start)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sensitivity',action='store_true');args=parser.parse_args()
    out=BASE/'computed_exclude13_selected' if args.sensitivity else OUT
    out.mkdir(exist_ok=True)
    requests=json.loads((BASE/('EXCLUDE13_SELECTED_REQUESTS.json' if args.sensitivity else 'DELTA_TEAM_REQUESTS.json')).read_text(encoding='utf8'))
    missing=[r for r in requests if not r['cached_physical_team_key']]
    jobs={im:[r for r in missing if r['image']==im] for im in sorted({r['image'] for r in missing})}
    print('Missing fusion teams',len(missing),'image jobs',[(im,len(r)) for im,r in jobs.items()],flush=True)
    receipts=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(run_image,im,rows,out) for im,rows in jobs.items()]
        for future in as_completed(futures):
            receipt=future.result();receipts.append(receipt);print('completed',receipt,flush=True)
    assert sum(r['already_saved']+r['new'] for r in receipts)==len(missing)
    (out/'COMPUTATION_RECEIPT.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
