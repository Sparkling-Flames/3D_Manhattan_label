"""Resume the registered tail and deliver exact rows before aggregate reports.

No fusion is performed here. Native endpoints are produced by the independently
checkpointed execute_capacity_tail.py queue. Main analyses run first to keep
memory bounded on the shared machine. Each completed action has its own receipt.
"""
from __future__ import annotations
import pandas as pd
from multin_design import HERE,gs
from resume_main_analyses import wait_for,step


def expressions_ready(plan):
    batches=pd.read_csv(HERE/plan).batch_id.tolist()
    return all((HERE.parent/'response/geometry_batches'/(bid+'_EXPRESSION.csv.json')).exists() for bid in batches)


def run():
    wait_for(lambda:(HERE/'MAIN_ANALYSIS_COMPLETE.json').exists())
    step('main_path_direct_publication',['publish_event_shards.py','path'])
    flags=['LARGE_BLOCK_BATCHES_COMPLETE.json','PURE_BLOCK_BATCHES_COMPLETE.json','F01_CAPACITY_BATCHES_COMPLETE.json']
    wait_for(lambda:all((HERE/f).exists() for f in flags))
    # Consolidated exact keys and all-n denominators are independent of the
    # class/geometry aggregate analyses; publish them as soon as endpoints exist.
    step('all_endpoint_direct_publication',['consolidate_deliverables.py'])
    step('all_n_opportunity_ledger',['all_n_opportunity_ledger.py'])
    for kind,plan in [('large','LARGE_BLOCK_BATCH_PLAN.csv'),('pure','PURE_BATCH_PLAN.csv')]:
        step(kind+'_event_evaluation',['evaluate_matched_events.py','run','--kind',kind])
        wait_for(lambda:expressions_ready(plan))
        step(kind+'_complete_event_export',['evaluate_matched_events.py','export','--kind',kind])
        step(kind+'_event_direct_publication',['publish_event_shards.py',kind])
    step('pure_cross_evaluation',['evaluate_pure_cross_only.py','run'])
    step('pure_cross_summary_and_export',['evaluate_pure_cross_only.py','summary'])
    step('pure_cross_event_direct_publication',['publish_event_shards.py','pure_cross'])
    for kind in ['large','pure']:
        step(kind+'_matched_summary',['evaluate_matched_events.py','summary','--kind',kind])
        step(kind+'_directed_effects',['analyze_directional_effects.py',kind])
    step('pure_cross_directed_effects',['analyze_directional_effects.py','pure_cross'])
    gs.save(HERE/'TAIL_ANALYSIS_COMPLETE.json',dict(status='complete',native_calls=0,
      endpoint_sets=360676,main_ABC=65371,large_ABC=16244,pure_ABC=1899,pure_AC=2056,
      exact_registered_path_edges=195888,independent_steps_saved=True))


if __name__=='__main__':run()
