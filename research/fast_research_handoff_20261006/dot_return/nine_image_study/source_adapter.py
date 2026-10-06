"""Explicit adapter for authoritative handed-off numerical baseline.

Copied algebra from paired_split_research/study.py:angular and
global_pair_consensus_20261004.py:_identities. No input rewriting.
The old prototype remains byte-for-byte vendored and unmodified.
"""
import numpy as np

def source_distances(nodes):
    def angular(a,b):
        a=np.asarray(a,float);b=np.asarray(b,float)
        du=((a[:,None,0]-b[None,:,0]+512.)%1024.-512.)*(2*np.pi/1024.)
        va=((a[:,1]+.5)/512.-.5)*np.pi;vb=((b[:,1]+.5)/512.-.5)*np.pi
        h=np.sin((va[:,None]-vb[None,:])/2.)**2+np.cos(va[:,None])*np.cos(vb[None,:])*np.sin(du/2.)**2
        h=np.clip(h,0.,1.)
        return np.degrees(2*np.arctan2(np.sqrt(h),np.sqrt(1-h)))
    p=np.array([n['points'] for n in nodes])
    top=angular(p[:,0]-.5,p[:,0]-.5);bottom=angular(p[:,1]-.5,p[:,1]-.5)
    return {'top':top,'bottom':bottom,'pair':np.maximum(top,bottom)}

def source_center(nodes,indices,pair_d):
    indices=np.asarray(indices,int);p=np.array([n['points'] for n in nodes])
    local=pair_d[np.ix_(indices,indices)]
    anchor=int(indices[int(np.argmin(local.sum(axis=1)))])
    xs=(p[indices,0,0]-p[anchor,0,0]+512)%1024-512
    ambiguous=bool(np.ptp(xs)>=512-1e-9 or np.any(abs(abs(xs)-512)<1e-9))
    center=None
    if not ambiguous:
        x=float((p[anchor,0,0]+np.median(xs))%1024)
        center=[[x,float(np.median(p[indices,0,1]))],[x,float(np.median(p[indices,1,1]))]]
    return dict(points=center,status='ambiguous' if ambiguous else 'ok',
                anchor={'id':nodes[anchor]['id'],'pair_index':nodes[anchor]['pair_index']},
                method='authoritative_first_argmin_medoid_periodic_coordinate_median',
                warning='conditional correspondence center; generated location has no new votes')
