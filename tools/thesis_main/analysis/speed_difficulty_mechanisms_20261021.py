"""Explain saved v2 speed-mixture outcomes using fixed images and local geometry."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .difficulty_mechanisms_v2_20261020 import ROOT, v, plt
from .fusion_change_mechanisms_20261020 import engine, normalized_state

OUT = ROOT / 'research/difficulty/speed_difficulty_mechanisms_20261021'
OLD = ROOT / 'research/difficulty/difficulty_mechanisms_v2_20261020'
METRICS = ['quality_difference', 'D10_difference', 'corner_recall_difference',
           'wall_coverage_difference', 'omission_difference', 'extension_difference',
           'same_count', 'loss_over_5', 'both_scored', 'both_complete', 'base_failed',
           'candidate_failed', 'log_source_time_ratio', 'base_nodes', 'candidate_nodes']


def read(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def save(name, obj):
    path = OUT / name
    if isinstance(obj, pd.DataFrame):
        obj.to_csv(path, index=False, encoding='utf-8-sig')
    else:
        data = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)
        if name.endswith('.gz'):
            with gzip.open(path, 'wt', encoding='utf-8') as f: f.write(data)
        else: path.write_text(data + '\n', encoding='utf-8')


def summarize(frame, keys, metrics=METRICS):
    """Repeated member draws -> image means -> equal-weight building means."""
    rows = []
    for labels, f in frame.groupby(keys, dropna=False):
        if not isinstance(labels, tuple): labels = (labels,)
        images = f.groupby(['building', 'image_id'])[metrics].mean()
        buildings = images.groupby('building').mean()
        q = buildings.quality_difference.dropna() if 'quality_difference' in metrics else pd.Series(dtype=float)
        row = dict(zip(keys, labels)) | dict(images=len(images), buildings=len(buildings), comparisons=len(f), **buildings.mean().to_dict())
        if 'both_scored' in f:
            row['scored_comparisons'] = int(f.both_scored.sum())
            row['images_with_any_unscored'] = int((~f.groupby('image_id').both_scored.all()).sum())
        if len(q) > 1:
            leave = (q.sum() - q) / (len(q) - 1)
            row.update(leave_building_min=leave.min(), leave_building_max=leave.max())
        rows.append(row)
    return pd.DataFrame(rows)


def actual_pairs(comparisons, teams, history):
    """Only replaced fast/slow pairs; the fifth retained slow is not an exposure."""
    rows = []
    h = {k: g for k, g in history.groupby('panel_id')}
    for _, r in comparisons.iterrows():
        if r.panel_id not in h: continue  # External history-pair table covers ordinary Manual only.
        before = set(teams[r.base_team_key]['member_workers'])
        after = set(teams[r.candidate_team_key]['member_workers'])
        pairs = h[r.panel_id]
        pairs = pairs[pairs.fast.isin(after-before) & pairs.slow.isin(before-after)]
        assert len(pairs) == 4
        for _, pair in pairs.iterrows():
            rows.append(dict(pair, base_team_key=r.base_team_key, candidate_team_key=r.candidate_team_key,
                             image=r.image, layer=r.layer, condition=r.condition, mechanism=r.mechanism,
                             ref_turn5=r.ref_turn5, reference_id=r.reference_id,
                             common_domains=r.common_domains))
    return pd.DataFrame(rows)


def main(bundle):
    OUT.mkdir(parents=True, exist_ok=True)
    records = read(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    byid = {r['object_id']: r for r in records}
    teams = {r['team_key']: r for r in read(bundle/'claims/claim_teams.json.gz')}
    all_comparisons = pd.read_csv(bundle/'claims/speed_n5_comparisons.csv.gz')
    d = all_comparisons[all_comparisons.n_fast.eq(4) & all_comparisons.contrast.eq('versus_slow')].copy()
    assert d.n.eq(5).all() and d.origin.eq('new').all()
    for key in set(d.base_team_key) | set(d.candidate_team_key):
        t = teams[key]
        assert len(t['member_object_ids']) == len(set(t['member_workers'])) == 5
        for oid, worker in zip(t['member_object_ids'], t['member_workers']):
            r = byid[oid]
            assert r['worker_id'] == worker and r['image_id'] == t['image_id']
            assert r['reference_id'] == t['reference_id'] and r['quality_usable'] and r['independent_vote_eligible']
    d['reference_id'] = d.base_team_key.map(lambda k: teams[k]['reference_id'])
    assert d.reference_id.eq(d.candidate_team_key.map(lambda k: teams[k]['reference_id'])).all()
    d = d.merge(pd.read_csv(OLD/'reference_conditions.csv'), on='reference_id', how='left', validate='many_to_one')
    d['mechanism'] = np.select([d.ref_H.isna(), d.ref_H.gt(0), d.ref_short_edges.gt(0)],
                               ['unknown', 'H_positive', 'H0_short'], default='H0_plain')
    # Domain differences are reported only on shared images, separately for each layer.
    common = {layer: set(f[f.domain.eq('allQ')].image_id) & set(f[f.domain.eq('above_peer_Q')].image_id)
              for layer, f in d.groupby('layer')}
    d['common_domains'] = [im in common[layer] for im, layer in zip(d.image_id, d.layer)]
    d['node_delta'] = d.candidate_nodes-d.base_nodes
    save('comparisons_conditions.csv.gz', d)
    summaries = []
    for scope, f in [('available', d), ('common_domains', d[d.common_domains])]:
        for split in ['mechanism', 'difficulty']:
            s = summarize(f, ['layer', 'domain', split]); s.insert(0, 'scope', scope); s['split'] = split
            summaries.append(s)
    save('condition_summary.csv', pd.concat(summaries, ignore_index=True))
    save('fixed6_summary.csv', summarize(d[d.common_domains & d.ref_turn5.eq(6)], ['layer', 'domain', 'mechanism']))
    save('layer_summary.csv', summarize(d, ['layer', 'domain']))
    common_manual = d[d.common_domains & d.layer.eq('ordinary_manual')]
    complete_images = common_manual.groupby('image_id').both_scored.all()
    save('fully_scored_common_summary.csv', summarize(common_manual[common_manual.image_id.isin(complete_images[complete_images].index)],
         ['layer', 'domain', 'mechanism']))
    imkeys = ['domain', 'image', 'image_id', 'building', 'difficulty', 'mechanism', 'ref_turn5']
    images = common_manual.groupby(imkeys)[METRICS+['node_delta']].mean().reset_index()
    save('common_image_effects.csv', images)
    domain_gap = images[images.domain.eq('allQ')].merge(images[images.domain.eq('above_peer_Q')],
                on=['image', 'image_id', 'building', 'difficulty', 'mechanism', 'ref_turn5'], suffixes=('_allQ', '_highQ'), validate='one_to_one')
    domain_gap['difference_of_effects'] = domain_gap.quality_difference_highQ-domain_gap.quality_difference_allQ
    save('common_domain_differences.csv', domain_gap)
    h = pd.read_csv(bundle/'tables/speed/speed_n5_historical_difficulty_pairs.csv')
    pairs = actual_pairs(d, teams, h)
    expr = pd.read_csv(OLD/'record_conditions.csv.gz', low_memory=False).set_index('object_id')
    object_lookup = {(t['pool_id'], w): oid for t in teams.values() for w, oid in zip(t['member_workers'], t['member_object_ids'])}
    panel_pool = d.set_index('panel_id').pool_id.to_dict()
    for arm in ['fast', 'slow']:
        pairs[arm+'_object_id'] = [object_lookup[panel_pool[pid], w] for pid, w in zip(pairs.panel_id, pairs[arm])]
        for field in ['annotation_turn5', 'reduced', 'unmatched_ref_9', 'bottom_bias_9', 'log_area']:
            pairs[arm+'_'+field] = pairs[arm+'_object_id'].map(expr[field])
        pairs[arm+'_target_Q'] = pairs[arm+'_object_id'].map(lambda oid: byid[oid]['B8L2'])
    pairs['target_Q_gap'] = pairs.fast_target_Q-pairs.slow_target_Q
    pairs['turn_gap'] = pairs.fast_annotation_turn5-pairs.slow_annotation_turn5
    pairs['reduced_gap'] = pairs.fast_reduced.astype(float)-pairs.slow_reduced.astype(float)
    pairs['unmatched_gap'] = pairs.fast_unmatched_ref_9-pairs.slow_unmatched_ref_9
    save('actual_replacement_pairs.csv.gz', pairs)
    pair_metrics = ['overall_Q_gap', 'hard_Q_mean_gap', 'hard_Q_peer_gap', 'target_Q_gap',
                    'turn_gap', 'reduced_gap', 'unmatched_gap', 'fast_hard_n', 'slow_hard_n']
    for scope, f in [('available', pairs), ('common_domains', pairs[pairs.common_domains])]:
        s = summarize(f, ['domain', 'mechanism'], pair_metrics)
        save('replacement_pairs_'+scope+'.csv', s)

    # Representative existing designs, not maximum-loss draws; pa14 adds a fast-member counterexample.
    specs = [('UwV83HsGsw3-22', [0]), ('B6ByNegPMKs-48', [0]), ('pa4otMbVnkk-14', [0, 1])]
    cases = []
    for code, reps in specs:
        f = d[d.layer.eq('ordinary_manual') & d.domain.eq('above_peer_Q') & d.image.eq(code) & d.replicate.isin(reps)]
        assert len(f) == len(reps)
        cases.extend(f.to_dict('records'))
    selected_keys = {c[k] for c in cases for k in ['base_team_key', 'candidate_team_key']}
    fe = engine(); pools = {p['pool_id']: p for p in fe.load_pools()}; states = {}; checks = []; measurements = {}
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE/'measurement_engine.zip', fe.ENGINE/'working_models.py') as (scorer, models):
        for key in sorted(selected_keys):
            t = teams[key]; pool = pools[t['pool_id']]; members = {r['worker_id']: r for r in pool['records']}
            rs = [members[w] for w in sorted(t['member_workers'])]
            assert pool['reference']['target_id'] == t['reference_id']
            assert all(r['points'] == byid[r['object_id']]['points_1024x512'] for r in rs)
            assert pool['reference']['points_1024x512'] == byid[rs[0]['object_id']]['reference_evidence']['points_1024x512']
            state = normalized_state(fe.compact(fe.fuse(rs, gap=fe.WORKING_GAP)['automatic']))
            score = fe.compute_score(state, pool, scorer, models)
            assert len(state['candidate']['points'])//2 == t['nodes']
            assert all(np.isclose(score[field], t[field], rtol=1e-10, atol=1e-7) for field in ['B8L2', 'D10'])
            states[key] = state
            measurements[key] = score
            checks.append(dict(team_key=key, nodes=t['nodes'], B8L2=score['B8L2'], D10=score['D10'], matches_saved_scores=True))
    save('selected_states.json.gz', fe.clean(states))
    save('selected_teams.json.gz', [teams[k] for k in sorted(selected_keys)])
    save('selected_references.json', {p: pools[p]['reference'] for p in {teams[k]['pool_id'] for k in selected_keys}})
    save('replay_checks.json', checks)
    save('selected_measurements.json', measurements)
    selected_designs = {(c['base_team_key'], c['candidate_team_key'], c['replicate']) for c in cases}
    case_pairs = pairs[[x in selected_designs for x in zip(pairs.base_team_key, pairs.candidate_team_key, pairs.replicate)]]
    save('case_replaced_people.csv', case_pairs)
    local = []
    for c in cases:
        pool = pools[c['pool_id']]; ref = np.asarray(pool['reference']['points_1024x512'])
        for arm in ['base', 'candidate']:
            key = c[arm+'_team_key']; state = states[key]
            for g in state['identity_groups']:
                center = np.asarray(g['center']); x = center[0, 0]
                dx = abs((ref[::2, 0]-x+512)%1024-512); idx = int(dx.argmin())
                local.append(dict(image=c['image'], replicate=c['replicate'], arm=arm, team_key=key,
                    feature_id=g['feature_id'], support=g['support'], selected=g['selected'],
                    minimum_support=state['minimum_support'], x=x, bottom_y=center[1, 1],
                    nearest_ref_index_1based=idx+1, nearest_ref_horizontal_px=float(dx[idx]),
                    workers='|'.join(sorted(m['worker'] for m in g['members']))))
    save('local_support.csv', pd.DataFrame(local))
    save('case_design.json', fe.clean(cases))
    offsets = []
    for key in sorted(selected_keys):
        t = teams[key]; ref = pools[t['pool_id']]['reference']; points = np.asarray(states[key]['candidate']['points'])
        rp = np.asarray(ref['points_1024x512']); rf = np.asarray(ref['floor_xz_h'])
        if len(points) != len(rp): continue
        ix = np.abs((points[::2, 0, None]-rp[::2, 0][None, :]+512)%1024-512).argmin(axis=0)
        assert len(set(ix)) == len(ix)
        ordered = points.reshape(-1, 2, 2)[ix].reshape(-1, 2)
        floor = v.viewer_geometry(ordered)['floor']
        e = np.roll(floor, -1, axis=0)-floor; re = np.roll(rf, -1, axis=0)-rf
        angles = np.degrees(np.arccos(np.clip((e*re).sum(1)/(np.linalg.norm(e,axis=1)*np.linalg.norm(re,axis=1)), -1, 1)))
        for j in range(len(ix)):
            offsets.append(dict(image=t['image'], team_key=key, reference_corner_1based=j+1,
                horizontal_dx=(ordered[2*j,0]-rp[2*j,0]+512)%1024-512,
                bottom_dy=ordered[2*j+1,1]-rp[2*j+1,1],
                floor_corner_distance_h=float(np.linalg.norm(floor[j]-rf[j])),
                outgoing_edge_length_h=float(np.linalg.norm(re[j])), outgoing_edge_angle_deg=angles[j]))
    save('case_reference_offsets.csv', pd.DataFrame(offsets))
    render(d, images, cases, states, teams, pools, byid)
    save('COVERAGE.json', dict(data_release='v2', input_inventory=len(records), speed_comparisons=len(d),
        common_manual_images=len(common['ordinary_manual']), common_doorway_images=len(common['doorway_manual']),
        common_semi_images=len(common['ordinary_semi']), replayed_unique_existing_teams=len(states),
        new_teams_designed=0, reference_and_difficulty_unchanged=True))
    print((OUT/'COVERAGE.json').read_text())


def render(d, images, cases, states, teams, pools, byid):
    v._configure_font(Path('C:/Windows/Fonts/msyh.ttc'))
    names = ['H0_plain', 'H0_short', 'H_positive']
    fig, ax = plt.subplots(figsize=(9, 5))
    for j, domain in enumerate(['allQ', 'above_peer_Q']):
        s = summarize(d[d.common_domains & d.layer.eq('ordinary_manual') & d.domain.eq(domain)], ['mechanism']).set_index('mechanism')
        x = np.arange(3)+(j-.5)*.25
        ax.bar(x, [s.loc[n, 'quality_difference'] for n in names], .24, label=['全Q域', '高Q域'][j], color=['#1685a4', '#b7652c'][j])
        for xx, name in zip(x, names):
            value = s.loc[name, 'quality_difference']
            ax.text(xx, value+(.25 if value>=0 else -.6), f'{value:+.2f}', ha='center', va='bottom' if value>=0 else 'top', fontsize=9)
    ax.axhline(0, color='gray', lw=.7); ax.set_xticks(range(3), ['H=0无短边：53图', 'H=0有短边：7图', '几何H>0：17图'])
    ax.set_ylabel('4快1慢 − 5慢：B8L2变化，建筑等权');ax.set_ylim(-12, 3)
    ax.set_title('固定共同77图：损失集中在特定结构条件，不能归因于换图');ax.legend()
    fig.tight_layout();fig.savefig(OUT/'common_conditions.png', dpi=160);plt.close(fig)
    # Each case keeps ERP coordinates and the complete frozen reference, including small features.
    zooms = {'UwV83HsGsw3-22':(430, 610, 100, 420), 'B6ByNegPMKs-48':(730, 810, 265, 305), 'pa4otMbVnkk-14':(35, 125, 190, 345)}
    for code in dict.fromkeys(c['image'] for c in cases):
        cs = [c for c in cases if c['image']==code]
        fig, axes = plt.subplots(len(cs), 3, figsize=(16, 4*len(cs)), squeeze=False)
        for i, c in enumerate(cs):
            pool = pools[c['pool_id']]; ref = pool['reference']['points_1024x512']
            image_path = ROOT/'data/mp3d_layout/img_v'/(c['image_id']+'.jpg')
            photo = np.asarray(Image.open(image_path).convert('RGB'))
            colors = ['#00c9ed', '#ff58aa']
            for j in [0, 1]:
                v._erp_background(axes[i,j], photo, None if j==0 else zooms[code])
                v._erp_edges(axes[i,j], ref, '#ffd43b', reference=True)
                for arm, color in zip(['base','candidate'], colors):
                    v._erp_edges(axes[i,j], states[c[arm+'_team_key']]['candidate']['points'], color, markers=True)
            ref_floor = np.asarray(pool['reference']['floor_xz_h'])
            axes[i,2].plot(*np.vstack([ref_floor, ref_floor[0]]).T, color='#a58800', lw=2, label='参考')
            for arm, color in zip(['base','candidate'], colors):
                floor = v.viewer_geometry(states[c[arm+'_team_key']]['candidate']['points'])['floor']
                axes[i,2].plot(*np.vstack([floor, floor[0]]).T, color=color, lw=1.7, label='5慢' if arm=='base' else '4快1慢')
            axes[i,2].set_aspect('equal'); axes[i,2].legend(fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.12), ncol=3)
            axes[i,2].set_title('底面／相机高度单位')
            axes[i,0].set_title(f"{code} r{c['replicate']}：{c['base_Q']:.2f} → {c['candidate_Q']:.2f}")
            axes[i,1].set_title('同图局部放大；青=5慢，品红=4快1慢，黄=参考')
        fig.tight_layout();fig.savefig(OUT/(code+'_teams.png'), dpi=150);plt.close(fig)
        c = cs[0]; pool = pools[c['pool_id']]; ref = pool['reference']['points_1024x512']
        photo = np.asarray(Image.open(ROOT/'data/mp3d_layout/img_v'/(c['image_id']+'.jpg')).convert('RGB'))
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        for i, arm in enumerate(['base', 'candidate']):
            key = c[arm+'_team_key']; t = teams[key]
            for j in range(2):
                ax = axes[i,j]; v._erp_background(ax, photo, None if j==0 else zooms[code])
                for k, oid in enumerate(t['member_object_ids']):
                    color = plt.get_cmap('tab10')(k)
                    v._erp_edges(ax, byid[oid]['points_1024x512'], color, markers=True)
                    ax.plot([], [], color=color, label=byid[oid]['worker_id'])
                v._erp_edges(ax, ref, '#ffd43b', reference=True)
                v._erp_edges(ax, states[key]['candidate']['points'], '#111111', markers=True)
                ax.set_title(('5慢' if i==0 else '4快1慢')+(' 原答全景' if j==0 else ' 原答局部；黑=融合，黄=参考'))
                if j==0: ax.legend(fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.04), ncol=5)
        fig.suptitle(code+'：每队5份既定处理点位，未补点／换序', fontsize=12)
        fig.subplots_adjust(top=.90, bottom=.10, hspace=.35, wspace=.15)
        fig.savefig(OUT/(code+'_members.png'), dpi=150, bbox_inches='tight', pad_inches=.15);plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True, help='Read-only external personnel research bundle root')
    main(parser.parse_args().bundle)
