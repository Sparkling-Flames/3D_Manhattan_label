"""Versioned personnel profiles and cached real-member replacements; no quality/fusion tuning."""
from contextlib import contextmanager
import gzip
import importlib.util
from itertools import combinations
import json
import math
from pathlib import Path
import tempfile
import zipfile

import numpy as np
import pandas as pd
from shapely.ops import unary_union

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from .worker_classification_progress_20261014 import fit_training_effects, half_stability
from .wall_consensus_population_20261014 import footprint, summarize_state, prepare_input
from .consensus_delivery_20261008 import fuse, WORKING_GAP

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/worker_wq_integration_20261015'
OLD = ROOT / 'research/workers/worker_classification_progress_20261014'
POP = ROOT / 'research/fusion/wall_consensus_population_20261014'
QUALITY = ROOT / 'research/quality/quality_joint_closeout_review_20261015'
VERSION = 'WQ-LS08-20261014'
AXES = ['WQ', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter',
        'height_mean_ratio', 'height_vs_floor']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(name, value):
    def normalize(v):
        if isinstance(v, dict): return {str(k): normalize(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, np.ndarray)): return [normalize(x) for x in v]
        if isinstance(v, np.generic): return normalize(v.item())
        if isinstance(v, float) and not np.isfinite(v): return None
        return v
    (OUT/name).write_text(json.dumps(normalize(value), ensure_ascii=False, indent=2,
                                   allow_nan=False)+'\n', encoding='utf-8')


def table(name, data):
    frame = pd.DataFrame(data).copy()
    for column in frame:
        if frame[column].map(lambda x: isinstance(x, (list, dict, tuple))).any():
            frame[column] = frame[column].map(lambda x: json.dumps(x, ensure_ascii=False)
                                              if isinstance(x, (list, dict, tuple)) else x)
    frame.to_csv(OUT/name, index=False, encoding='utf-8-sig')


