"""uNb真实点集对照表；不推定墙体连线、不改标注、不重定义收敛。"""
import base64
import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / 'analysis_results/research_validation_20260909_v2/annotation_review'
BUILDING = 'uNb9QFRL6hY'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build():
    base = ROOT / 'analysis_results/research_validation_20260909_v2'
    images = [r for r in read_csv(base / 'features/image_feature_audit.csv')
              if r['building_id'] == BUILDING and float(r['common_n']) >= 19]
    images.sort(key=lambda r: r['image_id'])
    assert len(images) == 12
    ids = {r['image_id'] for r in images}
    source = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
    with gzip.open(source, 'rt', encoding='utf8') as f:
        responses = [json.loads(line) for line in f]
    responses = [r for r in responses if r['image_id'] in ids and r['assistance_exposure'] == 'none']
    assert len({(r['image_id'], r['worker_id']) for r in responses}) == len(responses)
    geometry = {r['canonical_annotation_id']: r for r in read_csv(
        ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/revised/with_workers/geometry/response_geometry.csv')}
    onsets = [r for r in read_csv(base / 'stages/image_stage_onsets.csv')
              if r['image_id'] in ids and r['kind'] == 'anchor_stage' and r['config'] == 'q_0.950' and r['horizon'] == '23']
    diagnostics = {r['image_id']: r for r in read_csv(base / 'stages/stage_failure_diagnostics.csv')
                   if r['mode'] == 'with_workers' and r['config'] == 'q_0.950'}
    partitions = {mode: {r['image_id']: r for r in read_csv(ROOT / f'analysis_results/multibuilding_threshold_stability_20260909_v1/revised/{mode}/geometry/full_q_partitions.csv')
                        if float(r['threshold']) == .95 and r['image_id'] in ids}
                  for mode in ('with_workers', 'without_workers')}
    curves = []
    with gzip.open(base / 'stages/stage_curves.csv.gz', 'rt', encoding='utf8', newline='') as f:
        for r in csv.DictReader(f):
            if r['image_id'] in ids and r['kind'] == 'anchor_stage' and r['config'] == 'q_0.950' and r['horizon'] == '23' and r['k'] == '18':
                curves.append(r)
    common = set.intersection(*[{r['worker_id'] for r in responses if r['image_id'] == i and r['unassisted_manual_included']} for i in ids])
    defaults = sorted(common, key=int)[:3]
    workers = sorted({r['worker_id'] for r in responses}, key=int)
    cards, summary, annotations, cluster_rows = [], [], [], []
    for number, item in enumerate(images, 1):
        image_id = item['image_id']
        rr = sorted([r for r in responses if r['image_id'] == image_id], key=lambda r: int(r['worker_id']))
        counts = Counter(r['effective_point_count'] for r in rr if r['unassisted_manual_included'])
        entries = {}
        invalid = []
        for r in rr:
            g = geometry.get(r['canonical_annotation_id'])
            if r['unassisted_manual_included']:
                assert g is not None, r['canonical_annotation_id']
            for field, count in [('raw_points_1024x512', 'raw_point_count'), ('effective_points_1024x512', 'effective_point_count')]:
                if r[field] is not None:
                    assert len(r[field]) == r[count]
                    assert all(len(p) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in r[field])
            entry = dict(worker=r['worker_id'], canonical=r['canonical_annotation_id'], raw=r['raw_points_1024x512'],
                         effective=r['effective_points_1024x512'], raw_n=r['raw_point_count'], effective_n=r['effective_point_count'],
                         included=r['unassisted_manual_included'], processing=r['processing_status'], excluded=r['exclusion_reason'],
                         q_valid=None if g is None else g['q_geometry_valid'].lower() == 'true',
                         q_reason='' if g is None else g['q_geometry_reason'], stage=r['stage'],
                         imputed=r['imputed_point'], source=r['raw_export_path'], identity=r['annotation_identity'])
            entries[r['worker_id']] = entry
            if entry['q_valid'] is False:
                reason = '奇数点，当前q无法构造所需几何配对' if entry['q_reason'] == 'odd_keypoint_count' else entry['q_reason']
                invalid.append(f"W{r['worker_id']}：{r['effective_point_count']}点；{reason}")
            annotations.append(dict(image_number=number, image_id=image_id, worker_id=r['worker_id'],
                                    canonical_annotation_id=entry['canonical'], annotation_identity=entry['identity'],
                                    raw_export_path=entry['source'], raw_points_json=json.dumps(entry['raw']),
                                    effective_points_json=json.dumps(entry['effective']), raw_point_count=entry['raw_n'],
                                    effective_point_count=entry['effective_n'], unassisted_manual_included=entry['included'],
                                    processing_status=entry['processing'], exclusion_reason=entry['excluded'],
                                    q_geometry_valid=entry['q_valid'], q_geometry_reason=entry['q_reason']))
        evidence = {r['mode']: dict(onset=r, last=next(c for c in curves if c['image_id'] == image_id and c['mode'] == r['mode']))
                    for r in onsets if r['image_id'] == image_id}
        assert set(evidence) == {'with_workers', 'without_workers'}
        image_path = Path(item['image_path'])
        assert image_path.is_file() and image_path.suffix.lower() == '.png'
        png = image_path.read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        assert int.from_bytes(png[16:20], 'big') == 2 * int.from_bytes(png[20:24], 'big'), 'panorama aspect ratio mismatch'
        diag = diagnostics[image_id]
        ambiguous = int(float(diag.get('final_non_unique') or 0))
        partition_note = (f"含W19/W26、完整共同预算N={int(float(item['common_n']))}时，{ambiguous}/200次分区为多解。"
                          '这是完整预算的定位记录；图中H=23的逐前缀判定另列。') if ambiguous else ''
        display_partitions = {}
        by_canonical = {a['canonical']: a for a in entries.values()}
        for mode in partitions:
            saved = partitions[mode][image_id]
            candidates = json.loads(saved['candidate_partitions_json'])
            eligible = {a['canonical'] for a in entries.values() if a['included'] and a['q_valid']
                        and (mode == 'with_workers' or a['worker'] not in ('19', '26'))}
            converted = []
            for ci, candidate in enumerate(candidates, 1):
                flat = [aid for group in candidate for aid in group]
                assert len(flat) == len(set(flat)) and set(flat) == eligible
                groups = []
                for group in candidate:
                    members = [by_canonical[aid] for aid in group]
                    assert len({a['effective_n'] for a in members}) == 1, 'different counts in same cluster'
                    groups.append(sorted([a['worker'] for a in members], key=int))
                groups.sort(key=lambda g: (-len(g), tuple(map(int, g))))
                converted.append(groups)
                for gi, group in enumerate(groups, 1):
                    for worker in group:
                        cluster_rows.append(dict(image_id=image_id, mode=mode, q=.95, candidate=ci, group=gi,
                                                 supported=len(group) >= 2, group_people=len(group), worker_id=worker,
                                                 canonical_annotation_id=entries[worker]['canonical'], effective_point_count=entries[worker]['effective_n'],
                                                 full_image_status=saved['full_image_status'], partition_scope=saved['partition_scope']))
            assert len(candidates) == int(float(saved['candidate_partition_count']))
            display_partitions[mode] = dict(status=saved['full_image_status'], scope=saved['partition_scope'],
                                           truncated=saved['enumeration_truncated'].lower() == 'true', candidates=converted,
                                           pointset_n=int(saved['pointset_n']), q_valid_n=int(saved['q_valid_n']),
                                           unassigned=[a['worker'] for a in entries.values() if a['included'] and a['q_valid'] is False
                                                       and (mode == 'with_workers' or a['worker'] not in ('19', '26'))])
        cards.append(dict(number=number, id=image_id, short=image_id.split('_')[1][:8],
                          image='data:image/png;base64,' + base64.b64encode(png).decode('ascii'),
                          image_path=str(image_path), responses=entries, counts=dict(sorted(counts.items())),
                          included=sum(r['unassisted_manual_included'] for r in rr), total=len(rr),
                          q_valid_people=sum(a['q_valid'] is True for a in entries.values()),
                          common_n=int(float(item['common_n'])), invalid=invalid, partition_note=partition_note,
                          partitions=display_partitions, evidence=evidence))
        summary.append(dict(image_number=number, image_id=image_id, image_path=str(image_path),
                            available_unassisted_people=len(rr), included_people=cards[-1]['included'],
                            q_geometry_valid_people=cards[-1]['q_valid_people'],
                            common_replay_budget=cards[-1]['common_n'], effective_count_people=json.dumps(cards[-1]['counts']),
                            q_invalid_responses=' | '.join(invalid), full_budget_partition_note=partition_note,
                            onset_with_workers=evidence['with_workers']['onset']['identified'],
                            onset_status_with_workers=evidence['with_workers']['onset']['status'],
                            onset_without_workers=evidence['without_workers']['onset']['identified'],
                            onset_status_without_workers=evidence['without_workers']['onset']['status'],
                            suspected_room_group='', annotation_similarity_group='', review_notes=''))
    payload = dict(building=BUILDING, defaults=defaults, workers=workers, cards=cards)
    encoded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    DEST.mkdir(parents=True, exist_ok=True)
    page = PAGE.replace('__DATA__', encoded)
    page = page.replace('</style>', CLUSTER_STYLE + '</style>')
    page = page.replace('<div class="tablewrap">', CLUSTER_UI + '<details id="singleView"><summary>单人对照与填写我的观察</summary><div class="tablewrap">')
    page = page.replace('</table></div>', '</table></div></details>')
    page = page.replace('</script></html>', '</script>' + CLUSTER_SCRIPT + '</html>')
    page = page.replace('12张高人数图 · 默认同一批人员横向对照 · 可放大与填写观察', '12张高人数图 · 同簇成员彩色叠加 · 点击人员姓名突出显示')
    page = page.replace('先看图，再判断是否相似。', '先按簇看叠加，再比较图片。')
    page = page.replace('显示点号', '单人视图点号')
    page = page.replace('<div class="card"><p><b>', '<details class="card"><summary>说明与核对记录用法</summary><p><b>', 1)
    page = page.replace('</p></details></div>\n<div class="bar">', '</p></details></details>\n<details class="card"><summary>显示选项与导出记录</summary><div class="bar">', 1)
    page = page.replace('<span id="saveState" role="status"></span></div>', '<span id="saveState" role="status"></span></div></details>', 1)
    (DEST / 'uNb标注对照表.html').write_text(page, encoding='utf8')
    write_csv(DEST / 'uNb逐图核对表.csv', summary)
    write_csv(DEST / 'uNb真实标注明细.csv', annotations)
    write_csv(DEST / 'uNb簇成员.csv', cluster_rows)
    qa = dict(status='passed', image_count=len(cards), unassisted_responses=len(responses),
              included_responses=sum(r['unassisted_manual_included'] for r in responses), default_workers=defaults,
              all_defaults_cover_all_images=True, selection='All 12 uNb images with common_n >= 19, sorted by image_id; no outcome selection.',
              coordinates='Exact reviewed/raw 1024x512 point sets; display only, no inferred edges or additional point repair.',
              schema='Image CSV: one image per row; annotation CSV: one image/person canonical response per row. Missing q validity is not false. Empty onset is not zero. HTML notes are user review candidates, never written to raw data.',
              source=str(source), visual_qa='pending')
    qa['cluster_view'] = dict(q=.95, source='revised/{mode}/geometry/full_q_partitions.csv',
                              scopes=['with_workers', 'without_workers'], membership_rows=len(cluster_rows),
                              point_counts_hard_gate_checked=True, canonical_membership_coverage_checked=True,
                              candidates_not_silently_resolved=True, display='Full existing response pool, not a sampled k-prefix or proof of stability; invalid-q responses remain unassigned.')
    (DEST / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in qa.items() if k not in ('schema', 'source')}, ensure_ascii=False))


