"""Separate sensitivity for the user's F2/F9 x-coordinate candidate.

This never changes the 57-group fixed-coordinate human-order delivery. The
candidate retains its explicit not-adopted identity and reuses its saved score.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import pandas as pd
from .evaluate_manual_order_ac_20261104 import (
    AC,OUT,ROOT,RESULT,modules,read_json,iter_jsonl,load_native,overlay,
    compare,save,jsave,pool_table,metric_support,align)
from .evaluate_manual_order_ac_sensitivity_20261104 import changed_rows,patch,subset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=__import__('pathlib').Path,default=OUT/'coordinate_candidate')
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    measure,summary,metrics,refdiagnostic,geometry_metrics=modules()
    candidate=read_json(RESULT/'coordinate_candidate/CANDIDATE_FULL_STATE.json.gz')[1]
    assert candidate['version']=='user_F2_F9_shared_x_candidate'
    key=candidate['score']['team_key'];pid=candidate['score']['pool_id']
    fixed={r['team_key']:r for r in iter_jsonl(RESULT/'endpoints/ENDPOINTS.jsonl.gz')}
    assisted=dict(fixed[key]);assisted.update(candidate['score'])
    assert assisted['manual_feature_order']==candidate['manual_feature_order']
    original=pd.read_csv(OUT/'metric_shards'/(pid+'.csv.gz'),low_memory=False)
    selected=original[original.A_team_key.eq(key)|original.C_team_key.eq(key)].copy()
    assert len(selected)==50
    eventcols=pd.read_csv(AC/'stage01_registered/AC_EVENTS.csv.gz',nrows=0).columns
    events=selected[eventcols].reset_index(drop=True)
    pool=next(p for p in read_json(ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')['images'] if p['pool_id']==pid)
    native,provenance=load_native(pid,set(events.A_team_key)|set(events.C_team_key))
    baseline={k:overlay(r,fixed[k],metrics,measure.RAW_STATUS) if k in fixed else deepcopy(r) for k,r in native.items()}
    reproduction=measure.compute(events,deepcopy(baseline),pool,metrics,refdiagnostic,geometry_metrics)
    parity=compare(selected,reproduction,['event_id'],'fixed_coordinate_50_event_baseline',require_same_fields=False)
    revised=deepcopy(baseline);revised[key]=overlay(native[key],assisted,metrics,measure.RAW_STATUS)
    revised[key]['manual_order_analysis_version']='user_coordinate_candidate_not_adopted_20261104'
    measured=measure.compute(events,revised,pool,metrics,refdiagnostic,geometry_metrics)
    updated=original.set_index('event_id').copy()
    cols=[c for c in measured if c in updated and c not in eventcols]
    updated.loc[measured.event_id,cols]=measured.set_index('event_id')[cols]
    updated=updated.reset_index()[original.columns]
    save(selected,out/'EVENT_METRICS_FIXED_COORDINATES.csv.gz')
    save(updated[updated.event_id.isin(selected.event_id)],out/'EVENT_METRICS_CANDIDATE.csv.gz')
    save(metric_support(selected,updated[updated.event_id.isin(selected.event_id)],summary.DELTA_METRICS+summary.ARM_METRICS),out/'EVENT_SUPPORT_BY_METRIC.csv')
    save(pd.DataFrame(parity),out/'BASELINE_PARITY.csv')
    save(updated,out/'metric_shards'/(pid+'.csv.gz'))
    links=pd.read_csv(AC/'stage01_registered/DESIGN_LINKS.csv.gz',usecols=summary.LINK_COLS,low_memory=False)
    links=links[links.pool_id.eq(pid)]
    a,b=pool_table(original,links,summary),pool_table(updated,links,summary)
    keys=summary.GROUP+['pool_id','image','building']
    for d in (a,b):
        for k in summary.GROUP:d[k]=d[k].astype(str)
    save(a,out/'POOL_FIXED_COORDINATES.csv.gz');save(b,out/'POOL_CANDIDATE.csv.gz')
    c0,c1=changed_rows(a,b,keys);groups=c0[summary.GROUP].drop_duplicates()
    allbase=pd.read_csv(AC/'stage05_main/POOL_CONDITION_EFFECTS.csv.gz',low_memory=False,dtype={k:str for k in summary.GROUP})
    allfixed=pd.read_csv(OUT/'AFFECTED_POOLS_ASSISTED.csv.gz',low_memory=False,dtype={k:str for k in summary.GROUP})
    baseline=subset(allbase,groups,summary.GROUP)
    baseline=patch(baseline,allfixed,keys)
    new=patch(baseline,b,keys)
    olddir=out/'main_fixed_coordinates';newdir=out/'main_candidate'
    olddir.mkdir(exist_ok=True);newdir.mkdir(exist_ok=True)
    summary.aggregate(baseline,olddir);summary.aggregate(new,newdir)
    s0=pd.read_csv(olddir/'CONDITION_METRIC_SUMMARY.csv.gz',dtype={k:str for k in summary.GROUP})
    s1=pd.read_csv(newdir/'CONDITION_METRIC_SUMMARY.csv.gz',dtype={k:str for k in summary.GROUP})
    k=summary.GROUP+['metric'];s0,s1=changed_rows(s0,s1,k)
    delta=align(s0,k).add_prefix('fixed_coordinates_').join(align(s1,k).add_prefix('candidate_')).reset_index()
    save(delta,out/'MAIN_SUMMARY_CHANGES_CANDIDATE_ONLY.csv.gz')
    receipt=dict(analysis_version='user_coordinate_candidate_not_adopted_20261104',adopted_in_fixed_57=False,
        source_candidate='research/fusion/manual_order_impact_20261104/coordinate_candidate/CANDIDATE_FULL_STATE.json.gz',
        affected_events=len(selected),fixed_coordinate_scored=int(selected.AC_scored.sum()),
        candidate_scored=int(measured.AC_scored.sum()),changed_main_pool_conditions=len(c0),
        changed_main_summary_rows=len(delta),candidate_B8L2=assisted['B8L2'],candidate_D10=assisted['D10'],
        polygon_valid=candidate['geometry_audit'].get('polygon_valid'),
        camera_in_visible_kernel=candidate['geometry_audit'].get('camera_in_visible_kernel'),
        raw_fusions=0,new_endpoint_scores=0,new_labels=0,missing_Q_imputed=False,
        original_and_fixed_57_outputs_modified=False)
    jsave(out/'CANDIDATE_AC_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
