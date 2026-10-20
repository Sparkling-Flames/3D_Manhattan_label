#!/usr/bin/env python3
"""Frozen new-only K2 fixed-block nested assessment; no class/rule fitting."""
from __future__ import annotations
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from assessment_summary_common import (
    BASE, ROOT, HERE, sha, load_exact, METRICS, summarize, write_json, write_csv,
)

METHOD='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'
KEYS=['outgoing_class','incoming_class','m','n']
CURVE_METRICS=[
    'B_B8L2','C_B8L2','B_D10','C_D10','B_complete','C_complete',
    'B_score_missing','C_score_missing','net_B8L2_change','net_D10_change',
    'net_Q_improve_gt2','net_Q_worsen_gt2','net_Q_worsen_gt5',
    'within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
    'within_geometry_noQ_main','cross_geometry_noQ_main','gap_geometry_noQ_main',
    'within_geometry_shape_main','cross_geometry_shape_main','gap_geometry_shape_main',
    'within_abs_B8L2_change','cross_abs_B8L2_change','excess_abs_B8L2_change',
    'within_floor_jaccard_difference','cross_floor_jaccard_difference',
    'within_prism_distance','cross_prism_distance','within_node_count_changed','cross_node_count_changed',
    'net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','net_IoU3D100_delta',
    'net_complete_lost','net_complete_restored','B_nodes','C_nodes','B_minimum_support','C_minimum_support',
    'replacement_fraction','A_out_fraction','C_out_fraction','A_in_fraction','C_in_fraction',
    'cross_minus_within_history_Q','all_blocks_history_Q_close3',
]


def save_tables(out,name,tables):
    for level,table in zip(['per_true_image','per_building','aggregate'],tables):
        write_csv(out/(name+'_'+level+'.csv.gz'),table)


def simple_hierarchy(frame,keys,metrics):
    """Supports paired n-step/m comparisons, retaining true-image hierarchy."""
    if frame.empty:return pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    pk=keys+['building','image_id','pool_id']
    pool=frame.groupby(pk,dropna=False)[metrics].mean().reset_index()
    im=pool.groupby(keys+['building','image_id'],dropna=False)[metrics].mean().reset_index()
    bu=im.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
    ag=bu.groupby(keys,dropna=False)[metrics].mean().reset_index()
    support=[]
    for key,g in frame.groupby(keys,dropna=False):
        key=key if isinstance(key,tuple) else (key,)
        row=dict(zip(keys,key))|dict(observations=len(g),pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique())
        if 'path_id' in g:row['fixed_paths']=g.path_id.nunique()
        for metric in metrics:
            finite=g[g[metric].notna()]
            row[metric+'_finite_observations']=len(finite)
            row[metric+'_finite_true_images']=finite.image_id.nunique()
            row[metric+'_finite_buildings']=finite.building.nunique()
        support.append(row)
    ag=ag.merge(pd.DataFrame(support),on=keys,validate='one_to_one')
    return im,bu,ag


def draw_curves(out,curve):
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,3,figsize=(12.6,7.1),layout='constrained')
    metrics=[('net_B8L2_change','Quality change: C minus B (B8L2)'),
             ('gap_geometry_shape_main','Shape stability: within minus cross'),
             ('within_joint_stable_main','Same-composition joint stability')]
    for i,(oc,ic) in enumerate([('C01','C02'),('C02','C01')]):
        for j,(metric,label) in enumerate(metrics):
            ax=axes[i,j]
            for m,color in [(2,'#2780b9'),(5,'#c25a30')]:
                for cohort,style,alpha in [('native_support','--',.6),('fixed_capacity_both_m_n5_to21','-',1)]:
                    g=curve[(curve.outgoing_class==oc)&(curve.incoming_class==ic)&curve.m.eq(m)&curve.cohort.eq(cohort)].sort_values('n')
                    if g.empty:continue
                    ax.plot(g.n,g[metric],style,color=color,alpha=alpha,label=f'm={m}, '+('native support' if style=='--' else 'fixed image cohort'))
            ax.axvline(13,color='#888888',lw=.7,ls=':')
            if j!=2:ax.axhline(0,color='#aaaaaa',lw=.6)
            ax.set_title(f'{oc} to {ic}: {label}');ax.set_xlabel('Total people n');ax.set_ylabel('B8L2 points' if j==0 else 'Proportion')
            ax.set_xticks([3,5,9,13,17,21,25,29,31]);ax.grid(alpha=.15)
            if i==0 and j==0:ax.legend(fontsize=7,loc='best')
    fig.suptitle('Frozen K2 classes, all-new teams: fixed entrant blocks, identical nested core\nEqual building means; dashed native support varies with n; solid cohort supports both m over n=5..21',fontsize=11)
    fig.savefig(out/'NEW2_NESTED_CURVES.png',dpi=170)
    fig.savefig(out/'NEW2_NESTED_CURVES.pdf')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.4,3.1),layout='constrained')
    for oc,ic,ls in [('C01','C02','-'),('C02','C01','--')]:
        for m,color in [(2,'#2780b9'),(5,'#c25a30')]:
            g=curve[(curve.outgoing_class==oc)&(curve.incoming_class==ic)&curve.m.eq(m)&curve.cohort.eq('native_support')].sort_values('n')
            ax.plot(g.n,g.true_images,ls,color=color,label=f'{oc} to {ic}, m={m}')
    ax.set_xlabel('Total people n');ax.set_ylabel('Actual distinct image IDs');ax.set_title('Native feasible support: repeated paths are not additional images')
    ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.2);fig.savefig(out/'NEW2_NESTED_SUPPORT.png',dpi=170);plt.close(fig)


