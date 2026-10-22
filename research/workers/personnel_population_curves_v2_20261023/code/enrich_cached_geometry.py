"""Attach recovered historical candidate geometry without re-scoring or re-fusing.

Run after native endpoint workers finish. Writes pool checkpoints atomically, then
rebuilds the canonical scalar/prefix tables. Each input geometry source is retained.
"""
import argparse,json,sys,math
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from run_prefix_endpoints import read,save,normalize,geometry_enrich,setup,consolidate

def score_blocks(row):
    """Named B8L2/D10 explanation blocks, without changing any saved score.

    Historical unprefixed direction_loss and WQ fields belong to the older
    working-model diagnostics; do not silently relabel them as B8L2 components.
    These explicit fields use the frozen B8L2 formula from the quality closeout.
    """
    names=('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')
    values=[row.get(x) for x in names]
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
        return row
    iou,sbottom,direction,hmean,hcenter=values
    if iou<=0:return row
    floor=(1/iou-1)+sbottom*sbottom/32
    d8=1.5*direction*direction/(direction*direction+64)
    d10=1.5*direction*direction/(direction*direction+100)
    hg=(hmean/.8)**2;hl=(hcenter/.25)**2;height=hg+hl
    row.update(B8_floor_block=floor,B8_direction_block=d8,
               B8_global_height_block=hg,B8_local_height_block=hl,
               B8_height_block=height,D10_direction_block=d10)
    # A reproducible explanation diagnostic, never a replacement score.
    if row.get('B8L2') is not None:
        row['B8_formula_residual']=row['B8L2']-100/(1+math.hypot(floor,d8)+height)
    return row

def paired_reference_positions(row,pool,fe):
    """Separate top/bottom ray positions under the existing pair correspondence.

    This is a diagnostic assignment using max(top angular distance, bottom
    angular distance), as in reference_structure. Unmatched corners are counted
    separately; low position error on surviving pairs cannot stand for complete
    structure or a semantic identification of every corner.
    """
    points=(row.get('geometry') or {}).get('points')
    if points is None:return row
    a=np.asarray(points,float);b=np.asarray(pool['reference']['points_1024x512'],float)
    if a.ndim!=2 or len(a)<2 or len(a)%2 or not np.isfinite(a).all():return row
    top=fe.angular(a[::2],b[::2]);bottom=fe.angular(a[1::2],b[1::2])
    cost=np.maximum(top,bottom);i,j=linear_sum_assignment(cost)
    if len(i):
        row.update(ref_top_pair_mean_deg=float(top[i,j].mean()),
            ref_bottom_pair_mean_deg=float(bottom[i,j].mean()),
            ref_top_pair_max_deg=float(top[i,j].max()),
            ref_bottom_pair_max_deg=float(bottom[i,j].max()),
            ref_assigned_pair_n=len(i),ref_unassigned_pair_n=len(b)//2-len(i),
            candidate_unassigned_pair_n=len(a)//2-len(i))
    return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);p.add_argument('--orders',required=True);p.add_argument('--geometry',required=True,action='append');p.add_argument('--benchmark');a=p.parse_args()
    out=Path(a.out);gs,fe,fr,sg=setup(a.repo);pools=gs.pool_lookup();lookup={}
    benchmark_keys={r['team_key'] for r in read(a.benchmark)} if a.benchmark else set()
    for path in a.geometry:
        for r in pd.read_csv(path,keep_default_na=False).to_dict('records'):
            key=r['team_key'];text=r.get('geometry_json','')
            if key in lookup and lookup[key].get('geometry') is not None:continue
            r['geometry']=json.loads(text) if text and text not in ('nan','None') else None
            r['recovered_geometry_file']=str(Path(path).name);lookup[key]=r
    receipts=[]
    for pid in sorted(pools):
        path=out/'endpoints'/(pid+'.json.gz')
        if not path.exists():continue
        payload=read(path);new=[];changed=0
        for row in payload['teams']:
            key=row['team_key']
            if row.get('endpoint_origin') is None and key in benchmark_keys:
                row['endpoint_origin']='new_native_benchmark_20261023'
            if row.get('geometry') is None and key in lookup:
                r=lookup[key];row['geometry']=r['geometry'];row['recovered_geometry_file']=r['recovered_geometry_file']
                row['geometry_origin']=r.get('geometry_origin',r['recovered_geometry_file'])
                for field in ('node_supports',):
                    if field in r and r[field]!='':row[field]=[int(float(x)) for x in str(r[field]).split('|') if x]
                row=geometry_enrich(normalize(row,pools[pid]),pools[pid],fr);changed+=1
            elif row.get('geometry') is not None and row.get('geometry_available') is None:
                row=geometry_enrich(normalize(row,pools[pid]),pools[pid],fr)
            new.append(paired_reference_positions(score_blocks(row),pools[pid],fe))
        payload['teams']=new;save(path,payload)
        receipts.append(dict(pool_id=pid,attached_without_rescoring=changed,total=len(new),geometry_rows=sum(r.get('geometry') is not None for r in new)))
    save(out/'HISTORICAL_GEOMETRY_ATTACHMENT.json',dict(sources=a.geometry,by_pool=receipts,attached_without_rescoring=sum(r['attached_without_rescoring'] for r in receipts),new_scores=0,new_fusions=0,explicit_B8_formula_blocks_added=True,legacy_unprefixed_loss_fields_preserved=True))
    consolidate(out,pd.read_csv(a.orders,keep_default_na=False),pools)

if __name__=='__main__':main()
