"""Exact finite-roster composition calculations on a common polygon refinement.

A common refinement is only an offline integration device. An output reads votes
only from its chosen members; GT intersections enter evaluation, never voting.
q denotes the probability a COMPOSITION-SAMPLED CONSENSUS includes a tile, not
an annotator reliability or posterior truth probability. No geometry repair.
"""
from __future__ import annotations
from itertools import combinations
from math import comb
from pathlib import Path
import json, warnings
import numpy as np
import pandas as pd
from shapely import contains_xy
from shapely.geometry import Polygon, box
from shapely.ops import unary_union, polygonize
from analyze_profiles import load, higher_mask
ROOT=Path(__file__).resolve().parents[1]

def threshold(k,method):
    if method=='mv50':return (k+1)//2
    if method=='mv_strict':return k//2+1
    raise ValueError('unsupported method')

def basis_of(records,reference):
    if len({r['worker'] for r in records})!=len(records):raise ValueError('duplicate worker')
    polys=[Polygon(r['footprint']) for r in records]
    if any(not p.is_valid or p.area<=0 for p in polys):raise ValueError('invalid geometry')
    G=Polygon(reference)
    if not G.is_valid or G.area<=0:raise ValueError('invalid reference')
    tiles=list(polygonize(unary_union([p.boundary for p in polys])))
    pts=np.array([[p.representative_point().x,p.representative_point().y] for p in tiles])
    V=np.array([contains_xy(p,pts[:,0],pts[:,1]) for p in polys]);used=V.any(0)
    tiles=[p for p,k in zip(tiles,used) if k];V=V[:,used]
    area=np.array([p.area for p in tiles]);I=np.array([p.intersection(G).area for p in tiles])
    dom=unary_union(polys)
    assert abs(area.sum()-dom.area)<1e-10
    assert np.max(abs(V@area-np.array([p.area for p in polys])))<1e-10
    return dict(tiles=tiles,votes=V,area=area,intersection=I,gt_area=G.area,polygons=polys,gt=G,domain_area=dom.area)

def hyperprob(N,m,n,x):
    if x<0 or x>m or n-x<0 or n-x>N-m:return 0.
    return comb(m,x)*comb(N-m,n-x)/comb(N,n)

def inclusion_probability(NH,NL,mH,mL,h,l,method):
    if min(h,l)<0 or h>NH or l>NL or h+l==0:raise ValueError('infeasible composition')
    t=threshold(h+l,method)
    return sum(hyperprob(NH,mH,h,a)*hyperprob(NL,mL,l,b) for a in range(h+1) for b in range(l+1) if a+b>=t)

def inclusion_vector(basis,higher,h,l,method):
    NH=int(higher.sum());NL=len(higher)-NH
    mH=basis['votes'][higher].sum(0);mL=basis['votes'][~higher].sum(0)
    pair=np.c_[mH,mL];unique,inverse=np.unique(pair,axis=0,return_inverse=True)
    q=np.array([inclusion_probability(NH,NL,int(a),int(b),h,l,method) for a,b in unique])
    return q[inverse]

def additive_measures(basis,q):
    a,I,G=basis['area'],basis['intersection'],basis['gt_area'];D=basis['domain_area']
    under=float(G-I@q);over=float((a-I)@q)
    variability=float(a@(q*(1-q)))
    bias=float(G+a@(q*q)-2*I@q)
    risk=under+over
    assert abs(risk-(bias+variability))<1e-10
    return dict(expected_under_h2=under,expected_over_h2=over,expected_symdiff_h2=risk,
      expected_under_gt=under/G,expected_over_gt=over/G,expected_symdiff_gt=risk/G,
      consensus_field_bias_h2=bias,consensus_field_bias_gt=bias/G,
      consensus_field_variance_h2=variability,member_symdiff_h2=2*variability,
      member_symdiff_union=2*variability/D,
      ratio_of_expected_intersection_union=float(I@q/(G+(a-I)@q)))

def enumerate_k(basis,k):
    members=np.array(list(combinations(range(len(basis['votes'])),k)),dtype=np.int16)
    counts=basis['votes'][members].sum(1)
    out={}
    for method in ['mv50','mv_strict']:
        keep=counts>=threshold(k,method)
        inter=keep@basis['intersection'];ar=keep@basis['area']
        iou=inter/(basis['gt_area']+ar-inter)
        out[method]=dict(keep=keep,iou=iou)
    return members,out

