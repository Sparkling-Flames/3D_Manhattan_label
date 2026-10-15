"""独立复算固定836面板与逐图诊断；不拟合分类，不修改标签或分数。"""
import html
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_separation_audit_20261015'
DR = ROOT / 'analysis_results/difficulty_scope_preferred_20261011'
METRICS = ['WQ', 'A10', 'B8L2', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']
PRIORITY = {
    'wc2JMjhGNzB-53': ('范围与参考', '照片同时显示浴室主体和厕间开口，旧外部回执明确写“范围明显不同”。先核查工人是否按同一范围作答，再判断局部窄转折难度；不能因为质量参考与难度目标一致，就断言工人也选择了该范围。'),
    'wc2JMjhGNzB-60': ('墙体与柜体', '当前四角有两角靠柜体，柜体前缘、后墙及门口停止面可能混淆。中等定位负担有依据，仍需明确角点1/4对应的墙位置；不应因为分数低改为困难。'),
    'pa4otMbVnkk-05': ('遮挡还是难推断', '独立查看图卡及原图：主要上方墙线较清楚，拼接边的窄转折下端被家具挡住。旧理由不足以单凭“被挡”证明高推断负担。建议优先复核困难是否偏高，先核查接缝处3/4点；本轮不直接降档。'),
    'uNb9QFRL6hY-86': ('局部隐藏与整体难度', '大部分卧室轮廓清楚，3/4点附近是门后局部隐藏结构。必须精确恢复全部目标角时存在推断负担；若研究评估整体范围，困难标签可能夸大其整体影响。请判局部线索是否足以确定隐藏尺寸，不按高分改类。'),
    'q9vSo1VnCiC-34': ('局部隐藏与目标细节', '主卧室清楚，2/3/4点在右侧小转折，柜体干扰下端。第三方旧评简单、当前评困难。需说明这些点属于必要墙体，及上部线索是否足够；局部占比小不等于推断容易。'),
    'uNb9QFRL6hY-54': ('门口停止面与底界', '八个上方转折总体可辨，但开口、台阶与连接空间影响底界解释。“无家具遮挡”不能推出整体好标。优先核查1/2点附近的停止面与底面高度；暂不据照片新增OOS或门洞标签。'),
}
NOTES = {
    'jtcxE69GiFV-03': '窗侧帘与椅遮挡角位，上下端直接定位不足；中等补全负担有依据。',
    'jtcxE69GiFV-13': '主要六角的上边较清楚，窗帘和浴缸影响局部下端；中等/简单边界可讨论，高分仅来自2份作答。',
    'yqstnuAEVhm-27': '八处转折和主要墙脚可辨；中等主要体现表达数量，不应宣称高遮挡推断负担。',
    'pa4otMbVnkk-11': '主体卧室与入口凹槽清楚，局部家具挡底部；八角操作负担成立，仅1份作答不足评价类别表现。',
    'x8F5xyUWy9e-03': '八处转折含窄凹入，上部轮廓较明确，下端部分被床柜挡住；中等表达/定位负担基本合理。',
    'uNb9QFRL6hY-14': '门扇影响入口角位，主体其它角清楚；中等定位补全有依据，不能借其它视角补线索。',
    'zsNo4HB9uLZ-09': '柜体遮住必要角位、门扇邻近另一个角；四点不等于简单，中等判断有依据。',
    'pa4otMbVnkk-18': '暗色房间中央小凹槽必要角隐藏，家具遮住底边；困难有图像依据，但只有1份评分。',
    'B6ByNegPMKs-47': '近柱垛背面小转折与较多墙线并存，不能仅凭正面线定位所有角；保留困难依据。',
    'X7HyMhZNoso-07': '左侧密集跨空间转折含背面角；困难有依据，仍需区分未画某空间与定位误差。',
    '7y3sRwLe3Va-03': '冰箱/高柜后的必要角位上下均受干扰；固定当前目标时困难有依据。',
    'yqstnuAEVhm-09': '十四点含壁炉/入口窄转折；按既定GT保留复杂性，不重开此前搁置的壁炉细节裁决。',
    'VFuaQ6m2Qom-10': '多组柱垛与镜面、柜体邻近，既有表达与隐藏负担；保留困难，局部遗漏对总分影响仍待作答对照。',
    '7y3sRwLe3Va-21': '当前目标跨入口及卧室，近墙遮住局部背面；固定目标时有困难依据，不能据此排除范围选择差异。',
    'VFuaQ6m2Qom-04': '多组柱垛窄角和反射邻近结构，十四点表达及局部背面角负担成立。',
    'VFuaQ6m2Qom-07': '十六点包括淋浴间柱垛和镜柜邻近小转折；困难依据存在，评分较高不构成降档理由。',
    '7y3sRwLe3Va-26': '主要走道边界清楚，近门垛有局部背向小转折；局部推断负担存在，整体影响不宜夸大。',
    'yqstnuAEVhm-08': '砖柱/柜侧必要小转折局部受挡；按完整六角目标有推断负担，不把整体清楚等同所有角可定位。',
}


def main():
    all_rows = pd.read_csv(ROOT / 'research/statistics/descriptive_statistics_20261015/records.csv')
    panel = pd.read_csv(ROOT / 'research/difficulty/difficulty_target_integration_20261015/ordinary_same_target_panel.csv')
    scores = pd.read_csv(ROOT / 'research/quality/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv')
    a = all_rows[all_rows.in_target_836.eq(True)].copy()
    assert len(a) == a.object_id.nunique() == 836 and a.image_id.nunique() == 95
    assert not a.duplicated(['worker_id', 'image_id']).any()
    assert set(a.object_id) == set(panel.object_id)
    joined = a.merge(scores, on='record_id', suffixes=('', '_source'), validate='one_to_one')
    assert len(joined) == 836
    for key in ['object_id', 'image_id', 'worker_id', 'reference_id', 'condition']:
        assert joined[key].equals(joined[key + '_source']), key
    assert np.allclose(joined.B8L2, joined.Q_B8L2, atol=1e-10, rtol=0)
    I, s, d, hm, hc = (a[k].to_numpy() for k in ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter'])
    assert np.isfinite(np.array([I, s, d, hm, hc])).all() and (I > 0).all()
    F = 1 / I - 1 + s*s / 32
    D = 1.5 * d*d / (d*d + 64)
    recalc = 100 / (1 + np.hypot(F, D) + (hm/.8)**2 + (hc/.25)**2)
    error = float(np.max(np.abs(recalc-a.B8L2.to_numpy())))
    assert error < 1e-9
    ds = {r['image_id']: r for r in json.loads((DR/'current_259.json').read_text(encoding='utf-8-sig'))['records']}
    g = a.groupby(['difficulty_class', 'image_id', 'image_code'], as_index=False).agg(
        n=('B8L2', 'size'), **{k: (k, 'mean') for k in METRICS})
    for _, r in g.iterrows():
        assert ds[r.image_id]['current_class'] == r.difficulty_class
        assert set(a.loc[a.image_id.eq(r.image_id), 'difficulty_target_id']) == {ds[r.image_id]['selected']['target_id']}
    summary = []
    for label, x in g.groupby('difficulty_class'):
        answer = a[a.difficulty_class.eq(label)]
        loo = (x.B8L2.sum()-x.B8L2)/(len(x)-1)
        summary.append(dict(difficulty=label, images=len(x), answers=len(answer),
            answer_mean=answer.B8L2.mean(), image_mean=x.B8L2.mean(), image_median=x.B8L2.median(),
            images_with_at_most_two_answers=int(x.n.le(2).sum()),
            leave_one_image_out_min=loo.min(), leave_one_image_out_max=loo.max(),
            min_three_answers_images=int(x.n.ge(3).sum()), min_three_answers_image_mean=x.loc[x.n.ge(3),'B8L2'].mean()))
    detail = g[g.difficulty_class.ne('简单')].copy()
    assert len(detail) == 24 and set(detail.image_code) == set(PRIORITY) | set(NOTES)
    for key in ['N_turn', 'H', 'inference_burden', 'evidence']:
        detail[key] = [ds[i][key] for i in detail.image_id]
    detail['audit_opinion'] = [PRIORITY[c][1] if c in PRIORITY else NOTES[c] for c in detail.image_code]
    detail['priority_review'] = detail.image_code.isin(PRIORITY)
    w = a.groupby(['worker_id', 'difficulty_class']).B8L2.mean().unstack().dropna(subset=['中等', '困难'])
    medium = a[a.difficulty_class.eq('中等')]
    heavy = medium.image_code.isin(['wc2JMjhGNzB-53', 'wc2JMjhGNzB-60'])
    checks = dict(records=836, images=95, unique_person_image=True, max_B8L2_recalculation_error=error,
        medium_two_images_answers=int(heavy.sum()), medium_two_images_mean=medium.loc[heavy,'B8L2'].mean(),
        medium_other_34_answers_mean=medium.loc[~heavy,'B8L2'].mean(),
        both_group_workers=len(w), within_worker_hard_minus_medium_mean=(w['困难']-w['中等']).mean(),
        within_worker_comparison_is_not_image_matched=True, classification_changed=False,
        review_is_not_blind=True, visual_review='24 existing GT cards; 2 original photos (pa05,wc60); no worker overlay review')
    OUT.mkdir(exist_ok=True)
    pd.DataFrame(summary).to_csv(OUT/'group_summary.csv', index=False, encoding='utf-8-sig')
    g.to_csv(OUT/'image_means_95.csv', index=False, encoding='utf-8-sig')
    detail.to_csv(OUT/'review_24.csv', index=False, encoding='utf-8-sig')
    g.groupby('difficulty_class')[METRICS].mean().to_csv(OUT/'image_equal_components.csv', encoding='utf-8-sig')
    (OUT/'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    cards = []
    codes = list(PRIORITY) + sorted(set(NOTES))
    for code in codes:
        r = detail[detail.image_code.eq(code)].iloc[0]; z = ds[r.image_id]
        img = DR/z['card']; photo = Path(z['photo'])
        assert img.exists() and photo.exists()
        rel = lambda p: html.escape(os.path.relpath(p, OUT).replace('\\', '/'), quote=True)
        old = json.dumps(z['external_review'], ensure_ascii=False) if z['external_review'] else '无已记录第三方回执'
        cards.append(f'<section id="{code}"><h2>{code} · {r.difficulty_class}'+(' · 优先复核' if code in PRIORITY else '')+
            f'</h2><a href="{rel(photo)}">打开原图</a><img loading="lazy" src="{rel(img)}" alt="{code} 当前目标角点图">'
            f'<p><b>本轮看法：</b>{html.escape(r.audit_opinion)}</p>'
            f'<details><summary>旧依据、第三方结论和数值（建议看图后展开）</summary><p>{html.escape(z["evidence"])}</p><p>{html.escape(old)}</p>'
            f'<p>N={z["N_turn"]}，H={z["H"]}；{r.n}份作答，B8L2均值{r.B8L2:.2f}。目标：{html.escape(z["selected"]["target_id"])}</p></details></section>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>难度分离独立复核</title><style>body{font:17px/1.65 system-ui;max-width:1160px;margin:28px auto;padding:0 18px;background:#fafafa;color:#222}section{background:white;border:1px solid #ddd;padding:20px;margin:28px 0}img{display:block;width:100%;height:auto;margin:14px 0}summary{cursor:pointer}a{color:#165aaa}</style><h1>先复核6张，另18张留作对照</h1><p>本轮问题是目标范围、角点是否可推断、局部负担与整体负担。请指出具体点位与线索，不为得到分数排序而改档。这里不写回标签；可在聊天中按图片编号给意见。本轮已看过质量结果，不属于盲评。</p><p>'+ ' · '.join(f'<a href="#{c}">{c}</a>' for c in PRIORITY)+'</p>'+''.join(cards)+'</html>'
    (OUT/'review.html').write_text(page, encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False))
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == '__main__':
    main()
