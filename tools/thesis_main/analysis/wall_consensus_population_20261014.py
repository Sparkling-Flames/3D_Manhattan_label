"""冻结墙线方法的有限池人数过程；只用当前子集重新对应，不调用人审或质量调参。"""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import itertools
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from .consensus_delivery_20261008 import fuse, WORKING_GAP
from .research_artifact_io import ROOT, write_json, write_csv
from .research_round_20260929 import prepare_record, reconstruct

OUT = ROOT / 'research/wall_consensus_population_20261014'
SEED = 20261014
REPEATS = 24


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def automatic_prefixes(records, workers, cache=None):
    """缓存键是当前成员集合；不传入全员身份、人审分区或人工顺序。"""
    lookup = {r['worker']:r for r in records}
    if len(lookup) != len(records) or set(workers) != set(lookup) or len(workers) != len(lookup):
        raise ValueError('worker_order_must_cover_pool_once')
    cache = {} if cache is None else cache
    path = []
    for k in range(1, len(workers)+1):
        key = tuple(sorted(workers[:k]))
        if key not in cache:
            cache[key] = fuse([lookup[w] for w in key], gap=WORKING_GAP)['automatic']
        path.append(cache[key])
    return path


def partition(state):
    return {frozenset((m['id'], m['pair_index']) for m in g['members']):g
            for g in state['identity_groups']}


def coidentity_pairs(groups, shared):
    return {frozenset(pair) for g in groups
            for pair in itertools.combinations(g & shared, 2)}


