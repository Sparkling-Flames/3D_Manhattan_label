#!/usr/bin/env python3
"""Readable LOBO class roles and old, saved same-room panel examples.

No clustering, fusion, scoring or reconstruction of missing large-block data.
Run with --repo PATH; or rerun from this output directory using copied inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pandas as pd

BASE = Path('research/same_room/same_room_current_classes_v2_20261023')
STAGE = 'main_existing_small_block'
FILES = {
    'centers': 'source_index/CURRENT_MANUAL_FOLD_CENTERS.csv',
    'labels': 'source_index/CURRENT_MANUAL_LABELS_LOBO.csv',
    'interface': 'source_index/CURRENT_TAXONOMY_INTERFACE_ZH.md',
    'panels': 'design/PANELS.csv',
    'g015_teams': 'results/taxonomy_response/cases/CASE_G015_COMPOSITION_MEMBERS.csv.gz',
    'g015_panels': 'results/taxonomy_response/cases/CASE_G015_PANEL_SUMMARY.csv',
    'g015_same': 'results/taxonomy_response/cases/CASE_G015_SAME_CLASS_W104_W120.csv',
}
KEY_WORKERS = ['W112', 'W115', 'W032', 'W109', 'W122', 'W028',
               'W008', 'W029', 'W034', 'W035', 'W127']
METRICS = ['B8L2', 'D10', 'fusion_turn_n', 'fusion_short_turn_edges',
           'fusion_redundancy_n', 'ref_node_recall_9', 'ref_edge_recall_9',
           'S_bottom_deg', 'dir', 'Hmean', 'omission', 'extension',
           'recorded_time_total_seconds', 'failure']


def pipe_members(value):
    return [] if pd.isna(value) or value == '' else str(value).split('|')


def dump(df, path):
    df.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.12g')


def role_text(row, fold):
    family = row['selected_family']
    turn = row['turn_history_mean']
    short = row['short_history_mean']
    red = row['redundancy_history_mean']
    cturn = row['complex_turn_history_mean']
    if row['method'] == 'V3_BEHAVIOR' and family == 'TURN':
        ordered = fold.sort_values('turn_history_mean').class_id.tolist()
        rank = ordered.index(row['class_id'])
        if len(ordered) == 3:
            names = ['复杂结构明显简化', '常规转折表达', '较多转折与短细节表达']
            role = names[rank]
            alignment = ['TURN3_COMPLEX_SIMPLIFY', 'TURN3_REGULAR', 'TURN3_MORE_DETAIL'][rank]
        elif len(ordered) == 2:
            role = ['较少转折（本折两类，并非明显简化专类）', '较多转折与短细节（本折两类）'][rank]
            alignment = ['TURN2_LOWER', 'TURN2_HIGHER'][rank]
        else:
            role = f'转折表达第{rank+1}/{len(ordered)}位（由少到多）'
            alignment = ''
    elif row['method'] == 'V3_BEHAVIOR':
        family_zh = '结构多轴' if family == 'JOINT' else '简单/复杂条件表达'
        role = (f'{family_zh}类：转折{turn:+.3f}、复杂转折{cturn:+.3f}、'
                f'短细节{short:+.3f}、近共线冗余{red:+.3f}')
        # No new cross-fold taxonomy: literal historical centers remain separate.
        alignment = ''
    else:
        q, t = row['q_history_mean'], row['t_history_mean']
        role = (f'联合历史类：Q残差{q:+.3f}、对数时间残差{t:+.3f}、'
                f'转折{turn:+.3f}、复杂转折{cturn:+.3f}')
        alignment = ''
    return role, alignment


def run(repo, out):
    out.mkdir(parents=True, exist_ok=True)
    inputs = out/'inputs'
    inputs.mkdir(exist_ok=True)
    manifest = []
    if repo:
        commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        for key, rel in FILES.items():
            src, dst = repo/BASE/rel, inputs/Path(rel).name
            if not src.exists():
                raise FileNotFoundError(src)
            shutil.copyfile(src, dst)
            manifest.append({'input_key': key, 'repository_path': str(BASE/rel),
                             'copied_path': str(dst.relative_to(out)), 'bytes': dst.stat().st_size,
                             'sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
                             'read_commit': commit})
        dump(pd.DataFrame(manifest), out/'INPUT_INDEX.csv')
    else:
        manifest = pd.read_csv(out/'INPUT_INDEX.csv').to_dict('records')
        commit = manifest[0]['read_commit']
        for item in manifest:
            p = out/item['copied_path']
            if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError(f'Input checksum mismatch: {p}')
    source = {key: inputs/Path(rel).name for key, rel in FILES.items()}
    centers = pd.read_csv(source['centers'])
    labels = pd.read_csv(source['labels'])
    panels = pd.read_csv(source['panels'])
    roles = []
    for (_, _), fold in centers[centers.tier == 'coarse'].groupby(['method', 'heldout_building']):
        for _, row in fold.iterrows():
            record = row.to_dict()
            record['role_zh'], record['role_alignment_key'] = role_text(row, fold)
            record['class_join_key'] = '|'.join([row['method'], row['condition'], row['heldout_building'], row['class_id']])
            record['role_meaning'] = '历史中心的中文释义；非本轮重分类；非目标图表现保证'
            record['read_commit'] = commit
            record['stage'] = STAGE
            roles.append(record)
    roles = pd.DataFrame(roles)
    dump(roles, out/'LOBO_CLASS_MEANINGS_AND_MEMBERS.csv')
    role_lookup = {(r.method, r.heldout_building, r.class_id): r.role_zh for r in roles.itertuples()}
    label_lookup = {(r.method, r.heldout_building, r.worker_id): r.coarse_label for r in labels.itertuples()}
    roster = []
    for _, p in panels.iterrows():
        r = p.to_dict()
        r.update({'stage': STAGE, 'read_commit': commit,
                  'source_class_zh': role_lookup[(p['method'], p['building'], p['class_lo'])],
                  'target_class_zh': role_lookup[(p['method'], p['building'], p['class_hi'])],
                  'source_block_members': p['lo_candidates'], 'target_block_members': p['hi_candidates'],
                  'block_size_for_pure_endpoint_AC': int(p['k_selected']),
                  'replacement_fraction_for_pure_endpoint_AC': p['k_selected']/p['n'],
                  'background_n': len(pipe_members(p['core'])),
                  'background_class_counts': json.dumps(dict(sorted(Counter(
                      str(label_lookup[(p['method'], p['building'], w)]) for w in pipe_members(p['core'])
                  ).items())), ensure_ascii=False, separators=(',', ':')),
                  'outcome_status': '设计索引；未在此表合成任何缺失大块效果',
                  'strict_ABC_status': '本表为旧有限面板；不声明已恢复严格大块ABC'})
        roster.append(r)
    dump(pd.DataFrame(roster), out/'PRIOR_PANEL_DIRECTION_ROSTER.csv')
    key = labels[(labels.method == 'V3_BEHAVIOR') & labels.worker_id.isin(KEY_WORKERS)].copy()
    key['role_zh'] = [role_lookup.get((r.method, r.heldout_building, r.coarse_label), '标签未知') for r in key.itertuples()]
    key['matching_result_status'] = '缺失大块成员缺席对照表；本文件仅恢复楼外标签与历史特征'
    key['stage'] = STAGE
    key['read_commit'] = commit
    dump(key, out/'KEY_MEMBER_ROLES_BY_FOLD.csv')

    # Existing finite panel: 100 saved team-pair rows, five n/background panels.
    teams = pd.read_csv(source['g015_teams'])
    n7 = teams[(teams.n == 7) & (teams.replicate == 0)]
    assert len(n7) == 20 and n7.panel_id.nunique() == 1
    p = n7.iloc[0]
    pure_lo = n7[n7.hi_selected == 0].iloc[0]
    pure_hi = n7[n7.hi_selected == 3].iloc[0]
    same_saved = pd.read_csv(source['g015_same'])
    old = n7[n7.member_set_key == same_saved.iloc[0].member_set_key].iloc[0]
    new = n7[n7.member_set_key == same_saved.iloc[1].member_set_key].iloc[0]
    changes = []
    for name, before, after, src_members, dst_members, m, src_class, dst_class in [
        ('cross_class_AC_saved_endpoints', pure_lo, pure_hi, p.lo_candidates, p.hi_candidates, 3, p.class_lo, p.class_hi),
        ('same_class_AB_saved_endpoints', old, new, 'W104', 'W120', 1, 'M2', 'M2')]:
        background = sorted(set(pipe_members(before.member_set_key)) & set(pipe_members(after.member_set_key)))
        assert len(background) == 7-m
        for side in ['a', 'b']:
            r = {'stage': STAGE, 'read_commit': commit, 'comparison': name,
                 'panel_id': p.panel_id, 'pair_key': p.pair_key, 'building': p.building,
                 'groups': p.groups, 'image': p['image_'+side], 'image_id': p['image_id_'+side],
                 'pool_id': p['pool_id_'+side], 'reference_id': p['reference_id_'+side],
                 'condition': 'manual', 'method': p.method, 'selected_family': p.selected_family,
                 'heldout_building': p.building, 'source_class': src_class, 'target_class': dst_class,
                 'source_class_zh': role_lookup[(p.method, p.building, src_class)],
                 'target_class_zh': role_lookup[(p.method, p.building, dst_class)],
                 'source_members': src_members, 'target_members': dst_members,
                 'D_members': '|'.join(background), 'n': 7, 'm': m, 'm_over_n': m/7,
                 'D_class_counts': json.dumps(dict(sorted(Counter(label_lookup[(p.method, p.building, w)] for w in background).items())), ensure_ascii=False),
                 'before_team_key': before['team_key_'+side], 'after_team_key': after['team_key_'+side],
                 'before_members': before.member_set_key, 'after_members': after.member_set_key,
                 'before_object_ids': before['member_object_ids_'+side], 'after_object_ids': after['member_object_ids_'+side],
                 'support_description': '单图单次已有精确端点差；非大块严格ABC总体',
                 'time_semantics': '沿用原表 recorded_time_total_seconds；记录劳动时间，不是交付时间'}
            for metric in METRICS:
                b, a = before[metric+'_'+side], after[metric+'_'+side]
                r[metric+'_before'], r[metric+'_after'], r[metric+'_delta'] = b, a, a-b
            changes.append(r)
    dump(pd.DataFrame(changes), out/'G015_SAVED_DIRECTION_AND_MEMBER_CHANGES.csv')
    composition = []
    for h, g in n7.groupby('hi_selected'):
        for side in ['a', 'b']:
            r = {'stage': STAGE, 'read_commit': commit, 'panel_id': p.panel_id,
                 'image': p['image_'+side], 'n': 7, 'M3_count': int(h), 'M2_count': 7-int(h),
                 'attempted_teams': len(g), 'Q_available': int(g['B8L2_'+side].notna().sum()),
                 'failure_status_available': int(g['failure_'+side].notna().sum()),
                 'failed_teams': int((g['failure_'+side] == 1).sum()),
                 'D_members': p.core, 'selected_M2_pool': p.lo_candidates, 'selected_M3_pool': p.hi_candidates}
            for metric in METRICS:
                r[metric+'_mean'] = g[metric+'_'+side].mean()
            r['B8L2_p10'] = g['B8L2_'+side].quantile(.1)
            composition.append(r)
    dump(pd.DataFrame(composition), out/'G015_SAVED_COMPOSITION_CURVE.csv')
    counts = {'stage': STAGE, 'read_commit': commit,
              'new_fusion_endpoints': 0, 'new_classifications': 0,
              'role_rows': len(roles), 'structure_role_rows': int((roles.method == 'V3_BEHAVIOR').sum()),
              'folds': int(roles.heldout_building.nunique()), 'existing_panel_rows': len(panels),
              'key_member_fold_rows': len(key), 'case_saved_team_pair_rows': len(teams),
              'case_n7_saved_team_pair_rows': len(n7), 'case_change_rows': len(changes),
              'case_composition_rows': len(composition)}
    (out/'BUILD_RECEIPT.json').write_text(json.dumps(counts, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    a = parser.parse_args()
    run(a.repo, a.out)
