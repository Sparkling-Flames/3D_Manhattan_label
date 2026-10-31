"""Collect existing GT/scope evidence without changing geometry or eligibility."""
import csv
import gzip
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/data/gt_revision_collection_20261031'
EXT = ROOT / 'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028/extension_v1'
ORTH = EXT / 'orthogonal_v2_user_axes'
ADOPT = EXT / 'adopted_references_20261028'
CEILING = ADOPT / 'ceiling_adopted_20261028'
DOOR = ROOT / 'research/data/doorway_review_20261030'
FULL = DOOR / 'curve_preparation_v21/full_review_20261031'
AUDIT = DOOR / 'pro_delivery_independent_audit_20261031'
RELEASE = ROOT / 'research/data/releases/v2.1/reference_catalog.json'
GROUPS = {
    'saved_manual_gt': '用户保存的30张人工GT',
    'confirmed_scope': '不同空间范围：41图43空间',
    'explicit_revision': '后续两张明确删点修订',
    'ceiling_adoption': '后续30份顶面采用（与人工30图不同）',
    'doorway': '门洞及边界案例：含待定与OOS',
}
# Interpretation of the existing issue evidence, not a new physical-wall verdict.
DOOR_TYPES = {
    '2t7WUuJeko7-07': 'user_reported_missing_corners',
    '7y3sRwLe3Va-06': 'suspected_wall_offset',
    '7y3sRwLe3Va-10': 'suspected_missing_local_geometry',
    '7y3sRwLe3Va-18': 'suspected_wall_offset_and_scope_rule',
    'B6ByNegPMKs-42': 'implementation_or_numeric_only',
    'B6ByNegPMKs-43': 'suspected_wall_offset',
    'S9hNv5qa7GM-08': 'suspected_wall_offset',
    'b8cTxDM8gDG-08': 'scope_rule_or_real_shape',
    'jh4fc5c5qoQ-09': 'suspected_local_geometry_or_cut_interaction',
    'jh4fc5c5qoQ-14': 'suspected_missing_local_geometry',
    'jtcxE69GiFV-12': 'scope_rule_or_real_shape',
    'pRbA3pwrgk9-01': 'oos_not_doorway_analysis',
    'pRbA3pwrgk9-11': 'oos_not_doorway_analysis',
    'q9vSo1VnCiC-04': 'suspected_wall_offset',
    'q9vSo1VnCiC-13': 'adopted_axis_binding_fixed',
    'q9vSo1VnCiC-24': 'user_kept_pending',
    'uNb9QFRL6hY-21': 'suspected_wall_offset_and_implementation',
    'uNb9QFRL6hY-25': 'frame_depth_uncertain',
    'uNb9QFRL6hY-47': 'suspected_wall_offset_and_implementation',
    'uNb9QFRL6hY-83': 'occluded_offset_and_implementation',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rel(path):
    return path.relative_to(ROOT).as_posix()


def build():
    manual = list(csv.DictReader((ORTH / 'SAVED_MANUAL_GT_AUDIT.csv').open(encoding='utf-8-sig')))
    frozen_path = ROOT / 'research/data/releases/v2/analysis_input/data.json.gz'
    with gzip.open(frozen_path, 'rt', encoding='utf-8') as f:
        frozen_manual = {r['object_id']: r for r in json.load(f)['objects']
                         if r['object_kind'] == 'gt_manual_revision'}
    assert set(frozen_manual) == {r['object_id'] for r in manual}
    adopted = read(ADOPT / 'ADOPTED_REFERENCES.json')
    ceiling = read(CEILING / 'ADOPTED_REFERENCES.json')
    current = {r['target_id']: r for r in read(RELEASE)}
    final = {r['image']: r for r in read(FULL / 'ALIGNMENT_DECISIONS.json')}
    closeout = read(FULL / 'FINAL_USER_CLOSEOUT.json')
    issues = {r['image']: r for r in read(FULL / 'ISSUE_LEDGER.json')}
    scope_rules = {r['image']: r for r in read(DOOR / 'curve_preparation_v21/supplement_20261031/GT_ISSUE_LEDGER.json')}
    cases = {r['image']: r for r in json.loads((DOOR / 'data.js').read_text(encoding='utf-8').split('=', 1)[1][:-1])['cases']}
    rows = []

    def add(group, image, image_id, target_id, status, description, sources, detail, evidence=None):
        r = dict(entry_id=f'{group}:{len(rows)+1:03d}', group=group, image=image,
                 image_id=image_id, target_id=target_id, status=status, description=description,
                 sources=[rel(p) for p in sources], detail=detail,
                 evidence=[rel(p) for p in (evidence or [])], raw_gt_changed_this_collection=False,
                 original_gt_error_established_by_this_collection=False,
                 human_review_required_now=False)
        ref = current.get(target_id)
        r['release_reference'] = ({k: ref.get(k) for k in ['reference_version', 'current_target',
            'full_reference_available', 'image_analysis_blocked', 'image_analysis_hold_reasons', 'role']}
            if ref else None)
        rows.append(r)

    for r in manual:
        add('saved_manual_gt', r['image'], r['image_id'], r['object_id'], r['adoption'],
            '已保存的用户人工GT版本；逐图修改动机与原始GT具体错误类型不能仅由保存状态推断。OOS/暂停/历史身份继续保留。',
            [ORTH / 'SAVED_MANUAL_GT_AUDIT.csv', frozen_path, ROOT / 'export_label/groudTruth.json',
             ADOPT / 'USER_ADOPTION_RECEIPT.json', RELEASE],
            {**r, 'saved_manual_points_1024x512': frozen_manual[r['object_id']]['points_1024x512']},
            [ORTH / 'manual_gt_review' / (r['image'] + '.png')])
    for r in adopted:
        if r['kind'] not in ('confirmed_scope', 'explicit_user_revised_GT'):
            continue
        is_scope = r['kind'] == 'confirmed_scope'
        add('confirmed_scope' if is_scope else 'explicit_revision', r['image'], r['image_id'], r['target_id'],
            'user_adopted_reference',
            ('已确认空间范围；不同范围不是原GT错误的充分证据。是否存在不可见空间推断、门洞停止面规则冲突，需另有逐图证据。'
             if is_scope else '用户明确删点修订，后续采用用户轴下正交约束；保留修订前后版本。'),
            [ADOPT / 'ADOPTED_REFERENCES.json', ADOPT / 'USER_ADOPTION_RECEIPT.json', RELEASE],
            {k: r.get(k) for k in ['original_points', 'original_floor', 'points_1024x512', 'floor_xz_h',
                                  'adoption_method', 'reference_version', 'kept_1based']})
        if not is_scope:
            source = (ROOT / 'research/difficulty/difficulty_user_revision_20261015/user_revised_gt.json'
                      if r['image'] == '7y3sRwLe3Va-26' else
                      ROOT / 'research/difficulty/difficulty_review_update_20261015/x8F5xyUWy9e-03_user_gt.json')
            rows[-1]['sources'].append(rel(source))
            rows[-1]['detail']['explicit_revision_receipt'] = read(source)
    for r in ceiling:
        assert current[r['target_id']]['points_1024x512'] == r['points_1024x512']
        assert current[r['target_id']]['reference_version'] == r['reference_version']
        add('ceiling_adoption', r['image_code'], r['image_id'], r['target_id'], 'user_adopted_ceiling',
            '顶高采用记录：固定已采用底面与全部x，更新top y；高度由top/bottom共同决定，不归因于top单方错误。',
            [CEILING / 'ADOPTED_REFERENCES.json', CEILING / 'USER_REVIEW.json',
             CEILING / 'USER_ADOPTION_RECEIPT.json', RELEASE],
            {k: r.get(k) for k in ['previous_reference_version', 'reference_version', 'ceiling_adoption']})
    assert set(final) == set(issues) == set(DOOR_TYPES)
    for image, r in final.items():
        assert 'space_polygons' in r or DOOR_TYPES[image] == 'oos_not_doorway_analysis'
        evidence = [FULL / (image + '_review.png')]
        evidence = [p for p in evidence if p.exists()]
        add('doorway', image, r['image_id'], cases[image]['reference_id'], DOOR_TYPES[image],
            '门洞局部GT疑点、范围规则和切分实现分别记录；认可空间切分不等于确认原GT错误。',
            [FULL / 'ISSUE_LEDGER.json', FULL / 'ALIGNMENT_DECISIONS.json', FULL / 'FINAL_USER_CLOSEOUT.json',
             FULL / 'index.html', AUDIT / 'computed_delta/RESULTS_ZH.md'],
            {'historical_issues': issues[image]['issues'], 'latest_scope_notes': r['notes'],
             'latest_display_note': r.get('closeout_display_and_scope_note'),
             'user_closeout': closeout.get(image, closeout['other_images']),
             'space_polygons': r.get('space_polygons'),
             'historical_geometric_occlusion_indices': scope_rules.get(image, {}).get('geometric_occlusion_corner_indices'),
             'visibility_boundary': '几何射线遮挡不等于RGB不可见；本轮未重新裁决遮挡区域。',
             'historical_text_override': '以最终采用及计算结果为准：7y-18旧紫色未分配段已被接入空间2；2t7当前参考可诊断评分，另行修订GT不在当前范围。'}, evidence)
    by_image = defaultdict(list)
    for r in rows:
        by_image[r['image']].append(r)
    index = []
    for image, entries in sorted(by_image.items()):
        ids = {r['image_id'] for r in entries}
        assert len(ids) == 1, (image, ids)
        image_id = ids.pop()
        photos = [ROOT / 'data/mp3d_layout' / s / 'img' / f'{image_id}.png'
                  for s in ('train', 'valid', 'test')]
        originals = [ROOT / 'data/mp3d_layout' / s / 'label_cor' / f'{image_id}.txt'
                     for s in ('train', 'valid', 'test')]
        photos = [p for p in photos if p.exists()]
        originals = [p for p in originals if p.exists()]
        assert len(photos) == 1 and len(originals) == 1, (image, photos, originals)
        index.append(dict(image=image, image_id=image_id, groups=sorted({r['group'] for r in entries}),
                          entries=[r['entry_id'] for r in entries], photo=rel(photos[0]),
                          original_mp3d_points=rel(originals[0])))
    assert len(manual) == len(ceiling) == 30
    assert Counter(r['adoption'] for r in manual) == Counter(current_in_use=22,
        OOS_no_orthogonalization=4, excluded_hold=1, historical_not_current=3)
    counts = Counter(r['group'] for r in rows)
    assert counts == Counter(saved_manual_gt=30, confirmed_scope=43, explicit_revision=2,
                             ceiling_adoption=30, doorway=20)
    assert len({r['image'] for r in rows if r['group'] == 'confirmed_scope'}) == 41
    for r in rows:
        for path in r['sources'] + r['evidence']:
            assert (ROOT / path).is_file(), path
    checks = {'entries': len(rows), 'unique_images': len(index), 'group_counts': dict(counts),
              'purpose': 'collect_error_suspicion_and_hidden_scope_evidence_for_final_report',
              'new_gt_revision_in_scope': False,
              'manual_and_ceiling_image_overlap': len({r['image'] for r in manual} & {r['image_code'] for r in ceiling}),
              'source_and_photo_links_exist': True, 'new_physical_gt_verdicts': 0,
              'ceiling_30_match_release_geometry_and_version': True,
              'scoring_or_geometry_recomputed': False}
    return rows, index, checks


def write_page(rows, index, checks):
    def link(path, label):
        href = Path(os.path.relpath(ROOT / path, OUT)).as_posix()
        return f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
    lookup = {r['entry_id']: r for r in rows}
    cards = []
    for im in index:
        entries = [lookup[k] for k in im['entries']]
        contents = []
        for r in entries:
            links = ' · '.join(link(p, Path(p).name) for p in r['sources'])
            ev = ' · '.join(link(p, '既有复核叠线图（历史阶段）') for p in r['evidence'])
            contents.append(f'<details><summary>{html.escape(GROUPS[r["group"]])}：{html.escape(r["status"])}</summary>'
                f'<p>{html.escape(r["description"])}</p><p>{links}</p><p>{ev}</p>'
                f'<pre>{html.escape(json.dumps(r["detail"], ensure_ascii=False, indent=2))}</pre></details>')
        photo = Path(os.path.relpath(ROOT / im['photo'], OUT)).as_posix()
        cards.append(f'<article id="{im["image"]}"><h2>{im["image"]}</h2><p>'
            + '；'.join(GROUPS[g] for g in im['groups']) + '</p>'
            + f'<details><summary>展开原图</summary><img loading="lazy" alt="{im["image"]} 原始全景图" src="{photo}"></details>'
            + '<p>' + link(im['original_mp3d_points'], '原始MP3D点位') + '</p>' + ''.join(contents) + '</article>')
    nav = ''.join(f'<details><summary>{label}</summary><p>' + ' · '.join(
        f'<a href="#{im["image"]}">{im["image"]}</a>' for im in index if group in im['groups'])
        + '</p></details>' for group, label in GROUPS.items())
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>GT修订与空间范围问题集</title>'
        '<style>body{max-width:1150px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui;color:#182331;background:#f5f7fa}'
        'article{background:white;padding:20px;margin:22px 0;border:1px solid #d9dfe6;border-radius:10px}'
        'a{color:#0659a4}img{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}'
        'summary{cursor:pointer;padding:8px 0}h1{font-size:28px}</style>'
        f'<h1>GT修订、范围差异与门洞疑点</h1><p>2026-10-31 · {checks["unique_images"]}张去重图片，'
        f'{checks["entries"]}条分组记录。各组有交集，不相加当作错误图片数。</p>'
        '<p>用于最后汇报GT错误、可疑及“开天眼”范围规则问题，不修订GT，不要求重新审核已确认几何。人工30图与顶面30份是不同集合；'
        '疑似GT错、规则歧义、已修复切分程序问题分别保留。历史叠线图不冒充最新采用图。</p>'
        '<p><a href="REPORT_SUMMARY.md">问题汇报材料</a> · <a href="RESEARCH_STATUS.md">研究现状与缺口</a> · <a href="HUMAN_REVIEW.md">人工复核条件</a> · '
        '<a href="CASE_LEDGER.json">完整问题账本</a> · <a href="IMAGE_INDEX.json">去重图片索引</a></p>'
        + nav + ''.join(cards) + '</html>')


def main():
    rows, index, checks = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in [('CASE_LEDGER.json', rows), ('IMAGE_INDEX.json', index), ('CHECKS.json', checks)]:
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'index.html').write_text(write_page(rows, index, checks), encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
