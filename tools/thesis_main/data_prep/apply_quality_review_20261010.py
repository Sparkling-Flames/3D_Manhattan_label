"""Apply the authorized review layer at the formal input boundary; raw files stay frozen."""
import copy
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UPDATE = ROOT / 'analysis_results/research_input_20260929/quality_update_20261010.json'

def read_update():
    return json.loads(UPDATE.read_text(encoding='utf-8'))

def apply_data(data, update):
    if data.get('quality_update_revision') == update['revision']:
        return data
    if update['schema'] != 'authorized_quality_input_update_v1':
        raise ValueError('quality_update_schema')
    source=(ROOT/update['return_source']).resolve()
    if not source.is_relative_to(ROOT.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=update['return_sha256']:
        raise ValueError('review_return_hash')
    original=json.loads(source.read_text(encoding='utf-8'))
    if any(original['records'].get(k)!=v for k,v in update['accepted_records'].items()):
        raise ValueError('review_return_record_drift')
    from tools.thesis_main.analysis.final_review_summary_20260929 import geometry_status
    byid = {o['object_id']: o for o in data['objects']}
    if len(byid) != len(data['objects']):
        raise ValueError('duplicate_source_object')
    if len(update['accepted_records']) != 14:
        raise ValueError('accepted_review_population')
    for rid, d in update['accepted_records'].items():
        ident = d['identity']; oid = ident['canonical_object_id']; o = byid[oid]
        if d['status'] != 'completed' or d['base_version'] != 'raw':
            raise ValueError('uncompleted_or_nonraw_review:' + rid)
        if o['image_id'] != ident['image_id'] or any(o['source'][k] != ident[k] for k in ('project','task','annotation')):
            raise ValueError('review_source_identity:' + rid)
        if o['worker_id'] in {'W019','W026'} or o['object_kind'] != 'annotation':
            raise ValueError('excluded_worker_or_reference:' + rid)
        base = d['base_points']; raw = o['original_export_points']
        if [[p['x'],p['y']] for p in base] != raw:
            raise ValueError('review_raw_coordinate_drift:' + rid)
        for i,p in enumerate(base):
            if p['id'] != f'{oid}::original_export_points[{i}]' or p['source_index'] != i:
                raise ValueError('review_raw_point_identity:' + rid)
        # This accepted return has only deletions, pair candidates and order edits.
        # Reconstruct deletions/undo and reject undeclared point edits.
        state = copy.deepcopy(base); pairs=[]; history=[]
        for op in d['operations']:
            if op['type'] == 'undo':
                if not history or op.get('undo_of') != history[-1][0]: raise ValueError('undo_identity:'+rid)
                _,state,pairs=history.pop(); continue
            history.append((op['operation_id'],copy.deepcopy(state),copy.deepcopy(pairs)))
            if op['type'] == 'delete':
                p=next(p for p in state if p['id']==op['point_id'])
                if op['before'] != {'x':p['x'],'y':p['y']} or p.get('deleted'): raise ValueError('delete_binding:'+rid)
                p['deleted']=True; pairs=[p for p in pairs if op['point_id'] not in p]
            elif op['type']=='pair_x': pairs += op['pairs']
            elif op['type']=='pair': pairs.append(op['pair'])
            elif op['type']=='unpair': pairs.remove(op['pair'])
            elif op['type']=='order':
                order=op['order']
                if sorted(order)!=list(range(len(pairs))): raise ValueError('order_permutation:'+rid)
                pairs=[pairs[i] for i in order]
            else: raise ValueError('unsupported_review_operation:'+op['type'])
            if pairs != op['pairs_after']: raise ValueError('operation_pair_replay:'+rid)
        if state != d['points'] or pairs != d['pairs']: raise ValueError('review_replay_mismatch:'+rid)
        active=[p for p in state if not p.get('deleted')]; ix={p['id']:i for i,p in enumerate(active)}
        flat=[i for pair in pairs for i in pair]
        if len(flat)!=len(set(flat)) or set(flat)!=set(ix) or any(len(p)!=2 for p in pairs):
            raise ValueError('incomplete_review_pairing:'+rid)
        before=[[p['x'],p['y']] for p in active]
        if any(not all(math.isfinite(v) for v in p) or not(0<=p[0]<1024 and 0<=p[1]<=512) for p in before):
            raise ValueError('review_bounds:'+rid)
        links=[[ix[a],ix[b]] for a,b in pairs]; processed=copy.deepcopy(before)
        for top,bottom in links:
            if before[top][1]>=before[bottom][1]: raise ValueError('review_top_bottom:'+rid)
            delta=(before[bottom][0]-before[top][0]+512)%1024-512
            if abs(delta)>=512-1e-8: raise ValueError('ambiguous_pair_midpoint:'+rid)
            processed[top][0]=processed[bottom][0]=(before[top][0]+delta/2)%1024
        o['review_update_previous_geometry']={k:copy.deepcopy(o[k]) for k in ('preprocessing_status','pairing_basis','geometry','order_status')}
        o.update(before_preprocessing_points=before,preprocessed_points=processed,links_zero_based=links,
                 point_labels=[p['label'] for p in active],original_export_indices=[p['source_index'] for p in active],
                 deleted_previous_point_indices=[p['source_index'] for p in state if p.get('deleted')],
                 preprocessing_status='ready',pairing_basis='user_completed_point_review_20261010',
                 order_status='human_confirmed',ring_confirmed=True)
        order=list(range(len(links)));indices=[i for pair in links for i in pair]
        o.update(ordered_source_pair_indices=order,ordered_source_point_indices=indices,
                 ordered_source_point_labels=[o['point_labels'][i] for i in indices],
                 points_1024x512=[processed[i] for i in indices],matterport_links_zero_based=[[i,i+1] for i in range(0,len(indices),2)])
        binding=dict(id=oid,points=processed,labels=o['point_labels'],links=links,preprocessing=o['preprocessing'])
        o['order_record']=dict(binding=json.dumps(binding,ensure_ascii=False),order=order,status='confirmed',
            note=d['note'],cause='completed_review_formal_adoption_20261010',updated_at=d['updated_at'])
        o['order_origins']=['user_completed_point_review_20261010']
        o['geometry']=geometry_status(o,order)
        o['method_evaluability']='not_assessed_per_method'
        o['quality_review_provenance']=dict(record_id=rid,source=update['return_source'],source_sha256=update['return_sha256'],authorization=update['authorization_message_id'])
        old=o['repair_evidence']; old=old if isinstance(old,list) else [old]
        o['repair_evidence']=old+[dict(status='applied',source=update['return_source'],operations=copy.deepcopy(d['operations']),eligibility_changed=False)]
    policies={p['image_code']:p for p in update['image_decisions']}
    for im in data['images']:
        if im['image_code'] in policies: im['quality_review_20261010']=copy.deepcopy(policies[im['image_code']])
    for o in data['objects']:
        p=policies.get(o['image_code'])
        if not p: continue
        o['quality_review_20261010']=copy.deepcopy(p)
        if o['object_kind']=='annotation' and p.get('quality_reference_hold') and o['worker_quality_gate']!='excluded':
            o['quality_gate_before_20261010']=copy.deepcopy(o['main_quality_gate'])
            o['worker_quality_gate']='hold_reference_quality'
            o['main_quality_gate']=dict(status='hold_reference_quality',reasons=['user_reported_gt_issue_20261010'])
    annotations=[o for o in data['objects'] if o['object_kind']=='annotation']
    data['summary']['confirmed_orders']=sum(o['ring_confirmed'] for o in data['objects'])
    data['summary']['worker_quality_gate']=dict(Counter(o['worker_quality_gate'] for o in annotations))
    for im in data['images']:
        group=[o for o in annotations if o['image_id']==im['image_id']]
        if group:
            im['order_counts']=dict(Counter(o['order_status'] for o in group))
            im['quality_gate_counts']=dict(Counter(o['worker_quality_gate'] for o in group))
            im['geometry_counts']=dict(Counter(o['geometry']['status'] for o in group))
    data['quality_update_revision']=update['revision']
    data['quality_research_policy']=copy.deepcopy(update['confirmed_policy'])
    return data

def apply_bundle(loaded, update):
    data=apply_data(loaded['data'],update); objs={o['object_id']:o for o in data['objects']}
    research=loaded['research']
    for r in research['annotations']:
        o=objs[r['object_id']]
        for k in ('worker_quality_gate','main_quality_gate','order_status','method_evaluability'):
            r[k]=copy.deepcopy(o[k])
        r['geometry_status']=o['geometry']['status'];r['geometry_issues']=o['geometry']['issues']
        if o.get('quality_review_provenance'):
            r['order_change']='new_pairing_and_reviewed_order'
            r['order_change_evidence']=copy.deepcopy(o['quality_review_provenance'])
        if 'quality_review_20261010' in o: r['quality_review_20261010']=copy.deepcopy(o['quality_review_20261010'])
    image_map={im['image_id']:im for im in data['images']}
    for r in research['images']:
        group=[a for a in research['annotations'] if a['image_id']==r['image_id']]
        r['order_counts']=dict(Counter(a['order_status'] for a in group))
        r['quality_gate_counts']=dict(Counter(a['worker_quality_gate'] for a in group))
        r['geometry_counts']=dict(Counter(a['geometry_status'] for a in group))
        im=image_map[r['image_id']]
        im['order_counts']=copy.deepcopy(r['order_counts'])
        im['quality_gate_counts']=copy.deepcopy(r['quality_gate_counts'])
        im['geometry_counts']=copy.deepcopy(r['geometry_counts'])
        if 'quality_review_20261010' in im:r['quality_review_20261010']=copy.deepcopy(im['quality_review_20261010'])
    for name,table in research['cross_tables'].items():
        if not table:continue
        if name=='order_changes_by_kind':
            added=[o['object_id'] for o in data['objects'] if o.get('quality_review_provenance')]
            table.append(dict(dimensions=dict(object_kind='annotation',change='new_pairing_and_reviewed_order'),n=len(added),ids=added))
            continue
        fields=list(table[0]['dimensions']);items=research['images'] if name in {'gt_marks','scene_images'} else research['annotations']
        old_ids={i for row in table for i in row['ids']}
        items=[r for r in items if r.get('object_id',r.get('image_id')) in old_ids]
        key='image_id' if name in {'gt_marks','scene_images'} else 'object_id'
        groups=defaultdict(list)
        for r in items:groups[tuple(r[k] for k in fields)].append(r[key])
        research['cross_tables'][name]=[dict(dimensions=dict(zip(fields,k)),n=len(v),ids=v) for k,v in sorted(groups.items(),key=lambda x:str(x[0]))]
    research['summary']['confirmed_order_objects']=data['summary']['confirmed_orders']
    research['quality_update_revision']=update['revision']
    research['summary']['retained_geometry']=dict(Counter(r['geometry_status'] for r in research['annotations'] if r['cleaning_disposition'] in {'retained','retained_pending'}))
    research['quality_research_policy']=copy.deepcopy(update['confirmed_policy'])
    final=loaded['final_summary']
    final['confirmed_orders']=data['summary']['confirmed_orders']
    anns=[o for o in data['objects'] if o['object_kind']=='annotation']
    final['geometry']=dict(Counter(o['geometry']['status'] for o in anns))
    final['retained_geometry']=copy.deepcopy(research['summary']['retained_geometry'])
    final['historical_annotation_order_states']=final.pop('annotation_order_states',{})
    final['current_order_status_counts']=dict(Counter(o['order_status'] for o in anns))
    final['quality_update_revision']=update['revision']
    final.setdefault('batches',[]).append(dict(batch='authorized_point_review_20261010',objects=14,images=8))
    for o in data['objects']:
        if o.get('quality_review_provenance'):
            loaded['final_orders']['records'][o['object_id']]=o['order_record']
            loaded['final_orders'].setdefault('origins',{})[o['object_id']]=o['order_origins']
    return loaded
