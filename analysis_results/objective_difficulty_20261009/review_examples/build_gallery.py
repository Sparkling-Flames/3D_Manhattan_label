"""一次性审图材料；只展示已有分类、原图及历史判断，不改写源结果。"""
import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT = Path(__file__).parent
BASE = OUT.parent
SELECTION = [
    ('结构简单', ['7y3sRwLe3Va-04', 'q9vSo1VnCiC-32', '2t7WUuJeko7-06']),
    ('结构中等', ['uNb9QFRL6hY-19', 'VFuaQ6m2Qom-01', 'b8cTxDM8gDG-07', 'S9hNv5qa7GM-05']),
    ('结构困难', ['UwV83HsGsw3-09', 'yqstnuAEVhm-25', 'wc2JMjhGNzB-29']),
    ('门洞交界单列', ['jtcxE69GiFV-12', 'uNb9QFRL6hY-47', 'uNb9QFRL6hY-21']),
    ('OOS单列', ['x8F5xyUWy9e-01', 'x8F5xyUWy9e-09', 'S9hNv5qa7GM-01', 'uNb9QFRL6hY-63']),
    ('OOS与门洞重叠', ['pRbA3pwrgk9-01', 'pRbA3pwrgk9-11']),
    ('暂停待定：只说明状态，无需重审', ['jtcxE69GiFV-11', 'pRbA3pwrgk9-16']),
]

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def main():
    rows = read(BASE / 'structure_classification/images.csv')
    current = {r['image']: r for r in rows}
    recheck = {r['image']: r for r in read(OUT / 'score_recheck.csv')}
    working = {r['image']: r for r in read(OUT / 'working_classification_20261010.csv')}
    historical = {r['image_id']: r for r in read(BASE / 'stratified/features_and_scores.csv')}
    sources = {r['image_id']: r for r in read(BASE / 'model_comparison/image_source_audit.csv')}
    objects = {o['object_id']: o for o in load_current_bundle()['data']['objects']}
    assert len(rows) == len(current) == 259
    cards, records, overview = [], [], []
    used = set()
    for group, codes in SELECTION:
        cards.append(f'<h2>初选分组：{html.escape(group)}（旧分组，最新类别见图卡）</h2>')
        for code in codes:
            r = current[code]
            iid = r['image_id']
            assert iid not in used
            used.add(iid)
            old = historical[iid]
            path = Path(sources[iid]['hohonet_path'])
            assert path.is_file() and path.stem == iid and path.suffix.lower() == '.png'
            obj = objects[r['gt_object_id']]
            assert obj['image_id'] == iid
            points = obj['points_1024x512']
            assert len(points) == 2 * int(r['selected_gt_pair_count'])
            hidden = set(json.loads(r['hidden_pairs_1based']))
            serial = f'{len(records)+1:02d}'
            historical_kind = '早期过程预期，不能当执行难度' if '9/13' in old['subjective_definition'] else '历史图级主观判断' if old['subjective_label'] in ('简单', '中等', '困难') else '未获得三档评分'
            record = dict(review_id=serial, review_group=group, **r,
                image_path=str(path), historical_label=old['subjective_label'],
                historical_source=old['subjective_source'], historical_definition=old['subjective_definition'],
                historical_kind=historical_kind, historical_selection_note='目的性包含一致、不一致和未评分；非随机、非盲法，不估计准确率')
            records.append(record)
            overview.append(f'|{serial}|{code}|{group}|{r["coarse_class"]}|{r["selected_gt_pair_count"]}/{r["hidden_pair_count"]}|{old["subjective_label"]}（{historical_kind}）|')
            dots = []
            for k, (x, y) in enumerate(points):
                pair = k // 2 + 1
                color = '#ff4266' if pair in hidden else '#ffe76a'
                dots.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}" stroke="#111"/><text x="{x+6}" y="{y-5}" fill="{color}" stroke="#111" stroke-width=".8" paint-order="stroke" font-size="13">{pair}</text>')
            uri = '../../../' + path.relative_to(ROOT).as_posix()
            esc = html.escape
            flags = f'OOS：{r["oos_status"]}；门洞：{r["doorway_status"]}；可标性：{r["annotatability_status"]}；场景记录：{r["scene_stratum"]}'
            title = f'{serial} · {code} · GT结构记录：{r["coarse_class"]}'
            assessment = recheck[code]['difficulty_status']
            assessment_text = {'pending_reference_review': 'GT被用户指出有问题；图片难度待核，不沿用结构困难作为结论。',
                'separate_assessment_pending': '特殊场景：独立难度尚未赋分，GT结构类仅作诊断。',
                'existing_hold_or_inapplicable': '保留已有暂停或不适用状态。',
                'provisional_structure_proxy': '暂用结构粗分；GT范围一致性尚未逐图认证。'}[assessment]
            w = working[code]
            assessment_text += ' 最新工作类：' + (w['working_difficulty_class'] or '单列／待定，未赋三档') + '。'
            if w['classification_basis'] == 'codex_photo_review_20261010':
                assessment_text += '2026-10-10看图调整：' + w['visual_review_reason']
            evidence = r['latest_scene_note'] or r['pending_or_inapplicable_reason'] or '无追加图级备注；未知不等于普通。'
            cards.append(f'''<article id="r{serial}"><h3>{esc(title)}</h3>
<p>N={r['selected_gt_pair_count']} 点对，H={r['hidden_pair_count']} 个底面顶点被墙体遮挡；参考：{esc(r['gt_version'])}。</p>
<p>{esc(flags)}</p><label><input type="checkbox" onchange="this.closest('article').classList.toggle('showgt',this.checked)">叠加当前GT点对（黄＝未检出结构遮挡，红＝几何被挡；不是照片识别）</label>
<p><strong>复核状态：{esc(assessment_text)}</strong></p>
<div class="photo"><img src="{uri}" alt="{esc(code)} 原全景图" loading="lazy"><svg viewBox="0 0 1024 512" aria-hidden="true">{''.join(dots)}</svg></div>
<details><summary>展开你过去的判断：{esc(old['subjective_label'])} · {esc(historical_kind)}</summary><p>{esc(old['subjective_definition'])}</p><p class="source">来源：{esc(old['subjective_source'])}</p></details>
<p class="note">已有场景备注：{esc(evidence)}</p><details><summary>参考与图片来源</summary><p class="source">{esc(str(path))}<br>{esc(r['gt_object_id'])}<br>环确认：{esc(r['gt_ring_confirmed'])}；房间：{esc(r['room'] or '未知')}</p></details>
<p>回复示例：{serial}，主观中等；门洞状态认可／需改；理由……。暂停图无需重新判断。</p></article>''')
    assert len(records) == 21 and len(used) == 21
    for r in records:
        if r['review_group'].startswith('结构'):
            assert r['scene_stratum'] in ('clear', 'unflagged')
        if r['review_group'] == 'OOS与门洞重叠':
            assert r['scene_stratum'] == 'oos_and_doorway'
    title = '图片难度粗分类 · 21图主观对照审查'
    intro = '''<p><a href="SIX_PAIR_UPDATE_20261010.md">最新：6点对低遮挡看图调整</a>，6张改为简单；旧分组和GT结构类仅作追溯。<a href="SCORE_RECHECK.md">此前评分复核</a>：门洞／OOS独立评判；x8-01参考待核。<a href="x8_01_reference_comparison.png">查看x8-01原GT与5份作答</a>。</p><p>旧结构三档只由GT点对数和结构自遮挡决定；最新工作分类另含逐图视觉判断。门洞交界是相机处于门洞／门框交界附近，非照片中出现任何门；OOS不等于不可标。</p>
<p>本页为目的性案例，不是随机样本或准确率验证。普通三组示例不含已确认特殊图，但“unflagged”仍表示未标特殊，不认证普通。OOS、门洞及重叠组单列；其中的结构类别照常保留。</p>
<p>已有评分可展开查看；早期“过程预期”与后来“主观难度”明确区分。你可先看照片再展开，按编号在聊天中反馈。本页不会改动任何旧评分或类别。</p>
<p>状态说明：confirmed＝已记OOS；not_oos＝明确非OOS；not_recorded＝未记录；门洞none＝明确无，annotatable＝可标，difficult＝旧记录难标（不等于不可标）。not_explicitly_resolved＝可标性未明确裁决。</p>'''
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
body{{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f3f5f8;color:#172333}}main{{max-width:1180px;margin:auto;padding:24px}}article{{background:white;padding:22px;margin:20px 0 32px;border-radius:12px;border:1px solid #d5dce7}}h2{{margin-top:48px;border-bottom:3px solid #537aa9}}h3{{margin:0}}.photo{{position:relative;margin-top:14px}}img{{width:100%;height:auto;display:block}}svg{{position:absolute;inset:0;width:100%;height:100%;display:none;pointer-events:none}}.showgt svg{{display:block}}.source{{overflow-wrap:anywhere;font-size:13px}}summary,label{{cursor:pointer}}details{{background:#edf3fa;padding:10px;margin-top:14px}}.note{{color:#38475a}}header{{background:#e3edf9;padding:22px;border-radius:12px}}</style><main><header><h1>{title}</h1>{intro}</header>{''.join(cards)}</main></html>'''
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    (OUT / 'selection.json').write_text(json.dumps(dict(purpose='主观核对，不用于拟合或盲法验证', selection_rule='固定目的性样本，保留一致、不一致、无评分及特殊条件', records=records), ensure_ascii=False, indent=2), encoding='utf-8')
    cross = Counter((r['scene_stratum'], r['coarse_class']) for r in rows)
    crosslines = ['|场景记录|简单|中等|困难|待定|', '|---|---:|---:|---:|---:|']
    for scene in sorted({r['scene_stratum'] for r in rows}):
        crosslines.append('|'+scene+'|'+'|'.join(str(cross[scene,c]) for c in ['简单','中等','困难','待定'])+'|')
    readme = '# 图片粗分类：21图审查材料\n\n[打开原图与可选GT点位图集](index.html)。页面引用仓库已有PNG原图，未旋转、裁切、重新压缩；GT点位按1024×512坐标等比例展示，仅画点不猜连接。克隆仓库时须保留`data/mp3d_layout`，本地页面才能显示原图。\n\n抽样是目的性案例，包含一致、不一致和未评分，不代表各类总体比例。选择详情、全长ID、GT来源、旧评分来源与定义见[selection.json](selection.json)。早期过程预期不能冒称独立执行难度。反馈在聊天中按编号给出即可；不自动更新原评分、场景或类别。\n\n全体259图的类别总数包含特殊场景，不能称为普通图片三档的数量。未知保留未知；本页展示分组只服务审查，不修改主表或资格。\n\n'+'\n'.join(crosslines)+'\n\n|编号|图片|展示分组|结构类|N/H|旧判断及口径|\n|---|---|---|---|---|---|\n'+'\n'.join(overview)+'\n\n复建：`python analysis_results/objective_difficulty_20261009/review_examples/build_gallery.py`。脚本断言21个唯一研究图、身份与源图及GT一致、点对数正确、普通示例不混入已确认特殊场景。现有粗分类、GT、源图及旧评分未写入。\n'
    readme += '\n最新使用解释见[评分复核](SCORE_RECHECK.md)及[259图复核表](score_recheck.csv)。门洞／OOS独立难度尚未赋分；x8-01参考待核。上表结构类和旧判断只作追溯，不等于新的独立评分。\n'
    readme += '\n2026-10-10最新：[6点对低遮挡更新](SIX_PAIR_UPDATE_20261010.md)，6图由中等改为简单；[当前工作分类](working_classification_20261010.csv)保留旧结构结果及看图来源。\n'
    (OUT / 'README.md').write_text(readme, encoding='utf-8')
    print(json.dumps(dict(images=len(records), html_mb=round((OUT/'index.html').stat().st_size/1e6,2), source_checks='passed'), ensure_ascii=False))

if __name__ == '__main__':
    main()
