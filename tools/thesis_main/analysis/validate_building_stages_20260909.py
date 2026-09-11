"""有限历史终点下的持续稳定阶段、跨图预测与冻结模型特征对照；探索用途。"""
import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from itertools import combinations, groupby
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import changes, ORDERS
from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import onset as window_onset

OLD = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/revised'
OUT = ROOT / 'analysis_results/research_validation_20260909_v2'
MODES = ('with_workers', 'without_workers')
QS = (.975, .95, .925, .90, .85, .80)


def stage_onset(lower, upper):
    """m2的合法候选域k>=2；输入仍保留从k1开始的原始轨迹。"""
    if len(lower)!=len(upper) or len(lower)<2:
        raise ValueError('stage onset requires complete k1 and k2 nodes')
    result=window_onset(np.asarray(lower)[1:],np.asarray(upper)[1:])
    return tuple(None if v is None else v+1 for v in result[:3])+(result[3],)


def stage_tail(states):
    """三值逻辑的逐排列持续阶段；已知违反优先于未知。"""
    answer, tail = [], 'stable'
    for state in reversed(states):
        if state not in ('stable', 'changing', 'unknown'):
            raise ValueError('unexpected state')
        tail = 'changing' if 'changing' in (state, tail) else 'unknown' if 'unknown' in (state, tail) else 'stable'
        answer.append(tail)
    return answer[::-1]


def anchored_states(trajectory, horizon, *, min_future=5, epsilon=.1):
    result = {}
    for k in sorted(i for i in trajectory if i <= horizon - min_future):
        prefix = trajectory[k]
        if prefix['status'] != 'unique' or not any(len(g) >= 2 for g in prefix['clusters']):
            result[k] = 'unknown'
            continue
        states = []
        for j in range(k + 1, horizon + 1):
            later = trajectory[j]
            if later['status'] != 'unique':
                states.append('unknown')
            else:
                d = changes(prefix['clusters'], later['clusters'])
                states.append('stable' if d['membership'] <= epsilon + 1e-12 and d['shares'] <= epsilon + 1e-12
                              and d['promotions'][1] == 0 else 'changing')
        result[k] = stage_tail(states)[0]
    return result


def complete_link_partition(matrix, threshold, point_counts):
    """连续距离的凝聚完全连接；硬点数门禁，不采用连通分量的链式合并。"""
    d = np.asarray(matrix, float).copy()
    counts = np.asarray(point_counts)
    if d.shape != (len(counts), len(counts)) or not np.isfinite(d).all() or (d < 0).any() or not np.allclose(d, d.T):
        raise ValueError('invalid complete link inputs')
    d[counts[:, None] != counts[None, :]] = max(1e6, threshold + 1)
    np.fill_diagonal(d, 0)
    labels = fcluster(linkage(squareform(d), method='complete'), threshold, criterion='distance') if len(d) > 1 else np.ones(len(d))
    groups = [set(np.flatnonzero(labels == label)) for label in sorted(set(labels))]
    return {'status': 'unique', 'clusters': groups}


