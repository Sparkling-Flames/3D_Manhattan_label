"""Recompute the reviewed team pair, without changing fusion or scoring rules."""
import json
import subprocess
from copy import deepcopy
import argparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import personnel_type_validation_20261019 as v


def replace_pair_coordinates(points, donor, indices, component):
    result = deepcopy(points)
    for i in indices:
        if component == 'pair':
            result[2*i:2*i+2] = deepcopy(donor[2*i:2*i+2])
        elif component == 'x':
            result[2*i][0], result[2*i+1][0] = donor[2*i][0], donor[2*i+1][0]
        elif component in ('top_y', 'bottom_y'):
            j = 2*i + (component == 'bottom_y')
            result[j][1] = donor[j][1]
        else:
            raise ValueError(component)
    return result


def trace():
    source, fe = v.runtime(v.RUNTIME)
    audit = v.read(v.OUT/'CASE_SCORE_AUDIT.json')
    pool = next(p for p in v.read(source/'fusion/INPUT_SNAPSHOT.json.gz')['images'] if p['pool_id'] == audit['pool_id'])
    people = {r['worker_id']: r for r in pool['records']}
    originals = {w:deepcopy(people[w]['points']) for w in ['W131', 'W132']}
    assert len(originals['W131']) == len(originals['W132']) == 12
    common = set(audit['teams']['A']['members']) & set(audit['teams']['B']['members'])
    rows = []
    with fe.scoring_engine(fe.ENGINE/'measurement_engine.zip', fe.ENGINE/'working_models.py') as (engine, models):
        for receiver, donor, baseline in [('W131', 'W132', 'A'), ('W132', 'W131', 'B')]:
            jobs = [(i, component, [i]) for i in range(6) for component in ['pair', 'x', 'top_y', 'bottom_y']]
            jobs.append((-1, 'all_pairs', list(range(6))))
            for i, component, indices in jobs:
                selected = deepcopy([people[w] for w in sorted(common | {receiver})])
                modified = next(r for r in selected if r['worker_id'] == receiver)
                modified['points'] = replace_pair_coordinates(originals[receiver], originals[donor], indices,
                    'pair' if component == 'all_pairs' else component)
                # Same identities/order and all other records are held fixed; these are synthetic diagnostics.
                state = fe.compact(fe.fuse(selected, gap=fe.WORKING_GAP)['automatic'])
                score = fe.compute_score(state, pool, engine, models)
                rows.append(dict(receiver=receiver, donor=donor, baseline=baseline, pair_index=i, component=component,
                    B8L2=score['B8L2'], dir=score.get('dir'), nodes=len(state['node_consensus']['nodes']),
                    baseline_B8L2=audit['teams'][baseline]['score']['B8L2'], score_status=score['score_status'],
                    retained_supports=[g['support'] for g in state['identity_groups'] if g['selected']],
                    group_supports=[g['support'] for g in state['identity_groups']], candidate=state['candidate'],
                    assignments=state['assignments']))
                print(receiver, i, component, rows[-1]['nodes'], round(score['B8L2'],3) if score['B8L2'] is not None else None, flush=True)
        fig, ax = plt.subplots(figsize=(7, 6))
        for name, points, color, style in [('GT', pool['reference']['points_1024x512'], '#7c3aed', '--'),
                ('A / W131', originals['W131'], '#087f8c', '-'), ('B / W132', originals['W132'], '#b45309', ':')]:
            floor = np.asarray(engine.geometry(points)['bottom3d'])[:, [0, 2]]
            closed = np.vstack([floor, floor[0]])
            ax.plot(closed[:,0], closed[:,1], style, color=color, marker='o', label=name)
            indices = [3,2,1] if name == 'GT' else [5,4,3]
            for number, idx in enumerate(indices, 1):
                ax.annotate(str(number), floor[idx], xytext=(5, 8 if name=='GT' else -13), textcoords='offset points', color=color)
        ax.set_xlim(1.25, 2.65); ax.set_ylim(.65, -.45); ax.set_aspect('equal'); ax.grid(alpha=.2); ax.legend()
        ax.set_title('Original answers: local corners 1 / 2 / 3\nSource pair indices: 5 / 4 / 3 (zero based)')
        ax.set_xlabel('x / camera height'); ax.set_ylabel('z / camera height')
        fig.tight_layout(); fig.savefig(v.OUT/'case_original_numbered.png', dpi=160); plt.close(fig)
    assert originals == {w:people[w]['points'] for w in originals}
    for row in rows:
        if row['component'] == 'all_pairs':
            other = 'B' if row['baseline'] == 'A' else 'A'
            assert abs(row['B8L2']-audit['teams'][other]['score']['B8L2']) < 1e-10
    v.save(v.OUT/'CASE_POINT_CONTROLS.json', dict(schema='case_point_controls_v1',
        scope='synthetic diagnostics, not real teams or training samples', pool_id=pool['pool_id'],
        source_records={w:dict(object_id=people[w]['object_id'], points=originals[w]) for w in originals},
        matching='same source pair index; both six-pair rings start at the same physical corner',
        original_inputs_unchanged=True, rows=rows))


