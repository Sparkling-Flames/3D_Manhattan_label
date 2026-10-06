"""One-hop neighbor evidence probe, not a matcher or a local-path equivalence solver."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np

from .paired_split_research.study import angular

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT/'research/layout_reliability_20261005/pro_original/inputs'
HUMAN = ROOT/'research/point_route_review_20261006/human_review.json'
OUT = ROOT/'analysis_results/point_context_probe_20261006'
THRESHOLDS = [1, 2.5, 5, 7.5, 10]
IMAGES = ['2t7WUuJeko7-06', '7y3sRwLe3Va-04', 'rPc6DW4iMge-06', 'uNb9QFRL6hY-67']
# Display mapping already used by point_route_review_20261006; never used in scores.
IMAGE_IDS = dict(zip(IMAGES, ['2t7WUuJeko7_3be66dc4f0fb46449d63b07d92c74f3f',
    '7y3sRwLe3Va_1410b021e1c14f529188eb026fbb369a',
    'rPc6DW4iMge_186a32a1b7e34cb797731bfa78365db5',
    'uNb9QFRL6hY_ca08ebfb2da647f68db41630637e400b'], strict=True))


def compare_context(a, i, b, j, metric):
    """Compare immediate ring neighbors, allowing reversal only for comparison."""
    ai = [(i-1) % len(a), i, (i+1) % len(a)]
    bj = [(j-1) % len(b), j, (j+1) % len(b)]
    top = angular(a[ai, 0]-.5, b[bj, 0]-.5)
    bottom = angular(a[ai, 1]-.5, b[bj, 1]-.5)
    d = {'top': top, 'bottom': bottom, 'pair': np.maximum(top, bottom)}[metric]
    directions = dict(forward=float(max(d[0, 0], d[2, 2])),
                      reverse=float(max(d[0, 2], d[2, 0])))
    neighbor = min(directions.values())
    return dict(anchor_deg=float(d[1, 1]), neighbor_deg=neighbor,
                combined_deg=float(max(d[1, 1], neighbor)), orientations_deg=directions,
                best_orientations=[k for k, v in directions.items() if abs(v-neighbor) <= 1e-9],
                query_neighbor_indices=[ai[0], ai[2]], candidate_neighbor_indices=[bj[0], bj[2]])


def reviewed_relation(review, a, b, metric):
    keys = list(zip(review['record_ids'], review['processed_pair_indices'], strict=True))
    pair = frozenset((a, b))
    if review['relation'] == 'same_corner_pair':
        if pair in {frozenset(p) for p in itertools.combinations(keys, 2)}:
            return 'same_corner'
        if 'rejected_previous_purple_processed_pair_index' in review:
            wrong = (keys[2][0], review['rejected_previous_purple_processed_pair_index'])
            if pair in {frozenset((k, wrong)) for k in keys[:2]}:
                return 'different_corner'
    elif metric == 'bottom' and pair in {frozenset(p) for p in itertools.combinations(keys, 2)}:
        return 'same_bottom_tentative'
    elif metric == 'top' and pair in {
            frozenset((keys[i], keys[j])) for i, j in review['different_upper_target_indices']}:
        return 'different_upper_target'
    return 'unreviewed'


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def threshold_sensitivity(reviewed):
    """All empirical gate transitions; no threshold recommendation or statistical inference."""
    output = []
    for case, metric in sorted({(r['case_id'], r['metric']) for r in reviewed}):
        rows = [r for r in reviewed if (r['case_id'], r['metric']) == (case, metric)]
        for score in ['anchor_deg', 'combined_deg']:
            positive = [r[score] for r in rows if r['relation'] in ['same_corner', 'same_bottom_tentative']]
            negative = [r[score] for r in rows if r['relation'] in ['different_corner', 'different_upper_target']]
            events = sorted({0., *positive, *negative})
            intervals = [dict(lower_inclusive_deg=t, upper_exclusive_deg=events[i+1] if i+1<len(events) else None,
                positive_retained=sum(d <= t for d in positive), negative_admitted=sum(d <= t for d in negative))
                for i, t in enumerate(events)]
            lower = max(positive) if positive else None
            upper = min(negative) if negative else None
            output.append(dict(case_id=case, metric=metric, score=score,
                positive_directed_relations=len(positive), negative_directed_relations=len(negative),
                positive_requirement_deg=lower, first_negative_admission_deg=upper,
                status='two_classes_available' if positive and negative else 'one_class_only_no_selection',
                development_separation_interval_deg=[lower, upper] if positive and negative and lower < upper else None,
                intervals=intervals, upper_endpoint_excluded=True,
                note='Observed pair compatibility only; no global clustering success, calibrated optimum or held-out validation. Last interval has no further observed event; angles are bounded by 180 degrees.'))
    return output


def subdivision_control():
    floor = np.array([[-2.,-2.], [2.,-2.], [2.,2.], [-2.,2.]])
    subdivided = np.insert(floor, 1, [0.,-2.], axis=0)
    def project(p):
        x = (np.arctan2(p[:,0], -p[:,1])/(2*np.pi)+.5)*1024
        phi = np.arctan2(1, np.linalg.norm(p, axis=1))*512/np.pi
        return np.stack([np.c_[x, 256-phi], np.c_[x, 256+phi]], axis=1)
    a, b = project(floor), project(subdivided)
    return dict(kind='synthetic_straight_edge_subdivision_not_new_people',
        floor=floor.tolist(), subdivided_floor=subdivided.tolist(),
        statement='Inserted midpoint lies on the same straight 3D wall edge; continuous boundary and anchor unchanged.',
        comparison=compare_context(a, 0, b, 0, 'pair'))


def build_view(out, pools, reviewed):
    payload = []
    for row in reviewed:
        records = {r['id']: r for r in pools[row['image']]}
        paths = [ROOT/'data/mp3d_layout'/split/'img'/(IMAGE_IDS[row['image']]+'.png') for split in ['train','valid','test']]
        found = [p for p in paths if p.is_file()]
        if len(found) > 1:
            raise ValueError('ambiguous_image_path')
        payload.append(dict(**row, photo=os.path.relpath(found[0], out).replace('\\','/') if found else None,
            records=[records[row[k][0]] for k in ['query','candidate']]))
    # Small source-point display only: no new edges, scores or GT are imported.
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>邻接证据反例对照</title><style>body{font:16px system-ui;margin:24px;background:#f4f6f8;color:#24313a}main{max-width:1150px;margin:auto}select,button{padding:8px;margin:5px}svg{width:100%;height:58vh;background:#222}table{border-collapse:collapse;background:white;width:100%}td,th{border:1px solid #ccc;padding:7px}p{line-height:1.6}.note{background:#fff1cb;padding:12px}</style><main>
<h1>即时邻点不一定帮助对应</h1><p class="note">开发对照，不是新融合结果。黄色为查询记录，紫色为候选记录；大圆是当前点，小圆是前后邻点。只显示原始点，不把点间直线当墙边。5°仅演示，全部阈值未校准。</p>
<label>案例 <select id="case"></select></label><label>距离 <select id="metric"><option value="pair">上下整对</option><option value="top">上端</option><option value="bottom">下端</option></select></label>
<label>关系 <select id="relation"></select></label><label>探索阈值° <input id="tau" type="number" min="0" max="180" step="0.01" value="5"></label><button id="zoom">切换全图／局部</button>
<p>可修改阈值查看兼容变化；这里只检查局部关系，不重新运行全员聚类。<a href="threshold_sensitivity.json">所有实际转折区间</a>均保存，不由页面选出最佳值。</p>
<svg id="scene" viewBox="90 60 260 400" aria-label="原始查询点、候选点及各自邻点"></svg><p id="description"></p><table><thead><tr><th>候选（处理后索引）</th><th>人工关系</th><th>仅本点A</th><th>邻点N</th><th>max(A,N)</th><th>同一目标人员内排名 A→B</th><th>当前阈值兼容 A／B</th></tr></thead><tbody id="rows"></tbody></table>
<p>前后顺序比较同向／反向两种对齐，数值较小者用于N；这不修改源环。未审核关系不记为错误或正确。当前点正确而邻点不相似的原因仍可能包括不同分段、不同范围或邻点位置差异，本页不替你判定。</p><a href="REPORT.md">研究报告</a> · <a href="reviewed_comparisons.json">逐项来源与数值</a><details><summary>当前比较完整来源</summary><pre id="detail"></pre></details></main>
<script>const data=__DATA__;const el=id=>document.getElementById(id);let full=false;
const cases=[...new Set(data.map(r=>r.case_id))];el('case').innerHTML=cases.map(x=>`<option>${x}</option>`).join('');el('case').value='rpc_lower';
const names={same_corner:'同一墙角',different_corner:'不同墙角／细节',same_bottom_tentative:'下端暂定同处',different_upper_target:'不同上端目标'};
function options(){const rr=data.filter(r=>r.case_id===el('case').value&&r.metric===el('metric').value);el('relation').innerHTML=rr.map((r,i)=>`<option value="${i}">${r.query.join(':')} → ${r.candidate.join(':')} · ${names[r.relation]}</option>`).join('');const k=rr.findIndex(r=>r.query[0]==='R02452'&&r.candidate[0]==='R01557'&&r.candidate[1]===4);if(k>=0)el('relation').value=String(k);draw();}
function draw(){const rr=data.filter(r=>r.case_id===el('case').value&&r.metric===el('metric').value),r=rr[Number(el('relation').value)];if(!r){el('scene').innerHTML='';el('description').textContent='此侧别没有已审核关系，不记为零错误。';el('rows').innerHTML='';el('detail').textContent='';return;}
let shapes=r.photo?`<image href="${r.photo}" width="1024" height="512"/>`:'';
r.records.forEach((rec,k)=>{const mid=r[k?'candidate':'query'][1],idx=r[k?'candidate_neighbor_indices':'query_neighbor_indices'],color=k?'#ca70ff':'#ffe066';[...idx,mid].forEach(j=>{for(let s=0;s<2;s++){const [x,y]=rec.points[2*j+s],major=j===mid;shapes+=`<circle cx="${x}" cy="${y}" r="${major?3:1.8}" fill="${color}" stroke="#222" stroke-width=".5"/><text x="${x+(k?4:-4)}" y="${y+(major?-4:6)}" text-anchor="${k?'start':'end'}" font-size="4.5" fill="${color}" stroke="#222" stroke-width=".18" paint-order="stroke">${k?'C':'Q'}源${rec.source_pair_indices[j]+1}${major?'本点':'邻点'}</text>`;}});});
el('scene').innerHTML=shapes;el('scene').setAttribute('viewBox',full?'0 0 1024 512':'90 60 260 400');
el('description').textContent=`${names[r.relation]}；环状态：${r.order_status.join(' / ')}。当前查询${r.query.join(':')}；角度单位为度。排名只表示所用数值排序。`;
const tau=el('tau').valueAsNumber,valid=el('tau').value!==''&&Number.isFinite(tau)&&tau>=0&&tau<=180;const rows=rr.filter(x=>x.query.join(':')===r.query.join(':')&&x.candidate[0]===r.candidate[0]);el('rows').innerHTML=rows.map(x=>`<tr><td>${x.candidate.join(':')}</td><td>${names[x.relation]}</td><td>${x.anchor_deg.toFixed(4)}</td><td>${x.neighbor_deg.toFixed(4)}</td><td>${x.combined_deg.toFixed(4)}</td><td>${x.anchor_rank} → ${x.combined_rank}</td><td>${valid?`${x.anchor_deg<=tau?'兼容':'排除'} ／ ${x.combined_deg<=tau?'兼容':'排除'}`:'请输入0—180°'}</td></tr>`).join('');el('detail').textContent=JSON.stringify(r,null,2);}
el('case').onchange=options;el('metric').onchange=options;el('relation').onchange=draw;el('tau').oninput=draw;el('zoom').onclick=()=>{full=!full;draw()};options();</script></html>'''
    (out/'index.html').write_text(body.replace('__DATA__', json.dumps(payload, ensure_ascii=False).replace('</','<\\/')), encoding='utf-8')


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    human = json.loads(HUMAN.read_text(encoding='utf-8'))
    pools = {code: json.loads((INPUT/(code+'.json')).read_text(encoding='utf-8'))['records'] for code in IMAGES}
    before = copy.deepcopy(pools)
    rows, nearest, inventory = [], [], []
    for code, records in pools.items():
        inventory.append(dict(image=code, records=len(records),
            pairs=sum(len(r['points'])//2 for r in records),
            order_states=dict(Counter(r['order_status'] for r in records)),
            confirmed_rings=sum(r['ring_confirmed'] is True for r in records)))
    for review in human['reviews']:
        code = review['image']; records = pools[code]; source = {r['id']: r for r in records}
        for rid, index in zip(review['record_ids'], review['processed_pair_indices'], strict=True):
            query = source[rid]; a = np.asarray(query['points'], float).reshape(-1, 2, 2)
            for other in records:
                if other['worker'] == query['worker']:
                    continue
                b = np.asarray(other['points'], float).reshape(-1, 2, 2)
                for metric in ['pair', 'top', 'bottom']:
                    candidates = []
                    for j in range(len(b)):
                        r = dict(case_id=review['case_id'], image=code, metric=metric,
                            query=[rid, index], candidate=[other['id'], j],
                            source_pair_indices=[query['source_pair_indices'][index], other['source_pair_indices'][j]],
                            order_status=[query['order_status'], other['order_status']],
                            relation=reviewed_relation(review, (rid, index), (other['id'], j), metric),
                            **compare_context(a, index, b, j, metric))
                        r['neighbor_source_pair_indices'] = [
                            [query['source_pair_indices'][k] for k in r['query_neighbor_indices']],
                            [other['source_pair_indices'][k] for k in r['candidate_neighbor_indices']]]
                        candidates.append(r)
                    for r in candidates:
                        for name in ['anchor', 'combined']:
                            value = r[name+'_deg']
                            r[name+'_rank'] = 1+sum(c[name+'_deg'] < value-1e-9 for c in candidates)
                        rows.append(r)
                    nearest.append(dict(case_id=review['case_id'], query=[rid, index],
                        target_record=other['id'], metric=metric,
                        anchor_nearest=[r['candidate'] for r in candidates if r['anchor_rank'] == 1],
                        combined_nearest=[r['candidate'] for r in candidates if r['combined_rank'] == 1],
                        candidate_count=len(candidates), policy='rank only, no identity prediction'))
    assert pools == before
    reviewed = [r for r in rows if r['relation'] != 'unreviewed']
    gates = []
    for (case, metric, relation) in sorted({(r['case_id'], r['metric'], r['relation']) for r in reviewed}):
        group = [r for r in reviewed if (r['case_id'], r['metric'], r['relation']) == (case, metric, relation)]
        for tau in THRESHOLDS:
            gates.append(dict(case_id=case, metric=metric, relation=relation, threshold_deg=tau,
                directed_comparisons=len(group), anchor_compatible=sum(r['anchor_deg'] <= tau for r in group),
                combined_compatible=sum(r['combined_deg'] <= tau for r in group),
                removed=[dict(query=r['query'], candidate=r['candidate']) for r in group
                         if r['anchor_deg'] <= tau < r['combined_deg']]))
    dump(out/'comparisons.json', dict(schema='point_context_probe_v1', rows=rows, nearest=nearest))
    dump(out/'reviewed_comparisons.json', reviewed)
    dump(out/'threshold_checks.json', gates)
    dump(out/'threshold_sensitivity.json', threshold_sensitivity(reviewed))
    dump(out/'subdivision_control.json', subdivision_control())
    build_view(out, pools, reviewed)
    dump(out/'field_contract.json', dict(
        anchor_deg='Continuous ERP spherical endpoint distance; pair means max(top,bottom).',
        neighbor_deg='Min over forward/reverse alignments of max of two immediate-neighbor distances.',
        combined_deg='max(anchor_deg,neighbor_deg); conjunctive baseline, not learned score or physical identity.',
        ranks='1 + count strictly closer candidates in the same target record; all 1e-9 degree ties preserved.',
        relation='Human ledger scope only; different_upper_target is not a general corner-identity label; bottom tentative retained.',
        direction='Each query direction is saved; reciprocal observations are not independent samples.',
        threshold_sensitivity='All empirical score-event intervals per case/metric. Development separation is [max positive,min negative), only when both classes exist; never a recommended clustering threshold.',
        source='Archived complete input snapshots, no GT, no source mutation, no vote/fusion/ring generation.',
        interpretation='Finite development probe; one-hop comparison does not solve two-versus-three path equivalence.'))
    dump(out/'checks.json', dict(inventory=inventory, original_records_unchanged=pools == before,
        comparisons=len(rows), reviewed_directed_comparisons=len(reviewed), record_metric_queries=len(nearest),
        unreviewed_comparisons=len(rows)-len(reviewed), thresholds_calibrated=False,
        plan='research/point_context_probe_20261006/PLAN.md', human_source=str(HUMAN.relative_to(ROOT)).replace('\\','/'),
        reference_files_read=False, predicted_identities=False, new_full_layout=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    run(parser.parse_args().out)