def weighted_curve(curves, weights):
    c, w = np.asarray(curves, float), np.asarray(weights, float)
    if c.ndim != 3 or c.shape[-1] != 2 or len(c) != len(w) or not np.isfinite(c).all() or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError('invalid prediction weights or curves')
    if (c < 0).any() or (c > 1).any() or (c[:, :, 0] > c[:, :, 1]).any():
        raise ValueError('invalid probability bounds')
    return np.average(c, weights=w, axis=0)


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def extract_features():
    """同一ep300模型、同一PNG优先图源、四旋转，相同前向读取各层。"""
    import torch
    from PIL import Image
    from tools.thesis_main.registry.hohonet_feature_backend import load_model, shared_feature
    from tools.thesis_main.analysis.materialize_c2_task_risk import _apply_whitener, _knn

    dest = OUT / 'features'
    dest.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    checkpoint = ROOT / 'ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth'
    config = ROOT / 'config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml'
    model, device = load_model(checkpoint, config, device='cpu')
    inventory = pd.read_csv(OLD / 'comparison/image_support_comparison.csv').sort_values('image_id')
    cache_paths = [ROOT / 'analysis_results/stage3_test_preparation_20260804_v1/stage3_test_candidate_lhfeat_cache.npz',
                   ROOT / 'analysis_results/c2b_validation_static_20260802_v16/static/c2_candidate_lhfeat_cache.npz']
    caches = [np.load(p, allow_pickle=False) for p in cache_paths]
    lookup = [{Path(str(p)).stem: i for i, p in enumerate(c['paths'])} for c in caches]
    ref = np.load(ROOT / 'analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_reference_cache.npz')
    captured = {}
    def pool(value):
        value = shared_feature(value)
        x = value.detach().cpu().numpy().reshape(value.shape[0], value.shape[1], -1)
        return np.concatenate([x.mean(2), x.std(2)], 1).mean(0)
    def capture(name):
        def hook(_module, _args, value):
            if name == 'encoder':
                for i, item in enumerate(value):
                    captured[f'encoder_{i+1}'] = pool(item)
            else:
                captured[name] = pool(value)
        return hook
    handles = [module.register_forward_hook(capture(name)) for name, module in
               [('encoder', model.encoder), ('compressed', model.decoder), ('refined', model.horizon_refine)]]
    features, rows = {}, []
    started = time.perf_counter()
    with torch.inference_mode():
        for row in inventory.itertuples():
            matches = [(ci, lu[row.image_id]) for ci, lu in enumerate(lookup) if row.image_id in lu]
            if not matches:
                raise ValueError(f'no image path for {row.image_id}')
            # Prefer the PNG data asset when available, without mixing cached descriptor vectors.
            candidates = [Path(str(caches[ci]['paths'][idx])) for ci, idx in matches]
            pngs = list((ROOT / 'data/mp3d_layout').glob(f'*/img/{row.image_id}.png'))
            path = sorted(pngs)[0] if pngs else candidates[0]
            rgb = np.asarray(Image.open(path).convert('RGB'), dtype=np.float32) / 255
            x = torch.from_numpy(rgb).permute(2, 0, 1)[None]
            w = x.shape[-1]
            orbit = torch.cat([x.roll(round(w * f), -1) for f in (0, .25, .5, .75)])
            shared = shared_feature(model.extract_feat(orbit))
            captured['shared'] = pool(shared)
            captured['shared_local'] = shared.amax(-1).mean(0).numpy()
            # Old d_t used single-phase shared mean, normalized, rather than this orbit mean+std.
            captured['legacy_mean_phase0'] = shared[0].mean(-1).numpy()
            for name, vector in captured.items():
                features.setdefault(name, []).append(vector.copy())
            gw = _apply_whitener(captured['shared'], ref['global_mean'], ref['global_components'], ref['global_scale'])
            lw = _apply_whitener(captured['shared_local'], ref['local_mean'], ref['local_components'], ref['local_scale'])
            result = dict(image_id=row.image_id, building_id=row.building_id, common_n=row.common_n, image_path=str(path),
                          d_model_feat_recomputed=_knn(gw, ref['reference_global']),
                          d_model_feat_local_recomputed=_knn(lw, ref['reference_local']))
            for ci, idx in matches:
                result[f'cache_{ci}_path'] = str(caches[ci]['paths'][idx])
                result[f'cache_{ci}_max_abs_delta'] = float(np.max(abs(captured['shared'] - caches[ci]['global_descriptors'][idx])))
            rows.append(result)
            if len(rows) % 10 == 0:
                print(f'features {len(rows)}/{len(inventory)}, {time.perf_counter()-started:.1f}s', flush=True)
    for handle in handles:
        handle.remove()
    features = {k: np.asarray(v) for k, v in features.items()}
    if any(not np.isfinite(v).all() or len(v) != 214 for v in features.values()):
        raise ValueError('feature extraction coverage or finite value failure')
    np.savez_compressed(dest / 'image_features.npz', image_ids=inventory.image_id.to_numpy(dtype=str), **features)
    pd.DataFrame(rows).to_csv(dest / 'image_feature_audit.csv', index=False)
    save_json(dest / 'FEATURE_PLAN.json', dict(status='exploratory', images=len(rows), checkpoint=str(checkpoint), config=str(config),
        device=device, torch_version=torch.__version__, threads=4, orbit=[0, .25, .5, .75], pooling='channel mean+population std over spatial axes then orbit mean',
        feature_shapes={k:list(v.shape) for k,v in features.items()}, source_selection='prefer local layout PNG; log cache paths and numerical deltas',
        labels_used_for_extraction=False, trained_for_human_stability=False, risk_reference_images=1647,
        feature_cache_mixing=False, elapsed_seconds=time.perf_counter()-started))


