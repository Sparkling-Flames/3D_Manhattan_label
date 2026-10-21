#!/usr/bin/env python3
"""Bound-cyclic raw-annotation similarity of frozen v3 labels.

The angular/cyclic and viewer projection implementations are imported from the
unchanged repository. This is not clustering at a fusion correspondence angle.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import gzip,json,itertools,sys,importlib.util
sys.path.append('/tmp/hohonet_deps')
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
import discover_behavior_classes as b
sys.path.insert(0,str(b.REPO))
from tools.thesis_main.analysis.paired_split_research.study import angular,cyclic
spec=importlib.util.spec_from_file_location('frozen_v3_viewer',b.REPO/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)

def pair_observations():
    file=b.HERE/'RAW_GEOMETRIC_PAIRS.csv.gz'
    if file.exists():return pd.read_csv(file)
    x=b.load();x=x[x.behavior_usable & x.layer.eq('ordinary')]
    records=json.load(gzip.open(b.REPO/'research/statistics/v2_evidence_audit_20261019/records.json.gz','rt'))['records']
    wanted=set(x.object_id);geoms={}
    for r in records:
        if r['object_id'] not in wanted:continue
        points=np.asarray(r['points_1024x512'],float);g=viewer.viewer_geometry(points)
        floor=g['floor'];poly=Polygon(floor) if floor is not None else None
        geoms[r['object_id']]=(points,poly)
    rows=[]
    for (cond,img,ref),g in x.groupby(['condition','image_id','reference_id'],dropna=False):
        rr=g.sort_values('worker_id').to_dict('records')
        for aa,bb in itertools.combinations(rr,2):
            if aa['worker_id']==bb['worker_id']:continue
            pa,fa=geoms[aa['object_id']];pb,fb=geoms[bb['object_id']]
            same=len(pa)==len(pb)
            out=dict(condition=cond,image_id=img,image_code=aa['image_code'],reference_id=ref,building_id=aa['building_id'],
                worker_a=aa['worker_id'],worker_b=bb['worker_id'],object_a=aa['object_id'],object_b=bb['object_id'],
                origin_pair='|'.join(sorted([aa['origin'],bb['origin']])),same_origin=aa['origin']==bb['origin'],
                count_a=len(pa)//2,count_b=len(pb)//2,same_count=same,
                count_absdiff=abs(len(pa)-len(pb))/2,
                turn_absdiff=abs(aa['turn_n']-bb['turn_n']),redundancy_absdiff=abs(aa['near_straight_nodes_5deg']-bb['near_straight_nodes_5deg']),
                short_absdiff=abs(aa['short_turn_edges']-bb['short_turn_edges']),
                height_abslog=abs(aa['log_height']-bb['log_height']),bound_deg=np.nan,bottom_deg=np.nan,top_deg=np.nan,
                q_absdiff=abs(aa['B8L2']-bb['B8L2']))
            if same:
                top,bottom=angular(pa[::2],pb[::2]),angular(pa[1::2],pb[1::2]);bd,shift,_=cyclic(np.maximum(top,bottom));ii=np.arange(len(pa)//2);jj=(ii+shift)%len(ii)
                out.update(bound_deg=bd,bottom_deg=float(bottom[ii,jj].max()),top_deg=float(top[ii,jj].max()))
            if fa is not None and fb is not None and fa.is_valid and fb.is_valid:
                inter=fa.intersection(fb).area;out['floor_jaccard_difference']=1-inter/(fa.area+fb.area-inter)
            else:out['floor_jaccard_difference']=np.nan
            rows.append(out)
    d=pd.DataFrame(rows);b.save(d,file.name);return d

def aggregate(g,within,scheme,metric):
    g=g.copy();g['within']=within
    keys=['building_id','image_id','reference_id']
    if scheme=='equal_count_source':
        g=g[g.same_count];keys+=['count_a','origin_pair']
    elif scheme=='equal_count_source_historyQ':
        g=g[g.same_count & g.hist_q_mean.notna() & g.hist_q_diff.notna()].copy()
        g['qmean_bin']=np.floor(g.hist_q_mean/5).astype(int);g['qdiff_bin']=np.floor(g.hist_q_diff/5).astype(int)
        keys+=['count_a','origin_pair','qmean_bin','qdiff_bin']
    elif scheme=='equal_count':g=g[g.same_count]
    else:raise ValueError(scheme)
    gg=g[g[metric].notna()]
    a=gg.groupby(keys+['within'],dropna=False)[metric].agg(['mean','size']).unstack('within')
    if True not in a['mean'] or False not in a['mean']:return None
    a=a[a['mean'][True].notna()&a['mean'][False].notna()]
    if not len(a):return None
    z=pd.DataFrame({'within':a['mean'][True],'between':a['mean'][False],
        'pairs':a['size'][True]+a['size'][False]}).reset_index()
    z['difference']=z.within-z.between
    panels=z.groupby(['building_id','image_id','reference_id'],dropna=False)[['within','between','difference']].mean().reset_index()
    images=panels.groupby(['building_id','image_id'])[['within','between','difference']].mean().reset_index()
    buildings=images.groupby('building_id')[['within','between','difference']].mean()
    diff=buildings.difference.to_numpy();rng=np.random.default_rng(2026102137)
    bt=np.mean(rng.choice(diff,size=(2000,len(diff)),replace=True),axis=1)
    r=dict(scheme=scheme,metric=metric,pairs_before_matching=len(gg),pairs_contributing=int(z.pairs.sum()),
        strata=len(z),images=images.image_id.nunique(),buildings=len(buildings),within=buildings.within.mean(),
        between=buildings.between.mean(),within_minus_between=diff.mean(),ci_lo=np.quantile(bt,.025),ci_hi=np.quantile(bt,.975),
        positive_buildings=int((diff>0).sum()),negative_buildings=int((diff<0).sum()))
    return r,buildings.reset_index()

def main():
    assert (b.HERE/'LABEL_FREEZE.json').exists()
    d=pair_observations();l=pd.read_csv(b.HERE/'ALL_METHOD_LABELS_LOBO.csv.gz')
    qt=pd.read_csv(b.REPO/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz')
    qt=qt[qt.heldout_building.ne('ALL')][['condition','heldout_building','worker_id','q_effect']]
    for suffix in ['a','b']:
        q=qt.rename(columns={'heldout_building':'building_id','worker_id':'worker_'+suffix,'q_effect':'hist_q_'+suffix})
        d=d.merge(q,on=['condition','building_id','worker_'+suffix],validate='many_to_one')
    d['hist_q_mean']=(d.hist_q_a+d.hist_q_b)/2;d['hist_q_diff']=abs(d.hist_q_a-d.hist_q_b)
    summaries=[];bybuilding=[]
    metrics=['bound_deg','bottom_deg','top_deg','floor_jaccard_difference','height_abslog','turn_absdiff','redundancy_absdiff','short_absdiff']
    for method,ll in l.groupby('method'):
        p=d.copy()
        for suffix in ['a','b']:
            zz=ll[['condition','heldout_building','worker_id','coarse_label','fine_label','known']].rename(columns={'heldout_building':'building_id','worker_id':'worker_'+suffix,
                'coarse_label':'coarse_'+suffix,'fine_label':'fine_'+suffix,'known':'known_'+suffix})
            p=p.merge(zz,on=['condition','building_id','worker_'+suffix],validate='many_to_one')
        p=p[p.known_a&p.known_b]
        for cond,g in p.groupby('condition'):
            for level in ['coarse','fine','fine_within_parent']:
                z=g[g.coarse_a.eq(g.coarse_b)] if level=='fine_within_parent' else g
                tier='fine' if level.startswith('fine') else 'coarse';within=z[tier+'_a'].eq(z[tier+'_b'])
                for scheme in ['equal_count','equal_count_source','equal_count_source_historyQ']:
                    for metric in metrics:
                        out=aggregate(z,within,scheme,metric)
                        if out is None:continue
                        s,bb=out;meta=dict(method=method,condition=cond,tier=level)
                        summaries.append({**meta,**s});bb=bb.assign(**meta,scheme=scheme,metric=metric);bybuilding.append(bb)
        b.save(pd.DataFrame(summaries),'RAW_GEOMETRIC_SIMILARITY_SUMMARY.csv')
    b.save(pd.concat(bybuilding,ignore_index=True),'RAW_GEOMETRIC_SIMILARITY_BUILDINGS.csv')
    b.js('RAW_GEOMETRIC_SIMILARITY_CONTRACT.json',dict(raw_pairs=len(d),
        points='unchanged points_1024x512, primary_expression personal_comparison valid floor, ordinary; historical exclusions are behavior only',
        angular='repository paired_split_research angular and cyclic; common top/bottom cyclic shift; equal corner count required',
        floor='unchanged continuous-coordinate viewer geometry; no ring reorder, point deletion, reference use or scoring',
        matching='count_a AND origin_pair shared strata; optional historical Q pair mean and difference 5-point bins; require both within and between in same stratum',
        aggregation='strata within reference, reference within image, image within building, buildings equally',
        within_vs_between='negative means same-class raw annotations are closer; this does not establish interchangeability or correctness',
        labels='outer-building excluded, K/family chosen in inner raw-history validation; no team outcomes'))
    print(pd.DataFrame(summaries).query("scheme=='equal_count_source' and metric=='bound_deg'").round(4).to_string(index=False))

if __name__=='__main__':main()
