"""Merge full-image visual review without replacing prior human classifications."""
import html
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/open_layout_recheck_20260913_v1'
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def merge(registry, reviews, checks, independent=()):
    source = {r['image_id']: r for r in registry['images']}
    rows = [r for review in reviews for r in review['rows']]
    if len(rows) != len(source) or {r['image_id'] for r in rows} != set(source):
        raise ValueError('全量复核缺失、重复或图像身份不一致')
    cross = {r['image_id']: r for r in checks['rows']}
    secondary = {r['image_id']: r for r in independent}
    if len(cross) != len(checks['rows']) or len(secondary) != len(independent) or not set(cross).issubset(source) or not set(secondary).issubset(source):
        raise ValueError('交叉复核图像身份不一致')
    for r in [*rows, *cross.values(), *secondary.values()]:
        if r['verdict'] not in ('支持开放复合', '不支持开放复合', '待定'):
            raise ValueError('未知复核判定')
        if r['verdict'] != '不支持开放复合' and 'original' not in r['view_basis']:
            raise ValueError('支持或待定图片需原图复核')
    result = []
    for r in rows:
        old = source[r['image_id']]
        parent = cross.get(r['image_id'])
        final = parent or r
        prior_open = old['spatial_classification']['coarse_type'] == '开放复合空间'
        needs_confirmation = (final['verdict'] == '支持开放复合' and not prior_open) or (prior_open and final['verdict'] != '支持开放复合') or final['verdict']=='待定'
        history = old.get('review_history', [])
        explicit_type_revision = 'coarse_type' in old.get('spatial_changed_fields',[]) or any('user_type' in e.get('changed_from_initial',{}) for e in history)
        subtype = final.get('subtype') or ''
        subtype = {'客餐厨开放型':'厨房-用餐-起居开放型','客餐开放型':'起居-用餐开放型','客厨开放型':'厨房-起居开放型'}.get(subtype,subtype)
        result.append(dict(image_id=r['image_id'], building=old['building'], number=old['number'],
            path=old['path'], group_codes=old['group_codes'],
            prior_adopted=old['spatial_classification'], prior_ai=old['spatial_ai_proposal'],
            prior_raw_human_type=old.get('legacy_coarse_type_raw'),
            prior_human_comments=old['all_user_notes'], prior_field_sources=old['spatial_field_sources'],
            prior_ai_main_visual_space=old.get('main_visual_space'),
            prior_review_history=history,
            user_confirmation_required=needs_confirmation,
            explicit_human_type_revision=explicit_type_revision,
            confirmation_reason='AI建议与原采用粗类不同或开放判断存疑；需用户核实后才能改类' if needs_confirmation else '',
            independent_review=secondary.get(r['image_id']),
            ai_review=r, parent_review=parent,
            reviewer_disagreement=len({x['verdict'] for x in (r,parent,secondary.get(r['image_id'])) if x})>1,
            new_ai_verdict=final['verdict'], new_ai_reason=final['reason'], new_ai_functions=final['functions'],
            new_ai_subtype=subtype, adopted_classification_changed=False))
    return sorted(result, key=lambda r: (r['building'], r['number']))


