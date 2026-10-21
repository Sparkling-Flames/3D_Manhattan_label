"""Retrospective source-only stopping diagnostic on archived actual replay nodes.

No target quality enters choices. Source reference establishment is NOT costed.
A source near-peak rule uses the whole source curve, so is not an online rule.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import itertools
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'research/same_room/same_room_multiview_20261020'
OUTPUT = ROOT / 'research/same_room/same_room_independent_followup_20261021/stopping'
THRESHOLDS = (0, 1, 2, 5)


def choose_prefix(source, ks, tolerance):
    """source is paths x prefixes; all source views must be valid at a prefix."""
    source = np.asarray(source, float)
    valid = np.isfinite(source)
    peak = np.max(np.where(valid, source, -np.inf), axis=1)
    qualifies = valid & (source >= peak[:, None] - tolerance - 1e-10)
    idx = np.argmax(qualifies, axis=1)
    return np.where(qualifies.any(axis=1), np.asarray(ks)[idx], -1)


def splits(n):
    for m in range(n // 2 + 1, n):
        for h in itertools.combinations(range(n), m):
            yield h, [t for t in range(n) if t not in h]


def measure(part):
    q = part.target_q
    paired = part.target_q.notna() & part.terminal_q.notna()
    loss = part.loc[paired, 'terminal_q'] - part.loc[paired, 'target_q']
    return dict(attempts=len(part), groups=part.group_id.nunique(), buildings=part.building.nunique(),
                targets=part.target_image.nunique(), chosen_fraction=float(part.chosen_k.gt(0).mean()),
                mean_k=float(part.loc[part.chosen_k.gt(0), 'chosen_k'].mean()),
                target_complete_fraction=float(q.notna().mean()), target_valid=int(q.notna().sum()),
                target_q_mean=float(q.mean()), target_q10=float(q.quantile(.1)),
                target_below80_fraction=float(q.lt(80).sum()/q.notna().sum()) if q.notna().any() else np.nan,
                paired_terminal_n=int(paired.sum()), loss_to_terminal_mean=float(loss.mean()),
                loss_to_terminal_gt2_fraction=float(loss.gt(2).mean()),
                loss_to_terminal_gt5_fraction=float(loss.gt(5).mean()),
                source_fullcurve_fraction=float(part.source_fullcurve.mean()))


def run(input_dir=INPUT, output_dir=OUTPUT, metric="B8L2", save_cases=False):
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(input_dir / 'replay_nodes.csv.gz', low_memory=False)
    groups = {g['group_id']: g for g in json.load(open(input_dir/'REPLAY_GROUPS.json', encoding='utf-8'))}
    with gzip.open(input_dir/'REPLAY_ORDERS.json.gz', 'rt', encoding='utf-8') as f:
        orders = json.load(f)
    order_map = {(o['group_id'], o['replay']): o['workers'] for o in orders}
    assert nodes.request_id.is_unique
    # Check actual node membership against registered shared ordered prefixes.
    for row in nodes[['group_id','replay','k','ordered_workers']].itertuples(index=False):
        assert row.ordered_workers.split('|') == order_map[row.group_id, row.replay][:row.k]
    rows = []
    support = []
    for gid, part in nodes.groupby('group_id', observed=True):
        g = groups[gid]; images = g['images']; n = len(images)
        replays = sorted(part.replay.unique()); rmap = {r:i for i,r in enumerate(replays)}
        K = int(part.k.max()); matrix = np.full((n,len(replays),K+1), np.nan)
        imap = {im:i for i,im in enumerate(images)}
        for row in part.itertuples():
            if row.complete_evaluable and pd.notna(getattr(row, metric)):
                matrix[imap[row.image_id],rmap[row.replay],row.k] = getattr(row, metric)
        assert len(part) == n * len(replays) * K
        for horizon, cap in [('cap16', min(16,K)), ('full_pool', K)]:
            ks = np.array([k for k in range(1,cap+1) if k != 2])
            for si,(history,targets) in enumerate(splits(n)):
                assert len(history)>n/2 and not set(history).intersection(targets)
                source = matrix[list(history)][:,:,ks].mean(axis=0)
                source_full = np.isfinite(source).all(axis=1)
                choices = {f'source_within_{tol}': choose_prefix(source,ks,tol) for tol in THRESHOLDS}
                choices.update({f'fixed_{k}':np.full(len(replays),min(k,cap)) for k in (1,3,5,7,9,12,16,20,30)})
                choices['terminal_pool'] = np.full(len(replays), cap)
                for t in targets:
                    # This support mask is evaluation-only, identical for every policy.
                    common = np.isfinite(matrix[:,:,ks]).all(axis=(0,2))
                    support.append(dict(group_id=gid,panel=g['replay_panel'],building=g['building'],horizon=horizon,
                                        split_id=si,source_views=len(history),group_views=n,target_image=images[t],attempts=len(replays),
                                        source_fullcurve=int(source_full.sum()), common_complete=int(common.sum())))
                    for policy,chosen in choices.items():
                        for ri,r in enumerate(replays):
                            k = int(chosen[ri]); q = matrix[t,ri,k] if k>0 else np.nan
                            rows.append((gid,g.get('parent_group',gid),g['replay_panel'],g['building'],horizon,si,
                                         len(history),n,images[t],r,cap,policy,k,q,matrix[t,ri,cap],
                                         bool(source_full[ri]),bool(common[ri])))
    cases = pd.DataFrame(rows, columns=['group_id','parent_group','panel','building','horizon','split_id',
            'source_views','group_views','target_image','replay','terminal_k','policy','chosen_k','target_q',
            'terminal_q','source_fullcurve','common_complete'])
    del rows
    for col in ['group_id','parent_group','panel','building','horizon','target_image','policy']:
        cases[col] = cases[col].astype('category')
    if save_cases:
        cases.to_csv(output_dir/'cases.csv.gz', index=False)
    pd.DataFrame(support).to_csv(output_dir/'support.csv',index=False)
    summaries=[]; group_summaries=[]; target_summaries=[]
    keys=['panel','horizon','policy']
    strata=[]
    for budget, subset in [('all_m_pooled', cases), ('minimum_majority', cases[cases.source_views.eq(cases.group_views//2+1)]), ('maximum_history', cases[cases.source_views.eq(cases.group_views-1)])]:
        strata.extend([(budget,'all_attempts',subset),(budget,'common_complete',subset[subset.common_complete])])
    for budget, support_name, frame in strata:
        for key, part in frame.groupby(keys, observed=True):
            base=dict(zip(keys,key), support=support_name, history_budget=budget)
            summaries.append(dict(**base,weighting='case',**measure(part)))
            gm=[]
            for gid, gp in part.groupby('group_id', observed=True):
                stats=measure(gp)
                target_records=[]
                for target_id,tp in gp.groupby('target_image', observed=True):
                    tm=measure(tp);target_records.append(tm)
                    target_summaries.append(dict(**base,group_id=gid,building=gp.building.iloc[0],target_image=target_id,source_views='|'.join(map(str,sorted(tp.source_views.unique()))),group_views=int(tp.group_views.iloc[0]),**tm))
                target_stats=pd.DataFrame(target_records)
                descriptive=[c for c in target_stats if c not in ('attempts','groups','buildings','targets','target_valid','paired_terminal_n')]
                stats.update(target_stats[descriptive].mean().to_dict())
                gm.append(dict(group_id=gid,building=gp.building.iloc[0],**stats))
                group_summaries.append(dict(**base,group_id=gid,building=gp.building.iloc[0],**stats))
            gf=pd.DataFrame(gm)
            numeric=[c for c in gf if c not in ('group_id','building','attempts','groups','buildings','targets','target_valid','paired_terminal_n')]
            for weighting, values in [('group_equal',gf[numeric].mean()),
                                      ('building_equal',gf.groupby('building')[numeric].mean().mean())]:
                # Quantiles here are means of group quantiles, not pooled quantiles.
                summaries.append(dict(**base,weighting=weighting,**values.to_dict(),
                                      attempts=len(part),groups=part.group_id.nunique(),buildings=part.building.nunique(),
                                      targets=part.target_image.nunique(),target_valid=int(part.target_q.notna().sum())))
    summary=pd.DataFrame(summaries); summary.to_csv(output_dir/'summary.csv',index=False)
    pd.DataFrame(group_summaries).to_csv(output_dir/'group_summary.csv',index=False)
    pd.DataFrame(target_summaries).to_csv(output_dir/'target_summary.csv',index=False)
    pareto=[]
    for key, p in summary[summary.support.eq('common_complete')].groupby(['panel','horizon','weighting','history_budget']):
        for row in p.itertuples():
            others=p[p.policy.ne(row.policy)]
            dominates=(others.mean_k.le(row.mean_k+1e-9)&others.target_q_mean.ge(row.target_q_mean-1e-9)&
                       (others.mean_k.lt(row.mean_k-1e-9)|others.target_q_mean.gt(row.target_q_mean+1e-9)))
            pareto.append(dict(panel=key[0],horizon=key[1],weighting=key[2],history_budget=key[3],policy=row.policy,
                               mean_k=row.mean_k,target_q_mean=row.target_q_mean,
                               nondominated=not dominates.any(),dominated_by='|'.join(others.loc[dominates,'policy'])))
    pd.DataFrame(pareto).to_csv(output_dir/'pareto.csv',index=False)
    manifest=dict(metric=metric,reference='archived actual replay_nodes, not unavailable newPro package',
                  source_establishment_cost_not_counted=True,target_quality_excluded_from_choice=True,
                  source_rule='earliest available prefix within tolerance of full source mean curve maximum',
                  source_rule_is_retrospective=True,missing_source_policy='skip incomplete source prefixes; if no finite source mean exists choose -1 and report unchosen, no target-informed fallback',fixed_budgets=[1,3,5,7,9,12,16,20,30],thresholds=list(THRESHOLDS),thresholds_not_fit_to_targets=True,
                  k2='excluded: two-person sorting deferred in source replay',
                  cost='target prefix member count only; fixed_k means min(k, horizon, available pool), identical groups and cases for all budgets. cap16 uses min(16, pool size), not universally 16',
                  support='all_attempts retains missing target outcomes; common_complete requires every candidate prefix on ALL group views, identical across policies AND source history budgets',
                  weighting='case; equal targets within replay-groups; equal replay-groups; equal buildings after equal replay-groups within building. Coverage subsets overlap and are not independent rooms.',
                  low_tail='case target_q10 is pooled; group/building target_q10 is mean target-level quantiles under stated hierarchy, not pooled quantile',
                  history_budgets='minimum_majority and maximum_history separately; all_m_pooled is explicitly combination-weighted sensitivity, not a replacement for per-budget claims',
                  uncertainty='descriptive finite replay design, no independent-room inference or heldout tuning',
                  input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [input_dir/'replay_nodes.csv.gz',input_dir/'REPLAY_GROUPS.json',input_dir/'REPLAY_ORDERS.json.gz']},
                  actual_nodes=len(nodes),policy_case_rows=len(cases),ordered_members_verified=True)
    (output_dir/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return summary

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=INPUT);parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--save-cases', action='store_true')
    parser.add_argument('--metric', choices=['B8L2','D10'], default='B8L2')
    args=parser.parse_args();print(run(args.input,args.output,args.metric,args.save_cases).to_string(index=False))

