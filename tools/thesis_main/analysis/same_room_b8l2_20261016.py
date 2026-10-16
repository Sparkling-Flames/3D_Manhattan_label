"""冻结v6同房质量/时间描述；原B8L2同集合接入，不改共同评分或参考。"""
import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .descriptive_inventory_20261015 import load_inventory
from .descriptive_pool_gate_20261015 import build_pool_gate, RULE_VERSION
from .same_room_similarity_20261003 import relation_index, correlation
from .same_room_quality_curves_20261015 import information_block, save, read
from .scope_quality_scoring_20261016 import scoring_engine

ROOT=Path(__file__).resolve().parents[3]
SHARED=ROOT/'research/statistics/b8l2_shared_v6_20261016'
OUT=ROOT/'research/same_room/same_room_b8l2_v6_20261016'
OLD=ROOT/'research/same_room/same_room_quality_curves_20261015'
POINTER=ROOT/'analysis_results/image_difficulty_full_review_20261010/CURRENT.json'
QUALITY_METRICS=['B8L2','WQ','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
TIME_METRICS=['source_time_seconds','target_matched_time_seconds']


def verify_original_scores(records,models):
    """共享JSON表默认保留10位小数，使用原单调公式计算舍入区间，不改分数。"""
    values=[records[k].to_numpy() for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
    half_unit=0.5e-10
    center=models.score(*values,params=models.B)
    lower=models.score(np.clip(values[0]-half_unit,0,1),*[v+half_unit for v in values[1:]],params=models.B)
    upper=models.score(np.clip(values[0]+half_unit,0,1),*[np.maximum(v-half_unit,0) for v in values[1:]],params=models.B)
    rounding=half_unit+8*np.spacing(100.)
    valid=(records.B8L2.to_numpy()>=lower-rounding)&(records.B8L2.to_numpy()<=upper+rounding)
    if not valid.all():
        raise ValueError('B8L2 differs from original model outside shared-table rounding interval')
    return pd.DataFrame(dict(object_id=records.object_id.to_numpy(),shared_B8L2=records.B8L2.to_numpy(),
        reconstructed_from_exported_components=center,rounding_lower=lower-rounding,rounding_upper=upper+rounding,
        center_difference=center-records.B8L2.to_numpy(),within_rounding_interval=valid))


def confirmed_relation(relation):
    if 'adoption_version' in relation:
        return relation['analysis_layer'] if relation['physical_adopted'] else 'not_explicitly_confirmed'
    explicit=any(e['physical_same_supported'] and e['review_state']=='explicit_confirmed'
                 for e in relation['evidence'])
    return (relation['tier'] if relation['tier']=='confirmed_comparable' else 'confirmed_other_scope') \
        if explicit else 'not_explicitly_confirmed'


def paired_values(a,b,metric):
    if not a.worker_id.is_unique or not b.worker_id.is_unique:
        raise ValueError('duplicate worker within image/condition')
    joined=a.set_index('worker_id')[[metric]].join(b.set_index('worker_id')[[metric]],
        how='inner',lsuffix='_a',rsuffix='_b').sort_index()
    paired=joined.dropna()
    x,y=paired[metric+'_a'],paired[metric+'_b']
    if not np.isfinite(paired.to_numpy(dtype=float)).all():
        raise ValueError('nonfinite paired observation')
    timed=metric.endswith('seconds')
    if timed and ((x<=0).any() or (y<=0).any()):
        raise ValueError('valid time must be positive seconds')
    delta=y-x
    row=dict(n_source_records_a=len(a),n_source_records_b=len(b),
        n_valid_a=int(a[metric].notna().sum()),n_valid_b=int(b[metric].notna().sum()),
        n_common_workers=len(joined),n_paired=len(paired),n_missing_common=len(joined)-len(paired),
        all_worker_mean_a=float(a[metric].mean()) if a[metric].notna().any() else None,
        all_worker_mean_b=float(b[metric].mean()) if b[metric].notna().any() else None,
        mean_a=float(x.mean()) if len(x) else None,mean_b=float(y.mean()) if len(y) else None,
        median_a=float(x.median()) if len(x) else None,median_b=float(y.median()) if len(y) else None,
        mean_delta_b_minus_a=float(delta.mean()) if len(x) else None,
        absolute_mean_gap=float(abs(x.mean()-y.mean())) if len(x) else None,
        mean_absolute_person_delta=float(abs(delta).mean()) if len(x) else None,
        sd_delta=float(delta.std(ddof=1)) if len(x)>1 else None,
        worker_spearman=correlation(x.to_numpy(),y.to_numpy()),
        geometric_time_ratio_b_over_a=float(np.exp(np.mean(np.log(y)-np.log(x)))) if timed and len(x) else None,
        mean_absolute_log_time_ratio=float(np.mean(abs(np.log(y)-np.log(x)))) if timed and len(x) else None,
        absolute_log_mean_time_gap=float(abs(np.log(y).mean()-np.log(x).mean())) if timed and len(x) else None)
    return row,paired


def metadata(bundle):
    result={}
    for im in bundle['data']['room_registry']['images']:
        result[im['image_id']]=dict(image_code=f"{im['building']}-{im['number']:02d}",building_id=im['building'])
    for im in bundle['data']['images']:
        result[im['image_id']]={k:im[k] for k in ('image_code','building_id')}
    return result


def pair_tables(records,relations,images,metrics):
    grouped={(i,c):g for (i,c),g in records.groupby(['image_id','condition'])}
    empty=records.iloc[:0]
    rows=[];people=[];coverage=[]
    for (a,b),relation in sorted(relations.items()):
        confirmed=confirmed_relation(relation)
        for condition in ['manual','semi','oos']:
            aa,bb=grouped.get((a,condition),empty),grouped.get((b,condition),empty)
            base=dict(image_a=a,image_b=b,code_a=images[a]['image_code'],code_b=images[b]['image_code'],
                building=images[a]['building_id'],condition=condition,relation=relation['tier'],
                confirmation=confirmed,candidate_ids='|'.join(relation['candidates']),
                class_a=aa.difficulty_class.iloc[0] if len(aa) else None,
                class_b=bb.difficulty_class.iloc[0] if len(bb) else None,
                current_target_a=aa.current_target_id.iloc[0] if len(aa) else None,
                current_target_b=bb.current_target_id.iloc[0] if len(bb) else None,
                target_role_a=aa.target_role.iloc[0] if len(aa) else None,
                target_role_b=bb.target_role.iloc[0] if len(bb) else None,
                pair_layer='ordinary_both' if len(aa) and len(bb) and aa.ordinary_difficulty_eligible.all()
                    and bb.ordinary_difficulty_eligible.all() else 'special_or_missing_side')
            if 'adoption_version' in relation:
                base['user_group_ids']='|'.join(relation['user_group_ids'])
            common=set(aa.worker_id)&set(bb.worker_id)
            coverage.append(dict(**base,source_n_a=len(aa),source_n_b=len(bb),common_source_n=len(common)))
            if confirmed=='not_explicitly_confirmed' or not (len(aa) or len(bb)):
                continue
            for metric in metrics:
                result,paired=paired_values(aa,bb,metric)
                rows.append(dict(**base,metric=metric,paired_workers='|'.join(paired.index),**result))
                for w,r in paired.iterrows():
                    x,y=aa.set_index('worker_id').loc[w],bb.set_index('worker_id').loc[w]
                    people.append(dict(**base,metric=metric,worker_id=w,value_a=r.iloc[0],value_b=r.iloc[1],
                        object_id_a=x.object_id,object_id_b=y.object_id,
                        reference_id_a=x.get('reference_id'),reference_id_b=y.get('reference_id'),
                        time_source_a=x.get('time_source'),time_source_b=y.get('time_source'),
                        time_source_file_a=x.get('time_source_file'),time_source_file_b=y.get('time_source_file')))
    return pd.DataFrame(rows),pd.DataFrame(people),pd.DataFrame(coverage)


def aggregate_pairs(pairs):
    rows=[]
    for minimum in [1,4]:
        subset=pairs[pairs.n_paired.ge(minimum)]
        for keys,g in subset.groupby(['condition','confirmation','building','metric','pair_layer']):
            rows.append(dict(condition=keys[0],confirmation=keys[1],building=keys[2],metric=keys[3],
                pair_layer=keys[4],
                minimum_common=minimum,pairs=len(g),paired_person_occurrences=int(g.n_paired.sum()),
                images=len(set(g.image_a)|set(g.image_b)),candidate_groups='|'.join(sorted(set(g.candidate_ids))),
                mean_gap=float(g.absolute_mean_gap.mean()),
                median_gap=float(g.absolute_mean_gap.median()),
                mean_person_absolute_delta=float(g.mean_absolute_person_delta.mean()),
                worker_rho_evaluable=int(g.worker_spearman.notna().sum()),worker_rho=float(g.worker_spearman.mean()) if g.worker_spearman.notna().any() else None,
                log_time_gap=float(g.absolute_log_mean_time_gap.mean()) if g.absolute_log_mean_time_gap.notna().any() else None))
    return pd.DataFrame(rows)


def matched_controls(records,pairs,relations,*,comparable_label='confirmed_comparable'):
    groups={(i,c):g.set_index('worker_id') for (i,c),g in records.groupby(['image_id','condition'])}
    blocks={i:information_block(i,relations) for i in records.image_id.unique()}
    selected=pairs[pairs.confirmation.eq(comparable_label) & pairs.n_paired.ge(4)&pairs.pair_layer.eq('ordinary_both')
                   & pairs.metric.isin(['B8L2','D10','WQ','IoU3D100','target_matched_time_seconds'])]
    rows=[]
    for r in selected.itertuples():
        workers=r.paired_workers.split('|')
        for source,target in [(r.image_a,r.image_b),(r.image_b,r.image_a)]:
            source_frame=groups[source,r.condition];target_frame=groups[target,r.condition]
            forbidden=blocks[source]|blocks[target]
            source_class=source_frame.difficulty_class.iloc[0]
            controls=[i for (i,c),g in groups.items() if c==r.condition and i not in forbidden
                and g.building_id.iloc[0]==r.building and g.difficulty_class.iloc[0]==source_class
                and g.ordinary_difficulty_eligible.all()
                and set(workers)<=set(g.index[g[r.metric].notna()])]
            def value(i):
                v=groups[i,r.condition].loc[workers,r.metric]
                return float(np.log(v).mean()) if r.metric.endswith('seconds') else float(v.mean())
            a,b=value(source),value(target)
            errors=[abs(value(i)-b) for i in controls]
            rows.append(dict(source=source,target=target,building=r.building,condition=r.condition,metric=r.metric,
                candidate_ids=r.candidate_ids,workers='|'.join(workers),n_common=len(workers),source_class=source_class,
                target_class=target_frame.difficulty_class.iloc[0],control_images=len(controls),control_image_ids='|'.join(controls),
                distance='absolute_log_mean_time_gap' if r.metric.endswith('seconds') else 'absolute_quality_mean_gap',
                same_room_error=abs(a-b),one_control_expected_error=float(np.mean(errors)) if errors else None))
    return pd.DataFrame(rows)


def audit_current_curves(out,shared,relations,images,difficulty):
    folder=ROOT/'research/fusion/wall_consensus_b8l2_20261016'
    if not (folder/'SUMMARY.json').exists():
        return dict(status='await_fusion_delivery',same_room_pairs=0)
    snap=read(folder/'input_snapshot.json')
    assert snap['difficulty_version']==difficulty['version'] and snap['score_version']=='WQ-B8L2-20261015'
    refs=pd.read_csv(shared/'space_reference_catalog.csv').set_index('target_id')
    from .worker_wq_integration_20261015 import geometry_equal
    scores=pd.read_csv(folder/'trajectory_scores.csv')
    registry=[]
    im_by={im['image']:im for im in snap['images']}
    for im in snap['images']:
        ref=refs.loc[im['reference']['target_id']]
        if im['reference']['full_reference_available']:
            assert geometry_equal(im['reference']['geometry'],json.loads(ref.geometry))
        rows=scores[scores.image.eq(im['image'])]
        members={m['worker_id']:m['record_id'] for m in im['members']}
        for r in rows.itertuples():
            people=r.worker_ids.split('|')
            assert len(people)==r.k and len(set(people))==r.k and set(people)<=set(members)
            assert set(r.member_record_ids.split('|'))=={members[w] for w in people}
            assert r.reference_id==im['reference']['target_id']
            assert (ROOT/r.geometry_source).exists()
        registry.append(dict(image=im['image'],image_id=im['image_id'],condition='manual',
            n_actual_members=len(members),source_pool_allowed=im['source_pool']['pool_analysis_eligible'],
            source_pool_workers=im['source_pool']['n_effective_workers'],
            members_equal_frozen=im['members_equal_frozen'],reference_id=im['reference']['target_id'],
            full_reference_available=im['reference']['full_reference_available'],use=im['use'],
            observed_states=len(rows),B8L2_states=int(rows.B8L2.notna().sum()),
            primary_states=int(rows.primary_comparison_eligible.sum()),geometry_source=im['state_source']))
    save(out,'actual_curve_images.csv',pd.DataFrame(registry))
    ids={i['image_id'] for i in snap['images']}
    pairs=[dict(image_a=a,image_b=b,confirmation=confirmed_relation(r),candidate_ids='|'.join(r['candidates']))
        for (a,b),r in relations.items() if a in ids and b in ids and confirmed_relation(r)!='not_explicitly_confirmed']
    save(out,'actual_curve_audit.json',dict(source=str(folder.relative_to(ROOT)),difficulty_version=snap['difficulty_version'],
        score_version=snap['score_version'],actual_images=len(ids),path_states=len(scores),
        worker_record_memberships_checked=True,reference_geometry_checked=True,
        geometry_sources_exist=True,direct_confirmed_pairs=pairs))
    return dict(status='actual_18_image_delivery_audited',actual_images=len(ids),path_states=len(scores),
        same_room_pairs=len(pairs),comparison='no directly confirmed same-room pair; no interpolation or cross-room substitution')


def curve_coverage(relations,images):
    original=read(ROOT/'research/fusion/wall_consensus_population_20261014/input_snapshot.json')['images']
    special=read(ROOT/'research/fusion/wall_consensus_quality_20261015/special/input_snapshot.json')['images']
    codes={i['image'] for i in original+special}
    return pd.DataFrame([dict(image_a=a,image_b=b,code_a=images[a]['image_code'],code_b=images[b]['image_code'],
        confirmation=confirmed_relation(r),relation=r['tier'],candidate_ids='|'.join(r['candidates']),
        historical_wall_a=images[a]['image_code'] in codes,historical_wall_b=images[b]['image_code'] in codes,
        interpretation='historical 12+6 actual wall geometry coverage; not accepted v6 B8L2 curve evidence')
        for (a,b),r in sorted(relations.items())])


def main(out=OUT,shared=SHARED):
    out=Path(out);shared=Path(shared);out.mkdir(parents=True,exist_ok=True)
    snapshot=read(shared/'FROZEN_INPUTS.json')
    bundle,difficulty=snapshot['bundle'],snapshot['difficulty']
    assert bundle['validation']['status']=='passed'
    assert difficulty['version']==snapshot['difficulty_pointer']['version']
    live_pointer=read(POINTER)
    images=metadata(bundle)
    relations=relation_index(bundle['data']['room_registry']['candidates'])
    pools,gates=build_pool_gate(bundle,difficulty['records'])
    inventory=pd.DataFrame(load_inventory(bundle))
    gates=pd.DataFrame(gates)
    joined=inventory.merge(gates.drop(columns=['image_id','worker_id','condition']),on='object_id',validate='one_to_one')
    selected=joined[joined.pool_analysis_eligible].copy()
    assert not selected.duplicated(['image_id','condition','worker_id']).any()
    assert selected.pool_source_workers.ge(3).all()
    labels={r['image_id']:r for r in difficulty['records']}
    selected['difficulty_class']=selected.image_id.map(lambda i:labels[i]['current_class'])
    selected['current_target_id']=selected.image_id.map(lambda i:labels[i]['target_version'])
    selected['target_role']=selected.image_id.map(lambda i:labels[i]['selected']['role'])
    selected['source_time_seconds']=selected.active_time_seconds
    columns=['object_id','image_id','image_code','building_id','worker_id','condition','pool_source_workers',
        'pool_analysis_eligible','ordinary_difficulty_eligible','difficulty_class','current_target_id','target_role',
        'source_time_seconds','time_status','time_source','time_source_file','time_rule_version','time_stage','time_binding']
    source=selected[columns].copy()
    for r in source[source.source_time_seconds.notna()].itertuples():
        assert r.time_status=='usable' and r.time_source!='lead_time_fallback' and r.time_source_file
        assert r.source_time_seconds>0
    save(out,'source_time_records.csv',source)
    save(out,'source_pool_inventory.csv',pd.DataFrame(pools))
    save(out,'direct_relations.json',[dict(image_a=a,image_b=b,confirmation=confirmed_relation(r),**r) for (a,b),r in sorted(relations.items())])
    timed,people,coverage=pair_tables(source,relations,images,['source_time_seconds'])
    save(out,'source_time_pairs.csv',timed);save(out,'source_time_people.csv',people)
    save(out,'relation_coverage.csv',coverage);save(out,'source_time_by_building.csv',aggregate_pairs(timed))
    curves=curve_coverage(relations,images);save(out,'wall_curve_coverage.csv',curves)
    summary=dict(version='same_room_b8l2_v6_20261016_v1',input_snapshot=str((shared/'FROZEN_INPUTS.json').relative_to(ROOT)),
        input_version=snapshot['version'],difficulty_version=difficulty['version'],
        current_pointer_at_run=live_pointer['version'],frozen_pointer_matches_run=live_pointer==snapshot['difficulty_pointer'],
        pool_rule=RULE_VERSION,inventory_records=len(inventory),source_records=len(source),
        source_time_records=int(source.source_time_seconds.notna().sum()),
        direct_candidates=len(relations),confirmed_comparable_relations=sum(confirmed_relation(r)=='confirmed_comparable' for r in relations.values()),
        confirmed_other_scope_relations=sum(confirmed_relation(r)=='confirmed_other_scope' for r in relations.values()),
        historical_wall_both_confirmed_pairs=int((curves.historical_wall_a&curves.historical_wall_b&curves.confirmation.ne('not_explicitly_confirmed')).sum()),
        stage='source_time_completed_quality_pending',quality_dependency=str(shared.relative_to(ROOT)),
        personnel_migration='await latest B8L2 Q/T profiles; historical WQ profiles not relabelled',
        current_wall_curve_comparison='not yet accepted; actual member/reference/geometry delivery required')
    quality_path=shared/'analysis_records.csv'
    if quality_path.exists() and (shared/'FIELD_CONTRACT.json').exists():
        shared_contract=read(shared/'FIELD_CONTRACT.json')
        assert shared_contract['snapshot_version']==snapshot['version']
        assert shared_contract['score_versions']['B8L2']=='WQ-B8L2-20261015'
        analysis=pd.read_csv(quality_path)
        assert set(analysis.object_id)==set(source.object_id), 'shared v6 source cohort differs from frozen pool gate'
        assert analysis.difficulty_version.eq(difficulty['version']).all()
        assert not analysis.duplicated(['image_id','condition','worker_id']).any()
        index=analysis.set_index('object_id').loc[source.object_id]
        for field in ['image_id','worker_id','condition','current_target_id']:
            assert list(index[field])==list(source[field]), 'shared input identity/target drift: '+field
        assert np.allclose(index.active_time_seconds,source.source_time_seconds,equal_nan=True,rtol=0,atol=1e-10)
        record=source.merge(analysis[['object_id','reference_id','current_quality_eligible','target_matched_time_seconds',
            'target_time_interpretation']+QUALITY_METRICS],on='object_id',validate='one_to_one')
        complete=record[record.B8L2.notna()]
        assert complete.current_quality_eligible.all() and complete.reference_id.eq(complete.current_target_id).all()
        binding=pd.read_csv(shared/'shared_bindings.csv').set_index('object_id').loc[complete.object_id]
        assert binding.analysis_binding_eligible.all() and binding.score_input_eligible.all()
        assert binding.chosen_target_is_current.all() and binding.person_quality_restriction_clear.all()
        assert not binding.quality_used_for_binding.any() and not binding.annotation_modified.any() and not binding.annotation_cropped.any()
        catalog=pd.read_csv(shared/'space_reference_catalog.csv').set_index('target_id')
        adopted=catalog.loc[complete.reference_id]
        assert adopted.full_reference_available.all() and adopted.is_admitted_space_candidate.all()
        audit=binding.reset_index()[['object_id','chosen_target_id','binding_status','analysis_binding_eligible',
            'score_input_eligible','person_quality_restriction_clear','quality_used_for_binding']]
        audit['full_reference_available']=adopted.full_reference_available.to_numpy()
        audit['reference_status']=adopted.status.to_numpy()
        audit['reference_version']=adopted.reference_version.to_numpy()
        save(out,'quality_binding_reference_audit.csv',audit)
        valid_time=record.target_matched_time_seconds.notna()
        assert np.allclose(record.loc[valid_time,'target_matched_time_seconds'],record.loc[valid_time,'source_time_seconds'],rtol=0,atol=1e-10)
        with scoring_engine() as (engine,models):
            parity=verify_original_scores(complete,models)
            parameters=asdict(models.B)
        save(out,'original_model_rounding_audit.csv',parity)
        save(out,'frozen_analysis_records.csv',record)
        paired,persons,cov=pair_tables(record,relations,images,QUALITY_METRICS+TIME_METRICS)
        save(out,'current_pairs.csv',paired);save(out,'current_people.csv',persons)
        save(out,'current_by_building.csv',aggregate_pairs(paired))
        joint=record.dropna(subset=['B8L2','WQ','IoU3D100','target_matched_time_seconds'])
        joint_pairs,_,_=pair_tables(joint,relations,images,['B8L2','WQ','IoU3D100','target_matched_time_seconds'])
        save(out,'joint_quality_time_pairs.csv',joint_pairs)
        group_rows=[]
        for minimum in [1,4]:
            for keys,g in paired[paired.n_paired.ge(minimum)].groupby(['condition','confirmation','candidate_ids','metric','pair_layer']):
                group_rows.append(dict(condition=keys[0],confirmation=keys[1],candidate_ids=keys[2],metric=keys[3],pair_layer=keys[4],
                    minimum_common=minimum,pairs=len(g),images=len(set(g.image_a)|set(g.image_b)),
                    paired_person_occurrences=int(g.n_paired.sum()),mean_gap=float(g.absolute_mean_gap.mean()),
                    mean_person_absolute_delta=float(g.mean_absolute_person_delta.mean())))
        save(out,'current_by_group.csv',pd.DataFrame(group_rows))
        controls=matched_controls(record,paired,relations);save(out,'matched_single_source_controls.csv',controls)
        if len(controls):
            target=controls[controls.control_images.gt(0)].groupby(['building','condition','metric','target'],as_index=False).agg(
                tasks=('source','size'),source_error=('same_room_error','mean'),control_error=('one_control_expected_error','mean'))
            save(out,'controls_by_target.csv',target)
            save(out,'controls_by_building.csv',target.groupby(['building','condition','metric'],as_index=False).agg(
                target_images=('target','nunique'),source_error=('source_error','mean'),control_error=('control_error','mean')))
        old=pd.read_csv(OLD/'quality_pairs.csv');old=old[old.layer.eq('ordinary_same_target_conditional')&old.metric.eq('WQ')&old.relation.eq('confirmed_comparable')&old.n_common.ge(4)]
        current=paired[paired.metric.eq('B8L2')&paired.confirmation.eq('confirmed_comparable')&paired.n_paired.ge(1)]
        bridge=old[['image_a','image_b','workers','n_common','reference_ids_a','reference_ids_b','absolute_gap']].rename(columns={
            'workers':'historical_workers','n_common':'historical_n_common','reference_ids_a':'historical_reference_a',
            'reference_ids_b':'historical_reference_b','absolute_gap':'historical_WQ_mean_gap'}).merge(
            current[['image_a','image_b','condition','paired_workers','n_paired','absolute_mean_gap']],on=['image_a','image_b'],how='outer',indicator=True)
        bridge['same_worker_set']=bridge.historical_workers.fillna('').eq(bridge.paired_workers.fillna(''))
        ref_by=complete.groupby(['image_id','condition']).reference_id.agg(lambda s:'|'.join(sorted(s.unique()))).to_dict()
        bridge['current_reference_a']=[ref_by.get((r.image_a,r.condition)) for r in bridge.itertuples()]
        bridge['current_reference_b']=[ref_by.get((r.image_b,r.condition)) for r in bridge.itertuples()]
        bridge['same_reference_ids']=(bridge.historical_reference_a.eq(bridge.current_reference_a)&bridge.historical_reference_b.eq(bridge.current_reference_b))
        bridge['interpretation']='membership and reference-ID bridge; changed IDs do not by themselves prove changed geometry'
        save(out,'historical_23_pair_membership_bridge.csv',bridge)
        old_v4=pd.read_csv(ROOT/'research/statistics/b8l2_mainline_status_20261016/same_room.csv')
        old_v4=old_v4[old_v4.n_common_scored_workers.ge(1)].copy()
        old_v4['v4_workers']=old_v4.common_worker_ids.str.replace(';','|',regex=False)
        bridge_v4=old_v4[['image_a','image_b','condition','n_common_scored_workers','v4_workers']].merge(
            current[['image_a','image_b','condition','n_paired','paired_workers']],on=['image_a','image_b','condition'],how='outer',indicator=True)
        bridge_v4['same_worker_set']=bridge_v4.v4_workers.fillna('').eq(bridge_v4.paired_workers.fillna(''))
        save(out,'v4_27_pair_membership_bridge.csv',bridge_v4)
        v4=pd.read_csv(ROOT/'research/statistics/b8l2_mainline_status_20261016/quality_records.csv')
        bridge_records=v4[['object_id','reference_id','difficulty_class','B8L2','WQ']].merge(
            complete[['object_id','reference_id','difficulty_class','B8L2','WQ']],on='object_id',how='outer',suffixes=('_v4','_v6'),indicator=True)
        save(out,'v4_v6_quality_membership_bridge.csv',bridge_records)
        swap=paired[paired.metric.isin(['B8L2','WQ','IoU3D100'])].copy()
        save(out,'same_input_metric_swap_pairs.csv',swap)
        save(out,'score_parameters.json',parameters)
        summary.update(stage='quality_and_source_time_completed',quality_records=len(complete),
            quality_images=int(complete.image_id.nunique()),same_target_quality_time_records=int(complete.target_matched_time_seconds.notna().sum()),
            current_binding_and_full_reference_audited=True,
            original_formula_rounding_interval_passed=True,
            max_score_reconstruction_center_error=float(parity.center_difference.abs().max()),
            historical_23_pairs_retained=int(bridge._merge.eq('both').sum()),
            historical_v4_27_pairs_retained=int(bridge_v4._merge.eq('both').sum()),
            added_pairs_relative_to_v4=int(bridge_v4._merge.eq('right_only').sum()),
            score_version=parameters['version'],model_parameters=parameters,
            current_quality_pair_counts={condition:dict(any_common=int(g.n_paired.ge(1).sum()),common_ge4=int(g.n_paired.ge(4).sum()))
                for condition,g in current.groupby('condition')})
        plot(out,paired)
        summary['current_wall_curve_comparison']=audit_current_curves(out,shared,relations,images,difficulty)
        available=read(ROOT/'research/fusion/wall_consensus_b8l2_20261016/input_snapshot.json') if summary['current_wall_curve_comparison']['status']!='await_fusion_delivery' else dict(images=[])
        curve_ids={i['image_id'] for i in available['images']}
        candidate=[]
        for r in current[current.condition.eq('manual')&current.pair_layer.eq('ordinary_both')&current.n_paired.ge(4)].itertuples():
            workers=r.paired_workers.split('|')
            aa=record[record.image_id.eq(r.image_a)&record.condition.eq(r.condition)].set_index('worker_id')
            bb=record[record.image_id.eq(r.image_b)&record.condition.eq(r.condition)].set_index('worker_id')
            candidate.append(dict(image_a=r.image_a,image_b=r.image_b,code_a=r.code_a,code_b=r.code_b,
                candidate_ids=r.candidate_ids,n_common=r.n_paired,workers=r.paired_workers,
                reference_id_a=r.current_target_a,reference_id_b=r.current_target_b,
                object_ids_a='|'.join(aa.loc[workers,'object_id']),object_ids_b='|'.join(bb.loc[workers,'object_id']),
                existing_curve_a=r.image_a in curve_ids,existing_curve_b=r.image_b in curve_ids,
                missing_curve_views=2-int(r.image_a in curve_ids)-int(r.image_b in curve_ids),
                interpretation='pre-score role/member coverage only; new fusion and same-reference scoring still required'))
        candidates=pd.DataFrame(candidate).sort_values(['missing_curve_views','n_common','code_a','code_b'],ascending=[True,False,True,True])
        save(out,'missing_curve_pair_candidates.csv',candidates)
    save(out,'SUMMARY.json',summary)
    save(out,'FIELD_CONTRACT.json',dict(version=summary['version'],
        table_columns={p.name:list(pd.read_csv(p,nrows=0).columns) for p in sorted(out.glob('*.csv'))},
        pairing='same condition, identical real workers on both views for each metric; pool >=3 does not require paired overlap >=3',
        confirmation='direct physical_same_supported + explicit_confirmed only; scope-comparable primary and confirmed other-scope separated',
        times='seconds, usable frozen active_time only; source time does not become new target time; no lead_time fallback or missing=0',
        metrics='original B8L2 plus WQ and same-reference IoU3D100; all rows retain own specified reference, no highest-score target',
        differences='absolute gap of paired means and mean absolute individual differences are separate; time ratios use positive paired seconds',
        controls='one source image each time; same workers/condition/source grade; outside all recorded candidate blocks; no-evidence controls are not confirmed other rooms',
        history='v4 891 and historical 23 pairs retained as separate cohorts; metric swap only within current shared rows',
        curves='historical coverage only until a current B8L2 member/geometry/reference input is accepted; no interpolation or Lee substitution'))
    save(out,'CATALOG_ENTRY_PENDING.json',dict(path=str(out.relative_to(ROOT)),topic='same_room',entrypoint=str((out/'README.md').relative_to(ROOT)),
        title='同房原版B8L2与时间：冻结v6',version=summary['version'],adoption='module actual analysis; original B8L2 parameters',
        registration_owner='data/statistics thread; do not concurrently overwrite global catalog',
        dependencies=[str(shared.relative_to(ROOT)),'latest B8L2 Q/T profiles','actual current wall trajectories']))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def plot(out,pairs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for ax,metric in zip(axes,['B8L2','IoU3D100','target_matched_time_seconds']):
        selected=pairs[pairs.confirmation.eq('confirmed_comparable')&pairs.condition.eq('manual')&pairs.metric.eq(metric)
            &pairs.pair_layer.eq('ordinary_both')&pairs.n_paired.ge(4)]
        for building,g in selected.groupby('building'):
            ax.scatter(g.mean_a,g.mean_b,label=building[:3])
        title={'B8L2':'B8L2质量分（0—100）','IoU3D100':'同参考3D IoU（%）',
               'target_matched_time_seconds':'当前目标可比耗时（秒）'}[metric]
        ax.set(xlabel='视角A：共同人员均值',ylabel='视角B：共同人员均值',title=title)
        if metric.endswith('seconds'):
            ax.set_xscale('log');ax.set_yscale('log')
            if len(selected):
                lower=min(selected.mean_a.min(),selected.mean_b.min())/1.1
                upper=max(selected.mean_a.max(),selected.mean_b.max())*1.1
                ax.plot([lower,upper],[lower,upper],color='gray',lw=.7)
                ax.set(xlim=(lower,upper),ylim=(lower,upper))
                from matplotlib.ticker import StrMethodFormatter, NullFormatter
                ax.xaxis.set_major_formatter(StrMethodFormatter('{x:.0f}'))
                ax.yaxis.set_major_formatter(StrMethodFormatter('{x:.0f}'))
                ax.xaxis.set_minor_formatter(NullFormatter());ax.yaxis.set_minor_formatter(NullFormatter())
                ticks=[v for v in [150,175,200,225,250] if lower<v<upper]
                ax.set_xticks(ticks);ax.set_yticks(ticks)
        else:
            ax.set(xlim=(0,100),ylim=(0,100));ax.plot([0,100],[0,100],color='gray',lw=.7)
        ax.legend(fontsize=7)
    fig.suptitle('直接确认且既有范围可比；同条件共同人员≥4；图对非独立样本')
    fig.savefig(out/'same_room_quality_time.png',dpi=150);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--shared',type=Path,default=SHARED)
    args=parser.parse_args();main(args.out,args.shared)
