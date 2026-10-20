#!/usr/bin/env python3
"""Frozen R03..R08 assessment directions and explicit negative controls."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from assessment_summary_common import (BASE,ROOT,HERE,sha,load_exact,METRICS,summarize,write_json,write_csv,clean)


def save_tables(out,name,tables):
    for level,t in zip(['per_true_image','per_building','aggregate'],tables):write_csv(out/(name+'_'+level+'.csv.gz'),t)


def main():
    out=HERE/'directions';out.mkdir(exist_ok=True)
    freeze=json.load(open(BASE/'assessment/ASSESSMENT_FREEZE.json'))
    spec=BASE/'assessment/DIRECTION_SPEC.json'
    assert sha(spec)==freeze['file_sha256']['assessment/DIRECTION_SPEC.json']
    proposals=json.load(open(BASE/'reverse/discovery_interpretation/RECOMMENDED_DIRECTIONS.json'))['proposals']
    proposals=[r for r in proposals if r['proposal_id'] not in ['R01','R02']]
    pmap={(r['method_id'],r['outgoing_class'],r['incoming_class']):r for r in proposals}
    methods=sorted({r['method_id'] for r in proposals})
    frame,md,meta=load_exact('direction',methods)
    frame['proposal_id']=[pmap[(m,o,i)]['proposal_id'] for m,o,i in frame[['method_id','outgoing_class','incoming_class']].itertuples(index=False,name=None)]
    keys=['proposal_id','method_id','domain','context_id','outgoing_class','incoming_class']
    tables={level:[] for level in ['per_true_image','per_building','aggregate']}
    cover=[]
    for subset,data in [('overall',frame),('source_matched',frame[frame.actual_source_match]),
        ('source_Qclose3',frame[frame.actual_source_match&frame.all_blocks_history_Q_close3])]:
        data=data.copy();data['subset']=subset
        result=summarize(data,['subset']+keys,METRICS)
        for level,t in zip(tables,result):tables[level].append(t)
        for rid in [r['proposal_id'] for r in proposals]:
            for context in ['fixed_n13_m2','stress_integer_n_m']:
                g=data[(data.proposal_id==rid)&(data.context_id==context)]
                cover.append(dict(proposal_id=rid,context_id=context,subset=subset,events=len(g),
                    pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
                    status='observed' if len(g) else 'no_supported_event',quality_values_not_imputed=True))
    for level,parts in tables.items():write_csv(out/('direction_'+level+'.csv.gz'),pd.concat(parts,ignore_index=True))
    write_csv(out/'DIRECTION_COVERAGE.csv',pd.DataFrame(cover))
    # The fixed comparison and the broad stress frame remain separate.
    save_tables(out,'by_difficulty',summarize(frame,keys+['difficulty'],METRICS))
    save_tables(out,'by_n_m',summarize(frame,keys+['n','m'],METRICS))
    save_tables(out,'by_background',summarize(frame,keys+['background_policy'],METRICS))
    # One person cannot silently carry the named class direction. These are
    # descriptive event exclusions, not a new fit or a causal effect estimate.
    removal=[]
    primary=frame[frame.context_id.eq('fixed_n13_m2')]
    for r in proposals:
        g=primary[primary.proposal_id.eq(r['proposal_id'])]
        for role in ['any_replaceable_block','cross_block_only']:
            workers=r['incoming_members'] if role=='cross_block_only' else r['outgoing_members']+r['incoming_members']
            for worker in workers:
                cols=['cross_incoming'] if role=='cross_block_only' else ['outgoing_workers','within_incoming','cross_incoming']
                exists=pd.Series(False,index=g.index)
                for col in cols:exists|=g[col].map(lambda x:worker in x)
                z=g[~exists]
                if z.empty:
                    removal.append(dict(proposal_id=r['proposal_id'],worker_id=worker,removal_role=role,
                        events=0,pools=0,true_images=0,buildings=0,status='no_remaining_event'))
                    continue
                t=summarize(z,['proposal_id'],METRICS,tails=False)[2].iloc[0].to_dict()
                removal.append(dict(t,worker_id=worker,removal_role=role,status='observed'))
    write_csv(out/'PERSON_REMOVAL_DESCRIPTIVE.csv.gz',pd.DataFrame(removal))
    # Explicitly show all 6 possible incoming pairs for the 4-person R04 class;
    # unsupported pairs get zero support, no invented quality values.
    import itertools
    pairrows=[]
    r4=next(r for r in proposals if r['proposal_id']=='R04')
    g=frame[frame.proposal_id.eq('R04')].copy();g['incoming_pair']=g.cross_incoming.map(lambda x:'|'.join(sorted(x)))
    for context in ['fixed_n13_m2','stress_integer_n_m']:
        for workers in itertools.combinations(r4['incoming_members'],2):
            pair='|'.join(sorted(workers));z=g[(g.context_id==context)&(g.incoming_pair==pair)]
            if z.empty:pairrows.append(dict(context_id=context,incoming_pair=pair,events=0,pools=0,true_images=0,buildings=0,status='not_observed'))
            else:
                t=summarize(z,['context_id','incoming_pair'],METRICS,tails=False)[2].iloc[0].to_dict()
                pairrows.append(dict(t,status='observed'))
    write_csv(out/'R04_INCOMING_PAIR_COVERAGE.csv',pd.DataFrame(pairrows))
    # Reconstructable illustrative cases, selected after the frozen assessment
    # comparison solely for display. Keep both signs and unscored failures.
    evidence=[]
    for rid,g in primary.groupby('proposal_id'):
        choices=[('largest_quality_improvement',g.net_B8L2_change,'max'),('largest_quality_decline',g.net_B8L2_change,'min'),
                 ('shape_separation',g.gap_geometry_shape_main,'max'),('shape_counterexample',g.gap_geometry_shape_main,'min')]
        for reason,metric,order in choices:
            z=g[metric.notna()].sort_values(metric.name,ascending=order=='min')
            if z.empty:continue
            # Prefer a cached-image building only among equal scalar extrema.
            target=z.iloc[0][metric.name];z=z[z[metric.name]==target].copy()
            z['cached_building_priority']=z.building.isin(['UwV83HsGsw3','q9vSo1VnCiC','X7HyMhZNoso'])
            row=z.sort_values(['cached_building_priority','event_id'],ascending=[False,True]).iloc[0]
            e=md[md.event_id.eq(row.event_id)].iloc[0].to_dict()
            evidence.append(dict(proposal_id=rid,selection_reason=reason,selection_stage='assessment_display_only_not_rule_selection',
                event=e,metrics={k:row.get(k) for k in ['A_B8L2','B_B8L2','C_B8L2','net_B8L2_change','net_D10_change',
                    'within_joint_stable_main','cross_joint_stable_main','within_geometry_shape_main','cross_geometry_shape_main',
                    'within_floor_jaccard_difference','cross_floor_jaccard_difference','within_node_count_difference','cross_node_count_difference',
                    'net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','A_complete','B_complete','C_complete']},
                native_pool_path=str((BASE/'assessment/native_directions/pools'/(row.pool_id+'.json.gz')).relative_to(ROOT))))
    write_json(out/'CASE_CANDIDATES.json',evidence)
    write_json(out/'ASSESSMENT_DIRECTION_RECEIPT.json',dict(meta,
        input_direction_spec_sha256=sha(spec),source_script_sha256=sha(Path(__file__)),summary_common_sha256=sha(HERE/'assessment_summary_common.py'),
        primary='Fixed n13/m2, all named negative controls retained. Broad stress estimates separate.',
        requested_directions=[r['proposal_id'] for r in proposals],
        immutable_labels_and_rules=True,other_assessment_panels_opened=False,
        weighting='Events within reference pool -> pools within true image ID -> true images within building -> equal buildings',
        person_deletion='Descriptive exclusion; changes backgrounds/people/image support. Missing remaining events are not zero effects.',
        physical_oriented_ABC_duplicates=int(frame.duplicated(keys+['A_team_key','B_team_key','C_team_key']).sum())))
    print(json.dumps({k:meta[k] for k in ['events','pools','true_images','buildings']}),flush=True)


if __name__=='__main__':main()
