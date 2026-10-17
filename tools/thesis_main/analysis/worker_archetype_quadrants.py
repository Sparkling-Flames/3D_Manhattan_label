"""Worker archetype quadrants: quality x speed, from frozen real evidence.

Reads the frozen worker profiles (10-image panel IoU), per-answer IoU metrics and
per-annotation active time. Outputs a local-only quadrant table used to pick
templates for simulated annotators. No writes to tracked research inputs.

Quality axis: median per-answer IoU (original GT, all computable answers).
Speed axis: median active_time_seconds (formal time available, all conditions).
Excluded workers (W019/W026) are kept in the table but flagged.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv'
ANSWER_METRICS = ROOT / 'analysis_results/worker_profiles_20261003/answer_metrics.csv'
PROFILES = ROOT / 'analysis_results/worker_profiles_20261003/worker_profiles.csv'
ROSTERS = ROOT / 'analysis_results/worker_profiles_20261003/rosters.json'
PREPROCESSED = ROOT / 'analysis_results/research_input_20260929/preprocessed_source.json'
EXCLUDED = {'W019', 'W026'}  # workers excluded in prior research (P013/P016)


def build_p_to_w() -> dict:
    """Authoritative P-number -> W-number mapping.

    The research bundle numbers objects R00001.. by sorted object_id
    (see audit_worker_returns_20261003.py); rosters.zip(workers, record_ids)
    binds P-numbers to R-ids. Anchor check: R00020 must be P002/W002.
    """
    pre = json.loads(PREPROCESSED.read_text(encoding='utf-8'))
    objs = sorted(pre['objects'], key=lambda r: r['object_id'])
    r2w = {f'R{j:05d}': o.get('worker_id') for j, o in enumerate(objs, 1)}
    rosters = json.loads(ROSTERS.read_text(encoding='utf-8'))
    pw = {}
    conflicts = []
    for g in rosters['groups']:
        for p, r in zip(rosters['workers'], g['record_ids']):
            w = r2w.get(r)
            if w is None:
                continue
            if p in pw and pw[p] != w:
                conflicts.append((p, pw[p], w, r))
            pw[p] = w
    if conflicts:
        raise ValueError(f'P-W mapping conflicts: {conflicts}')
    if pw.get('P002') != 'W002':
        raise ValueError(f'Anchor failed: P002 -> {pw.get("P002")}, expected W002')
    return pw


def wnum(value: str) -> str:
    """Normalize any worker id spelling to the zero-padded W-number."""
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if digits:
        digits = digits.lstrip('0') or '0'
        return f'W{int(digits):03d}'
    return str(value)


def load_time() -> dict:
    out = {}
    with open(EVIDENCE, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            w = wnum(row['worker_id'])
            rec = out.setdefault(w, {'n': 0, 'times': [], 'n_time': 0,
                                     'manual_times': [], 'semi_times': []})
            rec['n'] += 1
            try:
                t = float(row.get('active_time_seconds') or '')
            except (TypeError, ValueError):
                t = None
            formal = row.get('time_active_time_formal_available', '').lower() == 'true'
            complete = row.get('active_time_owner_valid_status') == 'owner_valid_complete'
            if t is not None and math.isfinite(t) and t > 0 and formal and complete:
                rec['times'].append(t)
                rec['n_time'] += 1
                cond = (row.get('assistance_exposure') or '').strip()
                if cond == 'none':
                    rec['manual_times'].append(t)
                elif cond == 'model_preannotation':
                    rec['semi_times'].append(t)
    return out


def load_quality() -> dict:
    out = {}
    with open(ANSWER_METRICS, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row.get('version') != 'original':
                continue
            w = row['worker']  # P-number
            rec = out.setdefault(w, {'n': 0, 'iou': []})
            rec['n'] += 1
            try:
                iou = float(row['iou'])
            except (TypeError, ValueError):
                continue
            rec['iou'].append(iou)
    with open(PROFILES, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row.get('policy') != 'original':
                continue
            w = row['worker']
            out.setdefault(w, {'n': 0, 'iou': []})
            out[w]['profile_mean_iou'] = float(row['mean_iou'])
            out[w]['profile_median_iou'] = float(row['median_iou'])
            out[w]['profile_rank'] = row.get('descriptive_iou_rank')
            out[w]['profile_image_n'] = row.get('image_n')
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path,
                    default=ROOT / 'analysis_results/simulated_annotators_local_20261014/worker_archetypes')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    pw_map = build_p_to_w()
    times = load_time()
    quals = load_quality()
    workers = sorted(set(times) | {w for w in pw_map.values()}, key=lambda w: int(w[1:]))

    rows = []
    for w in workers:
        t = times.get(w, {})
        p_ids = [p for p, ww in pw_map.items() if ww == w]
        q = {}
        for p in p_ids:
            q = quals.get(p, {})
            if q:
                break
        ious = [v for v in q.get('iou', []) if v is not None]
        # Compare manual speed with manual geometry quality; retain Semi separately.
        ts = t.get('manual_times', [])
        rows.append({
            'worker': w,
            'person_id': '|'.join(p_ids),
            'excluded_prior': w in EXCLUDED,
            'n_answers': t.get('n', 0),
            'n_time': t.get('n_time', 0),
            'median_active_s': round(statistics.median(ts), 1) if ts else None,
            'median_manual_active_s': round(statistics.median(t['manual_times']), 1) if t.get('manual_times') else None,
            'median_semi_active_s': round(statistics.median(t['semi_times']), 1) if t.get('semi_times') else None,
            'n_iou_answers': q.get('n', 0),
            'median_iou': round(statistics.median(ious), 4) if ious else None,
            'mean_iou': round(statistics.mean(ious), 4) if ious else None,
            'profile_mean_iou': q.get('profile_mean_iou'),
            'profile_rank': q.get('profile_rank'),
            'profile_image_n': q.get('profile_image_n'),
        })

    usable = [r for r in rows if not r['excluded_prior'] and r['median_active_s'] is not None and r['median_iou'] is not None]
    med_iou = statistics.median(r['median_iou'] for r in usable)
    med_time = statistics.median(r['median_active_s'] for r in usable)
    for r in rows:
        if r['excluded_prior'] or r['median_active_s'] is None or r['median_iou'] is None:
            r['quadrant'] = 'excluded_or_no_data'
            continue
        fast = r['median_active_s'] <= med_time
        good = r['median_iou'] >= med_iou
        r['quadrant'] = ('fast_good' if fast and good else
                         'fast_bad' if fast and not good else
                         'slow_good' if not fast and good else 'slow_bad')
    with open(args.output / 'worker_quadrants.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'pool_median_iou': round(med_iou, 4),
        'pool_median_active_s': round(med_time, 1),
        'usable_workers': len(usable),
        'quality_policy': 'original_only',
        'speed_policy': 'manual_formal_owner_valid_complete_only',
        'counts': {q: sum(1 for r in rows if r['quadrant'] == q) for q in
                   ('fast_good', 'fast_bad', 'slow_good', 'slow_bad', 'excluded_or_no_data')},
        'anchors': {w: next((r['quadrant'] for r in rows if r['worker'] == w), None)
                    for w in ('W001', 'W002', 'W017', 'W027')},
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
