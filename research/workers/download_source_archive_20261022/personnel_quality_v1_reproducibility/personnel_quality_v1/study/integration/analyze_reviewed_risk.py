#!/usr/bin/env python3
"""Data-v1 secondary prediction probe on explicitly reviewed outcomes only.

This does not estimate population error prevalence. No eligibility is changed.
All Q/T profiles and event histories exclude the target building; all histories
exclude the repository's existing original-holdout records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261017
BOOTSTRAPS = 2000
SHRINKAGE = 20.0
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--study', type=Path, default=HERE.parent)
    ap.add_argument('--out', type=Path, default=HERE)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ledger_path = args.study / 'reliability/reliability_object_ledger.csv'
    profiles_path = args.study / 'q/fold_profiles_recomputed.csv'
    ledger = pd.read_csv(ledger_path)
    profiles = pd.read_csv(profiles_path)
    assert ledger.object_id.is_unique
    scene = ledger[ledger.condition.eq('manual') & ledger.ordinary_task
                   & ledger.reason_code.ne('personal_invalid_policy_ambiguous')].copy()
    assert not scene.oos.any() and not scene.doorway.any()
    assert not scene.gt_error_excluded_current.any()
    registered = json.loads((HERE / 'RISK_REGISTRATION.json').read_text())
    prediction_rows = []
    profile_checks = []
    coverage_rows = []
    worker_rows = []
    for outcome in ['broad', 'strict']:
        target = 'personal_binary_' + outcome + '_outcome'
        panel = scene[scene['personal_binary_' + outcome + '_eligible']].copy()
        assert len(panel) == registered['denominators_frozen'][outcome]
        assert panel[target].sum() == registered['denominators_frozen'][outcome + '_positive']
        assert not panel.duplicated(['worker_id', 'image_id', 'condition']).any()
        assert panel[target].notna().all()
        panel['outcome'] = panel[target].astype(int)
        development = panel[~panel.current_original_holdout]
        for worker, group in panel.groupby('worker_id'):
            worker_rows.append(dict(outcome_definition=outcome, worker_id=worker,
                adjudicated_records=len(group), personal_rejections=int(group.outcome.sum()),
                adjudicated_fraction=float(group.outcome.mean()),
                buildings=group.building_id.nunique(),
                current_original_holdout_records=int(group.current_original_holdout.sum()),
                unknown_or_other_records_in_selected_scene=int((scene.worker_id.eq(worker)).sum()-len(group))))
        for eval_name, evaluation in [('reviewed_development_LOBO', development),
                                      ('reviewed_preserved_original_holdout', panel[panel.current_original_holdout])]:
            coverage_rows.append(dict(outcome_definition=outcome, evaluation=eval_name,
                n=len(evaluation), errors=int(evaluation.outcome.sum()), workers=evaluation.worker_id.nunique(),
                images=evaluation.image_id.nunique(), buildings=evaluation.building_id.nunique()))
            for building, test in evaluation.groupby('building_id'):
                train = development[development.building_id.ne(building)].copy()
                assert not train.current_original_holdout.any()
                assert building not in train.building_id.values
                p0 = (train.outcome.sum() + 0.5) / (len(train) + 1)
                history = train.groupby('worker_id').outcome.agg(['size', 'sum'])
                class_frames = {}
                for axis in ['B8L2', 'D10']:
                    q = profiles[(profiles.panel == 'current') & (profiles.axis == axis) & (profiles.fold == building)]
                    t = profiles[(profiles.panel == 'T_source') & (profiles.axis == 'T_source') & (profiles.fold == building)]
                    assert q.worker_id.is_unique and t.worker_id.is_unique
                    for source in [q, t]:
                        for _, row in source.iterrows():
                            assert building not in json.loads(row.training_buildings)
                    qmap = q.set_index('worker_id')
                    tmap = t.set_index('worker_id')
                    assignments = {}
                    for worker in sorted(set(train.worker_id) | set(test.worker_id)):
                        qc = 'Q_unknown'
                        tc = 'T_unknown'
                        if worker in qmap.index and bool(qmap.loc[worker, 'supported']):
                            qc = str(qmap.loc[worker, 'label'])
                        if worker in tmap.index and bool(tmap.loc[worker, 'supported']):
                            tc = str(tmap.loc[worker, 'label'])
                        assignments[worker] = (qc, qc + '|' + tc)
                    for cls_kind, ci in [('Q', 0), ('QxT', 1)]:
                        mapping = {worker: pair[ci] for worker, pair in assignments.items()}
                        g = train.assign(personnel_class=train.worker_id.map(mapping)).groupby('personnel_class').outcome.agg(['size', 'sum'])
                        class_frames[cls_kind + '_' + axis] = (mapping, g)
                    profile_checks.append(dict(outcome_definition=outcome, evaluation=eval_name,
                        heldout_building=building, axis=axis, training_n=len(train), training_errors=int(train.outcome.sum()),
                        training_buildings=json.dumps(sorted(train.building_id.unique())),
                        Q_workers=len(q), Q_supported=int(q.supported.sum()),
                        T_workers=len(t), T_supported=int(t.supported.sum()), target_building_leakage=False))
                for _, row in test.iterrows():
                    base = dict(outcome_definition=outcome, evaluation=eval_name,
                        object_id=row.object_id, worker_id=row.worker_id, image_id=row.image_id,
                        image_code=row.image_code, building_id=building, outcome=int(row.outcome),
                        reason_code=row.reason_code, original_holdout=bool(row.current_original_holdout),
                        training_n=len(train), training_errors=int(train.outcome.sum()), pooled_probability=float(p0))
                    estimates = [('pooled', p0, 'all', len(train), train.outcome.sum(), False)]
                    if row.worker_id in history.index:
                        n, e = history.loc[row.worker_id, ['size', 'sum']]
                    else:
                        n, e = 0, 0
                    estimates.append(('worker_history', (e+SHRINKAGE*p0)/(n+SHRINKAGE), row.worker_id, n, e, n == 0))
                    for method, (mapping, g) in class_frames.items():
                        cls = mapping[row.worker_id]
                        if cls in g.index and not cls.startswith('Q_unknown'):
                            n, e = g.loc[cls, ['size', 'sum']]
                            p = (e+SHRINKAGE*p0)/(n+SHRINKAGE)
                            unknown = False
                        else:
                            n, e, p, unknown = 0, 0, p0, True
                        estimates.append((method, p, cls, n, e, unknown))
                    for method, p, cls, n, e, unknown in estimates:
                        prediction_rows.append({**base, 'method': method, 'personnel_class': cls,
                            'class_or_worker_training_n': int(n), 'class_or_worker_training_errors': int(e),
                            'probability': float(p), 'fallback_to_pooled': bool(unknown),
                            'brier': float((row.outcome-p)**2), 'pooled_brier': float((row.outcome-p0)**2)})
    pred = pd.DataFrame(prediction_rows)
    by_building = pred.groupby(['outcome_definition','evaluation','method','building_id']).agg(
        n=('outcome','size'), errors=('outcome','sum'), brier=('brier','mean'),
        pooled_brier=('pooled_brier','mean'), fallback_records=('fallback_to_pooled','sum')).reset_index()
    summaries = []
    rng = np.random.default_rng(SEED)
    for (outcome, evaluation), eframe in by_building.groupby(['outcome_definition','evaluation']):
        buildings = sorted(eframe.building_id.unique())
        draws = rng.integers(0, len(buildings), (BOOTSTRAPS, len(buildings)))
        for method, group in eframe.groupby('method'):
            group = group.set_index('building_id').reindex(buildings)
            y = group.brier.to_numpy(); z = group.pooled_brier.to_numpy()
            delta = z-y
            boot_delta = delta[draws].mean(1)
            boot_reduction = 1-y[draws].mean(1)/z[draws].mean(1)
            raw = pred[(pred.outcome_definition==outcome)&(pred.evaluation==evaluation)&(pred.method==method)]
            leave_b = [float(1-np.delete(y,i).mean()/np.delete(z,i).mean()) for i in range(len(y))] if len(y)>1 else [np.nan]
            summaries.append(dict(outcome_definition=outcome,evaluation=evaluation,method=method,
                n=int(group.n.sum()), errors=int(group.errors.sum()), buildings=len(group),
                record_weighted_brier=float(raw.brier.mean()), building_equal_brier=float(y.mean()),
                building_equal_pooled_brier=float(z.mean()),
                building_equal_brier_improvement=float(delta.mean()),
                improvement_bootstrap_low=float(np.quantile(boot_delta,.025)),
                improvement_bootstrap_high=float(np.quantile(boot_delta,.975)),
                relative_brier_reduction=float(1-y.mean()/z.mean()),
                reduction_bootstrap_low=float(np.quantile(boot_reduction,.025)),
                reduction_bootstrap_high=float(np.quantile(boot_reduction,.975)),
                delete_one_building_reduction_min=float(min(leave_b)),
                delete_one_building_reduction_max=float(max(leave_b)),
                fallback_records=int(group.fallback_records.sum())))
    files = {
        'reviewed_risk_predictions.csv':pred,
        'reviewed_risk_by_building.csv':by_building,
        'reviewed_risk_summary.csv':pd.DataFrame(summaries),
        'reviewed_risk_profile_checks.csv':pd.DataFrame(profile_checks),
        'reviewed_risk_coverage.csv':pd.DataFrame(coverage_rows),
        'reviewed_risk_worker_counts.csv':pd.DataFrame(worker_rows)
    }
    for name, value in files.items(): value.to_csv(args.out/name,index=False,encoding='utf-8-sig')
    receipt = dict(data_release='v1', status='completed', registration_sha256=digest(HERE/'RISK_REGISTRATION.json'),
        inputs={str(p.relative_to(args.study)):digest(p) for p in [ledger_path,profiles_path]},
        seed=SEED, bootstrap_replicates=BOOTSTRAPS, fixed_shrinkage=SHRINKAGE,
        no_duplicate_worker_image_condition=True, target_building_training_overlap=0,
        original_holdout_in_any_training_history=0,
        estimand=registered['estimand'], output_rows={k:len(v) for k,v in files.items()},
        limits=registered['limits'])
    (args.out/'REVIEWED_RISK_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(coverage_rows).to_string(index=False))
    print(pd.DataFrame(summaries)[['outcome_definition','evaluation','method','n','errors','buildings',
         'building_equal_brier','relative_brier_reduction','reduction_bootstrap_low','reduction_bootstrap_high']].to_string(index=False))
    print('COMPLETED: target-building overlap 0; original-holdout training overlap 0; population prevalence NOT estimated.')


if __name__ == '__main__': main()