def main():
    out=HERE/'nested_new2';out.mkdir(exist_ok=True)
    freeze=json.load(open(BASE/'assessment/ASSESSMENT_FREEZE.json'))
    spec=BASE/'assessment/NESTED_NEW2_SPEC.json'
    assert sha(spec)==freeze['file_sha256']['assessment/NESTED_NEW2_SPEC.json']
    f,md,meta=load_exact('nested_new2',[METHOD])
    assert f.actual_source_match.all() and f.m.isin([2,5]).all() and (f.n>=3).all()
    assert (f.A_new_n==f.n).all() and (f.B_new_n==f.n).all() and (f.C_new_n==f.n).all()
    assert f[['path_id','n']].duplicated().sum()==0
    primary=f[f.n.eq(13)].copy()
    primary_tables=summarize(primary,KEYS,METRICS)
    save_tables(out,'primary_n13',primary_tables)
    print(primary_tables[2][['outgoing_class','incoming_class','m','events','true_images','buildings',
        'net_B8L2_change','gap_joint_stable_main','gap_geometry_noQ_main','gap_geometry_shape_main']].to_json(orient='records'),flush=True)
    # Every prespecified n13 cell remains visible, even if it were empty.
    pc=[]
    for oc,ic in [('C01','C02'),('C02','C01')]:
        for m in [2,5]:
            for subset in ['overall','source_Qclose3']:
                g=primary[(primary.outgoing_class==oc)&(primary.incoming_class==ic)&primary.m.eq(m)]
                if subset!='overall':g=g[g.all_blocks_history_Q_close3]
                pc.append(dict(outgoing_class=oc,incoming_class=ic,m=m,n=13,subset=subset,
                    events=len(g),pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
                    status='observed' if len(g) else 'no_supported_event'))
    write_csv(out/'PRIMARY_COVERAGE.csv',pd.DataFrame(pc))
    qclose=primary[primary.all_blocks_history_Q_close3]
    save_tables(out,'primary_history_Qclose3',summarize(qclose,KEYS,METRICS))
    save_tables(out,'primary_by_difficulty',summarize(primary,KEYS+['difficulty'],METRICS))

    cap=json.load(open(BASE/'assessment/NESTED_NEW2_CAPACITY.json'))
    assert cap['input_request_sha256']==meta['request_sha256']
    cap=pd.DataFrame(cap['ledger'])
    coh=[]
    for name,required in [('fixed_capacity_both_m_n13',[13]),('fixed_capacity_both_m_n5_to21',list(range(5,22)))]:
        eligible=cap[cap.feasible_n.map(lambda ns:set(required).issubset(ns))]
        # Common pool universe across both directions and both m values.
        pools=set(eligible.groupby('pool_id').filter(lambda z:len(z)==4).pool_id)
        coh.append((name,pools))
    cohort_rows=[]
    for name,pools in coh:
        g=f[f.pool_id.isin(pools)]
        cohort_rows.append(dict(cohort=name,selection='capacity metadata only; all four direction/m cells',pools=sorted(pools),
            true_images=sorted(g.image_id.unique()),buildings=sorted(g.building.unique()),n_range=[int(g.n.min()),int(g.n.max())] if len(g) else None))
    write_json(out/'METADATA_COHORTS.json',cohort_rows)
    curve_outputs=[[],[],[]]
    for name,pools in [('native_support',set(f.pool_id))]+coh:
        z=f[f.pool_id.isin(pools)].copy();z['cohort']=name
        if name=='fixed_capacity_both_m_n5_to21':z=z[z.n.between(5,21)]
        tables=summarize(z,['cohort']+KEYS,CURVE_METRICS,tails=False)
        for bucket,t in zip(curve_outputs,tables):bucket.append(t)
    curves=tuple(pd.concat(p,ignore_index=True) for p in curve_outputs)
    save_tables(out,'curves',curves)

    # m5-minus-m2: average each frozen m panel within the same image first.
    # The two m panels contain different fixed draws, explicitly not matched blocks.
    compare=primary_tables[0]
    ck=['outgoing_class','incoming_class','n','building','image_id']
    mm=compare[compare.m.eq(5)].merge(compare[compare.m.eq(2)],on=ck,suffixes=('_m5','_m2'),validate='one_to_one')
    metrics=['net_B8L2_change','net_D10_change','gap_joint_stable_main','gap_geometry_noQ_main',
        'gap_geometry_shape_main','within_abs_B8L2_change','cross_abs_B8L2_change','net_diag_corner_recall_05_delta']
    for k in metrics:mm[k+'_m5_minus_m2']=mm[k+'_m5']-mm[k+'_m2']
    delta=[k+'_m5_minus_m2' for k in metrics]
    mm['pool_id']=mm.image_id  # One ordinary reference pool per selected image, asserted below.
    assert primary.groupby('image_id').pool_id.nunique().max()==1
    save_tables(out,'paired_m5_minus_m2_n13',simple_hierarchy(mm,['outgoing_class','incoming_class','n'],delta))

    # Consecutive n steps keep the exact three blocks and add the same new core person.
    lab=pd.read_csv(BASE/'reverse/mixed_fit/worker_labels.csv.gz')
    lab=lab[lab.method_id.eq(METHOD)&lab.known.astype(str).str.lower().isin(['true','1','1.0'])]
    cm=dict(zip(lab.worker_id,lab.class_id))
    step_rows=[]
    step_arm_fields=['B8L2','D10','complete','nodes','minimum_support','diag_wall_coverage_05','diag_corner_recall_05','IoU3D100']
    step_event_fields=['net_B8L2_change','within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
        'gap_geometry_shape_main','gap_geometry_noQ_main','within_floor_jaccard_difference','cross_floor_jaccard_difference']
    for path,g in f.groupby('path_id'):
        g=g.sort_values('n')
        for left,right in zip(g.iloc[:-1].to_dict('records'),g.iloc[1:].to_dict('records')):
            assert right['n']==left['n']+1
            added=right['added_core_worker'];assert added and added in cm
            for arm in 'ABC':assert set(right[arm+'_workers'])-set(left[arm+'_workers'])=={added}
            r={k:right[k] for k in ['path_id','pool_id','building','image_id','image','outgoing_class','incoming_class','m','replicate','difficulty']}
            r.update(n_from=left['n'],n_to=right['n'],event_from=left['event_id'],event_to=right['event_id'],
                added_core_worker=added,added_core_class=cm[added])
            for arm in 'ABC':
                for field in step_arm_fields:
                    name=arm+'_'+field
                    a=float(left[name]);b=float(right[name])
                    r[name+'_from']=a;r[name+'_to']=b;r[name+'_step']=b-a
            assert r['A_minimum_support_step']==r['B_minimum_support_step']==r['C_minimum_support_step']
            r['minimum_support_rises']=r['A_minimum_support_step']>0
            for metric in step_event_fields:
                a=float(left[metric]);b=float(right[metric]);r[metric+'_step']=b-a
            step_rows.append(r)
    steps=pd.DataFrame(step_rows)
    assert len(steps)==len(f)-f.path_id.nunique()==4950
    # This compact step table retains the event IDs needed to rebuild every large step.
    write_csv(out/'nested_adjacent_steps.csv.gz',steps)
    sm=[k for k in steps if k.endswith('_step')]
    save_tables(out,'steps_by_n_and_added_class',simple_hierarchy(steps,
        ['outgoing_class','incoming_class','m','n_from','n_to','added_core_class','minimum_support_rises'],sm))
    save_tables(out,'steps_by_support_increment',simple_hierarchy(steps,
        ['outgoing_class','incoming_class','m','added_core_class','minimum_support_rises'],sm))

    removal=[]
    for key,g in primary.groupby(KEYS):
        oc,ic,m,n=key
        workers=sorted(set(itertools.chain.from_iterable(g.outgoing_workers))|set(itertools.chain.from_iterable(g.within_incoming))|set(itertools.chain.from_iterable(g.cross_incoming)))
        for role in ['any_replaceable_block','cross_block_only']:
            for worker in workers:
                cols=['cross_incoming'] if role=='cross_block_only' else ['outgoing_workers','within_incoming','cross_incoming']
                present=pd.Series(False,index=g.index)
                for col in cols:present|=g[col].map(lambda ws:worker in ws)
                if not present.any():continue
                z=g[~present]
                if z.empty:r=dict(zip(KEYS,key))|dict(events=0,pools=0,true_images=0,buildings=0,status='no_remaining_event')
                else:r=summarize(z,KEYS,CURVE_METRICS,tails=False)[2].iloc[0].to_dict()|dict(status='observed')
                removal.append(r|dict(worker_id=worker,removal_role=role,excluded_events=int(present.sum())))
    write_csv(out/'PERSON_REMOVAL_DESCRIPTIVE.csv.gz',pd.DataFrame(removal))

    cases=[]
    mdmap={r['event_id']:r for r in md.to_dict('records')}
    def add_case(row,reason,extra=None):
        evidence=dict(selection_reason=reason,selection_stage='assessment_display_only_not_rule_selection',
            event=mdmap[row.event_id],metrics={k:row[k] for k in METRICS if k in row},
            native_pool_path=str((BASE/'assessment/native_nested_new2/pools'/(row.pool_id+'.json.gz')).relative_to(ROOT)))
        if extra:evidence.update(extra)
        cases.append(evidence)
    for key,g in primary.groupby(KEYS):
        for metric,order,reason in [('net_B8L2_change',False,'largest_quality_improvement'),('net_B8L2_change',True,'largest_quality_decline'),
            ('gap_geometry_shape_main',False,'shape_separation'),('gap_geometry_shape_main',True,'shape_counterexample')]:
            z=g[g[metric].notna()].sort_values([metric,'event_id'],ascending=[order,True])
            if len(z):add_case(z.iloc[0],'n13_'+reason)
    # Clearly mark step extrema as mechanism case search, not a tested new threshold.
    for oc,ic in [('C01','C02'),('C02','C01')]:
        for m in [2,5]:
            g=steps[(steps.outgoing_class==oc)&(steps.incoming_class==ic)&steps.m.eq(m)]
            for arm in ['B','C']:
                z=g[g[arm+'_B8L2_step'].notna()].sort_values([arm+'_B8L2_step','event_to'])
                if len(z):
                    st=z.iloc[0];row=f[f.event_id.eq(st.event_to)].iloc[0]
                    add_case(row,'localized_largest_'+arm+'_quality_drop_adjacent_n',
                        dict(previous_event=mdmap[st.event_from],step=st.to_dict()))
    write_json(out/'CASE_CANDIDATES.json',cases)
    draw_curves(out,curves[2])
    write_json(out/'NESTED_ANALYSIS_RECEIPT.json',dict(meta,
        spec_sha256=sha(spec),pre_effect_analysis_plan_sha256=sha(HERE/'NESTED_ANALYSIS_PLAN.json'),
        code_sha256=sha(Path(__file__)),summary_common_sha256=sha(HERE/'assessment_summary_common.py'),
        primary='n13/m5; n13/m2 dilution; two independently sampled fixed blocks per pool/direction/m',
        n13_events=len(primary),n13_true_images=primary.image_id.nunique(),fixed_paths=f.path_id.nunique(),adjacent_steps=len(steps),
        weighting='Events within reference pool -> pools within true image ID -> true images within building -> equal buildings',
        n_support_changes='Native curves accompanied by capacity-only common-image cohorts; 5..21 is a prespecified pressure span.',
        m_comparison='Image-paired different fixed block/core draws; exact nesting applies within m, not between m2 and m5.',
        person_deletion='Descriptive event exclusion; changes actual backgrounds/members/image support, not a causal identity estimate.',
        case_selection='After frozen assessment for display/mechanism localization only; both signs and counterexamples retained.',
        assessment_labels_unchanged=True,capacity_empty_cells_not_imputed=True))
    print(json.dumps(dict(completed=True,events=len(f),pools=f.pool_id.nunique(),true_images=f.image_id.nunique(),buildings=f.building.nunique())),flush=True)


if __name__=='__main__':main()
