"""冻结共同评分的登记关系组/直接图对描述；不把G编号认证为物理房间。"""
from collections import Counter

import pandas as pd

from .b8l2_detail_summary_20261016 import summarize_group, METRICS
from .same_room_similarity_20261003 import relation_index


def candidate_tier(candidate):
    if (candidate['physical_same_supported'] and candidate['comparable_for_prediction'] and
            not candidate['oos_pending'] and candidate['review_state']=='explicit_confirmed'):
        return 'confirmed_comparable'
    return 'supported_other' if candidate['physical_same_supported'] else 'candidate_unconfirmed'


def adopted_candidate_tier(candidate,groups):
    if candidate['adopted_comparable']:return 'user_classified_comparable'
    if candidate['physical_supported']:return 'user_classified_other_scope'
    return 'not_supported' if any(groups[g]['raw_current']['physical_same']=='不支持'
        for g in candidate['source_group_codes']) else 'physical_pending'


def refresh_adoption_labels(tables,adoption):
    """成员不变时只同步统一关系字段，不重新计算质量、时间或统计数值。"""
    candidates={r['candidate_id']:r for r in adoption['candidates']}
    groups={r['review_code']:r for r in adoption['groups']}
    pairs={(r['image_a'],r['image_b']):r for r in adoption['relations']}
    assert {r['candidate_id'] for r in tables['room_group_registry']}==set(candidates)
    assert {tuple(r['image_ids']) for r in tables['room_direct_pair_registry']}==set(pairs)
    tiers={}
    for row in tables['room_group_registry']:
        current=candidates[row['candidate_id']]
        assert set(row['image_ids'])==set(current['image_ids']), 'membership changed: regenerate group statistics'
        row.update(current,relation_tier=adopted_candidate_tier(current,groups))
        tiers[row['group_id']]=row['relation_tier']
    for row in tables['room_direct_pair_registry']:
        current=pairs[tuple(row['image_ids'])]
        row.update(relation_tier=current['tier'],evidence=current['evidence'],
            source_candidate_ids=current['candidates'],user_group_ids=current['user_group_ids'],
            physical_adopted=current['physical_adopted'],scope_comparable=current['scope_comparable'],
            substantive_conflict=current['substantive_conflict'])
        tiers[row['group_id']]=row['relation_tier']
    for row in tables['room_raw_group_evidence']:
        current=groups[row['review_code']]
        assert row['raw_current']==current['raw_current'] and set(row['image_ids'])==set(current['image_ids'])
    changed=[]
    for name,rows in tables.items():
        touched=False
        for row in rows:
            if 'relation_adoption_version' in row:
                row['relation_adoption_version']=adoption['version'];touched=True
                if 'relation_tier' in row and row.get('group_id') in tiers:row['relation_tier']=tiers[row['group_id']]
        if touched:changed.append(name)
    return changed


