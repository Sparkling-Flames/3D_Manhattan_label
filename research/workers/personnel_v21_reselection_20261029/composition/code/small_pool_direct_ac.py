#!/usr/bin/env python3
"""Complete n=3,m=1 direct AC census inside every admitted N=4 pool.

No third source block exists, so none of these pairs is called strict ABC.
Both directed changes are retained; undirected absolute summaries count once.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from aggregate_frozen_panels import METRICS, load_labels, save_csv, truth, words


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--design',type=Path,required=True)
    ap.add_argument('--endpoints',type=Path,required=True)
    ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--condition',choices=['manual','semi'])
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    capacity=pd.read_csv(args.design/'POOL_CAPACITY_PLAN.csv')
    if args.condition:
        capacity=capacity[capacity.condition.eq(args.condition)].copy()
    requests=pd.read_csv(args.design/'TEAM_REQUESTS.csv.gz')
    scalar=pd.read_csv(args.endpoints,low_memory=False).set_index('team_key')
    labels,maps=load_labels([args.labels],None)
    info={m:g.iloc[0].to_dict() for m,g in labels.groupby('method')}
    small=capacity[capacity.pool_n.eq(4)]
    pair_rows=[];measurements=[];class_rows=[]
    for pool in small.to_dict('records'):
        methods=[m for m in maps if pool['condition'] in str(info[m].get('evaluation_condition',pool['condition']))]
        teams=requests[requests.pool_id.eq(pool['pool_id']) & requests.n.eq(3)]
        assert len(teams)==4
        for a,c in itertools.combinations(teams.to_dict('records'),2):
            aid,cid=sorted([a['team_key'],c['team_key']])
            unordered=hashlib.sha256((aid+'|'+cid).encode()).hexdigest()[:20]
            for orientation,(A,C) in enumerate([(a,c),(c,a)]):
                wa,wc=set(words(A['member_workers'])),set(words(C['member_workers']))
                D=sorted(wa&wc);X=sorted(wa-wc);Z=sorted(wc-wa)
                assert len(D)==2 and len(X)==len(Z)==1
                event_id=unordered+f'_{orientation}'
                pair_rows.append(dict(event_id=event_id,unordered_pair_id=unordered,orientation=orientation,
                    pool_id=pool['pool_id'],image=pool['image'],building=pool['building'],
                    condition=pool['condition'],reference_id=pool['reference_id'],pool_n=4,n=3,actual_m=1,
                    design='direct_AC_no_third_source_block',D_workers='|'.join(D),X_workers=X[0],Z_workers=Z[0],
                    A_workers=A['member_workers'],C_workers=C['member_workers'],
                    A_team_key=A['team_key'],C_team_key=C['team_key']))
                ya,yc=scalar.loc[A['team_key']],scalar.loc[C['team_key']]
                metrics=dict(event_id=event_id,unordered_pair_id=unordered,orientation=orientation,
                    A_failed=not bool(ya['complete_evaluable']),C_failed=not bool(yc['complete_evaluable']),
                    A_score_status=ya['score_status'],C_score_status=yc['score_status'],
                    A_B8L2=ya['B8L2'],C_B8L2=yc['B8L2'],A_D10=ya['D10'],C_D10=yc['D10'])
                for field in METRICS:
                    if field in scalar and field not in {'failure','log_recorded_time','recorded_time_total_seconds'}:
                        av=pd.to_numeric(ya[field],errors='coerce');cv=pd.to_numeric(yc[field],errors='coerce')
                        if isinstance(av,(bool,np.bool_)):av=float(av)
                        if isinstance(cv,(bool,np.bool_)):cv=float(cv)
                        metrics['C_minus_A_'+field]=cv-av
                av=pd.to_numeric(ya.get('recorded_time_total_seconds'),errors='coerce')
                cv=pd.to_numeric(yc.get('recorded_time_total_seconds'),errors='coerce')
                time_ok=(pd.notna(av) and pd.notna(cv) and av>0 and cv>0 and
                         str(ya.get('time_source_kinds'))==str(yc.get('time_source_kinds')) and
                         '|' not in str(ya.get('time_source_kinds')))
                metrics.update(time_comparable=bool(time_ok),time_source_kind=ya.get('time_source_kinds') if time_ok else None,
                               C_minus_A_recorded_time_seconds=float(cv-av) if time_ok else None,
                               C_vs_A_recorded_time_percent=float((cv/av-1)*100) if time_ok else None)
                measurements.append(metrics)
                common=all((pool['building'],X[0]) in maps[m] and (pool['building'],Z[0]) in maps[m]
                           and all((pool['building'],w) in maps[m] for w in D) for m in methods)
                for method in methods:
                    lm=maps[method];b=pool['building']
                    cx=lm.get((b,X[0]));cz=lm.get((b,Z[0]))
                    known=(cx is not None and cz is not None and all((b,w) in lm for w in D))
                    class_rows.append(dict(event_id=event_id,method=method,heldout_building=b,
                        input_conditions=info[method].get('input_conditions',info[method].get('condition')),
                        source_class=cx,target_class=cz,known=known,all_candidates_known=common,
                        replacement_kind='same_class' if known and cx==cz else 'cross_class' if known else 'unknown',
                        actual_m=1,class_seat_replacements=int(cx!=cz) if known else None,
                        class_seat_l1=int(cx!=cz)*2 if known else None))
    pairs=pd.DataFrame(pair_rows);metric=pd.DataFrame(measurements);classes=pd.DataFrame(class_rows)
    save_csv(args.out/'DIRECT_AC_PAIRS.csv.gz',pairs)
    save_csv(args.out/'DIRECT_AC_PAIR_METRICS.csv.gz',metric)
    save_csv(args.out/'DIRECT_AC_METHOD_LABELS.csv.gz',classes)
    joined=classes.merge(pairs[['event_id','image','pool_id','condition','orientation']],on='event_id').merge(metric,on=['event_id','orientation'])
    # Never let the two reciprocal directions count as two independent pairs.
    u=joined[joined.orientation.eq(0)].copy()
    for field in ['B8L2','D10','fusion_turn_n','height_mean_h','geometry_area_h2']:
        if 'C_minus_A_'+field in u:
            u['abs_change_'+field]=u['C_minus_A_'+field].abs()
    agg={'pairs':('event_id','size'),'quality_pairs':('C_minus_A_B8L2','count'),
         'mean_abs_Q':('abs_change_B8L2','mean'),'mean_abs_D10':('abs_change_D10','mean'),
         'mean_abs_turn_change':('abs_change_fusion_turn_n','mean'),
         'mean_abs_height_change':('abs_change_height_mean_h','mean'),
         'mean_abs_area_change':('abs_change_geometry_area_h2','mean')}
    summary=u.groupby(['method','condition','pool_id','image','replacement_kind'],dropna=False).agg(**agg).reset_index()
    save_csv(args.out/'UNDIRECTED_CHANGE_SUMMARY.csv',summary)
    save_csv(args.out/'N3_NO_N_GE3_REPLACEMENT_OPPORTUNITY.csv',capacity[capacity.pool_n.eq(3)])
    report=dict(pools=len(small),manual_pools=int(small.condition.eq('manual').sum()),semi_pools=int(small.condition.eq('semi').sum()),
        directed_pairs=len(pairs),undirected_pairs=pairs.unordered_pair_id.nunique(),method_event_links=len(classes),
        n=3,m=1,strict_ABC_events=0,new_fusions=0,
        N3_pools_without_n_ge3_replacement=int(capacity.pool_n.eq(3).sum()),
        interpretation='Supplementary direct AC. Reciprocal signs are not pooled as a directional treatment effect.')
    (args.out/'COMPLETE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
