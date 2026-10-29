"""Reproduce one saved team using only the portable frozen source/input bundle.

This is a reproducibility check, not another sampled experimental endpoint.
"""
from __future__ import annotations
import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import argparse,gzip,json,math,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def maximum_difference(a,b):
    if isinstance(a,dict):
        assert set(a)==set(b)
        return max([maximum_difference(a[k],b[k]) for k in a] or [0.])
    if isinstance(a,list):
        assert len(a)==len(b)
        return max([maximum_difference(x,y) for x,y in zip(a,b)] or [0.])
    if isinstance(a,(float,int)) and not isinstance(a,bool):return abs(float(a)-float(b))
    assert a==b,(a,b)
    return 0.


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--team-key');ap.add_argument('--out');a=ap.parse_args()
    repo=ROOT/'stage07_reproduction/minimum_source/repo'
    sys.path.insert(0,str(repo/'research/workers/personnel_v21_reselection_20261029/experiment'))
    from benchmark_engine import load_engine
    old=None
    for folder in sorted((ROOT/'stage03_endpoints/pools').iterdir()):
        if not (folder/'CHECKS.json').exists():continue
        if a.team_key and not a.team_key.startswith(folder.name+'__'):continue
        for path in sorted(folder.glob('part_*.jsonl.gz')):
            with gzip.open(path,'rt',encoding='utf-8-sig') as f:
                for line in f:
                    row=json.loads(line)
                    if (a.team_key and row['team_key']==a.team_key) or (not a.team_key and row.get('B8L2') is not None):
                        old=row;break
            if old:break
        if old:break
    assert old,'Requested completed saved endpoint not found'
    pools={p['pool_id']:p for rel in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json']
        for p in json.loads((repo/'research/data/releases/v2.1'/rel).read_text())['images']}
    pool=pools[old['pool_id']]
    workers=old['member_workers'] if isinstance(old['member_workers'],list) else old['member_workers'].split('|')
    native=load_engine(repo)
    with native.Engine(full_state=False) as engine:
        new=engine.evaluate(pool,workers)
        geometry=new.get('geometry')
        if geometry is not None:
            extra=engine.scorecache.get(engine.fr.digest([new['k']==2,new.get('nodes'),geometry]))
            if extra:new.update(extra)
    fields=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
            'nodes','minimum_support','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
            'geometry_area_h2','height_mean_h','centroid_x_h','centroid_z_h','source_time_total_seconds',
            'boundary_loss','direction_loss','height_loss']
    differences={}
    for field in fields:
        v,w=old.get(field),new.get(field)
        assert (v is None)==(w is None),(field,v,w)
        if v is not None:
            differences[field]=abs(float(v)-float(w));assert differences[field]<1e-7,(field,v,w)
    assert old.get('score_status')==new.get('score_status')
    geomdiff=maximum_difference(old.get('geometry'),new.get('geometry'));assert geomdiff<1e-9
    new.update(data_release='v2.1',underlying_data_version='v2.1',repository_commit='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff')
    out=Path(a.out) if a.out else ROOT/'stage07_reproduction/verification'
    out.mkdir(parents=True,exist_ok=True)
    (out/'REPRODUCED_ENDPOINT.json').write_text(json.dumps(native.gs.clean(new),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    receipt={'team_key':old['team_key'],'pool_id':old['pool_id'],'members':workers,
      'source_tree':str(repo),'portable_source_tree_used':True,'full_original_repository_used':False,
      'metric_differences':differences,'geometry_maximum_difference':geomdiff,'score_status_equal':True,
      'passed':True,'verification_fusion_calls':1,'new_physical_teams':0,'study_sample_changed':False}
    (out/'REPRODUCTION_PARITY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
