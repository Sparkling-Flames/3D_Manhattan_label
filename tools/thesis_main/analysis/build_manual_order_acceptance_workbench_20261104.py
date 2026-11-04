"""Add the completed second acceptance to the existing offline research workbench.

Only a static acceptance section and its local source links are updated. The
original 57-endpoint browser, original images, calculations, and data.js remain
the frozen first delivery. No statistical values are recomputed here.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/manual_order_acceptance_20261104'
SITE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
PAGE = SITE / 'v21-manual-order.html'
ASSETS = SITE / 'v21-manual-order'
START = '<!-- ACCEPTANCE_20261104_BEGIN -->'
END = '<!-- ACCEPTANCE_20261104_END -->'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--font-source', type=Path)
    args = parser.parse_args()
    decisions = pd.read_csv(BASE / 'RERUN_DECISIONS.csv', keep_default_na=False)
    assert len(decisions) >= 6 and decisions.topic.is_unique
    opportunity=json.loads((BASE/'ac/OPPORTUNITY_CHECKS.json').read_text(encoding='utf-8'))
    bounds=json.loads((BASE/'ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json').read_text(encoding='utf-8'))
    assert opportunity['audit_completed'] and opportunity['confirmed57_propagation_complete']
    rows = []
    for row in decisions.to_dict('records'):
        rows.append('<tr>' + ''.join('<td>' + html.escape(str(row[key])) + '</td>'
                    for key in ['topic', 'decision', 'completed_action', 'reason']) + '</tr>')
    section = f'''{START}
<section id="acceptance" class="panel" aria-labelledby="acceptance-heading">
<p class="eyebrow">第二次独立验收 / 20261104</p>
<h2 id="acceptance-heading">是否需要重跑：验收与修正已完成</h2>
<p>本轮从原登记设计、原端点和实际消费者独立复核。Q-only 在固定 208 个事件内的全部 29 条无连接机会已覆盖，无需追加人工排序；AC 翻向按原事件、新增事件、图片与楼栋计权逐项追溯。AC 的定向 57 组不代表所有登记对手都获得了人工处理，剩余失败与机会边界单列。</p>
<p>AC 的 {opportunity['Q_reversal_rows']} 条 Q 统计口径中，{opportunity['condition_rows_with_opportunity_gap']} 条有处理机会缺口，去重后 {opportunity['distinct_residual_endpoints']} 个端点仍缺 Q。RAW3 其它目标 n=m=4 当前为 13/16 可评；三个残余 C 的合法 Q 界限为 [{bounds['all_subsets_effect_lower']:.6f}, {bounds['all_subsets_effect_upper']:.6f}]，方向仍负。界限没有写入实测评分，完整精确均值及同等人工处理仍不能声称完成。</p>
<p class="notice">实际修正：有限配比两份辅助标量表的 8 个成员字段单元及生成代码。成员内容、顺序和全部数值保持。原自动与人工辅助仍是两个方法版本，原缺失 Q 保持缺失。</p>
<div class="scroll"><table><thead><tr><th>项目</th><th>重跑判定</th><th>已完成补充</th><th>适用条件</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="resource-grid">
<a href="../../fusion/manual_order_acceptance_20261104/REPORT_ZH.md">第二次验收总报告</a>
<a href="../../fusion/manual_order_acceptance_20261104/CONCLUSION_MATRIX.csv">逐条结论与来源</a>
<a href="../../fusion/manual_order_acceptance_20261104/q_only/REPORT_ZH.md">Q-only 完整机会与关键七事件</a>
<a href="../../fusion/manual_order_acceptance_20261104/ac/REPORT_ZH.md">AC 全部翻向与支持分解</a>
<a href="../../fusion/manual_order_acceptance_20261104/secondary/REPORT_ZH.md">同房、配比、联盟、人数及策略</a>
<a href="../../fusion/manual_order_acceptance_20261104/secondary/repairs/MEMBER_FIELD_CELL_CHANGES.csv">8 个字段修正明细</a>
</div>
<p class="caption">Q-only 的机会覆盖证明限定 208 个冻结事件；AC 的不同指标和计权视图不能当作独立实验累加。57 组仍为定向案例。F2/F9 坐标候选继续单列，未纳入固定坐标主结果。</p>
</section>
{END}'''
    original = PAGE.read_text(encoding='utf-8')
    if START in original:
        revised = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _:section,
                         original, flags=re.S)
    else:
        anchor = '<section id="endpoint"'
        assert original.count(anchor)==1
        revised = original.replace(anchor,section+'\n'+anchor)
    if 'href="#acceptance"' not in revised:
        revised = revised.replace('<a href="#endpoint">','<a href="#acceptance">独立验收</a><a href="#endpoint">',1)
    PAGE.write_text(revised,encoding='utf-8')
    if args.font_source:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        font = TTFont(args.font_source)
        content = revised + ''.join(p.read_text(encoding='utf-8') for p in ASSETS.glob('*.js'))
        codepoints = set(map(ord,content)) | set(range(32,127))
        options = subset.Options()
        options.name_IDs=['*']; options.name_legacy=True; options.name_languages=['*']
        cutter = subset.Subsetter(options=options)
        cutter.populate(unicodes=codepoints); cutter.subset(font)
        names = {1:'HOHONET Sans',4:'HOHONET Sans Regular',6:'HOHONETSans-Regular',16:'HOHONET Sans',17:'Regular'}
        for name in font['name'].names:
            if name.nameID in names:
                name.string=names[name.nameID].encode(name.getEncoding())
        target=ASSETS/'fonts/HOHONETSans-Regular.otf'
        font.save(target)
        provenance=dict(source='https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
                        license='SIL Open Font License 1.1',transformation='subset to page/data Unicode; renamed family HOHONET Sans',
                        source_sha256=hashlib.sha256(args.font_source.read_bytes()).hexdigest(),
                        output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                        unicode_requested=len(codepoints),bytes=target.stat().st_size,
                        acceptance_section_included=True)
        (target.parent/'PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    from lxml import html as parse_html
    from fontTools.ttLib import TTFont
    document=parse_html.fromstring(PAGE.read_bytes())
    ids=document.xpath('//@id')
    assert len(ids)==len(set(ids))
    assert len(document.xpath('//section[@id="acceptance"]//tbody/tr'))==len(decisions)
    font=TTFont(ASSETS/'fonts/HOHONETSans-Regular.otf')
    glyphs=set(font.getBestCmap())
    chinese={ord(c) for c in document.text_content() if '\u3400'<=c<='\u9fff' or '\uf900'<=c<='\ufaff'}
    missing=sorted(chinese-glyphs)
    assert not missing,missing
    original_data_sha256=hashlib.sha256((ASSETS/'data.js').read_bytes()).hexdigest()
    assert original_data_sha256=='20434a744d5f9964319384434fa77fd39691de6df995952f3d020a894b4fa5a5'
    checks=dict(status='PASS',decision_rows=len(decisions),unique_DOM_ids=True,
                chinese_codepoints_checked=len(chinese),missing_chinese_codepoints=missing,
                original_data_js_sha256=original_data_sha256,
                validation_scope='Static DOM and font coverage; no new browser interaction run claimed.')
    (BASE/'WORKBENCH_STATIC_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(page=str(PAGE.relative_to(ROOT)),decision_rows=len(decisions),
                          original_endpoint_data_changed=False,font_updated=bool(args.font_source))))


if __name__=='__main__':
    main()
