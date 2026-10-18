"""数据v2基础统计、直接关系及原答分歧；不生成新融合或新正式人员分。"""
import ast
import gzip
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from .b8l2_detail_summary_20261016 import distribution
from .same_room_b8l2_20261016 import paired_values
from .same_room_v1_process_20261017 import balanced_gap
from .difficulty_coarse_closeout_20261014 import floor
from .wall_consensus_population_20261014 import footprint
from .v2_evidence_audit_20261019 import public_value
from ..data_prep.consolidate_research_input import load_current_bundle

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/statistics/v2_integrated_analysis_20261019'
MANIFEST=ROOT/'research/data/releases/v2/analysis_input/manifest.json'
CROSS=ROOT/'research/quality/quality_workers_v2_20261019/CROSS_MODULE_INPUTS.json'
EVIDENCE=ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
CONTEXT=OUT/'REPRO_CONTEXT.json.gz'
VERSION='v2_integrated_statistics_20261019_r1'
QUALITY=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
    'height_mean_ratio','iou_3d_corner_mean']
TIMES=['source_active_time_seconds','target_matched_time_seconds']


def read(path):
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item()),encoding='utf-8')
    temporary.replace(path)


def summarize(d):
    assert d.object_id.is_unique and d.condition.nunique()<=1
    assert d.B8L2.notna().equals(d.D10.notna()) and d.B8L2.notna().equals(d.quality_usable)
    q=d[d.quality_usable]
    result=dict(n_inventory=len(d),n_images=d.image_id.nunique(),n_workers=d.worker_id.nunique(),
        n_buildings=d.building_id.nunique(),n_retained=int(d.cleaning_disposition.eq('retained').sum()),
        n_independent=int(d.source_pool_eligible.sum()),n_source=int(d.pool_analysis_eligible.sum()),
        n_source_excluded=int((~d.pool_analysis_eligible).sum()),n_quality=len(q),
        n_quality_images=q.image_id.nunique(),n_quality_workers=q.worker_id.nunique(),
        n_quality_missing=len(d)-len(q),n_quality_difficulty_aligned=int(q.difficulty_reference_match.sum()))
    for name in QUALITY:
        if name not in d:continue
        v=q[name]
        result.update({name+'_'+k:n for k,n in distribution(v).items()})
        result[name+'_q10']=v.quantile(.1) if v.notna().any() else None
        result[name+'_image_equal_mean']=q.groupby('image_id')[name].mean().mean() if len(q) else None
    for name,label in zip(TIMES,['source','target']):
        v=d[name]
        result.update({label+'_time_'+k:n for k,n in distribution(v).items()})
        result[label+'_time_missing']=int(v.isna().sum())
        result[label+'_time_q90']=v.quantile(.9) if v.notna().any() else None
        joint=q[q[name].notna()]
        result['quality_'+label+'_time_n']=len(joint)
        result['quality_'+label+'_time_images']=joint.image_id.nunique()
        result['quality_'+label+'_time_B8L2_mean']=joint.B8L2.mean() if len(joint) else None
        result['quality_'+label+'_time_seconds_mean']=joint[name].mean() if len(joint) else None
    return result


def grouped(d,keys):
    assert 'condition' in keys and not d.duplicated(keys+['object_id']).any()
    d=d.copy()
    for column in [c for c in QUALITY+TIMES if c in d]:d[column]=pd.to_numeric(d[column],errors='raise')
    g=d.groupby(keys,dropna=False,sort=True);q=d[d.quality_usable]
    result=g.agg(n_inventory=('object_id','size'),n_images=('image_id','nunique'),
        n_workers=('worker_id','nunique'),n_buildings=('building_id','nunique'),
        n_independent=('source_pool_eligible','sum'),n_source=('pool_analysis_eligible','sum'))
    flags=d.assign(_retained=d.cleaning_disposition.eq('retained'))
    result['n_retained']=flags.groupby(keys,dropna=False)._retained.sum()
    qg=q.groupby(keys,dropna=False)
    counts=qg.agg(n_quality=('object_id','size'),n_quality_images=('image_id','nunique'),
        n_quality_workers=('worker_id','nunique'),n_quality_buildings=('building_id','nunique'),
        n_quality_difficulty_aligned=('difficulty_reference_match','sum'))
    result=result.join(counts)
    for c in counts:result[c]=result[c].fillna(0).astype(int)
    result['n_source_excluded']=result.n_inventory-result.n_source
    result['n_cleaning_removed']=result.n_inventory-result.n_retained
    result['cleaning_removed_rate']=result.n_cleaning_removed/result.n_inventory
    result['source_excluded_rate']=result.n_source_excluded/result.n_inventory
    result['quality_usable_rate']=result.n_quality/result.n_inventory
    result['n_quality_missing']=result.n_inventory-result.n_quality
    result['n_quality_missing_in_source']=result.n_source-result.n_quality

    def add_stats(group,column,prefix,quantiles):
        nonlocal result
        agg=group[column].agg(['count','mean','median','std']).rename(columns={'count':'n','std':'sd'})
        for label,fraction in quantiles:agg[label]=group[column].quantile(fraction)
        agg=agg.add_prefix(prefix+'_');result=result.join(agg)
        result[prefix+'_n']=result[prefix+'_n'].fillna(0).astype(int)
    for name in QUALITY:
        if name not in d:continue
        add_stats(qg,name,name,[('q10',.1),('q25',.25),('q75',.75)])
        if 'image_id' in keys:result[name+'_image_equal_mean']=result[name+'_mean']
        else:
            by_image=q.groupby(keys+['image_id'],dropna=False)[name].mean()
            result[name+'_image_equal_mean']=by_image.groupby(level=keys,dropna=False).mean()
    for name,label in zip(TIMES,['source','target']):
        add_stats(g,name,label+'_time',[('q25',.25),('q75',.75),('q90',.9)])
        result[label+'_time_missing']=result.n_inventory-result[label+'_time_n']
        common=q[q[name].notna()].groupby(keys,dropna=False)
        joint=common.agg(**{'quality_'+label+'_time_n':('object_id','size'),
            'quality_'+label+'_time_images':('image_id','nunique'),
            'quality_'+label+'_time_B8L2_mean':('B8L2','mean'),
            'quality_'+label+'_time_seconds_mean':(name,'mean')})
        result=result.join(joint)
        for suffix in ['n','images']:result['quality_'+label+'_time_'+suffix]=result['quality_'+label+'_time_'+suffix].fillna(0).astype(int)
    return result.reset_index()


def contextual_quality(records):
    d=records.copy()
    keys=['image_id','condition','chosen_target_id','reference_version']
    q=d.quality_usable & d.chosen_target_id.notna()
    for metric in ['B8L2','D10']:
        g=d.loc[q].groupby(keys,dropna=False)[metric]
        n=g.transform('size');total=g.transform('sum');rank=g.rank(method='average')
        d.loc[q,metric+'_peer_n']=n-1
        d.loc[q,metric+'_peer_mean']=(total-d.loc[q,metric])/(n-1).replace(0,np.nan)
        d.loc[q,metric+'_peer_residual']=d.loc[q,metric]-d.loc[q,metric+'_peer_mean']
        d.loc[q,metric+'_rank_percentile']=100*(rank-1)/(n-1).replace(0,np.nan)
    if 'time_source_kind' in d:
        timed=d.pool_analysis_eligible&d.source_active_time_seconds.gt(0)&d.chosen_target_id.notna()
        time_keys=keys+['origin','time_source_kind']
        logtime=np.log(d.loc[timed,'source_active_time_seconds'])
        frame=d.loc[timed,time_keys].assign(log_time=logtime)
        tg=frame.groupby(time_keys,dropna=False).log_time
        n=tg.transform('size');total=tg.transform('sum')
        d.loc[timed,'source_log_time_peer_n']=n-1
        d.loc[timed,'source_log_time_peer_residual']=logtime-(total-logtime)/(n-1).replace(0,np.nan)
    return d


