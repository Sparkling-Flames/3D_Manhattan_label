"""独立复查两个类别块方向，登记额外背景并沿用冻结融合；不重拟合类型。"""
from collections import Counter
from pathlib import Path
import argparse
import gzip
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/workers/personnel_composition_study_20261019/analysis'
OUT = ROOT / 'research/workers/personnel_composition_followup_20261019'
FUSION = ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
TARGETS = {
    'G_17_8': dict(method='R_geo9_source_signed_p2_K2', k=17, m=8, outgoing='C02', incoming='C01'),
    'R_13_2': dict(method='R_role_ward_K5', k=13, m=2, outgoing='C05', incoming='C02'),
}
SEED = 2026101973


def read(path):
    path = Path(path)
    data = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(data.decode('utf-8-sig'))


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def csv(path, frame):
    frame.to_csv(path, index=False, encoding='utf-8', lineterminator='\n',
                 compression={'method': 'gzip', 'mtime': 0} if str(path).endswith('.gz') else None)


def building_mean(frame, column):
    return frame.groupby(['building', 'pool_id'])[column].mean().groupby(level=0).mean().mean()


def validate_event(event, labels):
    arms = [event[a + '_workers'] for a in 'ABC']
    if any(len(a) != event['k'] or len(set(a)) != event['k'] for a in arms):
        raise ValueError('duplicate or wrong-size team')
    if any(w not in labels or labels[w] in ('', 'unknown') for a in arms for w in a):
        raise ValueError('unknown personnel class')
    a, b, c = map(set, arms)
    if a & b != a & c or a & b != set(event['core_workers']):
        raise ValueError('unequal actual backgrounds')
    if len(a - b) != event['m'] or len(a - c) != event['m']:
        raise ValueError('unequal actual turnover')
    counts = [Counter(labels[w] for w in arm) for arm in arms]
    if counts[0] != counts[1] or counts[0] == counts[2]:
        raise ValueError('incorrect within/cross composition')


def modules():
    sys.path.insert(0, str(SOURCE / 'composition'))
    import design_blocks
    import design_compositions
    import summarize_grid
    return design_blocks, design_compositions, summarize_grid


