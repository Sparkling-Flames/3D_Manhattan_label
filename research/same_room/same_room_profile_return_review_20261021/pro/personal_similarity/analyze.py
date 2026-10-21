"""Personal same-room quality: descriptive repetition and building-held-out information increments.

No room discovery, taxonomy refitting, fusion or score changes. See DESIGN_PRE_DATA.json.
Run: python analyze.py --repo /path/to/3D_Manhattan_label --out /path/to/output
"""
from __future__ import annotations
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse, gzip, hashlib, itertools, json, subprocess, warnings
from pathlib import Path
from functools import lru_cache
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from threadpoolctl import threadpool_limits
threadpool_limits(limits=2)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SEED = 20261021
STRUCT = ['pair_n_peer_delta', 'turn_n_peer_delta', 'short_turn_edges_peer_delta', 'near_straight_nodes_5deg_peer_delta', 'log_area_peer_delta', 'log_height_peer_delta']
warnings.filterwarnings('ignore', category=RuntimeWarning)

def readj(p):
    with _open_data(p, 'rt', encoding='utf-8-sig') if str(p).endswith('.gz') else open(p, encoding='utf-8-sig') as f:
        return json.load(f)

def writej(p, x):

    def default(v):
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
        if isinstance(v, np.ndarray):
            return v.tolist()
        if isinstance(v, Path):
            return str(v)
        raise TypeError(type(v))
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, default=default), encoding='utf-8')

def save(df, p):
    _write_csv(df, p, index=False, encoding='utf-8-sig', float_format='%.8g')

def corr(a, b, rank=False):
    a, b = (np.asarray(a), np.asarray(b))
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) < 1e-10 or np.std(b[ok]) < 1e-10:
        return np.nan
    return float(spearmanr(a[ok], b[ok]).statistic if rank else pearsonr(a[ok], b[ok]).statistic)

