"""Build trace-backed case facts without invoking fusion or scoring.

All numbers are copied from frozen selected cases or computed directly from
their saved source observations/geometry. Core endpoints are never edited.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path


def read(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def csvwrite(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')) if isinstance(value, (list, dict)) else value


def ring_covers(assignment, selected):
    projected = [x for x in assignment['feature_ids'] if x in selected]
    return len(selected) >= 3 and len(projected) == len(selected) and set(projected) == selected


def endpoint_fact(t):
    s = t['full_state']
    groups = s['identity_groups']
    selected = {g['feature_id'] for g in groups if g['selected']}
    edges = s['ring_diagnostics'].get('edges', [])
    known = [x for x in s['assignments'] if ring_covers(x, selected)]
    return {
        'team_key': t['team_key'], 'n': t['k'], 'score_status': t['score_status'],
        'B8L2': t.get('B8L2'), 'D10': t.get('D10'),
        'reference_nodes': t['reference_nodes'], 'all_groups_n': len(groups),
        'selected_n': len(selected), 'unselected_n': len(groups)-len(selected),
        'minimum_support': t['minimum_support'],
        'all_groups_unanimous': all(g['support'] == t['k'] for g in groups),
        'all_selected_locations_resolved': all(g['center'] is not None for g in groups if g['selected']),
        'complete_projected_source_rings_n': len(known),
        'complete_projected_source_ring_workers': [x['worker'] for x in known],
        'native_ring_reason': s['ring_diagnostics'].get('reason'),
        'native_candidate_reason': s['candidate'].get('reason'),
        'edge_n': len(edges),
        'edge_direct_supports': [x['direct_support'] for x in edges],
        'edge_projected_supports': [x['projected_support'] for x in edges],
        'all_edges_unanimous': all(x['direct_support'] == t['k'] and x['projected_support'] == t['k'] for x in edges) if edges else False,
        'location_policy': s['node_consensus']['location_policy'],
        'record_time_by_kind': json.loads(t['record_time_by_kind_json']),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    a = ap.parse_args()
    root = Path(a.root)
    dirs = ['alliance_pa4_06', 'alliance_pa4_11', 'background_wc2_53', 'representative_cases']
    all_events, all_teams, all_groups, all_sources = [], {}, [], []
    compact_keys = ['B8L2', 'D10', 'IoU3D100', 'S_bottom_deg', 'dir', 'Hmean',
                    'boundary_loss', 'direction_loss', 'height_loss', 'nodes', 'fusion_turn_n',
                    'fusion_short_turn_edges', 'ref_node_recall_5', 'ref_edge_recall_5',
                    'ref_node_recall_9', 'ref_edge_recall_9', 'geometry_area_h2', 'height_mean_h',
                    'centroid_x_h', 'centroid_z_h', 'score_status']
    case_objects = {}
    manifest = []
    for directory in dirs:
        r = root / directory
        minimal = r / 'minimal_inputs'
        minimal.mkdir(exist_ok=True)
        local_endpoints = {}
        originals_by_pool = {}
        for path in sorted((r / 'traces').glob('*.json.gz')):
            d = read(path)
            event = d['event']; eid = event['event_id']; case_objects[eid] = d
            manifest.append({'path': str(path.relative_to(root)), 'sha256': digest(path)})
            row = {k: event.get(k) for k in ['event_id', 'pool_id', 'image', 'method', 'n_A', 'n_C',
                'm_X', 'm_Z', 'source_class', 'target_class', 'source_class_available_n',
                'target_class_available_n', 'whole_source', 'whole_target', 'design_family',
                'D_workers', 'X_workers', 'Z_workers', 'A_team_key', 'C_team_key']}
            row['case_directory'] = directory
            for arm in ['A', 'C']:
                t = d['arms'][arm]
                for k in compact_keys:
                    row[arm+'_'+k] = t.get(k)
                for k in ['complete_projected_source_rings_n', 'all_groups_n', 'unselected_n', 'minimum_support']:
                    row[arm+'_'+k] = endpoint_fact(t)[k]
                if t['team_key'] not in all_teams:
                    all_teams[t['team_key']] = endpoint_fact(t)
                    all_teams[t['team_key']]['case_directory'] = directory
                    for g in t['full_state']['identity_groups']:
                        all_groups.append({'case_directory':directory,'team_key':t['team_key'],
                            'feature_id':g['feature_id'],'n':t['k'],'minimum_support':t['minimum_support'],
                            'selected':g['selected'],'support':g['support'],
                            'center':scalar(g['center']),
                            'workers':'|'.join(x['worker'] for x in g['members']),
                            'exact_original_observations':scalar([{'object_id':x['id'],'source_pair_index':x['source_pair_index']} for x in g['members']])})
                local_endpoints[t['team_key']] = t
            for key in compact_keys:
                av, cv = d['arms']['A'].get(key), d['arms']['C'].get(key)
                if isinstance(av, (float,int)) and isinstance(cv, (float,int)):
                    row[key+'_C_minus_A'] = cv-av
            for k in ['geometry_bev_distance_AC','geometry_centroid_distance_AC',
                      'time_comparable_source_count_AC','time_comparable_single_source_AC',
                      'record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched',
                      'record_time_CA_seconds_single_source','record_time_CA_pct_single_source']:
                row[k] = d['metrics'].get(k)
            all_events.append(row)
            if event['pool_id'] not in originals_by_pool:
                originals_by_pool[event['pool_id']] = d
                dump(minimal/(event['pool_id']+'.json'), {'images':[d['pool']]})
                dump(minimal/(event['pool_id']+'.reference.json'), d['reference'])
                for record in d['pool']['records']:
                    worker=record['worker_id']
                    all_sources.append({'case_directory':directory,'pool_id':event['pool_id'],
                        'image':event['image'],'method':event['method'],
                        **{k:scalar(v) for k,v in record.items()},
                        'original_corner_pairs':len(record['points'])//2,
                        'frozen_lobo_label':scalar(d['frozen_lobo_labels'].get(worker))})
        dump(r/'TRACE_BACKED_ENDPOINT_FACTS.json', {k:endpoint_fact(v) for k,v in local_endpoints.items()})
        if directory.startswith('alliance_'):
            d=next(iter(originals_by_pool.values()))
            assert len(local_endpoints)==7
            facts={'image':d['event']['image'],'reference_id':d['reference']['target_id'],
                'reference_nodes':len(d['reference']['points_1024x512'])//2,
                'original_answers_n':len(d['pool']['records']),
                'original_corner_pair_counts':dict(collections.Counter(len(x['points'])//2 for x in d['pool']['records'])),
                'unique_endpoint_n':len(local_endpoints),
                'groups_n':sum(len(t['full_state']['identity_groups']) for t in local_endpoints.values()),
                'all_identity_groups_unanimous':all(endpoint_fact(t)['all_groups_unanimous'] for t in local_endpoints.values()),
                'all_edges_unanimous':all(endpoint_fact(t)['all_edges_unanimous'] for t in local_endpoints.values()),
                'all_source_rings_complete':all(endpoint_fact(t)['complete_projected_source_rings_n']==t['k'] for t in local_endpoints.values()),
                'B8L2_range':[min(t['B8L2'] for t in local_endpoints.values()),max(t['B8L2'] for t in local_endpoints.values())],
                'all_statuses':sorted({t['score_status'] for t in local_endpoints.values()}),
                'original_source_sha256':digest(next((r/'traces').glob('*.json.gz'))),
                'no_new_fusion_or_scoring':True}
            dump(r/'FULL_ALLIANCE_TRACE_FACTS.json',facts)
    csvwrite(root/'CASE_EVENT_SUMMARY.csv',all_events)
    csvwrite(root/'CASE_ALL_UNIQUE_GROUPS.csv',all_groups)
    csvwrite(root/'CASE_ALL_COMPLETE_ORIGINALS.csv',all_sources)
    csvwrite(root/'CASE_ENDPOINT_SUMMARY.csv',[{k:scalar(v) for k,v in t.items()} for t in all_teams.values()])
    # Exact source-expression split: neither alternative pair is co-observed in
    # any n20 A source, and both pairs cross the inclusive MV50 threshold.
    first=case_objects['1883f7c444eec56b77d2bee9'];second=case_objects['c9d196878be82330b752a7fc']
    expr={}
    for label,d in [('n20',first),('n22',second)]:
        for arm,t in d['arms'].items():
            s=t['full_state'];g={x['feature_id']:x for x in s['identity_groups']}
            pattern=collections.defaultdict(list)
            for x in s['assignments']:
                pattern['|'.join(x['feature_ids'])].append(x['worker'])
            expr[label+'_'+arm]={'team_key':t['team_key'],'n':t['k'],'minimum_support':t['minimum_support'],
              'source_expression_workers':dict(pattern),
              'any_source_contains_both_alternative_pairs':any(set(['node_000','node_001','node_004','node_005']).issubset(x['feature_ids']) for x in s['assignments']),
              'groups':[{k:scalar(x.get(k)) for k in ['feature_id','selected','support','center']} for x in s['identity_groups']],
              'all_selected_locations_resolved':endpoint_fact(t)['all_selected_locations_resolved'],
              'complete_projected_source_rings_n':endpoint_fact(t)['complete_projected_source_rings_n'],
              'native_candidate_reason':s['candidate'].get('reason'),
              'score_status':t['score_status'],'B8L2':t.get('B8L2')}
    assert expr['n20_A']['any_source_contains_both_alternative_pairs'] is False
    assert expr['n20_A']['complete_projected_source_rings_n']==0
    assert expr['n20_A']['all_selected_locations_resolved']
    assert len(expr['n20_A']['source_expression_workers'])==2
    assert sorted(map(len,expr['n20_A']['source_expression_workers'].values()))==[10,10]
    dump(root/'representative_cases/fixed_xz_n20_n22/EXCLUSIVE_EXPRESSION_SOURCE_EVIDENCE.json',expr)
    receipt={'case_events':len(all_events),'unique_teams':len(all_teams),'unique_images':len({x['image'] for x in all_events}),
      'case_directories':dirs,'all_unique_identity_groups':len(all_groups),'all_complete_pool_original_records':len(all_sources),
      'trace_input_manifest':manifest,'new_teams':0,'new_fusions':0,'new_scores':0,
      'geometry_bev_distance_definition':'1 - footprint IoU, dimensionless',
      'individual_historical_quality_labels_not_recomputed':True,
      'no_Q_missing_imputation':True,'source_trace_files_unchanged':True}
    dump(root/'CASE_FACTS_GENERATION_RECEIPT.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='trace_input_manifest'},ensure_ascii=False))


if __name__=='__main__':
    main()
