"""Score and geometry contrasts on exact equal-n/equal-m/shared-D triples."""
import argparse, collections, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from run_native import ROOT,POP,read,save,csv
from shapely.geometry import Polygon

METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
 'height_mean_ratio','nodes','floor_turn5_n','floor_redundant5_n','floor_short_edge_03_n','floor_short_edge_05_n',
 'floor_area_camera_h2','height_mean_h','height_sd_h','centroid_x_h','centroid_z_h','ref_node_recall_5','ref_node_recall_9',
 'ref_edge_recall_5','ref_edge_recall_9','reference_node_shortfall','top_y_mean_px','bottom_y_mean_px',
 'source_time_total_seconds','target_time_total_seconds','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg',
 'matched_ref_horizontal_abs_deg','matched_ref_pair_fraction','boundary_loss','direction_loss','height_loss']

def rays(p):
    u=2*np.pi*np.asarray(p)[:,0]/1024;v=np.pi*(.5-np.asarray(p)[:,1]/512)
    return np.column_stack([np.cos(v)*np.sin(u),np.sin(v),np.cos(v)*np.cos(u)])
def angular(a,b):return np.degrees(np.arccos(np.clip(rays(a)@rays(b).T,-1,1)))

def geometry_metrics(a,b):
    ga=a.get('geometry') or {};gb=b.get('geometry') or {};out={}
    fa,fb=ga.get('footprint'),gb.get('footprint')
    if fa is not None and fb is not None and len(fa)>=3 and len(fb)>=3:
        pa,pb=Polygon(fa),Polygon(fb)
        if pa.is_valid and pb.is_valid and pa.area>0 and pb.area>0:
            inter=pa.intersection(pb).area;union=pa.union(pb).area
            out.update(geometry_bev_distance=1-inter/union,geometry_centroid_distance=float(pa.centroid.distance(pb.centroid)),geometry_log_area_distance=abs(math.log(pa.area/pb.area)))
    aa,bb=ga.get('points'),gb.get('points')
    if aa is not None and bb is not None and len(aa)>=6 and len(bb)>=6:
        aa,bb=np.asarray(aa,float),np.asarray(bb,float)
        tc,bc=angular(aa[::2],bb[::2]),angular(aa[1::2],bb[1::2]);cost=np.maximum(tc,bc);i,j=linear_sum_assignment(cost)
        out.update(geometry_pair_angle=float(cost[i,j].mean()),geometry_top_angle=float(tc[i,j].mean()),geometry_bottom_angle=float(bc[i,j].mean()),geometry_unmatched_pairs=abs(len(aa)-len(bb))/2,geometry_same_pair_count=float(len(aa)==len(bb)))
    return out

