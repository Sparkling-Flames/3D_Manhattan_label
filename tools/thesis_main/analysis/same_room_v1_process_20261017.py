"""数据v1同房端点解释与真实人数过程请求；不执行新融合、不修改冻结负载。"""
import itertools
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.project_public_research_20260929 import project_bundle
from .research_round_20260929 import prepare_record, reconstruct
from .same_room_b8l2_20261016 import ROOT, metadata, pair_tables
from .same_room_quality_curves_20261015 import save
from .same_room_similarity_20261003 import correlation
from .same_room_update_20261017 import prepare_panel, metric_sensitivity
from .wall_consensus_population_20261014 import footprint

OUT=ROOT/'research/same_room/same_room_v1_process_20261017'
VERSION='same_room_v1_process_20261017_a1'
FUSION_OUT='research/fusion/wall_consensus_v1_process_20261017'
REPEATS=4
SEED=20261017


def balanced_gap(rows):
    rooms=rows.groupby(['building','user_group_ids']).absolute_mean_gap.mean()
    buildings=rooms.groupby(level=0).mean()
    return dict(pairs=len(rows),buildings=len(buildings),user_groups=len(rooms),
        pair_equal_gap=float(rows.absolute_mean_gap.mean()),
        group_equal_gap=float(rooms.mean()),building_group_equal_gap=float(buildings.mean()))


def member_exclusion(row,gate,obj):
    reasons=[]
    if not row['pool_analysis_eligible']:reasons.append('source_pool_ineligible')
    if gate['original_holdout'] is True:reasons.append('original_holdout')
    elif gate['original_holdout'] is not False:reasons.append('holdout_status_unknown')
    if gate['role']!='manual_development_candidate':reasons.append('existing_experiment_role:'+gate['role'])
    reasons.extend('personnel:'+v for v in gate['personnel_barriers'])
    reasons.extend('context:'+v for v in gate['context_barriers'])
    if obj['points_1024x512'] is None:reasons.append('source_points_missing')
    return reasons


def replay_orders(workers,*,repeats=REPEATS,seed=SEED):
    if len(workers)!=len(set(workers)):raise ValueError('duplicate worker in replay pool')
    rng=np.random.default_rng(seed)
    return [rng.permutation(sorted(workers)).tolist() for _ in range(repeats)]


def select_panel(candidates):
    ready=[dict(r) for r in candidates if r['n_common_process']>=3 and not r.get('defer_reasons')]
    ready.sort(key=lambda r:(not r['reference_quality_primary_eligible'],-r['n_common_process'],r['code_a'],r['code_b']))
    best={};used=set()
    for row in ready:
        key=(row['building'],row['user_group_ids'])
        views={row['code_a'],row['code_b']}
        if key not in best and not views&used:
            best[key]=row;used.update(views)
    first=[];later=[];buildings=set()
    for row in best.values():
        row['priority_wave']=1 if row['building'] not in buildings else 2
        buildings.add(row['building'])
        (first if row['priority_wave']==1 else later).append(row)
    return first+later


def number_or_none(value):
    return float(value) if value is not None and pd.notna(value) and np.isfinite(value) else None


def load_v1():
    release=json.loads((ROOT/'research/data/releases/v1/RELEASE.json').read_text(encoding='utf-8'))
    assert release['data_release']=='v1' and release['status']=='frozen'
    bundle=load_current_bundle(ROOT/release['manifest'])
    with zipfile.ZipFile(ROOT/'research/data/releases/v1'/release['archive']) as archive:
        def read(path):return json.loads(archive.read(path).decode('utf-8-sig'))
        prefix=str(Path(release['manifest']).parent).replace('\\','/')
        frozen=read(prefix+'/data.json')
        current={o['object_id']:o for o in bundle['data']['objects']}
        assert set(current)=={o['object_id'] for o in frozen['objects']}
        for obj in frozen['objects']:
            for field in ['image_id','worker_id','condition','points_1024x512','ordered_source_pair_indices','ring_confirmed']:
                assert current[obj['object_id']].get(field)==obj.get(field),(obj['object_id'],field)
        base='research/quality/quality_b8l2_d10_20261017/'
        cross=read(base+'CROSS_MODULE_INPUTS.json')
        records=pd.read_csv(archive.open(cross['full_inventory_with_metric_eligibility']))
        refs={r['target_id']:r for r in read(base+'reference_catalog.json')}
        labels={r['image_id']:r for r in read(base+'difficulty_records.json')}
        relmanifest=read(cross['current_relation_adoption_manifest'])
        relations=read(relmanifest['relations'])
        gates={r['object_id']:r for r in read('research/workers/worker_b8l2_d10_20261017/admission_snapshot.json')}
        controls=pd.read_csv(archive.open('research/same_room/same_room_update_20261017/controls_by_building.csv'))
    assert cross['version']==release['quality_snapshot_version']
    assert len(records)==release['counts']['annotations'] and int(records.quality_usable.sum())==release['counts']['quality_usable']
    return release,bundle,cross,records,refs,labels,relmanifest,relations,gates,controls


