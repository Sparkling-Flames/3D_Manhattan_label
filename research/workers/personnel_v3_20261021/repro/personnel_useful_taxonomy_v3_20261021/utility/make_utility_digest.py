"""Small, directly readable actual-use table; no new fitting or selection."""
from pathlib import Path
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json,sha
from summarize_policy import macro_many

OUTCOMES=['delta_B8L2','delta_D10','time_percent_vs_uniform','time_seconds_delta',
          'failure_rate','ordinary_failure_rate','failure_delta_pp',
          'failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']
MAIN=[('new_joint','ordinary_uniform'),('new_joint','history_Q'),('new_joint','history_T'),
      ('new_joint','QT_interaction__balanced'),
      ('old_structure','class_coarse_interaction__balanced'),
      ('old_structure','class_fine_interaction__balanced'),
      ('new_behavior','class_coarse_interaction__balanced'),
      ('new_behavior','class_fine_interaction__balanced'),
      ('new_behavior','exact_continuous_interaction__balanced'),
      ('new_behavior','exact_continuous_interaction_class_fine__balanced'),
      ('new_joint','class_coarse_interaction__balanced'),
      ('new_joint','class_fine_interaction__balanced'),
      ('new_joint','exact_continuous_interaction__balanced'),
      ('new_joint','exact_continuous_interaction_class_fine__balanced')]

def record(d,meta):
    assert not d.outcome.duplicated().any()
    row=dict(meta)
    for r in d[d.outcome.isin(OUTCOMES)].itertuples():
        for stat in ['mean','low95','high95','panels','images','buildings']:
            row[r.outcome+'_'+stat]=getattr(r,stat)
    return row

def main():
    rows=[];sources=[]
    shared=pd.read_csv(HERE/'POLICY_FRONTIER_SHARED_PANELS.csv')
    for condition in ['manual','semi']:
        p=HERE/(condition.upper()+'_UTILITY_CHECKPOINT.csv');sources.append(p)
        d=pd.read_csv(p)
        d=d[d.regime.eq('cross_panel_LOBO')&d.slice_kind.eq('joint_time_support')]
        raw={}
        for family in sorted(set(f for f,_ in MAIN)):
            rp=HERE/'cross_panel_LOBO'/condition/family/'PANEL_POLICY_RESULTS.csv.gz';sources.append(rp)
            raw[family]=pd.read_csv(rp,low_memory=False)
        wanted=set(shared[shared.condition.eq(condition)].panel_id)
        for family,policy in MAIN:
            z=d[d.family.eq(family)&d.policy.eq(policy)]
            assert len(z),(condition,family,policy)
            row=record(z,dict(condition=condition,regime='cross_panel_LOBO',
                family=family,policy=policy,support_id=condition+'_three_families_identical_timed_candidates',
                identity_note='Manual joint coarse/fine unsplit; Semi joint may split' if family=='new_joint' else '',
                quality='success conditional; keep failure denominator separately',
                time_unit='sum reported compatible seconds; panel-relative percent then image/building equal'))
            p=raw[family];p=p[p.policy.eq(policy)&p.all_candidates_time_compatible]
            assert set(p.panel_id)==wanted,(condition,family,policy,'support')
            stats,_=macro_many(p,['failure_rate','ordinary_failure_rate'])
            for metric,values in stats.items():
                for stat in ['mean','low95','high95','panels','images','buildings']:
                    row[metric+'_'+stat]=values[stat]
            rows.append(row)
    p=HERE/'F01_POLICY_CHECKPOINT.csv';sources.append(p)
    d=pd.read_csv(p);d=d[d.slice_kind.eq('all')]
    for policy in ['ordinary_uniform','history_Q','history_T','class_coarse_interaction__balanced',
                   'QT_interaction__balanced','QT_class_coarse__balanced',
                   'transfer_main_QT_interaction__balanced']:
        rows.append(record(d[d.policy.eq(policy)],dict(condition='manual',regime='f01_finite_LOBO',
            family='F01_fixed_history',policy=policy,support_id='F01_12_variable_panels_1872_sets',
            identity_note='Coarse only; finite high-Q new-source domain, n12; transfer policies trained on ordinary panels',
            quality='success conditional; keep failure denominator separately',
            time_unit='sum reported compatible seconds; panel-relative percent then image/building equal')))
    out=HERE/'UTILITY_ACTUAL_USE_DIGEST.csv';atomic_csv(pd.DataFrame(rows),out)
    atomic_json(dict(rows=len(rows),sha256=sha(out),
        source_files=[dict(path=p.name,sha256=sha(p)) for p in sources],
        within_support_id_comparable=True,
        cross_support_id_not_directly_rankable=True,
        actual_fusion_and_recorded_time=True,no_new_selection=True),
        HERE/'UTILITY_ACTUAL_USE_DIGEST_RECEIPT.json')
    print(out,len(rows),flush=True)

if __name__=='__main__':main()
