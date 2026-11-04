"""Verify score definitions and repeated endpoint components without fusion."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
ANA=STUDY/'analysis'
REPO=STUDY.parents[2]
B12=REPO/'research/workers/mixture_patterns_and_c13_half_20261104/c13_half'
CORE=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
      'nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h',
      'ref_node_recall_9','ref_edge_recall_9','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg',
      'matched_ref_horizontal_abs_deg','boundary_loss','direction_loss','global_height_loss','local_height_loss','minimum_support']


def endpoint_view(d):
    out=[]
    for arm in ['A','C']:
        names=[c for c in CORE if arm+'_'+c in d]
        q=d[[arm+'_team_key']+[arm+'_'+c for c in names]].copy()
        q.columns=['team_key']+names
        out.append(q)
    return pd.concat(out,ignore_index=True)


def check_repeated(d,source):
    columns=[c for c in CORE if c in d]
    numeric=d[['team_key']+columns].copy()
    for c in columns:numeric[c]=pd.to_numeric(numeric[c],errors='coerce')
    g=numeric.groupby('team_key')[columns]
    minimum,maximum=g.min(),g.max()
    residual=(maximum-minimum).abs()
    finite_count=g.count()
    total_count=numeric.groupby('team_key').size()
    rows=[]
    for c in columns:
        inconsistent_missing=((finite_count[c]>0)&(finite_count[c]<total_count)).sum()
        rows.append(dict(source=source,metric=c,unique_teams=len(total_count),endpoint_uses=len(d),
                         repeated_value_max_difference=float(residual[c].max()) if residual[c].notna().any() else 0.,
                         teams_with_inconsistent_missingness=int(inconsistent_missing),
                         teams_with_nonmissing_values=int((finite_count[c]>0).sum())))
    return numeric.drop_duplicates('team_key'),rows


def scores(frame,source):
    cols=['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
    d=frame[['team_key']+cols].copy()
    for c in cols:d[c]=pd.to_numeric(d[c],errors='coerce')
    qfinite=d.B8L2.notna();components=d[cols[2:]].notna().all(axis=1)
    z=d[qfinite&components].copy()
    I,S,D,Hm,Hc=[z[c].to_numpy(float) for c in cols[2:]]
    boundary=(S*S)/32.
    height=(Hm/.8)**2+(Hc/.25)**2
    residual={}
    for scale,key in [(8.,'B8L2'),(10.,'D10')]:
        direction=1.5*(D*D)/(D*D+scale*scale)
        denominator=I+np.hypot(1-I+I*boundary,I*direction)+I*height
        predicted=np.divide(100*I,denominator,out=np.zeros_like(I),where=I!=0)
        residual[key]=predicted-z[key].to_numpy(float)
    z['source']=source
    z['B8L2_reconstructed_residual']=residual['B8L2']
    z['D10_reconstructed_residual']=residual['D10']
    stats=dict(source=source,unique_endpoints=len(d),Q_available=int(qfinite.sum()),formula_verified_endpoints=len(z),
        Q_available_with_missing_formula_components=int((qfinite&~components).sum()),
        B8L2_max_abs_residual=float(np.max(np.abs(residual['B8L2']))) if len(z) else None,
        D10_max_abs_residual=float(np.max(np.abs(residual['D10']))) if len(z) else None,
        B8L2_outside_0_100=int(((d.B8L2<0)|(d.B8L2>100)).sum()),
        D10_outside_0_100=int(((d.D10<0)|(d.D10>100)).sum()),
        Q_missing_D10_nonmissing=int((d.B8L2.isna()&d.D10.notna()).sum()))
    return stats,z[['source','team_key','B8L2_reconstructed_residual','D10_reconstructed_residual']]


def main():
    src=ANA/'LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz'
    header=pd.read_csv(src,nrows=0).columns
    use=[arm+'_'+c for arm in ['A','C'] for c in ['team_key']+CORE if arm+'_'+c in header]
    legacy=pd.read_csv(src,usecols=use,low_memory=False)
    legacy_ends,repeat_rows=check_repeated(endpoint_view(legacy),'legacy_all_52544_method_events')
    sources=[('legacy_all_unique_endpoints',legacy_ends)]
    for filename,name in [('PHYSICAL_PAIRS_AUTOMATIC.csv.gz','current_all_pairs_automatic'),('PHYSICAL_PAIRS_ASSISTED.csv.gz','current_all_pairs_assisted')]:
        header=pd.read_csv(ANA/filename,nrows=0).columns
        use=[arm+'_'+c for arm in ['A','C'] for c in ['team_key']+CORE if arm+'_'+c in header]
        d=pd.read_csv(ANA/filename,usecols=use,low_memory=False)
        unique,rep=check_repeated(endpoint_view(d),name);repeat_rows.extend(rep)
        sources.append((name,unique))
    for p,name in [(B12/'endpoints/ENDPOINT_SCALARS.csv.gz','batch12_native_scalar_source'),
                   (STUDY/'supplement/endpoints/ENDPOINT_SCALARS.csv.gz','gap_native_scalar_source'),
                   (REPO/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv','approved_order_scalar_source')]:
        sources.append((name,pd.read_csv(p,usecols=['team_key','B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter'],low_memory=False)))
    summary=[];residuals=[]
    for name,d in sources:
        s,z=scores(d,name);summary.append(s);residuals.append(z)
    summary=pd.DataFrame(summary);repeats=pd.DataFrame(repeat_rows)
    summary.to_csv(HERE/'INDEPENDENT_SCORE_FORMULA_SUMMARY.csv',index=False)
    repeats.to_csv(HERE/'REPEATED_ENDPOINT_COMPONENT_CONSISTENCY.csv',index=False)
    pd.concat(residuals,ignore_index=True).to_csv(HERE/'INDEPENDENT_SCORE_FORMULA_RESIDUALS.csv.gz',index=False,compression='gzip')
    passed=bool((summary.Q_available_with_missing_formula_components==0).all() and
        (summary.B8L2_max_abs_residual<1e-8).all() and (summary.D10_max_abs_residual<1e-8).all() and
        (summary.B8L2_outside_0_100==0).all() and (summary.D10_outside_0_100==0).all() and
        (summary.Q_missing_D10_nonmissing==0).all() and
        (repeats.repeated_value_max_difference<1e-8).all() and (repeats.teams_with_inconsistent_missingness==0).all())
    result=dict(status='passed' if passed else 'failed',formula_sources=len(summary),source_formula_rows=summary.to_dict('records'),
        repeated_metric_checks=len(repeats),repeated_component_global_max_difference=float(repeats.repeated_value_max_difference.max()),
        repeated_component_missingness_disagreements=int(repeats.teams_with_inconsistent_missingness.sum()),
        no_fusion_calls=True,no_score_source_overwrite=True,
        formula='100I / [I + hypot(1-I+I*S_bottom^2/32, I*1.5*dir^2/(dir^2+s^2)) + I*((Hmean/0.8)^2+(Hcenter/0.25)^2)], s=8 for B8L2; s=10 for D10; I=0 maps to 0.')
    (HERE/'SCORE_AND_COMPONENT_INDEPENDENT_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
