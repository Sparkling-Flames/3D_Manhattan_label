"""共享x × 两种分区：保留原始点、既有资格、同房面板和有限池重放判据。"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import io
import json
from pathlib import Path
import sys
import types
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/shared_x_reanalysis_20260922'
ARCHIVE = ROOT / 'analysis_results/cluster_validation_received_20260922/Pro原始返回.zip'
PRESERVE = {'new_94_3635_7036_W037'}
CUT = 25.6
RULES = [(3, 2, .1), (3, 2, .2), (3, 3, .1), (2, 2, .1)]


def shared_x(points, links, preserve=False):
    p = np.array(points, dtype=float, copy=True)
    if preserve or links is None:
        return p
    links = np.asarray(links, int)
    if links.shape != (len(p)//2, 2) or sorted(links.ravel()) != list(range(len(p))):
        raise ValueError('共享x要求完整、不重复的上下配对')
    dx = (p[links[:, 1], 0] - p[links[:, 0], 0] + 512) % 1024 - 512
    if np.any(abs(dx) >= 512 - 1e-8):
        raise ValueError('对跖点无唯一周期中点')
    mid = (p[links[:, 0], 0] + dx/2) % 1024
    p[links[:, 0], 0] = p[links[:, 1], 0] = mid
    return p


def evaluate_sequence(labs, N, rule, h, compare):
    J, m, tail = rule
    counts = {k: np.unique(l, return_counts=True)[1] for k, l in labs.items()}
    support = {k: sum(sorted(co[co >= m], reverse=True)[:J])/k >= 1-tail-1e-10 for k, co in counts.items()}
    result = dict(endpoint_pass=bool(support[N]), observed_onset=None, reason='no_anchor_room')
    anchors = list(range(4, N-h+1))
    if not anchors:
        return result
    candidates = [k for k in anchors if all(support[n] for n in range(k, N+1))]
    if not candidates:
        return dict(result, reason='no_support_suffix')
    failures = set()
    for k in candidates:
        tv_bad = flip_bad = False
        for n in range(k+1, N+1):
            tv, flip = compare(labs[k], labs[n])
            tv_bad |= tv > .1 + 1e-10
            flip_bad |= flip > .05 + 1e-10
        if not tv_bad and not flip_bad:
            return dict(result, observed_onset=k, reason='success')
        if tv_bad:
            failures.add('share')
        if flip_bad:
            failures.add('membership')
    reason = 'both_drift' if len(failures) == 2 else next(iter(failures))+'_drift'
    return dict(result, reason=reason)


def residual_attribution(y0, p0, y1, p1):
    # 对绝对误差的两因素对称分解；只是数值归因，不是因果效应。
    e00, e10, e01, e11 = abs(y0-p0), abs(y1-p0), abs(y0-p1), abs(y1-p1)
    return dict(residual_change=(y1-p1)-(y0-p0), error_change=e11-e00,
                target_contribution=((e10-e00)+(e11-e01))/2,
                source_contribution=((e01-e00)+(e11-e10))/2)


def modules():
    with ZipFile(ARCHIVE) as z:
        def load(name, path):
            m = types.ModuleType(name)
            m.__file__ = str(ARCHIVE.parent / path)
            sys.modules[name] = m
            exec(compile(z.read(path), m.__file__, 'exec'), m.__dict__)
            return m
        c = load('core', 'code/core.py')
        common = load('shared_x_common', 'source/analysis_results/panorama_research_received_20260921/original_package/code/common.py')
        common.configure(ROOT)
        c.SOURCE = ROOT
        c.load = common.load
        return c, load('shared_x_affinity', 'code/02_partition.py'), load('shared_x_replay', 'code/06_consensus_replay.py'), load('shared_x_rooms', 'code/07_rooms_and_collection.py')


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, pd.DataFrame):
        data.to_csv(path, index=False)
    else:
        def clean(x):
            if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
            if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
            if isinstance(x, (np.integer,)): return int(x)
            if isinstance(x, (np.bool_,)): return bool(x)
            if isinstance(x, (float, np.floating)): return float(x) if np.isfinite(x) else None
            return x
        text = json.dumps(clean(data), ensure_ascii=False, allow_nan=False)
        if path.suffix == '.gz':
            with gzip.open(path, 'wt', encoding='utf8') as f: f.write(text)
        else:
            path.write_text(text+'\n', encoding='utf8')


def verify_raw(rows, ids):
    source_cache = {}
    checked = []
    for row in rows:
        cid = row['canonical_annotation_id']
        if cid not in ids: continue
        prov = row.get('provenance')
        path = prov['source'] if prov else row['raw_export_path']
        task_id = str(prov['task'] if prov else row['runtime_task_id'])
        annotation_id = str(prov['annotation'] if prov else row['raw_annotation_id'])
        if path not in source_cache:
            payload = json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
            if not isinstance(payload, list): raise ValueError('导出必须为任务数组：'+path)
            source_cache[path] = {(str(t['id']), str(a['id'])): a for t in payload for a in t.get('annotations', [])}
        ann = source_cache[path][task_id, annotation_id]
        points = [[v['value']['x']*1024/100, v['value']['y']*512/100] for v in ann['result'] if v['type'] == 'keypointlabels']
        np.testing.assert_allclose(points, row['raw_points_1024x512'], rtol=0, atol=1e-8, err_msg=cid)
        checked.append(dict(id=cid, source=path, task=task_id, annotation=annotation_id,
                            existing_processing=row['processing_status']))
    if {r['id'] for r in checked} != ids: raise ValueError('原始来源核验不完整')
    return checked


def partition_cached(c, ap, d, ids, method, cache):
    key = method+'|'+';'.join(ids)
    if key not in cache:
        if method == 'complete':
            lab, _ = c.part(d, ids, 'complete', CUT)
            info = dict(certified=True, solver='complete_linkage')
        else:
            lab, info = ap.affinity_partition(d, ids, CUT, 'quadratic', time_limit=30)
            if lab is None or not info['certified']:
                raise RuntimeError('未获最优证书：'+str(info))
        cache[key] = dict(labels=lab.tolist(), **info)
    return np.array(cache[key]['labels'])


def run_image(job):
    v, matrices, orders = job
    c, ap, replay, _ = modules()
    cid = v['image_id']
    path = OUT/'image_runs'/f'{cid}.json.gz'
    result = dict(image_id=cid, endpoint=[], memberships=[], per_order=[], prefixes=[], solutions={})
    for variant, matrix in matrices.items():
        d = np.array(matrix)
        cache = {}
        for method in ['complete', 'affinity']:
            base = dict(variant=variant, method=method, image_id=cid, code=v['code'], building=v['building'], N=v['N'])
            lab = partition_cached(c, ap, d, v['ids'], method, cache)
            st = c.stats(lab, d, CUT)
            co = np.unique(lab, return_counts=True)[1]
            a, b = np.triu_indices(v['N'], 1)
            weight = np.maximum(0, 1-d[a,b]/CUT)**2
            result['endpoint'].append(dict(**base, **{k: val for k,val in st.items() if k != 'N'},
                core3_mass=sum(sorted(co[co>=2], reverse=True)[:3])/v['N'],
                objective=float(sum(weight*(lab[a]==lab[b])))))
            result['memberships'].append(dict(**base, ids=v['ids'], workers=v['workers'], labels=lab.tolist()))
            if v['N'] < 8: continue  # 明示沿用原Pro N>=8面板，不将低人数记作失败。
            wix = {w: j for j,w in enumerate(v['workers'])}
            for oi, order in enumerate(orders):
                perm = [wix[w] for w in order if w in wix]
                labs = {}
                for k in range(4, v['N']+1):
                    ss = sorted(perm[:k])
                    ll = partition_cached(c, ap, d[np.ix_(ss, ss)], [v['ids'][j] for j in ss], method, cache)
                    lookup = dict(zip(ss,ll))
                    labs[k] = np.array([lookup[j] for j in perm[:k]])
                    co = np.unique(ll,return_counts=True)[1]
                    result['prefixes'].append(dict(**base, order=oi, k=k, K=len(co), counts=';'.join(map(str, sorted(co, reverse=True))),
                        singleton_share=sum(co==1)/k, core3_mass=sum(sorted(co[co>=2],reverse=True)[:3])/k))
                drift_cache = {}
                def compare(a, b):
                    key = (len(a),len(b))
                    if key not in drift_cache: drift_cache[key] = replay.compare_prefix(a,b)
                    return drift_cache[key]
                for J,m,tail in RULES:
                    for h in [3,5]:
                        result['per_order'].append(dict(**base, order=oi, J=J, m=m, tail_fraction=tail, h=h,
                            **evaluate_sequence(labs,v['N'],(J,m,tail),h,compare)))
        result['solutions'][variant] = cache
    save(path,result)
    return result


def prepare():
    c, _, _, _ = modules()
    data = c.load()
    rows, recs, views, reg, eligibility = data
    ids = {cid for v in views.values() for cid in v['ids']}
    verified = verify_raw(rows, ids | PRESERVE)
    assert not (ids & PRESERVE)
    assert len(ids) == 2444 and len(views) == 240
    points, processing = [], []
    changed = {}
    for row in rows:
        cid = row['canonical_annotation_id']
        if row['worker_id'] in {'W019','W026'} or not row['calculation_included']: continue
        r = recs.get(cid)
        links = None if r is None else r['links']
        p = np.array(row['effective_points_1024x512'],float)
        q = shared_x(p,links,preserve=cid in PRESERVE)
        status = 'human_preserve' if cid in PRESERVE else 'binding_unresolved' if links is None else 'shared_x'
        processing.append(dict(id=cid,image_id=row['image_id'],worker=row['worker_id'],condition=row['raw_condition'],
            prediction_included=cid in ids,status=status,pairing_source=None if r is None else r['audit'].get('pairing_source'),
            changed_points=int(np.any(abs(q-p)>1e-9,axis=1).sum()),pairs=0 if links is None else len(links)))
        points.append(dict(**processing[-1],raw_effective_points=p.tolist(),shared_x_points=q.tolist(),
            pairs_zero_based=None if links is None else links.tolist()))
        if cid in ids: changed[cid] = q[links]
    matrices = {'raw':{},'shared_x':{}}
    pair_changes = []
    for iid,v in views.items():
        raw = v['d']
        d = np.zeros_like(raw)
        for i in range(v['N']):
            for j in range(i):
                d[i,j] = d[j,i] = c.distance(changed[v['ids'][i]],changed[v['ids'][j]])[0]
                if (round(float(raw[i,j]),8)<=CUT) != (round(float(d[i,j]),8)<=CUT):
                    pair_changes.append(dict(image_id=iid,code=v['code'],id_a=v['ids'][i],id_b=v['ids'][j],
                        raw_distance=raw[i,j],shared_x_distance=d[i,j],direction='became_near' if d[i,j]<=CUT else 'became_far'))
        matrices['raw'][iid] = raw.tolist()
        matrices['shared_x'][iid] = d.tolist()
    workers = sorted({w for v in views.values() for w in v['workers']})
    rng = np.random.default_rng(c.SEED)
    orders = [rng.permutation(workers).tolist() for _ in range(80)]
    save(OUT/'raw_source_verification.json',verified)
    save(OUT/'point_processing.csv',pd.DataFrame(processing))
    save(OUT/'pointsets.json.gz',points)
    save(OUT/'distance_variants.json.gz',matrices)
    save(OUT/'pair_threshold_changes.csv',pd.DataFrame(pair_changes))
    save(OUT/'orders.json',orders)
    simple = {iid:{k:v[k] for k in ['image_id','code','building','ids','workers','N']} for iid,v in views.items()}
    save(OUT/'views.json',simple)
    manifest = dict(version='shared_x_reanalysis_20260922_v1',status='running',responses=2444,images=240,
        coordinate_rule='所有既有可绑定角对取周期平均x；没有0.2触发阈值；y/身份/点数/配对/环顺序不变',
        preserve_ids=sorted(PRESERVE),preserve_not_in_prediction_pool=True,
        binding_scope='既有人审绑定与唯一水平匹配条件绑定均保留；后者不是逐份人工核验',
        source='现有终审effective点和审核规则；2444计算作答及7036逐份对照原始导出raw点',
        raw_modified=False,cut=CUT,methods=['complete','affinity'],variants=['raw','shared_x'],
        replay=dict(images=sum(v['N']>=8 for v in views.values()),orders=80,min_k=4,h=[3,5],rules=RULES,
                    tv_max=.1,coassignment_flip_max=.05,comparison='起点对所有后续前缀；成功起点统计条件于成功顺序'),
        pairing_counts=Counter(r['pairing_source'] for r in processing if r['prediction_included']))
    save(OUT/'MANIFEST.json',manifest)
    return simple, matrices, orders


def summarize_images(results):
    endpoint = pd.DataFrame([r for x in results for r in x['endpoint']])
    per_order = pd.DataFrame([r for x in results for r in x['per_order']])
    prefixes = pd.DataFrame([r for x in results for r in x['prefixes']])
    save(OUT/'endpoint_per_image.csv',endpoint)
    save(OUT/'memberships.json',[r for x in results for r in x['memberships']])
    save(OUT/'replay_per_order.csv.gz',per_order)
    save(OUT/'replay_prefixes.csv.gz',prefixes)
    keys = ['variant','method','J','m','tail_fraction','h','image_id','code','building','N']
    records=[]
    for key,z in per_order.groupby(keys,sort=False):
        success=z.observed_onset.dropna()
        records.append(dict(zip(keys,key),orders=len(z),success_orders=len(success),success_fraction=len(success)/len(z),
            observed_onset_median_success_only=success.median(),onset_q10_success_only=success.quantile(.1),
            onset_q90_success_only=success.quantile(.9),endpoint_pass=bool(z.endpoint_pass.iloc[0]),
            reason_counts=json.dumps(z.reason.value_counts().to_dict())))
    images=pd.DataFrame(records)
    save(OUT/'replay_per_image.csv',images)
    keys=['variant','method','J','m','tail_fraction','h']
    records=[]
    for key,z in images.groupby(keys):
        records.append(dict(zip(keys,key),images=len(z),buildings=z.building.nunique(),endpoint_pass=int(z.endpoint_pass.sum()),
            images_any_success=int((z.success_fraction>0).sum()),images_ge80pct_orders=int((z.success_fraction>=.8).sum()),
            building_equal_success=z.groupby('building').success_fraction.mean().mean(),
            mean_success_fraction=z.success_fraction.mean()))
    save(OUT/'replay_summary.csv',pd.DataFrame(records))
    # 原始完整链接必须逐图复现旧版，不只核对一个汇总数字。
    with ZipFile(ARCHIVE) as z:
        old=pd.read_csv(io.BytesIO(z.read('results/consensus_replay_per_image.csv')))
    old=old[(old.variant=='raw')&(old.method=='complete')&(old.cut==CUT)]
    current=images[(images.variant=='raw')&(images.method=='complete')]
    key=['image_id','J','m','tail_fraction','h']
    joined=old.merge(current,on=key,validate='one_to_one',suffixes=('_old','_new'))
    assert len(joined)==len(old)==len(current)
    for field in ['success_fraction','observed_onset_median_success_only','endpoint_pass']:
        np.testing.assert_allclose(joined[field+'_old'],joined[field+'_new'],rtol=0,atol=1e-12,equal_nan=True)
    print('raw replay reproduced',len(joined),flush=True)


def run_rooms(condition):
    variant, method = condition
    c, ap, _, rooms = modules()
    data=c.load(); c.load=lambda:data
    with gzip.open(OUT/'distance_variants.json.gz','rt',encoding='utf8') as f: matrices=json.load(f)
    location=OUT/f'{variant}__{method}'
    location.mkdir(exist_ok=True)
    save(location/'distance_variants.json.gz',{variant:matrices[variant]})
    c.OUT=location
    rooms.SPECS=[(variant,CUT)]
    original=c.part
    cache={}
    calls=0
    def part(d,ids,kind='complete',cut=CUT):
        nonlocal calls
        assert kind=='complete' and cut==CUT
        key=tuple(ids)
        if key not in cache:
            if method=='complete': lab,_=original(d,ids,'complete',cut)
            else:
                lab,info=ap.affinity_partition(d,ids,cut,'quadratic',time_limit=30)
                if lab is None or not info['certified']: raise RuntimeError(str(info))
            cache[key]=lab;calls+=1
        return cache[key],[]
    c.part=part
    rooms.main()
    return dict(variant=variant,method=method,partitions=calls,all_certified=True)


def summarize_rooms():
    frames=[];summary=[]
    for variant in ['raw','shared_x']:
        for method in ['complete','affinity']:
            location=OUT/f'{variant}__{method}'
            p=pd.read_csv(location/'room_predictions_new.csv');p['method']=method;frames.append(p)
            for r in json.loads((location/'room_summary_new.json').read_text(encoding='utf8')):
                r['method']=method;summary.append(r)
    predictions=pd.concat(frames,ignore_index=True)
    save(OUT/'room_predictions.csv',predictions)
    save(OUT/'room_summary.json',summary)
    rows=[]
    for variant in ['raw','shared_x']:
        p=predictions[predictions.variant==variant]
        key=['image_id','metric','kind']
        z=p[p.method=='complete'].merge(p[p.method=='affinity'],on=key,suffixes=('_old','_new'),validate='one_to_one')
        for r in z.to_dict('records'):
            assert r['source_codes_old']==r['source_codes_new'] and r['N_old']==r['N_new']
            rows.append(dict(variant=variant,**{k:r[k] for k in key},code=r['code_old'],building=r['building_old'],family=r['family_old'],
                old_value=r['value_old'],new_value=r['value_new'],old_prediction=r['prediction_old'],new_prediction=r['prediction_new'],
                source_codes=r['source_codes_old'],**residual_attribution(r['value_old'],r['prediction_old'],r['value_new'],r['prediction_new'])))
    attribution=pd.DataFrame(rows)
    invariant=attribution[attribution.metric=='pair_disagreement']
    assert (invariant.error_change==0).all()
    save(OUT/'room_error_attribution.csv',attribution)
    records=[]
    for key,z in attribution.groupby(['variant','metric','kind']):
        b=z.groupby(['building','family'])[['error_change','target_contribution','source_contribution']].mean().groupby('building').mean()
        rng=np.random.default_rng(20260922)
        ci=np.quantile(rng.choice(b.error_change.to_numpy(),(3000,len(b)),replace=True).mean(1),[.025,.975])
        records.append(dict(variant=key[0],metric=key[1],kind=key[2],images=len(z),buildings=len(b),
            **b.mean().to_dict(),conditional_delta_low=ci[0],conditional_delta_high=ci[1]))
    save(OUT/'room_method_comparison.csv',pd.DataFrame(records))


def dominant_tail_diagnostics():
    endpoint=pd.read_csv(OUT/'endpoint_per_image.csv').query('N>=8')
    replay=pd.read_csv(OUT/'replay_per_image.csv').query('J==3 and m==2')
    rows=[]
    for variant in ['raw','shared_x']:
        for method in ['complete','affinity']:
            ep=endpoint[(endpoint.variant==variant)&(endpoint.method==method)]
            rr=replay[(replay.variant==variant)&(replay.method==method)]
            for h in [3,5]:
                a=rr[(rr.h==h)&(rr.tail_fraction==.1)].set_index('image_id')
                b=rr[(rr.h==h)&(rr.tail_fraction==.2)].set_index('image_id')
                for r in ep.to_dict('records'):
                    iid=r['image_id']
                    rows.append(dict(variant=variant,method=method,image_id=iid,code=r['code'],building=r['building'],N=r['N'],h=h,
                        counts=r['counts'],largest_share=r['largest_share'],singleton_share=r['singleton_share'],core3_mass=r['core3_mass'],
                        dominant80_probe=r['largest_share']>=.8-1e-10,
                        dominant_but_fails90=r['largest_share']>=.8-1e-10 and r['core3_mass']<.9-1e-10,
                        endpoint_pass80=r['core3_mass']>=.8-1e-10,endpoint_pass90=r['core3_mass']>=.9-1e-10,
                        success_fraction80=b.loc[iid,'success_fraction'],success_fraction90=a.loc[iid,'success_fraction'],
                        onset80_success_only=b.loc[iid,'observed_onset_median_success_only'],onset90_success_only=a.loc[iid,'observed_onset_median_success_only'],
                        passes80pct_orders_only_under80=b.loc[iid,'success_fraction']>=.8 and a.loc[iid,'success_fraction']<.8,
                        reason_counts80=b.loc[iid,'reason_counts'],reason_counts90=a.loc[iid,'reason_counts']))
    frame=pd.DataFrame(rows)
    save(OUT/'dominant_tail_per_image.csv',frame)
    records=[]
    for key,z in frame.groupby(['variant','method','h']):
        records.append(dict(variant=key[0],method=key[1],h=key[2],images=len(z),
            dominant80_images=int(z.dominant80_probe.sum()),dominant_but_fails90_images=int(z.dominant_but_fails90.sum()),
            endpoint_pass80=int(z.endpoint_pass80.sum()),endpoint_pass90=int(z.endpoint_pass90.sum()),
            images_ge80pct_orders_under80=int((z.success_fraction80>=.8).sum()),
            images_ge80pct_orders_under90=int((z.success_fraction90>=.8).sum()),
            images_passing_only_under80=int(z.passes80pct_orders_only_under80.sum()),
            dominant_but_under80_orders_unresolved=int((z.dominant80_probe & (z.success_fraction80<.8)).sum())))
    save(OUT/'dominant_tail_summary.csv',pd.DataFrame(records))
    print('DOMINANT/TAIL DIAGNOSTICS\n'+pd.DataFrame(records).to_string(index=False))


def diagnose():
    endpoint=pd.read_csv(OUT/'endpoint_per_image.csv')
    orders=pd.read_csv(OUT/'replay_per_order.csv.gz')
    image_summary=pd.read_csv(OUT/'replay_per_image.csv')
    image_summary['no_anchor_room']=image_summary.N-image_summary.h<4
    image_summary['observation_status']=np.where(image_summary.no_anchor_room,'no_anchor_room',
        np.where(image_summary.success_fraction>=.8,'ge80pct_orders',
                 np.where(image_summary.success_fraction>0,'some_orders_only','no_onset_under_rule')))
    save(OUT/'replay_per_image.csv',image_summary)
    summary=pd.read_csv(OUT/'replay_summary.csv')
    key=['variant','method','J','m','tail_fraction','h']
    eligibility=image_summary.groupby(key).agg(no_observation_room=('no_anchor_room','sum')).reset_index()
    summary=summary.drop(columns=['no_observation_room','images_with_anchor_room'],errors='ignore').merge(eligibility,on=key,validate='one_to_one')
    summary['images_with_anchor_room']=summary.images-summary.no_observation_room
    save(OUT/'replay_summary.csv',summary)
    memberships=json.loads((OUT/'memberships.json').read_text(encoding='utf8'))
    with gzip.open(OUT/'distance_variants.json.gz','rt',encoding='utf8') as f: matrices=json.load(f)
    summaries=[]
    for (variant,method),z in endpoint[endpoint.N>=8].groupby(['variant','method']):
        forced=0
        for iid in z.image_id:
            d=np.round(np.array(matrices[variant][iid]),8)
            near=d<=CUT;np.fill_diagonal(near,False)
            forced+=int((near.sum(1)==0).sum())
        summaries.append(dict(variant=variant,method=method,images=len(z),responses=int(z.N.sum()),
            singleton_responses=int(z.singletons.sum()),near_split=int(z.near_split.sum()),
            endpoint_few90=int(z.few_J3_m2_s10.sum()),mean_K=z.K.mean(),
            mean_singleton_share=z.singleton_share.mean(),mean_core3_mass=z.core3_mass.mean(),
            mean_largest_share=z.largest_share.mean(),forced_singleton_responses=forced))
    save(OUT/'endpoint_summary.csv',pd.DataFrame(summaries))
    membermap={(r['variant'],r['method'],r['image_id']):r for r in memberships}
    changes=[]
    for variant in ['raw','shared_x']:
        for iid,dm in matrices[variant].items():
            a=membermap[variant,'complete',iid];b=membermap[variant,'affinity',iid]
            assert a['ids']==b['ids']
            old,new=np.array(a['labels']),np.array(b['labels']);d=np.array(dm)
            if np.array_equal(old[:,None]==old, new[:,None]==new): continue
            old_sizes=Counter(old);new_sizes=Counter(new)
            lost=[cid for j,cid in enumerate(a['ids']) if old_sizes[old[j]]>=2 and new_sizes[new[j]]==1]
            gained=[cid for j,cid in enumerate(a['ids']) if old_sizes[old[j]]==1 and new_sizes[new[j]]>=2]
            near=np.round(d,8)<=CUT;np.fill_diagonal(near,False)
            aa,bb=np.triu_indices(a['N'],1)
            weight=np.maximum(0,1-np.round(d[aa,bb],8)/CUT)**2
            objective_gain=float(sum(weight*((new[aa]==new[bb]).astype(int)-(old[aa]==old[bb]).astype(int))))
            if objective_gain < -1e-7: raise AssertionError('新分区目标劣于可行旧分区')
            entry={k:a[k] for k in ['variant','image_id','code','building','N','ids','workers']}
            entry.update(old_counts=sorted(old_sizes.values(),reverse=True),new_counts=sorted(new_sizes.values(),reverse=True),
                old_labels=old.tolist(),new_labels=new.tolist(),lost_repeated_support_ids=lost,gained_repeated_support_ids=gained,
                forced_singletons=int((near.sum(1)==0).sum()),objective_gain=objective_gain)
            changes.append(entry)
    save(OUT/'partition_changes.json',changes)
    transitions=[]
    key=['image_id','order','J','m','tail_fraction','h']
    comparisons=[('method_raw',('raw','complete'),('raw','affinity')),
                 ('method_shared_x',('shared_x','complete'),('shared_x','affinity')),
                 ('coordinates_complete',('raw','complete'),('shared_x','complete')),
                 ('coordinates_affinity',('raw','affinity'),('shared_x','affinity'))]
    for name,(v0,m0),(v1,m1) in comparisons:
        a=orders[(orders.variant==v0)&(orders.method==m0)]
        b=orders[(orders.variant==v1)&(orders.method==m1)]
        z=a.merge(b,on=key,validate='one_to_one',suffixes=('_old','_new'))
        assert len(z)==len(a)==len(b)
        z['transition']=np.select([z.observed_onset_old.notna()&z.observed_onset_new.isna(),
                                  z.observed_onset_old.isna()&z.observed_onset_new.notna(),
                                  z.observed_onset_old.notna()&z.observed_onset_new.notna()],
                                 ['lost','gained','both_success'],default='neither')
        z['comparison']=name
        transitions.append(z[['comparison',*key,'code_old','building_old','N_old','transition',
                              'reason_old','reason_new','observed_onset_old','observed_onset_new']])
    transition=pd.concat(transitions,ignore_index=True)
    save(OUT/'replay_transitions.csv.gz',transition)
    group=['comparison','J','m','tail_fraction','h','transition','reason_old','reason_new']
    save(OUT/'replay_transition_counts.csv',transition.groupby(group).size().rename('image_order_count').reset_index())
    comparison_rows=[]
    for name,(v0,m0),(v1,m1) in comparisons:
        aa=image_summary[(image_summary.variant==v0)&(image_summary.method==m0)]
        bb=image_summary[(image_summary.variant==v1)&(image_summary.method==m1)]
        z=aa.merge(bb,on=['image_id','J','m','tail_fraction','h'],validate='one_to_one',suffixes=('_old','_new'))
        z['delta']=z.success_fraction_new-z.success_fraction_old
        for key,g in z.groupby(['J','m','tail_fraction','h']):
            b=g.groupby('building_old').delta.mean()
            rng=np.random.default_rng(20260922)
            ci=np.quantile(rng.choice(b.to_numpy(),(3000,len(b)),replace=True).mean(1),[.025,.975])
            comparison_rows.append(dict(comparison=name,J=key[0],m=key[1],tail_fraction=key[2],h=key[3],
                images=len(g),buildings=len(b),building_equal_delta=b.mean(),conditional_low=ci[0],conditional_high=ci[1],
                improved_images=int((g.delta>1e-10).sum()),worsened_images=int((g.delta< -1e-10).sum())))
    save(OUT/'replay_method_comparison.csv',pd.DataFrame(comparison_rows))
    attribution=pd.read_csv(OUT/'room_error_attribution.csv')
    weighted=[]
    for key,z in attribution.groupby(['variant','metric','kind']):
        z=z.copy()
        nf=z.groupby('building').family.nunique();nb=z.building.nunique()
        ni=z.groupby(['building','family']).image_id.transform('size')
        z['aggregation_weight']=1/(nb*z.building.map(nf)*ni)
        assert np.isclose(z.aggregation_weight.sum(),1)
        z['weighted_error_change']=z.aggregation_weight*z.error_change
        weighted.append(z)
    save(OUT/'room_error_attribution.csv',pd.concat(weighted,ignore_index=True))
    # 原始同房结果须与之前发布一致，包括全局候选；允许浮点尾差，不吞面板变化。
    old=pd.read_csv(ROOT/'analysis_results/room_partition_comparison_20260922/paired_predictions.csv')
    pr=pd.read_csv(OUT/'room_predictions.csv')
    for method,suffix in [('complete','old'),('affinity','new')]:
        current=pr[(pr.variant=='raw')&(pr.method==method)]
        z=old.merge(current,on=['variant','cut','metric','kind','image_id'],validate='one_to_one')
        assert len(z)==len(old)==len(current)
        for field in ['value','prediction','outside_baseline','otherroom_baseline']:
            np.testing.assert_allclose(z[field+'_'+suffix],z[field],rtol=0,atol=1e-10,equal_nan=True)
    report=dict(raw_room_both_methods_reproduced=True,point_processing=pd.read_csv(OUT/'point_processing.csv').status.value_counts().to_dict(),
                partition_changed_images={v:sum(r['variant']==v for r in changes) for v in ['raw','shared_x']},
                interpretation='目标/来源分解是代数归因，不是外部真值上的准确性或因果识别；重放次数不是独立人员')
    save(OUT/'DIAGNOSTIC_CHECKS.json',report)
    dominant_tail_diagnostics()
    print(pd.DataFrame(summaries).to_string(index=False))
    print(pd.read_csv(OUT/'replay_summary.csv').query('J==3 and m==2 and tail_fraction==0.1').to_string(index=False))
    print(pd.read_csv(OUT/'room_method_comparison.csv').to_string(index=False))


def main(jobs):
    views,matrices,orders=prepare()
    work=[(v,{k:dd[iid] for k,dd in matrices.items()},orders) for iid,v in views.items()]
    work.sort(key=lambda x:-x[0]['N'])
    results=[]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for future in as_completed([pool.submit(run_image,w) for w in work]):
            r=future.result();results.append(r)
            print('image done',len(results),'/240',r['image_id'],flush=True)
    summarize_images(results)
    with ProcessPoolExecutor(max_workers=min(jobs,4)) as pool:
        certificates=list(pool.map(run_rooms,[(v,m) for v in ['raw','shared_x'] for m in ['complete','affinity']]))
    summarize_rooms()
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf8'))
    manifest.update(status='complete',room_solver_checks=certificates,raw_complete_replay_reproduced=True,
                    all_affinity_solutions_certified=True)
    save(OUT/'MANIFEST.json',manifest)
    print('COMPLETED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    main(args.jobs)