def validate_evidence_join(records,evidence):
    assert evidence.object_id.is_unique and set(evidence.object_id)==set(records.object_id)
    a,b=records.set_index('object_id'),evidence.set_index('object_id')
    for field in ['worker_id','image_id']:
        if field in b:assert a[field].equals(b.loc[a.index,field]),field


def pair_analysis(records,relations):
    r=records[records.pool_analysis_eligible].copy()
    if r.duplicated(['image_id','condition','worker_id']).any():raise ValueError('duplicate source worker within image/condition')
    cells={(i,c):g for (i,c),g in r.groupby(['image_id','condition'])}
    empty=r.iloc[:0];pairs=[];people=[]
    metrics=[m for m in ['B8L2','D10','IoU3D100']+TIMES if m in r]
    for relation in relations:
        a,b=relation['image_a'],relation['image_b']
        for condition in sorted(records.condition.unique()):
            aa,bb=cells.get((a,condition),empty),cells.get((b,condition),empty)
            base=dict(image_a=a,image_b=b,condition=condition,relation=relation['tier'],
                physical_adopted=relation['physical_adopted'],scope_comparable=relation['scope_comparable'],
                substantive_conflict=relation['substantive_conflict'],
                building=a.split('_')[0],user_group_ids='|'.join(relation['user_group_ids']))
            for panel in ['own_references','current_image_targets_only']:
                x,y=aa.copy(),bb.copy()
                for z in [x,y]:
                    for metric in ['B8L2','D10','IoU3D100']:
                        if metric in z:z.loc[~z.quality_usable,metric]=np.nan
                    if panel=='current_image_targets_only':
                        z.loc[z.chosen_target_id.ne(z.current_target_id),metrics]=np.nan
                indexed_a,indexed_b=x.set_index('worker_id'),y.set_index('worker_id')
                for metric in metrics:
                    summary,common=paired_values(x,y,metric)
                    pairs.append(dict(**base,scope_panel=panel,metric=metric,**summary))
                    for worker,row in common.iterrows():
                        source_a=indexed_a.loc[worker];source_b=indexed_b.loc[worker]
                        people.append(dict(**base,scope_panel=panel,metric=metric,worker_id=worker,
                            object_id_a=source_a.object_id,object_id_b=source_b.object_id,
                            reference_id_a=source_a.get('reference_id'),reference_id_b=source_b.get('reference_id'),
                            value_a=row.iloc[0],value_b=row.iloc[1],delta_b_minus_a=row.iloc[1]-row.iloc[0]))
    return pd.DataFrame(pairs),pd.DataFrame(people)


