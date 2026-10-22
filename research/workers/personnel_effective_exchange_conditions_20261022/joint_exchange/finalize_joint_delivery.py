"""Freeze compact coverage, exact endpoint references and reproducibility inputs.

Reads completed evidence only; does not fuse or change prior requests/outcomes.
"""
from __future__ import annotations
from joint_design import *
import importlib.metadata
import platform
import sys


def run():
    regs=[];coverage=[]
    for kind in ['native','cached','cross']:
        for condition in ['manual','semi']:
            path=HERE/f'{kind.upper()}_{condition.upper()}_EVENTS_COMPLETE.csv.gz'
            head=pd.read_csv(path,nrows=0)
            wanted=['event_id','physical_triple_id','oriented_triple_id','pool_id','image','building','condition','source_domain','method_id','tier','n','m_AB','m_AC','m_BC','composition_turnover_AC','team_A','team_B','team_C','common_background','all_complete','all_scored','recorded_time_single_source','A_failure','B_failure','C_failure','common_anchor_id','previous_physical_triple_seen']
            d=pd.read_csv(path,usecols=[c for c in wanted if c in head],low_memory=False)
            d['evaluation_stage']=kind
            d['physical_set_id']=d[['team_A','team_B','team_C']].apply(lambda x:digest(sorted(x))[:24],axis=1)
            d['oriented_set_id']=d[['team_A','team_B','team_C']].apply(lambda x:digest(list(x))[:24],axis=1)
            regs.append(d)
            for domain,g in [('ALL',d)]+[(str(k),g) for k,g in d.groupby('source_domain')]:
                coverage.append(dict(stage=kind,condition=condition,source_domain=domain,event_refs=len(g),distinct_event_ids=g.event_id.nunique(),physical_triples=g.physical_set_id.nunique(),oriented_triples=g.oriented_set_id.nunique(),unique_teams=len(set(g.team_A)|set(g.team_B)|set(g.team_C)),backgrounds=g[['pool_id','n','common_background']].drop_duplicates().shape[0],images=g.image.nunique(),buildings=g.building.nunique(),n_values='|'.join(map(str,sorted(g.n.unique()))),actual_m_values='|'.join(map(str,sorted(g.m_AB.unique()))),class_seat_change_values='|'.join(map(str,sorted(g.composition_turnover_AC.unique()))),all_scored_refs=int(g.all_scored.sum()),all_complete_refs=int(g.all_complete.sum()),time_comparable_refs=int(g.recorded_time_single_source.sum()),fail_A_refs=int(g.A_failure.sum()),fail_B_refs=int(g.B_failure.sum()),fail_C_refs=int(g.C_failure.sum()),new_fusion_in_evaluation=0))
    E=pd.concat(regs,ignore_index=True);assert not E[['evaluation_stage','event_id']].duplicated().any()
    write(HERE/'ALL_EVENT_REFERENCE_INDEX.csv.gz',E)
    write(HERE/'ACTUAL_COVERAGE.csv',pd.DataFrame(coverage))
    opportunities=[]
    cap=pd.read_csv(HERE/'NATIVE_CAPACITY.csv.gz',dtype=str,keep_default_na=False)
    for (condition,domain),g in cap.groupby(['condition','source_domain']):
        f=g[g.status.eq('registered')];theory=sum(map(int,f.theoretical_ordered_ABC));actual=E[E.evaluation_stage.eq('native')&E.condition.eq(condition)&E.source_domain.eq(domain+'_labelled')]
        opportunities.append(dict(stage='native',condition=condition,source_domain=domain,method_id='V3_JOINT_QT',opportunity_unit='ordered ABC within registered class-direction,n,m cells',feasible_direction_n_cells=len(f),insufficient_capacity_cells=int(g.status.eq('insufficient_capacity').sum()),feasible_ABC=str(theory),registered_event_refs=len(actual),registered_oriented_ABC=actual.oriented_set_id.nunique(),unexpanded_ABC=str(theory-actual.oriented_set_id.nunique()),member_exhaustive=False,reason='two frozen member/background paths per feasible direction,n,m; all directions retained; domains can overlap'))
    cap=pd.read_csv(HERE/'CACHED_OPPORTUNITIES.csv.gz',low_memory=False)
    for (condition,domain),g in cap.groupby(['condition','source_domain']):
        theory=int(g.all_feasible_ABC_r2.fillna(0).sum());actual=E[E.evaluation_stage.eq('cached')&E.condition.eq(condition)&E.source_domain.eq(domain)]
        opportunities.append(dict(stage='cached',condition=condition,source_domain=domain,method_id='V3_JOINT_QT',opportunity_unit='ordered ABC opportunities indexed by full 924 panel and shared variable background',feasible_backgrounds=int(g.status.eq('registered').sum()),no_r2_backgrounds=int(g.status.eq('no_r2_matched_opportunity').sum()),unknown_label_panels=int(g.status.eq('unknown_label_in_panel').sum()),feasible_source_anchors=int(g.source_anchors_with_r2_count.fillna(0).sum()),feasible_ABC=str(theory),registered_event_refs=len(actual),registered_oriented_ABC=actual.oriented_set_id.nunique(),unexpanded_ABC=str(theory-len(actual)),member_exhaustive=False,reason='all 66 shared backgrounds checked; one hash A per feasible background; all B and frozen-best C ties; no further fusion needed to expand unvisited anchors'))
    write(HERE/'OPPORTUNITY_COMPLETION.csv',pd.DataFrame(opportunities))
    # All stages share the same endpoint identity. Repeated uses are references.
    physical=E.groupby('physical_set_id').agg(event_refs=('event_id','size'),stages=('evaluation_stage',lambda s:'|'.join(sorted(set(s)))),methods=('method_id',lambda s:'|'.join(sorted(set(s)))),conditions=('condition',lambda s:'|'.join(sorted(set(s)))),oriented_triples=('oriented_set_id','nunique')).reset_index()
    write(HERE/'PHYSICAL_TRIPLE_USE_INDEX.csv.gz',physical)
    keys=set(E.team_A)|set(E.team_B)|set(E.team_C)
    old=pd.read_csv(COMP/'delivery/ENDPOINT_KEY_INDEX.csv.gz',low_memory=False)
    old=old[old.team_key.isin(keys)].copy();old['canonical_match']=old.endpoint_stage.eq(old.canonical_stage)
    old=old.sort_values(['team_key','canonical_match'],ascending=[True,False]).drop_duplicates('team_key')
    refs=[]
    for r in old.to_dict('records'):
        refs.append(dict(team_key=r['team_key'],condition=r['condition'],pool_id=r['pool_id'],image=r['image'],building=r['building'],n=int(r['n']),member_workers=r['member_workers'],origin='reused_v3_endpoint',scalar_file=str((COMP/r['scalar_file']).relative_to(ROOT)),geometry_file=str((COMP/r['geometry_file']).relative_to(ROOT)),request_file=str((COMP/r['request_file']).relative_to(ROOT)),endpoint_stage=r['endpoint_stage'],batch_id=r['batch_id']))
    known={r['team_key'] for r in refs}
    for batch in sorted((HERE.parent/'expanded_blocks/batches').glob('joint_*')):
        assert (batch/'COMPLETION.json').exists(),batch
        req=pd.read_csv(batch/'REQUESTS.csv.gz',low_memory=False)
        for r in req[req.team_key.isin(keys-known)].to_dict('records'):
            refs.append(dict(team_key=r['team_key'],condition=r['condition'],pool_id=r['pool_id'],image=r['image'],building=r['building'],n=int(r.get('n',r.get('k'))),member_workers=r['member_workers'],origin='new_native_joint_endpoint',scalar_file=str((batch/'ENDPOINT_SCALARS.csv.gz').relative_to(ROOT)),geometry_file=str((batch/'ENDPOINT_GEOMETRY.csv.gz').relative_to(ROOT)),request_file=str((batch/'REQUESTS.csv.gz').relative_to(ROOT)),endpoint_stage='JOINT_NATIVE_20261022',batch_id=batch.name));known.add(r['team_key'])
    R=pd.DataFrame(refs).sort_values('team_key');assert set(R.team_key)==keys;assert not R.team_key.duplicated().any()
    write(HERE/'ALL_USED_TEAM_REFERENCES.csv.gz',R)
    sourcefiles=[]
    for kind in ['scalar_file','geometry_file','request_file']:
        for fname,g in R.groupby(kind):
            fp=ROOT/fname;assert fp.exists(),fp
            sourcefiles.append(dict(source_kind=kind,file=fname,referenced_teams=g.team_key.nunique(),bytes=fp.stat().st_size,sha256=sha(fp)))
    write(HERE/'ENDPOINT_SOURCE_FILES.csv',pd.DataFrame(sourcefiles))
    dependencies=[
        TAX/'JOINT_LABELS_LOBO.csv.gz',TAX/'LABEL_FREEZE.json',COMP/'PANELS.csv',COMP/'DESIGN_TEAMS.csv.gz',COMP/'delivery/ENDPOINT_KEY_INDEX.csv.gz',
        V3/'utility/cross_panel_LOBO/manual/new_joint/FITS.csv.gz',V3/'utility/cross_panel_LOBO/semi/new_joint/FITS.csv.gz',
        HERE.parent/'cross_condition_taxonomy/CROSS_LABELS_LOBO.csv.gz',HERE.parent/'cross_condition_taxonomy/CROSS_CLASS_CENTERS_LOBO.csv.gz',
        ROOT/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz',
        ROOT/'research/workers/personnel_global_composition_20261021/composition/global_study.py',
        ROOT/'research/workers/personnel_global_composition_20261021/continuation_20261021/n20_abc/event_kernel.py',
        ROOT/'research/workers/personnel_global_composition_20261021/continuation_20261021/n20_abc/evaluate_n20_abc.py',
        ROOT/'research/workers/personnel_global_composition_20261021/continuation_20261021/n20_abc/discover_n20_abc.py',
        ROOT/'research/workers/personnel_global_composition_20261021/analysis/analyze_global.py',
        HERE.parent/'expanded_blocks/run_native.py']
    dependencies.extend(ROOT/f for f in [
        'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/fusion_engine.py',
        'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/pool_io.py',
        'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz',
        'research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py',
        'research/workers/personnel_interchangeability_20261020/analysis/composition/summarize_grid.py',
        'research/workers/personnel_interchangeability_20261020/analysis/composition/geometry_diagnostics.py',
        'research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py',
        'tools/thesis_main/analysis/consensus_delivery_20261008.py',
        'tools/thesis_main/analysis/wall_consensus_v1_process_20261017.py',
        'tools/thesis_main/analysis/wall_consensus_population_20261014.py',
        'tools/thesis_main/analysis/research_round_20260929.py',
        'tools/thesis_main/analysis/scope_quality_scoring_20261016.py',
        'tools/thesis_main/analysis/wall_consensus_quality_20261015.py',
        'tools/thesis_main/analysis/quality_b8l2_d10_20261017.py',
        'tools/thesis_main/analysis/wall_consensus_b8l2_20261016.py',
        'tools/thesis_main/analysis/paired_split_research/study.py'])
    # Direct imports are provided by the checked-out repository, not duplicated
    # with all historical caches in this deliverable.
    records=[]
    for f in dependencies:
        if not f.exists():raise FileNotFoundError(f)
        records.append(dict(file=str(f.relative_to(ROOT)),bytes=f.stat().st_size,sha256=sha(f),purpose='existing_frozen_reference_or_code'))
    for f in sorted(HERE.glob('*.py')):records.append(dict(file=str(f.relative_to(ROOT)),bytes=f.stat().st_size,sha256=sha(f),purpose='new_topic_code'))
    write(HERE/'INPUT_AND_CODE_DEPENDENCIES.csv',pd.DataFrame(records))
    # The frozen geometry engine inserts this existing runtime-only dependency
    # directory. Mirror its lookup for version recording; do not bundle it.
    sys.path.insert(0,'/tmp/hohonet_deps')
    versions={k:importlib.metadata.version(k) for k in ['numpy','pandas','scipy','shapely','matplotlib']}
    save(HERE/'ENVIRONMENT.json',dict(python=platform.python_version(),platform=platform.platform(),packages=versions,blas_threads=1,repository_main='324dba44d0a82d9d64a62965f2e549ee05165417'))
    summary=dict(status='complete',events_by_stage=E.groupby('evaluation_stage').size().to_dict(),event_references=len(E),global_event_id_unique=E.event_id.nunique(),physical_triples=E.physical_set_id.nunique(),oriented_triples=E.oriented_set_id.nunique(),unique_team_endpoints=len(keys),reused_team_endpoints=int(R.origin.eq('reused_v3_endpoint').sum()),new_native_team_endpoints=int(R.origin.eq('new_native_joint_endpoint').sum()),stages_per_physical_distribution=physical.stages.str.count(r'\|').add(1).value_counts().sort_index().to_dict(),same_physical_different_method_triples=int(physical.methods.str.contains(r'\|').sum()),all_registered_completed=True,new_fusion_during_evaluation=0,all_teams_combinations_exhaustive=False,native_finite_registered_directions_complete=True,native_member_paths_per_direction_n=2,cached_background_inventory_complete=True,cached_members_per_background_exhaustive=False,shared_method_anchors_not_independent_event_references=True)
    save(HERE/'FINAL_COVERAGE_RECEIPT.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
