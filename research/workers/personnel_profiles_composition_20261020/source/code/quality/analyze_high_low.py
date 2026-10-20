"""Image/building-level summaries and selected mechanisms for Q composition.

Run freeze before analyze. Freeze reads discovery-building outcomes only and
records candidate ratios; analyze then evaluates the recorded ratios elsewhere.
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import high_low_study as hs

METRICS = ['B8L2','D10','nodes','ref_node_recall_9','ref_edge_recall_9',
           'ref_node_precision_9','ref_unmatched_candidate_nodes_9','omission','extension',
           'diag_wall_coverage_05','diag_corner_recall_05','diag_corner_precision_05',
           'complete_rate','score_rate','low_Q50_rate','minimum_support']


def bmean(frame, column):
    return frame.groupby(['building','pool_id'])[column].mean().groupby('building').mean().mean()


def hierarchical(frame, metrics):
    row = dict(event_rows=len(frame),unique_teams=frame.team_key.nunique(),
               images=frame.image_id.nunique(),pools=frame.pool_id.nunique(),buildings=frame.building.nunique())
    available = [col for col in metrics if col in frame]
    if available:
        values = frame.groupby(['building','pool_id'])[available].mean().groupby('building').mean().mean()
        counts = frame[available].notna().sum()
        for col in available:
            row[col] = values[col]
            row[col+'_finite_n'] = int(counts[col])
    if 'B8L2' in frame:
        # Per-image means and finite-team tail are different estimands.
        row['score_images'] = frame.loc[frame.B8L2.notna(),'image_id'].nunique()
        row['score_buildings'] = frame.loc[frame.B8L2.notna(),'building'].nunique()
        row['B8L2_image_mean_q10'] = frame.groupby('pool_id').B8L2.mean().quantile(.1)
        row['B8L2_within_image_sd_mean'] = frame.groupby(['building','pool_id']).B8L2.std().groupby('building').mean().mean()
    return row


def delta_summary(frame, prefix='d_B8L2'):
    vals = frame.groupby(['building','pool_id'])[prefix].mean().groupby('building').mean().dropna()
    row = dict(paired_events=int(frame[prefix].notna().sum()),
               paired_images=frame.loc[frame[prefix].notna(),'image_id'].nunique(),
               paired_buildings=len(vals),mean=float(vals.mean()) if len(vals) else None)
    if len(vals) >= 2:
        generator = hs.rng('building_bootstrap',prefix,sorted(frame.pool_id.unique()),len(frame))
        draws = generator.choice(vals.to_numpy(),(2000,len(vals)),replace=True).mean(axis=1)
        row['cluster_CI_low'],row['cluster_CI_high'] = np.quantile(draws,[.025,.975]).tolist()
    else:
        row['cluster_CI_low'] = row['cluster_CI_high'] = None
    row['positive_image_fraction'] = (frame.groupby('pool_id')[prefix].mean().dropna() > 0).mean()
    row['negative_image_fraction'] = (frame.groupby('pool_id')[prefix].mean().dropna() < 0).mean()
    return row


def load_events(args, phase=None):
    payload = hs.read(args.out/'requests.json.gz')
    events = pd.DataFrame(payload['events'])
    if phase:
        events = events[events.phase == phase].copy()
    wanted = set(events.team_key)
    missing_files = [pid for pid in events.pool_id.unique() if not (args.out/'native_final'/f'{pid}.json.gz').exists()]
    if missing_files:
        raise RuntimeError(f'{len(missing_files)} requested pools not completed yet')
    rows = []
    for pid in events.pool_id.unique():
        for row in hs.read(args.out/'native_final'/f'{pid}.json.gz')['teams']:
            if row['team_key'] in wanted:
                keep = {k:row.get(k) for k in [*METRICS,'team_key','score_status','complete_evaluable','result_origin','member_workers','member_object_ids','new_n','old_n']}
                keep['complete_rate'] = float(bool(row.get('complete_evaluable')))
                keep['score_rate'] = float(row.get('B8L2') is not None)
                keep['low_Q50_rate'] = float(row['B8L2'] < 50) if row.get('B8L2') is not None else np.nan
                rows.append(keep)
    teams = pd.DataFrame(rows).drop_duplicates('team_key')
    assert wanted <= set(teams.team_key), 'requested exact team not computed'
    return events.merge(teams,on='team_key',how='left',validate='many_to_one'), teams


def paired_grid(frame):
    grid = frame[(frame.family == 'grid') & (frame.pure_comparison_available == True)].copy()
    keys = ['pool_id','n','source_policy','replicate']
    results = []
    for baseline, mask in [('pure_H',grid.H==grid.n),('pure_L',grid.H==0)]:
        base = grid[mask][keys+METRICS+['team_key']]
        pair = grid.merge(base,on=keys,suffixes=('','_baseline'),validate='many_to_one')
        pair['baseline'] = baseline
        for metric in METRICS:
            pair['d_'+metric] = pair[metric]-pair[metric+'_baseline']
        pair['within_2_of_H'] = np.where(pair.d_B8L2.notna(),(pair.d_B8L2>=-2).astype(float),np.nan) if baseline == 'pure_H' else np.nan
        pair['loss_over_5'] = np.where(pair.d_B8L2.notna(),(pair.d_B8L2 < -5).astype(float),np.nan)
        pair['gain_over_5'] = np.where(pair.d_B8L2.notna(),(pair.d_B8L2 > 5).astype(float),np.nan)
        results.append(pair)
    # Random has independent member selection, but the same image and n.
    random = frame[(frame.family=='random') & (frame.pure_comparison_available==True)][keys+METRICS+['team_key']]
    pair = grid.merge(random,on=keys,suffixes=('','_baseline'),validate='many_to_one')
    pair['baseline'] = 'random'
    for metric in METRICS:
        pair['d_'+metric] = pair[metric]-pair[metric+'_baseline']
    pair['within_2_of_H'] = np.nan
    pair['loss_over_5'] = np.where(pair.d_B8L2.notna(),(pair.d_B8L2 < -5).astype(float),np.nan)
    pair['gain_over_5'] = np.where(pair.d_B8L2.notna(),(pair.d_B8L2 > 5).astype(float),np.nan)
    results.append(pair)
    return pd.concat(results,ignore_index=True)


def summarize_pairs(pair, split_keys):
    rows=[]
    for key,g in pair.groupby(split_keys,dropna=False):
        if not isinstance(key,tuple):key=(key,)
        row=dict(zip(split_keys,key))
        row.update(hierarchical(g,['d_'+m for m in METRICS]+['within_2_of_H','loss_over_5','gain_over_5']))
        row.update(delta_summary(g))
        rows.append(row)
    return pd.DataFrame(rows)


def freeze(args):
    frame,teams=load_events(args,'discovery')
    pairs=paired_grid(frame)
    cells=summarize_pairs(pairs[(pairs.n==7)&(pairs.source_policy=='all_supported')&(pairs.baseline=='pure_H')],['layer','n','H','L'])
    hs.write_csv(args.out/'discovery_n7_candidate_screen.csv',cells)
    candidates=[]
    for layer in ['ordinary_manual','ordinary_semi']:
        tab=cells[(cells.layer==layer)&(cells.H.between(1,6))].sort_values('H')
        acceptable=tab[(tab['mean']>=-2)&(tab.d_ref_edge_recall_9>=-.03)&(tab.d_score_rate>=-.02)&(tab.paired_buildings>=3)]
        if len(acceptable):
            selected=acceptable.iloc[0]
            candidates.append(dict(layer=layer,n=7,H=int(selected.H),L=int(selected.L),discovery_mean_delta_H=selected['mean'],
                discovery_edge_recall_delta=selected.d_ref_edge_recall_9,discovery_score_rate_delta=selected.d_score_rate,
                discovery_images=int(selected.paired_images),discovery_buildings=int(selected.paired_buildings)))
        else:
            candidates.append(dict(layer=layer,n=7,H=None,L=None,status='no_mixed_ratio_met_exploratory_criteria'))
    hs.save(args.out/'CANDIDATES_FROZEN.json',dict(discovery_only=True,
        criteria='smallest H from 1..6 at n7: building-equal mean mixed-minus-pureH B8L2>=-2, reference edge recall>=-0.03, score-available fraction>=-0.02; at least 3 buildings',
        interpretation='operational exploratory tolerances, not a validated perceptual noninferiority margin; evaluate recorded ratio on validation buildings separately',
        candidates=candidates))
    print(pd.DataFrame(candidates).to_string(index=False))


def add_phase_all(frame):
    return pd.concat([frame,frame.assign(phase='all')],ignore_index=True)


def load_geometry(args,keys):
    by=collections.defaultdict(set)
    request_map={r['request_id']:r['pool_id'] for r in hs.read(args.out/'requests.json.gz')['requests']}
    for key in keys:by[request_map[key]].add(key)
    result={}
    for pid,wanted in by.items():
        result.update({r['team_key']:r for r in hs.read(args.out/'native_final'/f'{pid}.json.gz')['teams'] if r['team_key'] in wanted})
    return result


def block_analysis(args,frame):
    tab=frame[frame.family=='block'].copy()
    if tab.empty:return
    hs.init_engine(args.repo)
    from tools.thesis_main.analysis.personnel_corner_panel_20261020 import compare
    geom=load_geometry(args,set(tab.team_key))
    rows=[]
    for eid,g in tab.groupby('block_event_id'):
        x={r['arm']:r for r in g.to_dict('records')}
        a,b,c=x['A'],x['B'],x['C']
        assert set(a['member_workers'])&set(b['member_workers'])==set(a['core_workers'])
        assert set(a['member_workers'])&set(c['member_workers'])==set(a['core_workers'])
        assert len(set(a['member_workers'])-set(b['member_workers']))==int(a['m'])
        row={k:a[k] for k in ['pool_id','image','image_id','building','condition','layer','difficulty','phase','n','m','direction','source_policy','replicate','core_workers']}
        row.update(block_event_id=eid,A_team_key=a['team_key'],B_team_key=b['team_key'],C_team_key=c['team_key'],team_key=a['team_key'])
        for metric in METRICS:row['d_'+metric]=c[metric]-b[metric]
        for arm,other in [('within',b),('cross',c)]:
            row[arm+'_abs_B8L2']=abs(other['B8L2']-a['B8L2'])
            ga,gb=geom[a['team_key']],geom[other['team_key']]
            if not ga.get('geometry') or not gb.get('geometry'):
                res={'status':'missing_saved_geometry','same_count':np.nan}
            else:res,_=compare(ga,gb)
            row.update({arm+'_'+k:v for k,v in res.items()})
        rows.append(row)
    result=pd.DataFrame(rows)
    hs.write_csv(args.out/'block_events.csv.gz',result)
    status_tables=[]
    for arm in ['within','cross']:
        status=result.groupby(['layer','n','m','direction',arm+'_status']).agg(
            events=('block_event_id','size'),images=('image_id','nunique'),buildings=('building','nunique')
        ).reset_index().rename(columns={arm+'_status':'status'})
        status['arm']=arm
        status_tables.append(status)
    hs.write_csv(args.out/'block_status_support.csv',pd.concat(status_tables,ignore_index=True))
    summary=summarize_pairs(add_phase_all(result),['layer','phase','n','m','direction'])
    geo=[]
    for key,g in add_phase_all(result).groupby(['layer','phase','n','m','direction']):
        both=g[(g.within_status=='unique_cyclic_candidate')&(g.cross_status=='unique_cyclic_candidate')]
        row=dict(zip(['layer','phase','n','m','direction'],key),common_geometry_events=len(both),common_geometry_images=both.image_id.nunique())
        for arm in ['within','cross']:
            row[arm+'_same_count_rate']=bmean(g,arm+'_same_count')
            for col in ['bev_mean_h','bev_max_h','top_mean_h','angle_deg']:
                row[arm+'_'+col]=bmean(both,arm+'_'+col) if len(both) else np.nan
        geo.append(row)
    summary=summary.merge(pd.DataFrame(geo),on=['layer','phase','n','m','direction'])
    hs.write_csv(args.out/'block_summary.csv',summary)


def growth_analysis(args,frame):
    g=frame[frame.family=='growth'].copy()
    base=g[g.added_n==0][['path_id']+METRICS+['team_key']]
    growth=g.merge(base,on='path_id',suffixes=('','_baseline'),validate='many_to_one')
    for metric in METRICS:growth['d_'+metric]=growth[metric]-growth[metric+'_baseline']
    hs.write_csv(args.out/'growth_events.csv.gz',growth[['event_id','path_id','pool_id','image','image_id','building','condition','layer','difficulty','phase','n','H','L','core_n','incoming_group','added_n','replicate','team_key','team_key_baseline','core_workers','added_workers']+METRICS+['d_'+m for m in METRICS]])
    rows=[]
    for key,tab in add_phase_all(growth).groupby(['layer','phase','core_n','incoming_group','added_n']):
        row=dict(zip(['layer','phase','core_n','incoming_group','added_n'],key))
        row.update(hierarchical(tab,METRICS+['d_'+m for m in METRICS]));row.update(delta_summary(tab));rows.append(row)
    hs.write_csv(args.out/'growth_summary.csv',pd.DataFrame(rows))
    # Same exact H core and same number of additions; only the added group's
    # historical Q differs. Full new member identities remain available.
    keys=['pool_id','core_n','added_n','replicate']
    pure=g[g.incoming_group=='H'][keys+METRICS+['team_key']]
    mixed=g[g.incoming_group=='L'].merge(pure,on=keys,suffixes=('','_baseline'),validate='one_to_one')
    for metric in METRICS:mixed['d_'+metric]=mixed[metric]-mixed[metric+'_baseline']
    hs.write_csv(args.out/'growth_same_core_matched_events.csv.gz',mixed[['pool_id','image','image_id','building','condition','layer','difficulty','phase','n','core_n','added_n','replicate','team_key','team_key_baseline']+METRICS+['d_'+m for m in METRICS]])
    hs.write_csv(args.out/'growth_same_core_matched_summary.csv',summarize_pairs(add_phase_all(mixed),['layer','phase','core_n','added_n']))


def analyze(args):
    assert (args.out/'CANDIDATES_FROZEN.json').exists(),'freeze discovery candidates before validation summaries'
    frame,teams=load_events(args)
    hs.write_csv(args.out/'team_summary.csv.gz',teams.drop(columns=['member_workers','member_object_ids']))
    # Pool-level outputs retain support for tasks missing pure endpoints as well.
    grids=frame[frame.family=='grid']
    poolrows=[]
    pkeys=['pool_id','image','image_id','building','condition','layer','difficulty','phase','n','H','L','source_policy','pure_comparison_available']
    for key,g in grids.groupby(pkeys):
        poolrows.append(dict(zip(pkeys,key),**hierarchical(g,METRICS)))
    hs.write_csv(args.out/'composition_per_image.csv.gz',pd.DataFrame(poolrows))
    primary=grids[grids.pure_comparison_available==True]
    sumrows=[]
    for key,g in add_phase_all(primary).groupby(['layer','phase','source_policy','n','H','L']):
        sumrows.append(dict(zip(['layer','phase','source_policy','n','H','L'],key),**hierarchical(g,METRICS)))
    hs.write_csv(args.out/'composition_summary.csv',pd.DataFrame(sumrows))
    pairs=paired_grid(frame)
    paircols=['event_id','pool_id','image','image_id','building','condition','layer','difficulty','phase','n','H','L','source_policy','replicate','team_key','team_key_baseline','baseline']+['d_'+m for m in METRICS]+['within_2_of_H','loss_over_5','gain_over_5']
    hs.write_csv(args.out/'composition_pair_events.csv.gz',pairs[paircols])
    effects=summarize_pairs(add_phase_all(pairs),['layer','phase','source_policy','n','H','L','baseline'])
    hs.write_csv(args.out/'composition_effects.csv',effects)
    difficulty=summarize_pairs(pairs[(pairs.n==7)&(pairs.source_policy=='all_supported')],['layer','difficulty','phase','n','H','L','baseline'])
    hs.write_csv(args.out/'n7_difficulty_effects.csv',difficulty)
    # Exact candidates were selected using discovery outcomes alone.
    selected=[]
    for c in hs.read(args.out/'CANDIDATES_FROZEN.json')['candidates']:
        if c.get('H') is None:continue
        tab=effects[(effects.layer==c['layer'])&(effects.n==c['n'])&(effects.H==c['H'])]
        selected.extend(tab.to_dict('records'))
    hs.write_csv(args.out/'frozen_candidate_evaluation.csv',pd.DataFrame(selected))
    growth_analysis(args,frame)
    block_analysis(args,frame)
    coverage=dict(unique_teams=len(teams),event_rows=len(frame),pools=frame.pool_id.nunique(),images=frame.image_id.nunique(),buildings=frame.building.nunique(),
        new_native_unique=int((teams.result_origin=='new_native_fusion').sum()),prior_reused_unique=int((teams.result_origin!='new_native_fusion').sum()),
        score_available_unique=int(teams.score_rate.sum()),complete_unique=int(teams.complete_rate.sum()),
        result_origins=teams.result_origin.value_counts().to_dict(),layer_event_rows=frame.groupby('layer').size().to_dict(),
        independence='team repetitions are finite members within the same images; reported primary means are image-then-building equal',
        quality_tail='Q<50 is an exploratory score-tail descriptor, not human serious-error gold; failures reported separately, no zero imputation',
        structural_diagnostics='reference-relative automatic node/edge/wall correspondence; semantic necessary corners require existing/manual visual evidence')
    hs.save(args.out/'RESULT_COVERAGE.json',coverage)
    print(json_repr(coverage))


def json_repr(value):
    import json
    return json.dumps(hs.clean(value),ensure_ascii=False,indent=2)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['freeze','analyze'])
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.repo=a.repo.resolve();a.out=a.out.resolve()
    {'freeze':freeze,'analyze':analyze}[a.command](a)