def main():
    obj=json.loads((ROOT/'inputs/one_image_geometry.json').read_text())
    records=obj['records'];f,Y=load('matrix_original_iou.csv');tr=f.building.to_numpy()!=obj['building']
    higher=higher_mask(Y[tr].mean(0));assert higher is not None and int(higher.sum())==12
    assert [r['worker'] for r in records]==list(f.columns[2:])
    notices=[]
    with warnings.catch_warnings(record=True) as warn:
        warnings.simplefilter('always',RuntimeWarning)
        basis=basis_of(records,obj['reference']['footprint'])
        members,outs=enumerate_k(basis,4)
    notices=[str(x.message) for x in warn]
    number_h=higher[members].sum(1);rows=[];comparison=[]
    # Published original-calibration k=4 first-image values, read from composition_exact.csv.
    expected_mean={'mv50':[.9435150657243421,.9436270741365578,.94414680683217,.9450269845289023,.9463951370632063],
       'mv_strict':[.955747219135084,.9569236187683883,.9580030635808255,.9592357504788513,.9606904900802075]}
    expected_sd={'mv50':[.009827379983596271,.01334291840241259,.015164563613044203,.015931058134084734,.01574541283183787],
       'mv_strict':[.007430070354978498,.009029950928427078,.009703784016043248,.00985107658473951,.009619723764823607]}
    expected_pair={'mv50':[.06426882949706367,.07930926642563911,.08795142690339122,.09048332870141104,.08509186511279632],
       'mv_strict':[.06415586232409595,.07315786786630726,.07653565595380263,.07551487700666305,.06947258355598687]}
    for method,out in outs.items():
        for h in range(5):
            select=number_h==h;q_enum=out['keep'][select].mean(0)
            q=inclusion_vector(basis,higher,h,4-h,method)
            assert np.max(abs(q-q_enum))<1e-12
            metrics=additive_measures(basis,q);vs=out['iou'][select]
            for field,new,old in [('iou_mean',float(vs.mean()),expected_mean[method][h]),('iou_sd',float(vs.std()),expected_sd[method][h]),
                    ('member_symdiff_h2',metrics['member_symdiff_h2'],expected_pair[method][h])]:
                comparison.append(dict(method=method,higher_n=h,field=field,recomputed=new,published=old,absolute_difference=abs(new-old)))
            rows.append(dict(image=obj['image'],method=method,k=4,higher_n=h,lower_n=4-h,n=int(select.sum()),
                  iou_mean=float(vs.mean()),iou_sd=float(vs.std()),q_enum_max_difference=float(np.max(abs(q-q_enum))),**metrics))
        np.savez_compressed(ROOT/f'results/one_image_k4_{method}.npz',members=members,iou=out['iou'],higher_count=number_h)
    assert max(r['absolute_difference'] for r in comparison)<1e-12
    pd.DataFrame(comparison).to_csv(ROOT/'results/composition_30_field_checks.csv',index=False)
    pd.DataFrame(rows).to_csv(ROOT/'results/one_image_k4_exact.csv',index=False)
    grid=[]
    for method in ['mv50','mv_strict']:
        for h in range(13):
            for l in range(13):
                if h+l==0:continue
                q=inclusion_vector(basis,higher,h,l,method)
                grid.append(dict(image=obj['image'],method=method,k=h+l,higher_n=h,lower_n=l,
                    composition_count=comb(12,h)*comb(12,l),**additive_measures(basis,q)))
    pd.DataFrame(grid).to_csv(ROOT/'results/one_image_all_composition_area_expectations.csv',index=False)
    # Compare representative subsets using a freshly built current-subset arrangement.
    direct=[]
    for h in [0,2,4]:
        ix=np.flatnonzero(number_h==h)[0]; sub=[records[j] for j in members[ix]]
        sb=basis_of(sub,obj['reference']['footprint']);s=sb['votes'].sum(0)
        for method in ['mv50','mv_strict']:
            region=unary_union([t for t,k in zip(sb['tiles'],s>=threshold(4,method)) if k])
            score=region.intersection(basis['gt']).area/region.union(basis['gt']).area
            assert abs(score-outs[method]['iou'][ix])<1e-12
            direct.append(dict(method=method,higher_n=h,members='|'.join(r['worker'] for r in sub),
                 current_subset_tiling_iou=score,global_refinement_iou=float(outs[method]['iou'][ix])))
    pd.DataFrame(direct).to_csv(ROOT/'results/current_subset_direct_checks.csv',index=False)
    # True duplicates in this stored footprint extract; no automatic deduplication.
    duplicate_groups={}
    for r in records:duplicate_groups.setdefault(json.dumps(r['footprint']),[]).append(r['worker'])
    dup=[v for v in duplicate_groups.values() if len(v)>1]
    # Geometric counterexamples: equal GT-IoU does not imply equal consensus geometry.
    G=box(0,0,2,2);A=G.union(box(2,.8,3,1.2));B=G.union(box(-1,.8,0,1.2))
    toy=dict(equal_score_iou_a=A.intersection(G).area/A.union(G).area,
       equal_score_iou_b=B.intersection(G).area/B.union(G).area,
       iou_sd=0.,independent_pair_expected_symdiff_h2=.5*A.symmetric_difference(B).area,
       stable_wrong_iou=box(0,0,1,2).intersection(G).area/G.area,stable_wrong_variation_h2=0.)
    summary=dict(image=obj['image'],candidate_n=len(records),subsets_k4=len(members),output_n_k4=2*len(members),
        tile_n=len(basis['tiles']),area_h2=basis['domain_area'],gt_area_h2=basis['gt_area'],
        source_comparison_fields=len(comparison),source_comparison_max_abs=max(r['absolute_difference'] for r in comparison),
        unique_footprints=len(duplicate_groups),identical_footprint_groups=dup,analytic_composition_states=len(grid),warnings=notices,toys=toy,
        scope='Only one complete current B-line image geometry is recomputed. Other images are matrix analyses, not re-rendered compositions.')
    (ROOT/'results/composition_kernel_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(pd.DataFrame(rows)[['method','higher_n','iou_mean','iou_sd','expected_symdiff_gt','consensus_field_bias_gt','member_symdiff_union']].to_string(index=False))

if __name__=='__main__':main()