def prepare():
    db, dc, _ = modules()
    pools = {p['pool_id']: p for p in read(FUSION / 'INPUT_SNAPSHOT.json.gz')['images']}
    maps = dc.load_labels([SOURCE / 'reverse/worker_labels.csv.gz'])
    OUT.mkdir(parents=True, exist_ok=True)
    selected, availability = [], []
    for phase in ('discovery', 'validation'):
        spec = read(SOURCE / f'composition/BLOCK_{phase.upper()}_SPEC.json')
        spec['methods'] = [dict(s, sizes=[t['k']]) for s in spec['methods']
                           for t in TARGETS.values() if s['method_id'] == t['method']]
        spec_path = OUT / f'runtime/{phase}_spec.json'
        request_path = OUT / f'runtime/{phase}_requests.json.gz'
        save(spec_path, spec)
        subprocess.run([sys.executable, '-X', 'utf8', str(SOURCE / 'composition/design_blocks.py'),
                        '--snapshot', str(FUSION / 'INPUT_SNAPSHOT.json.gz'),
                        '--split', str(SOURCE / 'composition/SPLIT.json'),
                        '--labels', str(SOURCE / 'reverse/worker_labels.csv.gz'),
                        '--spec', str(spec_path), '--out', str(request_path)], check=True)
        original = read(request_path)['events']
        for target, t in TARGETS.items():
            mapping = maps[t['method'], 'all']
            for event in original:
                p = pools[event['pool_id']]
                origins = {r['worker_id']: r['origin'] for r in p['records']}
                outgoing = {c: n for c, n in event['outgoing_counts'].items() if n}
                incoming = {c: n for c, n in event['incoming_counts'].items() if n}
                if (event['method_id'] != t['method'] or event['k'] != t['k'] or event['m'] != t['m']
                        or outgoing != {t['outgoing']: t['m']} or incoming != {t['incoming']: t['m']}):
                    continue
                if len({tuple(sorted(Counter(origins[w] for w in event[a + '_workers']).items())) for a in 'ABC'}) != 1:
                    continue
                validate_event(event, mapping)
                selected.append(dict(event, target=target, sample='original_replay', historical_phase=phase))
    originals = list(selected)
    # Keep the original target pool support; sample fresh common cores without inspecting outcomes.
    for target, t in TARGETS.items():
        mapping = maps[t['method'], 'all']
        classes = sorted(set(mapping.values()))
        outcounts = tuple(t['m'] if c == t['outgoing'] else 0 for c in classes)
        incounts = tuple(t['m'] if c == t['incoming'] else 0 for c in classes)
        for pid in sorted({e['pool_id'] for e in originals if e['target'] == target}):
            p = pools[pid]
            old = [e for e in originals if e['target'] == target and e['pool_id'] == pid]
            phase = old[0]['historical_phase']
            seen_cores = {tuple(sorted(e['core_workers'])) for e in old}
            seen_teams = {tuple(sorted(e[a + '_workers'])) for e in old for a in 'ABC'}
            failures = Counter()
            found = 0
            for attempt in range(80):
                mode, origin = [('source_matched', 'new'), ('source_matched', 'v1'), ('unrestricted', 'any')][attempt % 3]
                event, reason = db.make_event(p, mapping, t['k'], t['m'], outcounts, incounts,
                                              mode, origin, (SEED, target, pid, attempt), attempt)
                if event is None:
                    failures[reason] += 1
                    continue
                origins = {r['worker_id']: r['origin'] for r in p['records']}
                if len({tuple(sorted(Counter(origins[w] for w in event[a + '_workers']).items())) for a in 'ABC'}) != 1:
                    failures['source_not_matched'] += 1
                    continue
                core = tuple(sorted(event['core_workers']))
                if core in seen_cores:
                    failures['repeated_core'] += 1
                    continue
                overlap = sum(tuple(sorted(event[a + '_workers'])) in seen_teams for a in 'ABC')
                event.update(event_id=f'{target}__{pid}__extra{found}', pool_id=pid, k=t['k'], m=t['m'],
                             method_id=t['method'], domain='all', target=target, sample='additional_background',
                             historical_phase=phase, matching=mode, matched_origin=origin,
                             overlaps_original_selected_teams=overlap)
                validate_event(event, mapping)
                selected.append(event)
                seen_cores.add(core)
                found += 1
                if found == 3:
                    break
            availability.append(dict(target=target, pool_id=pid, historical_phase=phase,
                                     requested_backgrounds=3, generated_backgrounds=found, attempts=attempt + 1,
                                     failure_counts=dict(failures)))
    save(OUT / 'REQUESTS.json.gz', {'events': selected})
    save(OUT / 'REGISTRATION.json', dict(seed=SEED, status='requests_registered_before_followup_fusion',
         targets=TARGETS, original_events=len(originals), additional_events=len(selected)-len(originals),
         generation='3 different common cores per original supported pool, up to80 deterministic attempts, actual source matched',
         interpretation='Post-hoc followup in previously explored v2; new cores, not new images or external blind validation. No claim all teams unseen in the full prior search.',
         decision='Unchanged frozen classes/fusion/scoring; strict/main/wide and continuous distances; no outcome filtering',
         availability=availability))
    print('Registered', len(selected), 'events before fusion', flush=True)


def run():
    _, dc, sg = modules()
    os.environ['PERSONNEL_V2_REPOSITORY'] = str(ROOT)
    sys.path.insert(0, str(FUSION))
    import fusion_engine as fe
    import fusion_runner as fr
    fr.FE = fe
    pools = {p['pool_id']: p for p in fe.load_pools()}
    maps = dc.load_labels([SOURCE / 'reverse/worker_labels.csv.gz'])
    events = read(OUT / 'REQUESTS.json.gz')['events']
    teams_path = OUT / 'TEAMS.json.gz'
    teams = read(teams_path) if teams_path.exists() else {}
    rows = []
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / 'measurement_engine.zip', fe.ENGINE / 'working_models.py') as (engine, models):
        for i, event in enumerate(events):
            p = pools[event['pool_id']]
            validate_event(event, maps[event['method_id'], 'all'])
            arm_rows = {}
            for arm in 'ABC':
                workers = event[arm + '_workers']
                key = fr.team_key(p['pool_id'], workers)
                if key not in teams:
                    teams[key] = fr.evaluate_one(p, workers, engine, models)
                arm_rows[arm] = teams[key]
            row = {k: event[k] for k in ('event_id', 'target', 'sample', 'historical_phase', 'pool_id', 'k', 'm')}
            row.update(image=p['meta']['image'], building=p['meta']['building'], difficulty=p['meta']['difficulty'],
                       reference_id=p['meta']['reference_id'], core_workers='|'.join(event['core_workers']))
            for arm, result in arm_rows.items():
                row[arm + '_workers'] = '|'.join(event[arm + '_workers'])
                for key in ('B8L2', 'D10', 'nodes', 'complete_evaluable', 'score_status', 'team_key', 'source_time_total_seconds'):
                    row[arm + '_' + key] = result.get(key)
            for name, a, b in (('within', 'A', 'B'), ('cross', 'A', 'C')):
                metrics = sg.pair_metrics(arm_rows[a], arm_rows[b])
                for key in ('turnover', 'abs_B8L2_change', 'floor_jaccard_difference', 'structure_bound_cyclic_deg',
                            'node_count_difference', 'mean_height_prism_pair_iou', 'joint_stable_strict',
                            'joint_stable_main', 'joint_stable_wide'):
                    row[name + '_' + key] = metrics[key]
                assert metrics['turnover'] == event['m']
            b, c = row['B_B8L2'], row['C_B8L2']
            row['net_Q'] = c-b if b is not None and c is not None else None
            rows.append(row)
            if i % 50 == 0:
                save(teams_path, teams)
                print('Fused events', i+1, '/', len(events), 'unique teams', len(teams), flush=True)
    save(teams_path, teams)
    csv(OUT / 'EVENTS.csv.gz', pd.DataFrame(rows))
    report()


