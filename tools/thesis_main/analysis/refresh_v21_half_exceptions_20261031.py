"""Refresh current-label half-team exceptions; reuse traces, replay only six missing arms."""
import base64
import gzip
import io
import itertools
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT / 'research/data/releases/v2.1'
UP = REL / 'admitted_space_extension/image_difficulty_20261030'
PRO = ROOT / 'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
OLD = PRO / 'stage01_half_team'
OUT = REL / 'half_team_current_exceptions_20261031'
KEYS = ['building', 'image', 'pool_id', 'block_id', 'background_id']


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz' else path.open(encoding='utf-8-sig')) as f:
        return json.load(f)


def aggregate(events, columns):
    result = events.groupby(KEYS, dropna=False)[columns].mean()
    for keys in [KEYS[:-1], KEYS[:-2], KEYS[:2]]:
        result = result.groupby(level=keys).mean()
    return result.reset_index()


def classify(images):
    images = images.copy()
    images['GA_nonpositive'] = images.gap_A.le(0)
    images['GS_nonpositive'] = images.gap_sym.le(0)
    images['CB_nonpositive'] = images.CB.le(0)
    images['no_joint_Q'] = images.gap_A.isna()
    images['numeric_exception'] = images[['GA_nonpositive', 'GS_nonpositive', 'CB_nonpositive', 'no_joint_Q']].any(axis=1)
    images['diagnostic'] = images.numeric_exception | images.partial_events
    return images


