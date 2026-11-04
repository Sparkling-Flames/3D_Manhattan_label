"""Independent acceptance of the *entire frozen* 208-event Q-only design.

No fusion, team selection, ordering, or model fitting is performed.  Recompute
all policy comparisons from the 670 frozen original endpoints and the already
accepted exact-team manual-order endpoints, then audit opportunity coverage.
This script deliberately does not import the previous propagation producer.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/manual_order_acceptance_20261104'
SRC = BASE / 'inputs/q_only'
OUT = BASE / 'q_only'
PREVIOUS = ROOT / 'research/fusion/manual_order_impact_20261104'
ORDERS = ROOT / 'research/fusion/missing_ring_review_20261104/user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz'
POLICIES = ['A', 'B', 'STRUCTURE', 'Q_RAW', 'Q_PEER']
METRICS = ['B8L2', 'D10', 'IoU3D100', 'fusion_turn_n', 'fusion_short_turn_edges',
           'boundary_loss', 'direction_loss', 'height_loss', 'omission', 'extension',
           'ref_node_recall_5']
HIERARCHY = ['n', 'building', 'image', 'pool_id', 'block_id', 'background_id']
CHECKS = []
INPUTS = set()


def frame(path):
    INPUTS.add(Path(path))
    return pd.read_csv(path, low_memory=False)


def records(path):
    INPUTS.add(Path(path))
    with gzip.open(path, 'rt', encoding='utf-8-sig') as handle:
        result = [json.loads(line) for line in handle if line.strip()]
    assert len({r['team_key'] for r in result}) == len(result)
    return {r['team_key']: r for r in result}


def write_csv(data, name):
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def check(name, passed, **detail):
    row = dict(check=name, passed=bool(passed), **detail)
    CHECKS.append(row)
    if not passed:
        raise AssertionError(row)


def value(x):
    return float(x) if isinstance(x, (float, int, np.number)) and np.isfinite(x) else np.nan


def members(x):
    return set(x) if isinstance(x, list) else set(x.split('|')) if isinstance(x, str) and x else set()


def numeric_parity(name, left, right, keys, cols, tolerance=1e-8):
    a, b = left.set_index(keys).sort_index(), right.set_index(keys).sort_index()
    check(name + '/keys', a.index.equals(b.index) and a.index.is_unique, rows=len(a))
    x, y = a[cols].to_numpy(float), b[cols].to_numpy(float)
    missing = int(np.sum(np.isnan(x) != np.isnan(y)))
    finite = np.isfinite(x) & np.isfinite(y)
    maximum = float(np.max(np.abs(x[finite] - y[finite]))) if finite.any() else 0.0
    check(name, missing == 0 and maximum <= tolerance,
          numeric_cells=int(finite.sum()), missing_mismatches=missing, max_abs_difference=maximum)


def image_values(data, columns):
    """Average equally at each registered layer, never across raw team links."""
    result = data.groupby(HIERARCHY, dropna=False)[columns].mean().reset_index()
    for keys in [HIERARCHY[:-1], HIERARCHY[:-2], HIERARCHY[:3]]:
        result = result.groupby(keys, dropna=False)[columns].mean().reset_index()
    return result


def weights(data):
    """Independent flat weights equivalent to replicate→background→block→pool→image."""
    result = pd.Series(1.0, index=data.index)
    result /= data.groupby(HIERARCHY, dropna=False)['event_id'].transform('size')
    for parent, child in [(HIERARCHY[:-1], 'background_id'),
                          (HIERARCHY[:-2], 'block_id'), (HIERARCHY[:3], 'pool_id')]:
        result /= data.groupby(parent, dropna=False)[child].transform('nunique')
    result /= len(data[HIERARCHY[:3]].drop_duplicates())
    return result


def interval(images, field):
    groups = images.groupby('building')[field].agg(['sum', 'count'])
    rng = np.random.default_rng(20261031)
    ix = rng.integers(0, len(groups), size=(2000, len(groups)))
    samples = groups['sum'].to_numpy()[ix].sum(1) / groups['count'].to_numpy()[ix].sum(1)
    return np.quantile(samples, [.025, .975]).tolist()


def labor(endpoint):
    raw = endpoint.get('record_time_by_kind_json')
    if not isinstance(raw, str):
        return None, None
    kinds = json.loads(raw)
    signature = tuple(sorted((k, v['n']) for k, v in kinds.items()))
    if not kinds or any(v['known_n'] != v['n'] or v['total_seconds'] is None for v in kinds.values()):
        return signature, None
    return signature, sum(v['total_seconds'] for v in kinds.values())


def policy_pairs(links, endpoints):
    rows = []
    for eid, group in links.groupby('event_id', sort=False):
        policies = group.set_index('policy')
        base = policies.loc['STRUCTURE']
        a = endpoints[base.team_key]
        for policy in ['Q_RAW', 'Q_PEER', 'A', 'B']:
            b = endpoints[policies.loc[policy, 'team_key']]
            row = dict(event_id=eid, comparator=policy, **{k: base[k] for k in HIERARCHY})
            for metric in METRICS:
                x, y = value(a.get(metric)), value(b.get(metric))
                ok = np.isfinite([x, y]).all()
                row.update({metric + '_structure': x if ok else np.nan,
                            metric + '_comparator': y if ok else np.nan,
                            metric + '_delta': x - y if ok else np.nan})
            ls, ts = labor(a)
            lc, tc = labor(b)
            ok = ls == lc and ts is not None and tc is not None and tc > 0
            row.update(labor_structure_seconds=ts if ok else np.nan,
                       labor_comparator_seconds=tc if ok else np.nan,
                       labor_ratio=ts / tc if ok else np.nan)
            rows.append(row)
    return pd.DataFrame(rows)


def summarize(pairs, version, subset):
    rows, image_rows = [], []
    for (n, comparator), group in pairs.groupby(['n', 'comparator']):
        for metric in METRICS + ['labor']:
            cols = ([metric + '_structure', metric + '_comparator', metric + '_delta']
                    if metric != 'labor' else ['labor_structure_seconds', 'labor_comparator_seconds', 'labor_ratio'])
            valid = group.dropna(subset=cols)
            if valid.empty:
                continue
            images = image_values(valid, cols)
            low, high = interval(images, cols[2])
            rows.append(dict(version=version, subset=subset, n=n, m=7, comparator=comparator,
                             metric=metric, events=len(valid), images=len(images), buildings=images.building.nunique(),
                             structure_mean=images[cols[0]].mean(), comparator_mean=images[cols[1]].mean(),
                             effect=images[cols[2]].mean(), ci_low=low, ci_high=high,
                             positive_images=int((images[cols[2]] > (1 if metric == 'labor' else 1e-9)).sum()),
                             negative_images=int((images[cols[2]] < (1 if metric == 'labor' else -1e-9)).sum()),
                             structure_p10=images[cols[0]].quantile(.1), comparator_p10=images[cols[1]].quantile(.1)))
            image_rows.append(images.rename(columns={cols[0]: 'structure', cols[1]: 'comparator_value', cols[2]: 'effect'})
                              .assign(version=version, subset=subset, comparator=comparator, metric=metric))
    return pd.DataFrame(rows), pd.concat(image_rows, ignore_index=True)


def decompose(old_pairs, new_pairs, subset, links, new_endpoints, original_endpoints):
    rows, contributions, additions = [], [], []
    for (n, policy), a in old_pairs.groupby(['n', 'comparator']):
        if policy not in ['Q_RAW', 'Q_PEER']:
            continue
        b = new_pairs[new_pairs.n.eq(n) & new_pairs.comparator.eq(policy)]
        for metric in METRICS:
            effect = metric + '_delta'
            old = a[a[effect].notna()].copy()
            new = b[b[effect].notna()].copy()
            old_ids = set(old.event_id)
            old_ims = set(old.image)
            new_only = new[~new.event_id.isin(old_ids)]
            im_old = image_values(old, [effect])
            im_new = image_values(new, [effect])
            common = new[new.event_id.isin(old_ids)].copy()
            im_common = image_values(common, [effect])
            original_image_expanded = im_new[im_new.image.isin(old_ims)]
            original_mean, new_mean = im_old[effect].mean(), im_new[effect].mean()
            old_weights = pd.Series(weights(old).to_numpy(), index=old.event_id)
            new_weights = weights(new)
            c = new[['event_id', 'image', 'building', 'pool_id', 'block_id', 'background_id', effect]].copy()
            c['old_weight'] = c.event_id.map(old_weights).fillna(0)
            c['new_weight'] = new_weights
            c['old_value'] = c.event_id.map(old.set_index('event_id')[effect])
            c['new_value'] = c[effect]
            c['newly_evaluable'] = ~c.event_id.isin(old_ids)
            c['new_image'] = ~c.image.isin(old_ims)
            # An absent old Q is retained as missing.  Zero below denotes only a
            # non-participating weight, never a fabricated old endpoint score.
            c['new_event_contribution'] = np.where(c.newly_evaluable, c.new_weight * c.new_value, 0.0)
            c['old_event_reweight_contribution'] = np.where(c.newly_evaluable, 0.0,
                                                          (c.new_weight - c.old_weight) * c.old_value)
            old_mass = np.sum(old_weights.to_numpy() * old.set_index('event_id').loc[old_weights.index, effect].to_numpy())
            new_mass = np.sum(c.new_weight * c.new_value)
            total = c.new_event_contribution.sum() + c.old_event_reweight_contribution.sum()
            errors = [abs(old_mass - original_mean), abs(new_mass - new_mean),
                      abs(total - (new_mean - original_mean)), abs(c.new_weight.sum() - 1)]
            check(f'weighted_decomposition/{subset}/{n}/{policy}/{metric}', max(errors) < 1e-9,
                  max_identity_error=float(max(errors)))
            rows.append(dict(subset=subset, n=n, comparator=policy, metric=metric,
                             old_events=len(old), added_events=len(new_only), expanded_events=len(new),
                             old_images=len(im_old), added_images=len(im_new)-len(im_old), expanded_images=len(im_new),
                             old_effect=original_mean, assisted_on_original_events=im_common[effect].mean(),
                             newly_evaluable_only_effect=(image_values(new_only, [effect])[effect].mean() if len(new_only) else np.nan),
                             expanded_effect=new_mean, old_images_expanded_effect=original_image_expanded[effect].mean(),
                             within_original_images_shift=original_image_expanded[effect].mean()-original_mean,
                             adding_new_images_shift=new_mean-original_image_expanded[effect].mean(),
                             new_event_weighted_contribution=c.new_event_contribution.sum(),
                             old_event_reweight_contribution=c.old_event_reweight_contribution.sum(),
                             sign_flip=original_mean * new_mean < -1e-12))
            changed = c[c.newly_evaluable | ((c.new_weight-c.old_weight).abs() > 1e-14)].copy()
            changed['subset'], changed['n'], changed['comparator'], changed['metric'] = subset, n, policy, metric
            contributions.append(changed.drop(columns=effect))
            if metric == 'B8L2':
                for r in new_only.to_dict('records'):
                    selection = links[links.event_id.eq(r['event_id'])].set_index('policy')
                    ak, bk = selection.loc['STRUCTURE', 'team_key'], selection.loc[policy, 'team_key']
                    sa, sb = new_endpoints[ak], new_endpoints[bk]
                    ca = c[c.event_id.eq(r['event_id'])].iloc[0]
                    additions.append(dict(subset=subset, n=n, comparator=policy, event_id=r['event_id'],
                                          image=r['image'], building=r['building'],
                                          structure_team=ak, comparator_team=bk,
                                          structure_members='|'.join(sorted(members(sa.get('member_workers')))),
                                          comparator_members='|'.join(sorted(members(sb.get('member_workers')))),
                                          original_structure_status=original_endpoints[ak].get('score_status'),
                                          original_comparator_status=original_endpoints[bk].get('score_status'),
                                          structure_manual=ak in MANUAL, comparator_manual=bk in MANUAL,
                                          structure_Q=sa['B8L2'], comparator_Q=sb['B8L2'], delta_Q=r[effect],
                                          same_selected_team=ak==bk, new_image=bool(ca.new_image),
                                          global_weight=ca.new_weight, contribution=ca.new_event_contribution,
                                          boundary_loss_delta=r['boundary_loss_delta'],
                                          direction_loss_delta=r['direction_loss_delta'], height_loss_delta=r['height_loss_delta']))
    return rows, contributions, additions


def main():
    global MANUAL
    links, requests = frame(SRC / 'DESIGN_LINKS.csv'), frame(SRC / 'TEAM_REQUESTS.csv')
    original = records(SRC / 'ENDPOINTS.jsonl.gz')
    MANUAL = records(PREVIOUS / 'endpoints/ENDPOINTS.jsonl.gz')
    returned = frame(ORDERS)
    check('frozen_design', len(links)==1040 and links.event_id.nunique()==208 and len(original)==670,
          policy_links=len(links), events=links.event_id.nunique(), unique_teams=len(original))
    check('five_arms_every_event', links.groupby('event_id').policy.apply(lambda x: set(x)==set(POLICIES) and len(x)==5).all())
    check('registered_conditions', links.drop_duplicates('event_id').groupby('n').size().to_dict()=={14:147,20:61})
    check('request_and_endpoint_identity', set(links.team_key)==set(requests.team_key)==set(original))
    check('returned_orders_57', len(returned)==57 and set(returned.team_key)==set(MANUAL))
    request_by = requests.set_index('team_key')
    identity_mismatches = []
    for key, r in original.items():
        req = request_by.loc[key]
        if members(req.members) != members(r.get('member_workers')):
            identity_mismatches.append((key, 'members'))
        for field in ['pool_id', 'reference_id', 'reference_version']:
            if req[field] != r[field]:
                identity_mismatches.append((key, field))
    check('original_requests_members_and_reference', not identity_mismatches, mismatches=identity_mismatches)

    revised = copy.deepcopy(original)
    for key in set(original) & set(MANUAL):
        old, new = original[key], MANUAL[key]
        for field in ['pool_id', 'reference_id', 'reference_version', 'nodes']:
            check(f'exact_manual_identity/{key}/{field}', old[field]==new[field])
        check(f'exact_manual_members/{key}', members(old['member_workers'])==members(new['member_workers']))
        revised[key].update({k: v for k, v in new.items()
                             if k in METRICS or k in ['score_status','complete_evaluable','connection_available','below_four']})

    coverage = []
    for r in links.to_dict('records'):
        old, new = original[r['team_key']], revised[r['team_key']]
        needs = old.get('score_status') == 'no_connection' and old.get('nodes', 0) >= 4
        coverage.append({**{k:r[k] for k in ['event_id','n','m','image','building','pool_id','block_id','background_id','policy','team_key']},
                         'nodes':old['nodes'],'automatic_status':old['score_status'],
                         'automatic_Q':value(old.get('B8L2')),'needs_human_order':needs,
                         'confirmed_order_available':r['team_key'] in MANUAL,
                         'manual_order_applied':needs and r['team_key'] in MANUAL,
                         'review_id':MANUAL.get(r['team_key'],{}).get('review_id'),
                         'assisted_status':new['score_status'],'assisted_Q':value(new.get('B8L2')),
                         'original_below_four':bool(old.get('below_four')),
                         'remaining_failure':not np.isfinite(value(new.get('B8L2'))),
                         'kernel_if_manual':MANUAL.get(r['team_key'],{}).get('geometry_check',{}).get('camera_in_visible_kernel'),
                         'treatment_decision':'manual_order' if needs else 'node_count_failure' if old.get('below_four') else 'original_scored_untouched'})
    coverage = pd.DataFrame(coverage)
    needy = coverage[coverage.needs_human_order]
    check('all_no_connection_opportunities_covered', needy.confirmed_order_available.all() and needy.assisted_Q.notna().all(),
          arm_event_links=len(needy), unique_teams=needy.team_key.nunique(), events=needy.event_id.nunique(), images=needy.image.nunique())
    check('no_unnecessary_treatment', (coverage.confirmed_order_available == coverage.needs_human_order).all())
    check('remaining_failures_are_below_four', coverage[coverage.remaining_failure].original_below_four.all(),
          remaining_links=int(coverage.remaining_failure.sum()))
    check('policy_comparison_complete', not coverage[coverage.policy.isin(['STRUCTURE','Q_RAW','Q_PEER'])].remaining_failure.any())
    write_csv(coverage, 'ALL_1040_POLICY_OPPORTUNITIES.csv.gz')
    write_csv(needy, 'ALL_NO_CONNECTION_OPPORTUNITIES.csv')
    write_csv(coverage[coverage.remaining_failure], 'REMAINING_NON_ORDER_FAILURES.csv')
    policy_summary = []
    for (n, p), g in coverage.groupby(['n', 'policy']):
        need = g[g.needs_human_order]
        policy_summary.append(dict(n=n, m=7, policy=p, registered_events=len(g), original_scored=int(g.automatic_Q.notna().sum()),
                                   order_needed_links=len(need), order_needed_unique_teams=need.team_key.nunique(),
                                   covered_links=int(need.confirmed_order_available.sum()), successful_links=int(need.assisted_Q.notna().sum()),
                                   uncovered_eligible_links=int((~need.confirmed_order_available).sum()),
                                   expanded_scored=int(g.assisted_Q.notna().sum()), node_count_failure_links=int(g.original_below_four.sum())))
    write_csv(policy_summary, 'OPPORTUNITY_COVERAGE_BY_ARM.csv')
    # Verify status from raw endpoints against the original publication AND
    # the previous assisted deliverable, independently of their check receipts.
    previous_status = frame(PREVIOUS / 'half_qonly/QONLY_OUTPUT_STATUS.csv')
    original_status = frame(SRC / 'OUTPUT_STATUS.csv')
    keycols = ['event_id', 'policy']
    for variant, status in [('automatic',original_status),('automatic',previous_status[previous_status.version.eq('automatic')]),
                            ('assisted_expanded',previous_status[previous_status.version.eq('assisted_expanded')])]:
        target = coverage.set_index(keycols).sort_index()
        status = status.set_index(keycols).sort_index()
        check('status_identity/'+variant+'/'+str(len(CHECKS)), target.index.equals(status.index))
        field = 'automatic' if variant=='automatic' else 'assisted'
        check('status_values/'+variant+'/'+str(len(CHECKS)),
              (target[field+'_status']==status.score_status).all() and (target[field+'_Q'].notna()==status.scored).all())

    old_pairs, new_pairs = policy_pairs(links, original), policy_pairs(links, revised)
    numcols = [c for c in old_pairs if c.endswith(('_structure','_comparator','_delta','_seconds','_ratio'))]
    numeric_parity('raw_original_pairs',frame(SRC/'PAIRED_EVENTS.csv'),old_pairs,keycols[:1]+['comparator'],numcols)
    numeric_parity('previous_automatic_pairs',frame(PREVIOUS/'half_qonly/QONLY_AUTOMATIC_PAIRED_EVENTS.csv.gz'),old_pairs,['event_id','comparator'],numcols)
    numeric_parity('previous_assisted_pairs',frame(PREVIOUS/'half_qonly/QONLY_ASSISTED_EXPANDED_PAIRED_EVENTS.csv.gz'),new_pairs,['event_id','comparator'],numcols)
    masked = new_pairs.copy()
    for metric in METRICS:
        cols = [metric+'_structure',metric+'_comparator',metric+'_delta']
        masked.loc[old_pairs[metric+'_delta'].isna(),cols] = np.nan
    numeric_parity('all_original_support_unchanged',old_pairs,masked,['event_id','comparator'],numcols)
    numeric_parity('labor_unchanged',old_pairs,new_pairs,['event_id','comparator'],[c for c in numcols if c.startswith('labor')])

    overlap = []
    for eid, group in links.groupby('event_id', sort=False):
        p = group.set_index('policy')
        a = members(p.loc['STRUCTURE','incoming_members'])
        for q in ['Q_RAW','Q_PEER']:
            b = members(p.loc[q,'incoming_members'])
            overlap.append(dict(event_id=eid,n=int(p.loc[q,'n']),comparator=q,image=p.loc[q,'image'],
                                building=p.loc[q,'building'],same_block=a==b,
                                shared_incoming=len(a&b),removed='|'.join(sorted(a-b)),added='|'.join(sorted(b-a)),
                                structure_team=p.loc['STRUCTURE','team_key'],comparator_team=p.loc[q,'team_key']))
    overlap = pd.DataFrame(overlap)
    saved_overlap=frame(SRC/'SELECTION_OVERLAP.csv').rename(columns={'policy':'comparator'})
    numeric_parity('selection_frozen',saved_overlap,overlap,['event_id','comparator'],['n','shared_incoming','same_block'])
    different = overlap[~overlap.same_block]
    check('20_7_different_selection_complete',different[different.n.eq(20)].groupby('comparator').event_id.nunique().to_dict()=={'Q_PEER':7,'Q_RAW':7})
    check('20_7_Q_RAW_Q_PEER_same_teams',
          links[links.n.eq(20)&links.policy.eq('Q_RAW')].set_index('event_id').team_key.equals(
          links[links.n.eq(20)&links.policy.eq('Q_PEER')].set_index('event_id').team_key))
    d_old=old_pairs.merge(different[['event_id','comparator']],on=['event_id','comparator'],validate='one_to_one')
    d_new=new_pairs.merge(different[['event_id','comparator']],on=['event_id','comparator'],validate='one_to_one')
    summaries, images = [], []
    for version,pair,subset in [('automatic',old_pairs,'all_registered'),('assisted_original_support',masked,'all_registered'),
                                 ('assisted_expanded',new_pairs,'all_registered'),('automatic',d_old,'different_selection'),
                                 ('assisted_expanded',d_new,'different_selection')]:
        summary,im=summarize(pair,version,subset)
        summaries.append(summary);images.append(im)
    summary=pd.concat(summaries,ignore_index=True)
    scols=[c for c in summary.select_dtypes(include='number') if c not in ['n','m']]
    numeric_parity('all_summary_and_cluster_intervals',frame(PREVIOUS/'half_qonly/QONLY_SUMMARY.csv'),summary,
                   ['version','subset','n','comparator','metric'],scols)
    numeric_parity('original_published_summary',frame(SRC/'SUMMARY.csv'),summary[summary.version.eq('automatic')&summary.subset.eq('all_registered')],
                   ['n','comparator','metric'],scols)
    write_csv(summary, 'INDEPENDENT_SUMMARY.csv')
    write_csv(pd.concat(images,ignore_index=True),'INDEPENDENT_IMAGE_EFFECTS.csv.gz')

    decomposition,contributions,additions=[],[],[]
    for a,b,label in [(old_pairs,new_pairs,'all_registered'),(d_old,d_new,'different_selection')]:
        ds,cs,ad=decompose(a,b,label,links,revised,original)
        decomposition.extend(ds);contributions.extend(cs);additions.extend(ad)
    write_csv(decomposition,'SUPPORT_AND_WEIGHT_DECOMPOSITION.csv')
    write_csv(pd.concat(contributions,ignore_index=True),'EVENT_WEIGHT_CONTRIBUTIONS.csv.gz')
    write_csv(additions,'NEWLY_PAIRED_Q_EVENTS.csv')
    different_rows=[]
    for r in different.to_dict('records'):
        a,b=r['structure_team'],r['comparator_team']
        row=dict(r)
        for name,key in [('structure',a),('comparator',b)]:
            row[name+'_members']='|'.join(sorted(members(original[key]['member_workers'])))
            row[name+'_automatic_status']=original[key]['score_status']
            row[name+'_assisted_status']=revised[key]['score_status']
            row[name+'_manual']=key in MANUAL
            row[name+'_nodes']=original[key]['nodes']
            for metric in ['B8L2','D10','boundary_loss','direction_loss','height_loss','fusion_turn_n']:
                row[name+'_automatic_'+metric]=value(original[key].get(metric))
                row[name+'_assisted_'+metric]=value(revised[key].get(metric))
        row['assisted_Q_difference']=row['structure_assisted_B8L2']-row['comparator_assisted_B8L2']
        row['original_paired']=np.isfinite([row['structure_automatic_B8L2'],row['comparator_automatic_B8L2']]).all()
        row['needs_more_manual_order']=False
        different_rows.append(row)
    write_csv(different_rows,'ALL_DIFFERENT_SELECTION_EVENTS.csv')
    write_csv(pd.DataFrame(different_rows).query('n==20'),'20_7_DIFFERENT_SELECTION_EVENTS.csv')
    focus_ids=set(different[different.n.eq(20)].event_id)
    write_csv(coverage[coverage.event_id.isin(focus_ids)],'20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv')
    # Influence is a support diagnostic, not a newly selected policy or a rerun.
    influence=[]
    for n,group in new_pairs[new_pairs.comparator.eq('Q_RAW')].groupby('n'):
        for subset,part in [('all_registered',group),('different_selection',d_new[d_new.n.eq(n)&d_new.comparator.eq('Q_RAW')])]:
            full=part.dropna(subset=['B8L2_delta'])
            for image in sorted(set(full.image)):
                remaining=full[~full.image.eq(image)]
                im=image_values(remaining,['B8L2_delta'])
                ci=interval(im,'B8L2_delta')
                influence.append(dict(n=n,comparator='Q_RAW',subset=subset,omitted_image=image,
                                      remaining_events=len(remaining),remaining_images=len(im),remaining_buildings=im.building.nunique(),
                                      effect=im.B8L2_delta.mean(),ci_low=ci[0],ci_high=ci[1],
                                      omission_changes_direction=im.B8L2_delta.mean()*image_values(full,['B8L2_delta']).B8L2_delta.mean()<0))
    write_csv(influence,'IMAGE_INFLUENCE_DIAGNOSTIC.csv')
    write_csv(pd.DataFrame(columns=['event_id','policy','team_key','image','reason','requested_human_decision']),
              'ADDITIONAL_HUMAN_REVIEW_QUEUE.csv')
    manifest=[]
    for path in sorted(INPUTS):
        manifest.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    write_csv(manifest,'INPUT_MANIFEST.csv')
    result=dict(schema='v21_qonly_opportunity_acceptance_20261104_v1',source_commit='ac395e703d1fef573d1ef3e105df0286d62a0468',
                method='independent_from_raw_frozen_endpoints_no_fusion_replay',checks=CHECKS,
                checks_passed=sum(r['passed'] for r in CHECKS),checks_failed=sum(not r['passed'] for r in CHECKS),
                design_events=208,unique_requested_teams=670,policy_event_links=1040,
                no_connection_links=len(needy),unique_no_connection_teams=needy.team_key.nunique(),
                manual_covered_links=int(needy.confirmed_order_available.sum()),
                newly_scored_links=int(needy.assisted_Q.notna().sum()),remaining_non_order_failure_links=int(coverage.remaining_failure.sum()),
                additional_manual_order_required=0,additional_endpoint_scoring_required=0,
                limitation='Complete opportunity coverage within the frozen 208-event design only; no global repair-rate or randomized human-treatment inference.')
    (OUT/'CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else x)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,default=lambda x:x.item() if isinstance(x,np.generic) else x))


if __name__=='__main__':
    main()
