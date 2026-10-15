"""Record the investigator's stage-one working choice, not an optimizer certificate."""
from datetime import datetime,timezone
from core import *

def main():
    c=read(ROOT/'configs/ordinary_candidates.json')['loss_sum']
    s=read(ROOT/'results/ordinary_candidate_summary.json')['loss_sum']
    m=read(ROOT/'results/ordinary_reconstruction.json')['summary']
    assert m['count']==593 and not m['failures'] and s['layers']['ordinary']['available']==574
    assert s['evidence']['P01_margin']>0 and not s['evidence']['severe_vs_light_inversions']
    prior=ROOT/'configs/ordinary_frozen.json'
    if prior.exists():
        assert read(prior)['config']==c
        print('existing unchanged freeze',sha(prior));return
    freeze=dict(schema='quality_working_stage1_freeze_v1',name='WQ-LS08-20261014',config=c,
        equation='Q=100*I/(1+I*(Sb^2/32+1.5*D^2/(D^2+37.5)+(Hm/.8)^2+(Hc/.25)^2))',
        frozen_utc=datetime.now(timezone.utc).isoformat(),ordinary_n=574,severe_n=9,severe_use='separate_constraint_not_pooled',
        doorway_rows_used_for_this_selection=0,source='quality_pro_handoff_20261014_READY.zip',
        input_archive_sha256='85a30dff05b00261fab356c9d1d31e8a756d9fbb2cfe17b693f207f23de64058',
        rationale=['Remove interaction between overlap deficit and every other penalty, without adding a new metric or dropping information.',
                   'Preserve all neutral single-factor curves at perfect remaining metrics; preserve 0-overlap limit and Q<=100*I.',
                   'P01 remains correctly ordered; known controls pass; J04 no near-total penalty; J01 increase is modest, not a validated absolute target.',
                   'Nearest-normal replacement confounds target size and fails P01; ray-normal replacement loses 49 ordinary cases and direct substitution fails P01.',
                   'Max-floor discards boundary sensitivity where overlap dominates; not chosen despite larger score increases.'],
        costs=['Structural priority relative to overlap is weakened when I<1; P01 margin shrinks.',
               'C02 gap increases; severe scores also rise; no human numerical targets established.',
               'D semantic blind spot not repaired; real-input trajectories are diagnostic, not monotonic human ordering labels.'],
        evidence_status='exposed_development_not_blind; investigator_choice_not_unique_optimum',formal_algorithm_changed=False,
        dependencies={p:sha(ROOT/p) for p in ['src/core.py','configs/ordinary_candidates.json','results/ordinary_reconstruction.json','results/ordinary_candidate_summary.json','results/mechanism_controls.json']})
    dump(prior,freeze);print('ordinary_frozen',sha(prior))
if __name__=='__main__':main()