PAGE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>uNb · 真实标注对照表</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#172635;font:15px/1.6 "Microsoft YaHei",sans-serif}header,main{padding:20px 28px}header{background:#152b42;color:white}h1{font-size:26px;margin:0 0 4px}p{margin:8px 0}.muted{color:#526477;font-size:13px}header .muted{color:#c6d7e8}.bar,.card{background:white;border:1px solid #d9e1e9;border-radius:8px;padding:14px;margin:0 0 14px}.bar{display:flex;gap:18px;align-items:center;flex-wrap:wrap}button,select,input,textarea{font:inherit}button,select{padding:6px 10px;border:1px solid #bdcad6;border-radius:5px;background:#fff;color:#163e66}button{cursor:pointer}button:hover{background:#e9f2fa}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #e8ac3c;outline-offset:2px}input,textarea{width:100%;padding:6px;border:1px solid #bdcad6;border-radius:4px}textarea{resize:vertical;min-height:60px}.tablewrap{overflow:auto;max-height:78vh;border:1px solid #d9e1e9;background:white}table{border-collapse:collapse;width:100%;min-width:1500px;table-layout:fixed}th,td{padding:10px;border:1px solid #d9e1e9;vertical-align:top}th{position:sticky;top:0;background:#eaf0f6;z-index:2;text-align:left}th:first-child{width:225px}th:not(:first-child){width:320px}.thumb{padding:0;border:0;display:block;width:100%;background:#0d1720;border-radius:0}.thumb svg{display:block;width:100%;height:auto}.caption{font-size:12px;margin-top:5px;color:#405a70}.warn{color:#9a4917}.id{font:12px monospace;overflow-wrap:anywhere}label{display:block;margin-top:6px;font-size:13px}details{margin-top:9px}summary{cursor:pointer;color:#285a83}.small{font-size:12px}dialog{width:min(1220px,96vw);max-height:95vh;border:1px solid #c5d2de;border-radius:8px;padding:18px}dialog::backdrop{background:#102131bd}.dialogbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.dialogbar strong{flex:1}#large svg{display:block;width:100%;background:#111}#large{margin-top:12px}#detailText{overflow-wrap:anywhere}#saveState{font-size:13px;color:#526477}a{color:#176395}.legend span{display:inline-block;margin-right:20px}.badge{background:#e9f0f6;padding:1px 5px;border-radius:3px}footer{padding:20px 28px;color:#526477}.empty{padding:55px 10px;text-align:center;background:#f4f6f8} @media print{header,main{padding:8px}.tablewrap{max-height:none;overflow:visible}table{min-width:0}.bar{display:none}th{position:static}tr{break-inside:avoid}}
</style>
<header><h1>uNb · 真实标注对照表</h1><div>12张高人数图 · 默认同一批人员横向对照 · 可放大与填写观察</div><div class="muted">2026-09-10 ｜ 全部符合人数条件的uNb图片，按图像ID排序；没有按收敛结果挑选。</div></header>
<main>
<div class="card"><p><b>先看图，再判断是否相似。</b>同一房间或相似标法的图片，可填写相同的自定义分组，例如R1、R2或A、B；不确定时写“待定”。房间分组与标法分组分别记录。点击任意图片可放大并保持同一人员切换上一图／下一图。</p><p class="muted">默认W1、W2、W6是所有12图均有纳入点集的人员中编号最小的3位，不按标注好坏选择。可切换全部人员。展示原始或人工复核后的点集，不推定未保存的墙体连线；点号仅表示该份作答内的存储次序，不代表跨人员的角点对应。点数不同必属不同簇；点数相同不保证同簇。</p><details><summary>“无法判断”与“未达标”的区别</summary><p><b>无法判断：</b>例如q所需几何不能解析、分区存在多个可行解，或当前人数下尚无两人支持的簇，使稳定判定或80%起点不能确定。它不是“不收敛”的标签。</p><p><b>观察内未达标：</b>在指定阈值、人员范围和观察终点下没有达到要求；可能是新受支持簇出现或份额变化。仍不证明永远无法收敛。</p><p>本表折叠结果复用q=.95、H=23、m=2、变化容差.10、80%门槛；合法候选起点最晚k=18。200次是同一批历史人员重排，实线为稳定次数/200，未知边界不是置信区间。你的观察先单独保存，不自动改变计算结果。</p></details></div>
<div class="bar"><div id="workerControls"></div><label><input id="raw" type="checkbox" style="width:auto"> 显示原始点（默认复核后点）</label><label><input id="numbers" type="checkbox" checked style="width:auto"> 显示点号</label><button id="export">导出我的核对记录 JSON</button><span id="saveState" role="status"></span></div>
<div class="tablewrap"><table><thead><tr id="thead"></tr></thead><tbody id="rows"></tbody></table></div>
<p class="muted">“全部无辅助作答”包含5份空点响应，均明确显示为计算暂排；291份纳入作答来自296份记录。实际可用人数与回放的共同人数预算分别列出。人员编号来自原始身份，不是本轮人员类别。</p>
</main><footer>离线单文件，可直接用浏览器打开。核对记录尝试保存在当前浏览器；请同时导出JSON以便提交或备份。图片、原始标注及正式实验配置不会因填写而改变。</footer>
<dialog id="viewer"><div class="dialogbar"><strong id="viewTitle"></strong><button id="prev">上一图</button><button id="next">下一图</button><label>查看 <select id="viewWorker"></select></label><button id="close">关闭</button></div><div id="large"></div><p id="detailText" class="small"></p></dialog>
<script id="data" type="application/json">__DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent), key='hohonet-unb-review-20260910-v1';
const $=id=>document.getElementById(id), h=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let notes={}, selected=[...data.defaults], active=0, activeWorker='raw';
try{notes=JSON.parse(localStorage.getItem(key)||'{}');if(!notes||Array.isArray(notes)||typeof notes!=='object')notes={};$('saveState').textContent='核对记录在当前浏览器本地保存';}catch(e){$('saveState').textContent='浏览器本地保存不可用，请使用导出按钮';}
function save(){try{localStorage.setItem(key,JSON.stringify(notes));$('saveState').textContent='已保存到当前浏览器；建议另行导出JSON';}catch(e){$('saveState').textContent='本地保存失败，当前填写仍在页面中，请立即导出JSON';}}
function svg(card,worker){
 const a=card.responses[worker], raw=$('raw').checked, points=worker==='raw'?[]:(raw?a?.raw:a?.effective);
 if(worker!=='raw'&&!a)return '<div class="empty">此人没有该图的无辅助作答</div>';
 let marks='';(points||[]).forEach((p,i)=>{marks+=`<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="#ffcf33" stroke="#15212e" stroke-width="1.5"/>`;if($('numbers').checked)marks+=`<text x="${p[0]+6}" y="${p[1]-5}" fill="white" stroke="#142130" stroke-width="2.5" paint-order="stroke" font-size="14" font-family="sans-serif">${i+1}</text>`;});
 return `<svg viewBox="0 0 1024 512" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="图${card.number} ${worker==='raw'?'原图':'W'+worker+'点集'}"><image href="${card.image}" width="1024" height="512" preserveAspectRatio="none"/>${marks}</svg>`;
}
function caption(c,w){if(w==='raw')return '全景原图 · 无叠加点';const a=c.responses[w];if(!a)return '无该人员作答';const n=$('raw').checked?a.raw_n:a.effective_n;let s=`W${w} · ${n??'不可用'}点 · ${a.stage}`;if(a.raw_n!==a.effective_n||a.processing!=='unchanged')s+=` · 原${a.raw_n}→复核${a.effective_n??'不可用'}点`;if(!a.included)s+=' · 计算暂排';if(a.q_valid===false)s+=' · q几何不可用';return h(s);}
function tile(c,w){return `<button class="thumb" data-image="${c.number-1}" data-worker="${w}" aria-label="放大图${c.number} ${w==='raw'?'原图':'W'+w}">${svg(c,w)}</button><div class="caption">${caption(c,w)}</div>`;}
function status(e){const o=e.onset,l=e.last;let text=o.status==='identified'?`起点 ${Number(o.identified)} 人`:o.status==='not_reached'?'未在k≤18达到80%':'起点无法确定';return `${text}；k=18：稳定${l.stable}、未达标${l.changing}、未知${l.unknown}（合计200次）`;}
function render(){
 $('thead').innerHTML='<th>图片与我的观察</th><th>全景原图</th>'+selected.map(w=>`<th>W${w} · 真实点集</th>`).join('');
 $('rows').innerHTML=data.cards.map(c=>{const n=notes[c.id]||{};return `<tr><td><b>图${String(c.number).padStart(2,'0')} · ${c.short}</b><div class="small">无辅助记录 ${c.total}人；纳入点集 ${c.included}人（q可算${c.q_valid_people}人）<br>回放共同预算 ${c.common_n}人</div><div class="small">有效点数分布：${Object.entries(c.counts).map(([k,v])=>`${k}点×${v}人`).join('，')}</div><label>疑似同房间组<input data-id="${c.id}" data-field="room_group" value="${h(n.room_group)}" placeholder="如R1；不确定可写待定"></label><label>相似标法组<input data-id="${c.id}" data-field="annotation_group" value="${h(n.annotation_group)}" placeholder="如A、B；与房间组分开"></label><label>观察依据／备注<textarea data-id="${c.id}" data-field="notes" placeholder="哪些图片相似？哪些人的标法相似？">${h(n.notes)}</textarea></label><details><summary>计算结果与q问题</summary><div class="small"><p>含W19/W26：${status(c.evidence.with_workers)}</p><p>排除W19/W26：${status(c.evidence.without_workers)}</p><p class="warn">${c.invalid.length?h(c.invalid.join('；')):'没有单份q几何不可用记录。分区仍可能多解；q可计算不代表布局正确。'}</p><p>${h(c.partition_note)}</p><div class="id">${c.id}</div></div></details></td><td>${tile(c,'raw')}</td>${selected.map(w=>`<td>${tile(c,w)}</td>`).join('')}</tr>`;}).join('');
}
function openView(index,worker){active=index;activeWorker=worker;updateView();if(!$('viewer').open)$('viewer').showModal();}
function updateView(){const c=data.cards[active];$('viewTitle').textContent=`图${String(c.number).padStart(2,'0')} · ${c.short}`;$('viewWorker').value=activeWorker;$('large').innerHTML=svg(c,activeWorker);const a=c.responses[activeWorker];$('detailText').textContent=a?`W${activeWorker}｜原始${a.raw_n}点 / 有效${a.effective_n??'不可用'}点｜${a.included?'纳入无辅助计算':'计算暂排：'+a.excluded}｜${a.q_valid===false?'q不可计算：'+(a.q_reason==='odd_keypoint_count'?'奇数点，当前q无法构造所需几何配对':a.q_reason):a.q_valid===true?'q几何可计算':'q未评价'}｜canonical ${a.canonical}｜${a.identity}｜来源 ${a.source}`:c.id;$('prev').disabled=active===0;$('next').disabled=active===data.cards.length-1;}
const options=data.workers.map(w=>`<option value="${w}">W${w}</option>`).join('');
$('workerControls').innerHTML=selected.map((w,i)=>`<label style="display:inline-block;margin-right:12px">人员列${i+1} <select data-column="${i}" aria-label="人员列${i+1}">${options}</select></label>`).join('');
document.querySelectorAll('[data-column]').forEach(s=>{s.value=selected[Number(s.dataset.column)];s.addEventListener('change',()=>{selected[Number(s.dataset.column)]=s.value;render();});});
$('viewWorker').innerHTML='<option value="raw">原图</option>'+options;$('viewWorker').addEventListener('change',()=>{activeWorker=$('viewWorker').value;updateView();});
$('rows').addEventListener('click',e=>{const b=e.target.closest('[data-image]');if(b)openView(Number(b.dataset.image),b.dataset.worker);});
$('rows').addEventListener('input',e=>{const t=e.target;if(!t.dataset.field)return;notes[t.dataset.id]??={};notes[t.dataset.id][t.dataset.field]=t.value;save();});
['raw','numbers'].forEach(id=>$(id).addEventListener('change',()=>{render();if($('viewer').open)updateView();}));
$('prev').onclick=()=>openView(Math.max(0,active-1),activeWorker);$('next').onclick=()=>openView(Math.min(data.cards.length-1,active+1),activeWorker);$('close').onclick=()=>$('viewer').close();
$('export').onclick=()=>{const result={schema:'unb_visual_review_v1',building:data.building,saved_at:new Date().toISOString(),interpretation:'用户候选分组与观察；非自动裁决、非重新计算',rows:data.cards.map(c=>({image_number:c.number,image_id:c.id,room_group:notes[c.id]?.room_group||'',annotation_group:notes[c.id]?.annotation_group||'',notes:notes[c.id]?.notes||''}))};const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));a.href=url;a.download='uNb_我的核对记录.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
render();
</script></html>'''


CLUSTER_STYLE = r'''
.clusterCanvas:hover{background:#101923}
#workerControls{display:none}body:has(#singleView[open]) #workerControls{display:block}.clusterNav{display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:#eaf1f8;padding:14px;border-radius:8px;margin-bottom:16px}.clusterGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.clusterCard{border:1px solid #cdd9e5;border-radius:8px;background:white;overflow:hidden}.clusterCard h3{font-size:17px;padding:10px 14px;margin:0}.clusterCanvas{display:block;width:100%;padding:0;border:0;border-radius:0;background:#101923}.clusterCanvas svg{display:block;width:100%;height:auto}.people{display:flex;gap:5px;flex-wrap:wrap;padding:10px}.person{padding:3px 7px;font-size:13px;border-left:6px solid var(--worker-color)}.person[aria-pressed=true]{background:#dcecfb;border-top:2px solid #183e66}.clusterHeading{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0}.clusterHeading h2{margin:0}.clusterNotice{padding:10px 14px;border-left:4px solid #d18c2c;background:#fff5df;margin-bottom:14px}.clusterIntro{font-size:14px;margin-bottom:12px}.directory{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.directory button img{width:100%;display:block}.directory button{font-size:12px}#clusterViewer{width:min(1450px,97vw)}#clusterViewer .clusterCanvas{cursor:default}.singleGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}#singleView{background:white;padding:12px;border-radius:8px;margin-top:20px}#singleView>summary{font-size:17px}.clusterHelp{max-width:1000px}#clusters input[type=range]{width:130px}.clusterNav label{margin:0}.clusterGrid .muted{padding:0 12px 10px}@media(max-width:850px){.clusterGrid,.singleGrid{grid-template-columns:1fr}.directory{grid-template-columns:repeat(3,1fr)}}
'''

CLUSTER_UI = r'''
<section id="clusters" class="card">
<div class="clusterIntro"><b>当前分簇：q=.95，点数不同必分开。</b>每幅叠加图只放同一簇的人员，每人一种颜色；点击姓名可突出该人的点，再点一次恢复全部。单人组不是受支持簇，另行折叠显示。这里使用各图现有完整作答池的分簇，不是某次抽样或稳定人数判定；不同图片的“簇1”不代表同一类。</div>
<div class="clusterNav"><button id="clusterPrev">上一张图</button><label>图片 <select id="clusterImage" aria-label="按簇查看图片"></select></label><button id="clusterNext">下一张图</button><label>人员范围 <select id="clusterScope"><option value="with_workers">含W19/W26</option><option value="without_workers">排除W19/W26</option></select></label><label>底图亮度 <input id="brightness" aria-label="底图亮度" type="range" min="20" max="100" value="65"></label></div>
<details><summary>展开12张原图目录，按画面选择</summary><div id="directory" class="directory"></div></details>
<div id="clusterBody"></div></section>
<dialog id="clusterViewer"><div class="dialogbar"><strong id="clusterViewTitle">簇叠加放大</strong><button id="clusterClose">关闭放大</button></div><div id="clusterLarge"></div></dialog>
'''

CLUSTER_SCRIPT = r'''<script>
let clusterIndex=0, candidateIndex=0;
const color=w=>`hsl(${(data.workers.indexOf(w)*137.508)%360} 92% 65%)`;
function overlay(c,workers){let marks='';for(const w of workers){const a=c.responses[w],pts=$('raw').checked?a.raw:a.effective;marks+=`<g data-person="${w}" opacity=".86">`+(pts||[]).map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="4.2" fill="${color(w)}" stroke="#172131" stroke-width="1.1"><title>W${w} · 点${i+1}</title></circle>`).join('')+'</g>';}
return `<svg viewBox="0 0 1024 512" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${workers.map(w=>'W'+w).join('、')}同组点集叠加"><image class="clusterPhoto" href="${c.image}" width="1024" height="512" opacity="${Number($('brightness').value)/100}"/>${marks}</svg>`;}
function groupCard(c,group,index,kind='cluster',large=false){const title=kind==='unassigned'?'未归簇 · q几何不可用':group.length<2?'单人组（未达到两人支持）':`簇${index+1} · ${group.length}人 · 每人${c.responses[group[0]].effective_n}点`;
return `<article class="clusterCard" data-group="${index}" data-kind="${kind}"><h3>${title}</h3><button class="clusterCanvas" ${large?'':'data-enlarge="'+index+'" data-kind="'+kind+'"'} aria-label="放大${title}">${overlay(c,group)}</button><div class="people">${group.map(w=>`<button class="person" style="--worker-color:${color(w)}" data-person-toggle="${w}" aria-pressed="false" title="点击突出W${w}，再次点击恢复">W${w}</button>`).join('')}<button data-reset-people="true" class="small">恢复全部叠加</button></div>${kind==='unassigned'?'<p class="muted">仅显示原有点集，未塞入任何现有簇。</p>':''}</article>`;}
function currentGroups(){const c=data.cards[clusterIndex],p=c.partitions[$('clusterScope').value];return {c,p,groups:p.candidates[candidateIndex]||[]};}
function renderClusters(){const {c,p,groups}=currentGroups();$('clusterImage').value=String(clusterIndex);$('clusterPrev').disabled=clusterIndex===0;$('clusterNext').disabled=clusterIndex===data.cards.length-1;
const multi=groups.map((g,i)=>({g,i})).filter(x=>x.g.length>=2), single=groups.map((g,i)=>({g,i})).filter(x=>x.g.length===1);
let notice='';if(p.scope==='q_valid_subset_only')notice+=`整图尚无法确定分簇：以下仅展示${p.q_valid_n}份q可计算作答的子集分簇；另有${p.unassigned.length}份未归簇，放在下方。`;
if(p.candidates.length>1)notice+=` 当前存在${p.candidates.length}种候选分法，未确定唯一分类；下方展示所选候选方案。`;
if(p.truncated)notice+=' 搜索曾截断，候选方案不保证完整。';
if($('raw').checked)notice+=' 当前显示原始点；分组仍固定依据复核后的点集，不随显示切换重新计算。';
$('clusterBody').innerHTML=`<div class="clusterHeading"><h2>图${String(c.number).padStart(2,'0')} · ${c.short}</h2><span>${p.pointset_n}份纳入点集 · ${multi.length}个两人以上组 · ${single.length}个单人组</span><button data-open-original="true">放大原图</button></div>${notice?'<div class="clusterNotice">'+notice+'</div>':''}${p.candidates.length>1?`<label>候选分法 <select id="candidateChoice">${p.candidates.map((g,i)=>`<option value="${i}" ${i===candidateIndex?'selected':''}>方案${i+1}（非唯一）</option>`).join('')}</select></label>`:''}<div class="clusterGrid">${multi.map(x=>groupCard(c,x.g,x.i)).join('')||'<p>此方案没有两人以上受支持组。</p>'}</div>${single.length?`<details><summary>单人组 ${single.length} 个（未达到两人支持）</summary><div class="singleGrid">${single.map(x=>groupCard(c,x.g,x.i)).join('')}</div></details>`:''}${p.unassigned.length?`<details open><summary>q几何不可用，未归簇 ${p.unassigned.length} 人</summary><div class="singleGrid">${p.unassigned.map((w,i)=>groupCard(c,[w],i,'unassigned')).join('')}</div></details>`:''}<p class="muted id">${c.id}</p>`;
const chooser=$('candidateChoice');if(chooser)chooser.onchange=()=>{candidateIndex=Number(chooser.value);renderClusters();};}
function peopleClick(e){const b=e.target.closest('[data-person-toggle],[data-reset-people]');if(!b)return false;const card=b.closest('.clusterCard'),w=b.dataset.personToggle,reset=!w||b.getAttribute('aria-pressed')==='true';card.querySelectorAll('g[data-person]').forEach(g=>g.setAttribute('opacity',reset||g.dataset.person===w?'.95':'.045'));card.querySelectorAll('[data-person-toggle]').forEach(x=>x.setAttribute('aria-pressed',String(!reset&&x.dataset.personToggle===w)));return true;}
function changeImage(i){clusterIndex=Math.max(0,Math.min(data.cards.length-1,i));candidateIndex=0;renderClusters();}
$('clusterImage').innerHTML=data.cards.map((c,i)=>`<option value="${i}">图${String(c.number).padStart(2,'0')} · ${c.short}</option>`).join('');
$('directory').innerHTML=data.cards.map((c,i)=>`<button data-directory="${i}"><img src="${c.image}" alt="图${c.number}原图">图${String(c.number).padStart(2,'0')} · ${c.short}</button>`).join('');
$('clusterPrev').onclick=()=>changeImage(clusterIndex-1);$('clusterNext').onclick=()=>changeImage(clusterIndex+1);$('clusterImage').onchange=()=>changeImage(Number($('clusterImage').value));$('clusterScope').onchange=()=>{candidateIndex=0;renderClusters();};
$('directory').onclick=e=>{const b=e.target.closest('[data-directory]');if(b)changeImage(Number(b.dataset.directory));};
$('brightness').oninput=()=>document.querySelectorAll('.clusterPhoto').forEach(x=>x.setAttribute('opacity',Number($('brightness').value)/100));
$('raw').addEventListener('change',renderClusters);
$('clusterBody').onclick=e=>{if(peopleClick(e))return;const original=e.target.closest('[data-open-original]');if(original){openView(clusterIndex,'raw');return;}const b=e.target.closest('[data-enlarge]');if(!b)return;const {c,p,groups}=currentGroups(),i=Number(b.dataset.enlarge),group=b.dataset.kind==='unassigned'?[p.unassigned[i]]:groups[i];$('clusterViewTitle').textContent=`图${String(c.number).padStart(2,'0')} · ${c.short} · ${group.length}人叠加`;$('clusterLarge').innerHTML=groupCard(c,group,i,b.dataset.kind,true);$('clusterViewer').showModal();};
$('clusterLarge').onclick=peopleClick;$('clusterClose').onclick=()=>$('clusterViewer').close();
renderClusters();
</script>'''


if __name__ == '__main__':
    build()