def load_records():
    if CONTEXT.is_file():
        context=read(CONTEXT);cross=context['score_interface'];bundle=context['bundle']
        d=pd.DataFrame(context['quality_inventory']);bindings=context['bindings']
        difficulty=context['difficulty'];refs=context['references'];measures=context['measurements']
    else:
        cross=read(CROSS);bundle=load_current_bundle(MANIFEST)
        d=pd.read_csv(ROOT/cross['full_inventory_with_metric_eligibility'].replace('\\','/'),low_memory=False)
        bindings=read(ROOT/cross['all_pre_score_bindings'].replace('\\','/').replace('.csv','.json'))
        difficulty=read(ROOT/cross['difficulty_records'].replace('\\','/'))
        refs=read(ROOT/cross['reference_catalog'].replace('\\','/'))
        measures=[json.loads(line)['result'] for line in (CROSS.parent/'measurements.jsonl').open(encoding='utf-8') if line.strip()]
        object_fields=['object_id','object_kind','points_1024x512','links_zero_based','source','scene_doorway_status',
            'ring_confirmed','order_status','independent_vote_eligible','pairing_basis','preprocessing','repair_evidence',
            'deleted_previous_point_indices','original_export_points','trap_status','model_edit_status','final_review','review_evidence']
        minimal_objects=[{k:o[k] for k in object_fields if k in o} for o in bundle['data']['objects'] if o['object_kind']=='annotation']
        needed_metrics=['object_id']+QUALITY+['WQ','A10']
        context=dict(schema='v2_statistics_exact_source_columns_v1',data_release='v2',
            source_manifest=MANIFEST.relative_to(ROOT).as_posix(),score_interface=cross,
            quality_inventory=d.astype(object).where(d.notna(),None).to_dict('records'),
            bundle=dict(data=dict(objects=minimal_objects)),bindings=bindings,difficulty=difficulty,references=refs,
            measurements=[{k:m[k] for k in needed_metrics if k in m} for m in measures],
            purpose='repository-contained replay of this statistics revision; formal truth remains v2 manifest; no new scoring')
        OUT.mkdir(parents=True,exist_ok=True);temporary=OUT/'REPRO_CONTEXT.pending.gz'
        with gzip.open(temporary,'wt',encoding='utf-8') as stream:json.dump(public_value(context),stream,ensure_ascii=False,allow_nan=False)
        temporary.replace(CONTEXT)
    assert cross['data_release']=='v2' and cross['n1_applied'] is False
    objects={o['object_id']:o for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    assert d.object_id.is_unique and set(d.object_id)==set(objects)
    assert len(d)==cross['counts']['inventory'] and d.quality_usable.sum()==cross['counts']['quality_rows']
    assert d.B8L2.notna().equals(d.quality_usable) and d.D10.notna().equals(d.quality_usable)
    assert not (d.quality_usable&d.is_oos).any()
    binding_by={b['object_id']:b for b in bindings};assert set(binding_by)==set(objects)
    diff={v['image_id']:v for v in difficulty};ref_by={r['target_id']:r for r in refs}
    assert len(ref_by)==len(refs)
    measured=pd.DataFrame(measures).set_index('object_id');assert measured.index.is_unique
    for metric in ['IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean']:
        d['diagnostic_'+metric]=d.object_id.map(measured[metric])
        d[metric]=d['diagnostic_'+metric].where(d.quality_usable)
    for metric in ['WQ','A10']:
        d['legacy_formula_'+metric+'_same_measurement']=d.object_id.map(measured[metric]).where(d.quality_usable)
    details=[]
    for row in d.to_dict('records'):
        oid=row['object_id'];obj=objects[oid];image=diff[row['image_id']];binding=binding_by[oid]
        pts=obj['points_1024x512'];links=obj['links_zero_based']
        source=obj['source'];ref=ref_by.get(row['chosen_target_id'])
        details.append(dict(object_id=oid,difficulty_class=image['current_class'],
            difficulty_reference_match=row['chosen_target_id']==image['target_version'],
            difficulty_target_relation='current_image_target' if row['chosen_target_id']==image['target_version'] else 'other_or_unbound',
            current_target_id=image['target_version'],doorway_status=obj['scene_doorway_status'],
            is_doorway=('doorway' in row['scene']),oos_subtype=row['image_oos_subtype'],
            pair_count=len(links) if links is not None else None,point_count=len(pts) if pts is not None else None,
            ring_confirmed=obj['ring_confirmed'],order_status=obj['order_status'],
            independent_vote_eligible=obj['independent_vote_eligible'],
            pairing_basis=obj['pairing_basis'],preprocessing_record=obj['preprocessing'],
            repair_evidence=obj['repair_evidence'],deleted_previous_point_indices=obj.get('deleted_previous_point_indices'),
            deleted_point_record_available='deleted_previous_point_indices' in obj,
            annotation_points=pts,original_export_points=obj['original_export_points'],
            annotation_source=source,source_project=source['project'],
            reference_points=ref['points_1024x512'] if ref else None,
            reference_full_available=ref['full_reference_available'] if ref else False,
            allowed_target_ids=binding['allowed_target_ids'],binding_evidence=binding,
            trap_status=obj['trap_status'],model_edit_status=obj['model_edit_status'],
            final_review=obj['final_review'],review_evidence=obj['review_evidence'],
            data_release='v2',score_version=cross['version'],analysis_revision=VERSION))
    d=d.merge(pd.DataFrame(details),on='object_id',validate='one_to_one')
    old=pd.read_csv(ROOT/'research/statistics/b8l2_d10_statistics_20261017/record_lookup.csv',low_memory=False).set_index('object_id')
    d['target_matched_time_seconds']=d.object_id.map(old.target_matched_time_seconds)
    d['target_time_status']=np.where(d.target_matched_time_seconds.notna(),'inherited_verified_v1_target_time','not_collected_or_not_target_attributed')
    d['source_time_status']=np.where(d.source_active_time_seconds.notna(),'source_task_time_available','source_task_time_missing')
    evidence_status='not_received'
    if EVIDENCE.is_file():
        evidence=pd.DataFrame(read(EVIDENCE)['records']);validate_evidence_join(d,evidence)
        ev=evidence.set_index('object_id');matched=ev.loc[d.object_id]
        for field in ['B8L2','D10','source_active_time_seconds']:
            assert np.allclose(d[field].to_numpy(float),matched[field].to_numpy(float),rtol=0,atol=1e-10,equal_nan=True),field
        d['target_matched_time_seconds']=d.object_id.map(ev.target_matched_time_seconds)
        for field in ['time_evidence','scope_evidence','semi_evidence','exclusion_attribution','calculation_class',
            'diagnostic_floor_iou','raw_original_available','fusion_or_cluster_membership_status']:
            d[field]=d.object_id.map(ev[field])
        d['time_source_kind']=d.time_evidence.map(lambda x:x['source_kind'])
        d['source_time_status']=d.time_evidence.map(lambda x:x['source_status'])
        d['target_time_status']=d.time_evidence.map(lambda x:x['target_missing_reason'] or 'verified_target_time')
        d['evidence_pointer']=d.object_id.map(lambda x:'research/statistics/v2_evidence_audit_20261019/records.json.gz#object_id='+x)
        d['scope_opportunity']=d.scope_evidence.map(lambda x:x['judgement_opportunity'])
        d['scope_correct']=d.scope_evidence.map(lambda x:x['correct'])
        d['scope_response']=d.scope_evidence.map(lambda x:x['response'])
        d['semi_exact_initialization']=d.semi_evidence.map(lambda x:x['exact_initialization_bound'])
        d['semi_confirmed_error_opportunity']=d.semi_evidence.map(lambda x:x['confirmed_error_opportunity'])
        d['semi_reported_error_opportunity']=d.semi_evidence.map(lambda x:x['reported_error_opportunity'])
        d['semi_known_error_unchanged']=d.semi_evidence.map(lambda x:x.get('known_error_unchanged'))
        d['semi_reported_known_error_unchanged']=d.semi_evidence.map(lambda x:x.get('reported_known_error_unchanged'))
        d['semi_current_gain_available']=d.semi_evidence.map(lambda x:x.get('current_qualified_gain_available',False))
        for metric in ['B8L2','D10','IoU3D100']:
            d['semi_initial_'+metric]=d.semi_evidence.map(lambda x:(x.get('current_initial_scores') or {}).get(metric))
            d['semi_project_gain_'+metric]=d.semi_evidence.map(lambda x:(x.get('current_project_gain') or {}).get(metric))
            d['semi_worker_gain_'+metric]=d.semi_evidence.map(lambda x:(x.get('current_worker_attributable_gain') or {}).get(metric))
        evidence_status='joined_by_object_id'
    d['scene_bucket']=np.select([d.is_doorway&d.is_oos,d.is_doorway,d.is_oos],
        ['doorway_and_oos','doorway_only','oos_only'],default='neither_flagged')
    return contextual_quality(d),bundle,objects,refs,bindings,evidence_status


def room_tables(records):
    source=ROOT/'research/same_room/relation_adoption_20261016'
    relations=read(source/'relations.json');groups=read(source/'original_groups.json')
    candidates=read(source/'candidate_adoption.json')
    memberships=[];registry=[]
    for kind,items,idfield in [('original',groups,'review_code'),('candidate',candidates,'candidate_id')]:
        for group in items:
            gid=kind+':'+group[idfield];ids=group['image_ids']
            registry.append(dict(group_id=gid,group_kind=kind,image_ids=ids,
                n_declared_views=len(ids),n_inventory_views=len(set(ids)&set(records.image_id)),
                classification=group.get('raw_current',group),identity_basis='existing_user_group_not_building'))
            memberships.extend(dict(group_id=gid,group_kind=kind,image_id=i) for i in ids)
    membership=pd.DataFrame(memberships);assert not membership.duplicated(['group_id','image_id']).any()
    expanded=membership.merge(records,on='image_id',validate='many_to_many')
    tables=dict(room_registry=pd.DataFrame(registry),room_memberships=membership,
        room_group_summary=grouped(expanded,['group_id','group_kind','condition']),
        room_worker_summary=grouped(expanded,['group_id','group_kind','worker_id','condition']),
        room_view_summary=grouped(expanded,['group_id','group_kind','image_id','condition']),
        direct_relation_registry=pd.DataFrame(relations))
    tables['room_view_worker_matrix']=expanded[['group_id','group_kind','image_id','worker_id','condition',
        'object_id','chosen_target_id','quality_usable','B8L2','D10']+TIMES]
    pairs,people=pair_analysis(records,relations)
    pairs['cancellation_fraction']=1-pairs.absolute_mean_gap/pairs.mean_absolute_person_delta.replace(0,np.nan)
    tables.update(direct_pair_summary=pairs,direct_pair_people=people)
    weights=[]
    for minimum in [1,4]:
        valid=pairs[pairs.physical_adopted & pairs.scope_comparable & ~pairs.substantive_conflict & pairs.n_paired.ge(minimum)]
        for keys,g in valid.groupby(['condition','metric','scope_panel']):
            expanded_groups=g.assign(user_group_ids=g.user_group_ids.str.split('|')).explode('user_group_ids')
            summary=balanced_gap(expanded_groups)
            summary.update(pairs=len(g),pair_equal_gap=float(g.absolute_mean_gap.mean()),
                pair_group_membership_occurrences=len(expanded_groups),group_definition='individual_original_user_group; overlap_explicit')
            weights.append(dict(zip(['condition','metric','scope_panel'],keys),minimum_common=minimum,**summary))
    tables['room_weighting_sensitivity']=pd.DataFrame(weights)
    tables['room_unlinked_images']=records.loc[~records.image_id.isin(membership.image_id),['image_id','image_code','building_id']].drop_duplicates()
    return tables


def raw_disagreement(records,objects):
    source=records[records.pool_analysis_eligible]
    polygons={};status=[]
    for r in source.itertuples():
        points=objects[r.object_id]['points_1024x512']
        pts=np.asarray(points,dtype=float) if points is not None else np.empty((0,2))
        reason=None
        if points is None:reason='prepared_coordinates_missing'
        elif len(pts)<6 or len(pts)%2:reason='fewer_than_three_pairs_or_unpaired'
        elif not np.isfinite(pts).all() or not (pts[1::2,1]>256).all():reason='floor_ray_unavailable'
        elif not ((pts[1::2,0]>=0)&(pts[1::2,0]<1024)&(pts[1::2,1]<512)).all():reason='floor_point_outside_continuous_canvas'
        else:
            poly=footprint(floor(pts))
            if poly is None:reason='invalid_declared_floor_polygon'
            else:polygons[r.object_id]=poly
        status.append(dict(object_id=r.object_id,image_id=r.image_id,condition=r.condition,
            floor_available=reason is None,unavailable_reason=reason))
    pairs=[]
    for (image,condition),group in source.groupby(['image_id','condition']):
        rows=group.to_dict('records')
        for a,b in combinations(rows,2):
            pa,pb=polygons.get(a['object_id']),polygons.get(b['object_id'])
            valid=pa is not None and pb is not None
            area=pa.symmetric_difference(pb).area if valid else None
            count_known=pd.notna(a['pair_count']) and pd.notna(b['pair_count'])
            same_count=a['pair_count']==b['pair_count'] if count_known else None
            ta,tb=a['chosen_target_id'],b['chosen_target_id']
            target='at_least_one_unbound' if pd.isna(ta) or pd.isna(tb) else 'same_known' if ta==tb else 'different_known'
            pairs.append(dict(image_id=image,condition=condition,object_id_a=a['object_id'],object_id_b=b['object_id'],
                worker_id_a=a['worker_id'],worker_id_b=b['worker_id'],target_relation=target,
                pair_count_a=a['pair_count'],pair_count_b=b['pair_count'],
                same_pair_count=same_count,floor_pair_measurable=valid,
                R_union_normalized=area/pa.union(pb).area if valid else None,
                R_symdiff_h2=area,
                structural_correspondence_distance=None,
                structural_status='pair_count_unavailable' if not count_known else 'not_run_same_count' if same_count else 'different_count_not_computed'))
    p=pd.DataFrame(pairs);summary=[]
    for keys,g in p.groupby(['image_id','condition','target_relation']):
        v=g.R_union_normalized
        summary.append(dict(zip(['image_id','condition','target_relation'],keys),possible_pairs=len(g),
            measurable_pairs=int(g.floor_pair_measurable.sum()),unmeasurable_pairs=int((~g.floor_pair_measurable).sum()),
            different_pair_count_pairs=int(g.same_pair_count.eq(False).sum()),unknown_pair_count_pairs=int(g.same_pair_count.isna().sum()),
            **{'R_'+k:v for k,v in distribution(v).items()}))
    return dict(raw_floor_record_status=pd.DataFrame(status),raw_answer_pairs=p,raw_disagreement_summary=pd.DataFrame(summary))


def base_tables(records,refs):
    d=records
    axes={
        'condition_summary':['condition'],
        'cohort_condition_summary':['origin','condition'],
        'image_inventory':['image_id','image_code','condition'],
        'worker_inventory':['worker_id','condition'],
        'difficulty_scene_condition':['difficulty_class','scene_bucket','condition','difficulty_target_relation'],
        'worker_difficulty':['worker_id','difficulty_class','condition','difficulty_target_relation'],
        'worker_scene':['worker_id','scene_bucket','condition'],
        'image_target':['image_id','image_code','chosen_target_id','condition'],
        'worker_calculation':['worker_id','condition','score_status'],
        'scene_calculation':['scene_bucket','condition','score_status'],
        'worker_quality_use':['worker_id','condition','quality_use'],
    }
    tables={name:grouped(d,keys) for name,keys in axes.items()}
    tables['shared_records']=d
    tables['image_worker_matrix']=d[['object_id','image_id','image_code','worker_id','condition','chosen_target_id',
        'quality_usable','B8L2','D10']+TIMES+['B8L2_peer_residual','B8L2_rank_percentile']]
    tables['point_structure_distribution']=d.groupby(['image_id','condition','pair_count','geometry_status'],dropna=False).agg(
        records=('object_id','size'),workers=('worker_id','nunique')).reset_index()
    response='scope_response' if 'scope_response' in d else 'worker_scope_response'
    tables['scope_choice_distribution']=d.groupby(['worker_id','condition',response],dropna=False).size().reset_index(name='records')
    tables['binding_distribution']=d.groupby(['image_id','condition','binding_status'],dropna=False).size().reset_index(name='records')
    tables['calculation_coverage']=d.groupby(['condition','origin','geometry_status','full_score_state','quality_use'],dropna=False).size().reset_index(name='records')
    tables['independent_pool_inventory']=d.groupby(['image_id','image_code','condition'],dropna=False).agg(
        inventory=('object_id','size'),raw_workers=('worker_id','nunique'),
        independent_workers=('source_pool_eligible','sum'),source_workers=('pool_analysis_eligible','sum'),
        quality_records=('quality_usable','sum'),declared_target_ids=('chosen_target_id','nunique')).reset_index()
    pools=tables['independent_pool_inventory']
    pools['low_people_pool']=pools.independent_workers.between(1,2)
    pools['v2_fusion_run']=False
    pools['candidate_for_future_fusion']=pools.source_workers.ge(3)
    pools['candidate_does_not_grant_quality_or_homogeneous_scope']=True
    targets=d[d.pool_analysis_eligible].groupby(['image_id','condition','chosen_target_id'],dropna=False).agg(
        source_workers=('worker_id','nunique'),quality_records=('quality_usable','sum')).reset_index()
    targets['feasible_min3_same_target_quality_panel']=targets.source_workers.ge(3)&targets.quality_records.ge(3)&targets.chosen_target_id.notna()
    targets['fusion_experiment_run']=False
    tables['target_pool_inventory']=targets
    tables['image_reference_registry']=pd.DataFrame([dict(image_id=r['image_id'],target_id=r['target_id'],
        reference_version=r['reference_version'],current_target=r['current_target'],
        role=r['role'],is_admitted_space_candidate=r['is_admitted_space_candidate'],
        full_reference_available=r['full_reference_available'],version_alias=r['version_alias']) for r in refs])
    ref_counts=tables['image_reference_registry'].groupby('image_id').agg(
        declared_reference_ids=('target_id','nunique'),admitted_reference_ids=('is_admitted_space_candidate','sum'),
        complete_reference_ids=('full_reference_available','sum')).reset_index()
    tables['image_inventory']=tables['image_inventory'].merge(ref_counts,on='image_id',validate='many_to_one')
    tables['image_context_registry']=d.groupby(['image_id','image_code','building_id','difficulty_class','current_target_id'],dropna=False).agg(
        is_doorway=('is_doorway','max'),is_oos=('is_oos','max'),
        doorway_statuses=('doorway_status',lambda x:sorted(set(x))),
        source_scenes=('scene',lambda x:sorted(set(x))),
        scene_buckets=('scene_bucket',lambda x:sorted(set(x)))).reset_index().merge(ref_counts,on='image_id',validate='one_to_one')
    tables['image_context_registry']['reference_ids_are_not_certified_distinct_physical_spaces']=True
    tables['image_context_registry']['difficulty_outcome_exposure_audit']='not_independently_reconstructed_here'
    reasons=[]
    for r in d.to_dict('records'):
        for field in ['quality_input_blockers','quality_exclusion_reasons','measurement_reasons']:
            value=r[field]
            values=json.loads(value) if isinstance(value,str) and value.startswith('[') else [] if pd.isna(value) else [value]
            for reason in values:
                reasons.append(dict(object_id=r['object_id'],worker_id=r['worker_id'],image_id=r['image_id'],
                    condition=r['condition'],reason_kind=field,reason=json.dumps(reason,ensure_ascii=False) if isinstance(reason,dict) else reason))
    tables['exclusion_reason_hits']=pd.DataFrame(reasons)
    tables['exclusion_reason_summary']=tables['exclusion_reason_hits'].groupby(['condition','reason_kind','reason']).agg(
        records=('object_id','nunique'),workers=('worker_id','nunique'),images=('image_id','nunique')).reset_index()
    overlaps=[]
    for oid,cell in tables['exclusion_reason_hits'].groupby('object_id'):
        for a,b in combinations(sorted(set(cell.reason_kind+'|'+cell.reason)),2):
            overlaps.append(dict(object_id=oid,reason_a=a,reason_b=b))
    tables['exclusion_reason_intersections']=pd.DataFrame(overlaps).groupby(['reason_a','reason_b']).object_id.nunique().reset_index(name='records')
    cleaning=[]
    for keys,g in d.groupby(['condition','cleaning_disposition']):
        row=dict(zip(['condition','cleaning_disposition'],keys),inventory=len(g),
            quality=int(g.quality_usable.sum()),diagnostic_only=True)
        for metric in ['diagnostic_B8L2','diagnostic_D10']:
            row.update({metric+'_'+k:v for k,v in distribution(g[metric]).items()})
        cleaning.append(row)
    tables['cleaning_diagnostics']=pd.DataFrame(cleaning)
    sensitive=[]
    for keys,g in d[d.quality_usable].groupby(['condition','quality_use','difficulty_class']):
        v=g.D10-g.B8L2
        sensitive.append(dict(zip(['condition','quality_use','difficulty_class'],keys),
            images=g.image_id.nunique(),workers=g.worker_id.nunique(),
            **{'D10_minus_B8L2_'+k:n for k,n in distribution(v).items()},
            spearman_B8L2_D10=g.B8L2.corr(g.D10,method='spearman'),
            same_rows_references_eligibility=True))
    tables['fixed_record_metric_sensitivity']=pd.DataFrame(sensitive)
    relative=[];components=[]
    for keys,g in d.groupby(['worker_id','condition','quality_use']):
        scored=g[g.quality_usable]
        row=dict(zip(['worker_id','condition','quality_use'],keys),n_inventory=len(g),n_quality=len(scored),
            images=scored.image_id.nunique(),buildings=scored.building_id.nunique())
        for metric in ['B8L2','D10']:
            row[metric+'_mean']=scored[metric].mean()
            row[metric+'_peer_supported_n']=int(scored[metric+'_peer_residual'].notna().sum())
            row[metric+'_peer_residual_mean']=scored[metric+'_peer_residual'].mean()
            row[metric+'_rank_percentile_mean']=scored[metric+'_rank_percentile'].mean()
        relative.append(row)
    profiles=pd.DataFrame(relative)
    for metric in ['B8L2','D10']:
        profiles[metric+'_raw_rank']=profiles.groupby(['condition','quality_use'])[metric+'_mean'].rank(ascending=False)
        profiles[metric+'_relative_rank']=profiles.groupby(['condition','quality_use'])[metric+'_rank_percentile_mean'].rank(ascending=False)
    profiles['B8L2_raw_minus_relative_rank']=profiles.B8L2_raw_rank-profiles.B8L2_relative_rank
    profiles['D10_rank_minus_B8L2_rank']=profiles.D10_relative_rank-profiles.B8L2_relative_rank
    tables['worker_relative_quality']=profiles
    for keys,g in d[d.quality_usable].groupby(['condition','quality_use']):
        for metric in QUALITY:
            common=g[[metric,'IoU3D100']].dropna() if metric!='IoU3D100' else g[['IoU3D100']].dropna()
            components.append(dict(zip(['condition','quality_use'],keys),metric=metric,n=len(common),
                images=g.loc[common.index,'image_id'].nunique(),workers=g.loc[common.index,'worker_id'].nunique(),
                buildings=g.loc[common.index,'building_id'].nunique(),
                spearman_with_IoU3D100=common[metric].corr(common.IoU3D100,method='spearman') if len(common)>1 else None))
    tables['quality_component_associations']=pd.DataFrame(components)
    if 'scope_opportunity' in d:
        rows=[]
        for keys,g in d.groupby(['worker_id','condition']):
            judged=g[g.scope_opportunity]
            retained=judged[judged.cleaning_disposition.eq('retained')]
            rows.append(dict(worker_id=keys[0],condition=keys[1],submissions=len(g),
                scope_response_n=g.scope_response.notna().sum(),scope_opportunities=len(judged),
                scope_correct_n=int(judged.scope_correct.eq(True).sum()),scope_retained_opportunities=len(retained),
                scope_retained_correct_n=int(retained.scope_correct.eq(True).sum()),
                scope_unjudged_n=int((~g.scope_opportunity).sum()),
                confirmed_error_opportunities=int(g.semi_confirmed_error_opportunity.sum()),
                confirmed_error_unchanged=int((g.semi_confirmed_error_opportunity&g.semi_known_error_unchanged.eq(True)).sum()),
                reported_error_opportunities=int(g.semi_reported_error_opportunity.sum()),
                reported_error_unchanged=int((g.semi_reported_error_opportunity&g.semi_reported_known_error_unchanged.eq(True)).sum()),
                exact_initializations=int(g.semi_exact_initialization.sum()),
                current_compatible_gain_n=int(g.semi_current_gain_available.sum()),
                worker_gain_n=int(g.semi_worker_gain_B8L2.notna().sum()),
                worker_gain_mean=g.semi_worker_gain_B8L2.mean(),
                evidence_definition='compatible_independently_bound_task_gold; confirmed_and_reported_semi_separate'))
        tables['worker_scope_semi_evidence']=pd.DataFrame(rows)
        tables['calculation_coverage']=d.groupby(['condition','origin','calculation_class','quality_use'],dropna=False).size().reset_index(name='records')
        tables['time_provenance_coverage']=d.groupby(['condition','origin','time_source_kind','source_time_status','target_time_status'],dropna=False).size().reset_index(name='records')
    return tables


def historical_and_personnel_tables(records):
    tables={};index=[]
    for name in ['profiles','difficulty_preferences','groups','reliability']:
        path=ROOT/'research/workers/personnel_v2_20261019'/(name+'.csv')
        table=pd.read_csv(path,low_memory=False)
        if name=='groups':table['workers']=table.workers.map(ast.literal_eval)
        table['classification_status']='exploratory_descriptive_not_validated_worker_types'
        tables['personnel_'+name]=table
        index.append(dict(topic='personnel_'+name,status='computed',source=str(path.relative_to(ROOT)),
            data_release='v2',limitation='exploratory_descriptive_not_validated_worker_types; thresholds_not_frozen'))
    for topic,path in [('fusion','research/fusion/wall_consensus_v1_process_20261017/CURRENT.json'),
        ('same_room_process','research/same_room/same_room_v1_process_20261017/CONSUMER_INTERFACE.json'),
        ('response_clusters','analysis_results/consensus_response_20261006')]:
        index.append(dict(topic=topic,status='historical_only',source=path,data_release='v1_or_older',
            limitation='not_v2_recomputed; no v2 membership/trajectory claim'))
    plan=ROOT/'research/statistics/annotation_gallery_20261017/supplement_plan.json'
    tables['historical_supplement_plan']=pd.DataFrame([dict(status='historical_only',source=str(plan.relative_to(ROOT)),
        current_v2_quota_frozen=False,payload=read(plan))])
    tables['historical_source_index']=pd.DataFrame(index)
    old=pd.read_csv(ROOT/'research/statistics/b8l2_d10_statistics_20261017/record_lookup.csv',low_memory=False)
    current=records[['object_id','worker_id','condition','reference_id','quality_usable','B8L2','D10']]
    comparison=old[['object_id','worker_id','condition','reference_id','quality_usable','B8L2','D10']].merge(
        current,on=['object_id','worker_id','condition'],validate='one_to_one',suffixes=('_v1','_v2'))
    assert len(comparison)==len(old)
    comparison['same_reference_identity']=comparison.reference_id_v1.eq(comparison.reference_id_v2)
    comparison['geometry_and_reference_geometry_verified_equal']=False
    comparison['version_comparison_use']='membership_and_description_only; input/reference geometry bridge_not_revalidated_here'
    for metric in ['B8L2','D10']:comparison[metric+'_v2_minus_v1']=comparison[metric+'_v2']-comparison[metric+'_v1']
    tables['v1_v2_common_membership']=comparison
    return tables


def field_unit(name):
    if name.endswith('_n') or name.startswith('n_') or name.endswith('_missing') or name in ['records','inventory','possible_pairs','measurable_pairs','unmeasurable_pairs']:
        return 'count; see table grain and denominator'
    if 'percentile' in name:return 'percentile_0_to_100; within same image/condition/reference; singleton missing'
    if '_rank' in name:return 'ordinal rank or rank difference; condition/quality-use separated, ties averaged'
    if 'log_time' in name or name=='absolute_log_mean_time_gap':return 'natural_log_time_ratio; cohort/time-source-stratified'
    if 'time_ratio' in name:return 'dimensionless time ratio b/a'
    if name.endswith('_rate') or 'cancellation_fraction' in name:return 'ratio; definition in denominator fields'
    if 'time' in name or 'seconds' in name:return 'seconds if numeric duration; status/provenance if categorical'
    if 'B8L2' in name or 'D10' in name or 'IoU3D100' in name:return '0_to_100 score or difference; n/sd/quantiles as suffix'
    if 'S_bottom' in name or name=='dir' or name.startswith('dir_'):return 'degrees'
    if any(k in name for k in ['Hmean','Hcenter','height_mean_ratio','iou_3d_corner_mean']):return 'dimensionless ratio or relative height error'
    if 'iou' in name.lower() or name=='R_union_normalized':return 'ratio_0_to_1'
    if name=='R_symdiff_h2':return 'camera_height_squared; declared footprint symmetric difference'
    if name.startswith('R_'):return 'normalized floor-disagreement ratio; suffix n is count'
    return 'source_identity/category/boolean/relative quantity; see field name and source evidence'


def coverage_rows(tables,evidence_status):
    attachment=OUT/'REQUIREMENTS.md'
    import re
    section=None;rows=[]
    for line in attachment.read_text(encoding='utf-8-sig').splitlines():
        match=re.match(r'\*\*([一二三四五六七八九十]+)、(.+?)\*\*',line)
        if match:section=match.group(1)+'、'+match.group(2)
        requirement=line[2:].strip() if line.startswith('- ') else line.strip() if line.startswith('| 人员') or line.startswith('| 图片') or line.startswith('| 难度') or line.startswith('| 房间') else None
        if not section or not requirement:continue
        status='computed';missing=None;detail='本轮按现有资格、直接关系和条件计算；均值/中位数/分位/离散/缺失及独立图人楼支持见分表。'
        files=['tables.json','FIELD_CONTRACT.json']
        if any(term in requirement for term in ['融合人数过程','实际全员','实际成员名单','相邻人数节点','每条路径','两侧过程','相同进入顺序','共同人员Lee','必要细节','墙线、角点和连接','组合的质量','组合的影响','整簇','从作答簇','同簇换人','不同簇构成','原图、成员作答、融合','所属融合成员']):
            status='historical_only';missing='experiment_not_run_v2';detail='历史真实结果有明确入口；本轮只算v2可行人员池，不将旧成员/轨迹/簇冒充v2。';files=['historical_source_index.csv','independent_pool_inventory.csv']
        if section.startswith('十二') or section.startswith('十三'):
            status='historical_only';missing='experiment_not_run_v2';detail='已有人员画像与可行池支持可查；v2新融合、组合/替换/顺序实验未运行。';files=['historical_source_index.csv','independent_pool_inventory.csv','personnel_profiles.csv']
        if section.startswith('十三') and '连续Q／T画像及已有分组' in requirement:
            status='computed';missing=None;detail='复用当前v2人员描述画像/候选分组及支持；不是经楼外验证的稳定人员类型，阈值未冻结。';files=['personnel_profiles.csv','personnel_groups.csv']
        if any(term in requirement for term in ['不同进入顺序','重新选人','同一类别构成','更换具体成员','随机组合','楼外预测','人员组合与人数增长的累计时间']):
            status='not_run';missing='experiment_not_run_v2';detail='相关成员/时间底表已备；尚无本轮v2实际组合产物，不能由个人均值模拟共识。'
        if any(term in requirement for term in ['补标人数缺口','初始严重程度','明确个人严重错误','同等质量下谁更快','确认错误是否','原本正确的预标注','判断是否合适']):
            status='source_missing';missing='gold_or_target_definition_missing';detail='已有可判机会单列；不能把未知当正确/严重错误，v2补标目标数未固定。'
        if any(term in requirement for term in ['不同结构表达','作答分簇','每图簇数','不同标法分布']):
            status='not_run';missing='experiment_not_run_v2';detail='点对数分布和原答底面差异已算；变点数结构对应距离/分簇未运行，不设0。';files=['point_structure_distribution.csv','raw_disagreement_summary.csv']
        if '快／中／慢时间阈值' in requirement or '尚不能当' in requirement:
            status='not_run';missing='method_not_frozen';detail='既有v2探索候选阈值可查，不当正式冻结方案。'
        if '历史WQ' in requirement or '固定成员和几何' in requirement:
            status='not_run';missing='matched_geometry_experiment_not_run_v2';detail='B8L2-D10固定作答敏感性已算；历史算法/团队几何严格版本对照不在本轮新增。'
        if '未来v2' in requirement:
            status='not_run';missing='migration_and_refit_experiments_not_run';detail='已列共同旧3222和新增7217及资格变化；共同几何/参考桥未重新认证，画像迁移与重新拟合比较未完成。';files=['v1_v2_common_membership.csv','cohort_condition_summary.csv']
        if '不同空间对应的质量、时间及融合差异' in requirement:
            status='not_run';missing='fusion_experiment_not_run_v2';detail='空间绑定的质量、来源时间和目标时间分布已算；各空间融合差异未运行。';files=['image_target.csv','independent_pool_inventory.csv']
        if '清洗后质量较好' in requirement or '明确个人严重错误' in requirement or '偶发严重失误' in requirement:
            status='source_missing';missing='independent_severity_gold_missing';detail='已有清洗计数、历史明确个人错误及候选原因可与当前质量联查；没有新增独立严重度gold，不能由文本候选推总体严重失误率。';files=['worker_inventory.csv','worker_scope_semi_evidence.csv','cleaning_diagnostics.csv']
        if '图片／难度／房间结论是否变化' in requirement:
            status='not_run';missing='matched_version_comparison_not_run';detail='v2各层分布及B8L2/D10固定记录敏感性已算；未完成全量新旧相同输入/参考/资格的结论对照。';files=['fixed_record_metric_sensitivity.csv','v1_v2_common_membership.csv']
        if '原图、原标注、预处理后标注、参考叠线、BEV及可用的3D' in requirement:
            status='source_missing';missing='two_photos_missing_and_ui_owned_by_coordinator';detail='逐份点、处理/参考证据已连接，由统筹接原图/叠线/BEV/可用3D展示；原图Release仍有2图缺口，不能宣称本模块完成所有视觉核验。';files=['shared_records.csv']
        if '有来源活动时间、同目标时间、初始化、参考、融合过程的覆盖数量' in requirement:
            status='computed';missing='v2_fusion_not_run';detail='活动/目标时间、初始化及参考覆盖已计；v2融合真实过程覆盖为0，已有v1过程仅历史入口。';files=['time_provenance_coverage.csv','worker_scope_semi_evidence.csv','historical_source_index.csv']
        if '同房表现与已有可用对照' in requirement:
            status='not_run';missing='matched_control_analysis_not_run_v2';detail='同房双侧质量/时间及权重已算；v2同建筑可用对照匹配尚未重做，旧对照不得移植。';files=['direct_pair_summary.csv','room_weighting_sensitivity.csv']
        if '难度标签是否参考过实际作答' in requirement:
            status='source_missing';missing='label_outcome_exposure_history_not_fully_reconstructed';detail='沿用既有难度，不依据本次分数改标签；未重建全部标签的作答暴露历史。';files=['image_context_registry.csv']
        if '初始化质量、最终质量及净变化' in requirement or '修改行为、净改善和耗时' in requirement:
            status='source_missing';missing='new_semi_initialization_geometry_missing';detail='已接入与当前最终几何/参考匹配的历史兼容净改善；新Semi只有报告标记，没有逐份实际初始化几何，不能计算其净改善。';files=['shared_records.csv','worker_scope_semi_evidence.csv']
        if '已审核数、可判断机会数、原因未知数' in requirement:
            status='source_missing';missing='unified_review_opportunity_and_severity_gold_missing';detail='scope/Semi的明确机会与逐份源裁决/归因已有；全库存统一审核机会和独立严重度分母未建立，不能把保留或未排除视为确认无错。';files=['worker_scope_semi_evidence.csv','shared_records.csv']
        if '同等质量下谁更快' in requirement:
            status='not_run';missing='conditional_efficiency_comparison_not_run';detail='逐份Q/时间和按来源分层的同图同参考相对时间已备；固定Q效用下的效率匹配或模型比较尚未做。';files=['shared_records.csv','worker_relative_quality.csv']
        if '同一个人' in requirement or '人员 × 房间' in requirement or '房间 × 视角' in requirement:
            files=['direct_pair_people.csv','room_view_worker_matrix.csv'];detail='已有直接分组/图对中的逐人质量和两类时间差已算，未知房间关系不推断。'
        if '各质量分项' in requirement or '各分项与同参考3D IoU' in requirement:
            files=['quality_component_associations.csv','shared_records.csv'];detail='当前质量合格同参考集合的分项及3D IoU关系已算，诊断值另列；典型案例尚需统筹可视复核。'
        if '每张图片的空间候选数' in requirement:
            files=['image_reference_registry.csv','image_context_registry.csv','image_target.csv'];detail='列出声明参考/候选ID、当前目标与每目标作答；ID可能含版本别名，未把版本ID数冒称独立物理空间数。'
        completed=['实际计算子项见所列分表'] if status=='computed' else ['可用基础记录/分布已留在所列分表']
        remaining=[] if status=='computed' and missing is None else [missing or 'see_detail']
        rows.append(dict(section=section,requirement=requirement,status=status,remaining_type=missing,detail=detail,
            completed_parts=completed,remaining_parts=remaining,files=files))
    return rows


def export_tables(tables,checks,evidence_status):
    OUT.mkdir(parents=True,exist_ok=True)
    payload={};descriptions=[];contract={}
    for name,frame in tables.items():
        table_id='quality__shared_records' if name=='shared_records' else 'statistics__'+name
        csvframe=frame.copy()
        for c in csvframe:
            if csvframe[c].dtype=='object':csvframe[c]=csvframe[c].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v)
        csvframe.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
        payload[table_id]=public_value(json.loads(frame.to_json(orient='records',force_ascii=False,double_precision=15)))
        grain='one annotation; all inventory and exclusions retained' if name in ['shared_records','image_worker_matrix'] else (
            'one annotation pair within image/condition; dependent pairs' if name=='raw_answer_pairs' else
            'one observed grouping cell; grouping keys are leading identity fields, condition separated')
        if name.startswith('room_') or name.startswith('direct_'):grain+='; existing direct user relations only; groups overlap'
        keymap=dict(shared_records=['object_id'],image_worker_matrix=['object_id'],
            image_inventory=['image_id','condition'],worker_inventory=['worker_id','condition'],
            image_context_registry=['image_id'],image_reference_registry=['target_id'],
            condition_summary=['condition'],cohort_condition_summary=['origin','condition'],
            worker_difficulty=['worker_id','difficulty_class','condition','difficulty_target_relation'],
            worker_scene=['worker_id','scene_bucket','condition'],image_target=['image_id','chosen_target_id','condition'],
            worker_quality_use=['worker_id','condition','quality_use'],worker_relative_quality=['worker_id','condition','quality_use'],
            room_registry=['group_id'],room_memberships=['group_id','image_id'],
            room_group_summary=['group_id','condition'],room_worker_summary=['group_id','worker_id','condition'],
            room_view_summary=['group_id','image_id','condition'],room_view_worker_matrix=['group_id','object_id'],
            direct_relation_registry=['image_a','image_b'],direct_pair_summary=['image_a','image_b','condition','scope_panel','metric'],
            direct_pair_people=['image_a','image_b','condition','scope_panel','metric','worker_id'],
            raw_floor_record_status=['object_id'],raw_answer_pairs=['image_id','condition','object_id_a','object_id_b'],
            raw_disagreement_summary=['image_id','condition','target_relation'],
            independent_pool_inventory=['image_id','condition'],target_pool_inventory=['image_id','condition','chosen_target_id'],
            v1_v2_common_membership=['object_id'],worker_scope_semi_evidence=['worker_id','condition'])
        denominator='full observed inventory cell; quality metrics only quality_usable; source/target times have their own nonmissing counts'
        if name.startswith('direct_pair'):denominator='source-eligible common workers; n_paired is actual both-side nonmissing metric, scope_panel explicitly separated'
        if name.startswith('raw_'):denominator='all pairs of pool_analysis_eligible workers in image/condition; invalid floors remain unmeasurable, never zero'
        if name=='worker_scope_semi_evidence':denominator='scope independently bound compatible gold; confirmed and reported Semi error opportunities distinct; unknown outcomes not success'
        item=dict(id=table_id,path=name+'.csv',json_path='tables.json#/tables/'+table_id,
            rows=len(frame),columns=list(frame.columns),grain=grain,keys=keymap.get(name),denominator=denominator,
            status='historical_only' if name.startswith('historical_') else 'computed',data_release='v2')
        descriptions.append(item)
        contract[table_id]=dict(item,fields={c:dict(unit=field_unit(c),dtype=str(frame[c].dtype),missing='null retained, not zero') for c in frame})
    temporary=OUT/'tables.pending.json'
    temporary.write_text(json.dumps(dict(data_release='v2',analysis_revision=VERSION,tables=payload),ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    temporary.replace(OUT/'tables.json')
    write(OUT/'FIELD_CONTRACT.json',dict(data_release='v2',analysis_revision=VERSION,tables=contract,
        rules=['B8L2/D10 identical quality masks, each own declared reference',
            'source task time is not target-matched time; no lead_time or zero imputation',
            'no transitive same-room inference; buildings are not rooms; overlapping groups not additive',
            'raw floor R is not a structural correspondence score; different-count structural distance missing',
            'task percentile/peer residual are descriptive, not a new validated worker type or comprehensive score']))
    coverage=coverage_rows(tables,evidence_status)
    write(OUT/'COVERAGE.json',dict(data_release='v2',analysis_revision=VERSION,requirements=coverage,
        status_definitions=dict(computed='this run actual data/summary, bounded by listed missing evidence',
            historical_only='existing v1/older sources, not v2 trajectories/clusters',source_missing='missing gold/source/declared quota, not filled',
            not_run='data may exist; experiment/method comparison not executed'),
        evidence_join=evidence_status,all_15_sections=len({r['section'] for r in coverage})==15))
    write(OUT/'CHECKS.json',checks)
    write(OUT/'CONSUMER_INTERFACE.json',dict(schema='v2_integrated_statistics_consumer_v1',data_release='v2',
        analysis_revision=VERSION,status='ready',n1_applied=False,tables=descriptions,
        tables_json='tables.json',field_contract='FIELD_CONTRACT.json',coverage='COVERAGE.json',checks='CHECKS.json',
        input_manifest=MANIFEST.relative_to(ROOT).as_posix(),score_source=CROSS.relative_to(ROOT).as_posix(),
        evidence_source=EVIDENCE.relative_to(ROOT).as_posix(),evidence_join=evidence_status,
        publication=dict(local_json='tables.json',coordinator_generated_gzip='tables.json.gz',
            gzip_must_be_regenerated_from_final_json=True,csv_is_local_derivative=True),
        new_fusion_run=False,v1_modified=False,ui_owned_by_coordinator=True))
    paths=[CONTEXT,EVIDENCE,OUT/'REQUIREMENTS.md',ROOT/'research/same_room/relation_adoption_20261016/CROSS_MODULE_RELATIONS.json',
        ROOT/'research/statistics/b8l2_d10_statistics_20261017/record_lookup.csv',
        ROOT/'research/statistics/annotation_gallery_20261017/supplement_plan.json']
    paths.extend(ROOT/'research/same_room/relation_adoption_20261016'/name for name in ['relations.json','original_groups.json','candidate_adoption.json'])
    paths.extend((ROOT/'research/workers/personnel_v2_20261019').glob('*.csv'))
    write(OUT/'SOURCE_INPUTS.json',dict(data_release='v2',analysis_revision=VERSION,
        sources=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size) for p in paths],
        formal_upstream_manifest=MANIFEST.relative_to(ROOT).as_posix(),
        replay_context=CONTEXT.relative_to(ROOT).as_posix(),
        full_upstream_bundle_needed_for_statistics_replay=False,
        all_input_paths_inside_repository=True,no_future_simulation_inputs=True,no_new_zip=True))