def report():
    data = pd.read_csv(OUT / 'EVENTS.csv.gz')
    for arm, letter in [('within','B'),('cross','C')]:
        complete = data.A_complete_evaluable & data[letter+'_complete_evaluable']
        data[arm+'_geometry_main'] = complete & (data[arm+'_floor_jaccard_difference']<=.05) & (data[arm+'_node_count_difference']==0) & (data[arm+'_structure_bound_cyclic_deg']<=3)
        data[arm+'_quality_main'] = complete & (data[arm+'_abs_B8L2_change']<=2)
    component_fields = [key for key in data if key.endswith(('_geometry_main','_quality_main'))]
    components = []
    for keys, group in data.groupby(['target','sample','historical_phase']):
        row = dict(zip(['target','sample','historical_phase'],keys))
        row.update({key:building_mean(group,key) for key in component_fields})
        components.append(row)
    csv(OUT/'CRITERION_COMPONENTS.csv',pd.DataFrame(components))
    metrics = ['net_Q', 'within_abs_B8L2_change', 'cross_abs_B8L2_change',
               'within_floor_jaccard_difference', 'cross_floor_jaccard_difference']
    metrics += [f'{arm}_joint_stable_{mode}' for arm in ('within', 'cross') for mode in ('strict', 'main', 'wide')]
    summary = []
    for key, g in data.groupby(['target', 'sample', 'historical_phase']):
        row = dict(zip(['target', 'sample', 'historical_phase'], key))
        row.update(events=len(g), images=g.pool_id.nunique(), buildings=g.building.nunique(),
                   scored_events=int(g.net_Q.notna().sum()), scored_images=g.loc[g.net_Q.notna(), 'pool_id'].nunique(),
                   improved_events=int((g.net_Q>0).sum()), worsened_events=int((g.net_Q<0).sum()),
                   net_Q_event_p10=g.net_Q.quantile(.1))
        row.update({m: building_mean(g, m) for m in metrics})
        summary.append(row)
    summary = pd.DataFrame(summary)
    csv(OUT / 'SUMMARY.csv', summary)
    by_image = data.groupby(['target', 'sample', 'historical_phase', 'building', 'pool_id'])[metrics].mean().reset_index()
    csv(OUT / 'PER_IMAGE.csv', by_image)
    csv(OUT / 'PER_BUILDING.csv', by_image.groupby(['target', 'sample', 'historical_phase', 'building'])[metrics].mean().reset_index())
    previous = pd.read_csv(SOURCE / 'composition/compact_block_evidence/02_all_exact_strata.csv.xz')
    checks = []
    for target, t in TARGETS.items():
        for phase in ('discovery', 'validation'):
            old = previous[(previous['view']=='exact_counts_k_m') & (previous.subset=='actual_source_matched') &
                           (previous.phase==phase) & (previous.method_id==t['method']) & (previous.k==t['k']) & (previous.m==t['m'])]
            def pure(value, who):
                return {c:int(n) for c,n in (v.split(':') for v in value.split('|')) if int(n)} == {who:t['m']}
            old = old[old.outgoing_counts.map(lambda x:pure(x,t['outgoing'])) & old.incoming_counts.map(lambda x:pure(x,t['incoming']))]
            assert len(old)==1
            row = summary[(summary.target==target)&(summary['sample']=='original_replay')&(summary.historical_phase==phase)].iloc[0]
            for field, source_field in [('net_Q','delta_Q'),('within_joint_stable_main','within_stable'),('cross_joint_stable_main','changed_stable')]:
                error = float(row[field]-old.iloc[0][source_field])
                checks.append(dict(target=target, phase=phase, field=field, error=error))
                assert abs(error)<1e-6, checks[-1]
            assert '/'.join(str(int(row[c])) for c in ('events','images','buildings'))==old.iloc[0].attempted_events_images_buildings
    save(OUT / 'CHECKS.json', dict(original_aggregate_checks=checks, all_passed=True,
         events=len(data), unique_teams=len(read(OUT/'TEAMS.json.gz')), scoring='B8L2 main/D10 sensitivity; N1 unchanged',
         sources=['research/workers/personnel_composition_study_20261019', str(FUSION.relative_to(ROOT)).replace('\\','/')]))
    print(summary[['target','sample','historical_phase','events','images','buildings','net_Q','within_joint_stable_main','cross_joint_stable_main']].to_string(index=False))


