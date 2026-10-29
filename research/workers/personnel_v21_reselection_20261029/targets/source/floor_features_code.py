"""按用户确认的底面范围生成难度工作版本；不修改GT、点对、资格或旧分类。"""
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.gt_order_visibility_20261009 import visibility_from_floor, classify_ring_x

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/scope_difficulty_audit_20261011'
PRIOR = ROOT / 'analysis_results/image_difficulty_full_review_20261010'
VERSION = 'scope_conditioned_difficulty_20261011_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def floor_features(floor):
    p = np.asarray(floor, dtype=float)
    vis = visibility_from_floor(p)
    incoming, outgoing = p - np.roll(p, 1, axis=0), np.roll(p, -1, axis=0) - p
    lengths = np.linalg.norm(incoming, axis=1) * np.linalg.norm(outgoing, axis=1)
    assert np.all(lengths > 0), 'zero_length_edge'
    sine = np.abs(incoming[:, 0] * outgoing[:, 1] - incoming[:, 1] * outgoing[:, 0]) / lengths
    straight = np.flatnonzero((sine <= 1e-8) & ((incoming * outgoing).sum(axis=1) > 0))
    order = classify_ring_x((np.arctan2(p[:, 0], -p[:, 1]) / (2 * np.pi) + .5) * 1024)
    return dict(N_floor=len(p), N_turn=len(p)-len(straight),
                straight_vertices_1based=(straight+1).tolist(),
                H=None if vis['hidden_vertices_1based'] is None else len(vis['hidden_vertices_1based']),
                hidden_vertices_1based=vis['hidden_vertices_1based'],
                geometry_status=vis['status'], ring_class=order['x_order_class'])


def assemble(prior, refs, notes):
    old = {r['image']: r for r in prior}
    decisions = {r['image']: r for r in notes}
    assert len(decisions) == len(notes) == len(refs) == 35
    assert set(decisions) == {r['image_code'] for r in refs}
    reviews = []
    for ref in refs:
        code = ref['image_code']
        d = decisions[code]
        assert (d['image_id'], d['reference_id']) == (ref['image_id'], ref['reference_id'])
        assert d['reviewed'] and bool(d['question']) == d['needs_user_review']
        assert d['needs_user_review'] == (d['current_class'] == '待复核')
        before = old.get(code)
        assert ref['in_current_formal_corpus'] == (before is not None)
        if before:
            assert before['image_id'] == ref['image_id']
            assert before['gt_object_id'] == ref['selected_gt_object_id']
        features = floor_features(ref['floor_xz_h'])
        if d['current_class'] == '简单':
            assert features['N_turn'] in (4, 6) and features['H'] == 0
            assert d['V'] in ('none', 'limited')
        if d['current_class'] == '中等':
            assert features['H'] == 0 and (features['N_turn'] >= 8 or d['V'] == 'substantial')
        if before and before['visual']['difficulty_recommendation'] in ('单列', '特殊单列'):
            assert d['current_class'] in ('单列', '特殊单列'), 'cannot erase special scene gate'
        review = dict(d, features=features, in_corpus=ref['in_current_formal_corpus'],
                      scope_decision=ref['decision'], top_boundary_pending=ref['top_boundary_pending'],
                      reference_ready=ref['reference_ready'],
                      previous_visual_class=before['visual']['difficulty_recommendation'] if before else None,
                      previous_working_class=before['working_class'] if before else None,
                      previous_gt_object_id=ref['selected_gt_object_id'],
                      previous_N=before['N'] if before else None,
                      previous_H=before['H'] if before else None,
                      scene=before['scene'] if before else 'reference_only',
                      oos_subtype=before['visual']['oos_subtype'] if before else 'unknown',
                      doorway_status=before['visual']['doorway_status'] if before else 'unknown',
                      external_review=before['external_review'] if before else None)
        reviews.append(review)
    changed = {r['image']: r for r in reviews if r['in_corpus']}
    current = []
    for oldrow in prior:
        r = changed.get(oldrow['image'])
        current.append(dict(image=oldrow['image'], image_id=oldrow['image_id'],
            scene=oldrow['scene'], oos_subtype=oldrow['visual']['oos_subtype'],
            doorway_status=oldrow['visual']['doorway_status'],
            current_class=r['current_class'] if r else oldrow['visual']['difficulty_recommendation'],
            target_version=r['reference_id'] if r else oldrow['gt_object_id'],
            classification_basis='confirmed_floor_and_photo_review' if r else 'inherited_visual_v2',
            previous_visual_class=oldrow['visual']['difficulty_recommendation'],
            previous_working_class=oldrow['working_class'], old_gt_N=oldrow['N'], old_gt_H=oldrow['H'],
            scope_review=r, classification_status='exploratory_working_class',
            top_boundary_pending=r['top_boundary_pending'] if r else None))
    assert len(current) == len({r['image_id'] for r in current}) == 259
    return reviews, current