@contextmanager
def frozen_engine(archive):
    # Current deployments use checked-in source files; archives remain legacy inputs.
    if isinstance(archive, (str, Path)):
        target = Path(archive)
        spec = importlib.util.spec_from_file_location('personnel_frozen_quality', target/'src/quality.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
        return
    # Compatibility for old callers holding an already-open ZipFile.
    with tempfile.TemporaryDirectory(prefix='worker_wq_') as directory:
        target = Path(directory)
        for name in archive.namelist():
            if name.startswith('engine/') and name.endswith('.py') or name in (
                    'src/quality.py', 'configs/WQ_LS08_UNCHANGED.json'):
                assert '..' not in Path(name).parts and not Path(name).is_absolute()
                archive.extract(name, target)
        spec = importlib.util.spec_from_file_location('personnel_frozen_quality', target/'src/quality.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module


def geometry_equal(a, b):
    x = np.column_stack([a['bottom3d'], a['top3d']])
    y = np.column_stack([b['bottom3d'], b['top3d']])
    if x.shape != y.shape:
        return False
    return any(np.allclose(x, np.roll(v, k, axis=0), rtol=0, atol=1e-10)
               for v in (y, y[::-1]) for k in range(len(y)))


def reference_cells(entries):
    pools, cells = {}, []
    for image, condition, ref_id, geometry in entries:
        group = pools.setdefault((image, condition), [])
        index = next((i for i, g in enumerate(group) if geometry_equal(g, geometry)), None)
        if index is None:
            index = len(group)
            group.append(geometry)
        cells.append(json.dumps([image, condition, index]))
    return cells


def classify(effect, supported):
    if not supported or not np.isfinite(effect) or effect == 0:
        return 'unclassified'
    return 'above_pool' if effect > 0 else 'below_pool'


def fit_axis(data, axis, target=None):
    p = fit_training_effects(data.assign(value=data[axis]), target)
    p['label'] = [classify(r.effect, r.supported) for r in p.itertuples()]
    p['axis'], p['fold'] = axis, target if target is not None else 'full_descriptive'
    return p


def replacement_edges(teams):
    normalized = [tuple(sorted(t)) for t in teams]
    if any(len(set(t)) != len(t) for t in teams) or len(set(normalized)) != len(teams):
        raise ValueError('duplicate real worker or duplicate team')
    edges = []
    for i, j in combinations(range(len(teams)), 2):
        a, b = set(teams[i]), set(teams[j])
        if len(a) == len(b) and len(a-b) == len(b-a) == 1:
            edges.append((i, j, tuple(sorted(a & b)), next(iter(a-b)), next(iter(b-a))))
    return edges


def summarize_entrants(effects, outcomes):
    """Descriptive association in one fixed base; not a fitted test-set predictor."""
    d=pd.DataFrame(dict(effect=effects,outcome=outcomes)).dropna()
    d=d[d.effect.ne(0)]
    if len(d)<2:
        return dict(evaluable_entrants=len(d),spearman=None,class_explained_fraction=None,class_gap=None)
    labels=d.effect.gt(0); residual=d.outcome-d.groupby(labels).outcome.transform('mean')
    total=float(((d.outcome-d.outcome.mean())**2).sum())
    means=d.groupby(labels).outcome.mean()
    return dict(evaluable_entrants=len(d),spearman=d.effect.rank().corr(d.outcome.rank()) if d.outcome.nunique()>1 else None,
        class_explained_fraction=1-float((residual**2).sum())/total if total>0 else None,
        class_gap=means.get(True,np.nan)-means.get(False,np.nan),
        outcome_range=float(d.outcome.max()-d.outcome.min()))


def bind_quality(archive, engine):
    native = load_current_bundle()['data']
    archived = json.loads(archive.read('source/historical_current_formal_loader_data.json'))
    if native != archived:
        raise ValueError('current geometry/source version differs from reviewed quality snapshot')
    objects = {r['object_id']: r for r in native['objects']}
    gate = {r['record_id']: r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    scores = json.loads(archive.read('results/all_scores.json'))
    pairs = {(r['record_id'], r['reference_id'], r['score_kind']): r for r in scores['records']}
    routing = json.loads(archive.read('source/routing_prepared.json'))
    old_routing = read(ROOT/'research/quality_pro_joint_archive_20261013/source/routing/inputs/prepared_input.json')
    assert routing == old_routing, 'routing reference geometry version changed since old profile material'
    candidates = {c['candidate_id']: c for im in routing['candidate_images'] for c in im['candidates']}
    joint = pd.read_csv(QUALITY/'JOINT_COMPARISON_1145.csv')
    old = pd.read_csv(OLD/'expanded_metric_inventory.csv')
    old_by = old.set_index('record_id').to_dict('index')
    old_metrics = {r['record_id']: r for r in read(ROOT/'research/quality_candidate_disagreement_20261013/RESULTS.json')['records']}
    geometries, entries, rows, audit = {}, [], [], []
    assert joint.record_id.is_unique and old.record_id.is_unique
    for row in joint.to_dict('records'):
        rid = row['record_id']; g = gate[rid]; obj = objects[row['object_id']]
        assert all(row[k] == g[k] for k in ('record_id', 'object_id', 'worker_id', 'image_id', 'condition'))
        assert obj['worker_id'] == row['worker_id'] and row['role'] == g['role']
        pair = pairs[(rid, row['reference_id'], 'full')]
        assert pair['status'] == 'complete'
        assert abs(pair['scores']['WQ']-row['WQ']) < 1e-8
        assert abs(pair['IoU3D100']-row['IoU3D100']) < 1e-8
        prior = old_by.get(rid)
        match = None
        if prior:
            assert all(prior[k] == row[k] for k in ('object_id','worker_id','image_id'))
            m = old_metrics[rid]['metrics']
            assert all(abs(m[k]-row[k]) < 1e-8 for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'))
            old_cid = old_metrics[rid].get('selected_candidate_id')
            old_geom = candidates[old_cid]['full_geometry'] if old_cid else engine.geometry(objects[prior['reference_object_id']]['points_1024x512'])
            geom = candidates[pair['candidate_id']]['full_geometry'] if pair['candidate_id'] else engine.geometry(objects[row['reference_id']]['points_1024x512'])
            match = geometry_equal(old_geom, geom)
            assert match, 'old and current scoring reference geometries differ'
        ordinary = row['role'] == 'manual_development_candidate' and row['condition'] == 'manual'
        permitted = ordinary and not row['original_holdout'] and not row['same_target_quality_hold'] and obj['independent_vote_eligible']
        audit.append(dict(record_id=rid, in_old_1179=bool(prior), old_score_kind=prior['score_kind'] if prior else None,
            same_reference_id=prior['reference_object_id'] == row['reference_id'] if prior else None,
            same_actual_reference_geometry=match, current_role=row['role'], score_status=row['score_status'],
            profile_included=permitted, reason='included' if permitted else 'target_hold' if ordinary else 'separate_use_layer'))
        if not permitted:
            continue
        assert not g['personnel_barriers'] and not g['context_barriers']
        ref_key = pair['candidate_id'] or row['reference_id']
        geom = candidates[pair['candidate_id']]['full_geometry'] if pair['candidate_id'] else engine.geometry(objects[row['reference_id']]['points_1024x512'])
        geometries[ref_key] = dict(reference_id=row['reference_id'], candidate_id=pair['candidate_id'], geometry=geom,
            source='archived routing actual geometry' if pair['candidate_id'] else 'current formal points; exact archived version checked')
        entries.append((row['image_id'], row['condition'], row['reference_id'], geom))
        row.update(reference_geometry_key=ref_key, score_version=VERSION, score_kind='full',
            height_mean_ratio=pair['metrics']['height_mean_ratio'],
            height_vs_floor=np.log1p(pair['scores']['height_loss'])-np.log1p(pair['scores']['boundary_loss']+pair['scores']['direction_loss']))
        rows.append(row)
    panel = pd.DataFrame(rows)
    panel['context_key'] = reference_cells(entries)
    if panel.duplicated(['context_key', 'worker_id']).any():
        raise ValueError('duplicate worker in equivalent reference cell')
    audit.extend(dict(record_id=r.record_id, in_old_1179=True, old_score_kind=r.score_kind,
        profile_included=False, reason='floor_only_no_full_Q') for r in old.itertuples() if r.record_id not in set(joint.record_id))
    assert sum(r['reason']=='floor_only_no_full_Q' for r in audit)==217
    table('binding_audit.csv', audit); table('quality_panel.csv', panel)
    save('reference_geometries.json', geometries)
    return panel, objects, gate, dict(native_snapshot_exact=True, joint_rows=len(joint), old_rows=len(old),
        overlap=len(set(joint.record_id)&set(old.record_id)), joined_reference_geometry_matches=sum(r['same_actual_reference_geometry'] is True for r in audit if 'same_actual_reference_geometry' in r),
        status_counts=pd.DataFrame(audit).reason.value_counts().to_dict())


def profiles(panel, target_buildings):
    fits, predictions, performance, halves = [], [], [], []
    for axis in AXES:
        for target in [None] + sorted(set(panel.building_id) | set(target_buildings)):
            p = fit_axis(panel, axis, target); fits.append(p)
            if target is None or axis not in ('WQ', 'IoU3D100'):
                continue
            supported = p[p.label.ne('unclassified')].copy()
            supported['class_effect'] = supported.groupby('label').effect.transform('mean')
            test = panel[panel.building_id.eq(target)].merge(supported[['worker_id','effect','label','class_effect']], on='worker_id')
            test = test[test.groupby('context_key').worker_id.transform('size').ge(2)].copy()
            if test.empty:
                continue
            test['target'] = test[axis]-test.groupby('context_key')[axis].transform('mean')
            for name, field in [('continuous','effect'),('class','class_effect')]:
                test[name+'_prediction'] = test[field]-test.groupby('context_key')[field].transform('mean')
                test[name+'_sqerr'] = (test.target-test[name+'_prediction'])**2
            test['baseline_sqerr'] = test.target**2; test['axis'] = axis
            predictions.append(test[['record_id','worker_id','building_id','context_key','axis','target','label',
                'continuous_prediction','class_prediction','baseline_sqerr','continuous_sqerr','class_sqerr']])
        if axis in ('WQ','IoU3D100','height_vs_floor'):
            h = half_stability(panel.assign(value=panel[axis]), sorted(panel.worker_id.unique()))
            h['axis'] = axis
            # Existing helper's names denote signs; rename to avoid a speed interpretation.
            h = h.replace({'faster':'below_pool', 'slower':'above_pool'})
            halves.append(h)
    fits = pd.concat(fits, ignore_index=True); preds = pd.concat(predictions, ignore_index=True)
    for axis, group in preds.groupby('axis'):
        by = group.groupby('building_id')[['baseline_sqerr','continuous_sqerr','class_sqerr']].mean()
        for method in ('continuous','class'):
            performance.append(dict(axis=axis, method=method, evaluated_rows=len(group), buildings=len(by),
                pooled_reduction=1-group[method+'_sqerr'].sum()/group.baseline_sqerr.sum(),
                building_equal_reduction=1-by[method+'_sqerr'].mean()/by.baseline_sqerr.mean(),
                improved_buildings=int((by[method+'_sqerr']<by.baseline_sqerr).sum())))
    full = fits[fits.fold.eq('full_descriptive')].copy(); halves = pd.concat(halves, ignore_index=True)
    stable = halves.groupby(['axis','worker_id']).agg(comparable_halves=('comparable','sum'), direction_agreement=('same_direction','mean')).reset_index()
    full = full.merge(stable, on=['axis','worker_id'], how='left')
    table('profiles.csv',full);table('fold_profiles.csv',fits);table('predictions.csv',preds)
    table('prediction_performance.csv',performance);table('disjoint_halves.csv',halves)
    wide = full[full.supported].pivot(index='worker_id', columns='axis', values='effect')
    old_time = pd.read_csv(OLD/'time_profiles.csv').set_index('worker_id')
    wide['time'] = old_time.effect.where(old_time.supported)
    correlations=[]
    for a,b in combinations(wide.columns,2):
        d=wide[[a,b]].dropna()
        correlations.append(dict(axis_a=a,axis_b=b,workers=len(d),spearman=d[a].rank().corr(d[b].rank())))
    table('axis_correlations.csv',correlations);table('profile_wide.csv',wide.reset_index())
    return fits, performance


def compare_cached(panel, fits, objects, gate, archive, engine):
    snapshot = read(POP/'input_snapshot.json')
    # prepare_record may reorder points without rewriting source-index bookkeeping.
    # Compare the actual prepared input, including its ring, against a fresh current-loader projection.
    assert snapshot == prepare_input(), 'cached fusion prepared input version drift'
    endpoint = {r['image_code']:r for r in json.loads(archive.read('results/FUSION_220_RESULTS.json'))['records'] if r['version']=='automatic'}
    times = pd.read_csv(OLD/'time_assignments.csv')
    team_rows, edge_rows, coverage, ref_rows, entrant_rows, entrant_summary = [], [], [], [], [], []
    for im in snapshot['images']:
        code=im['image']; building=im['building']; records=im['records']; n=len(records)
        alias={r['worker']:gate[r['id']]['worker_id'] for r in records}
        polygons={}
        for r in records:
            obj=objects[gate[r['id']]['object_id']]
            actual=[obj['preprocessed_points'][i] for i in r['source_point_indices']]
            assert np.array_equal(actual,r['points']), 'cached fusion input geometry drift'
            assert obj['independent_vote_eligible']
            polygons[r['worker']]=footprint(np.asarray(engine.geometry(r['points'])['bottom3d'])[:,[0,2]])
        assert all(p is not None for p in polygons.values())
        union_area=unary_union(list(polygons.values())).area
        distances={tuple(sorted((a,b))):polygons[a].symmetric_difference(polygons[b]).area/union_area for a,b in combinations(polygons,2)}
        labels={axis:fits[fits.axis.eq(axis)&fits.fold.eq(building)].set_index('worker_id').to_dict('index') for axis in ('WQ','IoU3D100','height_vs_floor')}
        labels['time']=times[times.fold.eq(building)].set_index('worker_id').to_dict('index')
        ref=endpoint[code]; full_ref=ref['reference_id'] if ref['status']=='complete_conditional' else None
        geom=engine.geometry(objects[full_ref]['points_1024x512']) if full_ref else None
        ref_rows.append(dict(image=code,reference_id=full_ref,reference_binding=ref['binding'],
            geometry=geom,interpretation='fixed prior full reference for conditional subset comparison; no subset semantic certification'))
        payload=json.load(gzip.open(POP/'states'/f'{code}.json.gz','rt',encoding='utf-8'))
        states=payload['states']; cached={tuple(sorted(s['workers'])):s for s in states}
        designed_bases=[]; new_states=[]
        if n>=9:
            # Two pre-existing random orders define bases without using scores or labels.
            designed_bases=sorted({tuple(sorted(order[:7])) for order in payload['orders'][:2]})
            record_by={r['worker']:r for r in records}
            for base in designed_bases:
                for worker in sorted(set(alias)-set(base)):
                    key=tuple(sorted((*base,worker)))
                    if key not in cached:
                        state=fuse([record_by[w] for w in key],gap=WORKING_GAP)['automatic']
                        entry=dict(workers=list(key),automatic=state)
                        cached[key]=entry;new_states.append(entry)
            (OUT/'new_states').mkdir(exist_ok=True)
            with gzip.open(OUT/'new_states'/f'{code}.json.gz','wt',encoding='utf-8') as handle:
                json.dump(dict(image=code,bases=designed_bases,states=new_states),handle,ensure_ascii=False)
        states=list(cached.values())
        for k in sorted(set([3,8,16,n-1])):
            chosen=[s for s in states if len(s['workers'])==k]
            teams=[tuple(s['workers']) for s in chosen]; edges=replacement_edges(teams)
            if k==8:
                edges=[edge for edge in edges if edge[2] in designed_bases]
            coverage.append(dict(image=code,pool_n=n,k=k,possible_teams=math.comb(n,k) if k<=n else 0,
                available_unique_teams=len(chosen),one_person_pairs=len(edges),full_reference_available=bool(full_ref),
                new_unique_teams=sum(len(s['workers'])==k for s in new_states),
                comparison_design='two_fixed_seven_person_bases_all_remaining_workers' if k==8 and designed_bases else 'cached_exact_replacements'))
            # Middle-k snapshots have no exact swaps: keep coverage, avoid duplicating the fusion thread's scoring run.
            participants=sorted({ix for i,j,*_ in edges for ix in (i,j)})
            scored={}
            for ix in participants:
                entry=chosen[ix]; state=entry['automatic']; members=entry['workers']; summary=summarize_state(state)
                gates=[gate[r['id']] for r in records if r['worker'] in members]
                row=dict(image=code,building_id=building,subset='|'.join(sorted(members)),
                    workers='|'.join(sorted(alias[w] for w in members)),condition='manual',score_version=VERSION,
                    fusion_version='consensus_delivery_20261008_MV50_gap7.5_automatic',
                    reference_id=full_ref,reference_binding=ref['binding'],original_holdout=any(g['original_holdout'] for g in gates),
                    restricted_member_n=sum(g['role']!='manual_development_candidate' for g in gates),
                    WQ=None,IoU3D100=None,score_status='no_bound_full_reference',
                    raw_pair_distance=np.mean([distances[tuple(sorted(ab))] for ab in combinations(members,2)]),**summary)
                if geom is not None:
                    if summary['complete_evaluable']:
                        measured=engine.measure(engine.geometry(state['candidate']['points']),geom)
                        row['score_status']=measured['status']
                        if measured['status']=='complete':
                            row.update(WQ=measured['scores']['WQ'],IoU3D100=100*measured['metrics']['iou_3d_corner_mean'])
                        else: row['measurement_reasons']=measured.get('reasons')
                    else: row['score_status']='incomplete_fusion'
                for axis,lookup in labels.items():
                    ps=[lookup.get(alias[w]) for w in members]
                    supported=[p for p in ps if p and p['supported']]
                    row[axis+'_classified_n']=len(supported)
                    row[axis+'_positive_n']=sum(p['effect']>0 for p in supported)
                    row[axis+'_mean_effect']=np.mean([p['effect'] for p in supported]) if supported else None
                team_rows.append(row);scored[ix]=row
            for i,j,base,a,b in edges:
                x,y=scored[i],scored[j]
                pa,pb=footprint(chosen[i]['automatic']['candidate']['footprint']),footprint(chosen[j]['automatic']['candidate']['footprint'])
                complete_floor=x['complete_floor_evaluable'] and y['complete_floor_evaluable']
                row=dict(image=code,building_id=building,k=k,base='|'.join(base),team_a=x['subset'],team_b=y['subset'],
                    removed=alias[a],added=alias[b],reference_id=full_ref,score_version=VERSION,
                    original_holdout=x['original_holdout'] or y['original_holdout'],
                    restricted_member_n=max(x['restricted_member_n'],y['restricted_member_n']),
                    both_complete_floor=complete_floor,both_full_score=x['WQ'] is not None and y['WQ'] is not None,
                    floor_change=1-pa.intersection(pb).area/pa.union(pb).area if complete_floor else None,
                    raw_pair_change=y['raw_pair_distance']-x['raw_pair_distance'],
                    WQ_change=y['WQ']-x['WQ'] if x['WQ'] is not None and y['WQ'] is not None else None,
                    IoU3D100_change=y['IoU3D100']-x['IoU3D100'] if x['IoU3D100'] is not None and y['IoU3D100'] is not None else None)
                for axis,lookup in labels.items():
                    l,r=lookup.get(alias[a]),lookup.get(alias[b]); valid=l and r and l['supported'] and r['supported'] and l['effect']!=0 and r['effect']!=0
                    row[axis+'_swap']='same_class' if valid and np.sign(l['effect'])==np.sign(r['effect']) else 'cross_class' if valid else 'unclassified'
                    row[axis+'_effect_change']=r['effect']-l['effect'] if valid else None
                edge_rows.append(row)
            if k==8:
                for base in designed_bases:
                    rows=[]
                    for ix,row in scored.items():
                        added=set(teams[ix])-set(base)
                        if not set(base).issubset(teams[ix]) or len(added)!=1: continue
                        worker=alias[next(iter(added))]
                        e=dict(image=code,building_id=building,base='|'.join(base),worker_id=worker,
                            WQ=row['WQ'],IoU3D100=row['IoU3D100'],raw_pair_distance=row['raw_pair_distance'],
                            score_status=row['score_status'],original_holdout=row['original_holdout'],
                            complete_floor_evaluable=row['complete_floor_evaluable'])
                        for axis,lookup in labels.items():
                            person=lookup.get(worker)
                            e[axis+'_effect']=person['effect'] if person and person['supported'] else None
                        rows.append(e);entrant_rows.append(e)
                    d=pd.DataFrame(rows)
                    for axis in labels:
                        for outcome in ('WQ','IoU3D100','raw_pair_distance'):
                            entrant_summary.append(dict(image=code,base='|'.join(base),axis=axis,outcome=outcome,
                                eligible_entrants=len(rows),original_holdout=any(r['original_holdout'] for r in rows),
                                **summarize_entrants(d[axis+'_effect'],d[outcome])))
        print('cached replacements complete:',code,flush=True)
    table('team_coverage.csv',coverage);table('cached_team_scores.csv',team_rows)
    table('replacement_pairs.csv',edge_rows);save('team_references.json',ref_rows)
    table('fixed_base_entrants.csv',entrant_rows);table('fixed_base_associations.csv',entrant_summary)
    return pd.DataFrame(edge_rows),pd.DataFrame(team_rows)


def summarize_replacements(edges):
    rows, matched = [], []
    for axis in ('WQ','IoU3D100','height_vs_floor','time'):
        for (image,k,kind),g in edges.groupby(['image','k',axis+'_swap']):
            valid=g[g.both_full_score]
            change=valid[axis+'_effect_change']
            rows.append(dict(axis=axis,image=image,k=k,swap=kind,pairs=len(g),
                complete_floor_pairs=int(g.both_complete_floor.sum()),full_score_pairs=len(valid),
                mean_floor_change=g.floor_change.mean(),mean_abs_raw_pair_change=g.raw_pair_change.abs().mean(),
                mean_abs_WQ_change=valid.WQ_change.abs().mean(),
                WQ_change_toward_higher_axis=(valid.WQ_change*np.sign(change)).mean(),
                IoU_change_toward_higher_axis=(valid.IoU3D100_change*np.sign(change)).mean(),
                original_holdout=bool(g.original_holdout.any()),restricted_member_n=int(g.restricted_member_n.max())))
        for (image,k,base),g in edges.groupby(['image','k','base']):
            a=g[g[axis+'_swap'].eq('same_class')]; b=g[g[axis+'_swap'].eq('cross_class')]
            if a.empty or b.empty: continue
            matched.append(dict(axis=axis,image=image,k=k,base=base,same_pairs=len(a),cross_pairs=len(b),
                same_floor_evaluable=int(a.both_complete_floor.sum()),cross_floor_evaluable=int(b.both_complete_floor.sum()),
                same_Q_evaluable=int(a.both_full_score.sum()),cross_Q_evaluable=int(b.both_full_score.sum()),
                original_holdout=bool(g.original_holdout.any()),restricted_member_n=int(g.restricted_member_n.max()),
                floor_cross_minus_same=b.floor_change.mean()-a.floor_change.mean(),
                abs_raw_cross_minus_same=b.raw_pair_change.abs().mean()-a.raw_pair_change.abs().mean(),
                abs_WQ_cross_minus_same=b.WQ_change.abs().mean()-a.WQ_change.abs().mean()))
    table('replacement_summary.csv',rows);table('matched_base_comparisons.csv',matched)
    return dict(matched_base_comparisons=len(matched),matched_by_axis=pd.DataFrame(matched).axis.value_counts().to_dict() if matched else {})


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(QUALITY/'pro_closeout_delta.zip') as archive, frozen_engine(archive) as engine:
        panel,objects,gate,binding=bind_quality(archive,engine)
        targets=[im['building'] for im in read(POP/'input_snapshot.json')['images']]
        fits,performance=profiles(panel,targets)
        edges,teams=compare_cached(panel,fits,objects,gate,archive,engine)
    replacement=summarize_replacements(edges)
    summary=dict(score_version=VERSION,binding=binding,profile_rows=len(panel),workers=panel.worker_id.nunique(),
        images=panel.image_id.nunique(),reference_cells=panel.context_key.nunique(),buildings=panel.building_id.nunique(),
        profile_class_counts=fits[(fits.axis=='WQ')&(fits.fold=='full_descriptive')].label.value_counts().to_dict(),
        prediction_performance=performance,replacements=len(edges),scored_unique_teams=len(teams),
        team_score_status=teams.score_status.value_counts().to_dict(),replacement_diagnostics=replacement,
        holdout_pairs=int(edges.original_holdout.sum()),restricted_pairs=int(edges.restricted_member_n.gt(0).sum()),
        fusion_recomputed='only missing fixed-base eight-person subsets; frozen core unchanged',formal_eligibility_changed=False)
    save('SUMMARY.json',summary)
    plot_results()
    save('FIELD_CONTRACT.json',dict(schema='worker_wq_integration_20261015_v1',score_version=VERSION,
        input_sources=['current load_current_bundle()',str((QUALITY/'JOINT_COMPARISON_1145.csv').relative_to(ROOT)),
            str((QUALITY/'pro_closeout_delta.zip').relative_to(ROOT)),str(OLD.relative_to(ROOT)),str(POP.relative_to(ROOT))],
        Q_formula='100*I/(1+I*(Sb^2/32+1.5*D^2/(D^2+37.5)+(Hm/.8)^2+(Hc/.25)^2))',
        geometry_version='Exact current native snapshot and routing geometry compared to reviewed archive; full prepared fusion snapshot regenerated and compared.',
        identity='record_id/object_id/current W ids; cached P aliases bound via record IDs, not numeric position',
        units=dict(WQ='0..100 work score',IoU3D100='0..100 current corner-mean prism proxy',
            effect='axis units; sum-zero worker effect after image/condition/actual-reference intercept removal',
            height_vs_floor='log1p(height_loss)-log1p(boundary_loss+direction_loss)',
            floor_change='1-IoU between two complete fused footprints; 0..1',
            raw_pair_distance='mean annotation pair symmetric difference / fixed full image pool union',
            class_explained_fraction='descriptive between-sign-class share of entrant outcome variation inside a fixed base; not crossvalidated',
            class_gap='positive-axis entrant mean minus negative-axis entrant mean in a fixed base'),
        missing='NA is unavailable, unclassified, or zero-variance correlation as documented; not a zero-quality value',
        classes='positive/negative relative effects; no fixed population sizes; >=6 informative cells and >=3 buildings',
        inference='building-isolated profile diagnostic; dependent team pairs are not independent samples; original holdouts separate',
        reference_policy='Fixed prior frozen full reference per image, conditional subset comparison; unresolved full reference gives NA, never highest-Q selection',
        table_columns={p.name:list(pd.read_csv(p,nrows=0).columns) for p in sorted(OUT.glob('*.csv'))}))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def plot_results():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei']
    plt.rcParams['axes.unicode_minus']=False
    wide=pd.read_csv(OUT/'profile_wide.csv')
    base=pd.read_csv(OUT/'matched_base_comparisons.csv')
    base=base[(base.axis=='WQ')&(base.k==8)]
    fig,axes=plt.subplots(1,2,figsize=(15,7),gridspec_kw={'width_ratios':[1,1.3]})
    axes[0].scatter(wide.WQ,wide.IoU3D100,color='#2878a0')
    offsets={'W011':(-38,10),'W014':(5,20),'W017':(5,-16),'W021':(8,5),'W029':(6,-12),
             'W035':(10,-3),'W027':(-22,10),'W002':(5,5),'W012':(5,5),'W037':(5,-12)}
    for r in wide.itertuples():
        if r.worker_id in offsets:
            axes[0].annotate(r.worker_id,(r.WQ,r.IoU3D100),xytext=offsets[r.worker_id],
                textcoords='offset points',fontsize=8,arrowprops=dict(arrowstyle='-',lw=.5,color='#888888'))
    axes[0].axhline(0,color='#aaaaaa');axes[0].axvline(0,color='#aaaaaa')
    axes[0].set(title='同条件调整后的连续人员画像',xlabel='WQ 相对效应（分）',ylabel='IoU3D 相对效应（百分点）')
    images=sorted(base.image.unique())
    for y,code in enumerate(images):
        g=base[base.image.eq(code)]
        axes[1].scatter(100*g.floor_cross_minus_same,[y-.1,y+.1],
            color='#999999' if g.original_holdout.any() else '#b05a36',s=45)
    axes[1].axvline(0,color='#aaaaaa')
    axes[1].set_yticks(range(len(images)),[c+(' *' if base[base.image.eq(c)].original_holdout.any() else '') for c in images])
    axes[1].invert_yaxis()
    axes[1].set(title='固定7人基础团队：跨类换人减同类换人',xlabel='融合底面变化 1−IoU 的差（百分点）\n每点一个基础团队；负值表示跨类变化更小；*原留出诊断')
    fig.suptitle('质量画像可重复，类别变化不保证产生更大融合波动',fontsize=15)
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(OUT/'personnel_evidence.png',dpi=150);plt.close(fig)


if __name__=='__main__':
    main()
