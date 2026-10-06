"""用已有单一融合结果连接人工难度记录；只重汇总，不重算几何。"""
from collections import Counter, defaultdict
import json
from statistics import mean, median

from .lee_tile_stage1_20261002 import ROOT, write_csv, write_json
from .worker_count_composition_20261006 import INVENTORY, read_csv

OUT = ROOT / 'analysis_results/difficulty_consensus_20261006'
LABELS = ('简单', '中等', '困难')
REVIEW = ('7y3sRwLe3Va-04', 'UwV83HsGsw3-09', 'q9vSo1VnCiC-02',
          'q9vSo1VnCiC-32', 'rPc6DW4iMge-06', 'yqstnuAEVhm-32',
          'yqstnuAEVhm-34', 'wc2JMjhGNzB-59')


def scene_group(row):
    oos, door = row['oos_status'], row['doorway_status']
    if oos == 'confirmed' and door == 'difficult':
        return 'oos_and_doorway'
    if oos == 'confirmed':
        return 'oos'
    if door == 'difficult':
        return 'doorway_difficult'
    if oos == 'pending':
        return 'oos_pending'
    if door == 'annotatable':
        return 'doorway_annotatable'
    return 'clear' if (oos, door) == ('not_oos', 'none') else 'unflagged'


def summarize(rows, meta, limit):
    eligible = {r['image'] for r in rows if r['n'] >= limit
                and meta[r['image']]['scene'] in ('clear', 'unflagged')
                and meta[r['image']]['difficulty'] in LABELS}
    result = []
    for scope in ('all', 'within_uNb', 'without_uNb'):
        groups = defaultdict(list)
        for r in rows:
            m = meta[r['image']]
            in_unb = m['building'].startswith('uNb')
            if (r['image'] not in eligible or r['k'] > limit
                    or (scope == 'within_uNb' and not in_unb)
                    or (scope == 'without_uNb' and in_unb)):
                continue
            groups[m['difficulty'], r['method'], r['k']].append(r)
        for (label, method, k), members in sorted(groups.items()):
            buildings = defaultdict(list)
            for r in members:
                buildings[meta[r['image']]['building']].append(r['distance'])
            result.append(dict(panel_n=limit, scope=scope, difficulty=label,
                               method=method, k=k, image_count=len(members),
                               building_count=len(buildings),
                               mean_distance=mean(r['distance'] for r in members),
                               median_distance=median(r['distance'] for r in members),
                               building_equal_distance=mean(mean(v) for v in buildings.values()),
                               images='|'.join(sorted(r['image'] for r in members))))
    return result


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    bundle = load_current_bundle()
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    latest = {r['image_code']: r for r in bundle['research']['images']}
    meta = {}
    for r in inventory['images']:
        scene = latest[r['image']]
        meta[r['image']] = dict(r, oos_status=scene['oos_status'],
                               doorway_status=scene['doorway_status'], scene=scene_group(scene))
    old_path = ROOT / 'analysis_results/lee_expanded_20261003/image_curves.csv'
    new_path = ROOT / 'analysis_results/worker_count_composition_20261006/per_image.csv'
    old = [dict(image=r['image'], n=int(r['n']), k=int(r['k']), method=r['method'],
                distance=float(r['omission_fraction'])+float(r['extension_fraction']))
           for r in read_csv(old_path) if r['condition']=='manual' and r['version']=='original']
    new = [dict(image=r['image'], n=int(r['n']), k=int(r['k']), method=r['method'],
                distance=float(r['ref_symdiff_ref']))
           for r in read_csv(new_path) if r['condition']=='manual' and r['version']=='original'
           and r['scenario']=='uniform' and r['policy']=='none']
    summary = summarize(old, meta, 8)+summarize(new, meta, 16)+summarize(new, meta, 20)
    counts = {r['image']: r['n'] for r in old if r['n'] >= 8}
    counts.update({r['image']: r['n'] for r in new})
    fields = ('image', 'building', 'difficulty', 'difficulty_legacy', 'oos_status', 'doorway_status', 'scene')
    roster = [dict(**{f: meta[i][f] for f in fields}, manual_n=n) for i, n in sorted(counts.items())]
    specials = [{f: r[f] for f in fields} for r in meta.values() if r['scene'] not in ('clear', 'unflagged')]
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT/'summary.csv', summary)
    write_csv(OUT/'difficulty_roster.csv', roster)
    write_csv(OUT/'special_scenes.csv', specials)
    write_json(OUT/'label_sources.json', dict(source=str(INVENTORY.relative_to(ROOT)),
               images={i: {f: r[f] for f in ('difficulty', 'difficulty_legacy',
                       'difficulty_later_review', 'difficulty_text_review')} for i, r in meta.items()}))
    write_json(OUT/'field_contract.json', dict(
        schema='difficulty_consensus_regroup_v1',
        source_manifest='analysis_results/research_input_20260929/manifest.json',
        sources=[str(p.relative_to(ROOT)) for p in (old_path, new_path, INVENTORY)],
        unit='每组人员、每种投票规则仅一个Lee融合区域；本表对抽组结果的参考误差取期望。',
        distance='E[area(C_k symmetric_difference G)] / area(G)；较小更近，只衡量BEV范围；不是1-IoU。',
        summary='同一panel_n内固定图片，k从1到panel_n；图片等权均值/中位数，以及先楼内均值再楼间等权。',
        scope='all、within_uNb、without_uNb；后两者仅为建筑构成敏感性检查。',
        roster='至少8人且已有主质量结果的Manual图片；未知或待定难度保留，不补成三档。',
        scenes='保留两个原始轴及交集。clear须显式not_oos+none；unflagged不代表已审核正常。',
        special_scenes='全259图中已记录的OOS、难标门洞、待定OOS、可标门洞；不把GT远近直接解释为人员质量。',
        label_counts=dict(Counter(r['difficulty'] for r in meta.values())),
        scene_counts=dict(Counter(r['scene'] for r in meta.values())),
        interpretation='描述性初查，未建立难度预测或快/慢/远自动分类，不改原始标签或研究合同。'))
    lines = ['# 可选补标：8张高人数图片', '',
             '[打开难度补标工作台](index.html)：复用原候选图片审查台，点击放大、难度与独立场景字段、自动暂存、导出／导入JSON。', '',
             '前7张补齐共同24人×10图面板的未记录难度，最后1张补充23人图片；选择依据为覆盖，不按融合误差选图。', '',
             '每图只需填：简单／中等／困难／暂不能判断，可加一句原因。OOS、门洞交界另记，不强塞进困难档。',
             '这里的“未记录”指当前有效难度字段缺失，不代表从未看过。已有新记录可直接补充，无需重复审核。', '',
             '| 图片 | Manual人数 | 难度 | 可选原因／特殊场景 |', '|---|---:|---|---|']
    for i in REVIEW:
        lines.append(f'| {i} | {counts[i]} | | |')
    for i in REVIEW:
        r = latest[i]
        ref = ROOT / r['references']['gt_original'].split(':', 2)[2]
        path = ref.parent.parent/'img'/f"{r['image_id']}.png"
        assert path.is_file(), path
        lines.extend(['', f'## {i}', '', f'![{i}]({path.as_posix()})'])
    (OUT/'REVIEW_LIST.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(OUT), summary_rows=len(summary), roster=len(roster),
                          special_scenes=len(specials)), ensure_ascii=False))


if __name__ == '__main__':
    run()
