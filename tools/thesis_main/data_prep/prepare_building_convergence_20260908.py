"""Portable building/context coverage and existing replay inventory; no new convergence fit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

BASE='analysis_results/uncertainty_cloud_inputs_20260906_v1'
READY='analysis_results/uncertainty_decision_ready_20260908_v1'
OUTPUT='analysis_results/building_convergence_preparation_20260908_v1'
IDENTITY=['building_id','image_id','stage','block_index','raw_condition']


def read(path):return pd.read_csv(path,dtype=str,keep_default_na=False)
def js(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def yes(series):
    if not series.str.lower().isin(['true','false']).all():raise ValueError('unknown_boolean_not_success')
    return series.str.lower()=='true'


def context_rows(a):
    if not a.canonical_annotation_id.is_unique or a.duplicated(['context_key','worker_id']).any():raise ValueError('duplicate_canonical_or_worker_context')
    if a[['canonical_annotation_id','context_key','worker_id',*IDENTITY]].isna().any().any() or a[['canonical_annotation_id','context_key','worker_id',*IDENTITY]].eq('').any().any():raise ValueError('missing_identity')
    if (a.groupby('worker_id').current20_member.nunique()!=1).any():raise ValueError('roster_conflict')
    rows=[];roster=set(a.loc[yes(a.current20_member),'worker_id'])
    for context,g in a.groupby('context_key'):
        if any(g[c].nunique()!=1 for c in IDENTITY):raise ValueError('context_metadata_conflict')
        workers=set(g.worker_id);current=workers&roster;n=len(workers)
        seen=set(a.loc[a.image_id==g.image_id.iloc[0],'worker_id'])
        row={c:g.iloc[0][c] for c in IDENTITY}
        row.update(context_key=context,response_count=len(g),worker_count=n,current20_worker_count=len(current),
            worker_ids_json=js(sorted(workers,key=int)),current20_worker_ids_json=js(sorted(current,key=int)),
            raw_geometry_computable_count=int(yes(g.raw_geometry_computable).sum()),
            max_equal_disjoint_k=n//2,current20_observed_max_equal_disjoint_k=len(current)//2,
            current20_seen_same_image_count=len(roster&seen),current20_no_record_same_image_count=len(roster-seen),
            current20_no_record_same_image_ids_json=js(sorted(roster-seen,key=int)),
            true_new_worker_availability='unknown_not_recruited')
        rows.append(row)
    return pd.DataFrame(rows)


def building_rows(contexts,a):
    rows=[]
    for building,g in contexts.groupby('building_id'):
        people=a[a.building_id==building]
        rows.append(dict(building_id=building,images=g.image_id.nunique(),contexts=len(g),
            canonical_responses=int(g.response_count.sum()),building_union_worker_count=people.worker_id.nunique(),
            building_union_current20_worker_count=people.loc[yes(people.current20_member),'worker_id'].nunique(),
            minimum_context_workers=int(g.worker_count.min()),maximum_context_workers=int(g.worker_count.max()),
            context_worker_count_is_not_building_union=True))
    return pd.DataFrame(rows)


def candidate_rows(images,a):
    c=images[images.population_role=='candidate_without_historical_annotation'].copy()
    if c.image_id.isin(a.image_id).any():raise ValueError('candidate_has_historical_response')
    c['historical_response_count']=0;c['historical_worker_count']=0
    c['has_historical_building']=c.building_id.isin(a.building_id)
    c['true_new_worker_availability']='unknown_not_recruited'
    return c


def link_contexts(frame,contexts):
    """Join legacy files by fields; only explicit old context supplies missing block."""
    rows=[]
    for row in frame.to_dict('records'):
        if row.get('context_key') in set(contexts.context_key):
            matches=contexts[contexts.context_key==row['context_key']]
            aliases={'image_id':['image_id','base_task_id','image'],'building_id':['building_id','building'],
                     'stage':['stage'],'block_index':['block_index'],'raw_condition':['raw_condition','condition']}
            for field,names in aliases.items():
                for name in names:
                    if row.get(name,'')!='' and str(row[name])!=str(matches.iloc[0][field]):
                        raise ValueError('valid_context_key_metadata_conflict:'+name)
        else:
            image=row.get('image_id',row.get('base_task_id',row.get('image','')))
            condition=row.get('raw_condition',row.get('condition',''))
            stage=row.get('stage','');block=row.get('block_index','')
            if row.get('context'):
                parts=str(row['context']).split('|')
                if len(parts)!=4 or (stage and parts[0]!=stage) or (condition and parts[2]!=condition) or (image and parts[3]!=image):
                    raise ValueError('legacy_context_order_or_fields_conflict')
                stage,block,condition,image=parts
            matches=contexts[(contexts.image_id==image)&(contexts.stage==stage)]
            if condition:matches=matches[matches.raw_condition==condition]
            if block!='':matches=matches[matches.block_index==str(block)]
        row['context_link_status']='matched' if len(matches)==1 else 'ambiguous_context' if len(matches)>1 else 'unmatched_context'
        row['context_key']=matches.context_key.iloc[0] if len(matches)==1 else ''
        rows.append(row)
    return pd.DataFrame(rows)


def curve_specs():
    old='analysis_results/historical_uncertainty_recompute_20260829_v1/'
    pre='analysis_results/preflight_20260906_v2/'
    follow='analysis_results/uncertainty_followup_analysis_20260908_v1/'
    code='tools/thesis_main/analysis/'
    # Explicit semantics, not inferred from a filename or a small numerical value.
    return [
      (BASE+'/archive/historical42_partitions.csv.gz',code+'materialize_historical_uncertainty_k_curves_20260829.py','partition_support','historical42_strict_roster','yes','fixed_full_partition','旧42分区与阈值，非人数曲线'),
      (old+'reference_free_curves.csv',code+'materialize_historical_uncertainty_k_curves_20260829.py','reference_free_status_curves','historical42_eligible_roster','yes','subset_recomputed','历史状态恢复，不是正确性'),
      (old+'aggregate_quality_task_k.csv',code+'materialize_historical_uncertainty_k_curves_20260829.py','reference_relative_quality_and_delivery','historical_reference_ready_41_common_support_to13','not_applicable_reference_layout_provenance_separate','subset_recomputed','共同reference支持止于k13，不称20人质量平台；参考布局独立性另行核实'),
      (old+'minority_mode_replay_task_k.csv',code+'materialize_historical_uncertainty_k_curves_20260829.py','same_second_mode_recovery','historical42_full_strict_roster','yes','fixed_target_subset_recomputed','全量第二簇为目标；并列和不可算须保留'),
      (BASE+'/archive/extended73_k_replay.csv.gz',code+'audit_annotation_research_data_20260905.py','status_partition_second_mode_recovery','all_observed_canonical_no_old_eligibility','yes','fixed_target_subset_recomputed','73原支持单元；k15–20可算支持随条件变化'),
      (BASE+'/archive/extended73_k_summary.csv.gz',code+'audit_annotation_research_data_20260905.py','task_and_building_equal_recovery','see_support_set','yes','fixed_target_subset_recomputed','仅汇总，不可无条件连接逐图'),
      ('analysis_results/annotation_research_prework_20260905_v2/statistics/strict_medoid_replay_summary.csv',code+'materialize_annotation_research_prework_statistics_20260905.py','remaining_d_mask_mean','strict_geometry_selected_vs_remaining','no_remaining_workers_disjoint','no_cluster_target','剩余同图人员验证；k=N时无剩余'),
      (pre+'task_inventory.csv',code+'preflight_data_20260906.py','strict_support_inventory','strict_geometry_at_least2','not_applicable','not_applicable','230context非全部270；70个strictN>=20'),
      (pre+'precision_curves_k_and_fraction.csv',code+'preflight_statistics_20260906.py','finite_sd;empirical_iid_sd;medoid_step;medoid_remaining;medoid_reference','strict_N>=20_historical_roster','mixed_see_metric_contract','no_cluster_for_precision','有限全量含子样本；remaining排除子样本；iid非新人'),
      (pre+'minority_capture_curves.csv',code+'preflight_statistics_20260906.py','second_mode_capture2','full_strict_empirical_second_cluster','yes','fixed_full_complete_link','捕获至少2个成员，不验证合法解释'),
      (pre+'denominator_tolerance_sensitivity.csv',code+'preflight_statistics_20260906.py','finite_first_k;empirical_iid_first_k_to200;medoid_hindsight_first_stable_k','strict_N>=20_roster','mixed','not_applicable','first_k是已有探索阈值诊断；medoid使用后续到20全部步长，是事后量'),
      (pre+'standardized_N20_summary.csv',code+'preflight_deliver_20260906.py','standardized_support_first_k','historical_subsamples_of20','yes','not_applicable','有限样本分母敏感性，不是独立新20人'),
      (pre+'fixed_panel_vs_independent.csv',code+'preflight_panels_20260906.py','condition_common_image_mean_disagreement_variance','common_current20_historical_panels','yes','not_applicable','按阶段/条件共同图片的固定跨图面板，可跨多栋楼；不是单楼曲线'),
      (pre+'current20_panel_feasibility.csv',code+'preflight_panels_20260906.py','common_image_support','current20_observed','not_applicable','not_applicable','旧严格集合内可行性，不是新人'),
      (pre+'current20_composition_replay.csv',code+'preflight_panels_20260906.py','pairwise_D;medoid_reference_distance','current20_crossfit_tentative_groups','mixed','not_applicable','旧人员画像仅背景，不作为building主线'),
      (pre+'rebuilt_asymptote_sensitivity.csv',code+'preflight_deliver_20260906.py','power_asymptote_sensitivity','finite_historical_curves','yes','not_applicable','既有外推敏感性，不采纳为上限结论'),
      (follow+'fixed_partition_capture.csv',code+'analyze_uncertainty_handoff.py','expected_cluster_capture','archived_extended73_unique_partitions','yes','fixed_full_partition','不重新分簇，实际覆盖见数据'),
      (follow+'confirmed_20260908/distribution_recovery.csv',code+'analyze_uncertainty_handoff.py','expected_tv;expected_missing_mass;expected_cluster_fraction','archived_all_or_current20','yes_full_archived_target','fixed_full_partition','经验全体含被抽子样本；current20目标仍是全体历史簇'),
      (follow+'confirmed_20260908/building_distribution_fixed51.csv',code+'analyze_uncertainty_handoff.py','building_equal_distribution_recovery','fixed51_current20_complete_partitions','yes','fixed_full_partition','固定51单元building汇总，仅k15/20'),
      (follow+'confirmed_20260908/roster_mixture.csv',code+'analyze_uncertainty_handoff.py','distribution_recovery_by_roster_mix','historical_current20_plus_historical_outside','yes','fixed_full_partition','outside不是新人；固定total_k20'),
      ('analysis_results/bottleneck_reanalysis_20260906_v1/READING_GUIDE_ZH.md',code+'bottleneck_models_20260906.py','description_only','unknown','unknown','unknown','仅查到说明；代码存在性独立登记，不视为完整分析'),
    ]


def main(root,out):
    out.mkdir(parents=True,exist_ok=True);sources=[]
    def load(path):
        p=root/path;sources.append(dict(path=path,exists=p.is_file(),bytes=p.stat().st_size if p.is_file() else None))
        return read(p)
    a=load(BASE+'/annotations.csv.gz');images=load(BASE+'/images.csv');response=load(READY+'/response_index.csv.gz')
    if not images.image_id.is_unique or not images.population_role.isin(['historical_annotated','candidate_without_historical_annotation']).all():raise ValueError('unknown_image_role_or_duplicate')
    if set(response.canonical_annotation_id)!=set(a.canonical_annotation_id):raise ValueError('response_universe_mismatch')
    for c in ['context_key',*IDENTITY,'worker_id']:
        if not a.set_index('canonical_annotation_id')[c].sort_index().equals(response.set_index('canonical_annotation_id')[c].sort_index()):raise ValueError('response_identity_conflict:'+c)
    contexts=context_rows(a);roster=a[['worker_id','current20_member']].drop_duplicates().sort_values('worker_id',key=lambda s:s.astype(int))
    roster.to_csv(out/'worker_roster.csv',index=False)
    parts=load(BASE+'/clusters/partitions.csv.gz');members=load(BASE+'/clusters/memberships.csv.gz')
    parts.to_csv(out/'cluster_partition_index.csv.gz',index=False)
    geo=load(READY+'/geometry/human_bi_comparisons.csv.gz');geo=geo[geo.representation=='native_uv']
    if not set(geo.canonical_annotation_id)<=set(a.canonical_annotation_id):raise ValueError('geometry_unknown_canonical')
    semantics=root/READY/'semantics/case_evidence.jsonl'
    cases=[json.loads(x) for x in semantics.read_text(encoding='utf-8').splitlines() if x.strip()]
    bindings=[json.loads(x) for x in (semantics.parent/'response_semantic_links.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    case_map={r['image_id']:r['case_id'] for r in cases}
    comment_rows=[]
    for r in cases:
        answers=(r.get('original_human_record') or {}).get('answers',{})
        comment_rows.append(dict(image_id=r['image_id'],case_id=r['case_id'],human_notes=answers.get('notes',''),
            human_review_status=answers.get('status',''),later_human_supplement_json=js(r.get('later_human_supplement')),
            final_user_decision_json=js(r.get('final_user_decision')),source=READY+'/semantics/case_evidence.jsonl',
            use_scope='image_comment_not_whole_cluster_or_worker_label'))
    pd.DataFrame(comment_rows).to_csv(out/'existing_human_comment_index.csv',index=False)
    pd.DataFrame(bindings).to_json(out/'response_comment_links.jsonl',orient='records',lines=True,force_ascii=False)
    extra=[]
    for c in contexts.to_dict('records'):
        r=response[response.context_key==c['context_key']];p=parts[parts.context_key==c['context_key']]
        c.update(partition_ids_json=js(p.partition_id.tolist()),partition_version_status_json=js(p[['version','partition_status','structure_status','member_count']].to_dict('records')),
            initialization_source_counts_json=js(r.initialization_reconstructed_source.replace('','unknown_not_recorded').value_counts().to_dict()),
            initial_import_match_status_counts_json=js(r.initial_import_match_status.replace('','unknown_not_applicable_or_missing').value_counts().to_dict()),
            legacy_initialization_source_counts_json=js(r.legacy_initialization_source_kind.replace('','unknown_not_applicable_or_missing').value_counts().to_dict()),
            case_id=case_map.get(c['image_id'],''),human_comment_link_status='image_link_only' if c['image_id'] in case_map else 'no_existing_case_record',
            canonical_annotation_ids_json=js(r.canonical_annotation_id.tolist()))
        for reading in ['serialized_adjacency','historical_pairmap_unaveraged']:
            g=geo[(geo.context_key==c['context_key'])&(geo.reading==reading)]
            if len(g)!=len(r):raise ValueError('geometry_coverage_missing')
            c[reading+'_human_status_counts_json']=js(g.human_status.value_counts().to_dict())
            c[reading+'_bi_comparison_status_counts_json']=js(g.comparison_status.value_counts().to_dict())
        extra.append(c)
    contexts=pd.DataFrame(extra).merge(images.drop(columns='building_id'),on='image_id',validate='many_to_one')
    contexts.to_csv(out/'building_image_context_coverage.csv',index=False)
    response.to_csv(out/'response_identity_index.csv.gz',index=False)
    candidates=candidate_rows(images,a)
    human=json.loads((root/BASE/'archive/human30.json').read_text(encoding='utf-8'))
    ai=json.loads((root/BASE/'archive/ai50_selection.json').read_text(encoding='utf-8'))
    human_ids={r['image_id']:r.get('review_id','') for r in human['items']}
    # Selection source is recorded even if its schema changes; never infer AI review from membership.
    ai_items=ai.get('items',ai.get('selected',[]))
    if not ai_items:raise ValueError('unknown_ai50_selection_schema')
    ai_ids={r['image_id']:r.get('review_id','') for r in ai_items}
    candidates['prior_human30_review_id']=candidates.image_id.map(human_ids).fillna('')
    candidates['prior_ai50_selection_id']=candidates.image_id.map(ai_ids).fillna('')
    candidates['later_case_id']=candidates.image_id.map(case_map).fillna('')
    candidates['image_fetch_command']=candidates.image_id.map(lambda i:'python '+BASE+'/cloud_inputs.py image --package '+BASE+' --image-id '+i+' --output panorama.jpg')
    candidates['image_access_status']=candidates.image_url.map(lambda s:'url_present_access_not_checked' if s else 'missing_url')
    candidates.to_csv(out/'candidate_images.csv',index=False)
    b=building_rows(contexts,a);candidate_counts=candidates.groupby('building_id').size()
    b['candidate_images']=b.building_id.map(candidate_counts).fillna(0).astype(int)
    b.to_csv(out/'building_summary.csv',index=False)
    stage_rows=[];arithmetic=[]
    for key,all_g in contexts.groupby(['building_id','stage','raw_condition']):
        for scope,g in [('all_contexts',all_g),('raw_support_ge20_coverage_only',all_g[all_g.worker_count>=20])]:
            sets=[set(json.loads(s)) for s in g.worker_ids_json];current=[set(json.loads(s)) for s in g.current20_worker_ids_json]
            common=set.intersection(*sets) if sets else set();cc=set.intersection(*current) if current else set()
            stage_rows.append(dict(zip(['building_id','stage','raw_condition'],key))|dict(contexts=len(g),images=g.image_id.nunique(),
                canonical_responses=int(g.response_count.sum()),minimum_context_workers=int(g.worker_count.min()) if len(g) else None,
                maximum_context_workers=int(g.worker_count.max()) if len(g) else None,
                contexts_ge15=int((g.worker_count>=15).sum()),contexts_ge20=int((g.worker_count>=20).sum()),
                all_context_common_worker_count=len(common),all_context_common_worker_ids_json=js(sorted(common,key=int)),
                all_context_common_max_equal_disjoint_k=len(common)//2,current20_all_context_common_count=len(cc),
                current20_all_context_common_max_equal_disjoint_k=len(cc)//2,scope=scope,
                support_status='observed' if len(g) else 'no_context_in_this_coverage_view'))
    for r in contexts.to_dict('records'):
        for k in range(15,21):
            n=r['worker_count'];cur=r['current20_worker_count']
            arithmetic.append({x:r[x] for x in ['context_key',*IDENTITY]}|dict(k=k,historical_N=n,current20_observed_N=cur,
                one_historical_group_supported=n>=k,remaining_historical_workers_after_k=n-k if n>=k else None,
                two_disjoint_equal_k_groups_supported=n>=2*k,current20_two_disjoint_equal_k_supported=cur>=2*k,
                additional_distinct_responses_needed_for_two_k=max(0,2*k-n),
                additional_responses_are_not_confirmed_new_people=True,finite_population_endpoint=k==n))
    pd.DataFrame(stage_rows).to_csv(out/'building_stage_condition_support.csv',index=False)
    pd.DataFrame(arithmetic).to_csv(out/'same_image_disjoint_group_arithmetic.csv',index=False)
    inventory=[];portable=[]
    for path,code,metric,reference,selfref,cluster,note in curve_specs():
        p=root/path;row=dict(path=path,generator=code,generator_exists=(root/code).is_file(),exists=p.is_file(),metric_contract=metric,
            reference_population=reference,full_reference_contains_evaluated_subset=selfref,cluster_contract=cluster,note=note,
            status='existing_not_newly_recomputed' if p.is_file() else 'missing_not_claimed_executed')
        if metric=='description_only':row['status']='description_only_missing_generator' if not row['generator_exists'] else 'description_only'
        sources.append(dict(path=path,exists=p.is_file(),bytes=p.stat().st_size if p.is_file() else None))
        if p.is_file() and '.csv' in p.name:
            d=read(p);row.update(rows=len(d),columns_json=js(list(d.columns)))
            for col in ['k','k_valid','total_k']:
                if col in d:
                    v=pd.to_numeric(d[col],errors='coerce').dropna();row[col+'_range']=js([float(v.min()),float(v.max())]) if len(v) else '[]'
            if ('context_key' in d or 'context' in d or (any(c in d for c in ['image_id','base_task_id','image']) and 'stage' in d)):
                linked=link_contexts(d,contexts);row['context_link_counts_json']=js(linked.context_link_status.value_counts().to_dict())
                row['matched_contexts']=linked.loc[linked.context_link_status=='matched','context_key'].nunique()
                for i,r in enumerate(linked.to_dict('records')):
                    portable.append(dict(source_file=path,source_row=i,context_key=r['context_key'],context_link_status=r['context_link_status'],
                        metric_contract=metric,original_row_json=js({k:v for k,v in r.items() if k not in ['context_key','context_link_status']})))
        inventory.append(row)
    pd.DataFrame(inventory).to_csv(out/'existing_curve_inventory.csv',index=False)
    pd.DataFrame(portable).to_csv(out/'existing_curves_context_links.csv.gz',index=False)
    qa=dict(canonical_responses=len(a),historical_images=a.image_id.nunique(),contexts=len(contexts),historical_buildings=len(b),
            historical_workers=a.worker_id.nunique(),current20_count=int(yes(roster.current20_member).sum()),
            candidates=len(candidates),candidates_in_historical_buildings=int(candidates.has_historical_building.sum()),
            partition_versions=parts.groupby('version').agg(partitions=('partition_id','size'),images=('image_id','nunique'),contexts=('context_key','nunique')).to_dict('index'),
            curve_files_existing=sum(r['exists'] for r in inventory),portable_source_rows=len(portable),
            external_image_access_tested=False,new_curve_fitting=False,new_people_claimed=False,
            audit_directory_owned_by_coordinator=True)
    (out/'PREPARATION_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    for path in [READY+'/semantics/case_evidence.jsonl',READY+'/semantics/response_semantic_links.jsonl',BASE+'/archive/human30.json',BASE+'/archive/ai50_selection.json']:
        p=root/path;sources.append(dict(path=path,exists=p.is_file(),bytes=p.stat().st_size if p.is_file() else None))
    (out/'SOURCE_FILES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False))


def verify(out):
    a=read(out/'response_identity_index.csv.gz');c=read(out/'building_image_context_coverage.csv')
    b=read(out/'building_summary.csv');cand=read(out/'candidate_images.csv');arith=read(out/'same_image_disjoint_group_arithmetic.csv')
    assert a.canonical_annotation_id.is_unique and not a.duplicated(['context_key','worker_id']).any()
    assert set(c.context_key)==set(a.context_key) and c.context_key.is_unique
    assert int(c.response_count.astype(int).sum())==len(a)
    assert not set(cand.image_id)&set(a.image_id) and cand.historical_response_count.astype(int).eq(0).all()
    for row in c.to_dict('records'):
        g=a[a.context_key==row['context_key']];n=g.worker_id.nunique()
        assert n==int(row['worker_count'])==len(json.loads(row['worker_ids_json']))
        assert n//2==int(row['max_equal_disjoint_k'])
    for row in b.to_dict('records'):
        assert int(row['building_union_worker_count'])==a[a.building_id==row['building_id']].worker_id.nunique()
    assert len(arith)==6*len(c)
    assert yes(arith.two_disjoint_equal_k_groups_supported).equals(arith.historical_N.astype(int)>=2*arith.k.astype(int))
    linked=read(out/'existing_curves_context_links.csv.gz')
    assert set(linked.loc[linked.context_link_status=='matched','context_key'])<=set(c.context_key)
    views=read(out/'building_stage_condition_support.csv')
    for row in views.to_dict('records'):
        g=c[(c.building_id==row['building_id'])&(c.stage==row['stage'])&(c.raw_condition==row['raw_condition'])]
        if row['scope']=='raw_support_ge20_coverage_only':g=g[g.worker_count.astype(int)>=20]
        sets=[set(json.loads(s)) for s in g.worker_ids_json];common=set.intersection(*sets) if sets else set()
        assert len(g)==int(row['contexts']) and common==set(json.loads(row['all_context_common_worker_ids_json']))
    result=dict(status='passed',canonical=len(a),contexts=len(c),buildings=len(b),candidates=len(cand),
                curve_source_rows=len(linked),curve_link_status=linked.context_link_status.value_counts().to_dict(),
                group_arithmetic_rows=len(arith),new_convergence_fit=False,image_access_tested=False)
    (out/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size) for p in sorted(out.glob('*')) if p.is_file() and p.name!='FILE_LIST.json']
    (out/'FILE_LIST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);parser.add_argument('--out',type=Path)
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args();out=args.out or args.root/OUTPUT
    if args.verify_only:verify(out)
    else:main(args.root.resolve(),out)