def main():
    registry = read(REGISTRY)
    independent = [r for name in ('crosscheck_b_on_c','crosscheck_a_on_wc') for r in read(OUT / f'{name}.json')['rows']]
    rows = merge(registry, [read(OUT / f'review_{x}.json') for x in ('a','b','c','a_extra_b','a_extra_parent')], read(OUT / 'parent_crosscheck.json'), independent)
    planning = read(ROOT / 'analysis_results/candidate_selection_review_20260913_v1/复算结果.json')
    selected = {r['image_id'] for r in planning['images'] if r['status'] == '确定采用'}
    counts = Counter(r['new_ai_verdict'] for r in rows)
    selected_counts = Counter(r['new_ai_verdict'] for r in rows if r['image_id'] in selected)
    summary = dict(total_images=len(rows), prior_adopted_open=sum(r['prior_adopted']['coarse_type']=='开放复合空间' for r in rows),
        prior_ai_open=sum(r['prior_ai']['coarse_type']=='开放复合空间' for r in rows),
        selected_images=len(selected), prior_selected_open=sum(r['image_id'] in selected and r['prior_adopted']['coarse_type']=='开放复合空间' for r in rows),
        new_ai_counts=dict(counts), selected_new_ai_counts=dict(selected_counts),
        supported_subtypes=dict(Counter(r['new_ai_subtype'] for r in rows if r['new_ai_verdict']=='支持开放复合')),
        reviewer_disagreements=sum(r['reviewer_disagreement'] for r in rows),
        user_confirmation_required=sum(r['user_confirmation_required'] for r in rows))
    (OUT / '完整复核结果.json').write_text(json.dumps(dict(schema='open_layout_visual_recheck_v1',summary=summary,rows=rows),ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    h = html.escape
    cards = []
    for r in rows:
        photo = Path(os.path.relpath(ROOT/r['path'],OUT)).as_posix()
        prior = r['prior_adopted']['coarse_type'] or '待定'
        notes = h(json.dumps(r['prior_human_comments'],ensure_ascii=False,indent=2))
        cards.append(f'''<article data-confirm="{int(r['user_confirmation_required'])}" data-verdict="{h(r['new_ai_verdict'])}">
<h3>{h(r['building'])} · {r['number']:02} · {h(r['new_ai_verdict'])}</h3>
<a href="{h(photo)}" target="_blank"><img loading="lazy" src="{h(photo)}" alt="全景原图"></a>
<p>原采用：{h(prior)}；旧AI：{h(r['prior_ai']['coarse_type'] or '')}；新AI子型：{h(r['new_ai_subtype'])}</p>
<small>早期人工类型原文：{h(r['prior_raw_human_type'] or '未记录')}</small>
<p>原人工功能组合／保留值：{h(r['prior_adopted'].get('functions') or '无独立字段记录')}；本轮AI功能：{h('、'.join(r['new_ai_functions']))}</p>
<p><b>原人工主区域／保留值：</b>{h(r['prior_adopted'].get('focus') or '无独立focus字段作答，需结合早期类型及下方原评论')}<br><small>来源：{h(r['prior_field_sources'].get('focus','未记录'))}</small><br>旧AI主区域：{h(r['prior_ai'].get('focus') or '未记录')}</p>
<p>{h(r['new_ai_reason'])}</p><p style="color:#a44200">{h(r['confirmation_reason'])}</p>
<p>{'注意：历轮记录存在人工粗类改值。' if r['explicit_human_type_revision'] else ''}</p>
<details><summary>本轮复核者意见对照</summary><pre style="white-space:pre-wrap">{h(json.dumps([x for x in (r['ai_review'],r['parent_review'],r['independent_review']) if x],ensure_ascii=False,indent=2))}</pre></details>
<details><summary>人工原评论及讨论记录</summary><pre style="white-space:pre-wrap">{notes}</pre></details>
<small>同房展示组：{h('、'.join(r['group_codes']))}；新意见尚未覆盖人工分类。</small></article>''')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>开放复合空间复核</title><style>body{font:16px system-ui;margin:24px;background:#edf1f5}header{position:sticky;top:0;background:white;padding:15px;z-index:1}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}article{background:white;padding:14px;border-radius:10px}img{width:100%}p{line-height:1.6}article[hidden]{display:none}@media(max-width:850px){main{grid-template-columns:1fr}}</style>
<header><h1>开放复合空间 · 全量复核</h1><p>人工原记录、旧AI与本轮AI意见并列；点图查看原图。待核实的改类建议不生效。</p>
<label>显示 <select id="filter"><option>需用户核实</option><option>支持开放复合</option><option>待定</option><option>不支持开放复合</option><option>全部</option></select></label><span id="count" aria-live="polite"></span></header><main>'''+''.join(cards)+'''</main><script>
const f=document.getElementById('filter');
function render(){let n=0;document.querySelectorAll('article').forEach(a=>{a.hidden=f.value==='需用户核实'?a.dataset.confirm!=='1':f.value!=='全部'&&a.dataset.verdict!==f.value;if(!a.hidden)n++});document.getElementById('count').textContent='　'+n+' 张'}
f.onchange=render;render();</script></html>'''
    (OUT/'开放复合空间复核查看.html').write_text(page,encoding='utf-8',newline='\n')
    lines=['# 开放复合空间全量复核','',f'原报告“4图”指已选{len(selected)}图中的4图，不是全648图。全量原采用9图、旧AI建议42图，属于不同来源与分母。','',
        '本次全部648图逐图查看接触表筛查，支持及待定图进一步查看原图；主代理复核部分边界案例。只新增AI复核意见，不覆盖人工原分类，也不以标注难度、收敛结果或预期数量决定类别。','',
        '| 本轮AI判定 | 全648图 | 已确定采用图 |','|---|---:|---:|']
    for key in ['支持开放复合','待定','不支持开放复合']:
        lines.append(f'| {key} | {counts[key]} | {selected_counts[key]} |')
    lines+=['','已选98图中，本轮支持的5图是G002（2t7的02／03／05／10／17）；待定4图是G015相关的7y 09／11／16／19。图片数不等于独立房间数，不能将同组多视点当成多个独立房间样本。原“4图”也不能直接改写成“全库只有4图”。','',
        '主要区域记录与开放属性分开：后续独立focus字段包含人工复核保留值，早期区域类别及评论也承载主区域判断；无独立focus不表示未人工判断。仅看见邻接开放客餐区的门厅视点，与身处开放主空间的视点分开。','',
        '本轮复核者存在5图意见不同（pa14及wc31／47／55／63），全部保留待定，双方理由可在页面展开。存在明确人工粗类改值且本轮仍存疑的7y10、pa14优先向用户核实；不由AI裁定覆盖。']
    lines+=['','判据：连续开放且多个实质功能区明确；无需客厨餐三者齐全。厨房内独立餐桌区单列“厨房-用餐开放型”；仅吧台凳、卧室附书桌、门洞看见邻室、走廊附座椅不自动升级为开放复合。空置房间缺功能证据时保留待定。','',
        '这种开放组织判断不等于两张图视觉主空间相同，也不自动合并同房预测组。功能组合仍须分别记录；厨房-用餐型不应未经检查就与大型客餐厨一体空间视作同质预测样本。','',
        '| 支持图的细分组合 | 图片数 |','|---|---:|']
    for key,n in summary['supported_subtypes'].items():lines.append(f'| {key} | {n} |')
    lines+=['',f'有{summary["user_confirmation_required"]}图的新AI意见与原采用粗类不同或无法维持原开放判断，需用户核实后才能改类。类别名称不同有时只是功能与开放属性的口径差异，不自动等于人工判断错误。原评论与历轮修改保留在机器表中，页面默认筛出这些图。','',
        '| 需核实图片 | 原采用粗类 | 本轮AI意见 |','|---|---|---|']
    for r in rows:
        if r['user_confirmation_required']:
            lines.append(f'| {r["building"]} · {r["number"]:02} | {r["prior_adopted"]["coarse_type"]} | {r["new_ai_verdict"]}：{r["new_ai_subtype"]} |')
    lines+=['','[逐图查看](开放复合空间复核查看.html) · [完整机器结果](完整复核结果.json)。结果逐条保留原采用分类、旧AI预填、人工评论、新AI理由、主代理交叉复核及分歧；不能把新增AI支持数称为已人工确认数量。']
    (OUT/'复核说明.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