def endpoint_analysis(records,relations,images,controls):
    metrics=['B8L2','D10','IoU3D100','source_time_seconds','target_matched_time_seconds']
    pairs,people,coverage=pair_tables(records,relations,images,metrics)
    save(OUT,'endpoint_pairs.csv',pairs);save(OUT,'endpoint_people.csv',people)
    save(OUT,'relation_source_coverage.csv',coverage)
    save(OUT,'metric_sensitivity.csv',metric_sensitivity(pairs))
    observed=pairs[pairs.n_paired.gt(0)].copy()
    observed['mean_difference_cancellation_fraction']=1-observed.absolute_mean_gap/observed.mean_absolute_person_delta.replace(0,np.nan)
    save(OUT,'endpoint_explanation.csv',observed)
    rows=[];balanced=[];loo=[]
    for minimum in [1,4]:
        valid=pairs[pairs.n_paired.ge(minimum)]
        for keys,g in valid.groupby(['metric','condition','confirmation','building','user_group_ids']):
            rows.append(dict(zip(['metric','condition','layer','building','user_group_ids'],keys),minimum_common=minimum,
                pairs=len(g),views=len(set(g.image_a)|set(g.image_b)),person_pair_occurrences=int(g.n_paired.sum()),
                gap_mean=float(g.absolute_mean_gap.mean()),gap_median=float(g.absolute_mean_gap.median()),
                gap_q25=float(g.absolute_mean_gap.quantile(.25)),gap_q75=float(g.absolute_mean_gap.quantile(.75)),
                mean_person_gap=float(g.mean_absolute_person_delta.mean()),
                rho_evaluable=int(g.worker_spearman.notna().sum()),rho_median=number_or_none(g.worker_spearman.median())))
        primary=valid[valid.condition.eq('manual')&valid.confirmation.eq('user_classified_comparable')]
        for metric,g in primary.groupby('metric'):
            balanced.append(dict(metric=metric,minimum_common=minimum,**balanced_gap(g)))
            for building in sorted(g.building.unique()):
                remaining=g[g.building.ne(building)]
                if len(remaining):loo.append(dict(metric=metric,minimum_common=minimum,omitted_building=building,**balanced_gap(remaining)))
    save(OUT,'coverage_by_building_group.csv',pd.DataFrame(rows))
    save(OUT,'balanced_endpoint_summary.csv',pd.DataFrame(balanced))
    save(OUT,'endpoint_leave_one_building_out.csv',pd.DataFrame(loo))
    controls=controls.copy();controls['source_minus_control']=controls.source_error-controls.control_error
    save(OUT,'building_controls.csv',controls)
    sensitivity=[]
    for metric,g in controls.groupby('metric'):
        for omitted in [None]+sorted(g.building.unique()):
            v=g if omitted is None else g[g.building.ne(omitted)]
            sensitivity.append(dict(metric=metric,omitted_building=omitted,buildings=len(v),
                source_mean=float(v.source_error.mean()),control_mean=float(v.control_error.mean()),
                source_minus_control=float(v.source_minus_control.mean()),source_favored_buildings=int(v.source_minus_control.lt(0).sum())))
    save(OUT,'control_leave_one_building_out.csv',pd.DataFrame(sensitivity))
    return pairs