def refdiagnostic(row,pool):
    p=(row.get('geometry') or {}).get('points');ref=pool['reference']['points_1024x512']
    if p is None or len(p)<6:return row
    p=np.asarray(p,float);r=np.asarray(ref,float);az=((p[::2,0,None]-r[None,::2,0]+512)%1024-512)*360/1024
    i,j=linear_sum_assignment(np.abs(az));ok=np.abs(az[i,j])<=9;i,j=i[ok],j[ok]
    row['matched_ref_pair_fraction']=len(i)/(len(r)//2)
    if len(i):
        row.update(matched_ref_top_abs_deg=float(np.abs(p[2*i,1]-r[2*j,1]).mean()*180/512),matched_ref_bottom_abs_deg=float(np.abs(p[2*i+1,1]-r[2*j+1,1]).mean()*180/512),matched_ref_horizontal_abs_deg=float(np.abs(az[i,j]).mean()))
    return row

def compute_events(ev,rows,pool):
    for r in rows.values():refdiagnostic(r,pool)
    scalars=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows.values()]).set_index('team_key')
    available=[m for m in METRICS if m in scalars];extra={};metric_table={}
    for arm in ['A','B','C']:
        ar=scalars.reindex(ev[arm+'_team_key']);ar.index=ev.index;metric_table[arm]=ar
        extra[arm+'_failed']=~ar.B8L2.notna();extra[arm+'_incomplete']=~ar.complete_evaluable.fillna(False).astype(bool)
        for m in available:extra[arm+'_'+m]=pd.to_numeric(ar[m],errors='coerce')
    for m in available:
        a,b,c=[extra[x+'_'+m] for x in ['A','B','C']]
        ok=a.notna()&b.notna()&c.notna()
        within=(b-a).abs().where(ok);cross=((c-a).abs()+(c-b).abs()).div(2).where(ok)
        extra[m+'_within']=within;extra[m+'_cross']=cross;extra[m+'_gap']=cross-within
        extra[m+'_CA']=c-a;extra[m+'_CB']=c-b;extra[m+'_BA']=b-a
    extra['ABC_scored']=~(extra['A_failed']|extra['B_failed']|extra['C_failed'])
    for comp in ['CA','CB']:
        d=extra['B8L2_'+comp];extra['C_loss10_'+comp]=np.where(d.notna(),(d<-10).astype(float),np.nan)
        extra['C_improved_'+comp]=np.where(d.notna(),(d>0).astype(float),np.nan)
    for comp,base in [('CA','A'),('CB','B')]:
        extra['record_time_'+comp+'_pct']=100*(extra['C_source_time_total_seconds']/extra[base+'_source_time_total_seconds']-1)
        extra['C_failure_or_loss10_'+comp]=np.where(~extra[base+'_failed'],(extra['C_failed']|pd.Series(extra['C_loss10_'+comp],index=ev.index).eq(1)).astype(float),np.nan)
    geometry=[];paircache={}
    for er in ev.to_dict('records'):
        per={}
        for lhs,rhs in [('A','B'),('A','C'),('B','C')]:
            key=tuple(sorted([er[lhs+'_team_key'],er[rhs+'_team_key']]))
            if key not in paircache:paircache[key]=geometry_metrics(rows[key[0]],rows[key[1]])
            per[lhs+rhs]=paircache[key]
        vals={}
        for metric in set(per['AB'])|set(per['AC'])|set(per['BC']):
            ab,ac,bc=[per[k].get(metric,np.nan) for k in ['AB','AC','BC']]
            vals.update({metric+'_AB':ab,metric+'_AC':ac,metric+'_BC':bc})
            if all(np.isfinite(x) for x in [ab,ac,bc]):vals.update({metric+'_within':ab,metric+'_cross':(ac+bc)/2,metric+'_gap':(ac+bc)/2-ab})
        geometry.append(vals)
    out=pd.concat([ev,pd.DataFrame(extra,index=ev.index),pd.DataFrame(geometry,index=ev.index)],axis=1)
    return out

def main(a):
    events=pd.read_csv(ROOT/'design'/a.stage/'EVENTS_EXACT.csv.gz');pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']};out=ROOT/'results'/a.stage;out.mkdir(parents=True,exist_ok=True);done=[];missing=[]
    for pid,g in events.groupby('pool_id',sort=False):
        target=out/'metric_shards'/(pid+'.csv.gz')
        if target.exists() and not a.refresh:
            done.append(pd.read_csv(target,low_memory=False));continue
        endpoint=ROOT/'native/endpoints'/(pid+'.json.gz')
        if not endpoint.exists():missing.append(pid);continue
        rows={r['team_key']:r for r in read(endpoint)['teams']};needed=set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)
        if not needed<=rows.keys():missing.append(pid);continue
        rows={k:rows[k] for k in needed};d=compute_events(g,rows,pools[pid]);csv(target,d);done.append(d);print('MEASURED',pid,len(d),flush=True)
    if done:
        merged=pd.concat(done,ignore_index=True);csv(out/'EVENT_METRICS.csv.gz',merged)
        save(out/'COMPLETION.json',dict(stage=a.stage,registered_events=len(events),measured_events=len(merged),pools=len(done),pending_pools=missing,complete=not missing,geometry_contract='1-IoU valid floor, camera-height centroid/area; spherical Hungarian matched-pair angle and unmatched-node count separate',reference_diagnostic='Azimuth 9-degree correspondence only for diagnostic top/bottom errors, no change to scoring or fusion.'))
        print('EVENT_METRICS',len(merged),'pending',len(missing),flush=True)
    if missing and not a.partial:raise RuntimeError(f'Pending {len(missing)} pools')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',default='screen');p.add_argument('--partial',action='store_true');p.add_argument('--refresh',action='store_true');main(p.parse_args())