def view():
    data = pd.read_csv(OUT / 'EVENTS.csv.gz')
    extra = data[(data['sample']=='additional_background') & (data.historical_phase=='validation')]
    cases = []
    selections = [(target + '：同类相近、跨类变化', extra[(extra.target==target) & extra.within_joint_stable_main & ~extra.cross_joint_stable_main]) for target in TARGETS]
    selections += [('边界：同类主判据未过、宽判据通过', extra[~extra.within_joint_stable_main & extra.within_joint_stable_wide]),
                   ('反例：同类变化、跨类相近', extra[~extra.within_joint_stable_main & extra.cross_joint_stable_main])]
    pools = {p['pool_id']: p for p in read(FUSION / 'INPUT_SNAPSHOT.json.gz')['images']}
    teams = read(OUT / 'TEAMS.json.gz')
    gallery = ROOT/'research/statistics/research_explorer_v1_r2_20261017'
    photos = {r['image_id']:r.get('photo') for r in read(gallery/'v2-resources/index.json')['images']}
    for title, group in selections:
        group = group.sort_values(['cross_abs_B8L2_change','event_id'])
        if group.empty:
            continue
        row = group.iloc[len(group)//2].to_dict()
        pool = pools[row['pool_id']]
        photo = photos.get(pool['meta']['image_id'])
        if photo and not photo.startswith(('http:', 'https:', 'data:')):
            photo = os.path.relpath((gallery/photo).resolve(), OUT).replace('\\','/')
        cases.append(dict(title=title, event=row, image=dict(photo=photo,image_code=pool['meta']['image']),
                          reference=dict(points=pool['reference']['points_1024x512'],floor=pool['reference']['floor_xz_h']),
                          teams={a:teams[row[a+'_team_key']] for a in 'ABC'},
                          answers={r['worker_id']:r['points'] for r in pool['records'] if r['worker_id'] in set('|'.join(row[a+'_workers'] for a in 'ABC').split('|'))}))
    assert len(cases)==4
    save(OUT/'REVIEW_CASES.json',dict(selection='Within additional-background historical-validation events: median cross absolute Q change in each displayed diagnostic group, tie by event_id; illustrations only, no effect estimation',cases=cases))
    (OUT/'view-data.js').write_bytes(('window.FOLLOWUP='+json.dumps(clean(cases),ensure_ascii=False,allow_nan=False).replace('</','<\\/')+';\n').encode())
    features = pd.read_csv(SOURCE/'forward/results/features_train.csv.gz')
    labels = pd.read_csv(SOURCE/'forward/results/worker_labels.csv.gz')
    qlabels = labels[labels.method_id=='F_rule_Q_threshold_K2'][['worker_id','class_id']]
    merged = features.merge(qlabels,on='worker_id')
    known = merged[merged.class_id!='unknown']
    high = known[known.class_id==known.groupby('class_id').q_beta.mean().idxmax()]
    fields = ['t_supported','hard_supported','semi_old_error_nonedit_supported','semi_new_error_nonedit_supported','semi_old_edit_supported','semi_new_edit_supported','scope_supported']
    rows=[]
    for name, frame in [('all',features),('high_Q_threshold',high)]:
        for origin,g in frame.groupby('person_origin'):
            rows.append(dict(group=name,origin=origin,people=len(g),**{k:int(g[k].fillna(False).sum()) for k in fields}))
    csv(OUT/'SUBDIVISION_SUPPORT.csv',pd.DataFrame(rows))
    csv(OUT/'HIGH_Q_FEATURES.csv',high[['worker_id','person_origin','q_beta','t_source_origin_effect','hard_minus_easy','pair_count_effect','semi_new_error_nonedit_effect','scope_out_effect']+fields])
    print('Four review cases and historical subdivision support saved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'run', 'report', 'view'])
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'report': report, 'view': view}[args.stage]()
