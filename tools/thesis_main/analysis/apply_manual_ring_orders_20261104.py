"""Apply returned orders to fixed saved nodes, keeping automatic results separate.

This module never invokes fusion/build, selects nodes, changes coordinates,
chooses a reference from scores, or refits personnel classes.  Its output is a
targeted human-assisted sensitivity version of 57 saved endpoint identities.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/fusion/missing_ring_review_20261104'
RETURN = SOURCE / 'user_order_return'
OUT = ROOT / 'research/fusion/manual_order_impact_20261104/endpoints'
VERSION = 'v21_targeted_manual_order_assisted_20261104_v1'
BASE_COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
REASON = 'no_source_ring_covering_all_selected_nodes'
COMPONENTS = ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if str(path).endswith('.gz')
          else open(path, encoding='utf-8-sig')) as stream:
        return json.load(stream)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def digest(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True,
                                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                               allow_nan=False) + '\n', encoding='utf-8')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def saved_state(case, order=None):
    """Reassemble only frozen selected groups; restore source projections exactly.

    Unselected original observations receive explicit unique placeholders. They
    are removed by the existing source_ring projection and cannot affect node
    inclusion, locations, votes, or an approved order.  No identity clustering
    or coordinate median is rerun here.
    """
    from .ring_correspondence_20261007 import assemble_fusion
    nodes = deepcopy(case['nodes'])
    records = case['records']
    assert len(records) == case['k']
    assert len({r['id'] for r in records}) == len(records)
    assert len({str(r['worker']) for r in records}) == len(records)
    by_record = {r['id']: r for r in records}
    groups = []
    selected_lookup = {}
    for node in nodes:
        assert node['support'] == len(node['members'])
        assert node['support'] >= math.ceil(case['k'] / 2)
        assert len({str(m['worker']) for m in node['members']}) == node['support']
        assert np.asarray(node['points']).shape == (2, 2)
        assert np.isfinite(np.asarray(node['points'], float)).all()
        for member in node['members']:
            r = by_record[member['id']]
            assert str(member['worker']) == str(r['worker'])
            assert 0 <= member['pair_index'] < len(r['points']) // 2
            key = (member['id'], member['pair_index'])
            assert key not in selected_lookup
            selected_lookup[key] = node['feature_id']
        groups.append(dict(feature_id=node['feature_id'], selected=True,
                           support=node['support'], center=deepcopy(node['points']),
                           members=deepcopy(node['members'])))
    assignments = []
    for r in records:
        assert len(r['points']) % 2 == 0
        ids = [selected_lookup.get((r['id'], i), f'unselected:{r["id"]}:{i}')
               for i in range(len(r['points']) // 2)]
        assignments.append(dict(id=r['id'], worker=r['worker'], feature_ids=ids))
    result = assemble_fusion(groups, assignments, order)
    assert result['node_consensus']['nodes'] == nodes, 'Frozen node binding changed'
    original_ring = case['ring_diagnostics']
    assert original_ring['reason'] == REASON
    assert result['ring_diagnostics']['reason'] == REASON
    assert not result['ring_diagnostics']['feature_ids']
    # Preserve the original full diagnostic, not the placeholder provenance.
    result['ring_diagnostics'] = deepcopy(original_ring)
    result.update(n=case['k'], minimum_support=math.ceil(case['k']/2),
                  identity_groups=groups, assignments=assignments)
    if order is not None:
        result['candidate']['order_status'] = 'human_reviewed_order'
    return result


def diagnostic_modules():
    """Reuse pure diagnostics without instantiating or running a fusion engine."""
    from .paired_split_research.study import angular
    comp = ROOT / 'research/workers/personnel_interchangeability_20261020/analysis/composition'
    global_comp = ROOT / 'research/workers/personnel_global_composition_20261021/composition'
    sys.path[:0] = [str(comp), str(global_comp)]
    fr = module('fusion_runner', comp / 'fusion_runner.py')
    fr.FE = SimpleNamespace(angular=angular)
    sg = module('manual_order_frozen_signature', comp / 'summarize_grid.py')
    prefix = module('manual_order_frozen_prefix', ROOT / 'research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py')
    os.environ['HOHONET_REPO'] = str(ROOT)
    native = module('manual_order_frozen_expression', ROOT / 'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py')
    return fr, sg, prefix, native


def evaluate(state, reference, engine, models, helpers, identity):
    from .wall_consensus_population_20261014 import summarize_state
    from .wall_consensus_quality_20261015 import measured
    from .quality_b8l2_d10_20261017 import dual_scores
    fr, sg, prefix, native = helpers
    row = dict(identity, **summarize_state(state), geometry=deepcopy(state['candidate']))
    result = measured(engine, state, dict(floor=reference['floor_xz_h'],
                                         points=reference['points_1024x512']))
    if all(result.get(k) is not None and math.isfinite(float(result[k])) for k in COMPONENTS):
        result.update(dual_scores(result, models))
        values = [result[k] for k in COMPONENTS]
        for name, parameter in models.MODELS.items():
            result[name] = float(models.score(*values, parameter))
        assert abs(result['WQ'] - engine.score(result)['WQ']) < 1e-10
    else:
        result.update(B8L2=None, D10=None, A10=None)
    row.update(result)
    row.update(native.expression(row['geometry']))
    row = prefix.geometry_enrich(row, dict(reference=reference), fr)
    sig = sg.signature(row, reference['floor_xz_h'])
    row.update({k: v for k, v in sig.items() if k.startswith('diag_')})
    poly = sig.get('floor')
    if poly is not None:
        row.update(geometry_area_h2=poly.area, centroid_x_h=poly.centroid.x,
                   centroid_z_h=poly.centroid.y)
        row['bounds_min_x_h'], row['bounds_min_z_h'], row['bounds_max_x_h'], row['bounds_max_z_h'] = poly.bounds
    row.update(score_available=row.get('B8L2') is not None,
               policy_deferred=False,
               score_failure_nonpolicy=row.get('B8L2') is None,
               incomplete_nonpolicy=not row['complete_evaluable'],
               minimum_support=state['minimum_support'],
               selected_support_min=min(n['support']/state['n'] for n in state['node_consensus']['nodes']),
               selected_node_support_mean=float(np.mean([n['support']/state['n'] for n in state['node_consensus']['nodes']])),
               reference_nodes=len(reference['points_1024x512'])//2,
               reference_node_shortfall=max(0,len(reference['points_1024x512'])//2-len(state['node_consensus']['nodes'])),
               node_supports=[n['support'] for n in state['node_consensus']['nodes']])
    return clean(row)


def load_references():
    path = ROOT / 'research/data/releases/v2.1/reference_catalog.json'
    result = {}
    for r in read(path):
        key = (r['target_id'], r['reference_version'])
        assert key not in result
        result[key] = r
    return result, path


def load_current_pools():
    paths = [ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
             ROOT/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
    result={}
    for path in paths:
        for pool in read(path)['images']:
            assert pool['pool_id'] not in result
            result[pool['pool_id']] = (pool,path)
    return result


def verify_current_pool(case, pools, reference):
    pid=case['team_key'].rsplit('__',1)[0]
    pool,path=pools[pid]
    for field in ('target_id','reference_version','points_1024x512','floor_xz_h'):
        assert pool['reference'][field] == reference[field], (pid,field,'Reference differs from actual consumer pool')
    byid={r['id']:r for r in pool['records']}
    for record in case['records']:
        current=byid[record['id']]
        assert str(current['worker'])==str(record['worker'])
        assert current['points']==record['points'],(pid,record['id'],'Source points changed')
    assert pool['meta']['reference_id']==case['reference_id']
    assert pool['meta']['reference_version']==case['reference_version']
    return dict(pool_id=pid,source=path.relative_to(ROOT).as_posix(),
                records=len(case['records']),raw_record_coordinates_exact=True,
                reference_coordinates_exact=True,reference_metadata_exact=True)


def reference_contexts(case, links):
    base = (case['reference_id'], case['reference_version'])
    assert all(isinstance(v, str) and v for v in base), ('Missing prepared reference binding', case['review_id'])
    contexts = {base}
    rows = []
    for r in links.to_dict('records'):
        rid = r.get('reference_id')
        ver = r.get('reference_version')
        rid = rid if isinstance(rid, str) and rid else base[0]
        ver = ver if isinstance(ver, str) and ver else base[1]
        contexts.add((rid, ver))
        r.update(resolved_reference_id=rid, resolved_reference_version=ver,
                 reference_binding_source='explicit_current_reference' if pd.notna(r.get('reference_id')) else 'exact_prepared_endpoint_reference')
        rows.append(r)
    return sorted(contexts), rows


def geometry_details(geometry, feature_order):
    """Record degeneracy and crossing witnesses without proposing another order."""
    from shapely.geometry import LineString, Polygon
    from shapely.validation import explain_validity
    floor = geometry.get('floor')
    result = dict(polygon_validation=None, minimum_edge_length_h=None,
                  nonadjacent_intersections=[])
    if floor is None or len(floor) < 3:
        return result
    p = np.asarray(floor, float)
    poly = Polygon(p)
    result['polygon_validation'] = explain_validity(poly)
    edges = np.roll(p, -1, axis=0)-p
    result['minimum_edge_length_h'] = float(np.linalg.norm(edges,axis=1).min())
    for i in range(len(p)):
        for j in range(i+1, len(p)):
            if (i-j) % len(p) in (1, len(p)-1):
                continue
            a = LineString([p[i],p[(i+1)%len(p)]])
            b = LineString([p[j],p[(j+1)%len(p)]])
            if a.intersects(b):
                result['nonadjacent_intersections'].append(dict(
                    first_edge_0based=i,second_edge_0based=j,
                    first_nodes=[feature_order[i],feature_order[(i+1)%len(p)]],
                    second_nodes=[feature_order[j],feature_order[(j+1)%len(p)]],
                    intersection_wkt=a.intersection(b).wkt))
    return result


def verify_score_parity(destination=OUT):
    """Check the installed environment against two saved scored geometries."""
    from .scope_quality_scoring_20261016 import scoring_engine
    from .wall_consensus_quality_20261015 import measured
    from .quality_b8l2_d10_20261017 import dual_scores
    refs, _ = load_references()
    paths = [ROOT/'research/data/releases/v2.1/q_only_exchange_20261031/ENDPOINTS.jsonl.gz',
             ROOT/'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031/REUSED_ENDPOINTS.jsonl.gz']
    chosen = {}
    for path in paths:
        if not path.exists():
            continue
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:
            for line in stream:
                r = json.loads(line)
                if r.get('B8L2') is None or r.get('D10') is None or not r.get('geometry'):
                    continue
                key = (r['reference_id'], r['reference_version'])
                if key not in refs or r['geometry'].get('points') is None:
                    continue
                kind = 'gt_original' if key[1]=='gt_original' else 'adopted_reference'
                chosen.setdefault(kind,(r,path))
                if len(chosen)==2:
                    break
        if len(chosen)==2:
            break
    assert len(chosen)==2, 'Two distinct saved original/adopted reference geometries required for parity'
    checks=[]
    with scoring_engine() as (engine,models):
        for kind,(old,path) in chosen.items():
            ref=refs[(old['reference_id'],old['reference_version'])]
            n=old.get('nodes') or len(old['geometry']['points'])//2
            state=dict(n=old['k'],candidate=old['geometry'],node_consensus=dict(nodes=[None]*n))
            new=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
            assert all(new.get(k) is not None for k in COMPONENTS)
            new.update(dual_scores(new,models))
            for metric in list(COMPONENTS)+['B8L2','D10','IoU3D100','WQ','omission','extension','height_mean_ratio','boundary_loss','direction_loss','height_loss']:
                if old.get(metric) is None or new.get(metric) is None:
                    continue
                delta=abs(float(new[metric])-float(old[metric]))
                assert delta<1e-7,(old['team_key'],metric,old[metric],new[metric])
                checks.append(dict(kind=kind,team_key=old['team_key'],reference_id=old['reference_id'],
                                   reference_version=old['reference_version'],metric=metric,
                                   saved=float(old[metric]),recomputed=float(new[metric]),absolute_difference=delta,
                                   tolerance=1e-7,passed=True,source=path.relative_to(ROOT).as_posix()))
    destination.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(checks).to_csv(destination/'SCORING_ENVIRONMENT_PARITY.csv',index=False,encoding='utf-8-sig')
    import importlib.metadata
    write_json(destination/'SCORING_ENVIRONMENT.json',dict(
        python=sys.version,packages={name:importlib.metadata.version(name) for name in ['numpy','scipy','pandas','shapely','opencv-python-headless']},
        saved_endpoints=2,comparisons=len(checks),max_absolute_difference=max(r['absolute_difference'] for r in checks),
        passed=True,scope='Only rescoring two existing scored geometries; zero fusion calls'))
    return checks


def run(destination=OUT):
    from .scope_quality_scoring_20261016 import scoring_engine
    from .research_round_20260929 import reconstruct
    from .quality_b8l2_d10_20261017 import model_parameters
    destination.mkdir(parents=True, exist_ok=True)
    orders = pd.read_csv(RETURN/'VALIDATED_ENDPOINT_ORDERS.csv.gz')
    links = pd.read_csv(RETURN/'AFFECTED_CURRENT_REFERENCES.csv.gz', low_memory=False)
    original_export = read(RETURN/'融合节点排序_全部图片.json')
    receipt = read(RETURN/'IMPORT_RECEIPT.json')
    assert len(orders) == receipt['validated_endpoint_identities'] == 57
    assert orders.team_key.is_unique and orders.review_id.is_unique
    assert orders.application_status.eq('validated_not_applied').all()
    references, reference_path = load_references()
    pools = load_current_pools()
    helpers = diagnostic_modules()
    outputs, checks, bindings = [], [], []
    score_rows, geometry_rows = [], []
    with scoring_engine() as (engine, models):
        parameter_snapshot={name:asdict(value) for name,value in zip(('B8L2','D10'),model_parameters(models))}
        for ordinal, order_row in enumerate(orders.to_dict('records'), 1):
            source = SOURCE/'prepared'/(order_row['review_id']+'.json.gz')
            case = read(source)
            assert case['team_key'] == order_row['team_key']
            assert case['image'] == order_row['image']
            nodes = json.loads(order_row['order_binding'])
            assert nodes == case['nodes'], 'Previously validated node data changed'
            order = order_row['manual_feature_order'].split('|')
            user = original_export['records']['missing_ring:'+case['review_id']]
            assert user['status'] == 'confirmed'
            assert [nodes[i]['feature_id'] for i in user['order']] == order
            before_hash = digest(case)
            automatic_state = saved_state(case)
            assisted_state = saved_state(case, order)
            assert digest(case) == before_hash
            assert automatic_state['node_consensus'] == assisted_state['node_consensus']
            assert automatic_state['candidate']['points'] is None
            assert assisted_state['candidate']['points'] == [p for fid in order for n in nodes if n['feature_id']==fid for p in n['points']]
            # Retain the detailed reconstruction result (crossing/degeneracy etc.),
            # in addition to the historical compact candidate geometry.
            geom_audit = reconstruct(assisted_state['candidate'], coordinate_convention='continuous')
            geom_audit.update(geometry_details(geom_audit, order))
            contexts, contextual_links = reference_contexts(case, links[links.team_key.eq(case['team_key'])])
            bindings.extend(contextual_links)
            ws = sorted(str(r['worker']) for r in case['records'])
            ids = sorted(str(r['id']) for r in case['records'])
            for reference_id, reference_version in contexts:
                assert (reference_id, reference_version) in references, (case['review_id'], reference_id, reference_version, 'Reference version absent')
                ref = references[(reference_id, reference_version)]
                assert ref['image_id'] == case['image_id']
                # These returned cases each have one actual reference context.
                # A future multi-reference binding must use its own explicit pool.
                pool_check=verify_current_pool(case,pools,ref)
                ref_hash = digest(ref)
                identity = dict(team_key=case['team_key'], review_id=case['review_id'],
                                group_id=order_row['group_id'], image=case['image'],
                                image_id=case['image_id'], building=case['image'].split('-')[0],
                                condition=case['condition'], k=case['k'],
                                pool_id=case['team_key'].rsplit('__',1)[0],
                                reference_id=reference_id, reference_version=reference_version,
                                data_release='v2.1', member_workers=ws, member_object_ids=ids)
                auto = evaluate(automatic_state, ref, engine, models, helpers, identity)
                new = evaluate(assisted_state, ref, engine, models, helpers, identity)
                assert auto['B8L2'] is None and auto['D10'] is None and auto['score_status']=='no_connection'
                assert ref_hash == digest(ref)
                new.update(analysis_version=VERSION, fusion_version='MV50_gap7.5_fixed_nodes_human_order',
                           original_source_data_release=case.get('data_release'),
                           method_relation='separate_targeted_human_assisted_sensitivity',
                           automatic_B8L2=auto['B8L2'], automatic_D10=auto['D10'],
                           automatic_score_status=auto['score_status'],
                           automatic_complete_evaluable=auto['complete_evaluable'],
                           automatic_connection_available=auto['connection_available'],
                           connection_changed=True, original_scored_support=False,
                           new_scored_support=new['score_available'],
                           paired_Q_change=None, support_change='newly_evaluable' if new['score_available'] else 'still_unscored',
                           human_labor_seconds=None, original_annotation_labor_changed=False,
                           source_prepared=source.relative_to(ROOT).as_posix(),
                           source_order=(RETURN/'VALIDATED_ENDPOINT_ORDERS.csv.gz').relative_to(ROOT).as_posix(),
                           source_reference=reference_path.relative_to(ROOT).as_posix(),
                           source_current_pool=pool_check['source'],
                           original_sources=case['sources'])
                joined = dict(new, automatic=auto, assisted=deepcopy(new),
                              fixed_nodes=deepcopy(nodes), automatic_source_ring=deepcopy(case['ring_diagnostics']),
                              manual_feature_order=order, geometry_check=clean(geom_audit),
                              reference_snapshot=deepcopy(ref), source_records=deepcopy(case['records']))
                outputs.append(clean(joined))
                scalar = {k: v for k, v in new.items() if not isinstance(v, (dict, list))}
                scalar.update(member_workers='|'.join(ws), member_object_ids='|'.join(ids),
                              node_supports='|'.join(str(n['support']) for n in nodes),
                              manual_feature_order='|'.join(order),
                              automatic_geometry_status=auto['geometry_status'],
                              geometry_check_reason=geom_audit.get('reason'),
                              geometry_polygon_validation=geom_audit.get('polygon_validation'),
                              geometry_nonadjacent_intersections=len(geom_audit['nonadjacent_intersections']),
                              geometry_polygon_valid=geom_audit.get('polygon_valid'),
                              geometry_camera_relation=geom_audit.get('camera_relation'),
                              geometry_camera_in_visible_kernel=geom_audit.get('camera_in_visible_kernel'))
                for field in ('ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9'):
                    scalar[field] = json.dumps(new.get(field), ensure_ascii=False)
                score_rows.append(scalar)
                geometry_rows.append(dict(team_key=case['team_key'],reference_id=reference_id,reference_version=reference_version,
                                          original_geometry=json.dumps(auto['geometry'],ensure_ascii=False),
                                          assisted_geometry=json.dumps(new['geometry'],ensure_ascii=False),
                                          geometry_check=json.dumps(clean(geom_audit),ensure_ascii=False)))
                checks.append(dict(team_key=case['team_key'],review_id=case['review_id'],reference_id=reference_id,reference_version=reference_version,
                                   nodes_fixed=True,coordinates_fixed=True,votes_fixed=True,team_fixed=True,
                                   source_records_fixed=True,reference_fixed=True,order_exactly_once=True,
                                   current_pool_raw_coordinates_exact=True,current_pool_reference_coordinates_exact=True,
                                   automatic_no_connection_reproduced=True,raw_fusion_calls=0,
                                   node_count=len(nodes),team_size=case['k'],new_score_available=new['score_available'],
                                   complete_evaluable=new['complete_evaluable'],score_status=new['score_status'],
                                   geometry_status=new['geometry_status'],geometry_reason=geom_audit.get('reason'),
                                   source_case_sha256=before_hash,reference_semantic_sha256=ref_hash))
            print(f'fixed-node assisted endpoint {ordinal}/{len(orders)}: {case["image"]}', flush=True)
    frame = pd.DataFrame(score_rows)
    assert not frame.duplicated(['team_key','reference_id','reference_version']).any()
    frame.to_csv(destination/'ENDPOINT_SCORES.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(geometry_rows).to_csv(destination/'ENDPOINT_GEOMETRY.csv.gz',index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0})
    pd.DataFrame(checks).to_csv(destination/'FIXED_INPUT_CHECKS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(bindings).to_csv(destination/'ENDPOINT_REFERENCE_BINDINGS.csv',index=False,encoding='utf-8-sig')
    with gzip.open(destination/'ENDPOINTS.jsonl.gz','wt',encoding='utf-8') as stream:
        for row in outputs:
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    frame[~frame.score_available].to_csv(destination/'UNSCORED_REASONS.csv',index=False,encoding='utf-8-sig')
    result=dict(analysis_version=VERSION,source_repository_commit=BASE_COMMIT,
                approved_geometry_groups=len(orders),unique_team_identities=orders.team_key.nunique(),images=orders.image.nunique(),
                score_contexts=len(frame),automatic_scored=0,assisted_scored=int(frame.score_available.sum()),
                assisted_complete_geometry=int(frame.complete_evaluable.sum()),
                assisted_status_counts=frame.score_status.value_counts().to_dict(),
                geometry_status_counts=frame.geometry_status.value_counts().to_dict(),
                score_min=frame.B8L2.min(),score_median=frame.B8L2.median(),score_max=frame.B8L2.max(),
                raw_fusion_calls=0,new_identity_clustering_calls=0,new_node_selection_calls=0,
                original_outputs_modified=False,reference_changed=False,personnel_labels_changed=False,
                fixed_checks_passed=all(all(r[k] for k in ('nodes_fixed','coordinates_fixed','votes_fixed','team_fixed','reference_fixed','source_records_fixed','order_exactly_once','automatic_no_connection_reproduced')) for r in checks),
                interpretation='Targeted support extension from no_connection; unavailable old Q is not zero. No claim about all no-ring cases.',
                measurement_function='wall_consensus_quality_20261015.measured; quality_b8l2_d10_20261017.dual_scores',
                reconstruction_function='ring_correspondence_20261007.assemble_fusion -> research_round_20260929.reconstruct(continuous)')
    write_json(destination/'CHECKS.json',result)
    write_json(destination/'SCORING_PARAMETERS.json',parameter_snapshot)
    write_json(destination/'FIELD_CONTRACT.json',dict(key=['team_key','reference_id','reference_version'],
        unprefixed_fields='assisted endpoint, compatible original scalar names; join all identity fields',
        automatic_fields='original no-connection endpoint remains unavailable and unmodified',
        state_provenance='fixed selected nodes and raw source ring projection reassembled; no raw fusion replay',
        labor='Original annotation labor is unchanged; human ordering duration is unrecorded, not zero',
        full_json='ENDPOINTS.jsonl.gz retains automatic/assisted/fixed_nodes/source_records/reference_snapshot',
        missing='None/blank only; do not substitute zero or calculate paired improvement for unavailable automatic Q'))
    print(json.dumps(clean(result),ensure_ascii=False),flush=True)
    return clean(result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--parity-only',action='store_true')
    args=parser.parse_args()
    if args.parity_only:
        verify_score_parity(args.out)
    else:
        run(args.out)
