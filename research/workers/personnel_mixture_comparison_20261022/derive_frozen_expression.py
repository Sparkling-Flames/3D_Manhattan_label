#!/usr/bin/env python3
"""Attach structural measurements to frozen geometry; never run fusion/score."""
from pathlib import Path
import gzip,hashlib,io,json,os
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
SOURCE=REPO/'research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz'

def expression(s):
    g=json.loads(s);p=np.asarray(g.get('footprint') or [],dtype=float)
    if p.ndim!=2 or len(p)<3 or not np.isfinite(p).all():return [np.nan]*3
    e=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(e,axis=1)
    if np.any(length<1e-10):return [np.nan]*3
    angle=np.degrees(np.arccos(np.clip(np.sum(np.roll(e,1,axis=0)*e,axis=1)/(np.roll(length,1)*length),-1,1)))
    redundancy=(angle<=5)
    short=(length/length.sum()<.04)&(angle>=15)&(np.roll(angle,-1)>=15)
    return [int((~redundancy).sum()),int(short.sum()),int(redundancy.sum())]

def main():
    s=pd.read_csv(SOURCE,usecols=['team_key','geometry_json'])
    out=pd.DataFrame([expression(v) for v in s.geometry_json],columns=['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n'])
    out.insert(0,'team_key',s.team_key)
    target=HERE/'inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz';target.parent.mkdir(exist_ok=True)
    payload=gzip.compress(out.to_csv(index=False).encode('utf-8-sig'),mtime=0)
    tmp=target.with_suffix('.tmp')
    with tmp.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    assert len(pd.read_csv(io.BytesIO(gzip.decompress(tmp.read_bytes()))))==len(out)
    os.replace(tmp,target)
    receipt={'source':str(SOURCE.relative_to(REPO)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
      'rows':len(out),'finite_rows':int(out.fusion_turn_n.notna().sum()),'data':'real_v2','new_fusion':0,'new_score':0,
      'parameters':{'redundant_angle_max_deg':5,'short_edge_perimeter_fraction_max':.04,'short_endpoint_turn_min_deg':15},
      'output_sha256':hashlib.sha256(payload).hexdigest()}
    (HERE/'inputs/CLOSURE_ENDPOINT_EXPRESSIONS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