def build_candidates(records,relations,objects,gates,refs,labels,images):
    grouped={i:g.set_index('worker_id') for i,g in records[records.condition.eq('manual')].groupby('image_id')}
    empty=records.iloc[:0].set_index('worker_id')
    rows=[];audits=[];pools={}
    for (a,b),relation in sorted(relations.items()):
        if not relation['physical_adopted']:continue
        aa,bb=grouped.get(a,empty),grouped.get(b,empty)
        common=sorted(set(aa.index)&set(bb.index));eligible=[]
        for worker in common:
            reasons=[]
            for side,frame in [('a',aa),('b',bb)]:
                row=frame.loc[worker].to_dict();oid=row['object_id']
                excluded=member_exclusion(row,gates[oid],objects[oid])
                audits.append(dict(image_a=a,image_b=b,worker_id=worker,side=side,object_id=oid,
                    reasons='|'.join(excluded),process_member_allowed=not excluded,
                    individual_quality_usable=bool(row['quality_usable']),bound_reference_id=row['reference_id']))
                reasons.extend(excluded)
            if not reasons:eligible.append(worker)
        references=[refs.get(labels[i]['target_version']) if i in labels else None for i in [a,b]]
        primary=all(ref and ref['full_reference_available'] for ref in references)
        for frame,image in [(aa,a),(bb,b)]:
            for worker in eligible:
                row=frame.loc[worker]
                primary=primary and bool(row.target_binding_unique and row.reference_id==labels[image]['target_version'] and not row.is_oos)
        reasons=[]
        if relation['analysis_layer']!='user_classified_comparable':reasons.append('different_or_pending_scope_not_initial_primary_design')
        if len(eligible)<3:reasons.append('common_window_below3_initial_process_design_not_image_exclusion')
        if not len(aa) or not len(bb):reasons.append('one_or_both_current_source_pools_unavailable')
        request_id='SRP_'+images[a]['image_code']+'__'+images[b]['image_code']
        row=dict(request_id=request_id,image_a=a,image_b=b,code_a=images[a]['image_code'],code_b=images[b]['image_code'],
            building=images[a]['building_id'],user_group_ids='|'.join(relation['user_group_ids']),relation_layer=relation['analysis_layer'],
            source_n_a=len(aa),source_n_b=len(bb),n_common_source=len(common),n_common_process=len(eligible),
            n_common_individual_quality=sum(bool(aa.loc[w].quality_usable and bb.loc[w].quality_usable) for w in eligible),
            reference_quality_primary_eligible=bool(primary),common_workers=eligible,defer_reasons=reasons)
        rows.append(row);pools[request_id]=(aa,bb,references)
    return rows,audits,pools