def run():
    print('loading v2 inventory and evidence',flush=True)
    records,bundle,objects,refs,bindings,evidence_status=load_records()
    print('building inventory and cross tables',flush=True)
    tables=base_tables(records,refs)
    print('building direct room comparisons',flush=True)
    tables.update(room_tables(records))
    print('measuring declared floor disagreements',flush=True)
    tables.update(raw_disagreement(records,objects))
    tables.update(historical_and_personnel_tables(records))
    pools=tables['independent_pool_inventory'];raw=tables['raw_answer_pairs']
    checks=dict(data_release='v2',analysis_revision=VERSION,inventory=len(records),images=records.image_id.nunique(),
        workers=records.worker_id.nunique(),buildings=records.building_id.nunique(),
        quality=int(records.quality_usable.sum()),quality_images=records.loc[records.quality_usable,'image_id'].nunique(),
        quality_workers=records.loc[records.quality_usable,'worker_id'].nunique(),
        ordinary_manual=int((records.quality_usable&records.condition.eq('manual')&records.quality_use.eq('ordinary_primary')).sum()),
        source_time=int(records.source_active_time_seconds.notna().sum()),target_time=int(records.target_matched_time_seconds.notna().sum()),
        direct_relations=len(tables['direct_relation_registry']),registered_groups=len(tables['room_registry']),
        raw_possible_pairs=len(raw),raw_measurable_pairs=int(raw.floor_pair_measurable.sum()),
        raw_unmeasurable_pairs=int((~raw.floor_pair_measurable).sum()),
        different_pair_count_pairs=int(raw.same_pair_count.eq(False).sum()),
        low_people_pools=int(pools.low_people_pool.sum()),future_fusion_candidate_pools=int(pools.candidate_for_future_fusion.sum()),
        evidence_status=evidence_status,n1_applied=False,new_fusion_run=False,v1_modified=False,
        tables={name:len(frame) for name,frame in tables.items()})
    print('exporting typed JSON and CSV interfaces',flush=True)
    export_tables(tables,checks,evidence_status)
    print(json.dumps(checks,ensure_ascii=False),flush=True)
    return checks


if __name__=='__main__':run()
