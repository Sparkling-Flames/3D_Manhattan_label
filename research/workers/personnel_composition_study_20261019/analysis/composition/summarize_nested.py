"""Direct nested size effects around the fixed role's half-vote capacity."""
import argparse,collections,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read,team_key,digest,write
from summarize_grid import signature,structural_distance
from geometry_diagnostics import diagnose

def finite(v):return v is not None and np.isfinite(v)
def diff(a,b,key):return float(b[key]-a[key]) if finite(a.get(key)) and finite(b.get(key)) else None

def summarize(requests,runs,snapshot,out):
    manifest=read(requests);pools={p['pool_id']:p for p in read(snapshot)['images']};by=collections.defaultdict(list)
    for ch in manifest['chains']:by[ch['pool_id']].append(ch)
    points=[];transitions=[];workers=set();allteams=set()
    for pid,chains in by.items():
        pool=pools[pid];cache=read(runs/'pools'/(pid+'.json.gz'));assert cache['context']['pool_digest']==digest(pool)
        teams={t['team_key']:t for t in cache['teams']};diags={};sigs={}
        for ch in chains:
            previous=None
            for point in ch['points']:
                t=teams[point['team_key']];assert sorted(t['member_workers'])==point['worker_ids'];assert team_key(pid,t['member_workers'])==point['team_key']
                if t['team_key'] not in diags:
                    diags[t['team_key']]=diagnose((t.get('geometry') or {}).get('footprint'),pool['reference']['floor_xz_h'])
                    sigs[t['team_key']]=signature(t)
                ds=diags[t['team_key']]
                row={k:ch[k] for k in ['phase','chain_id','method_id','domain','pool_id','replicate','fixed_n']}
                row.update({k:pool['meta'][k] for k in ['image','building','difficulty','layer','scene','reference_id','reference_version']})
                row.update(k=t['k'],added_n=point['added_n'],fixed_class=ch['fixed_class'],added_class=ch['added_class'],team_key=t['team_key'],member_workers='|'.join(t['member_workers']),counts=json.dumps(point['counts'],sort_keys=True),
                    B8L2=t.get('B8L2'),D10=t.get('D10'),nodes=t.get('nodes'),minimum_support=t['minimum_support'],score_status=t.get('score_status'),complete=bool(t.get('complete_evaluable')),new_n=t['new_n'],
                    diag_wall_coverage_05=ds.get('diag_wall_coverage_05'),diag_corner_recall_05=ds.get('diag_corner_recall_05'),IoU3D100=t.get('IoU3D100'),iou_2d=t.get('iou_2d'))
                points.append(row);workers.update(t['member_workers']);allteams.add(t['team_key'])
                if previous is not None:
                    pa,ta=previous;assert set(ta['member_workers'])<set(t['member_workers']) and len(set(t['member_workers'])-set(ta['member_workers']))==1
                    sa,sb=sigs[ta['team_key']],sigs[t['team_key']]
                    fd=None
                    if sa['floor'] is not None and sb['floor'] is not None and ta.get('complete_floor_evaluable') and t.get('complete_floor_evaluable'):
                        inter=sa['floor'].intersection(sb['floor']).area;union=sa['floor'].area+sb['floor'].area-inter;fd=1-inter/union if union>0 else None
                    bound,reason,shift=structural_distance(sa['points'],sb['points'])
                    before=pa['k'];m=ch['fixed_n'];tag='critical_2m_to_2m1' if before==2*m else ('earlier_no_threshold_step' if before==2*m-1 else ('later_no_threshold_step' if before==2*m+1 else 'other'))
                    tr={k:row[k] for k in ['phase','chain_id','method_id','domain','pool_id','image','building','difficulty','layer','scene','fixed_n','fixed_class','added_class','replicate']}
                    tr.update(before_k=before,after_k=row['k'],tag=tag,before_team=pa['team_key'],after_team=row['team_key'],added_worker=next(iter(set(t['member_workers'])-set(ta['member_workers']))),
                        Q_change=diff(pa,row,'B8L2'),D10_change=diff(pa,row,'D10'),node_change=diff(pa,row,'nodes'),corner_change=diff(pa,row,'diag_corner_recall_05'),wall_change=diff(pa,row,'diag_wall_coverage_05'),IoU3D100_change=diff(pa,row,'IoU3D100'),
                        before_complete=pa['complete'],after_complete=row['complete'],complete_lost=pa['complete'] and not row['complete'],complete_restored=row['complete'] and not pa['complete'],
                        floor_jaccard_difference=fd,structural_bound_cyclic_deg=bound,structure_reason=reason,threshold_increase=row['minimum_support']-pa['minimum_support'])
                    transitions.append(tr)
                previous=(row,t)
    out.mkdir(parents=True,exist_ok=True);P=pd.DataFrame(points);T=pd.DataFrame(transitions)
    P.to_csv(out/'nested_points.csv.gz',index=False);T.to_csv(out/'nested_transitions.csv.gz',index=False)
    rows=[]
    for keys,g in T.groupby(['phase','method_id','domain','fixed_n','tag']):
        row=dict(zip(['phase','method_id','domain','fixed_n','tag'],keys));row.update(transitions=len(g),chains=g.chain_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique())
        for metric in ['Q_change','D10_change','node_change','corner_change','wall_change','IoU3D100_change','floor_jaccard_difference','complete_lost','complete_restored']:
            img=g.groupby(['building','image'])[metric].mean();b=img.groupby('building').mean();row[metric+'_valid']=int(g[metric].notna().sum());row[metric+'_image_mean']=img.mean();row[metric+'_building_mean']=b.mean();row[metric+'_building_negative']=int((b<0).sum())
        row.update(node_loss_fraction=(g.node_change.dropna()<0).mean(),corner_loss_fraction=(g.corner_change.dropna()<0).mean(),Q_drop_over2_fraction=(g.Q_change.dropna()<-2).mean(),Q_drop_over2_valid=int(g.Q_change.notna().sum()))
        rows.append(row)
    pd.DataFrame(rows).to_csv(out/'nested_summary.csv',index=False)
    # Paired changes within the same actual nested member chain; equal building
    # weights are retained. This is a descriptive mechanism contrast, not an
    # independently randomized threshold intervention.
    C=T[T.tag.eq('critical_2m_to_2m1')].copy();paired=[]
    for other in ['earlier_no_threshold_step','later_no_threshold_step']:
        J=C.merge(T[T.tag.eq(other)],on='chain_id',suffixes=('_critical','_neighbor'))
        for _,r in J.iterrows():
            z={k:r[k+'_critical'] for k in ['phase','method_id','domain','fixed_n','pool_id','image','building']};z.update(chain_id=r.chain_id,neighbor=other)
            for metric in ['Q_change','D10_change','node_change','corner_change','wall_change']:
                a,b=r[metric+'_critical'],r[metric+'_neighbor'];z[metric+'_critical_minus_neighbor']=float(a-b) if finite(a) and finite(b) else None
            paired.append(z)
    pd.DataFrame(paired).to_csv(out/'nested_neighbor_contrasts.csv.gz',index=False)
    write(out/'NESTED_RECEIPT.json',dict(request_sha256=hashlib.sha256(requests.read_bytes()).hexdigest(),points=len(P),transitions=len(T),chains=P.chain_id.nunique(),images=P.image.nunique(),buildings=P.building.nunique(),workers=len(workers),unique_teams=len(allteams),member_nesting_verified=True,critical_definition='n=2m to2m+1: one common-role member added, fixed detail-role m workers unchanged; supplementary mechanism, not general category causal effect'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--requests',type=Path,required=True);ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();summarize(a.requests,a.runs,a.snapshot,a.out)

if __name__=='__main__':main()