def flat_records(repo):
    raw = readj(repo / 'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    cols = ['object_id', 'worker_id', 'image_id', 'image_code', 'building_id', 'room_id', 'condition', 'origin', 'current_class', 'scene', 'is_oos', 'is_doorway', 'quality_usable', 'quality_use', 'pool_analysis_eligible', 'independent_vote_eligible', 'cleaning_disposition', 'B8L2', 'D10', 'reference_id', 'reference_version', 'source_active_time_seconds', 'target_matched_time_seconds', 'declared_pair_count', 'geometry_status']
    rows = []
    for r in raw:
        a = {c: r.get(c) for c in cols}
        be = r.get('binding_evidence') or {}
        re = r.get('reference_evidence') or {}
        a.update(chosen_target_id=be.get('chosen_target_id'), current_target_id=be.get('current_target_id'), reference_pairs=len(re.get('points_1024x512') or []) // 2, scope_response=(r.get('scope_evidence') or {}).get('response'), source_path=(r.get('source_evidence') or {}).get('path'))
        rows.append(a)
    d = pd.DataFrame(rows)
    d['building'] = d.building_id
    gates = _read_csv(repo / 'research/same_room/same_room_v2_prediction_20261019/training_admission.csv')
    d['training_allowed'] = d.object_id.map(gates.set_index('object_id').training_allowed).eq(True)
    d['layer'] = np.where(d.is_doorway, 'doorway', 'ordinary')
    d['formal'] = d.quality_usable & d.pool_analysis_eligible & ~d.is_oos & d.quality_use.isin(['ordinary_primary', 'doorway_quality']) & d.chosen_target_id.eq(d.current_target_id)
    d = d[d.formal & d.B8L2.notna() & d.D10.notna()].copy()
    assert not d.duplicated(['image_id', 'condition', 'worker_id']).any()
    d['task_key'] = d.image_id + '|' + d.condition + '|' + d.reference_id + '|' + d.reference_version
    for metric in ['B8L2', 'D10']:
        g = d.groupby('task_key')[metric]
        n = g.transform('count')
        s = g.transform('sum')
        d['peer_' + metric] = np.where(n > 1, (s - d[metric]) / (n - 1), np.nan)
        d['relative_' + metric] = d[metric] - d['peer_' + metric]
        d['rank_' + metric] = g.rank(pct=True)
        ss = d[metric].pow(2).groupby(d.task_key).transform('sum')
        peer_var = (ss - d[metric] ** 2 - (s - d[metric]) ** 2 / (n - 1)) / (n - 2)
        d['task_sd_' + metric] = np.sqrt(np.maximum(peer_var, 0)).where(n > 2)
        low = d[metric].lt(50).astype(float)
        low_n = low.groupby(d.task_key).transform('sum')
        d['task_low_' + metric] = ((low_n - low) / (n - 1)).where(n > 1)
    d['task_n'] = d.groupby('task_key').object_id.transform('size')
    return d

def history_stats(d, excluded, metric='B8L2', condition='manual'):
    h = d[d.condition.eq(condition) & d.layer.eq('ordinary') & d.training_allowed & ~d.building.isin(excluded)].copy()
    g = h.groupby('task_key')[metric]
    n = g.transform('count')
    s = g.transform('sum')
    h['theta'] = h[metric] - (s - h[metric]) / (n - 1)
    h.loc[n.le(1), 'theta'] = np.nan
    return h.groupby('worker_id').agg(ext_abs=(metric, 'mean'), theta=('theta', 'mean'), ext_sd=(metric, 'std'), ext_q10=(metric, lambda x: x.quantile(0.1)), ext_n=(metric, 'size'), ext_images=('image_id', 'nunique'), ext_buildings=('building', 'nunique'))

def descriptive(d, relations, original, groups, out):
    hist = {(c, b): history_stats(d, {b}, condition=c) for c in d.condition.unique() for b in d.building.unique()}
    rows = []
    summary = []
    pairindex = []
    cells = {(c, i): v.set_index('worker_id') for (c, i), v in d.groupby(['condition', 'image_id'])}
    for ri, r in enumerate(relations):
        if not r.get('physical_adopted'):
            continue
        for cond in ['manual', 'semi']:
            a = cells.get((cond, r['image_a']))
            b = cells.get((cond, r['image_b']))
            if a is None or b is None:
                continue
            workers = sorted(set(a.index) & set(b.index))
            layer = 'doorway' if a.is_doorway.any() or b.is_doorway.any() else 'ordinary'
            base = dict(pair_id=ri, condition=cond, layer=layer, building=a.building.iloc[0], image_a=r['image_a'], image_b=r['image_b'], code_a=a.image_code.iloc[0], code_b=b.image_code.iloc[0], user_groups='|'.join(r.get('user_group_ids') or []), scope_comparable=r.get('scope_comparable'), substantive_conflict=r.get('substantive_conflict'), oos_pending=r.get('oos_pending'), n_a=len(a), n_b=len(b), n_common=len(workers), reference_a=a.reference_id.iloc[0], reference_b=b.reference_id.iloc[0])
            pairindex.append(base)
            if not workers:
                continue
            av = a.loc[workers]
            bv = b.loc[workers]
            h = hist[cond, base['building']]
            ex = h.reindex(workers).theta.to_numpy()
            qa = av.B8L2.to_numpy()
            qb = bv.B8L2.to_numpy()
            ra = av.relative_B8L2.to_numpy()
            rb = bv.relative_B8L2.to_numpy()
            n = len(workers)
            ca = (qa - qa.mean()) * n / (n - 1) if n > 1 else np.full(n, np.nan)
            cb = (qb - qb.mean()) * n / (n - 1) if n > 1 else np.full(n, np.nan)
            for k, w in enumerate(workers):
                aa = av.loc[w]
                bb = bv.loc[w]
                rows.append(dict(**base, worker_id=w, origin=aa.origin, object_a=aa.object_id, object_b=bb.object_id, Q_a=qa[k], Q_b=qb[k], D10_a=aa.D10, D10_b=bb.D10, relative_a=ra[k], relative_b=rb[k], common_relative_a=ca[k], common_relative_b=cb[k], rank_a=aa.rank_B8L2, rank_b=bb.rank_B8L2, external_theta=ex[k], surprise_a=ra[k] - ex[k], surprise_b=rb[k] - ex[k], low_a=qa[k] < 50, low_b=qb[k] < 50, pairs_a=aa.declared_pair_count, pairs_b=bb.declared_pair_count, ref_pairs_a=aa.reference_pairs, ref_pairs_b=bb.reference_pairs, difficulty_a=aa.current_class, difficulty_b=bb.current_class, source_time_a=aa.source_active_time_seconds, source_time_b=bb.source_active_time_seconds, source_a=aa.source_path, source_b=bb.source_path))
            summary.append(dict(**base, mean_a=float(qa.mean()), mean_b=float(qb.mean()), abs_mean_gap=float(abs(qa.mean() - qb.mean())), person_abs_gap=float(abs(qa - qb).mean()), relative_abs_gap=float(abs(ra - rb).mean()), common_relative_abs_gap=float(abs(ca - cb).mean()), rank_rho=corr(qa, qb, True), Q_pearson=corr(qa, qb), relative_pearson=corr(ra, rb), surprise_pearson=corr(ra - ex, rb - ex), same_relative_sign=float(np.mean((ra >= 0) == (rb >= 0))), same_surprise_sign=float(np.mean(((ra - ex >= 0) == (rb - ex >= 0))[np.isfinite(ex)])) if np.isfinite(ex).any() else np.nan, low_either=int(np.sum((qa < 50) | (qb < 50))), low_both=int(np.sum((qa < 50) & (qb < 50))), both_good=int(np.sum((qa >= 80) & (qb >= 80))), good_bad_switch=int(np.sum((qa >= 80) & (qb < 50) | (qb >= 80) & (qa < 50))), relative_sign_chance=float(np.mean(ra >= 0) * np.mean(rb >= 0) + (1 - np.mean(ra >= 0)) * (1 - np.mean(rb >= 0)))))
    pairs = pd.DataFrame(summary)
    person = pd.DataFrame(rows)
    save(pd.DataFrame(pairindex), out / 'direct_pair_index.csv')
    save(pairs, out / 'direct_pair_similarity.csv')
    save(person, out / 'direct_pair_workers.csv.gz')
    primary = person[person.condition.eq('manual') & person.layer.eq('ordinary') & person.scope_comparable & ~person.substantive_conflict].copy()
    primary['abs_gap'] = abs(primary.Q_a - primary.Q_b)
    primary['relative_gap'] = abs(primary.relative_a - primary.relative_b)
    primary['same_sign'] = (primary.relative_a >= 0) == (primary.relative_b >= 0)
    primary['rank_gap'] = abs(primary.rank_a - primary.rank_b)
    primary['same_surprise'] = np.where(primary.surprise_a.notna() & primary.surprise_b.notna(), (primary.surprise_a >= 0) == (primary.surprise_b >= 0), np.nan)
    wr = []
    for w, g in primary.groupby('worker_id'):
        bi = g.groupby('building').agg(abs_gap=('abs_gap', 'mean'), relative_gap=('relative_gap', 'mean'), same_sign=('same_sign', 'mean'), rank_gap=('rank_gap', 'mean'), same_surprise=('same_surprise', 'mean'))
        imgs = set(g.image_a) | set(g.image_b)
        rr = d[d.condition.eq('manual') & d.image_id.isin(imgs) & d.worker_id.eq(w)]
        wr.append(dict(worker_id=w, origin=g.origin.iloc[0], n_pairs=len(g), n_images=len(imgs), n_buildings=g.building.nunique(), groups='|'.join(sorted(set('|'.join(g.user_groups).split('|')))), Q_mean=rr.B8L2.mean(), relative_mean=rr.relative_B8L2.mean(), low_count=int(rr.B8L2.lt(50).sum()), n_records=len(rr), Q_sd=rr.B8L2.std(), external_theta_mean=g.external_theta.mean(), symmetric_pair_Q_rho=corr(np.r_[g.Q_a, g.Q_b], np.r_[g.Q_b, g.Q_a], True), **bi.mean().to_dict()))
    save(pd.DataFrame(wr), out / 'worker_repeatability.csv')
    an = []
    effects = []
    matrix = []
    index = []
    for og in original:
        images = og['image_ids']
        gid = og['review_code']
        relkeys = {tuple(sorted([r['image_a'], r['image_b']])): r for r in relations}
        for cond in ['manual', 'semi']:
            x = d[d.image_id.isin(images) & d.condition.eq(cond)]
            for layer in ['ordinary', 'doorway']:
                xx = x[x.layer.eq(layer)]
                if xx.image_id.nunique() < 2:
                    continue
                p = xx.pivot(index='worker_id', columns='image_id', values='B8L2').dropna()
                present = sorted(xx.image_id.unique())
                scope = all((relkeys.get(tuple(sorted(ij)), {}).get('scope_comparable', False) for ij in itertools.combinations(present, 2)))
                direct = all((relkeys.get(tuple(sorted(ij)), {}).get('physical_adopted', False) for ij in itertools.combinations(present, 2)))
                index.append(dict(group=gid, condition=cond, layer=layer, n_declared=len(images), n_observed=len(present), n_common=len(p), scope_comparable=scope, direct_complete=direct, images='|'.join(present)))
                if len(p) < 3 or p.shape[1] < 2:
                    continue
                q = p.to_numpy()
                gm = q.mean()
                we = q.mean(1) - gm
                ve = q.mean(0) - gm
                interaction = q - gm - we[:, None] - ve[None, :]
                sst = np.square(q - gm).sum()
                ssw = q.shape[1] * np.square(we).sum()
                ssv = q.shape[0] * np.square(ve).sum()
                ssi = np.square(interaction).sum()
                an.append(dict(group=gid, condition=cond, layer=layer, building=xx.building.iloc[0], n_workers=len(p), n_views=p.shape[1], scope_comparable=scope, direct_complete=direct, mean=gm, view_mean_range=float(np.ptp(q.mean(0))), worker_share=ssw / sst, view_share=ssv / sst, interaction_share=ssi / sst, interaction_rms=float(np.sqrt(np.mean(interaction ** 2))), total_ss=sst, worker_ss=ssw, view_ss=ssv, interaction_ss=ssi))
                for k, w in enumerate(p.index):
                    row = xx[xx.worker_id.eq(w)].set_index('image_id').loc[p.columns]
                    effects.append(dict(group=gid, condition=cond, layer=layer, worker_id=w, n_views=p.shape[1], Q_mean=q[k].mean(), Q_min=q[k].min(), Q_max=q[k].max(), worker_effect=we[k], interaction_rms=np.sqrt(np.mean(interaction[k] ** 2)), relative_sign_consistency=max(np.mean(q[k] > q.mean(0)), np.mean(q[k] < q.mean(0))), external_theta=hist[cond, xx.building.iloc[0]].theta.get(w, np.nan)))
                    for j, im in enumerate(p.columns):
                        aa = row.loc[im]
                        matrix.append(dict(group=gid, condition=cond, layer=layer, worker_id=w, image_id=im, image_code=aa.image_code, object_id=aa.object_id, reference_id=aa.reference_id, reference_version=aa.reference_version, Q=q[k, j], view_mean=q[:, j].mean(), worker_effect=we[k], view_effect=ve[j], interaction=interaction[k, j], relative=q[k, j] - q[:, j].mean()))
    save(pd.DataFrame(index), out / 'declaration_support.csv')
    save(pd.DataFrame(an), out / 'declaration_variation_partition.csv')
    save(pd.DataFrame(effects), out / 'declaration_worker_effects.csv')
    save(pd.DataFrame(matrix), out / 'declaration_common_matrix.csv.gz')
    return (primary, pairs, pd.DataFrame(an), pd.DataFrame(matrix))

def make_base(d, repo, primary, out):
    p = _read_csv(repo / 'research/same_room/same_room_multiview_20261020/individual_features.csv.gz')
    p = p[p.metric.eq('B8L2') & p.origin.eq('all')].copy().drop(columns=['metric', 'origin', 'panel', 'actual', 'source', 'baseline', 'single_error'])
    splits = _read_csv(repo / 'research/same_room/same_room_multiview_20261020/splits.csv.gz')
    histories = splits.set_index('split_id').history.str.split('|').to_dict()
    p['budget'] = 'majority'
    single = []
    for r in primary.itertuples():
        for src, tgt in [(r.image_a, r.image_b), (r.image_b, r.image_a)]:
            sid = f'PAIR{r.pair_id}_{src}'
            histories[sid] = [src]
            single.append(dict(group_id=f'PAIR{r.pair_id}', building=r.building, m=1, N=2, split_id=sid, target_image=tgt, worker_id=r.worker_id, source_n=1, budget='single_direct'))
    single = pd.DataFrame(single).drop_duplicates()
    matched = []
    groups = readj(repo / 'research/same_room/same_room_multiview_20261020/GROUPS.json')
    manual = d[d.condition.eq('manual') & d.layer.eq('ordinary')].set_index(['image_id', 'worker_id'])
    gmap = {g['group_id']: g for g in groups}
    present = set(manual.index)
    for r in p[['group_id', 'building', 'target_image', 'worker_id', 'N']].drop_duplicates().itertuples():
        for src in gmap[r.group_id]['images']:
            if src == r.target_image or (src, r.worker_id) not in present:
                continue
            sid = f'{r.group_id}_single_{src}'
            histories[sid] = [src]
            matched.append(dict(group_id=r.group_id, building=r.building, m=1, N=r.N, split_id=sid, target_image=r.target_image, worker_id=r.worker_id, source_n=1, budget='single_matched'))
    p = pd.concat([p, single, pd.DataFrame(matched)], ignore_index=True)
    p['row_id'] = np.arange(len(p))
    srcmap = {}
    manual_dict = manual.to_dict('index')
    for sid, w in p[['split_id', 'worker_id']].drop_duplicates().itertuples(index=False, name=None):
        srcmap[sid, w] = [im for im in histories[sid] if (im, w) in manual.index]
    p['source_images'] = ['|'.join(srcmap[s, w]) for s, w in zip(p.split_id, p.worker_id)]
    p['target_object_id'] = [manual_dict[i, w]['object_id'] for i, w in zip(p.target_image, p.worker_id)]
    p['training_allowed'] = [bool(manual_dict[i, w]['training_allowed'] and all((manual_dict[s, w]['training_allowed'] for s in srcmap[sid, w]))) for i, w, sid in zip(p.target_image, p.worker_id, p.split_id)]
    g = p[p.budget.eq('majority')].groupby(['group_id', 'target_image', 'worker_id']).m.nunique()
    p['fixed_support'] = [r.budget != 'majority' or g.get((r.group_id, r.target_image, r.worker_id), 0) == r.N - 1 - r.N // 2 for r in p.itertuples()]
    p = p[p.fixed_support].copy().reset_index(drop=True)
    p['row_id'] = np.arange(len(p))
    save(p, out / 'prediction_design.csv.gz')
    return (p, srcmap)

def hierarchy_weights(p):
    keys = ['budget', 'building', 'target_image', 'group_id', 'worker_id', 'm']
    nrep = p.groupby(keys).row_id.transform('size')
    nm = p.groupby(keys[:-1]).m.transform('nunique')
    nw = p.groupby(['budget', 'building', 'target_image', 'group_id']).worker_id.transform('nunique')
    ng = p.groupby(['budget', 'building', 'target_image']).group_id.transform('nunique')
    ni = p.groupby(['budget', 'building']).target_image.transform('nunique')
    nb = p.groupby('budget').building.transform('nunique')
    return np.asarray(1 / (nrep * nm * nw * ng * ni * nb), float)

def features(p, d, labels, outer, metric, srcmap):
    v = d[d.condition.eq('manual') & d.layer.eq('ordinary')].copy()
    v = v.set_index(['image_id', 'worker_id'])
    label = labels[labels.condition.eq('manual') & labels.heldout_building.eq(outer)].set_index('worker_id')
    workers = sorted(v.index.get_level_values('worker_id').unique())
    li = label.reindex(workers)
    a = li[STRUCT].to_numpy(float)
    mask = np.isfinite(a).sum(1) >= 4
    med = np.nanmedian(a, axis=0)
    a = np.where(np.isfinite(a), a, med)
    scale = np.nanstd(a, axis=0)
    a = (a - med) / np.where(scale > 1e-09, scale, 1)
    dist = np.sqrt(np.square(a[:, None, :] - a[None, :, :]).sum(2))
    dist[~mask, :] = np.inf
    dist[:, ~mask] = np.inf
    np.fill_diagonal(dist, np.inf)
    nearest = {w: [workers[j] for j in np.argsort(dist[k]) if np.isfinite(dist[k, j])][:5] for k, w in enumerate(workers)}
    target_dict = v.to_dict('index')
    label_dict = label.to_dict('index')
    blocks = []
    for building, g in p.groupby('building', sort=False):
        h = history_stats(d, {outer, building}, metric)
        imids = set(g.source_images.str.split('|').explode())
        vv = v.loc[v.index.get_level_values('image_id').isin(imids)].copy()
        vv['theta'] = vv.index.get_level_values('worker_id').map(h.theta)
        vv['surprise'] = vv[metric] - vv['peer_' + metric] - vv.theta
        lv = label.primary_fine_class.to_dict()
        cv = label.primary_coarse_class.to_dict()
        cs = {}
        for image, x in vv.groupby(level=0):
            xx = x.droplevel(0)
            xx['fine'] = xx.index.map(lv)
            xx['coarse'] = xx.index.map(cv)
            for w, r in xx.iterrows():
                other_surprise = xx[metric] - (xx[metric].sum() - r[metric] - xx[metric]) / (len(xx) - 2) - xx.theta
                other_surprise.loc[w] = np.nan
                values = []
                for col in ['fine', 'coarse']:
                    others = other_surprise[(xx.index != w) & xx[col].eq(r[col]) & xx[col].notna()].dropna()
                    values.extend([float(others.sum() / (len(others) + 2)), len(others)])
                nn = other_surprise.loc[xx.index.intersection(nearest.get(w, []))].dropna()
                cs[image, w] = values + [float(nn.sum() / (len(nn) + 2)), len(nn)]
        source_dict = vv.to_dict('index')
        h_dict = h.to_dict('index')
        cache = {}
        f = []
        for row in g.itertuples():
            sources = row.source_images.split('|')
            w = row.worker_id
            hs = h_dict.get(w, {})
            lab = label_dict.get(w, {})
            key = (row.source_images, w)
            if key not in cache:
                sr = [source_dict[s, w] for s in sources]
                q = np.array([r[metric] for r in sr])
                pe = np.array([r['peer_' + metric] for r in sr])
                sig = np.array([cs[s, w] for s in sources])
                cache[key] = dict(peer=float(np.mean(pe)), own=float(np.mean(q)), own_sd=float(np.std(q)), own_low=float(np.mean(q < 50)), peer_sd=float(np.std(pe)), peer_dispersion=float(np.mean([r['task_sd_' + metric] for r in sr])), peer_low=float(np.mean([r['task_low_' + metric] for r in sr])), own_surprise=float(np.mean(q - pe) - hs.get('theta', np.nan)), class_fine=float(sig[:, 0].mean()), class_fine_n=float(sig[:, 1].mean()), class_coarse=float(sig[:, 2].mean()), class_coarse_n=float(sig[:, 3].mean()), neighbor=float(sig[:, 4].mean()), neighbor_n=float(sig[:, 5].mean()), source_count=len(sources), fine_label=lab.get('primary_fine_class', 'unassigned'), coarse_label=lab.get('primary_coarse_class', 'unassigned'), **{k: hs.get(k, np.nan) for k in ['ext_abs', 'theta', 'ext_sd', 'ext_q10', 'ext_n', 'ext_images', 'ext_buildings']}, **{k: lab.get(k, np.nan) for k in STRUCT})
            target = target_dict[row.target_image, w]
            f.append(dict(row_id=row.row_id, actual=target[metric], target_relative=target['relative_' + metric], origin_new=float(target['origin'] == 'new'), **cache[key]))
        blocks.append(pd.DataFrame(f))
    f = pd.concat(blocks).set_index('row_id').reindex(p.row_id)
    f['log_ext_n'] = np.log1p(f.ext_n)
    f['log_source_count'] = np.log1p(f.source_count)
    for c in ['M00', 'M01', 'M10', 'M11']:
        f['class_' + c] = f.fine_label.eq(c).astype(float)
    return f.reset_index(drop=True)

def fitted_models(p, d, labels, srcmap, out):
    metric_outputs = []
    folds = []
    coeffs = []
    oof_features = []
    basic = ['peer', 'theta']
    continuous = basic + ['ext_abs', 'ext_sd', 'ext_q10', 'log_ext_n', 'log_source_count', 'peer_sd', 'peer_dispersion', 'peer_low', 'origin_new'] + STRUCT
    own = ['own_surprise', 'own_sd', 'own_low']
    classes = ['class_fine', 'class_coarse', 'class_fine_n', 'class_coarse_n', 'class_M00', 'class_M01', 'class_M10', 'class_M11']
    neighbors = ['neighbor', 'neighbor_n']
    feature_sets = {'basic': basic, 'continuous': continuous, 'continuous_own': continuous + own, 'continuous_class': continuous + classes, 'continuous_own_class': continuous + own + classes, 'continuous_own_neighbor': continuous + own + neighbors, 'continuous_own_neighbor_class': continuous + own + neighbors + classes}
    for metric in ['B8L2', 'D10']:
        results = []
        p_all = p
        for outer in sorted(p_all.building.unique()):
            p = p_all if outer in set(p_all[p_all.budget.eq('majority')].building) else p_all[p_all.budget.eq('single_direct')].reset_index(drop=True)
            print('FEATURES', metric, outer, flush=True)
            f = features(p, d, labels, outer, metric, srcmap)
            held = p.building.eq(outer)
            if metric == 'B8L2':
                oof_features.append(pd.concat([p.loc[held].reset_index(drop=True), f.loc[held].reset_index(drop=True)], axis=1).loc[:, lambda x: ~x.columns.duplicated()])
            for budget in ['majority', 'single_direct']:
                te = held & (p.budget.isin(['majority', 'single_matched']) if budget == 'majority' else p.budget.eq(budget))
                tr = ~held & p.budget.eq(budget) & p.training_allowed
                valid = f[['peer', 'theta', 'ext_abs']].notna().all(axis=1)
                tr &= valid
                te &= valid
                if not te.any() or p.loc[tr].building.nunique() < 3:
                    continue
                train = p[tr]
                test = p[te]
                ft = f.loc[tr]
                fe = f.loc[te]
                y = ft.actual.to_numpy()
                w = hierarchy_weights(train)
                w = w / w.sum() * len(train)
                rr = test[['row_id', 'budget', 'group_id', 'building', 'm', 'N', 'split_id', 'target_image', 'worker_id', 'source_images', 'target_object_id', 'source_n']].copy()
                rr['metric'] = metric
                rr['actual'] = fe.actual.to_numpy()
                rr['target_relative'] = fe.target_relative.to_numpy()
                rr['external_abs'] = fe.ext_abs.to_numpy()
                rr['own_source'] = fe.own.to_numpy()
                rr['public_source'] = fe.peer.to_numpy()
                rr['public_external'] = np.clip(fe.peer + fe.theta, 0, 100).to_numpy()
                rr['public_external_halfown'] = np.clip(fe.peer + fe.theta + 0.5 * fe.own_surprise, 0, 100).to_numpy()
                rr['public_external_halfclass'] = np.clip(fe.peer + fe.theta + 0.5 * fe.class_fine, 0, 100).to_numpy()
                for key, cols in feature_sets.items():
                    print('MODEL', metric, outer, budget, key, flush=True)
                    imp = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                    xt = imp.fit_transform(ft[cols])
                    xe = imp.transform(fe[cols])
                    sc = StandardScaler().fit(xt, sample_weight=w)
                    xt = sc.transform(xt)
                    xe = sc.transform(xe)
                    ridge = Ridge(alpha=10).fit(xt, y, sample_weight=w * 1000 / w.sum())
                    rr['ridge_' + key] = np.clip(ridge.predict(xe), 0, 100)
                    names = list(imp.get_feature_names_out(cols))
                    coeffs.append(dict(metric=metric, outer=outer, budget=budget, model='ridge_' + key, intercept=float(ridge.intercept_), feature_names=names, coefficient=ridge.coef_.tolist(), imputer_statistics=imp.statistics_.tolist(), scaler_mean=sc.mean_.tolist(), scaler_scale=sc.scale_.tolist()))
                    if metric == 'B8L2' and key in ['continuous', 'continuous_own', 'continuous_own_class', 'continuous_own_neighbor']:
                        hg = HistGradientBoostingRegressor(loss='absolute_error', max_iter=100, max_leaf_nodes=7, learning_rate=0.06, min_samples_leaf=30, l2_regularization=10, early_stopping=False, random_state=SEED)
                        hg.fit(ft[cols], y, sample_weight=w)
                        rr['hgb_' + key] = np.clip(hg.predict(fe[cols]), 0, 100)
                    if metric == 'B8L2' and key in ['continuous', 'continuous_own', 'continuous_class', 'continuous_own_class', 'continuous_own_neighbor']:
                        target = (y < 50).astype(int)
                        logit = LogisticRegression(C=1, solver='lbfgs', max_iter=1000).fit(xt, target, sample_weight=w * 1000 / w.sum())
                        rr['p_low_' + key] = logit.predict_proba(xe)[:, 1]
                folds.append(dict(metric=metric, outer=outer, fit_budget=budget, train_rows=len(train), test_rows=len(test), train_buildings='|'.join(sorted(train.building.unique())), train_unique_answers=train.target_object_id.nunique(), test_unique_answers=test.target_object_id.nunique(), external_history_exclusions='outer + training target building', labels_heldout=outer, training_minimum_buildings=3))
                results.append(rr)
                print('FIT', metric, outer, budget, len(train), len(test), flush=True)
        metric_outputs.append(pd.concat(results, ignore_index=True))
        p = p_all
    result = pd.concat(metric_outputs, ignore_index=True)
    save(result, out / 'prediction_rows.csv.gz')
    save(pd.DataFrame(folds), out / 'model_folds.csv')
    writej(out / 'ridge_parameters.json', coeffs)
    save(pd.concat(oof_features, ignore_index=True), out / 'heldout_information.csv.gz')
    return result

def summarize(pred, out):
    idcols = ['metric', 'budget', 'group_id', 'building', 'm', 'N', 'target_image', 'worker_id', 'target_object_id']
    methods = [c for c in pred if c.startswith(('ridge_', 'hgb_')) or c in ['external_abs', 'own_source', 'public_source', 'public_external', 'public_external_halfown', 'public_external_halfclass']]
    pred['low_actual'] = pred.actual.lt(50)
    agg = []
    tail = []
    for method in methods:
        x = pred[pred[method].notna()].copy()
        x['error'] = x[method] - x.actual
        x['ae'] = x.error.abs()
        x['se'] = x.error ** 2
        x['over20'] = x.error > 20
        x['ae20'] = x.ae > 20
        x['predicted'] = x[method]
        t = x.groupby(idcols, as_index=False).agg(predicted=('predicted', 'mean'), actual=('actual', 'first'), mae=('ae', 'mean'), bias=('error', 'mean'), mse=('se', 'mean'), error_gt20=('over20', 'mean'), abs_error_gt20=('ae20', 'mean'), n_histories=('error', 'size'), source_count=('source_n', 'mean'))
        t['method'] = method
        agg.append(t)
    wt = pd.concat(agg, ignore_index=True)
    save(wt, out / 'prediction_worker_targets.csv.gz')
    target = wt.groupby([c for c in idcols if c not in ['worker_id', 'target_object_id']] + ['method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), mse=('mse', 'mean'), error_gt20=('error_gt20', 'mean'), abs_error_gt20=('abs_error_gt20', 'mean'), workers=('worker_id', 'nunique'))
    rkkeys = [c for c in idcols if c not in ['worker_id', 'target_object_id']]
    ranks = []
    for k, g in pred.groupby(rkkeys + ['split_id']):
        if len(g) < 3:
            continue
        rr = g[['actual'] + methods].rank().to_numpy(float)
        rr -= np.nanmean(rr, axis=0)
        cov = np.nansum(rr[:, 1:] * rr[:, 0, None], axis=0)
        den = np.sqrt(np.nansum(rr[:, 1:] ** 2, axis=0) * np.nansum(rr[:, 0] ** 2))
        rho = np.divide(cov, den, out=np.full_like(cov, np.nan), where=den > 1e-12)
        base = dict(zip(rkkeys, k[:-1]))
        for method, value in zip(methods, rho):
            ranks.append(dict(**base, method=method, rho=value))
    ranks = pd.DataFrame(ranks).groupby(rkkeys + ['method'], as_index=False).rho.mean()
    target = target.merge(ranks, how='left')
    save(target, out / 'prediction_targets.csv')
    groups = target.groupby(['metric', 'budget', 'group_id', 'building', 'm', 'N', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), rho=('rho', 'mean'), images=('target_image', 'nunique'))
    save(groups, out / 'prediction_group_budget.csv')
    bparts = []
    for budget in pred.budget.unique():
        part = target[target.budget.eq(budget)]
        stages = ['minimum_majority', 'maximum_history'] if budget == 'majority' else ['single']
        for stage in stages:
            x = part[part.m.eq(part.N // 2 + 1 if stage == 'minimum_majority' else part.N - 1)] if budget == 'majority' else part
            im = x.groupby(['metric', 'budget', 'building', 'target_image', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), mse=('mse', 'mean'), rho=('rho', 'mean'), error_gt20=('error_gt20', 'mean'), abs_error_gt20=('abs_error_gt20', 'mean'), workers=('workers', 'mean'))
            b = im.groupby(['metric', 'budget', 'building', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), mse=('mse', 'mean'), rho=('rho', 'mean'), error_gt20=('error_gt20', 'mean'), abs_error_gt20=('abs_error_gt20', 'mean'), images=('target_image', 'nunique'))
            b['stage'] = stage
            bparts.append(b)
    b = pd.concat(bparts)
    save(b, out / 'prediction_buildings.csv')
    sm = b.groupby(['metric', 'budget', 'stage', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), mse=('mse', 'mean'), rho=('rho', 'mean'), error_gt20=('error_gt20', 'mean'), abs_error_gt20=('abs_error_gt20', 'mean'), buildings=('building', 'nunique'), images=('images', 'sum'))
    sm['rmse'] = np.sqrt(sm.mse)
    save(sm, out / 'prediction_summary.csv')
    tails = wt[wt.actual < 50]
    for budget in tails.budget.unique():
        x = tails[tails.budget.eq(budget)]
        if budget == 'majority':
            x = x[x.m.eq(x.N - 1)]
        z = x.groupby(['metric', 'budget', 'building', 'target_image', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), people=('worker_id', 'nunique'))
        z = z.groupby(['metric', 'budget', 'building', 'method'], as_index=False).agg(mae=('mae', 'mean'), bias=('bias', 'mean'), targets=('target_image', 'nunique'), people=('people', 'sum'))
        tail.append(z)
    save(pd.concat(tail), out / 'actual_low_quality_diagnostic.csv')
    lowparts = []
    for c in [c for c in pred if c.startswith('p_low_')]:
        x = pred[pred[c].notna()].copy()
        x['brier'] = (x[c] - x.low_actual) ** 2
        x['prob'] = x[c]
        x['logloss'] = -(x.low_actual * np.log(np.clip(x[c], 1e-08, 1 - 1e-08)) + (1 - x.low_actual) * np.log(np.clip(1 - x[c], 1e-08, 1 - 1e-08)))
        t = x.groupby(idcols, as_index=False).agg(prob=('prob', 'mean'), brier=('brier', 'mean'), logloss=('logloss', 'mean'), actual_low=('low_actual', 'first'))
        t['method'] = c
        lowparts.append(t)
    low = pd.concat(lowparts)
    save(low, out / 'lowtail_worker_targets.csv.gz')
    lb = []
    for budget in low.budget.unique():
        x = low[low.budget.eq(budget)]
        if budget == 'majority':
            x = x[x.m.eq(x.N - 1)]
        im = x.groupby(['metric', 'budget', 'building', 'target_image', 'method'], as_index=False).agg(brier=('brier', 'mean'), logloss=('logloss', 'mean'), event_rate=('actual_low', 'mean'), predicted_rate=('prob', 'mean'))
        b = im.groupby(['metric', 'budget', 'building', 'method'], as_index=False).agg(brier=('brier', 'mean'), logloss=('logloss', 'mean'), event_rate=('event_rate', 'mean'), predicted_rate=('predicted_rate', 'mean'))
        lb.append(b)
    lb = pd.concat(lb)
    save(lb, out / 'lowtail_buildings.csv')
    save(lb.groupby(['metric', 'budget', 'method'], as_index=False).mean(numeric_only=True), out / 'lowtail_summary.csv')
    return (sm, wt)

def figures(pairs, an, matrix, summary, out):
    s = summary[(summary.metric == 'B8L2') & (summary.budget == 'majority') & (summary.stage == 'maximum_history')].sort_values('mae')
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(s.method, s.mae, color=['#215e7c' if 'class' not in x else '#c07a2a' for x in s.method])
    ax.invert_yaxis()
    ax.set(xlabel='Building-equal held-out MAE (B8L2)', title='Same targets: source public level, personal history and class increment')
    ax.grid(axis='x', alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / 'heldout_information_increment.png', dpi=170)
    plt.close(fig)
    a = an[(an.condition == 'manual') & (an.layer == 'ordinary') & an.scope_comparable & an.direct_complete].sort_values('interaction_share')
    fig, ax = plt.subplots(figsize=(10, max(5, len(a) * 0.25)))
    left = np.zeros(len(a))
    for col, label, c in [('worker_share', 'Between-worker means', '#176b89'), ('view_share', 'Shared view level', '#d2a047'), ('interaction_share', 'Worker × view residual', '#9b5266')]:
        ax.barh(a.group, a[col], left=left, label=label, color=c)
        left += a[col]
    ax.set(xlabel='Descriptive share of balanced Q sum of squares', title='Original declarations, common-person complete matrices')
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.01), ncol=3)
    fig.tight_layout()
    fig.savefig(out / 'worker_view_variation.png', dpi=170)
    plt.close(fig)
    focus = ['G046', 'G057', 'G090', 'G124', 'G178', 'G205']
    mm = matrix[(matrix.condition == 'manual') & (matrix.layer == 'ordinary') & matrix.group.isin(focus)]
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), constrained_layout=True)
    for ax, gid in zip(axes.flat, focus):
        x = mm[mm.group.eq(gid)]
        pv = x.pivot(index='worker_id', columns='image_code', values='relative')
        order = x.groupby('worker_id').Q.mean().sort_values().index
        pv = pv.reindex(order)
        if pv.empty:
            continue
        im = ax.imshow(pv, vmin=-35, vmax=35, cmap='RdBu', aspect='auto')
        ax.set_xticks(range(len(pv.columns)), [x.split('-')[-1] for x in pv.columns])
        ax.set_yticks(range(len(pv)), pv.index, fontsize=7)
        ax.set_title(gid + ' · Q minus common-person view mean')
        ax.set_xlabel('View code')
    fig.colorbar(im, ax=axes, shrink=0.7, label='B8L2 relative difference')
    fig.savefig(out / 'common_worker_view_relative_heatmap.png', dpi=170)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    ap.add_argument('--stage', choices=['all', 'descriptive', 'predict', 'summarize'], default='all')
    args = ap.parse_args()
    repo = args.repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.stage in ['all', 'descriptive', 'predict']:
        d = flat_records(repo)
        save(d, out / 'formal_record_index.csv.gz')
        rel = readj(repo / 'research/same_room/relation_adoption_20261016/relations.json')
        ogs = readj(repo / 'research/same_room/relation_adoption_20261016/original_groups.json')
        gs = readj(repo / 'research/same_room/same_room_multiview_20261020/GROUPS.json')
        primary, pairs, an, matrix = descriptive(d, rel, ogs, gs, out)
        print('DESCRIBED', len(primary), len(pairs), flush=True)
        if args.stage == 'descriptive':
            return
        p, srcmap = make_base(d, repo, primary, out)
        print('DESIGN', len(p), p.groupby('budget').size().to_dict(), flush=True)
        labels = _read_csv(repo / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv')
        pred = fitted_models(p, d, labels, srcmap, out)
    else:
        pred = _read_csv(out / 'prediction_rows.csv.gz')
        pairs = _read_csv(out / 'direct_pair_similarity.csv')
        an = _read_csv(out / 'declaration_variation_partition.csv')
        matrix = _read_csv(out / 'declaration_common_matrix.csv.gz')
    sm, wt = summarize(pred, out)
    figures(pairs, an, matrix, sm, out)
    inputs = ['research/statistics/v2_evidence_audit_20261019/records.json.gz', 'research/same_room/relation_adoption_20261016/relations.json', 'research/same_room/relation_adoption_20261016/original_groups.json', 'research/same_room/same_room_multiview_20261020/individual_features.csv.gz', 'research/same_room/same_room_multiview_20261020/splits.csv.gz', 'research/same_room/same_room_v2_prediction_20261019/training_admission.csv', 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv']
    writej(out / 'PROVENANCE.json', dict(commit=subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(), status='new calculation from fixed repository inputs; no previous package artifacts recovered', relation_version='same_room_user_working_classification_20261016_v2', taxonomy_version='personnel_taxonomy_20261021_v1', seed=SEED, inputs={p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in inputs}, model_status='fixed-method exploratory comparison with internal building-held-out evaluation; not external prospective validation'))
    print(sm[(sm.metric == 'B8L2') & (sm.budget == 'majority') & (sm.stage == 'maximum_history')][['method', 'mae', 'rho']].sort_values('mae').to_string(index=False), flush=True)
if __name__ == '__main__':
    main()
