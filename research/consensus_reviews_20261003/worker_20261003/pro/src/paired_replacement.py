"""One-person replacements with the other k-1 members held fixed.

This consumes already computed subset scores. It is not a new aggregation rule,
not a causal study of real-time social influence, and not a geometry-variation
estimator: scalar IoU alone does not recover differences between shapes.
"""
from __future__ import annotations
from itertools import combinations
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

def paired_effects(members: np.ndarray, scores: np.ndarray, workers: list[str]) -> pd.DataFrame:
    members = np.asarray(members, dtype=int)
    scores = np.asarray(scores, dtype=float)
    if members.ndim != 2 or scores.shape != (len(members),) or not np.isfinite(scores).all():
        raise ValueError('invalid complete-subset score table')
    n, k = len(workers), members.shape[1]
    if len(set(workers)) != n or k < 1 or k >= n:
        raise ValueError('invalid roster or subset size')
    canonical = [tuple(sorted(map(int, row))) for row in members]
    if any(len(set(t)) != k or min(t) < 0 or max(t) >= n for t in canonical):
        raise ValueError('invalid member indices')
    lookup = dict(zip(canonical, scores))
    if len(lookup) != len(scores) or set(lookup) != set(combinations(range(n), k)):
        raise ValueError('all distinct k-person subsets required')
    rows = []
    for a, b in combinations(range(n), 2):
        eligible = [j for j in range(n) if j not in (a, b)]
        delta = np.array([lookup[tuple(sorted((*t, a)))] - lookup[tuple(sorted((*t, b)))]
                          for t in combinations(eligible, k-1)])
        rows.append(dict(worker_a=workers[a], worker_b=workers[b], k=k,
                         common_context_n=len(delta), mean_a_minus_b=float(delta.mean()),
                         sd_a_minus_b=float(delta.std()), p10=float(np.quantile(delta, .1)),
                         p90=float(np.quantile(delta, .9)),
                         a_better_fraction=float(np.mean(delta > 1e-12)),
                         b_better_fraction=float(np.mean(delta < -1e-12)),
                         ties_fraction=float(np.mean(np.abs(delta) <= 1e-12))))
    return pd.DataFrame(rows)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, help='Full repository worker_profiles_20261003 output directory')
    parser.add_argument('--out', type=Path, default=ROOT/'results/paired_replacements')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.source_dir:
        roster = json.loads((args.source_dir/'rosters.json').read_text(encoding='utf-8'))
        with np.load(args.source_dir/'subsets.npz', allow_pickle=False) as archive:
            for group in roster['groups']:
                for method in ('mv50', 'mv_strict'):
                    for version in ('original', 'manual_revision'):
                        key=f"{group['key']}_{method}_{version}"
                        if key not in archive: continue
                        out=paired_effects(archive['members'], archive[key], roster['workers'])
                        out.insert(0,'reference_version',version);out.insert(0,'method',method)
                        out.insert(0,'image',group['image'])
                        out.to_csv(args.out/f'{key}.csv',index=False)
        return
    # Executed demonstration uses only the genuinely mounted one-image extract.
    obj=json.loads((ROOT/'inputs/one_image_geometry.json').read_text())
    workers=[r['worker'] for r in obj['records']]
    for method in ('mv50','mv_strict'):
        with np.load(ROOT/f'results/one_image_k4_{method}.npz',allow_pickle=False) as archive:
            out=paired_effects(archive['members'],archive['iou'],workers)
            out.insert(0,'image',obj['image']);out.insert(1,'method',method)
            out.to_csv(args.out/f'{method}.csv',index=False)
    print('One-image paired replacement demonstration complete; full repository mode not executed.')

if __name__=='__main__': main()