def transition(old, new):
    """只比较旧观察的分区；未重分的组才能明确归为存在票变化。"""
    a, b = partition(old), partition(new)
    old_members = set().union(*a) if a else set()
    new_members = set().union(*b) if b else set()
    shared = old_members & new_members
    changed = coidentity_pairs(a, shared) ^ coidentity_pairs(b, shared)
    restricted_b = {g & shared:row for g,row in b.items() if g & shared}
    losses = gains = 0
    for members, row in a.items():
        # 本计数用于嵌套加人；换组分区诊断另用changed_coidentity_pairs。
        if members <= shared and members in restricted_b:
            after = restricted_b[members]
            losses += row['selected'] and not after['selected']
            gains += not row['selected'] and after['selected']
    return dict(shared_observations=len(shared), changed_coidentity_pairs=len(changed),
                common_pair_comparisons=len(shared)*(len(shared)-1)//2,
                unchanged_identity_vote_losses=int(losses), unchanged_identity_vote_gains=int(gains),
                threshold_increased=(new['n']+1)//2 > (old['n']+1)//2)


def footprint(points):
    if points is None or len(points) < 3:
        return None
    poly = Polygon(points)
    return poly if poly.is_valid and poly.area > 0 and np.isfinite(poly.area) else None


def footprint_metrics(points, reference):
    a, g = footprint(points), footprint(reference)
    if a is None or g is None:
        return None
    inter = a.intersection(g).area
    omission = max(0., g.area-inter)/g.area
    extension = max(0., a.area-inter)/g.area
    return dict(iou=inter/(a.area+g.area-inter), D_ref=omission+extension,
                omission_ref=omission, extension_ref=extension)


def summarize_state(state):
    c = state['candidate']
    nodes = state['node_consensus']['nodes']
    floor_ok = footprint(c['footprint']) is not None
    return dict(k=state['n'], parity=state['n'] % 2, nodes=len(nodes),
        below_four=len(nodes)<4, half_vote_nodes=sum(2*n['support']==state['n'] for n in nodes),
        connection_available=c['points'] is not None, order_status=c['order_status'],
        order_tied=state['ring_diagnostics']['tied_best'],
        geometry_status=c.get('geometry_status','not_evaluable'),
        geometry_reason=c.get('reason'), floor_evaluable=floor_ok,
        complete_floor_evaluable=floor_ok and len(nodes)>=4,
        complete_evaluable=c.get('geometry_status')=='ok' and len(nodes)>=4,
        location_unresolved=any(g.get('center') is None for g in state['identity_groups'] if g['selected']))


def compare_outputs(a, b):
    pa, pb = footprint(a['candidate']['footprint']), footprint(b['candidate']['footprint'])
    t = transition(a, b)
    return dict(node_count_difference=abs(len(a['node_consensus']['nodes'])-len(b['node_consensus']['nodes'])),
        shared_observations=t['shared_observations'],
        changed_coidentity_pairs=t['changed_coidentity_pairs'],
        common_pair_comparisons=t['common_pair_comparisons'],
        floor_jaccard_difference=None if pa is None or pb is None else 1-pa.intersection(pb).area/pa.union(pb).area,
        floor_symdiff_h2=None if pa is None or pb is None else pa.symmetric_difference(pb).area,
        both_complete_floor=summarize_state(a)['complete_floor_evaluable'] and summarize_state(b)['complete_floor_evaluable'])


def prepare_input():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle = load_current_bundle()
    data, aliases = project_bundle(bundle)
    objects = {aliases['records'][r['object_id']]:r for r in bundle['data']['objects']}
    block = read(ROOT/'analysis_results/worker_profiles_20261003/block.json')
    codes = block['images'] + ['yqstnuAEVhm-25','uNb9QFRL6hY-36']
    old = {im['image']:im for im in read(ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json')['images']}
    difficulty = read(ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.json')
    labels = {im['image']:im for im in difficulty['records']}
    registry = read(ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    held = {r['image_id']:r['classification'] for name in ('confirmed_reference_exclusions',
        'preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine') for r in registry[name]}
    images = []
    for im in data['images']:
        if im['code'] not in codes:
            continue
        records = [prepare_record(dict(r, source_pair_indices=objects[r['id']]['ordered_source_pair_indices']))
                   for r in im['annotations'] if r['independent'] and r['consensus_eligible']
                   and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate']
        records.sort(key=lambda r:r['worker'])
        if im['code'] in block['images']:
            assert [r['worker'] for r in records] == block['workers'].split('|')
        prior = {r['id']:r for r in old[im['code']]['records']}
        assert set(prior) == {r['id'] for r in records}
        changed = [r['id'] for r in records if any(r.get(k)!=prior[r['id']].get(k)
                    for k in ('points','source_pair_indices','ring_confirmed'))]
        d = labels[im['code']]
        refs = []
        for r in im['references']:
            prepared = prepare_record(r)
            g = reconstruct(prepared, coordinate_convention='continuous')
            refs.append(dict(version=r['version'], id=r['id'], points=prepared['points'],
                floor=None if g['floor'] is None else g['floor'].tolist(),
                geometry_status=g['status'], geometry_reason=g['reason']))
        refs.append(dict(version='difficulty_selected_floor', id=d['target_version'],
                         floor=d['selected']['floor'], role=d['selected']['role'], points=None,
                         interpretation='target-conditioned bottom-only diagnostic; not final Q'))
        images.append(dict(image=im['code'], image_id=d['image_id'], building=im['building'],
            panel='common24x10' if im['code'] in block['images'] else 'sentinel',
            records=records, references=refs, changed_since_1008=changed,
            reference_hold=held.get(d['image_id']),
            difficulty={k:d[k] for k in ('current_class','conditional_difficulty','target_version','scene',
                'oos_subtype','doorway_status','classification_basis','top_boundary_pending')},
            difficulty_version=difficulty['version']))
    assert len(images)==12
    return dict(source='load_current_bundle + project_bundle + prepare_record, 2026-10-14 snapshot',
                images=images)


def compact(state):
    return {k:state[k] for k in ('n','minimum_support','identity_groups','assignments',
                                 'node_consensus','candidate','ring_diagnostics')}


def run_image(image):
    code = image['image']
    workers = [r['worker'] for r in image['records']]
    rng = np.random.default_rng(SEED)
    orders = [rng.permutation(workers).tolist() for _ in range(REPEATS)]
    # 相同人员池使用相同排列，控制共同面板跨图的人员构成。
    cache, paths, observations, changes, swaps = {}, [], [], [], []
    for path_id, order in enumerate(orders):
        states = automatic_prefixes(image['records'], order, cache)
        paths.append(states)
        for k, s in enumerate(states, 1):
            key = '|'.join(sorted(order[:k]))
            row = dict(image=code, panel=image['panel'], path=path_id, subset=key, **summarize_state(s))
            for ref in image['references']:
                metrics = None if image['reference_hold'] else footprint_metrics(s['candidate']['footprint'], ref['floor'])
                for field in ('iou','D_ref','omission_ref','extension_ref'):
                    row[ref['version']+'__'+field] = metrics[field] if metrics else None
            observations.append(row)
            if k > 1:
                previous = states[k-2]
                changes.append(dict(image=code, path=path_id, k_from=k-1, k_to=k,
                    nodes_from=len(previous['node_consensus']['nodes']), nodes_to=len(s['node_consensus']['nodes']),
                    added_worker=order[k-1], **transition(previous, s),
                    connection_lost=previous['candidate']['points'] is not None and s['candidate']['points'] is None,
                    **{k:v for k,v in compare_outputs(previous, s).items() if k.startswith('floor_')}))
    for path_a in range(0, REPEATS, 2):
        for k, (a,b) in enumerate(zip(paths[path_a], paths[path_a+1]),1):
            swaps.append(dict(image=code, k=k, pair=path_a//2,
                shared_workers=len(set(orders[path_a][:k]) & set(orders[path_a+1][:k])),
                same_subset=set(orders[path_a][:k])==set(orders[path_a+1][:k]), **compare_outputs(a,b)))
    old = read(ROOT/f'analysis_results/consensus_delivery_20261008/{code}.json')
    end = paths[0][-1]
    comparable = not image['changed_since_1008']
    if comparable:
        assert end['node_consensus']==old['automatic']['node_consensus'], code
        assert end['candidate']==old['automatic']['candidate'], code
    endpoint = dict(image=code, input_same_as_1008=comparable, changed_records=image['changed_since_1008'],
        automatic=summarize_state(end), prior_assisted=summarize_state(old['assisted']) if old['assisted'] else None,
        prior_assisted_interpretation='same-input separate endpoint' if comparable else 'historical input; do not connect to current trajectory',
        applied_reviews=old['applied_reviews'])
    folder = OUT/'states';folder.mkdir(exist_ok=True)
    with gzip.open(folder/(code+'.json.gz'),'wt',encoding='utf-8') as f:
        json.dump(dict(image=code, orders=orders,
            states=[dict(workers=list(key), automatic=compact(value)) for key,value in cache.items()]),f,ensure_ascii=False,allow_nan=False)
    write_json(OUT/'endpoints'/f'{code}.json',dict(current_automatic=compact(end),
        prior_assisted=old['assisted'],endpoint_summary=endpoint))
    print(code, 'unique subsets',len(cache),'done',flush=True)
    return observations, changes, swaps, endpoint


def aggregate(observations, swaps):
    by_k, by_swap = defaultdict(list), defaultdict(list)
    for r in observations:by_k[(r['image'],r['k'])].append(r)
    for r in swaps:by_swap[(r['image'],r['k'])].append(r)
    rows = []
    for (image,k), group in sorted(by_k.items()):
        row = dict(image=image,k=k,panel=group[0]['panel'],paths=len(group),
            unique_subsets=len({r['subset'] for r in group}),nodes_mean=float(np.mean([r['nodes'] for r in group])),
            nodes_min=min(r['nodes'] for r in group),nodes_max=max(r['nodes'] for r in group))
        for field in ('below_four','half_vote_nodes','connection_available','complete_floor_evaluable','complete_evaluable','order_tied'):
            row[field+'_mean']=float(np.mean([r[field] for r in group]))
        for field in sorted({f for r in group for f in r if '__' in f}):
            # 不完整但底面可算的诊断保留在逐次表；主曲线明确限制为>=4对的可评价底面。
            values = [r[field] for r in group if r['complete_floor_evaluable'] and r.get(field) is not None]
            row[field+'_n']=len(values)
            row[field+'_mean']=float(np.mean(values)) if values else None
        paired = by_swap[(image,k)]
        values = [r['floor_jaccard_difference'] for r in paired if r['both_complete_floor']]
        row.update(swap_pairs=len(paired),swap_complete_pairs=len(values),
            swap_floor_difference_mean=float(np.mean(values)) if values else None,
            swap_node_difference_mean=float(np.mean([r['node_count_difference'] for r in paired])),
            swap_same_subset_pairs=sum(r['same_subset'] for r in paired))
        rows.append(row)
    return rows


def plots(rows, images):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    grouped = {im['image']:[r for r in rows if r['image']==im['image']] for im in images}
    for filename, field, title in (
        ('completeness.png','complete_floor_evaluable_mean','At least 4 nodes and evaluable floor / all paths'),
        ('member_sensitivity.png','swap_floor_difference_mean','Same-k independent teams: mean 1 - floor IoU (valid pairs only)'),
        ('reference_range.png','difficulty_selected_floor__D_ref_mean','Range difference / fixed selected reference area (valid paths only)'),
        ('node_counts.png','nodes_mean','Selected wall-line nodes; band = path min/max')):
        fig,axes=plt.subplots(3,4,figsize=(16,10),sharex=False)
        for ax,im in zip(axes.flat,images):
            rr=grouped[im['image']];x=[r['k'] for r in rr]
            y=[r[field] if r[field] is not None else np.nan for r in rr]
            ax.plot(x,y,lw=1,color='#426b98')
            for parity,marker,color in ((0,'s','#ca651b'),(1,'o','#1b6f9c')):
                ix=[j for j,k in enumerate(x) if k%2==parity]
                ax.scatter(np.array(x)[ix],np.array(y)[ix],marker=marker,c=color,s=18,label='even k' if parity==0 else 'odd k')
            if field=='nodes_mean':
                ax.fill_between(x,[r['nodes_min'] for r in rr],[r['nodes_max'] for r in rr],alpha=.15)
                ax.axhline(4,c='grey',lw=.7,ls='--')
            if field=='difficulty_selected_floor__D_ref_mean':
                ks=sorted({min(8,len(rr)),min(16,len(rr)),len(rr)})
                counts=[next(r[field.replace('_mean','_n')] for r in rr if r['k']==k) for k in ks]
                ax.text(.02,.02,'valid paths '+ '/'.join(map(str,ks))+': '+ '/'.join(str(int(v)) for v in counts)+' (of 24)',
                        transform=ax.transAxes,fontsize=7,bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
            ax.set_title(im['image']+(' [sentinel]' if im['panel']=='sentinel' else ''),fontsize=10)
            ax.set_xlabel('Number of workers');ax.grid(alpha=.2)
            if field!='nodes_mean':
                ax.axvspan(1.7,2.3,color='grey',alpha=.18)
            if field=='complete_floor_evaluable_mean':ax.set_ylim(-.05,1.05)
        axes.flat[0].legend(fontsize=8);fig.suptitle(title+'\nGrey strip: k=2 ordering deferred by policy' if field!='nodes_mean' else title)
        fig.tight_layout();fig.savefig(OUT/filename,dpi=150);plt.close(fig)


def summarize_saved():
    """从逐次结果生成成对区间比较；不重跑融合或重新选择参数。"""
    import pandas as pd
    obs=pd.read_csv(OUT/'observations.csv')
    steps=pd.read_csv(OUT/'transitions.csv')
    swaps=pd.read_csv(OUT/'same_k_pairs.csv')
    source=read(OUT/'input_snapshot.json')
    images=[];intervals=[]
    for im in source['images']:
        code=im['image'];n=len(im['records'])
        r=obs[obs.image==code];t=steps[(steps.image==code)&(steps.k_from>=3)]
        mid=r[(r.k>=3)&(r.k<n)]
        images.append(dict(image=code,panel=im['panel'],n=n,difficulty=im['difficulty']['current_class'],
            interior_paths=len(mid),interior_below_four=int(mid.below_four.sum()),
            interior_without_order=int((~mid.connection_available).sum()),
            interior_geometry_unavailable=int((mid.connection_available & (mid.geometry_status!='ok')).sum()),
            interior_incomplete_paths=int(mid.loc[mid.below_four,'path'].nunique()),
            transitions=len(t),regrouped_steps=int((t.changed_coidentity_pairs>0).sum()),
            unchanged_identity_vote_loss_steps=int((t.unchanged_identity_vote_losses>0).sum()),
            unchanged_identity_vote_losses=int(t.unchanged_identity_vote_losses.sum()),
            losses_at_even_to_odd=int(t.loc[t.threshold_increased,'unchanged_identity_vote_losses'].sum()),
            unchanged_identity_vote_gains=int(t.unchanged_identity_vote_gains.sum()),
            connection_loss_steps=int(t.connection_lost.sum())))
        for start,end in [(8,16),(8,24),(3,n)]:
            if end>n or start>=end:continue
            paired=r[r.k==start].merge(r[r.k==end],on='path',suffixes=('_a','_b'))
            for ref in im['references']:
                field=ref['version']+'__D_ref'
                good=paired[paired.complete_floor_evaluable_a & paired.complete_floor_evaluable_b
                    & paired[field+'_a'].notna() & paired[field+'_b'].notna()]
                delta=good[field+'_b']-good[field+'_a']
                intervals.append(dict(image=code,panel=im['panel'],difficulty=im['difficulty']['current_class'],
                    reference=ref['version'],k_from=start,k_to=end,total_paths=len(paired),paired_valid=len(good),
                    mean_D_from=float(good[field+'_a'].mean()) if len(good) else None,
                    mean_D_to=float(good[field+'_b'].mean()) if len(good) else None,
                    mean_D_change=float(delta.mean()) if len(good) else None,
                    improved_paths=int((delta< -1e-12).sum()),worsened_paths=int((delta>1e-12).sum())))
    write_csv(OUT/'matched_intervals.csv',intervals)
    write_json(OUT/'findings.json',dict(observations=len(obs),unique_subsets=sum(
        r[['image','subset']].drop_duplicates().shape[0] for _,r in obs.groupby('image')),
        transitions=len(steps),same_k_pairs=len(swaps),image_findings=images,
        endpoint_single_set='All-N repeated paths describe one member set, not repeated independent outputs',
        unresolved_attribution='Stage counters do not establish whether a regrouping is semantically right or wrong; valid-only area curves have changing denominators'))
    with gzip.open(OUT/'states/UwV83HsGsw3-09.json.gz','rt',encoding='utf-8') as f:
        saved=json.load(f)
    lookup={tuple(r['workers']):r['automatic'] for r in saved['states']}
    order=saved['orders'][0]
    a,b=[lookup[tuple(sorted(order[:k]))] for k in (12,13)]
    old_members=set().union(*partition(a))
    after={ms & old_members:g for ms,g in partition(b).items() if ms & old_members}
    losses=[]
    for ms,g in partition(a).items():
        if g['selected'] and ms in after and not after[ms]['selected']:
            losses.append(dict(source_members=sorted(ms),support_before=g['support'],support_after=after[ms]['support'],
                center_before=g['center'],center_after=after[ms]['center']))
    write_json(OUT/'uw_path0_example.json',dict(image=saved['image'],path=0,worker_order=order,
        states={str(k):summarize_state(lookup[tuple(sorted(order[:k]))]) for k in (8,9,12,13,24)},
        transition_12_to_13=transition(a,b),unchanged_identity_lost_nodes=losses,
        interpretation='A saved illustrative path, selected after inspecting results; not a frequency estimate or semantic identity certification'))


def run(snapshot=None):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'endpoints').mkdir(exist_ok=True)
    source=read(snapshot) if snapshot else prepare_input()
    write_json(OUT/'input_snapshot.json',source)
    write_json(OUT/'design.json',dict(schema='wall_population_v1',gap=WORKING_GAP,rule='MV50',
        repeats=REPEATS,seed=SEED,panel='existing common24x10 + two separate sentinels; no outcome selection',
        input='current formal loader; exact snapshot saved; old endpoints compared only if inputs unchanged',
        sampling='24 independently shuffled without-replacement orders; all prefixes k=1..N; same orders across common-worker images',
        swaps='12 independent pairs of paths at each k; member overlap allowed; all-N difference mechanically zero',
        reference='original and revision separate; difficulty-selected floor is target-conditioned diagnostic, not Q; no top grafting',
        incomplete='below-four, no-order, invalid-geometry and two-person-deferred separate; not zero-filled',
        inference='finite-panel descriptive pilot; no general convergence or automatic accuracy claim',
        no_human_assistance_in_prefixes=True,no_quality_tuning=True))
    observations=[];changes=[];swaps=[];endpoints=[]
    with ProcessPoolExecutor(max_workers=3) as executor:
        for a,b,c,d in executor.map(run_image,source['images']):
            observations.extend(a);changes.extend(b);swaps.extend(c);endpoints.append(d)
    rows=aggregate(observations,swaps)
    for name,data in [('observations',observations),('transitions',changes),('same_k_pairs',swaps),('by_image_k',rows)]:
        fields=list(dict.fromkeys(k for row in data for k in row))
        write_csv(OUT/(name+'.csv'),[{k:r.get(k) for k in fields} for r in data])
    write_json(OUT/'endpoint_summary.json',endpoints)
    write_json(OUT/'field_contract.json',dict(schema='wall_population_v1',
        observations='one image/path/k; subset is actual sorted worker list; k=2 lacks layout by policy',
        reference_fields='version__metric: IoU, (omission+extension)/reference area, omission/reference, extension/reference; null if unavailable/held',
        by_image_k='n suffixed fields count evaluable paths, not independent people. Reference means only for >=4-node valid floors. No-order and below-four remain in denominators of completeness',
        transitions='coidentity changes compare pairs of old observations; vote loss/gain counts only unchanged restricted identities. This is algorithm bookkeeping, not semantic correctness or causal attribution',
        same_k='paired independent random teams; floor distance = 1-IoU with pairwise union denominator, NOT old full-pool-union V. Raw symdiff also saved. Complete pairs only in summary',
        states='gz saves each unique current-member subset, all groups, selected nodes/coordinates, assignments and ring evidence; no global-identity projection',
        endpoints='old human-assisted terminal result separate; changed inputs make historical endpoint noncomparable',
        difficulty='existing scope_preferred_v2 labels copied without reclassification; target-specific and not blindly assigned'))
    plots(rows,source['images'])
    summarize_saved()
    print('Finished:',len(observations),'path states;',len(changes),'transitions;',len(swaps),'same-k pairs',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,help='从已保存的实际输入复现；省略时读取当前正式loader')
    args=parser.parse_args()
    run(args.snapshot)