def create_requests(selected,pools,projected,aliases,objects,cross,release):
    request_pairs=[];prefix_rows=[];original_rows=[];original_summary=[]
    for index,candidate in enumerate(selected):
        orders=replay_orders(candidate['common_workers'],seed=SEED+index)
        frames=pools[candidate['request_id']][:2];references=pools[candidate['request_id']][2]
        views={};floor_by={}
        for side,frame,reference in zip(['a','b'],frames,references):
            members=[];floor_by[side]={}
            for worker in candidate['common_workers']:
                row=frame.loc[worker];obj=objects[row.object_id]
                fusion_record=prepare_record(dict(projected[aliases['records'][row.object_id]],source_pair_indices=obj['ordered_source_pair_indices']))
                original_geometry=reconstruct(fusion_record)
                floor_by[side][worker]=footprint(original_geometry['floor'])
                members.append(dict(worker_id=worker,object_id=row.object_id,record_id=fusion_record['id'],
                    fusion_worker=fusion_record['worker'],fusion_record=fusion_record,
                    bound_reference_id=None if pd.isna(row.reference_id) else row.reference_id,
                    target_binding_unique=bool(row.target_binding_unique),individual_quality_usable=bool(row.quality_usable),
                    source_time_seconds=number_or_none(row.source_time_seconds),target_matched_time_seconds=number_or_none(row.target_matched_time_seconds),
                    time_source=None if pd.isna(row.time_source) else row.time_source,
                    time_source_file=None if pd.isna(row.time_source_file) else row.time_source_file,
                    time_rule_version=None if pd.isna(row.time_rule_version) else row.time_rule_version))
            views[side]=dict(image_id=candidate['image_'+side],image=candidate['code_'+side],condition='manual',
                original_qualified_source_n=candidate['source_n_'+side],records=members,
                reference=dict(reference,evaluation_only=True) if reference else None)
        paths=[dict(replay_id=f'R{i:02d}',worker_order=order,
                    fusion_worker_order=[aliases['workers'][w] for w in order]) for i,order in enumerate(orders)]
        for path in paths:
            for k in range(1,len(path['worker_order'])+1):
                prefix=path['worker_order'][:k]
                for side,frame in zip(['a','b'],frames):
                    times=frame.loc[prefix]
                    prefix_rows.append(dict(data_release='v1',analysis_revision=VERSION,
                        request_id=candidate['request_id'],replay_id=path['replay_id'],side=side,k=k,
                        worker_ids='|'.join(prefix),object_ids='|'.join(times.object_id),
                        source_time_complete=bool(times.source_time_seconds.notna().all()),
                        cumulative_source_seconds=float(times.source_time_seconds.sum()) if times.source_time_seconds.notna().all() else None,
                        target_time_complete=bool(times.target_matched_time_seconds.notna().all()),
                        cumulative_target_seconds=float(times.target_matched_time_seconds.sum()) if times.target_matched_time_seconds.notna().all() else None))
        for wa,wb in itertools.combinations(candidate['common_workers'],2):
            values={}
            for side in ['a','b']:
                pa,pb=floor_by[side][wa],floor_by[side][wb]
                values[side]=None if pa is None or pb is None else 1-pa.intersection(pb).area/pa.union(pb).area
            original_rows.append(dict(request_id=candidate['request_id'],worker_a=wa,worker_b=wb,
                within_a_pair_disagreement=values['a'],within_b_pair_disagreement=values['b']))
        own=[r for r in original_rows if r['request_id']==candidate['request_id']]
        complete=[r for r in own if r['within_a_pair_disagreement'] is not None and r['within_b_pair_disagreement'] is not None]
        xa=np.array([r['within_a_pair_disagreement'] for r in complete]);xb=np.array([r['within_b_pair_disagreement'] for r in complete])
        original_summary.append(dict(request_id=candidate['request_id'],building=candidate['building'],user_group_ids=candidate['user_group_ids'],
            common_members=candidate['n_common_process'],attempted_worker_pairs=len(own),both_view_valid_worker_pairs=len(complete),
            valid_worker_pairs_a=sum(r['within_a_pair_disagreement'] is not None for r in own),
            valid_worker_pairs_b=sum(r['within_b_pair_disagreement'] is not None for r in own),
            original_R_a=float(xa.mean()) if len(xa) else None,original_R_b=float(xb.mean()) if len(xb) else None,
            worker_pair_pattern_spearman=correlation(xa,xb)))
        request_pairs.append(dict(candidate,condition='manual',status='ready',views=views,replays=paths,replay_seed=SEED+index,
            data_release='v1',input_revision=release['input_revision'],reference_quality_use='primary_if_output_evaluable' if candidate['reference_quality_primary_eligible'] else 'diagnostic_or_floor_only',
            declared_pool='common_source_development_workers; includes all retained members, not only individual quality successes',
            endpoint_definition='all_common_members_endpoint, not original whole-image full-person endpoint'))
    manifest=dict(schema='same_room_pair_process_requests_v1',analysis_revision=VERSION,data_release='v1',design_status='frozen',
        release_manifest='research/data/releases/v1/RELEASE.json',source_archive='research/data/releases/v1/snapshot.zip',
        input_manifest=release['manifest'],input_revision=release['input_revision'],common_score_version=cross['version'],
        metric_parameters=cross['parameters'],pairs=request_pairs,
        fusion_rule=dict(version='MV50_gap7.5_all_members_median_frozen',implementation='tools.thesis_main.analysis.consensus_delivery_20261008.fuse',gap_degrees=7.5,
            prefix_identity='rebuild using current prefix only; no full-pool identity/human ordering/future coordinates'),
        replay_design=dict(repeats=REPEATS,seed=SEED,sampling='independent uniform permutations with replacement; retain sampling frequency even if identical',
            k='every integer 1..N; k2 ordering deferred remains attempted/incomplete, never removed',
            pairing='identical canonical workers, entry order and k in both views',
            cache='same image + canonical member set + preparation/algorithm identity; cache geometry but do not deduplicate path counts'),
        selection='one pair per versioned working group, first one per building, then other groups; primary-reference availability, common N, fixed codes; never quality score magnitude',
        output_root=FUSION_OUT,expected_result_manifest=FUSION_OUT+'/MANIFEST.json',
        expected_trajectory_file=FUSION_OUT+'/trajectory_scores.csv',
        eligibility_audit=dict(candidates='research/same_room/same_room_v1_process_20261017/process_candidate_coverage.csv',
            members='research/same_room/same_room_v1_process_20261017/process_member_audit.csv'),
        output_contract=dict(required_trace=['request_id','replay_id','side','k','worker_ids','object_ids','data_release','reference_id','reference_version','geometry_source'],
            required_outcomes=['output_status','failure_reason','quality_use','B8L2','D10'],
            semantics='save real automatic geometry for every attempted prefix including failures; both metrics share geometry/reference/eligibility; normal quality masked when not allowed',
            pending='missing results are not_run, not numerical failure or zero score',
            stability='within-view comparisons across replays at fixed k and adjacent k only; no cross-camera BEV intersection',
            quality='reference scoring after geometry; never choose members, ordering, geometry or algorithm by target score',
            aggregation='per pair first, fixed available-N panel, then user groups/buildings equally; no all-member boundary interpreted as population convergence'))
    save(OUT,'PAIR_PROCESS_REQUESTS.json',manifest)
    save(OUT,'planned_prefixes.csv',pd.DataFrame(prefix_rows))
    save(OUT,'original_response_disagreement.csv',pd.DataFrame(original_rows))
    save(OUT,'original_response_disagreement_summary.csv',pd.DataFrame(original_summary))
    return manifest,prefix_rows


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    release,bundle,cross,raw,refs,labels,relmanifest,relation_rows,gates,controls=load_v1()
    record=prepare_panel(raw);objects={o['object_id']:o for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    images=metadata(bundle);relations={(r['image_a'],r['image_b']):r for r in relation_rows}
    candidates,audits,pools=build_candidates(record,relations,objects,gates,refs,labels,images)
    selected=select_panel(candidates)
    save(OUT,'process_candidate_coverage.csv',pd.DataFrame(candidates))
    save(OUT,'process_member_audit.csv',pd.DataFrame(audits))
    save(OUT,'selected_process_panel.csv',pd.DataFrame(selected))
    public,aliases=project_bundle(bundle)
    projected={r['id']:r for im in public['images'] for r in im['annotations']}
    request,prefixes=create_requests(selected,pools,projected,aliases,objects,cross,release)
    pairs=endpoint_analysis(record,relations,images,controls)
    expected=ROOT/request['expected_result_manifest']
    summary=dict(analysis_revision=VERSION,data_release='v1',input_revision=release['input_revision'],
        common_score_version=cross['version'],relation_version=relmanifest['version'],
        source_records=len(record),quality_records=int(raw.quality_usable.sum()),endpoint_pairs=pairs[pairs.n_paired.gt(0)].groupby(
            ['metric','condition','confirmation']).size().reset_index(name='pairs').to_dict('records'),
        selected_pairs=len(selected),selected_buildings=len({r['building'] for r in selected}),selected_user_groups=len({r['user_group_ids'] for r in selected}),
        initial_wave_pairs=sum(r['priority_wave']==1 for r in selected),replays_per_pair=REPEATS,planned_side_prefixes=len(prefixes),
        primary_reference_pairs=sum(r['reference_quality_primary_eligible'] for r in selected),
        requests_written=True,new_fusion_run_by_same_room_thread=False,
        process_comparison_status='results_arrived_require_separate_validation' if expected.exists() else 'awaiting_real_fusion_output',
        complete_paired_trajectory_conclusions=False,release_payload_modified=False)
    save(OUT,'SUMMARY.json',summary)
    save(OUT,'INPUTS.json',dict(data_release='v1',release_manifest='research/data/releases/v1/RELEASE.json',
        frozen_archive='research/data/releases/v1/snapshot.zip',common_score=cross,relation=relmanifest,
        frozen_geometry_identity_checked=True,existing_controls='frozen same_room_update_20261017/controls_by_building.csv'))
    save(OUT,'FIELD_CONTRACT.json',dict(analysis_revision=VERSION,data_release='v1',
        tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')},
        inputs='read frozen v1 archive; current loader geometry checked equal, no release/current bindings changed',
        endpoints='original-answer reference-score differences, person deltas, ranks and separate source/target times; not fusion endpoints',
        balanced='pair -> versioned user group -> building; report pair equal separately and all leave-one-building sensitivities',
        membership='common source/independent experimental-development members, original holds/barriers retained; quality success not an input filter',
        min_window='initial replay design uses >=3 common members; below3 remains in candidate inventory, not a new image eligibility gate',
        original_R='within-view bottom IoU disagreement of original answers only; compare scalar patterns, never cross-camera polygons',
        time='known cumulative active seconds only; any missing member gives missing full cumulative cost; replay not new human work',
        processes='requests/planned prefixes only until actual fusion output; no endpoint interpolation; not_run/failure/incomplete separate',
        all_member='paired common-pool endpoint differs from original full image pool endpoint; boundary variance zero is not correctness'))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
