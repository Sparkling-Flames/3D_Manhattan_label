"""Exact retained diagnostics from original measure_events.py; no score/fusion changes."""
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon

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