def main():
    source, fe = v.runtime(v.RUNTIME)
    pid = 'wc2JMjhGNzB-46__manual__ddafdd7484'
    pool = next(p for p in v.read(source/'fusion/INPUT_SNAPSHOT.json.gz')['images'] if p['pool_id'] == pid)
    cache = v.OUT/'runtime/pools'/pid
    results = v.read(cache/'request_results.json.gz')['results']
    states = {s['team_id']: s['automatic'] for s in v.read(cache/'states.json.gz')['states']}
    raw = (v.OUT/'view-data.js').read_text(encoding='utf-8')
    display = json.loads(raw.removeprefix('window.PERSONNEL_VALIDATION=').strip().removesuffix(';'))
    assert display['images'][pid]['reference']['points'] == pool['reference']['points_1024x512']
    report = dict(pool_id=pid, context=1, k=25, teams={}, checks={}, controls={})
    geometries = {}
    with fe.scoring_engine(fe.ENGINE/'measurement_engine.zip', fe.ENGINE/'working_models.py') as (engine, models):
        geometries['GT'] = engine.geometry(pool['reference']['points_1024x512'])
        for name, rid in [('A', 'b_8a53f7e09f5a90d84e3e'), ('B', 'b_e2f45f0175457dca2583')]:
            r = next(r for r in results if r['request_id'] == rid)
            state = states[r['team_id']]
            points = state['candidate']['points']
            assert points == display['teams'][rid]['points']
            assert r['B8L2'] == display['teams'][rid]['Q']
            members = r['member_workers'].split('|')
            selected = sorted([x for x in pool['records'] if x['worker_id'] in members], key=lambda x: x['worker_id'])
            fresh = fe.compact(fe.fuse(selected, gap=fe.WORKING_GAP)['automatic'])
            assert fresh == state, 'fresh fusion differs from saved state'
            geometry = engine.geometry(points)
            geometries[name] = geometry
            js = "const C=require('./research/statistics/research_explorer_v1_r2_20261017/workbench-core.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(C.geometry(JSON.parse(s)))));"
            shown = json.loads(subprocess.run(['node', '-e', js], input=json.dumps(points), text=True, capture_output=True, check=True, cwd=v.ROOT).stdout)
            error = max(float(np.max(np.abs(np.asarray(shown[k])-geometry[k+'3d']))) for k in ['bottom', 'top'])
            assert error < 1e-12
            score = fe.compute_score(state, pool, engine, models)
            assert abs(score['B8L2']-r['B8L2']) < 1e-10
            theta, lengths = engine.au.direction_data(geometry)
            axis = engine.au.direction_axis(geometry)
            residual = np.degrees((theta-axis+np.pi/4) % (np.pi/2)-np.pi/4)
            contributions = lengths/lengths.sum()*residual**2
            assert abs(np.sqrt(contributions.sum())-score['dir']) < 1e-10
            values = [score[k] for k in ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']]
            iou, bottom, direction, hmean, hcenter = values
            floor_loss = 1/iou-1+bottom**2/32
            direction_loss = 1.5*direction**2/(direction**2+64)
            height_loss = (hmean/.8)**2+(hcenter/.25)**2
            independent_score = 100/(1+np.hypot(floor_loss, direction_loss)+height_loss)
            assert abs(independent_score-score['B8L2']) < 1e-10
            attr = models.attribution(*values, models.MODELS['B8L2'])
            groups = [dict(feature_id=g['feature_id'], support=g['support'], selected=g['selected'],
                           members=[(m['worker'], m['pair_index']) for m in g['members']]) for g in state['identity_groups']]
            report['teams'][name] = dict(request_id=rid, points=points, geometry=geometry, members=members,
                score=score, B8L2_attribution=attr, B8L2_direction_zero=attr['score']+attr['delete_intrinsic_direction_gain'],
                axis_deg=float(np.degrees(axis)), minimum_support=state['minimum_support'], groups=groups,
                edges=[dict(start=i, end=(i+1)%len(lengths), length_h=float(lengths[i]),
                    perimeter_fraction=float(lengths[i]/lengths.sum()), residual_deg=float(residual[i]),
                    direction_squared_share=float(contributions[i]/contributions.sum())) for i in range(len(lengths))])
            report['checks'][name] = dict(fresh_fusion_exact=True, saved_score_recomputed=True, display_points_exact=True, browser_geometry_max_error=error)
        # Diagnostic deletion of B's inside corner isolates this shape error; never used as a new team result.
        bpoints = report['teams']['B']['points']
        control = engine.geometry(bpoints[:4]+bpoints[6:])
        measured = engine.measure(control, geometries['GT'])
        report['controls']['B_delete_corner_2_only'] = dict(meaning='synthetic diagnostic, not real team or proposed correction',
            metrics=measured['metrics'], scores=fe.dual_scores(measured['metrics'], models))
    assert len(set(report['teams']['A']['members']) & set(report['teams']['B']['members'])) == 24
    report['checks']['same_reference_points'] = True
    report['checks']['common_members'] = 24
    v.save(v.OUT/'CASE_SCORE_AUDIT.json', report)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax in axes:
        for name, color, style in [('GT', '#7c3aed', '--'), ('A', '#087f8c', '-'), ('B', '#b45309', ':')]:
            floor = np.asarray(geometries[name]['bottom3d'])[:, [0, 2]]
            closed = np.vstack([floor, floor[0]])
            ax.plot(closed[:, 0], closed[:, 1], style, color=color, marker='o', markersize=4, label=name)
        ax.set_aspect('equal'); ax.grid(alpha=.2); ax.set_xlabel('x / camera height'); ax.set_ylabel('z / camera height'); ax.legend()
    axes[0].set_title('Same saved team geometry: full floor')
    axes[1].set_title('Local corner: A diagonal vs B / GT turn')
    axes[1].set_xlim(1.4, 2.2); axes[1].set_ylim(-.35, .55)
    fig.tight_layout(); fig.savefig(v.OUT/'case_score_floor.png', dpi=160); plt.close(fig)
    print(json.dumps(dict(checks=report['checks'],
        controls=report['controls'], scores={k:dict(B8L2=x['score']['B8L2'], no_direction=x['B8L2_direction_zero']) for k,x in report['teams'].items()}), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--trace', action='store_true')
    if parser.parse_args().trace:
        trace()
    else:
        main()