def replay_stages():
    dest = OUT / 'stages'
    dest.mkdir(parents=True, exist_ok=True)
    inventory = pd.read_csv(OLD / 'comparison/image_support_comparison.csv').set_index('image_id')
    dense = inventory[inventory.common_n >= 16]
    orders = [json.loads(line) for line in ORDERS.read_text(encoding='utf8').splitlines()]
    if len(orders) != 200 or len({x['replicate'] for x in orders}) != 200:
        raise ValueError('order coverage mismatch')
    curve_rows, full_rows, reason_rows = [], [], []
    started = time.perf_counter()

    def summarize(image_id, config, mode, cache, members):
        n = int(inventory.loc[image_id, 'common_n'])
        horizons = [h for h in (19, 20, 22, 23, 24) if h <= n]
        worker_pos = dict(zip(members.worker_id.astype(str), members.position.astype(int)))
        if len(worker_pos) != len(members):
            raise ValueError('duplicate worker in image')
        agg, reasons = {}, Counter()
        for order in orders:
            seq = [worker_pos[str(w)] for w in order['worker_ids'] if str(w) in worker_pos][:n]
            if len(set(seq)) != n:
                raise ValueError('projected order coverage')
            trajectory, mask = {}, 0
            for k, pos in enumerate(seq, 1):
                mask |= 1 << pos
                trajectory[k] = cache[mask]
            states = np.full((n + 1, n + 1), 2, dtype=np.int8)
            for k in range(1, n):
                prefix = trajectory[k]
                if prefix['status'] != 'unique' or not any(len(g) >= 2 for g in prefix['clusters']):
                    continue
                for j in range(k + 1, n + 1):
                    if trajectory[j]['status'] != 'unique':
                        continue
                    delta = changes(prefix['clusters'], trajectory[j]['clusters'])
                    failed = [delta['membership'] > .1 + 1e-12, delta['shares'] > .1 + 1e-12, delta['promotions'][1] > 0]
                    states[k, j] = 1 if any(failed) else 0
                    if k == 8 and j == n:
                        reasons.update({f'k8_to_N_{r}':int(f) for r,f in zip(('membership','share','new_supported'),failed)})
                        reasons['k8_to_N_evaluable'] += 1
            for h in horizons:
                anchor, rolling = [], []
                for k in range(1, h-4):
                    ds = states[k, k+1:h+1]
                    anchor.append('changing' if 1 in ds else 'unknown' if 2 in ds else 'stable')
                    short = states[k, k+1:k+6]
                    rolling.append('changing' if 1 in short else 'unknown' if 2 in short else 'stable')
                for kind, values in [('anchor',anchor), ('anchor_stage',stage_tail(anchor)), ('rolling_stage',stage_tail(rolling))]:
                    for k, state in enumerate(values,1):
                        counter = agg.setdefault((h,kind,k),Counter())
                        counter[state] += 1
                        if state == 'stable':
                            supported = sum(len(g)>=2 for g in trajectory[k]['clusters'])
                            counter['stable_multi' if supported>=2 else 'stable_single'] += 1
            final = trajectory[n]
            reasons['final_'+final['status']] += 1
        for (h,kind,k), c in agg.items():
            if c['stable']+c['changing']+c['unknown'] != 200:
                raise ValueError('three-state conservation failure')
            curve_rows.append(dict(image_id=image_id,building_id=inventory.loc[image_id,'building_id'],mode=mode,config=config,
                horizon=h,kind=kind,k=k,stable=c['stable'],changing=c['changing'],unknown=c['unknown'],
                lower=c['stable']/200,upper=(c['stable']+c['unknown'])/200,stable_multi=c['stable_multi'],stable_single=c['stable_single']))
        reason_rows.append(dict(image_id=image_id,mode=mode,config=config,common_n=n,**reasons))

    for mode in MODES:
        members = pd.read_csv(OLD / mode / 'replay/image_members.csv',dtype={'worker_id':str})
        members = members[members.image_id.isin(dense.index)]
        by_image = {i:g.sort_values('position') for i,g in members.groupby('image_id')}
        path = OLD / mode / 'replay/subset_partitions.csv.gz'
        with gzip.open(path,'rt',encoding='utf8',newline='') as stream:
            for (image_id,config), group in groupby(csv.DictReader(stream), key=lambda r:(r['image_id'],r['config'])):
                if image_id not in dense.index:
                    continue
                cache = {int(r['subset_mask']):dict(status=r['status'],clusters=[set(g) for g in json.loads(r['clusters_positions_json'])]) for r in group}
                summarize(image_id,config,mode,cache,by_image[image_id])
        print(f'{mode}: saved v5 partitions replayed; {time.perf_counter()-started:.1f}s',flush=True)
        pairs = pd.read_csv(OLD / mode / 'geometry/pairwise_q.csv.gz')
        for image_id, ms in by_image.items():
            n = len(ms)
            ids = {c:p for c,p in zip(ms.canonical_annotation_id,ms.position)}
            d = np.full((n,n),1e6); np.fill_diagonal(d,0)
            for p in pairs[pairs.image_id==image_id].itertuples():
                if p.count_compatible and p.pointwise_correspondence_compatible:
                    a,b=ids[p.left_canonical],ids[p.right_canonical]
                    d[a,b]=d[b,a]=1-min(p.q_boundary,p.q_wallwall)
            invalid = set(ms.loc[~ms.q_geometry_valid,'position'])
            cache = {}
            worker_pos = dict(zip(ms.worker_id,ms.position))
            counts = ms.effective_point_count.to_numpy()
            for order in orders:
                seq = [worker_pos[str(w)] for w in order['worker_ids'] if str(w) in worker_pos]
                mask=0
                for k,p in enumerate(seq,1):
                    mask |= 1<<p
                    if mask in cache:
                        continue
                    ix = sorted(seq[:k])
                    if invalid.intersection(ix):
                        result={'status':'unknown_geometry','clusters':[]}
                    else:
                        result=complete_link_partition(d[np.ix_(ix,ix)],.05,counts[ix])
                        result['clusters']=[set(ix[j] for j in g) for g in result['clusters']]
                        if any(len(set(counts[list(g)]))!=1 for g in result['clusters']):
                            raise ValueError('hard point count failure')
                    cache[mask]=result
            summarize(image_id,'hac_q_0.950',mode,cache,ms)
        print(f'{mode}: complete-link sensitivity finished; {time.perf_counter()-started:.1f}s',flush=True)
    frame = pd.DataFrame(curve_rows)
    frame.to_csv(dest/'stage_curves.csv.gz',index=False)
    pd.DataFrame(reason_rows).to_csv(dest/'stage_failure_diagnostics.csv',index=False)
    write_onsets(frame)
    save_json(dest/'STAGE_PLAN.json',dict(status='completed_exploratory',images=55,buildings=15,modes=MODES,
        geometry_source=str(OLD),lineage_view='confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz',
        permutations=200,min_support=2,epsilon=.1,rate=.8,min_future=5,min_candidate_k=2,horizons=[19,20,22,23,24],
        anchor='each k compared with every later j through H',anchor_stage='each permutation must satisfy all anchor checks from k through H-5',
        rolling_stage='same-permutation all later h5 checks; supplementary',three_value_logic='known violation => changing even if other comparisons unknown; otherwise unknown if any required partition/support missing',
        HAC='scipy complete linkage of continuous 1-min(q) distances with hard effective point counts; canonical-ID input order breaks exact-distance ties',
        v5='reuse independently verified unique maximum-clique partitions, keep nonunique/invalid status',
        bounds='unknown-state identification bounds, not statistical confidence intervals',elapsed_seconds=time.perf_counter()-started))


