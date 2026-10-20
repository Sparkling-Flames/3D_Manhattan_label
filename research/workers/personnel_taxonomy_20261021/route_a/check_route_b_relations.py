#!/usr/bin/env python3
"""Independent raw-answer relation evaluation of route B's held-out labels.

Uses only the label for which the entire target building was excluded.
The geometry table is the formal frozen-quality panel, not the larger non-OOS
behavior inventory used to discover B; its scope is explicitly reported.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_route_a import eval_crossfit,write_json,SEED

HERE=Path(__file__).resolve().parent

def q_source_match(p,condition,level):
    p=p[p.same_count.eq(1)].copy()
    p['meanQbin']=(p.q_mean//10).astype(int)
    p['diffQbin']=(p.q_absdiff//5).astype(int)
    out=[]
    for metric in ['same9','same12','bound_deg','bottom_deg','top_deg','floor_iou']:
        strata=['building_id','image_id','origin_pair','count_a','meanQbin','diffQbin']
        grouped=p.groupby(strata+['within'])[metric].agg(['mean','count']).unstack('within')
        a=grouped['mean']
        a=a.reindex(columns=[True,False]).dropna()
        matched=grouped['count'].reindex(a.index).fillna(0).sum(axis=1).sum()
        a['gap']=a[True]-a[False]
        im=a.groupby(['building_id','image_id']).mean();b=im.groupby('building_id').mean()
        if len(b)==0:continue
        vals=b.gap.to_numpy();rng=np.random.default_rng(SEED)
        bs=rng.choice(vals,size=(2000,len(vals)),replace=True).mean(1)
        out.append(dict(condition=condition,stage='leave_building_out',method='B_'+level,k=level,
            panel='equal_count_origin_count_Qmean10_Qdiff5_matched',metric=metric,n_pairs=len(p),
            n_pairs_contributing=int(matched),n_pairs_unmatched=int(len(p)-matched),n_images=len(im),n_buildings=len(b),
            n_matching_strata=len(a),within=b[True].mean(),between=b[False].mean(),within_minus_between=vals.mean(),
            ci_lo=np.quantile(bs,.025),ci_hi=np.quantile(bs,.975),buildings_positive=int((vals>0).sum()),buildings_negative=int((vals<0).sum())))
    return out

def main():
    lab=pd.read_csv(HERE.parent/'route_b/lobo_labels.csv')
    p=pd.read_csv(HERE/'pair_observations.csv.gz')
    allrows=[];bypair=[];coverage=[];details=[];source_matched=[]
    for condition in ['manual','semi']:
        for level in ['coarse','fine']:
            for layer in ['ordinary_'+condition,'doorway_'+condition]:
                ps=p[p.layer.eq(layer)].copy()
                if not len(ps):continue
                ls=lab[lab.condition.eq(condition)&lab.label_status.eq('assigned')]
                mapping=ls.set_index(['heldout_building','worker_id'])[level+'_class'].to_dict()
                ps['class_a']=[mapping.get((b,w),None) for b,w in zip(ps.building_id,ps.worker_a)]
                ps['class_b']=[mapping.get((b,w),None) for b,w in zip(ps.building_id,ps.worker_b)]
                before=len(ps);ps=ps.dropna(subset=['class_a','class_b'])
                ps['within']=ps.class_a.eq(ps.class_b)
                coverage.append(dict(condition=condition,level=level,layer=layer,pairs_before=before,pairs_labeled=len(ps),
                    images=ps.image_id.nunique(),buildings=ps.building_id.nunique(),workers=len(set(ps.worker_a)|set(ps.worker_b))))
                zz=eval_crossfit(ps,'B_'+level,level,condition)
                for r in zz:r['layer']=layer
                allrows+=zz
                zq=q_source_match(ps,condition,level)
                for r in zq:r['layer']=layer
                source_matched+=zq
                ps['class_pair']=['|'.join(sorted([a,b])) for a,b in zip(ps.class_a,ps.class_b)]
                for panel,q in [('all',ps),('same_count',ps[ps.same_count.eq(1)])]:
                    r=q.groupby(['class_pair','building_id','image_id'])[['same9','same12','same_count','bound_deg','bottom_deg','top_deg','floor_iou','height_abslog','q_absdiff']].mean()
                    bybuild=r.groupby(['class_pair','building_id']).mean()
                    fin=bybuild.groupby('class_pair').mean().reset_index()
                    support=q.groupby('class_pair').agg(n_pairs=('worker_a','size'),n_images=('image_id','nunique'),n_buildings=('building_id','nunique')).reset_index()
                    fin=fin.merge(support,on='class_pair');fin['condition']=condition;fin['level']=level;fin['layer']=layer;fin['panel']=panel
                    bypair+=fin.to_dict('records')
                if layer.startswith('ordinary'):
                    ps[['pool_id','image_id','image_code','building_id','worker_a','worker_b','object_a','object_b','class_a','class_b','within','same_count','same9','same12','bound_deg','bottom_deg','top_deg','floor_iou']].to_csv(HERE/f'B_crossfit_pairs_{condition}_{level}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
                    for pid,g in ps[ps.same_count.eq(1)].groupby('pool_id'):
                        for anchor in sorted(set(g.worker_a)|set(g.worker_b)):
                            z=g[g.worker_a.eq(anchor)|g.worker_b.eq(anchor)]
                            same=z[z.within].dropna(subset=['bound_deg']);other=z[~z.within].dropna(subset=['bound_deg'])
                            if len(same)==0 or len(other)==0:continue
                            # Middle pairs give reviewable, less extremal displays.
                            s=same.sort_values('bound_deg').iloc[len(same)//2]
                            o=other.sort_values('bound_deg').iloc[len(other)//2]
                            partner=lambda row: row.worker_b if row.worker_a==anchor else row.worker_a
                            details.append(dict(condition=condition,level=level,pool_id=pid,image_code=s.image_code,building_id=s.building_id,
                                anchor=anchor,same_class_partner=partner(s),other_class_partner=partner(o),same_bound=s.bound_deg,other_bound=o.bound_deg,
                                distance_gain=o.bound_deg-s.bound_deg,same_floor_iou=s.floor_iou,other_floor_iou=o.floor_iou,
                                same_object_a=s.object_a,same_object_b=s.object_b,other_object_a=o.object_a,other_object_b=o.object_b))
    pd.DataFrame(allrows+source_matched).to_csv(HERE/'B_raw_answer_validation.csv',index=False)
    pd.DataFrame(bypair).to_csv(HERE/'B_class_pair_geometry.csv',index=False)
    pd.DataFrame(coverage).to_csv(HERE/'B_raw_answer_coverage.csv',index=False)
    dd=pd.DataFrame(details);out=[]
    for (c,l),g in dd.groupby(['condition','level']):
        for tag,ascending in [('positive',False),('counterexample',True)]:
            z=g.sort_values('distance_gain',ascending=ascending).drop_duplicates('pool_id').head(5).copy();z['case_kind']=tag;out.append(z)
    pd.concat(out,ignore_index=True).to_csv(HERE/'B_geometry_case_candidates.csv',index=False)
    print(pd.DataFrame(allrows+source_matched).query("layer.str.startswith('ordinary') and metric in ['same9','bound_deg','floor_iou'] and panel in ['all_pairs','equal_count','equal_count_origin_Qmean10_Qdiff5_matched']")[['condition','method','panel','metric','n_images','n_buildings','within','between','within_minus_between','ci_lo','ci_hi']].to_string(index=False))

if __name__=='__main__':main()