def main():
    refs = read(OUT / 'reference_registry_snapshot.json')['records']
    reviews, current = assemble(read(PRIOR / 'review_data.json'), refs,
                                read(OUT / 'visual_decisions.json')['records'])
    user = {r['image']: r for r in read(PRIOR / 'user_review_20261010/source_review.json')['records']}
    for r in reviews:
        r['previous_user_review'] = user.get(r['image'])
    summary = dict(version=VERSION, reviewed=35, in_corpus=33, reference_only=2,
                   reviewed_counts=dict(Counter(r['current_class'] for r in reviews)),
                   current_259_counts=dict(Counter(r['current_class'] for r in current)),
                   pending=[r['image'] for r in reviews if r['needs_user_review']],
                   changed_from_visual_v2=sum(r['current_class'] != r['previous_visual_class'] for r in current))
    write(OUT / 'review.json', dict(version=VERSION, summary=summary, records=reviews))
    write(OUT / 'current_259.json', dict(version=VERSION, records=current))
    write(OUT / 'pending_review.json', dict(version=VERSION, records=[r for r in reviews if r['needs_user_review']]))
    columns = ['image','image_id','current_class','previous_visual_class','previous_working_class',
               'target_version','classification_basis','scene','oos_subtype','doorway_status',
               'old_gt_N','old_gt_H','new_N_floor','new_N_turn','new_H','top_boundary_pending','question']
    with (OUT / 'current_259.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader()
        for r in current:
            s = r['scope_review']; row = {k:r.get(k) for k in columns}
            row.update(new_N_floor=s['features']['N_floor'] if s else None,
                       new_N_turn=s['features']['N_turn'] if s else None,
                       new_H=s['features']['H'] if s else None, question=s['question'] if s else '')
            w.writerow(row)
    write(PRIOR / 'CURRENT.json', dict(version=VERSION,
          table='../scope_difficulty_audit_20261011/current_259.csv',
          details='../scope_difficulty_audit_20261011/current_259.json',
          review='../scope_difficulty_audit_20261011/review.html',
          status='exploratory_working_class; new targets are floor-only; no GT/eligibility change'))
    template = (OUT / 'review_template.html').read_text(encoding='utf-8')
    (OUT / 'review.html').write_text(template.replace('__DATA__', json.dumps(reviews, ensure_ascii=False).replace('</', '<\\/')), encoding='utf-8')
    lines = ['# 确认范围后的逐图难度复核', '',
             '2026-10-11。已逐张查看35张照片及新旧底面对照，33张进入259图当前工作表，2张仅参考。', '',
             '这是目标空间条件下的探索性粗分类；顶边尚未确认，不是完整3D参考发布。原GT、旧分类、人员资格不改。', '',
             f"本轮35张：{summary['reviewed_counts']}；当前259图：{summary['current_259_counts']}。", '',
             f"相对v2视觉建议，{summary['changed_from_visual_v2']}张发生档位变化。11张需人工复核；其余226张继承v2视觉建议，不能称本轮重新看过。", '',
             '[待核与全部35张对照页面](review.html)、[259图当前工作表](current_259.csv)、[完整字段](current_259.json)、[待核清单](pending_review.json)。', '',
             '## 方法与版本', '',
             '固定图片与用户确认的目标空间，再计算底面顶点数N_floor、转折数N_turn、严格结构自遮挡H及循环环序。N_floor不是已确认上下点对数。N_turn只扣除同向共线中间点（归一化叉积≤1e-8且点积>0），不改变原坐标、不删除近似共线点；wc2-03的第5点和wc2-61的第4点因此为5点/4转折。其它9/13点原样保留。', '',
             '新底面工作类沿用少量4/6转折且H=0、定位线索足够为简单；H=0且≥8转折为中等；H>0须证实必要隐藏实体结构才能判困难。照片证据不足、玻璃/停止边与实心墙模型冲突、门洞状态未决时单列待核。4张9点中等图有近直线点，但多处主体转折仍足以支持中等，无需合并或调整阈值。', '',
             'OOS、门洞、可标性原字段保留；本轮门洞交界疑点仅是待确认问题，不将“图中有门”标成门洞交界。无特殊场景被改为普通图。照片V是Codex定性判读；用户确认的是范围，不能写成用户已认可本次难度。新旧空间均保留，不按较易或最高IoU自动选取。', '',
             '数据来自上一轮固定云端回执的reference_registry_snapshot.json；snapshot保留原回执的来源绑定，visual_decisions.json记录本轮逐图判断。重建命令：python -m tools.thesis_main.analysis.scope_difficulty_review_20261011。CURRENT.json为新入口，旧日期化表和旧v2证据保留。', '',
             '## 全部35张', '', '|图片|旧视觉类|新范围类|新底面点/转折/H|依据与待核问题|', '|---|---|---|---|---|']
    for r in reviews:
        f = r['features']
        lines.append(f"|{r['image']}|{r['previous_visual_class'] or '参考图'}|{r['current_class']}|{f['N_floor']}/{f['N_turn']}/{f['H']}|{r['visible_evidence']} {r['question']}|")
    lines += ['', '## 边界与验证', '',
              '未改规范合同consensus_research_20260923_v1，未重算人员质量或融合曲线，未提交/推送或合并云端main。顶边待确认、透明/虚拟边界和目标选择引入的差异继续保留。既往报告为原版本快照，本报告取代其“本轮尚未审新范围”的状态描述。', '',
              '新增测试覆盖同向共线与近共线区别、不可计算不填零、35/33/2与259图分母、其余226图继承、特殊属性保留及错绑/重复回执拒绝。图卡是保留的分析证据；临时审查拼页和浏览器截图清理。']
    (OUT / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()