def write_onsets(frame=None):
    dest=OUT/'stages'
    if frame is None:
        frame=pd.read_csv(dest/'stage_curves.csv.gz')
    onsets=[]
    for key,g in frame.groupby(['image_id','building_id','mode','config','horizon','kind']):
        g=g.sort_values('k'); result=stage_onset(g.lower,g.upper)
        onsets.append(dict(zip(['image_id','building_id','mode','config','horizon','kind'],key))|
            dict(possible=result[0],conservative=result[1],identified=result[2],status=result[3],
                 unknown_node_fraction=(g.unknown/200).mean(),stable_k8_lower=float(g.loc[g.k==8,'lower'].iloc[0]),
                 stable_k8_upper=float(g.loc[g.k==8,'upper'].iloc[0])))
    pd.DataFrame(onsets).to_csv(dest/'image_stage_onsets.csv',index=False)
    plan_path=dest/'STAGE_PLAN.json'
    if plan_path.exists():
        plan=json.loads(plan_path.read_text(encoding='utf8')); plan['min_candidate_k']=2
        plan['onset_domain_note']='k1 trajectory retained; candidates k>=2 because min_support=2'
        save_json(plan_path,plan)


def imputation_sensitivity():
    """两份人工补点撤回到原奇数点；其他图不变。"""
    inventory=pd.read_csv(OLD/'comparison/image_support_comparison.csv').set_index('image_id')
    main=pd.read_csv(OUT/'stages/image_stage_onsets.csv')
    orders=[json.loads(line) for line in ORDERS.read_text(encoding='utf8').splitlines()]
    rows=[]
    for mode in MODES:
        base=OLD/mode/'no_imputation/affected_replay'
        members=pd.read_csv(base/'image_members.csv',dtype={'worker_id':str})
        images=members.image_id.unique()
        with gzip.open(base/'subset_partitions.csv.gz','rt',encoding='utf8',newline='') as stream:
            for (image,config),g in groupby(csv.DictReader(stream),key=lambda r:(r['image_id'],r['config'])):
                if config not in ('q_0.950','ospa30_t6'):
                    continue
                cache={int(r['subset_mask']):dict(status=r['status'],clusters=[set(s) for s in json.loads(r['clusters_positions_json'])]) for r in g}
                ms=members[members.image_id.eq(image)]
                n=int(inventory.loc[image,'common_n']); pos=dict(zip(ms.worker_id,ms.position))
                for h in (19,20,22,23,24):
                    if h>n: continue
                    counts=[Counter() for _ in range(h-5)]
                    for order in orders:
                        sequence=[pos[str(w)] for w in order['worker_ids'] if str(w) in pos][:h]
                        trajectory={}; mask=0
                        for k,p in enumerate(sequence,1):
                            mask|=1<<p; trajectory[k]=cache[mask]
                        values=anchored_states(trajectory,h)
                        for counter,state in zip(counts,stage_tail(list(values.values()))):
                            counter[state]+=1
                    lower=[c['stable']/200 for c in counts]
                    upper=[(c['stable']+c['unknown'])/200 for c in counts]
                    new=stage_onset(lower,upper)
                    original=main[(main.image_id==image)&(main['mode']==mode)&(main.config==config)&(main.horizon==h)&(main.kind=='anchor_stage')].iloc[0]
                    rows.append(dict(image_id=image,mode=mode,config=config,horizon=h,original_status=original.status,
                        original_possible=original.possible,original_conservative=original.conservative,
                        no_imputation_status=new[3],no_imputation_possible=new[0],no_imputation_conservative=new[1],
                        curve_bounds_json=json.dumps(list(zip(lower,upper)))))
    pd.DataFrame(rows).to_csv(OUT/'stages/no_imputation_sensitivity.csv',index=False)
    print(f'no-imputation sensitivity: {len(rows)} image/config/horizon rows',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['features','replay','no-imputation','onsets'])
    args=parser.parse_args()
    {'features':extract_features,'replay':replay_stages,'no-imputation':imputation_sensitivity,'onsets':write_onsets}[args.action]()
