"""All adopted direct pairs, declared groups, and matched unknown relations.

python run_similarity.py --repo /path/to/3D_Manhattan_label --out /path/to/output
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse
from pathlib import Path
import itertools
import json
import warnings
import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance, spearmanr
from common import load, save_csv, COMMIT, RELATION_VERSION, METRICS, cluster_interval
warnings.filterwarnings('ignore', category=RuntimeWarning)

def image_table(q):
    rows = []
    for origin in ['all', 'v1', 'new']:
        z = q if origin == 'all' else q[q.origin.eq(origin)]
        for (image, condition), a in z.groupby(['image_id', 'condition']):
            x = {k: a.iloc[0][k] for k in ['image_id', 'image_code', 'condition', 'building_id', 'layer', 'current_class', 'reference_id', 'reference_version', 'chosen_target_id', 'N_floor', 'N_turn', 'H', 'main_visual_space', 'expected_annotation_extent']}
            x.update(origin=origin, n=len(a), worker_ids='|'.join(sorted(a.worker_id)), object_ids='|'.join(sorted(a.object_id)))
            for metric in METRICS:
                v = a[metric].dropna()
                x.update({metric + '_mean': v.mean(), metric + '_sd': v.std(), metric + '_q10': v.quantile(0.1), metric + '_q25': v.quantile(0.25), metric + '_median': v.median(), metric + '_low50': v.lt(50).mean()})
            rows.append(x)
    return pd.DataFrame(rows)

def pairs(q, rel, images):
    rows = []
    coverage = []
    cells = {(im, con): a.set_index('worker_id') for (im, con), a in q.groupby(['image_id', 'condition'])}
    for j, r in enumerate(rel):
        for con in ['manual', 'semi']:
            a = cells.get((r['image_a'], con))
            b = cells.get((r['image_b'], con))
            coverage.append(dict(pair_index=j, image_a=r['image_a'], image_b=r['image_b'], condition=con, physical_adopted=r['physical_adopted'], scope_comparable=r['scope_comparable'], substantive_conflict=r['substantive_conflict'], user_group_ids='|'.join(r['user_group_ids']), quality_n_a=0 if a is None else len(a), quality_n_b=0 if b is None else len(b)))
            if a is None or b is None or (not r['physical_adopted']):
                continue
            for origin in ['all', 'v1', 'new']:
                aa = a if origin == 'all' else a[a.origin.eq(origin)]
                bb = b if origin == 'all' else b[b.origin.eq(origin)]
                if aa.empty or bb.empty:
                    continue
                common = aa.index.intersection(bb.index)
                layer = 'doorway' if aa.is_doorway.any() or bb.is_doorway.any() else 'ordinary'
                for metric in METRICS:
                    va = aa[metric].dropna()
                    vb = bb[metric].dropna()
                    w = va.index.intersection(vb.index)
                    ca = va.loc[w]
                    cb = vb.loc[w]
                    delta = cb - ca
                    all_delta = vb.mean() - va.mean()
                    common_delta = delta.mean()
                    valid_rank = len(w) >= 3 and ca.nunique() > 1 and (cb.nunique() > 1)
                    row = dict(pair_id=f'R{j:04d}', pair_index=j, image_a=r['image_a'], image_b=r['image_b'], code_a=aa.image_code.iloc[0], code_b=bb.image_code.iloc[0], building_id=aa.building_id.iloc[0], condition=con, origin=origin, metric=metric, layer=layer, scope_comparable=r['scope_comparable'], substantive_conflict=r['substantive_conflict'], oos_pending=r['oos_pending'], user_group_ids='|'.join(r['user_group_ids']), difficulty_relation='|'.join(sorted({str(e.get('difficulty_similarity')) for e in r['evidence'] if e.get('difficulty_similarity')})), class_a=aa.current_class.iloc[0], class_b=bb.current_class.iloc[0], N_turn_a=aa.N_turn.iloc[0], N_turn_b=bb.N_turn.iloc[0], H_a=aa.H.iloc[0], H_b=bb.H.iloc[0], reference_id_a=aa.reference_id.iloc[0], reference_id_b=bb.reference_id.iloc[0], reference_version_a=aa.reference_version.iloc[0], reference_version_b=bb.reference_version.iloc[0], n_a=len(va), n_b=len(vb), n_common=len(w), common_workers='|'.join(sorted(w)), common_object_ids_a='|'.join(aa.loc[sorted(w)].object_id), common_object_ids_b='|'.join(bb.loc[sorted(w)].object_id), actual_mean_a=va.mean(), actual_mean_b=vb.mean(), actual_signed_gap=all_delta, actual_abs_gap=abs(all_delta), common_mean_a=ca.mean(), common_mean_b=cb.mean(), common_signed_gap=common_delta, common_abs_gap=abs(common_delta), composition_signed_shift=all_delta - common_delta, composition_abs_shift=abs(all_delta - common_delta), actual_minus_common_abs_gap=abs(all_delta) - abs(common_delta), actual_wasserstein=wasserstein_distance(va, vb) if len(va) and len(vb) else np.nan, common_wasserstein=wasserstein_distance(ca, cb) if len(w) else np.nan, common_person_abs_gap=delta.abs().mean(), worker_spearman=spearmanr(ca, cb).statistic if valid_rank else np.nan, positive_movers=int(delta.gt(5).sum()), negative_movers=int(delta.lt(-5).sum()), common_sd_a=ca.std(), common_sd_b=cb.std(), common_q10_a=ca.quantile(0.1), common_q10_b=cb.quantile(0.1), actual_low50_a=va.lt(50).mean(), actual_low50_b=vb.lt(50).mean(), common_low50_a=ca.lt(50).mean(), common_low50_b=cb.lt(50).mean(), common_q10_abs_gap=abs(cb.quantile(0.1) - ca.quantile(0.1)), common_low50_abs_gap=abs(cb.lt(50).mean() - ca.lt(50).mean()))
                    rows.append(row)
    return (pd.DataFrame(rows), pd.DataFrame(coverage))

def group_tables(q, rel, groups, candidates, pairs):
    declared = [dict(declaration_id=g['review_code'], source='original', images=g['image_ids'], building_id=g['building']) for g in groups]
    seen = {(g['declaration_id'], tuple(sorted(g['images']))) for g in declared}
    for g in candidates:
        k = (g['candidate_id'], tuple(sorted(g['image_ids'])))
        if k not in seen and g['physical_supported']:
            declared.append(dict(declaration_id=g['candidate_id'], source='candidate_subset', images=g['image_ids'], building_id=g['image_ids'][0].split('_')[0]))
            seen.add(k)
    direct = {tuple(sorted([r['image_a'], r['image_b']])): r for r in rel if r['physical_adopted']}
    rows = []
    views = []
    for dec in declared:
        for condition in ['manual', 'semi']:
            z = q[q.image_id.isin(dec['images']) & q.condition.eq(condition)]
            if z.image_id.nunique() < 2:
                continue
            ims = sorted(z.image_id.unique())
            links = [p for p in itertools.combinations(ims, 2) if p in direct]
            if not links:
                continue
            used = set(sum([list(p) for p in links], []))
            z = z[z.image_id.isin(used)]
            ims = sorted(used)
            pivot = z.pivot(index='image_id', columns='worker_id', values='B8L2').reindex(ims)
            common = pivot.columns[pivot.notna().all()]
            means = pivot.mean(axis=1)
            cmeans = pivot[common].mean(axis=1)
            eligible = [p for p in links if direct[p]['scope_comparable'] and (not direct[p]['substantive_conflict'])]
            gm = means.mean()
            for im in ims:
                a = z[z.image_id.eq(im)]
                v = a.B8L2
                co = a[a.worker_id.isin(common)].B8L2
                views.append(dict(declaration_id=dec['declaration_id'], declaration_source=dec['source'], condition=condition, building_id=dec['building_id'], image_id=im, image_code=a.image_code.iloc[0], layer=a.layer.iloc[0], current_class=a.current_class.iloc[0], N_turn=a.N_turn.iloc[0], H=a.H.iloc[0], reference_id=a.reference_id.iloc[0], reference_version=a.reference_version.iloc[0], n=len(v), mean=v.mean(), median=v.median(), sd=v.std(), q10=v.quantile(0.1), q25=v.quantile(0.25), q75=v.quantile(0.75), low50=v.lt(50).mean(), whole_group_common_n=len(common), whole_group_common_mean=co.mean(), whole_group_common_workers='|'.join(common), delta_vs_other_views=means.loc[im] - means.drop(im).mean(), main_visual_space=a.main_visual_space.iloc[0], expected_annotation_extent=a.expected_annotation_extent.iloc[0]))
            pp = pairs[pairs.image_a.isin(ims) & pairs.image_b.isin(ims) & pairs.condition.eq(condition) & pairs.origin.eq('all') & pairs.metric.eq('B8L2')]
            rows.append(dict(declaration_id=dec['declaration_id'], declaration_source=dec['source'], condition=condition, building_id=dec['building_id'], n_declared_images=len(dec['images']), n_quality_images=len(ims), n_adopted_pairs=len(links), n_scope_comparable_pairs=len(eligible), layer='doorway' if z.is_doorway.any() else 'ordinary', all_pair_scope_comparable=len(eligible) == len(links), actual_grand_mean=gm, actual_mean_sd=means.std(), actual_mean_range=means.max() - means.min(), pair_actual_abs_gap=pp.actual_abs_gap.mean(), pair_common_abs_gap=pp.common_abs_gap.mean(), whole_group_common_n=len(common), whole_group_common_range=cmeans.max() - cmeans.min(), max_image=z.set_index('image_id').loc[means.idxmax()].image_code.iloc[0], min_image=z.set_index('image_id').loc[means.idxmin()].image_code.iloc[0], image_ids='|'.join(ims), image_codes='|'.join(z.drop_duplicates('image_id').sort_values('image_id').image_code), current_classes='|'.join(sorted(z.current_class.unique()))))
    return (pd.DataFrame(rows), pd.DataFrame(views))

def matched_unknown(q, rel, pairs, images):
    """Anchor A fixed; B same room vs X relation-unknown, no outcome matching.

    All relation-registry pairs (including nonadopted conflicts) are excluded
    from unknown controls. Strict controls match B's class and reference turns
    and hidden-turn count exactly. Triple-common roster is fixed for A/B/X.
    """
    known = {tuple(sorted([r['image_a'], r['image_b']])) for r in rel}
    d = q[q.condition.eq('manual') & q.layer.eq('ordinary')]
    im = images[images.condition.eq('manual') & images.layer.eq('ordinary') & images.origin.eq('all')].set_index('image_id')
    cells = {i: a.set_index('worker_id') for i, a in d.groupby('image_id')}
    prim = pairs[pairs.condition.eq('manual') & pairs.origin.eq('all') & pairs.metric.eq('B8L2') & pairs.layer.eq('ordinary') & pairs.scope_comparable & ~pairs.substantive_conflict & pairs.n_common.ge(4)]
    rows = []
    for p in prim.itertuples():
        for a, b in [(p.image_a, p.image_b), (p.image_b, p.image_a)]:
            ia = im.loc[a]
            ib = im.loc[b]
            for x, ix in im[im.building_id.eq(p.building_id) & im.n.ge(3)].iterrows():
                if x in [a, b] or tuple(sorted([a, x])) in known:
                    continue
                same_class = ib.current_class == ix.current_class
                same_turns = ib.N_turn == ix.N_turn
                same_hidden = ib.H == ix.H
                w = cells[a].index.intersection(cells[b].index).intersection(cells[x].index)
                row = dict(pair_id=p.pair_id, building_id=p.building_id, anchor=a, same_room=b, unknown_target=x, code_a=ia.image_code, code_b=ib.image_code, code_x=ix.image_code, class_match=same_class, turns_match=same_turns, hidden_match=same_hidden, strict_match=same_class and same_turns and same_hidden, n_triple_common=len(w), triple_workers='|'.join(sorted(w)), class_b=ib.current_class, class_x=ix.current_class, N_turn_b=ib.N_turn, N_turn_x=ix.N_turn, H_b=ib.H, H_x=ix.H)
                for metric in METRICS:
                    va = cells[a][metric]
                    vb = cells[b][metric]
                    vx = cells[x][metric]
                    row.update({metric + '_same_actual_gap': abs(va.mean() - vb.mean()), metric + '_unknown_actual_gap': abs(va.mean() - vx.mean()), metric + '_same_triple_gap': abs(va.loc[w].mean() - vb.loc[w].mean()), metric + '_unknown_triple_gap': abs(va.loc[w].mean() - vx.loc[w].mean())})
                rows.append(row)
    return pd.DataFrame(rows)

def summaries(p, matched):
    rows = []
    for origin in ['all', 'v1', 'new']:
        for con in ['manual', 'semi']:
            for layer in ['ordinary', 'doorway']:
                for scope in [True, False]:
                    for threshold in [1, 4]:
                        x = p[p.origin.eq(origin) & p.condition.eq(con) & p.layer.eq(layer) & p.scope_comparable.eq(scope) & ~p.substantive_conflict & p.n_common.ge(threshold)]
                        for metric, z in x.groupby('metric'):
                            vals = ['actual_abs_gap', 'common_abs_gap', 'composition_abs_shift', 'actual_minus_common_abs_gap', 'common_person_abs_gap', 'common_wasserstein', 'common_low50_abs_gap', 'common_q10_abs_gap']
                            base = dict(origin=origin, condition=con, layer=layer, scope_comparable=scope, min_common=threshold, metric=metric, pairs=len(z), images=len(set(z.image_a) | set(z.image_b)), buildings=z.building_id.nunique(), median_common=z.n_common.median(), median_spearman=z.worker_spearman.median())
                            for weighting in ['pair_equal', 'building_equal']:
                                a = z[vals].mean() if weighting == 'pair_equal' else z.groupby('building_id')[vals].mean().mean()
                                rows.append(dict(**base, weighting=weighting, **a.to_dict()))
    ms = []
    direction = []
    for subset in ['all_unknown', 'same_class', 'strict_class_turns_hidden']:
        z = matched if subset == 'all_unknown' else matched[matched.class_match] if subset == 'same_class' else matched[matched.strict_match]
        for panel in ['actual', 'triple']:
            a = z if panel == 'actual' else z[z.n_triple_common.ge(4)]
            for metric in METRICS:
                sc = metric + '_same_' + panel + '_gap'
                uc = metric + '_unknown_' + panel + '_gap'
                v = a.groupby(['building_id', 'pair_id', 'anchor', 'same_room'], as_index=False).agg(same_gap=(sc, 'mean'), unknown_gap=(uc, 'mean'), candidates=('unknown_target', 'nunique'), triple_common=('n_triple_common', 'mean'))
                if v.empty:
                    continue
                v['gain'] = v.unknown_gap - v.same_gap
                v['subset'] = subset
                v['panel'] = panel
                v['metric'] = metric
                direction.append(v)
                b = v.groupby('building_id')[['same_gap', 'unknown_gap', 'gain']].mean()
                lo, hi = cluster_interval(b.gain)
                ms.append(dict(subset=subset, panel=panel, metric=metric, directions=len(v), pairs=v.pair_id.nunique(), buildings=len(b), anchors=v.anchor.nunique(), same_images=v.same_room.nunique(), candidate_rows=len(a), mean_candidates=v.candidates.mean(), same_gap=b.same_gap.mean(), unknown_gap=b.unknown_gap.mean(), gain=b.gain.mean(), gain_building_bootstrap_lo=lo, gain_building_bootstrap_hi=hi, buildings_gain_positive=b.gain.gt(0).sum()))
    return (pd.DataFrame(rows), pd.DataFrame(ms), pd.concat(direction, ignore_index=True) if direction else pd.DataFrame())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    raw, q, rel, groups, candidates = load(args.repo)
    images = image_table(q)
    p, cov = pairs(q, rel, images)
    g, v = group_tables(q, rel, groups, candidates, p)
    matched = matched_unknown(q, rel, p, images)
    s, ms, dirs = summaries(p, matched)
    for n, x in [('formal_record_index', q), ('image_quality', images), ('direct_pair_similarity', p), ('relation_coverage', cov), ('declared_group_similarity', g), ('declared_group_views', v), ('matched_unknown_candidates', matched), ('matched_unknown_directions', dirs), ('pair_summary', s), ('matched_unknown_summary', ms)]:
        save_csv(x, out / 'tables' / (n + ('.csv.gz' if n in ['formal_record_index', 'matched_unknown_candidates'] else '.csv')))
    b = dirs.groupby(['subset', 'panel', 'metric', 'building_id'], as_index=False).agg(same_gap=('same_gap', 'mean'), unknown_gap=('unknown_gap', 'mean'), gain=('gain', 'mean'), directions=('anchor', 'size'), pairs=('pair_id', 'nunique'), anchors=('anchor', 'nunique'), mean_candidates=('candidates', 'mean'))
    save_csv(b, out / 'tables/matched_unknown_buildings.csv')
    bridge = []
    for panel in ['actual', 'triple']:
        available = matched if panel == 'actual' else matched[matched.n_triple_common.ge(4)]
        strict = available[available.strict_match]
        keys = ['building_id', 'pair_id', 'anchor', 'same_room']
        fixed = available.merge(strict[keys].drop_duplicates(), on=keys)
        for label, c in [('same_support_unmatched', fixed), ('same_support_class', fixed[fixed.class_match]), ('same_support_strict', strict)]:
            for metric in METRICS:
                x = c.groupby(keys, as_index=False).agg(same=(metric + '_same_' + panel + '_gap', 'mean'), unknown=(metric + '_unknown_' + panel + '_gap', 'mean'))
                bb = x.groupby('building_id')[['same', 'unknown']].mean()
                bridge.append(dict(panel=panel, metric=metric, control=label, directions=len(x), buildings=len(bb), same_gap=bb.same.mean(), unknown_gap=bb.unknown.mean(), gain=(bb.unknown - bb.same).mean(), candidate_rows=len(c)))
    save_csv(pd.DataFrame(bridge), out / 'tables/matched_control_support_bridge.csv')
    cases = q[q.image_code.isin(['pa4otMbVnkk-42', 'pa4otMbVnkk-44', 'wc2JMjhGNzB-26', 'wc2JMjhGNzB-53']) & q.condition.eq('manual')].copy()
    cases['group_id'] = cases.image_code.map(lambda x: 'G130' if x.startswith('pa4') else 'G202')
    cases['common_both_views'] = cases.groupby(['group_id', 'worker_id']).image_id.transform('nunique').eq(2)
    cases['image_mean'] = cases.groupby('image_id').B8L2.transform('mean')
    cases['peer_residual'] = cases.B8L2 - (cases.groupby('image_id').B8L2.transform('sum') - cases.B8L2) / (cases.groupby('image_id').B8L2.transform('size') - 1)
    save_csv(cases.sort_values(['group_id', 'worker_id', 'image_code']), out / 'tables/G130_G202_record_cases.csv')
    old = _read_csv(args.repo / 'research/same_room/same_room_v2_prediction_20261019/pair_descriptive.csv')
    old = old[old.metric.eq('B8L2') & old.origin.eq('all') & old.layer.eq('ordinary') & old.relation_eligible & old.n_paired.ge(4)]
    new = p[p.metric.eq('B8L2') & p.origin.eq('all') & p.condition.eq('manual') & p.layer.eq('ordinary') & p.scope_comparable & ~p.substantive_conflict & p.n_common.ge(4)]
    chk = old.merge(new, on=['image_a', 'image_b'], suffixes=('_old', '_new'))
    receipt = dict(commit=COMMIT, relation_version=RELATION_VERSION, status='本轮新增；固定口径旧值复算', formal_records=len(q), same_support_pairs=len(chk), old_common_mean_gap=old.absolute_mean_gap.mean(), old_person_abs_gap=old.mean_absolute_person_delta.mean(), old_rank_median=old.worker_spearman.median(), max_old_new_common_gap_difference=float((chk.absolute_mean_gap - chk.common_abs_gap).abs().max()), old_7p24_weighting='123无向图对等权，双方固定共同人员；不是实际池均值差或房间等权', new_pair_equal_actual_gap=new.actual_abs_gap.mean(), new_pair_equal_common_gap=new.common_abs_gap.mean(), new_building_equal_actual_gap=new.groupby('building_id').actual_abs_gap.mean().mean(), new_building_equal_common_gap=new.groupby('building_id').common_abs_gap.mean().mean(), no_transitive_relations_added=True, unknown_controls='exclude every pair listed in frozen relation registry; unknown is not different-room')
    (out / 'INPUTS_AND_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(ms.to_string(index=False))
    print(g[g.condition.eq('manual')].sort_values('pair_common_abs_gap', ascending=False).head(15).to_string(index=False))
if __name__ == '__main__':
    main()
