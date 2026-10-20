"""Freeze a forward capacity/domain shortlist and explicit matched ablations.

Selection uses only already frozen history traits and class capacity, not new
discovery or assessment fusion outcomes. Reverse specs can be added separately.
"""
from __future__ import annotations
import argparse, datetime
from pathlib import Path
from design_history_panel import read, write

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--forward',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    shortlist=read(a.forward/'SHORTLIST.json'); manifest=read(a.forward/'method_manifest.json')['methods']
    wanted=[m['method_id'] for m in shortlist['items']]
    for family in shortlist['additional_ablation_families']:
        wanted.extend(family['method_ids'])
    wanted.extend(['F20_all_T_qK2','F20_highQnew_Scope_qK2','F20_highQnew_NewNonedit_qK2',
                   'F20_semiNew_NewEdit_qK2','F20_semiV1_Edit_qK2',
                   'F20_semi_new_Q_qK2','F20_semi_new_T_qK2','F20_semi_v1_Q_qK2','F20_semi_v1_T_qK2'])
    methods=[]
    for mid in dict.fromkeys(wanted):
        item=manifest[mid]; filt=item['pool_filter']; domain=item['domain']
        method=dict(method_id=mid,domain=domain,family='forward_'+item['family'],
                    description_zh=item['description_zh'],context_id='primary',
                    selection_basis='History trait/domain/capacity coverage plus same-person feature-group ablations; no new fusion result selection',
                    events_per_pool=24 if item['classes_n']<=3 else 36 if item['classes_n']==4 else 48,
                    pool_filter={'layer': 'ordinary_semi' if filt in ['semi_new','semi_v1'] else filt})
        if domain in ['easy','medium','hard']:
            method['pool_filter']['difficulty']={'easy':'简单','medium':'中等','hard':'困难'}[domain]
        if filt in ['semi_new','semi_v1']:
            method['allowed_origins']=['new' if filt=='semi_new' else 'v1']
            method['context_id']='same_source_team'
        methods.append(method)
    methods.extend([dict(method_id=mid,domain='global',family='prior_reverse_baseline',
                         context_id='primary',pool_filter={'layer':'ordinary_manual'},events_per_pool=36)
                    for mid in ['R_geo9_source_signed_p2_K2','R_role_ward_K5']])
    spec=dict(schema='interchangeability_discovery_forward_spec_v1',phase='discovery',seed=2026102011,
              frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              methods=methods,
              finite_frame='All feasible ordered pure class-block directions and integer n,m within each actual pool; m requires two disjoint same-class blocks and one other-class block. Background random/out-rich/in-rich; unrestricted and exact source-count-matched.',
              sampled='24/36/48 contexts per method-pool depending on K; deterministic ordered-direction/source stratification; all remaining integer n,m in the frame may be drawn. All finite context counts retained.',
              criteria='Old joint main primary, strict/wide/noQ and pre-frozen shape parallel; Q direction, failure/bad tail, reference structure and time independent. Selection after these new discovery results will be separately frozen before assessment.')
    write(a.out,spec); print('methods',len(methods),'forward',len(methods)-2)

if __name__=='__main__':main()
