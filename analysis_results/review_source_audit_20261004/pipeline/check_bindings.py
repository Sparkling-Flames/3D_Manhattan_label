"""只读比较当前最终源与冻结分析输入；不导入融合、几何或资格算法。"""
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'analysis_results/research_input_20260929'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def expected_record(o,alias,workers):
    """独立实现已声明的投影与确认环/默认x规则，不调用历史source_binding。"""
    row=dict(id=alias,points=copy.deepcopy(o['points_1024x512']),order_status=o['order_status'],
        geometry_status=o['geometry']['status'],geometry_issues=o['geometry']['issues'],
        source_point_indices=o['ordered_source_point_indices'],source_pair_indices=o['ordered_source_pair_indices'],
        source_point_labels=o['ordered_source_point_labels'],preprocessing_status=o['preprocessing_status'],
        ring_confirmed=o['ring_confirmed'])
    if o['object_kind']=='annotation':
        row.update(worker=workers[o['worker_id']],condition=o['condition'],cleaning=o['cleaning_disposition'],
            independent=o['independent_vote_eligible'],independence_reasons=o['independent_vote_reasons'],
            consensus_eligible=o['main_consensus_gate']['status'] in ('main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'),
            quality_candidate=o['main_quality_gate']['status']=='candidate_pending_geometry',
            main_quality_gate=o['main_quality_gate'],main_consensus_gate=o['main_consensus_gate'],
            scene_category=o['scene_category'],borrowed_points=bool(o['borrowed_point_provenance']))
    else:row['version']={'gt_original':'original','gt_manual_revision':'manual_revision'}[o['object_kind']]
    if row['points'] is None:row['order_used']='unavailable'
    elif row['ring_confirmed'] or row.get('version')=='original':
        row['order_used']='human_confirmed' if row['ring_confirmed'] else 'original_gt_reference'
    else:
        order=sorted(range(len(row['points'])//2),key=lambda i:row['points'][2*i][0])
        for field,stride in [('points',2),('source_point_indices',2),('source_pair_indices',1),('source_point_labels',2)]:
            if row[field] is not None:row[field]=[row[field][stride*i+j] for i in order for j in range(stride)]
        row['order_used']='default_x_unreviewed'
    return row


def main():
    manifest=read(SOURCE/'manifest.json')
    data=read(SOURCE/manifest['entrypoints']['data'])
    orders=read(SOURCE/manifest['entrypoints']['final_orders'])['records']
    objects=data['objects'];by_oid={o['object_id']:o for o in objects}
    # This is the documented project_public_research alias rule, derived anew from the full current source.
    aliases={o['object_id']:f'R{i:05d}' for i,o in enumerate(sorted(objects,key=lambda o:o['object_id']),1)}
    workers={w:f'P{i:03d}' for i,w in enumerate(sorted({o['worker_id'] for o in objects if o['object_kind']=='annotation'}),1)}
    current={aliases[o['object_id']]:expected_record(o,aliases[o['object_id']],workers) for o in objects}
    source_by_alias={aliases[o['object_id']]:o for o in objects}
    anomalies=[];source_rows=[]
    for o in objects:
        checks={};points=o['points_1024x512'];ix=o['ordered_source_point_indices']
        if points is not None:
            checks['points_exactly_follow_preprocessed_source_indices']=points==[o['preprocessed_points'][j] for j in ix]
            checks['labels_exactly_follow_source_indices']=o['ordered_source_point_labels']==[o['point_labels'][j] for j in ix]
            checks['pair_indices_follow_links']=ix==[j for i in o['ordered_source_pair_indices'] for j in o['links_zero_based'][i]]
        if o['ring_confirmed']:
            received=orders.get(o['object_id'])
            checks['final_confirmed_order_present']=received is not None and received.get('status')=='confirmed'
            checks['current_order_record_equals_final_received_record']=received==o.get('order_record')
            if received:
                binding=json.loads(received['binding'])
                checks['final_binding_id']=binding['id']==o['object_id']
                checks['final_binding_coordinates']=binding['points']==o['preprocessed_points']
                checks['final_binding_links']=binding['links']==o['links_zero_based']
                checks['final_binding_labels']=binding['labels']==o['point_labels']
                checks['final_pair_order_applied']=received['order']==o['ordered_source_pair_indices']
        if o['object_kind']=='annotation':
            checks['source_export_exists']=(ROOT/o['source']['path']).is_file()
            checks['source_worker_binding']=o['source']['worker']==o['worker_id']
            checks['source_condition_binding']=o['source']['condition']==o['condition']
            checks['source_image_binding']=o['source']['image_id']==o['image_id']
        bad=[k for k,v in checks.items() if not v]
        row=dict(id=aliases[o['object_id']],object_id=o['object_id'],image=o['image_code'],kind=o['object_kind'],
            ring_confirmed=o['ring_confirmed'],checks=checks,failed_checks=bad)
        source_rows.append(row)
        if bad:anomalies.append(dict(stage='current_source_internal',**row))
    write('current_source_checks.json',source_rows)
    panels=[('lee_difficulty45','lee_difficulty_20261003/input.json'),
            ('lee_expanded137_source','lee_expanded_20261003/source_input.json'),
            ('lee_expanded136_success','lee_expanded_20261003/input.json'),
            ('worker_profiles10','worker_profiles_20261003/input.json')]
    summaries=[];frozen_by_stage={}
    for stage,relative in panels:
        panel=read(ROOT/'analysis_results'/relative);rows=[];image_checks=[];flat={}
        for im in panel['images']:
            seen={r['id'] for field in ('annotations','references') for r in im[field]}
            expected={aliases[o['object_id']] for o in objects if o['image_code']==im['code']}
            image_checks.append(dict(image=im['code'],same_complete_object_population=seen==expected,
                missing=sorted(expected-seen),extra=sorted(seen-expected)))
            for field in ('annotations','references'):
                for frozen in im[field]:
                    rid=frozen['id'];flat[rid]=frozen;o=source_by_alias.get(rid);exp=current.get(rid)
                    differences=[]
                    if exp is None:differences.append(dict(field='id',expected='present in current source',actual=rid))
                    else:
                        if o['image_code']!=im['code']:differences.append(dict(field='image',expected=o['image_code'],actual=im['code']))
                        for key,value in exp.items():
                            if key not in frozen or frozen[key]!=value:
                                differences.append(dict(field=key,expected=value,actual=frozen.get(key),missing=key not in frozen))
                        if frozen['points'] is not None:
                            bound=[o['preprocessed_points'][i] for i in frozen['source_point_indices']]
                            if bound!=frozen['points']:differences.append(dict(field='direct_preprocessed_index_binding',expected=bound,actual=frozen['points']))
                    row=dict(id=rid,object_id=o['object_id'] if o else None,image=im['code'],kind=field,
                        ring_confirmed=frozen.get('ring_confirmed'),compared_fields=len(exp or {}),differences=differences)
                    rows.append(row)
                    if differences:anomalies.append(dict(stage=stage,**row))
        frozen_by_stage[stage]=flat
        write(stage+'_record_checks.json',rows)
        write(stage+'_image_population_checks.json',image_checks)
        summaries.append(dict(stage=stage,input='analysis_results/'+relative,images=len(panel['images']),
            annotations=sum(len(i['annotations']) for i in panel['images']),references=sum(len(i['references']) for i in panel['images']),
            confirmed_objects=sum(bool(r['ring_confirmed']) for r in rows),records_with_differences=sum(bool(r['differences']) for r in rows),
            images_with_population_differences=sum(not r['same_complete_object_population'] for r in image_checks)))
    roster_checks=[]
    for stage,directory in [('lee_difficulty45','lee_difficulty_20261003'),('lee_expanded136_success','lee_expanded_20261003'),('worker_profiles10','worker_profiles_20261003')]:
        rosters=read(ROOT/'analysis_results'/directory/'rosters.json')
        if stage=='worker_profiles10':
            rosters=[dict(r,workers=rosters['workers']) for r in rosters['groups']]
        for roster in rosters:
            ids=roster['record_ids'];expected=[rid for rid,o in source_by_alias.items() if o['image_code']==roster['image'] and o['object_kind']=='annotation'
                and current[rid]['condition']=='manual' and current[rid]['independent'] and current[rid]['consensus_eligible']
                and current[rid]['main_consensus_gate']['status']=='main_candidate']
            differences=[]
            if set(ids)!=set(expected):differences.append('roster_set_differs_from_current_manual_main_candidate_gate')
            if roster['workers']!=[current[rid]['worker'] for rid in ids]:differences.append('worker_order_or_identity_mismatch')
            row=dict(stage=stage,image=roster['image'],n=len(ids),differences=differences)
            roster_checks.append(row)
            if differences:anomalies.append(row)
    write('roster_gate_checks.json',roster_checks)
    global_data=read(ROOT/'analysis_results/global_pair_consensus_20261004/primary_results.json')
    global_checks=[];observations=0
    for im in global_data['images']:
        expected={rid for rid,o in source_by_alias.items() if o['image_code']==im['image'] and o['object_kind']=='annotation'
            and current[rid]['condition']=='manual' and current[rid]['independent'] and current[rid]['consensus_eligible']
            and current[rid]['main_consensus_gate']['status']=='main_candidate'}
        for method,result in im['methods'].items():
            diffs=[];assignments={r['id']:r for r in result['assignments']}
            if set(assignments)!=expected:diffs.append(dict(field='all_input_ids',expected=sorted(expected),actual=sorted(assignments)))
            if result['vote_denominator']!=len(expected):diffs.append(dict(field='vote_denominator'))
            evidence=defaultdict(dict)
            for group in result['identity_groups']:
                for member in group['members']:
                    rid=member['id'];i=member['pair_index'];exp=current[rid];observations+=1
                    if i in evidence[rid]:diffs.append(dict(id=rid,field='duplicate_pair_evidence',pair_index=i))
                    evidence[rid][i]=member['points']
                    for key,value in dict(worker=exp['worker'],points=exp['points'][2*i:2*i+2],
                        source_pair_index=exp['source_pair_indices'][i],source_point_indices=exp['source_point_indices'][2*i:2*i+2]).items():
                        if member[key]!=value:diffs.append(dict(id=rid,pair_index=i,field=key,expected=value,actual=member[key]))
            for rid,row in assignments.items():
                exp=current[rid]
                for key,value in dict(worker=exp['worker'],source_ring_confirmed=exp['ring_confirmed'],source_order_status=exp['order_status']).items():
                    if row[key]!=value:diffs.append(dict(id=rid,field=key,expected=value,actual=row[key]))
                if row['input_status']=='ok' and sorted(evidence[rid])!=list(range(len(exp['points'])//2)):
                    diffs.append(dict(id=rid,field='missing_source_pair_evidence'))
                if row['input_status']!='ok' and not any(x['id']==rid for x in result['input_issues']):
                    diffs.append(dict(id=rid,field='unavailable_record_not_reported'))
            row=dict(image=im['image'],method=method,n=len(expected),assignments=len(assignments),
                source_pair_observations=sum(len(v) for v in evidence.values()),differences=diffs)
            global_checks.append(row)
            if diffs:anomalies.append(dict(stage='global_pair137',**row))
    write('global_pair_observation_checks.json',global_checks)
    summary=dict(schema='current_final_source_pipeline_binding_audit_v1',source_manifest=str((SOURCE/'manifest.json').relative_to(ROOT)).replace('\\','/'),
        source_objects=len(objects),source_annotations=sum(o['object_kind']=='annotation' for o in objects),
        source_confirmed_orders=sum(o['ring_confirmed'] for o in objects),source_internal_failed_objects=sum(bool(r['failed_checks']) for r in source_rows),
        stages=summaries,roster_checks=len(roster_checks),roster_failures=sum(bool(r['differences']) for r in roster_checks),
        global_images=len(global_data['images']),global_method_cases=len(global_checks),global_source_pair_observations=observations,
        global_cases_with_differences=sum(bool(r['differences']) for r in global_checks),anomalies=len(anomalies),
        limits=['No fusion, geometry, statistics, or eligibility is recalculated.',
            'Comparison is to current manifest source and received_orders; later review files outside that source need a separate upstream intake audit.',
            'Raw export paths exist and source identities are checked; raw export annotations are not reparsed here.',
            'Nondefault 2.5/10 degree results do not persist full observation assignments; their declared source path matches the audited source but individual provenance was only directly audited at saved 5 degrees.',
            'BEV footprint numbers and quality scores are not recomputed.'])
    write('anomalies.json',anomalies);write('summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
