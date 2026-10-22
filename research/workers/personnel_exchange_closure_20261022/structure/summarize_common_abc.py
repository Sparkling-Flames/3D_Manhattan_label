#!/usr/bin/env python3
"""Same-support signed/absolute ABC contrasts from completed events only."""
import json
from pathlib import Path
import pandas as pd
from analyze_structure import BASE, hierarchy
from register_structure import HERE, sha, write, save

METRICS = ['same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10',
           'common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage']

def main():
    cols=BASE+['building','image','pool_id','panel_id','background_stratum','difficulty',
               'background_target_band','all_scored']+METRICS
    E=pd.read_csv(HERE/'EVENTS_COMPLETE.csv.gz',usecols=cols)
    E=E[E.all_scored.eq(True)].copy()
    rows=[]
    for kind,extra in [('overall',[]),('difficulty',['difficulty']),('background',['background_target_band'])]:
        P,S,I,B=hierarchy(E,METRICS,extra)
        group=BASE+extra
        for k,g in E.groupby(group,dropna=False):
            key=dict(zip(group,k));i=I;b=B
            for field,val in key.items():
                i=i[i[field].eq(val)];b=b[b[field].eq(val)]
            r=dict(slice_kind=kind,**key,common_ABC_events=len(g),
                common_ABC_images=g.image.nunique(),common_ABC_buildings=g.building.nunique(),
                common_ABC_backgrounds=g.panel_id.nunique(),
                common_ABC_count_vectors=g.groupby(['pool_id','background_stratum']).ngroups)
            for metric in METRICS:
                x=i[metric].dropna();y=b[metric].dropna()
                r[metric+'_mean']=y.mean()
                r[metric+'_image_n']=len(x);r[metric+'_images_positive']=int((x>1e-9).sum())
                r[metric+'_building_n']=len(y);r[metric+'_buildings_positive']=int((y>1e-9).sum())
            rows.append(r)
    out=pd.DataFrame(rows)
    assert ((out.cross_B8L2_mean-out.same_B8L2_mean-out.net_B8L2_mean).abs()<1e-9).all()
    info=write(HERE/'COMMON_ABC_COMPARISON.csv',out)
    save(HERE/'COMMON_ABC_COMPLETION.json',dict(status='complete',native_calls=0,
        event_source_sha256=sha(HERE/'EVENTS_COMPLETE.csv.gz'),script_sha256=sha(Path(__file__)),
        interpretation='All signed and absolute quality changes in each row use the same ABC scored events and the unchanged hierarchy.',
        output=info))
    print(out[(out.slice_kind=='overall')&(out.study_group=='main_n20')&(out.source_role=='TURN/K3/E2')&out.m.isin([4,7])][
        ['m','common_ABC_events','same_B8L2_mean','cross_B8L2_mean','net_B8L2_mean','net_B8L2_images_positive','net_B8L2_image_n','net_B8L2_buildings_positive','net_B8L2_building_n']].to_string(index=False))

if __name__=='__main__':main()
