"""Pilot simulated annotators for visual review: archetype x image type.

Generates a small batch of simulated annotations per worker archetype on a
stratified set of images (simple/medium/hard/doorway), writes review_cases.json
and renders the self-contained review page with render_simulated_annotators.

Local-only experiment. Simulated rows are marked synthetic=True; template
worker archetypes come from worker_archetype_quadrants.py.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tools.thesis_main.analysis import simulate_annotators as s1
from tools.thesis_main.analysis.simulate_annotators_opt import simulate_v2, fit_holdout, normalize_worker_id, diagnostics
from tools.thesis_main.analysis.simulated_response_metadata import load_evidence, augment

ROOT = Path(__file__).resolve().parents[3]

PILOT_IMAGES = {
    'simple': ['uNb9QFRL6hY_c1ebb8b34eb846ba9b5ce23b30b299a7',
               'B6ByNegPMKs_cee80ced97274e248d4ccaa582e12624'],
    'medium': ['uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97'],
    'hard': ['UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65',
             'VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d'],
    'unclassified_doorway': ['q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4',
                             'UwV83HsGsw3_71ada030981d4468b76dcebc1b6fb940'],
}


def archetypes(path):
    out = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            q = r['quadrant']
            if q not in ('fast_good', 'fast_bad', 'slow_good', 'slow_bad'):
                continue
            out.setdefault(q, []).append(r['worker'])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20261014)
    ap.add_argument('--per-archetype', type=int, default=4)
    ap.add_argument('--cap', type=float, default=8.0)
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--independent-endpoints', action='store_true')
    ap.add_argument('--count-mode', action='store_true')
    ap.add_argument('--quadrants', type=Path, required=True,
                    help='Explicit quadrant table produced by worker_archetype_quadrants')
    ap.add_argument('--conditions', nargs='+', choices=('manual', 'semi'), default=['manual', 'semi'])
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit('Output exists; use a new directory')
    if args.per_archetype < 2 or args.cap <= 0 or args.scale <= 0:
        raise SystemExit('per-archetype >= 2 and positive cap/scale required')
    args.output.mkdir(parents=True)
    human, models, images, exclusions = s1.load_inputs()
    grouped = {}
    for h in human:
        grouped.setdefault(h['image_id'], []).append(h)
    arch = archetypes(args.quadrants)
    if len(arch) != 4:
        raise SystemExit('All four archetypes require eligible templates')
    evidence = load_evidence()
    cases, metrics = [], []
    for label, iids in PILOT_IMAGES.items():
        for iid in iids:
            if iid not in models or not all(k in models[iid] for k in s1.FAMILIES):
                print('skip (no complete bank):', iid)
                continue
            building = images[iid]['building_id']
            learned = fit_holdout(human, models, building)
            photo = next(iter((ROOT / 'data/mp3d_layout').glob(f'*/img/{iid}.png')), None)
            case = dict(image_id=iid, image_type=label, building_id=building, image_path=str(photo) if photo else '',
                        models=list(models[iid].values()),
                        human=[dict(name='真实 W' + h['worker_id'], points=h['points']) for h in grouped.get(iid, [])],
                        synthetic=[])
            for q, templates in arch.items():
                prof_ids = sorted({normalize_worker_id(w) for w in templates}, key=int)
                roster = [f'{q}_{j + 1:02d}' for j in range(args.per_archetype)]
                pmap = {w: prof_ids[j % len(prof_ids)] for j, w in enumerate(roster)}
                gen = simulate_v2(models[iid], learned, roster, 'worker',
                                  s1.seed_for(args.seed, iid, q), iid,
                                  no_x_collapse=args.independent_endpoints, cap=args.cap, scale=args.scale,
                                  count_mode=args.count_mode, worker_profile_map=pmap, tries=1)
                for condition in dict.fromkeys(args.conditions):
                    augmented = []
                    for g in gen:
                        row = augment(g, models[iid], evidence, building, condition,
                                      s1.seed_for(args.seed, iid, g['simulated_worker_id'], condition))
                        row.update(archetype=q, held_out_building=building,
                                   simulation_id=g['simulation_id'] + ':' + condition)
                        row['name'] = f'{q} / {condition} / 模板 {row["source_worker_profile_id"]}'
                        augmented.append(row)
                        case['synthetic'].append(row)
                    metrics.append(dict(image_id=iid, building_id=building, archetype=q, condition=condition,
                        **s1.comparison([h['points'] for h in grouped[iid]], augmented), **diagnostics(augmented)))
            cases.append(case)
            print('case', iid, label, 'human', len(case['human']), 'synthetic', len(case['synthetic']), flush=True)
    (args.output / 'review_cases.json').write_text(
        json.dumps({'cases': cases, 'default_examples': [c['image_id'] for c in cases]},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    samples = [r for c in cases for r in c['synthetic']]
    s1.write_jsonl(args.output / 'simulations.jsonl', samples)
    s1.write_csv(args.output / 'evaluation.csv', metrics)
    import collections
    source_paths = [args.quadrants, Path(__file__), s1.REVIEWED,
                    s1.INPUT / 'models/layouts.jsonl',
                    s1.ROOT / 'tools/thesis_main/analysis/simulate_annotators_opt.py',
                    s1.ROOT / 'tools/thesis_main/analysis/simulated_response_metadata.py',
                    s1.ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv',
                    s1.ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence/semi_initial_final_changes.csv',
                    s1.ROOT / 'analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv']
    s1.dump(args.output / 'summary.json', dict(
        seed=args.seed, images=len(cases), samples=len(samples), synthetic=True,
        conditions=args.conditions, cap=args.cap, scale=args.scale,
        independent_endpoints=args.independent_endpoints, count_mode=args.count_mode,
        profile_missing=sum(not r['profile_found'] for r in samples),
        residual_sources=dict(collections.Counter(r['residual_source'] for r in samples)),
        semi_status=dict(collections.Counter(r['semi_status'] for r in samples)),
        timing_status=dict(collections.Counter(r['timing_status'] for r in samples)),
        scope_status=dict(collections.Counter(r['scope_status'] for r in samples)),
        source_sha256={str(p): s1.digest(p) for p in source_paths},
        metadata_training='target building excluded from all donor channels',
        scope_policy='worker response sampling; no floor polygon adjudication'))
    from tools.thesis_main.analysis.render_simulated_annotators import main as render_main
    import sys
    sys.argv = ['render_simulated_annotators.py', '--run-dir', str(args.output)]
    render_main()
    print('DONE', args.output)


if __name__ == '__main__':
    main()