def fmt(x):
    return '不可评' if pd.isna(x) else f'{x:+.3f}'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(PRO / 'scripts'))
    from complete_half_traces import parity, clean, write
    from analyze_half_mechanisms import spherical
    from research.workers.personnel_v21_reselection_20261029.experiment.benchmark_engine import load_engine

    def save(data, name):
        pd.DataFrame(data).to_csv(OUT / name, index=False, encoding='utf-8-sig')

    legal = pd.read_csv(UP / 'HALF_EVENT_LEGALITY.csv.gz', low_memory=False)
    legal = legal[legal.n.eq(14) & legal.updated_class_legal].copy()
    assert len(legal) == 147 and legal.event_id.is_unique
    source = pd.read_csv(OLD / 'EVENTS_WITH_ENDPOINTS.csv.gz', low_memory=False).set_index('event_id')
    e = source.loc[legal.event_id].reset_index()
    for col in ['pool_id', 'reference_id', 'reference_version', 'D', 'X', 'Y', 'Z'] + [a+'_team_key' for a in 'ABC']:
        assert e[col].tolist() == legal[col].tolist(), col
    for col in ['gap_A', 'gap_sym', 'CB']:
        np.testing.assert_allclose(e[col], legal[col], equal_nan=True)
    e['updated_direction'] = legal.updated_direction.to_numpy()
    e['label_scope'] = 'updated_labels_legal_subset'
    pools = {p['pool_id']: p for p in read(REL / 'pools/INPUT_SNAPSHOT.json')['images']}
    e['difficulty'] = e.pool_id.map(lambda p: pools[p]['meta']['difficulty'])
    metrics = ['gap_A', 'gap_sym', 'CB', 'C_between_A_B', 'opposed_CB_loss_components', 'all_Q_at_least_90']
    metrics += ['B8L2_within', 'B8L2_cross_direct', 'B8L2_cross_symmetric']
    metrics += [c for c in e if c.startswith('geometry_') and c.endswith(('_AB', '_AC', '_BC'))]
    metrics += [f'{m}_CB' for m in ['fusion_turn_n', 'boundary_loss', 'direction_loss', 'height_loss']]
    im = aggregate(e, metrics)
    im['events'] = im.image.map(e.groupby('image').size())
    im['scored_events'] = im.image.map(e.groupby('image').gap_A.count())
    im['partial_events'] = im.scored_events.lt(im.events)
    im = classify(im)
    check = pd.read_csv(UP / 'HALF_SUMMARY.csv')
    check = check[check.n.eq(14) & check.scope.eq('updated_labels_legal_subset')].iloc[0]
    for metric in ['gap_A', 'gap_sym', 'CB']:
        assert abs(im[metric].mean() - check[metric]) < 1e-10
    assert len(im) == 69 and im.gap_A.notna().sum() == 67
    cases = im[im.diagnostic].copy()
    evs = e[e.image.isin(cases.image)].copy()
    oldindex = pd.read_csv(OLD / 'MECHANISM_EVENT_INDEX.csv').set_index('event_id')
    for r in evs[evs.event_id.isin(oldindex.index)].to_dict('records'):
        for col in ['pool_id', 'D', 'X', 'Y', 'Z'] + [a+'_team_key' for a in 'ABC']:
            assert r[col] == oldindex.loc[r['event_id'], col], (r['event_id'], col)
    traces, receipts = {}, []
    native = None
    for r in evs.to_dict('records'):
        pool = pools[r['pool_id']]
        for arm in 'ABC':
            key = r[arm+'_team_key']
            if key in traces:
                continue
            dest = OUT / 'trace_endpoints' / (key+'.json.gz')
            existing = OLD / 'trace_endpoints' / (key+'.json.gz')
            source_path = existing if existing.exists() else dest
            before = {c[3:]: v for c, v in r.items() if c.startswith(arm+'__')}
            req = dict(team_key=key, members=r[arm+'_members'], n=14)
            if not source_path.exists():
                if native is None:
                    native = load_engine(ROOT)
                with native.Engine(full_state=True) as engine:
                    row = engine.evaluate(pool, req['members'].split('|'))
                    if row.get('geometry') is not None:
                        extra = engine.scorecache.get(engine.fr.digest([False, row.get('nodes'), row['geometry']]))
                        if extra:
                            row.update(extra)
                parity(before, row, req, pool)
                row['trace_acquisition'] = 'current_exception_missing_trace_existing_team'
                write(dest, row)
                print('Recovered trace:', key, flush=True)
            tr = read(source_path)
            receipt = parity(before, tr, req, pool)
            receipt['source'] = source_path.relative_to(ROOT).as_posix()
            receipt['acquisition'] = 'old_trace' if source_path == existing else 'six_arm_trace_supplement'
            receipts.append(receipt)
            traces[key] = tr

    facts, votes, refs = [], [], []
    for r in evs.to_dict('records'):
        pool = pools[r['pool_id']]
        reference = np.asarray(pool['reference']['points_1024x512']).reshape(-1, 2, 2)
        for arm, block in zip('ABC', 'XYZ'):
            tr = traces[r[arm+'_team_key']]
            fs = tr['full_state']; groups = fs['identity_groups']
            selected = [g for g in groups if g['selected']]
            support = {g['feature_id']: {x['worker'] for x in g['members']} for g in selected}
            background, replacement = set(r['D'].split('|')), set(r[block].split('|'))
            covered = [a for a in fs['assignments'] if len([k for k in a['feature_ids'] if k in support]) == len(support) and set(a['feature_ids']) & set(support) == set(support) and len(support) >= 3]
            near_missing = 0
            valid = [g for g in groups if g.get('center') is not None]
            for i, ref in enumerate(reference):
                dist = spherical([g['center'][1] for g in valid], ref[1:2]).ravel()
                j = int(np.argmin(dist)); g = valid[j]
                near_missing += int(dist[j] <= 5 and not g['selected'])
                refs.append(dict(event_id=r['event_id'], image=r['image'], arm=arm, reference_corner=i+1, nearest_group=g['feature_id'], bottom_distance_deg=dist[j], support=g['support'], selected=g['selected'], threshold=fs['minimum_support']))
            facts.append(dict(event_id=r['event_id'], image=r['image'], arm=arm, team_key=tr['team_key'], score_status=tr['score_status'], Q=tr.get('B8L2'), minimum_support=fs['minimum_support'], selected_groups=len(selected), all_groups=len(groups), exact_threshold_selected_groups=sum(g['support']==7 for g in selected), background_alone_reaches_groups=sum(len(v & background)>=7 for v in support.values()), replacement_alone_reaches_groups=sum(len(v & replacement)>=7 for v in support.values()), source_complete_projected_rings=len(covered), reference_near_group_below_threshold_n=near_missing, selected_unresolved_locations=sum(g.get('center') is None for g in selected), native_ring_reason=fs.get('ring_diagnostics', {}).get('reason'), native_candidate_reason=fs.get('candidate', {}).get('reason')))
            for g in groups:
                members = {x['worker'] for x in g['members']}
                assert len(members)==g['support'] and members <= set(tr['member_workers'])
                assert g['selected'] == (g['support'] >= fs['minimum_support'])
                votes.append(dict(event_id=r['event_id'], image=r['image'], arm=arm, team_key=tr['team_key'], feature_id=g['feature_id'], selected=g['selected'], support=g['support'], D_support=len(members & background), replacement_support=len(members & replacement), center_json=json.dumps(g.get('center')), members='|'.join(sorted(members))))
    facts = pd.DataFrame(facts)
    oldfacts = pd.read_csv(OLD / 'mechanism_tables/ARM_MECHANISM_FACTS.csv')
    shared = facts.merge(oldfacts, on=['event_id', 'arm'], suffixes=('_new', '_old'), validate='one_to_one')
    fact_columns = ['selected_groups', 'all_groups', 'exact_threshold_selected_groups', 'source_complete_projected_rings', 'selected_unresolved_locations', 'background_alone_reaches_groups', 'replacement_alone_reaches_groups', 'reference_near_group_below_threshold_n']
    for col in fact_columns:
        assert shared[col+'_new'].eq(shared[col+'_old']).all(), col
    save(e, 'CURRENT_147_EVENTS.csv.gz'); save(im, 'ALL_69_IMAGE_RESULTS.csv')
    save(evs, 'DIAGNOSTIC_63_EVENTS.csv.gz'); save(facts, 'ARM_MECHANISM_FACTS.csv')
    save(votes, 'VOTE_GROUPS.csv.gz'); save(refs, 'REFERENCE_NEAR_GROUPS.csv')
    write(OUT/'TRACE_PARITY.json', receipts)

    payload = dict(images={}, events={}, teams={}, pools={}, metadata={'classification': 'DSTRUCT正向分类；RFUSE反向解释；当前图片难度LOBO标签', 'events':147, 'weighting':'背景→块→池→图等权'})
    label = pd.read_csv(UP/'classification/LABELS_ALL_LOBO.csv.gz')
    label = label[label.method.eq('TARGET_DSTRUCT_K3') & label.known]
    lm = {(r.heldout_building, r.worker_id): r.class_id for r in label.itertuples()}
    lines = ['# 当前147个合法半队事件：逐图反例与机制', '', 'DSTRUCT K3，普通Manual主目标，14人换7人。图片难度更新后的楼外标签；原团队、参考、质量和算法保持原身份。', '', 'GA=|C−A|−|B−A|；GS=(|C−A|+|C−B|)/2−|B−A|。先对背景、替换块、池依次等权，再对图片等权。空值不补零。锚点是示例，所有合法事件均保留；事件机制不自动代表整张图。', '']
    records, event_notes = [], []
    for row in cases.sort_values('image').to_dict('records'):
        sub = evs[evs.image.eq(row['image'])].copy()
        focus = 'gap_sym' if row['GS_nonpositive'] else 'gap_A' if row['GA_nonpositive'] else 'CB'
        if row['partial_events']:
            anchor = sub[sub.gap_A.isna()].sort_values('event_id').iloc[0]
        else:
            sub['distance'] = (sub[focus]-row[focus]).abs()
            anchor = sub.sort_values(['distance', 'event_id']).iloc[0]
        eid = anchor.event_id
        flags = [name for key, name in [('GA_nonpositive','同起点幅度未超同类'), ('GS_nonpositive','对称幅度未超同类'), ('CB_nonpositive','C队未升质'), ('no_joint_Q','无三队共同Q'), ('partial_events','含不可评事件')] if row[key]]
        numerical = [f"当前{row['events']}事件、{row['scored_events']}个三队共同Q事件；GA {fmt(row['gap_A'])}，GS {fmt(row['gap_sym'])}，C−B {fmt(row['CB'])}。",
                     f"同类幅度 {fmt(row['B8L2_within'])}，跨类同起点幅度 {fmt(row['B8L2_cross_direct'])}，跨类对称幅度 {fmt(row['B8L2_cross_symmetric'])}。"]
        if row['GA_nonpositive'] or row['GS_nonpositive']:
            numerical.append('这里未达到的是跨类幅度超过同类的预期；'+('C仍比B升质，不能写作换类无效。' if row['CB']>0 else '同时需看下述C−B方向。'))
        if pd.notna(row['C_between_A_B']):
            numerical.append(f"三队共同可评事件中，C落在A/B分数之间的设计权重占{row['C_between_A_B']:.1%}，三队均Q≥90占{row['all_Q_at_least_90']:.1%}；按B/C分项自身支持，loss方向相反占{row['opposed_CB_loss_components']:.1%}。这不是独立人群比例。")
        numerical.append(f"C−B有效转折变化 {fmt(row['fusion_turn_n_CB'])}；边界/方向/高度loss变化分别为 {fmt(row['boundary_loss_CB'])} / {fmt(row['direction_loss_CB'])} / {fmt(row['height_loss_CB'])}（负值表示该损失降低，各分项按自身支持）。")
        numerical.append(f"底面几何距离AB/AC/BC为 {fmt(row['geometry_bev_distance_AB'])} / {fmt(row['geometry_bev_distance_AC'])} / {fmt(row['geometry_bev_distance_BC'])}；几何距离描述改变多少，不表示离参考更近。")
        notes = []
        for a in 'ABC':
            f = facts[(facts.event_id.eq(eid)) & facts.arm.eq(a)].iloc[0]
            notes.append(f"锚点{a}队Q {fmt(f.Q)}；入选{f.selected_groups}/{f.all_groups}组，恰达7票{f.exact_threshold_selected_groups}组，D独自达票{f.background_alone_reaches_groups}组，替换块独自达票{f.replacement_alone_reaches_groups}组；覆盖全部已选组的源环{f.source_complete_projected_rings}份；已选定位缺失{f.selected_unresolved_locations}；状态{f.score_status}。")
            if f.reference_near_group_below_threshold_n:
                notes.append(f"{a}队有{f.reference_near_group_below_threshold_n}个参考角，其5°内最近候选未达票；具体角号、组号及票数见REFERENCE_NEAR_GROUPS.csv与页面票账。")
            if f.score_status == 'no_connection':
                notes.append(f"{a}队未形成连接；保存原因：{f.native_ring_reason} / {f.native_candidate_reason}。这是连接状态失败，不是Q=0。")
        af = facts[facts.event_id.eq(eid)]
        if af.selected_groups.nunique()==1 and af.score_status.eq('complete_conditional').all():
            notes.append('锚点三队入选数量相同且均完整；结合定位几何和损失变化解释质量差，不能只归因为多保留转折。节点数量相同也不保证节点身份相同。')
        for er in sub.sort_values('event_id').to_dict('records'):
            ef = facts[facts.event_id.eq(er['event_id'])].set_index('arm')
            detail = f"事件 {er['event_id']}：A/B/C的Q={fmt(er['A__B8L2'])}/{fmt(er['B__B8L2'])}/{fmt(er['C__B8L2'])}；GA {fmt(er['gap_A'])}、GS {fmt(er['gap_sym'])}、C−B {fmt(er['CB'])}。"
            if pd.isna(er['gap_A']):
                detail += '共同Q缺失原因：'+'；'.join(f"{a}队{ef.loc[a,'score_status']}，入选{ef.loc[a,'selected_groups']}组，完整投影源环{ef.loc[a,'source_complete_projected_rings']}份，定位缺失{ef.loc[a,'selected_unresolved_locations']}组" for a in 'ABC' if ef.loc[a,'score_status']!='complete_conditional')+'。'
            else:
                if er['C_between_A_B']==1:
                    detail += 'C位于A/B之间：两段跨类绝对差之和等于AB差，GS为同类幅度的负一半；这直接解释对称幅度非正。'
                elif er['gap_sym']<=0 and er['CB']>0:
                    detail += 'C虽高于B，但对称跨类距离是CA与CB的平均，仍不超过AB；同类换人本身已经产生较大的变化。'
                elif er['gap_A']<=0:
                    detail += '同起点CA幅度不超过AB，原同类成员差异已达到或超过跨类替换幅度。'
                worse = [name for key,name in [('boundary_loss_CB','边界'),('direction_loss_CB','方向'),('height_loss_CB','高度')] if er[key]>0]
                better = [name for key,name in [('boundary_loss_CB','边界'),('direction_loss_CB','方向'),('height_loss_CB','高度')] if er[key]<0]
                detail += f"C−B损失上升项：{'、'.join(worse) or '无'}；下降项：{'、'.join(better) or '无'}；有效转折变化{fmt(er['fusion_turn_n_CB'])}。"
            detail += ' 三队入选/完整投影源环数：'+'；'.join(f"{a}={ef.loc[a,'selected_groups']}/{ef.loc[a,'source_complete_projected_rings']}" for a in 'ABC')+'。'
            event_notes.append(dict(event_id=er['event_id'],image=er['image'],explanation=detail))
        human = '无需为上述数值及算法机制重复人工判级；若要解释具体物体是镜面、柜体还是墙，仍需局部视觉判断，该语义不用于本轮结论。'
        pid = anchor.pool_id; pool = pools[pid]
        pool['frozen_lobo_labels'] = {r['worker_id']: {'class_id':lm.get((pool['meta']['building'],r['worker_id']))} for r in pool['records']}
        original = OLD/'originals'/(row['image']+'.png')
        if not original.exists():
            candidates = list((ROOT/'data/mp3d_layout').glob('*/img/'+pool['meta']['image_id']+'.png'))
            assert candidates, row['image']
            original = sorted(candidates)[0]
        with Image.open(original) as photo:
            photo = photo.convert('RGB'); photo.thumbnail((1536,768)); buf = io.BytesIO(); photo.save(buf, format='JPEG', quality=90)
        payload['images'][row['image']] = clean(dict(image=row['image'], difficulty=pool['meta']['difficulty'], flags=flags, anchor_event=eid, event_ids=sorted(sub.event_id), numerical_notes=numerical, trace_notes=notes, human_check=human, preview='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()))
        payload['pools'][pid] = pool
        records.append(dict(**row, flags='；'.join(flags), anchor_event=eid, numeric_evidence=' '.join(numerical), trace_evidence=' '.join(notes), human_review=human, original=original.relative_to(ROOT).as_posix()))
        lines += [f"## {row['image']}（{pool['meta']['difficulty']}）", '', '；'.join(flags), '', *numerical, '', f'锚点 `{eid}`；该图全部合法事件可在研究台切换。', *notes, '', '逐事件解释：', *[r['explanation'] for r in event_notes if r['image']==row['image']], '']
    for r in evs.to_dict('records'):
        payload['events'][r['event_id']] = clean({k:r[k] for k in ['event_id','image','pool_id','building','n','m','D','X','Y','Z','updated_direction','A_team_key','B_team_key','C_team_key','gap_A','gap_sym','CB','record_time_CB_pct_source_matched']})
        for a in 'ABC':
            tr = traces[r[a+'_team_key']]
            payload['teams'][tr['team_key']] = {k:tr.get(k) for k in ['team_key','member_workers','score_status','B8L2','D10','nodes','minimum_support','geometry','full_state','fusion_turn_n','fusion_short_turn_edges','ref_node_recall_5','ref_edge_recall_5','boundary_loss','direction_loss','height_loss','geometry_area_h2','height_mean_h','source_time_total_seconds','recorded_time_eligible','record_time_by_kind_json']}
    save(records, 'CASE_INDEX.csv')
    save(event_notes, 'EVENT_EXPLANATIONS.csv')
    for r in event_notes:
        payload['events'][r['event_id']]['current_explanation'] = r['explanation']
    (OUT/'CASES_ZH.md').write_text('\n\n'.join(lines)+'\n', encoding='utf-8')
    # Reuse the existing canvas, vote and source-ring reader; only its dataset and scope change.
    page = (OLD/'HOHONET_latest_half_all36_viewer_ZH.html').read_text(encoding='utf-8')
    page = re.sub(r'<script id="data" type="application/json">.*?</script>', '<script id="data" type="application/json">'+json.dumps(clean(payload),ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/')+'</script>', page, flags=re.S)
    page = page.replace('197事件综合口径 · 36张图完整索引 · 全部相关原事件含20/7对照 · 精确原团队轨迹。TARGET K3是本轮工作分析对象，最终分类尚未选定。', '当前147合法事件 · 69登记/67共同Q图 · 30张诊断图、63个合法原事件 · DSTRUCT正向分类，RFUSE反向解释。')
    page = page.replace('最新半队全部反例', '当前合法半队反例与机制').replace('每图提供具体人工查看点。', '本轮不提交重复人工判级；物体语义与算法事实分别解释。')
    page = page.replace('原始综合事件、当前楼外标签、正式主目标参考、原答和冻结融合均来自提交 <code>13a7861334749805a86dc19e9ea79fcaa71020c0</code>。', '原团队与参考沿用综合存档；合法性使用图片难度更新后的LOBO标签。61个事件复用原轨迹，2个事件只补六支既有团队轨迹并通过数值一致性检查。')
    page = page.replace('完整PNG和校验值在结果包 originals。', '完整原图来源见CASE_INDEX.csv。')
    page = page.replace('<p><strong>人工查看点：</strong>', '<p><strong>当前事件解释：</strong>${esc(currentEvent.current_explanation)}</p><p><strong>人工复核边界：</strong>')
    page = page.replace('};setImage();', "};const requested=new URLSearchParams(location.search).get('image');if(DATA.images[requested])$('image').value=requested;setImage();")
    (OUT/'viewer.html').write_text(page, encoding='utf-8')
    oldimages = set(pd.read_csv(OLD/'ALL_36_CASE_READING_INDEX.csv').image)
    newimages = set(cases.image)
    save([dict(image=i, previous_diagnostic=i in oldimages, current_diagnostic=i in newimages, current_events=int(e.image.eq(i).sum()), reason=('无当前合法事件' if not e.image.eq(i).any() else '当前子集重新计权')) for i in sorted(oldimages|newimages)], 'OLD_CURRENT_IMAGE_MEMBERSHIP.csv')
    summary = dict(events=len(e), images=len(im), common_Q_images=int(im.gap_A.notna().sum()), scored_events=int(e.gap_A.notna().sum()), GA_nonpositive=int(im.GA_nonpositive.sum()), GS_nonpositive=int(im.GS_nonpositive.sum()), CB_nonpositive=int(im.CB_nonpositive.sum()), no_joint_Q=int(im.no_joint_Q.sum()), numeric_exception_images=int(im.numeric_exception.sum()), diagnostic_images=len(cases), diagnostic_events=len(evs), partial_only_images=int((im.partial_events & ~im.numeric_exception).sum()), GS_nonpositive_but_CB_positive=int((im.GS_nonpositive & im.CB.gt(0)).sum()), CB_positive_images=int(im.CB.gt(0).sum()), old_trace_events=int(evs.event_id.isin(oldindex.index).sum()), supplemented_trace_events=int((~evs.event_id.isin(oldindex.index)).sum()), trace_teams=len(traces), supplemented_trace_teams=sum(r['acquisition']=='six_arm_trace_supplement' for r in receipts), max_scalar_difference=max(r['maximum_scalar_difference'] for r in receipts), prior_fact_parity_rows=len(shared), entered=sorted(newimages-oldimages), removed=sorted(oldimages-newimages), new_physical_teams=0, human_review_required_for_current_claims=0)
    write(OUT/'CHECKS.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
