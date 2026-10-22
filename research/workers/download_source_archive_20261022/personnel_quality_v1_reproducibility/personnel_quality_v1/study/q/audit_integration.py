#!/usr/bin/env python3
"""Independent read-only checks of fusion, reliability and reviewed-risk outputs."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import numpy as np
import pandas as pd


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(x):
    if isinstance(x, dict): return {str(k): normalize(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [normalize(v) for v in x]
    if isinstance(x, np.generic): return normalize(x.item())
    return x


def main(args):
    study = Path(args.study).resolve(); out = Path(args.out).resolve()
    rp = study / 'reliability'; fp = study / 'fusion'; ip = study / 'integration'; qp = study / 'q'
    source_files = [rp/'validated_annotations.json', rp/'reliability_object_ledger.csv', rp/'semi_scores_b8l2_d10.csv',
        fp/'primary_true_path_states.csv', fp/'out_of_building_member_profiles.csv', fp/'path_selection_manifest.csv',
        ip/'reviewed_risk_predictions.csv', qp/'fold_profiles_recomputed.csv']
    hashes = {str(p.relative_to(study)): sha(p) for p in source_files}
    receipt = {'data_release': 'v1', 'source_sha256': hashes, 'changed_other_agents_files': False}

    objects = json.loads((rp/'validated_annotations.json').read_text())
    byid = {o['object_id']: o for o in objects}
    led = pd.read_csv(rp/'reliability_object_ledger.csv')
    assert led.object_id.is_unique and len(led) == 3222
    neg = led[led.explicitly_accepted_negative_candidate]
    assert neg.individually_reviewed_flag.eq(True).all()
    for oid in neg.object_id:
        assert byid[oid]['review_evidence']['verdict'] in {'usable', 'retained_scope_variation'}
        assert byid[oid]['final_review']['individually_reviewed'] is True
    assert led.strict_specific_personal_severe.le(led.reviewer_personal_nonacceptance).all()
    a = set(led.loc[led.model_unchanged_audit_covered, 'object_id'])
    strict = set(led.loc[led.strict_specific_personal_severe, 'object_id'])
    broad = set(led.loc[led.reviewer_personal_nonacceptance, 'object_id'])
    receipt['review_denominators'] = dict(accepted_candidates=len(neg), accepted_individually_reviewed=len(neg),
        strict_events=len(strict), broad_events=len(broad), targeted_audit=len(a),
        strict_overlap_targeted_audit=len(strict & a), broad_overlap_targeted_audit=len(broad & a),
        duplicate_objects=0, accepted_is_not_error_free=True)

    semi = pd.read_csv(rp/'semi_scores_b8l2_d10.csv')
    assert semi.object_id.is_unique and len(semi) == 574
    unchanged = semi[semi.recovered_edit_status.eq('unchanged_coordinates') & semi.paired_score_available].copy()
    unchanged['payload_only_gain'] = unchanged.final_B8L2 - unchanged.initial_payload_B8L2
    falsegain = unchanged[unchanged.payload_only_gain.abs().gt(1e-8)]
    assert falsegain.initial_and_final_same_array_order.all()
    assert not falsegain.raw_final_equals_current.any()
    assert unchanged.gain_B8L2.abs().max() < 1e-8
    assert not semi.loc[semi.researcher_point_repair_applied, 'current_qualified_gain_available'].any()
    assert not semi.loc[semi.semi_profile_training_candidate, 'original_holdout'].any()
    assert semi.loc[semi.semi_profile_training_candidate, 'independent_vote_eligible'].all()
    assert semi.groupby(['initialization_hash', 'reference_id']).reference_version.nunique().le(1).all()
    coding = {r['object_id']: r for r in json.loads((rp/'exclusion_reason_coding.json').read_text())}
    assert set(coding) == set(led.loc[led.any_current_invalid, 'object_id'])
    for oid, entry in coding.items():
        texts = [r['text'] for r in entry['comments']]
        assert len(texts) == len(set(texts)), oid
    rejected = semi[semi.reviewer_personal_nonacceptance]
    receipt['semi_measurement'] = dict(rows=len(semi), paired_scores=int(semi.paired_score_available.sum()),
        final_recomputed=int(semi.final_score_status.eq('complete').sum()),
        unchanged_paired=len(unchanged), unchanged_max_abs_gain=float(unchanged.gain_B8L2.abs().max()),
        spurious_payload_only_gain_records=len(falsegain), spurious_payload_gain_min=float(falsegain.payload_only_gain.min()),
        spurious_payload_gain_max=float(falsegain.payload_only_gain.max()), raw_array_unchanged_in_every_spurious_case=True,
        all_current_repaired_excluded_from_gain_credit=True,
        training_candidates=int(semi.semi_profile_training_candidate.sum()),
        training_candidate_uses=semi[semi.semi_profile_training_candidate].current_quality_use.value_counts().to_dict(),
        native_unconfirmed_initial_ring_rows=int(semi.initial_ring_status.eq('native_initialization_ring_unconfirmed').sum()),
        rejected_semi=len(rejected), rejected_and_changed=int(rejected.recovered_edit_status.eq('changed_coordinates').sum()),
        rejected_and_positive_gain=int(rejected.gain_B8L2.gt(0).sum()))

    states = pd.read_csv(fp/'primary_true_path_states.csv')
    members = pd.read_csv(fp/'out_of_building_member_profiles.csv')
    choices = pd.read_csv(fp/'path_selection_manifest.csv')
    folds = pd.read_csv(qp/'fold_profiles_recomputed.csv')
    assert len(states) == 4032 and states.image.nunique() == 7 and states.building_id.nunique() == 6
    assert not states.duplicated(['image', 'path', 'k']).any()
    assert (states.groupby(['image', 'path']).k.agg(set).map(lambda x: x == set(range(1, 25)))).all()
    assert not states.original_holdout.any() and not states.is_oos.any()
    assert members.groupby('image').worker_id.nunique().eq(24).all()
    mm = members.set_index(['image', 'worker_id'])
    for r in members.itertuples():
        for axis in ['B8L2', 'D10', 'T_source']:
            assert r.building_id not in json.loads(getattr(r, axis+'_training_buildings'))
            if not getattr(r, axis+'_supported'): continue
            part = folds[(folds.axis == axis) & (folds.panel == ('current' if axis in ['B8L2', 'D10'] else 'T_source'))
                & folds.fold.eq(r.building_id) & folds.worker_id.eq(r.worker_id)]
            assert len(part) == 1 and abs(part.effect.iloc[0] - getattr(r, axis+'_effect')) < 1e-10
    totals_checked = 0
    for r in states.itertuples():
        ws = r.worker_ids.split('|'); ps = [mm.loc[(r.image, w)] for w in ws]
        assert len(ws) == len(set(ws)) == r.k
        assert set(r.subset.split('|')) == {p.source_worker for p in ps}
        for axis in ['B8L2', 'D10']:
            assert abs(np.mean([p[axis+'_effect'] for p in ps]) - getattr(r, axis+'_mean_effect')) < 1e-10
        for stem, col in [('source', 'source_active_time_seconds'), ('target_matched', 'target_matched_time_seconds')]:
            ts = [p[col] for p in ps]; known = [t for t in ts if pd.notna(t) and t > 0]
            value = getattr(r, stem+'_time_total_seconds')
            assert len(known) == getattr(r, stem+'_time_known_n')
            assert len(ts) - len(known) == getattr(r, stem+'_time_missing_n')
            assert (pd.isna(value) if len(known) != len(ts) else abs(value-sum(known)) < 1e-8)
            totals_checked += 1
    for (image, axis), c in choices.groupby(['image', 'axis']):
        expected = states[states.image.eq(image) & states.k.eq(8)].sort_values([axis+'_mean_effect', 'path'], ascending=[False, True])
        assert set(c.loc[c.selected_high, 'path']) == set(expected.head(6).path)
        assert set(c.loc[c.selected_low, 'path']) == set(expected.tail(6).path)
    endpoint = states[states.k.eq(24)]
    assert endpoint.groupby('image').subset.nunique().eq(1).all()
    assert endpoint.groupby('image').B8L2.nunique(dropna=False).eq(1).all()
    receipt['fusion'] = dict(attempts=len(states), images=7, buildings=6, successful=int(states.complete_evaluable.sum()),
        policy_k2=int(states.k.eq(2).sum()), other_incomplete=int((~states.complete_evaluable & ~states.k.eq(2)).sum()),
        real_path_count=int(states[['image','path']].drop_duplicates().shape[0]), full_prefix_membership_checks=len(states),
        separate_source_target_cost_checks=totals_checked, all_labels_recomputed_outside_target_building=True,
        high_low_path_policy_exact_from_external_Q=True, identical_full_pool_endpoint=True,
        geometry_was_not_rerun_by_this_auditor=True)

    risk = pd.read_csv(ip/'reviewed_risk_predictions.csv')
    scene = led[led.condition.eq('manual') & led.ordinary_task & led.reason_code.ne('personal_invalid_policy_ambiguous')]
    assert not risk.duplicated(['outcome_definition', 'evaluation', 'object_id', 'method']).any()
    assert risk.groupby(['outcome_definition','evaluation','object_id']).method.nunique().eq(6).all()
    maxerr = 0.; checked = 0; train_unique = 0
    for definition, defined in risk.groupby('outcome_definition'):
        panel = scene[scene['personal_binary_'+definition+'_eligible']].copy()
        target = 'personal_binary_'+definition+'_outcome'
        assert not panel.duplicated(['worker_id','image_id','condition']).any()
        dev = panel[~panel.current_original_holdout]
        for (evaluation, building), block in defined.groupby(['evaluation','building_id']):
            test = panel[panel.building_id.eq(building) & (panel.current_original_holdout if 'preserved' in evaluation else ~panel.current_original_holdout)]
            train = dev[dev.building_id.ne(building)].copy()
            assert set(block.object_id) == set(test.object_id)
            assert set(train.object_id).isdisjoint(set(test.object_id))
            assert not train.current_original_holdout.any() and building not in set(train.building_id)
            pooled = (train[target].sum()+.5)/(len(train)+1)
            classes = {}
            for axis in ['B8L2','D10']:
                qf = folds[(folds.panel=='current') & (folds.axis==axis) & folds.fold.eq(building)].set_index('worker_id')
                tf = folds[(folds.panel=='T_source') & folds.fold.eq(building)].set_index('worker_id')
                def qclass(w): return qf.loc[w,'label'] if w in qf.index and qf.loc[w,'supported'] else 'Q_unknown'
                def tclass(w): return tf.loc[w,'label'] if w in tf.index and tf.loc[w,'supported'] else 'T_unknown'
                classes['Q_'+axis] = ({w:qclass(w) for w in panel.worker_id.unique()})
                classes['QxT_'+axis] = ({w:qclass(w)+'|'+tclass(w) for w in panel.worker_id.unique()})
            for r in block.itertuples():
                assert r.training_n == len(train) and r.training_errors == int(train[target].sum())
                if r.method=='pooled': expected=pooled
                elif r.method=='worker_history':
                    wg=train[train.worker_id.eq(r.worker_id)]
                    expected=(wg[target].sum()+20*pooled)/(len(wg)+20)
                else:
                    mapping=classes[r.method]; cls=mapping[r.worker_id]
                    wg=train[train.worker_id.map(mapping).eq(cls)]
                    expected=pooled if cls.startswith('Q_unknown') or wg.empty else (wg[target].sum()+20*pooled)/(len(wg)+20)
                maxerr=max(maxerr,abs(expected-r.probability)); checked+=1
                assert abs(expected-r.probability) < 1e-12
                assert abs((r.outcome-r.probability)**2-r.brier) < 1e-12
            train_unique += 1
    receipt['reviewed_risk'] = dict(prediction_rows_verified=checked, independent_probability_max_abs_error=maxerr,
        training_fold_units_verified=train_unique, target_building_or_object_leakage=0, original_holdout_in_history=0,
        same_event_panel_for_all_six_methods=True, duplicated_events_within_definition_method=0,
        scope='selected explicitly adjudicated ordinary Manual records only; no population prevalence inference')
    assert {str(p.relative_to(study)): sha(p) for p in source_files} == hashes
    out.mkdir(parents=True, exist_ok=True)
    (out/'INTEGRATION_AUDIT_RECEIPT.json').write_text(json.dumps(normalize(receipt),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(normalize(receipt),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--study',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--out',default=str(Path(__file__).resolve().parent))
    main(parser.parse_args())
