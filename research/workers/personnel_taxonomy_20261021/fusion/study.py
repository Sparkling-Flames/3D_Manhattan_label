"""Frozen-label personnel substitutions with the repository's existing fusion.

New requests are selected from metadata and class capacity, before outcomes.
The separate common-library branch relabels previously saved endpoint pairs.
No preprocessing, reference, correspondence, voting or scoring code is changed.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
sys.path.append('/tmp/hohonet_deps')
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TAX = OUT.parent
FUSION = ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
COMP = ROOT / 'research/workers/personnel_interchangeability_20261020/analysis/composition'
CORNER = ROOT / 'research/workers/personnel_interchangeability_followup_20261020/audit_corner'
LABELS = TAX / 'route_b/lobo_labels.csv'
SEED = 2026102117


def read(path):
    path = Path(path)
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        return json.load(f)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(clean(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def csv(path, frame):
    frame.to_csv(path, index=False, encoding='utf-8', lineterminator='\n',
                 compression={'method': 'gzip', 'mtime': 0} if str(path).endswith('.gz') else None)


def digest(v):
    return hashlib.sha256(json.dumps(clean(v), sort_keys=True).encode()).hexdigest()


def rng(v):
    return np.random.default_rng(int(digest([SEED, v])[:16], 16))


def label_maps(path=LABELS):
    data = pd.read_csv(path, keep_default_na=False)
    result = {}
    for (condition, building), g in data.groupby(['condition', 'heldout_building']):
        result[condition, building] = {
            row.worker_id: {'coarse': row.coarse_class, 'fine': row.fine_class}
            for row in g.itertuples()
            if row.coarse_class not in ('', 'unknown', 'unassigned', 'insufficient_evidence')
        }
    return result


def counts(ws, labels, tier):
    return dict(sorted(Counter(labels[w][tier] for w in ws).items()))


def setup_engine():
    os.environ['PERSONNEL_V2_REPOSITORY'] = str(ROOT)
    sys.path[:0] = [str(ROOT), str(FUSION), str(COMP), str(CORNER)]
    import fusion_engine as fe
    import fusion_runner as fr
    import summarize_grid as sg
    from corner_distance import corner_compare
    from tools.thesis_main.analysis.fusion_change_mechanisms_20261020 import step_mechanisms, normalized_state
    fr.FE = fe
    return fe, fr, sg, corner_compare, step_mechanisms, normalized_state


def draw_blocks(pool, labels, tier, c, d, n, m, repeat):
    """Disjoint pure blocks; exchanged source-origin counts match exactly."""
    by = {r['worker_id']: r for r in pool['records'] if r['worker_id'] in labels}
    ca = [w for w in by if labels[w][tier] == c]
    cb = [w for w in by if labels[w][tier] == d]
    valid_origins = []
    for new_n in range(m + 1):
        need = {'new': new_n, 'v1': m - new_n}
        if all(sum(by[w]['origin'] == o for w in ca) >= 2 * k and
               sum(by[w]['origin'] == o for w in cb) >= k for o, k in need.items()):
            valid_origins.append(need)
    if not valid_origins:
        return None, 'no_two_disjoint_same_class_blocks_with_matched_source'
    if len(by) < n + 2 * m:
        return None, 'insufficient_workers_for_three_disjoint_blocks_and_core'
    rr = rng([pool['pool_id'], tier, c, d, n, m, repeat])
    need = valid_origins[int(rr.integers(len(valid_origins)))]
    aa, bb, cc = [], [], []
    for origin, k in need.items():
        x = sorted(w for w in ca if by[w]['origin'] == origin)
        y = sorted(w for w in cb if by[w]['origin'] == origin)
        if k:
            draw = rr.choice(x, size=2*k, replace=False).tolist()
            aa.extend(draw[:k]); bb.extend(draw[k:]); cc.extend(rr.choice(y, size=k, replace=False).tolist())
    reserve = sorted(set(by) - set(aa + bb + cc))
    core = rr.choice(reserve, size=n-m, replace=False).tolist()
    return dict(core_workers=sorted(core), A_workers=sorted(core+aa), B_workers=sorted(core+bb),
                C_workers=sorted(core+cc), A_block=sorted(aa), B_block=sorted(bb), C_block=sorted(cc),
                block_origin_counts=need), None


def validate(e, labels):
    aa, bb, cc = (set(e[x + '_workers']) for x in 'ABC')
    core = set(e['core_workers'])
    assert aa & bb == aa & cc == bb & cc == core
    assert all(len(x) == e['n'] for x in (aa, bb, cc))
    assert len(aa-bb) == len(aa-cc) == e['m']
    assert counts(aa, labels, e['design_tier']) == counts(bb, labels, e['design_tier'])
    assert counts(aa, labels, e['design_tier']) != counts(cc, labels, e['design_tier'])


def prepare():
    pools = read(FUSION / 'INPUT_SNAPSHOT.json.gz')['images']
    maps = label_maps()
    selected = {}
    for p in pools:
        meta = p['meta']
        if meta['layer'] == 'ordinary_manual':
            k = (meta['layer'], meta['building'], meta['difficulty'])
            if k not in selected or digest(p['pool_id']) < digest(selected[k]['pool_id']):
                selected[k] = p
        else:
            selected[meta['layer'], p['pool_id']] = p
    panel = sorted(selected.values(), key=lambda p:p['pool_id'])
    events, capacity = [], []
    for p in panel:
        meta = p['meta']; labels = maps.get((meta['condition'], meta['building']), {})
        available = [r['worker_id'] for r in p['records'] if r['worker_id'] in labels]
        for tier in ('coarse', 'fine'):
            cs = sorted({labels[w][tier] for w in available} - {''})
            parents = {labels[w]['fine']: labels[w]['coarse'] for w in available}
            directions = [(c, d) for c in cs for d in cs if c != d and
                          (tier == 'coarse' or parents[c] == parents[d])]
            # Fine experiments specifically test within-coarse distinctions.
            for n, m, repeats in [(5, 1, 2), (9, 2, 1), (13, 3, 1)]:
                for c, d in directions:
                    for repeat in range(repeats):
                        blocks, reason = draw_blocks(p, labels, tier, c, d, n, m, repeat)
                        row = dict(pool_id=p['pool_id'], image=meta['image'], building=meta['building'],
                                   condition=meta['condition'], layer=meta['layer'], difficulty=meta['difficulty'],
                                   design_tier=tier, n=n, m=m, repeat=repeat, outgoing_class=c, incoming_class=d,
                                   available_workers=len(available), reason=reason)
                        capacity.append(dict(row, feasible=blocks is not None))
                        if blocks is None:
                            continue
                        e = dict(row, **blocks)
                        e['event_id'] = 'TX_' + digest(e)[:22]
                        validate(e, labels)
                        events.append(e)
    save(OUT/'REQUESTS.json.gz', dict(events=events))
    csv(OUT/'DESIGN_CAPACITY.csv', pd.DataFrame(capacity))
    csv(OUT/'SELECTED_POOLS.csv', pd.DataFrame([p['meta'] for p in panel]))
    save(OUT/'REGISTRATION.json', dict(seed=SEED, label_source=str(LABELS.relative_to(ROOT)),
        labels_sha256=hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        status='requests_frozen_before_new_fusion', selected_pools=len(panel), events=len(events),
        design='Manual one minimum stable-hash pool per building x difficulty; all Semi/doorway/special pools; exact source-matched blocks, no outcome selection',
        tiers='coarse directions and fine sibling directions; both tiers relabel all results',
        sizes=[{'n':5,'m':1,'repeats':2},{'n':9,'m':2,'repeats':1},{'n':13,'m':3,'repeats':1}],
        qualification='Existing quality-usable independent-voter same-image/condition/reference pools only',
        boundary='Internal v2 followup; held-out-building labels, existing research images; not external blind validation',
        fusion_gap=7.5, voting='MV50; even half-votes retained', location='median',
        scoring='B8L2 primary, D10 sensitivity', N1_applied=False))
    print('Prepared', len(events), 'ABC events,', len(panel), 'metadata-selected pools', flush=True)


def compare(a, b, sg, corner_compare):
    basic = sg.pair_metrics(a, b)
    corner, _ = corner_compare(a, b)
    fields = ['turnover','abs_B8L2_change','abs_D10_change','B8L2_change','D10_change',
              'floor_jaccard_difference','node_count_change','node_count_difference',
              'both_complete','joint_stable_main','joint_stable_wide','structure_bound_cyclic_deg']
    out = {k:basic.get(k) for k in fields}
    out.update({k:corner.get(k) for k in ('status','bev_mean_h','bev_max_h','top_mean_h','top_max_h',
                                        'angle_deg','same_count','complete')})
    out['different_count'] = bool(corner.get('status') == 'different_corner_count')
    out['valid_distance'] = corner.get('status') == 'unique_cyclic_candidate'
    out['unavailable_geometry'] = not out['valid_distance'] and not out['different_count']
    return out


def run_pool(pool, events, labels):
    fe, fr, sg, corners, step, normalize = setup_engine()
    started = time.monotonic()
    path = OUT/'runtime'/(pool['pool_id'] + '.json.gz')
    # This small cache contains our registered final endpoints and scalar events.
    # Original full-state caches are intentionally not hydrated or altered.
    if path.exists():
        old = read(path)
        if old['event_ids'] == [e['event_id'] for e in events]:
            return {'pool_id': pool['pool_id'], 'new':0, 'events':len(events), 'cached':True}
    teams, states, rows = {}, {}, []
    keep_states = {}
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE/'measurement_engine.zip', fe.ENGINE/'working_models.py') as (engine, models):
        for e in events:
            validate(e, labels)
            keys = {}
            for arm in 'ABC':
                key = fr.team_key(pool['pool_id'], e[arm+'_workers']); keys[arm] = key
                if key not in teams:
                    result = fr.evaluate_one(pool, e[arm+'_workers'], engine, models, full_state=True)
                    states[key] = normalize(result.pop('full_state')) if 'full_state' in result else None
                    result['type_counts'] = {tier:counts(result['member_workers'],labels,tier) for tier in ('coarse','fine')}
                    teams[key] = result
            row = dict(e, **{arm+'_team_key':key for arm,key in keys.items()})
            for arm in 'ABC':
                for field in ('B8L2','D10','nodes','omission','extension','Hmean','dir','S_bottom_deg','score_status',
                              'complete_evaluable','ref_node_recall_5','ref_edge_recall_5'):
                    row[arm+'_'+field] = teams[keys[arm]].get(field)
            for arm, name in [('B','within'),('C','cross')]:
                aa, bb = teams[keys['A']], teams[keys[arm]]
                row.update({name+'_'+k:v for k,v in compare(aa,bb,sg,corners).items()})
                if states[keys['A']] is not None and states[keys[arm]] is not None:
                    mech = step(states[keys['A']],states[keys[arm]],set(e['core_workers']))
                    mech.pop('group_components')
                    row.update({name+'_'+k:v for k,v in mech.items()})
                for tier in ('coarse','fine'):
                    row[name+'_'+tier+'_same_counts'] = aa['type_counts'][tier] == bb['type_counts'][tier]
            for field in ('B8L2','D10','nodes','omission','extension','ref_node_recall_5'):
                x,y=row.get('B_'+field),row.get('C_'+field)
                row['net_'+field] = y-x if x is not None and y is not None else None
            rows.append(row)
            # Save designated mechanisms only; case metadata was selected before outcomes.
            if pool['meta']['image'] in ('jtcxE69GiFV-26','UwV83HsGsw3-22','q9vSo1VnCiC-30'):
                if e['n']==5 and e['repeat']==0:
                    keep_states.update({keys[a]:states[keys[a]] for a in 'ABC'})
    save(path, dict(event_ids=[e['event_id'] for e in events], teams=teams, events=rows, selected_states=keep_states))
    return dict(pool_id=pool['pool_id'],new=len(teams),events=len(events),cached=False,seconds=time.monotonic()-started)


def run(jobs):
    pools = {p['pool_id']:p for p in read(FUSION/'INPUT_SNAPSHOT.json.gz')['images']}
    maps = label_maps()
    requests = read(OUT/'REQUESTS.json.gz')['events']
    grouped = defaultdict(list)
    for e in requests:
        grouped[e['pool_id']].append(e)
    receipts = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        fs = {ex.submit(run_pool,pools[pid],es,maps[pools[pid]['meta']['condition'],pools[pid]['meta']['building']]):pid
              for pid,es in grouped.items()}
        for f in as_completed(fs):
            r=f.result();receipts.append(r);print(dict(r,done=len(receipts),total=len(fs)),flush=True)
    save(OUT/'RUN_RECEIPT.json',dict(pools=receipts,new_teams=sum(r['new'] for r in receipts)))
    allteams, allevents, selectedstates = {}, [], {}
    for pid in grouped:
        r=read(OUT/'runtime'/(pid+'.json.gz'))
        allteams.update(r['teams']);allevents.extend(r['events']);selectedstates.update(r['selected_states'])
    save(OUT/'TEAMS.json.gz',allteams)
    save(OUT/'SELECTED_STATES.json.gz',selectedstates)
    csv(OUT/'EVENTS.csv.gz',pd.DataFrame(allevents))
    print('Saved',len(allteams),'final teams,',len(allevents),'ABC events',flush=True)


def summarize_events():
    data=pd.read_csv(OUT/'EVENTS.csv.gz')
    shared_distance=data.within_valid_distance & data.cross_valid_distance
    data['common_distance_pair']=shared_distance.astype(int)
    for arm in ('within','cross'):
        for metric in ('bev_mean_h','bev_max_h','top_mean_h','top_max_h'):
            data[arm+'_'+metric+'_common']=data[arm+'_'+metric].where(shared_distance)
    metrics=['net_B8L2','net_D10','net_nodes','net_omission','net_extension','net_ref_node_recall_5']
    for arm in ('within','cross'):
        metrics += [arm+'_'+f for f in ('abs_B8L2_change','abs_D10_change','floor_jaccard_difference',
            'node_count_difference','both_complete','joint_stable_main','bev_mean_h','bev_max_h','top_mean_h',
            'different_count','valid_distance','unavailable_geometry','retained_partition_changed','new_vote_gains')]
        metrics += [arm+'_'+metric+'_common' for metric in ('bev_mean_h','bev_max_h','top_mean_h','top_max_h')]
    metrics += ['common_distance_pair']
    keys=['condition','layer','design_tier','outgoing_class','incoming_class','n','m']
    rows=[]
    perimage=data.groupby(keys+['building','image'])[metrics].mean().reset_index()
    perbuilding=perimage.groupby(keys+['building'])[metrics].mean().reset_index()
    for key,g in data.groupby(keys):
        x=perbuilding
        for k,v in zip(keys,key):x=x[x[k]==v]
        row=dict(zip(keys,key));row.update(events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
                                          scored_events=int(g.net_B8L2.notna().sum()),
                                          common_distance_events=int(g.common_distance_pair.sum()),
                                          positive_events=int((g.net_B8L2>0).sum()),negative_events=int((g.net_B8L2<0).sum()))
        row.update({m:x[m].mean() for m in metrics})
        v=x.net_B8L2.dropna().to_numpy()
        if len(v)>=3:
            boot=rng(['building_bootstrap',key]).choice(v,size=(2000,len(v)),replace=True).mean(axis=1)
            row['net_B8L2_building_boot_lo'],row['net_B8L2_building_boot_hi']=np.quantile(boot,[.025,.975])
            row['positive_buildings']=int((v>0).sum());row['negative_buildings']=int((v<0).sum())
        rows.append(row)
    csv(OUT/'SUMMARY.csv',pd.DataFrame(rows))
    csv(OUT/'PER_IMAGE.csv',perimage);csv(OUT/'PER_BUILDING.csv',perbuilding)
    # Same events, two hierarchy levels. Exact count vectors determine the label.
    pairrows=[]
    for e in data.to_dict('records'):
        for arm in ('within','cross'):
            for tier in ('coarse','fine'):
                row={k:e[k] for k in ['event_id','pool_id','image','building','condition','layer','difficulty','n','m','design_tier']}
                row.update(tier=tier,arm='same_composition' if e[arm+'_'+tier+'_same_counts'] else 'different_composition',original_arm=arm)
                row.update({k:e.get(arm+'_'+k) for k in ['bev_mean_h','top_mean_h','different_count','valid_distance',
                   'unavailable_geometry','floor_jaccard_difference','abs_B8L2_change','abs_D10_change','joint_stable_main']})
                pairrows.append(row)
    csv(OUT/'HIERARCHY_PAIR_VALUES.csv.gz',pd.DataFrame(pairrows))


def common_library():
    source=CORNER/'common_library/COMMON_ENDPOINT_PAIRS.csv.gz'
    keep=['anchor_id','pool_id','image','image_id','building','n','m','replicate','pair_id','A_team_key','B_team_key',
          'left_workers','right_workers','status','bev_mean_h','bev_max_h','top_mean_h','top_max_h','angle_deg',
          'valid_distance','different_count','missing_geometry','noncomplete']
    data=pd.read_csv(source,usecols=keep)
    maps=label_maps()
    rows=[]
    for e in data.to_dict('records'):
        labels=maps.get(('manual',e['building']),{})
        left=e['left_workers'].split('|');right=e['right_workers'].split('|')
        for tier in ('coarse','fine'):
            if not all(w in labels and labels[w][tier] for w in left+right):continue
            ca,cb=counts(left,labels,tier),counts(right,labels,tier)
            rows.append(dict(e,tier=tier,arm='same_composition' if ca==cb else 'different_composition',
                             left_class_counts=json.dumps(ca),right_class_counts=json.dumps(cb)))
    result=pd.DataFrame(rows);csv(OUT/'REUSED_COMMON_ENDPOINT_LABELS.csv.gz',result)
    metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','valid_distance','different_count','missing_geometry','noncomplete']
    summaries=[];anchorrows=[]
    for (tier,n,m),g in result.groupby(['tier','n','m']):
        for metric in metrics:
            sub=g[g[metric].notna()]
            arms=sub.groupby('anchor_id').arm.nunique()
            anchors=arms[arms==2].index
            sub=sub[sub.anchor_id.isin(anchors)]
            a=sub.groupby(['anchor_id','image','building','arm'])[metric].mean().reset_index()
            a['tier']=tier;a['n']=n;a['m']=m;a['metric']=metric;a=a.rename(columns={metric:'value'})
            anchorrows.extend(a.to_dict('records'))
            agg=a.groupby(['building','image','arm']).value.mean().groupby(['building','arm']).mean().groupby('arm').mean()
            summaries.append(dict(tier=tier,n=n,m=m,metric=metric,common_anchors=len(anchors),images=sub.image.nunique(),
                buildings=sub.building.nunique(),pairs=len(sub),same_composition=agg.get('same_composition'),
                different_composition=agg.get('different_composition'),
                cross_minus_same=agg.get('different_composition',np.nan)-agg.get('same_composition',np.nan)))
    csv(OUT/'REUSED_COMMON_SUMMARY.csv',pd.DataFrame(summaries))
    csv(OUT/'REUSED_COMMON_ANCHOR_VALUES.csv.gz',pd.DataFrame(anchorrows))
    save(OUT/'REUSED_COMMON_RECEIPT.json',dict(source=str(source.relative_to(ROOT)),source_pairs=len(data),
        source_images=int(data.image.nunique()),source_buildings=int(data.building.nunique()),geometry_recomputed=False,
        labels='new leave-one-building-out route B; independent Manual labels only',
        historical_design='152 metadata-selected common background libraries; original K3/Rnew2 work; n=5/9/13/17,m=2/5; disjoint blocks',
        estimand='paired endpoint displacement conditional on metric-specific anchors with both same/different class composition',
        aggregation='pair mean within anchor -> image equal -> building equal',
        boundary='Relabelled historical endpoint evidence; neither new images nor independent validation of earlier selection'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run','summarize','common'])
    parser.add_argument('--jobs',type=int,default=4)
    a=parser.parse_args()
    {'prepare':prepare,'run':lambda:run(a.jobs),'summarize':summarize_events,'common':common_library}[a.stage]()


if __name__=='__main__':main()
