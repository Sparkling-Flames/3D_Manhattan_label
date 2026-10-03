"""真实 BEV 共识教学演示：确定性成员链、当前前缀重切 tile、保留失败与平票。"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import warnings

import numpy as np
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

from .lee_tile_stage1_20261002 import ROOT, METHODS, tile_consensus, region_iou, write_json, write_csv
from .lee_tile_precision_20261003 import integration_basis, measure_masks, subset_mask

SOURCE = ROOT / 'analysis_results/lee_expanded_20261003'
OUT = ROOT / 'analysis_results/lee_consensus_demos_20261003'


def build_case(records, references):
    """展示计算全由当前成员重新切片；全池基底仅用于事后交叉核验。"""
    if records != sorted(records, key=lambda r: r['id']):
        raise ValueError('demo_requires_record_id_order')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        basis = integration_basis(records, references)
    notices = [dict(stage='offline_basis', message=s) for s in basis['warnings']]
    notices.extend(dict(stage='offline_basis_evaluation', message=str(w.message)) for w in caught)
    steps = []; max_geometry = 0.; max_iou = 0.
    for k in range(1, len(records) + 1):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            current = tile_consensus(records[:k])
            notices.extend(dict(stage='current_tiling', k=k, message=s) for s in current['warnings'])
            counts = current['mesh']['votes'].sum(axis=0)
            tie = unary_union([tile for tile, s in zip(current['mesh']['tiles'], counts) if 2*s == k])
            step = dict(k=k, members=[r['id'] for r in records[:k]],
                        tiles=[dict(geometry=mapping(t), support=int(s)) for t, s in zip(current['mesh']['tiles'], counts)],
                        tile_count=len(counts), tie_geometry=mapping(tie), tie_area_h2=float(tie.area),
                        regions={}, metrics={})
            for method in METHODS:
                region = current['regions'][method]
                offline_counts = basis['mesh']['votes'][:k].sum(axis=0)
                selected = 2*offline_counts >= k if method == 'mv50' else 2*offline_counts > k
                offline = unary_union([t for t, keep in zip(basis['mesh']['tiles'], selected) if keep])
                geometry_error = float(region.symmetric_difference(offline).area)
                if geometry_error > 1e-9 * max(1., float(basis['area'].sum())):
                    raise ValueError('current_prefix_geometry_mismatch')
                max_geometry = max(max_geometry, geometry_error)
                measured = measure_masks(basis, np.array([subset_mask(range(k))], dtype=np.uint32), k, method)
                step['regions'][method] = mapping(region)
                step['metrics'][method] = {}
                for version, gt in basis['references'].items():
                    iou = region_iou(region, gt)
                    error = abs(iou - float(measured[version][0]))
                    if error > 1e-10:
                        raise ValueError('current_prefix_iou_mismatch')
                    max_iou = max(max_iou, error)
                    step['metrics'][method][version] = dict(iou=iou, area_h2=float(region.area),
                        omission_h2=float(gt.difference(region).area), extension_h2=float(region.difference(gt).area),
                        empty=region.is_empty)
            notices.extend(dict(stage='evaluation', k=k, message=str(w.message)) for w in caught)
            steps.append(step)
    return dict(steps=steps, warnings=notices, checks=dict(prefixes_rebuilt=len(records),
        region_comparisons=2*len(records), max_geometry_difference_h2=max_geometry, max_iou_difference=max_iou))


def choose_examples(curves):
    rows = [r for r in curves if r['version'] == 'original' and r['method'] == 'mv50'
            and int(r['k']) == int(r['n']) and int(r['n']) >= 8]
    rows.sort(key=lambda r: (float(r['gain_from_one']), r['image']))
    strict = {r['image']: r for r in curves if r['version'] == 'original' and r['method'] == 'mv_strict'
              and int(r['k']) == int(r['n'])}
    even = [r for r in rows if int(r['n']) % 2 == 0]
    tie = max(even, key=lambda r: (abs(float(r['iou_mean'])-float(strict[r['image']]['iou_mean'])), r['image']))
    return [(rows[-1], '较大改善', 'N≥8图中全员MV50减全池单人均值最大'),
            (rows[len(rows)//2], '增益中位附近', 'N≥8图按同一增益排序取上中位；不代表所有属性典型'),
            (rows[0], '接近参考变差', 'N≥8图中全员MV50减全池单人均值最小'),
            (tie, '平票规则敏感', 'N≥8且N为偶数，取全员两规则原参考IoU绝对差最大')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args(); out = args.out
    if out.exists():
        raise ValueError('use_new_output_directory')
    out.mkdir(parents=True)
    data = json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    rosters = {r['image']: r for r in json.loads((SOURCE/'rosters.json').read_text(encoding='utf-8'))}
    images = {r['code']: r for r in data['images']}
    with (SOURCE/'image_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
        curves = list(csv.DictReader(stream))
    selection = choose_examples(curves)
    write_json(out/'design.json', dict(schema='lee_consensus_demos_v1', status='started',
        input='analysis_results/lee_expanded_20261003/input.json',
        source_binding='analysis_results/lee_expanded_20261003/source_binding.json',
        selection=[dict(image=r['image'], purpose=title, reason=reason) for r,title,reason in selection],
        member_chain='Ascending fixed record ID; never searched for best chain. User-confirmed independent repeated geometry retains separate votes.',
        interpretation='Post-outcome teaching examples, not an unbiased estimate of fusion benefit.',
        no_new_preprocessing=True, gt_used_in_votes=False))
    demos = []; rows = []; notices = []; failures = []
    for chosen, title, reason in selection:
        code = chosen['image']; image = images[code]; roster = rosters[code]
        by_id = {r['id']: r for r in image['annotations']}
        records = [by_id[i] for i in roster['record_ids']]
        if [r['worker'] for r in records] != roster['workers']:
            raise ValueError('roster_worker_binding_mismatch:'+code)
        references = {r['version']: r['footprint'] for r in image['references']}
        try:
            case = build_case(records, references)
        except Exception as exc:
            failures.append(dict(image=code, error=type(exc).__name__+': '+str(exc), roster_n=len(records)))
            write_json(out/'failures.json', failures)
            raise
        notices.extend(dict(image=code, **w) for w in case.pop('warnings'))
        gts = {v: Polygon(p) for v,p in references.items() if p is not None}
        full = case['steps'][-1]
        full_difference = abs(full['metrics']['mv50']['original']['iou']-float(chosen['iou_mean']))
        singles = [region_iou(Polygon(r['footprint']), gts['original']) for r in records]
        original_rows = [r for r in curves if r['image'] == code and r['version'] == 'original']
        baseline = next(float(r['iou_mean']) for r in original_rows if r['method']=='mv50' and int(r['k'])==1)
        if full_difference > 1e-10 or abs(float(np.mean(singles))-baseline) > 1e-10:
            raise ValueError('saved_A_line_endpoint_mismatch:'+code)
        photo = ROOT/'data/mp3d_layout/test/img'/(image['image_id']+'.png')
        photo_rel = os.path.relpath(photo, out).replace('\\', '/') if photo.exists() else None
        demo = dict(image=code, title=title, selection_reason=reason, n=len(records), difficulty=image['difficulty'],
            building=image['building'], scene=image['scene'], photo=photo_rel,
            photo_source=photo.relative_to(ROOT).as_posix() if photo.exists() else None,
            references={v:mapping(g) for v,g in gts.items()},
            workers=[dict(id=r['id'], worker=r['worker'], geometry=mapping(Polygon(r['footprint'])),
                original_iou=score, order_status=r['order_status'], ring_confirmed=r['ring_confirmed']) for r,score in zip(records,singles)],
            single_mean=baseline, single_best=max(singles), full_gain=float(chosen['gain_from_one']),
            mean_curve=[dict(k=int(r['k']), method=r['method'], iou=float(r['iou_mean']),
                mc_error=float(r['mc_error_bound']), estimator=r['estimator']) for r in original_rows], **case)
        for step in case['steps']:
            for method in METHODS:
                for version, metrics in step['metrics'][method].items():
                    rows.append(dict(image=code, k=step['k'], method=method, version=version,
                        members='|'.join(step['members']), tile_count=step['tile_count'], tie_area_h2=step['tie_area_h2'], **metrics))
        demos.append(demo)
        print(code, 'prefixes', len(case['steps']), 'full gain', chosen['gain_from_one'], flush=True)
    write_json(out/'demos.json', demos); write_csv(out/'metrics.csv', rows)
    write_json(out/'warnings.json', notices); write_json(out/'failures.json', failures)
    checks = dict(status='passed', examples=len(demos), prefixes=sum(d['n'] for d in demos),
        region_comparisons=sum(d['checks']['region_comparisons'] for d in demos),
        max_geometry_difference_h2=max(d['checks']['max_geometry_difference_h2'] for d in demos),
        max_iou_difference=max(d['checks']['max_iou_difference'] for d in demos),
        warnings=len(notices), failures=len(failures), source_status='Reused frozen source binding and roster; no raw resubmission audit',
        visual_status='Panoramas provided for inspection; no new visual GT adjudication')
    write_json(out/'checks.json', checks)
    write_json(out/'field_contract.json', dict(schema='lee_consensus_demos_v1',
        metrics_fields=list(rows[0]), coordinates='Common camera BEV X,Z in h units; area h². Equal aspect and per-image fixed extent.',
        chain='Nested prefixes of ascending record IDs; deterministic teaching replay, not average/optimal chain.',
        mean_curve='Unchanged A-line uniform-member-set mean; exact or 16384-draw MC marked individually. Not this chain.',
        tie='Area supported by exactly k/2 current members; MV50 retains it and strict majority omits it.',
        photos='Local original PNGs referenced by repository-relative paths; copied demo folder alone is insufficient for photographs.',
        failures='No failed member is dropped; error stops calculation and writes failures.json.',
        selection='Post-outcome selection from N>=8 A-line images for illustration; no inference across these four examples.'))
    (out/'index.html').write_text(HTML.replace('__DATA__', json.dumps(demos, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')), encoding='utf-8', newline='\n')
    report(demos, checks, out)
    design = json.loads((out/'design.json').read_text(encoding='utf-8')); design['status']='completed'; write_json(out/'design.json', design)


def report(demos, checks, out):
    lines = ['# Lee 等权区域融合：四个真实数据演示', '',
        '当前可以固定作为研究基线的是：既有预处理与环序 → 声明BEV足迹 → 当前成员边界切tile → 人人等权投票。MV50保留支持率≥50%的区域，严格多数保留>50%；GT仅用于评价。它输出区域，不保证单连通、无孔或完整可重建的Manhattan layout。', '',
        '## 演示内容与选例', '',
        '打开[index.html](index.html)，可切换四例、当前人数、MV50／严格多数、GT／成员层、单个成员及支持人数tile。相机原点、相同轴比例和每图固定范围保留。原全景图沿仓库相对路径显示，仅提供视觉参照，尚未新增GT视觉裁决。', '',
        '**按既有结果选例用于解释，不能当作四图总体效果估计。** 最大／中位／最小增益均在已有A线N≥8图片中，以全员MV50减全池单人均值选出；平票例取偶数N中两规则全员IoU差最大。成员按固定R编号升序进入，未搜索有利链。图中的细虚线是这条链，粗实线是已有成员集合均值，二者不可混用。', '',
        '| 目的 | 图片 | N | 全池单人均值 | 全员MV50 | 全员严格多数 | MV50增益 | 最好单人 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for d in demos:
        m=d['steps'][-1]['metrics']
        lines.append(f"| {d['title']} | {d['image']} | {d['n']} | {d['single_mean']:.6f} | {m['mv50']['original']['iou']:.6f} | {m['mv_strict']['original']['iou']:.6f} | {d['full_gain']:+.6f} | {d['single_best']:.6f} |")
    lines += ['', '## 实测结果能说明什么', '',
        '- 当前真实输入的每个前缀都重新切tile，并与全池细分积分在形状和IoU上对照。计算正确性与质量提升是两件事；上表同时保留改善、下降和平票敏感例。',
        '- 不要求超过最好单人；最好单人需事后GT才能识别。若声称融合比随机单人好，应使用全池单人均值及完整图片面板，不能只拿链的第一个人作基线。',
        '- MV50奇→偶只能扩张、偶→奇只能收缩，严格多数相反；IoU如何变化仍取决于扩张／收缩位置。原始曲线不平滑。',
        '- 重复几何按用户确认的独立作答保留，不合并票、不更改人员资格。确认环保留，其余沿用已有共享x默认环，不重新预处理。',
        '- 融合算法已足以开展当前区域共识实验；当前结果没有证明它是最优融合、完整3D重建或自动标注替代，也没有证明加人必然更好。', '',
        '## 验证与追溯', '',
        f"本轮重新切片 {checks['prefixes']} 个前缀、核对 {checks['region_comparisons']} 个规则输出；最大形状对称差 {checks['max_geometry_difference_h2']:.3g} h²，最大IoU差 {checks['max_iou_difference']:.3g}。警告 {checks['warnings']} 条，失败 {checks['failures']} 条，均独立保存。四图k=1均值及全员MV50与既有A线结果一致。",
        '输入复用[冻结面板](../lee_expanded_20261003/input.json)、[来源绑定](../lee_expanded_20261003/source_binding.json)、[成员表](../lee_expanded_20261003/rosters.json)。本轮未重新审计原始提交链。',
        '来源、选例及固定链见design.json、demos.json；逐前缀机器指标见metrics.csv，核验见checks.json，字段见field_contract.json。每份作答的确认状态、人员ID和记录ID随演示保留。',
        '复现：`python -B -m tools.thesis_main.analysis.lee_consensus_demos_20261003 --out analysis_results/<新的目录>`。已有目录拒绝覆盖。',
        '相关测试：`python -B -m pytest tests/test_lee_consensus_demos_20261003.py tests/test_lee_tile_stage1_20261002.py tests/test_lee_tile_precision_20261003.py -q -p no:cacheprovider`。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lee 共识 · 四例实测</title>
<style>
:root{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#17293d;background:#f3f6fa}body{max-width:1320px;margin:24px auto;padding:0 20px}h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:0 0 12px}p{line-height:1.65}small,.muted{color:#53667b}button,select,input{font:inherit}button,select{border:1px solid #b9c6d4;background:white;border-radius:7px;padding:8px 11px}button{cursor:pointer}button[aria-pressed=true]{background:#173f68;color:white}nav{display:flex;gap:9px;flex-wrap:wrap;margin:18px 0}.box{background:white;border:1px solid #dee5ee;border-radius:12px;padding:18px;margin:14px 0}.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.controls label{white-space:nowrap}input[type=range]{width:230px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stat{background:#f3f6fa;border-radius:8px;padding:12px}.stat b{display:block;font-size:24px;margin:5px 0}.warning{border-left:4px solid #bb7833;padding:9px 14px;background:#fff8ed}svg{width:100%;height:auto;display:block}#bev{background:#fafbfd;border:1px solid #e8edf3;border-radius:8px}#photo{width:100%;display:block;border-radius:8px}a{color:#175f9a}details{line-height:1.7}#members{font-family:ui-monospace,monospace;font-size:12px;overflow-wrap:anywhere}#curve text{font:12px system-ui}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;margin:10px 0}.key:before{content:"";display:inline-block;width:20px;height:3px;background:var(--c);vertical-align:middle;margin-right:5px}@media(max-width:850px){.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}}
</style>
<header><h1>Lee 共识 · 四例实测</h1><p class="muted">由真实标注形成 BEV 区域，当前成员切 tile 后等权投票。GT 只作评价，不参与切片与投票。</p></header>
<div class="warning">这四例按既有结果选出，用于解释改善、下降和平票。它们不是整体效果估计；固定进入顺序也不是最优成员链。</div>
<nav id="cases" aria-label="选择真实案例"></nav>
<section class="box"><h2 id="title"></h2><p id="context" class="muted"></p>
<div class="controls"><label for="k">当前人数 <b id="klabel"></b></label><input id="k" type="range" min="1" value="1" step="1" aria-label="当前人数"><label>投票规则 <select id="method"><option value="mv50">MV50 · ≥50%</option><option value="mv_strict">严格多数 · &gt;50%</option></select></label><button id="full">全员</button></div>
<div class="stats" style="margin-top:16px"><div class="stat">当前链：共识 IoU<b id="iou"></b><small id="delta"></small></div><div class="stat">另一规则 IoU<b id="other"></b><small id="gap"></small></div><div class="stat">遗漏 / GT面积<b id="omit"></b><small>GT内未覆盖</small></div><div class="stat">外扩 / GT面积<b id="extra"></b><small>GT外增加范围</small></div></div>
</section>
<div class="grid"><section class="box"><h2>当前共识与成员</h2><div class="controls"><label><input id="showgt" type="checkbox" checked>GT</label><label><input id="showall" type="checkbox" checked>当前成员</label><label><input id="showtiles" type="checkbox">支持率 tile</label><label><input id="showtie" type="checkbox">平票区域</label></div><p><label>单体查看 <select id="person"><option value="">不突出</option></select></label> <small id="personscore"></small></p><svg id="bev" viewBox="0 0 580 500" role="img" aria-label="同坐标比例BEV叠加"></svg><div class="legend"><span class="key" style="--c:#192f47">GT虚线</span><span class="key" style="--c:#087e8b">融合</span><span class="key" style="--c:#8298af">当前成员</span><span class="key" style="--c:#d6533d">选中单体</span><span class="key" style="--c:#dd950a">平票</span></div><small id="geometrynote"></small></section>
<section class="box"><h2>人数曲线：均值与一条成员链</h2><svg id="curve" viewBox="0 0 580 350" role="img" aria-label="均值与固定成员链的IoU人数曲线"></svg><div class="legend"><span class="key" style="--c:#087e8b">MV50</span><span class="key" style="--c:#bd5f25">严格多数</span></div><p class="muted">粗实线：已有均匀成员集合均值；细虚线：本演示固定链。淡带仅为均值的计算误差界。固定链每一步是精确计算；不是均值，更不表示一般加入顺序。</p><p id="meanvalue"></p><details><summary>成员与计算追溯</summary><p id="members"></p><p id="verification"></p></details></section></div>
<section class="box"><h2>对应原全景图</h2><img id="photo" alt="当前案例原始全景图"><p class="muted">本地原图按 image_id 对应，仅作观察参照。本页不将 BEV 共识强行投回完整三维，也未重新裁决 GT 的视觉正确性。图片需保留仓库 data 目录。</p></section>
<section class="box"><h2>如何判断“有效”</h2><p>计算层面：每个当前前缀重新切 tile，对照全池积分的形状和 IoU。研究层面：看相对全池单人均值的收益，并保留下降与平票敏感结果。融合不保证超过最好单人、不保证人数增加时单调改善，也不等于完整 layout 或三维质量。</p><p><a href="REPORT.md">中文报告</a> · <a href="metrics.csv">逐步指标 CSV</a> · <a href="checks.json">实测核验</a> · <a href="demos.json">完整几何与来源</a> · <a href="warnings.json">警告</a></p></section>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';let selected=0;
function elt(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!=null)e.textContent=text;return e}
function rings(g){if(g.type==='Polygon')return g.coordinates;if(g.type==='MultiPolygon')return g.coordinates.flat();if(g.type==='GeometryCollection')return g.geometries.flatMap(rings);return[]}
function area(g){const absRing=r=>Math.abs(r.reduce((s,p,i)=>s+p[0]*r[(i+1)%r.length][1]-r[(i+1)%r.length][0]*p[1],0))/2;const poly=r=>r.length?absRing(r[0])-r.slice(1).reduce((s,x)=>s+absRing(x),0):0;return g.type==='Polygon'?poly(g.coordinates):g.type==='MultiPolygon'?g.coordinates.reduce((s,p)=>s+poly(p),0):0}
function path(g,project){return rings(g).map(r=>r.map((p,i)=>(i?'L':'M')+project(p).join(',')).join(' ')+'Z').join(' ')}
function polygon(svg,g,project,attrs){svg.append(elt('path',{d:path(g,project),'fill-rule':'evenodd',...attrs}))}
function changeCase(i){selected=i;const d=DATA[i];$('k').max=d.n;$('k').value=d.n;$('person').value='';document.querySelectorAll('nav button').forEach((b,j)=>b.setAttribute('aria-pressed',String(j===i)));$('title').textContent=d.title+' · '+d.image;$('context').textContent=`${d.n}位独立人员 · 粗难度：${d.difficulty} · ${d.selection_reason}。全员MV50相对全池单人均值：${d.full_gain>=0?'+':''}${d.full_gain.toFixed(4)}。`;$('photo').src=d.photo||'';$('photo').hidden=!d.photo;render()}
function render(){const d=DATA[selected],k=+$('k').value,s=d.steps[k-1],method=$('method').value,other=method==='mv50'?'mv_strict':'mv50',m=s.metrics[method].original,o=s.metrics[other].original,ga=area(d.references.original);$('klabel').textContent=`${k} / ${d.n}`;$('iou').textContent=m.iou.toFixed(4);$('delta').textContent=`全池单人均值 ${d.single_mean.toFixed(4)} · 最好单人 ${d.single_best.toFixed(4)}`;$('other').textContent=o.iou.toFixed(4);$('gap').textContent=`当前规则 − 另一规则 ${(m.iou-o.iou).toFixed(4)}`;$('omit').textContent=(100*m.omission_h2/ga).toFixed(1)+'%';$('extra').textContent=(100*m.extension_h2/ga).toFixed(1)+'%';
const p=$('person'),previous=p.value;p.replaceChildren(new Option('不突出',''));d.workers.slice(0,k).forEach((w,i)=>p.add(new Option(`${i+1}. ${w.worker} / ${w.id}`,w.id)));p.value=previous;if(p.selectedIndex<0)p.value='';const chosen=d.workers.find(w=>w.id===p.value);$('personscore').textContent=chosen?`单体IoU ${chosen.original_iou.toFixed(4)} · ${chosen.ring_confirmed?'人工确认环':'默认环'}`:'';
const points=[...d.workers.flatMap(w=>rings(w.geometry).flat()),...rings(d.references.original).flat(),[0,0]];const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys),scale=Math.min(500/(xmax-xmin||1),400/(ymax-ymin||1)),project=p=>[290+(p[0]-(xmin+xmax)/2)*scale,240-(p[1]-(ymin+ymax)/2)*scale];const svg=$('bev');svg.replaceChildren();if($('showtiles').checked)s.tiles.forEach(t=>polygon(svg,t.geometry,project,{fill:`rgba(8,126,139,${.05+.55*t.support/k})`,stroke:'#7c8b9b','stroke-width':.25}));else polygon(svg,s.regions[method],project,{fill:'#52bbba',opacity:.3,stroke:'none'});
if($('showall').checked)d.workers.slice(0,k).forEach(w=>polygon(svg,w.geometry,project,{fill:'none',stroke:'#8298af','stroke-width':1,opacity:.6}));if($('showtie').checked)polygon(svg,s.tie_geometry,project,{fill:'#efae24',opacity:.55,stroke:'#c67c00','stroke-width':1});polygon(svg,s.regions[method],project,{fill:'none',stroke:'#087e8b','stroke-width':2.7});if($('showgt').checked)polygon(svg,d.references.original,project,{fill:'none',stroke:'#192f47','stroke-width':2.1,'stroke-dasharray':'7 5'});if(chosen)polygon(svg,chosen.geometry,project,{fill:'none',stroke:'#d6533d','stroke-width':2.5});const camera=project([0,0]);svg.append(elt('circle',{cx:camera[0],cy:camera[1],r:3,fill:'#17293d'}));svg.append(elt('text',{x:camera[0]+6,y:camera[1]-6,fill:'#17293d','font-size':11},'相机 (0,0)'));svg.append(elt('line',{x1:40,y1:465,x2:40+scale,y2:465,stroke:'#17293d','stroke-width':2}));svg.append(elt('text',{x:40,y:484,fill:'#17293d','font-size':12},'1 h · X 向右，Z 向上 · 全人数固定范围 / 等比例'));$('geometrynote').textContent=`${s.tile_count}个当前tile；恰好半数支持面积 ${s.tie_area_h2.toFixed(4)} h²。${m.empty?'当前融合为空。':''}非连通和孔洞按原样保留。`;
const chart=$('curve');chart.replaceChildren();const cx=j=>48+(j-1)*510/(d.n-1),cy=v=>292-v*250;for(let j=0;j<=5;j++){const y=cy(j/5);chart.append(elt('line',{x1:48,y1:y,x2:558,y2:y,stroke:'#e0e7ef'}));chart.append(elt('text',{x:16,y:y+4,fill:'#53667b'},(j/5).toFixed(1)))}for(const j of [...new Set([1,k,d.n,...Array.from({length:Math.floor(d.n/4)},(_,i)=>(i+1)*4)])].sort((a,b)=>a-b))chart.append(elt('text',{x:cx(j)-4,y:317,fill:'#53667b'},j));for(const [method,color]of[['mv50','#087e8b'],['mv_strict','#bd5f25']]){const r=d.mean_curve.filter(r=>r.method===method).sort((a,b)=>a.k-b.k);const band=r.map(q=>[cx(q.k),cy(Math.min(1,q.iou+q.mc_error))]).concat([...r].reverse().map(q=>[cx(q.k),cy(Math.max(0,q.iou-q.mc_error))]));chart.append(elt('polygon',{points:band.map(p=>p.join(',')).join(' '),fill:color,opacity:.09}));chart.append(elt('polyline',{points:r.map(q=>`${cx(q.k)},${cy(q.iou)}`).join(' '),fill:'none',stroke:color,'stroke-width':2.6}));chart.append(elt('polyline',{points:d.steps.map(q=>`${cx(q.k)},${cy(q.metrics[method].original.iou)}`).join(' '),fill:'none',stroke:color,'stroke-width':1.2,'stroke-dasharray':'4 4',opacity:.7}));chart.append(elt('circle',{cx:cx(k),cy:cy(s.metrics[method].original.iou),r:4,fill:color}))}chart.append(elt('line',{x1:cx(k),y1:38,x2:cx(k),y2:292,stroke:'#768b9f','stroke-dasharray':'2 3'}));chart.append(elt('text',{x:7,y:20,fill:'#53667b'},'BEV IoU'));chart.append(elt('text',{x:518,y:341,fill:'#53667b'},'人数 k'));const mu=d.mean_curve.find(q=>q.k===k&&q.method===method);$('meanvalue').textContent=`当前k的集合均值：${mu.iou.toFixed(4)}；${mu.estimator==='exact'?'精确枚举':`MC计算误差界 ±${mu.mc_error.toFixed(4)}`}。这与当前链IoU ${m.iou.toFixed(4)} 是不同量。`;$('members').textContent=d.workers.slice(0,k).map(w=>`${w.worker}(${w.id})`).join(' → ');$('verification').textContent=`每一步已重切tile；本例 ${d.checks.region_comparisons} 个区域核对。最大形状差 ${d.checks.max_geometry_difference_h2.toExponential(2)} h²，最大IoU差 ${d.checks.max_iou_difference.toExponential(2)}。`;}
DATA.forEach((d,i)=>{const b=document.createElement('button');b.textContent=d.title;b.onclick=()=>changeCase(i);$('cases').append(b)});['k','method','person','showgt','showall','showtiles','showtie'].forEach(id=>$(id).addEventListener('input',render));$('full').onclick=()=>{$('k').value=DATA[selected].n;render()};changeCase(0);
</script></html>'''


if __name__ == '__main__':
    main()