def build_room_descriptions(records, bundle, *, adoption=None):
    """返回listdict表；库存切片含已屏蔽质量/时间，始终分condition与analysis_layer。"""
    frame=pd.DataFrame(records).copy()
    if frame.object_id.duplicated().any():
        raise ValueError('duplicate object_id in shared records')
    for metric in METRICS:
        frame[metric]=pd.to_numeric(frame[metric].replace('',None),errors='raise')
    frame['pool_analysis_eligible']=frame.pool_analysis_eligible.isin([True,'True'])
    registry=bundle['data']['room_registry']
    if adoption:
        adopted_candidates={c['candidate_id']:c for c in adoption['candidates']}
        assert set(adopted_candidates)=={c['candidate_id'] for c in registry['candidates']}
        original_groups={g['review_code']:g for g in adoption['groups']}
        assert all(g['viewed'] for g in original_groups.values())
    current_images=set(frame.image_id)
    membership_count=Counter(image for candidate in registry['candidates'] for image in set(candidate['image_ids']))
    record_counts=frame.groupby('image_id').size().to_dict()
    codes=frame.drop_duplicates('image_id').set_index('image_id').image_code.to_dict()
    tables={name:[] for name in ['room_group_registry','room_raw_group_evidence','room_group_memberships',
        'room_group_summary','room_worker_groups','room_group_views','room_direct_pair_registry',
        'room_direct_pair_summary','room_worker_direct_pairs','room_unlinked_images']}
    definitions=[]
    for index,candidate in enumerate(registry['candidates']):
        ids=sorted(set(candidate['image_ids']))
        row=dict(group_id='candidate:'+candidate['candidate_id'], group_kind='registered_relation_group',
            candidate_id=candidate['candidate_id'], image_ids=ids, source_group_codes=candidate.get('source_group_codes',[]),
            relation_tier=candidate_tier(candidate),review_state=candidate['review_state'],
            physical_same_supported=candidate['physical_same_supported'],
            physical_room_identity_certified=False,
            source_registry=registry['source'],source_pointer=f'/candidates/{index}',
            n_registered_views=len(ids),n_current_inventory_views=len(set(ids)&current_images),
            n_current_inventory_records=sum(record_counts.get(i,0) for i in ids),
            overlap_image_ids=[i for i in ids if membership_count[i]>1],
            excluded_from_this_subset=candidate.get('excluded_from_this_subset',[]),
            subset_scope=candidate.get('subset_scope',''),issue_tags=candidate.get('issue_tags',[]))
        tables['room_group_registry'].append(row)
        if adoption:
            adopted=adopted_candidates[candidate['candidate_id']]
            assert set(adopted['image_ids'])==set(ids), candidate['candidate_id']
            classifications=[original_groups[g]['raw_current']['physical_same'] for g in adopted['source_group_codes']]
            row.update(adopted,relation_adoption_version=adoption['version'],
                user_classification_adopted=True,identity_basis='versioned_user_working_group',
                source_user_classifications=classifications,
                relation_tier=adopted_candidate_tier(adopted,original_groups))
            row.pop('physical_room_identity_certified')
        definitions.append(row)
        for image in ids:
            tables['room_group_memberships'].append(dict(group_id=row['group_id'],image_id=image,
                image_code=codes.get(image,''),n_registered_candidate_groups=membership_count[image],
                n_current_inventory_records=record_counts.get(image,0),
                membership_is_physical_room_identity=False))
            if adoption:
                tables['room_group_memberships'][-1].update(relation_adoption_version=adoption['version'],
                    identity_basis='versioned_user_working_group')
                tables['room_group_memberships'][-1].pop('membership_is_physical_room_identity')
    if adoption:
        tables.update({name:[] for name in ['user_original_group_summary','user_original_worker_groups',
            'user_original_group_views','user_original_group_memberships']})
    for index,group in enumerate(registry.get('groups',[])):
        tables['room_raw_group_evidence'].append(dict(review_code=group['review_code'],
            original_group_id=group['group_id'],image_ids=group['image_ids'],
            source_registry=registry['source'],source_pointer=f'/groups/{index}',
            review_state=group.get('review_state'),raw_current=group.get('raw_current',{}),
            interpretation=group.get('interpretation',{}),source_pair_ids=group.get('source_pair_ids',[]),
            physical_room_identity_certified=False,
            note='原组证据不替代经解释后的候选子组，也不参与另一次汇总'))
        if adoption:
            row=tables['room_raw_group_evidence'][-1]
            assert group['raw_current']==original_groups[group['review_code']]['raw_current']
            row.update(viewed=group['viewed'],user_classification_adopted=True,
                user_physical_classification=group['raw_current']['physical_same'],
                relation_adoption_version=adoption['version'],
                n_registered_views=len(group['image_ids']),
                n_current_inventory_views=len(set(group['image_ids'])&current_images),
                n_current_inventory_records=sum(record_counts.get(i,0) for i in group['image_ids']),
                note='完整人工原组分类；与采用子组分表，不跨表相加')
            row.pop('physical_room_identity_certified')
            definitions.append(dict(group_id='user_group:'+group['review_code'],group_kind='original_user_group',
                image_ids=group['image_ids'],relation_tier=group['raw_current']['physical_same'],
                relation_adoption_version=adoption['version']))
            for image in group['image_ids']:
                tables['user_original_group_memberships'].append(dict(group_id='user_group:'+group['review_code'],
                    image_id=image,image_code=codes.get(image,''),relation_adoption_version=adoption['version']))
    relations=(relation_index(registry['candidates']) if not adoption else
        {(r['image_a'],r['image_b']):r for r in adoption['relations']})
    for (a,b),relation in sorted(relations.items()):
        row=dict(group_id='pair:'+a+'|'+b,group_kind='direct_registered_pair',image_ids=[a,b],
            image_code_a=codes.get(a,''),image_code_b=codes.get(b,''),
            relation_tier=relation['tier'],source_candidate_ids=relation['candidates'],
            evidence=relation['evidence'],physical_room_identity_certified=False,
            pair_origin='registered candidate co-membership; no transitive closure',
            n_registered_views=2,n_current_inventory_views=len({a,b}&current_images),
            n_current_inventory_records=record_counts.get(a,0)+record_counts.get(b,0))
        if adoption:
            row.update(relation_adoption_version=adoption['version'],user_group_ids=relation['user_group_ids'],
                physical_adopted=relation['physical_adopted'],scope_comparable=relation['scope_comparable'],
                substantive_conflict=relation['substantive_conflict'],
                pair_origin='direct original user group or explicit retained/merged subgroup; no transitive closure')
            row.pop('physical_room_identity_certified')
        tables['room_direct_pair_registry'].append(row)
        # 缺少任一当前视角的图对仍在registry，避免伪装成实际双视角比较。
        if {a,b}<=current_images:
            definitions.append(row)
    for definition in definitions:
        selected=frame[frame.image_id.isin(definition['image_ids'])]
        base={key:definition[key] for key in ['group_id','group_kind','relation_tier']}
        if adoption:base['relation_adoption_version']=adoption['version']
        base['n_declared_views']=len(definition['image_ids'])
        summary_name,worker_name,view_name={
            'registered_relation_group':('room_group_summary','room_worker_groups','room_group_views'),
            'direct_registered_pair':('room_direct_pair_summary','room_worker_direct_pairs',None),
            'original_user_group':('user_original_group_summary','user_original_worker_groups','user_original_group_views')
        }[definition['group_kind']]
        if selected.empty:
            if adoption:
                tables[summary_name].append(dict(base,condition='no_current_inventory',analysis_layer='no_current_inventory',
                    cell_status='no_observations',all_declared_views_have_records=False,**summarize_group(selected)))
            continue
        for (condition,layer),cell in selected.groupby(['condition','analysis_layer'],sort=True,dropna=False):
            labels=dict(base,condition=condition,analysis_layer=layer)
            table_row=dict(labels,**summarize_group(cell))
            table_row['all_declared_views_have_records']=cell.image_id.nunique()==base['n_declared_views']
            for label,metric in [('quality','B8L2'),('source_time','active_time_seconds'),('target_time','target_matched_time_seconds')]:
                workers=[set(cell.loc[cell.image_id.eq(i)&cell[metric].notna(),'worker_id']) for i in definition['image_ids']]
                table_row['n_'+label+'_workers_all_declared_views']=len(set.intersection(*workers))
            tables[summary_name].append(table_row)
            for worker,part in cell.groupby('worker_id',sort=True):
                tables[worker_name].append(dict(labels,worker_id=worker,
                    all_declared_views_have_records=part.image_id.nunique()==base['n_declared_views'],
                    **summarize_group(part)))
            if view_name:
                for image,part in cell.groupby('image_id',sort=True):
                    tables[view_name].append(dict(labels,image_id=image,image_code=codes[image],
                        n_registered_candidate_groups=membership_count[image],**summarize_group(part)))
    for image,part in frame[~frame.image_id.isin(membership_count)].groupby('image_id'):
        tables['room_unlinked_images'].append(dict(image_id=image,image_code=codes[image],n_inventory_records=len(part),
            recorded_room_ids=sorted({str(v) for v in part.room_id if pd.notna(v) and v!=''}),
            room_evidence_status='no_registered_candidate_membership; not confirmed different room'))
        if adoption:
            codes_in_original=[g['review_code'] for g in adoption['groups'] if image in g['image_ids']]
            tables['room_unlinked_images'][-1].update(original_user_group_ids=codes_in_original,
                relation_adoption_version=adoption['version'],
                room_evidence_status='outside_retained_working_subgroups; original_group_available' if codes_in_original else
                    'no_original_user_group_membership; not confirmed different room')
    return tables
