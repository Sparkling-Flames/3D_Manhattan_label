"""第一阶段探索性逐人图片建议包；不导入LS，不派发，不计入可选承诺。"""
import argparse
import csv
import gzip
import json
import random
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from html import escape
from itertools import combinations
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
SELECTION = ROOT / 'analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json'
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
VIEW = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
ROSTER = ROOT / 'analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_worker_roster.csv'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def save_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draft_worker(row):
    match = re.search(r',\s*(\d+)\s*$', row['created_username'])
    if not match:
        raise ValueError('草稿缺少可验证的数字人员ID，不能当成未接触')
    return int(match[1])


def check_pairs(rows, active, seen):
    assert len({(r['worker_id'], r['image_id']) for r in rows}) == len(rows), '重复人员图片'
    for r in rows:
        assert r['worker_id'] in active, '非本轮人员'
        assert r['worker_id'] not in seen.get(r['image_id'], set()), '已有提交或草稿接触'


def exposure(records):
    paths = {ROOT / r['raw_export_path'] for r in records}
    folders = ['stage1_chinese', 'stage1_English', 'stage2_Chinese', 'stage2_English',
               'c2B_Chinese', 'c2B_English', 'c2arp_block1', 'c2arp_block2']
    paths.update(p for folder in folders for p in (ROOT / 'export_label' / folder).glob('project-*.json'))
    by_pair = defaultdict(lambda: dict(submissions=set(), drafts=set(), sources=set()))
    sources, seen = [], defaultdict(set)
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        submitted, drafts = 0, 0
        for task in read(path):
            iid = Path(unquote(urlparse(task['data']['image']).path)).stem
            for row in task.get('annotations', []):
                worker = row['completed_by']
                worker = int(worker['id'] if isinstance(worker, dict) else worker)
                pair = by_pair[worker, iid]
                pair['submissions'].add((str(task['id']), str(row['id'])))
                pair['sources'].add(relative)
                seen[iid].add(worker)
                submitted += 1
            for row in task.get('drafts', []):
                worker = draft_worker(row)
                pair = by_pair[worker, iid]
                pair['drafts'].add((str(task['id']), str(row['id'])))
                pair['sources'].add(relative)
                seen[iid].add(worker)
                drafts += 1
        sources.append(dict(path=relative, submission_rows=submitted, draft_rows=drafts))
    return seen, by_pair, sources


def worker_page(worker, rows, language, image_paths, folder):
    english = language == 'en'
    title = f'W{worker:03d} — Image list' if english else f'W{worker:03d} — 图片清单'
    intro = ('Planning list. Image codes are not Label Studio task IDs. Complete the 30 required images first. '
             'The additional 20 images are optional: you may do none, some, or all. '
             'Use the task links and annotation instructions supplied separately when the project is ready.' if english else
             '图片分配建议清单，图片编号不是Label Studio任务编号。本次必做20张；正式标注时使用另行提供的任务链接和标注说明。')
    blocks = []
    for tier in ['required', 'optional']:
        selected = [r for r in rows if r['tier'] == tier]
        if not selected:
            continue
        heading = ('Required — 30 images' if english else '必做 — 20张') if tier == 'required' else 'Optional — 20 additional images'
        blocks.append(f'<h2>{heading}</h2>')
        if tier == 'optional':
            blocks.append('<p>Optional candidate list for planning review. If you volunteer, following the listed order is helpful; record any skipped images. No optional task is required.</p>')
        last_group = None
        for r in selected:
            if r['batch'] != last_group:
                blocks.append(f'<h3>{escape(r["batch"])}</h3>')
                last_group = r['batch']
            rel = 'images/' + Path(image_paths[r['image_id']]).name
            blocks.append(f'<figure><figcaption>{r["order"]:02d} · {escape(r["code"])}</figcaption>'
                          f'<a href="{escape(rel)}"><img loading="lazy" src="{escape(rel)}" alt="{escape(r["code"])}"></a></figure>')
    html = ('<!doctype html><html lang="' + ('en' if english else 'zh-CN') + '"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title>'
            '<style>body{max-width:1100px;margin:32px auto;padding:0 20px;font:16px/1.6 Arial,sans-serif;color:#183343;background:#f5f8fa}'
            'h1,h2{color:#174e64}h2{margin-top:48px;border-bottom:2px solid #a4c6d1}figure{margin:20px 0;background:white;padding:14px;border-radius:8px}'
            'img{width:100%;height:auto}figcaption{font-weight:bold}p{max-width:950px}</style><h1>' + title + '</h1><p>' + intro + '</p>' + ''.join(blocks) + '</html>')
    (folder / f'W{worker:03d}.html').write_text(html, encoding='utf-8')
    assert html.count('<figure>') == len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--external-package', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'analysis_results/stage1_person_image_packages_20260913_v1')
    parser.add_argument('--optional-door-count', type=int, default=10)
    args = parser.parse_args()
    assert 0 <= args.optional_door_count <= 20
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    current = read(SELECTION)
    assert current['schema'] == 'candidate_selection_planning_v2'
    assert current['source_user'] == read(SELECTION.parent / '用户审查原始记录.json')
    images = {r['image_id']: r for r in read(REGISTRY)['images']}
    adopted = {r['image_id']: r for r in current['images'] if r['status'] == '确定采用'}
    assert len(adopted) == 102
    active = set(current['future_workers'])
    assert len(active) == 19 and not active & {11, 19, 26}
    languages = {int(r['annotator_id']): r['language'] for r in csv_rows(ROSTER)}
    assert Counter(languages[w] for w in active) == {'zh': 9, 'en': 10}
    english = sorted(w for w in active if languages[w] == 'en')
    with gzip.open(VIEW, 'rt', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    seen, by_pair, sources = exposure(records)
    manual = defaultdict(set)
    semi = defaultdict(set)
    for r in records:
        worker, iid = int(r['worker_id']), r['image_id']
        if worker in {19, 26}:
            continue
        if r['unassisted_manual_included']:
            manual[iid].add(worker)
        if r['assistance_exposure'] == 'model_preannotation':
            semi[iid].add(worker)
    for iid, row in adopted.items():
        assert set(row['manual_workers']) == manual[iid]
        assert row['history_manual'] == len(manual[iid])

    witness = csv_rows(args.external_package / 'results/NOT_FOR_DISPATCH_assignment_witness.csv')
    required, assigned = [], defaultdict(set)
    for r in witness:
        worker, iid = int(r['worker_id']), r['image_id']
        source = adopted[iid]
        assert source['oos']['disposition'] == '保留候选'
        assert (r['group'], int(r['number'])) == (source['group'], source['number'])
        assert r['difficulty'] == source['difficulty'] and r['coarse'] == source['scene']
        assert worker in source['clean_workers']
        required.append(dict(worker_id=worker, image_id=iid, tier='required'))
        assigned[iid].add(worker)
    assert len(required) == 480 and len(assigned) == 43
    check_pairs(required, active, seen)
    for worker in active:
        assert sum(r['worker_id'] == worker for r in required) == (30 if languages[worker] == 'en' else 20)
    for iid, workers in assigned.items():
        row = adopted[iid]
        assert len(workers) + len(manual[iid]) == min(row['planned_manual'], row['current_roster_cap'])
        assert all(sum(languages[w] == lang for w in ((workers | manual[iid]) & active)) >= 2 for lang in ['zh', 'en'])

    doorway_pool = {r['image_id']: r for r in current['supplementary_doorway_candidates']}
    pool = {**doorway_pool, **adopted}
    offered = defaultdict(set)
    optional = []
    # ponytail: 固定候选内的可解释贪心编排，不声称科学最优；只有容量检查失败才需要整数优化。
    worker_order = english[:]
    random.Random(20260913).shuffle(worker_order)
    priority = {group: i for i, group in enumerate(['G178', 'G090', 'G205', 'G078', 'G015'])}
    for optional_kind, count, candidates_pool in [('同房补充', 20 - args.optional_door_count, adopted),
                                                  ('门洞补充', args.optional_door_count, doorway_pool)]:
        for turn in range(count):
            order = worker_order[turn % 10:] + worker_order[:turn % 10]
            for worker in order:
                candidates = []
                for iid, row in candidates_pool.items():
                    if worker in seen[iid] or worker in assigned[iid] or worker in offered[iid]:
                        continue
                    if optional_kind == '同房补充':
                        if row['planned_manual'] <= len(manual[iid]) + len(assigned[iid]) + len(offered[iid]):
                            continue
                        preference = (priority.get(row['group'], 99), -len(offered[iid]), row['group'], row['number'])
                    else:
                        assert row['oos']['disposition'] == '保留候选'
                        if iid in adopted and len(manual[iid]) + len(assigned[iid]) + len(offered[iid]) >= adopted[iid]['planned_manual']:
                            continue
                        # 确认身份、可补齐少量历史的图优先，不把既有收敛标签用于选图。
                        preference = (row['doorway'] != '确认', not (0 < len(manual[iid]) < 8),
                                      -len(offered[iid]), -sum(w not in seen[iid] for w in english), row['building'], row['number'])
                    candidates.append((preference, iid))
                assert candidates, f'W{worker:03d} {optional_kind}不足，需要重新审图'
                iid = min(candidates)[1]
                offered[iid].add(worker)
                optional.append(dict(worker_id=worker, image_id=iid, tier='optional', optional_kind=optional_kind))
    # 避免无历史的新门洞图仅安排一个可选名额；这不是实际完成或收敛保证。
    for iid in sorted(offered):
        if iid not in doorway_pool or len(offered[iid]) != 1 or manual[iid]:
            continue
        donor = next((r for r in optional if r['optional_kind'] == '门洞补充'
                      and len(offered[r['image_id']]) >= 3 and not manual[r['image_id']]
                      and r['worker_id'] not in offered[iid] | seen[iid] | assigned[iid]), None)
        if donor is not None:
            offered[donor['image_id']].remove(donor['worker_id'])
            offered[iid].add(donor['worker_id'])
            donor['image_id'] = iid
    rows = required + optional
    check_pairs(rows, active, seen)
    assert len(optional) == 200
    for worker in english:
        assert Counter(r['optional_kind'] for r in optional if r['worker_id'] == worker) == {
            '门洞补充': args.optional_door_count, '同房补充': 20 - args.optional_door_count}
    for r in rows:
        iid = r['image_id']
        source = adopted[iid] if r['tier'] == 'required' else pool[iid]
        registry = images[iid]
        group_codes = source.get('group_codes', [source['group']] if 'group' in source else [])
        # 多个重叠展示组不强行合并为一个物理房间；单图先独立保留。
        batch = source['group'] if 'group' in source else (group_codes[0] if len(group_codes) == 1 else f'{registry["building"]}-{registry["number"]:02d}')
        r.update(language=languages[r['worker_id']], batch=batch, source_groups=' / '.join(group_codes),
                 code=f'{registry["building"]}-{registry["number"]:02d}', number=registry['number'],
                 scene=source['scene'], difficulty=source.get('difficulty', '未预判'),
                 doorway=source['doorway'], image_path=registry['path'],
                 selection_state='已明确采用' if iid in adopted else ('原表备选；本次仅建议可选' if any(x['image_id'] == iid for x in current['images']) else '补充候选；尚未逐图采用'),
                 baseline_credit=1 if r['tier'] == 'required' else 0)
        r.setdefault('optional_kind', '')
    for worker in sorted(active):
        for tier in ['required', 'optional']:
            subset = [r for r in rows if r['worker_id'] == worker and r['tier'] == tier]
            batches = sorted({r['batch'] for r in subset})
            random.Random(20260913 + worker + (1000 if tier == 'optional' else 0)).shuffle(batches)
            # 组内保持相邻，轮换人员看到各组的顺序；不提供预期难度或历史标注给标注者。
            subset.sort(key=lambda r: (batches.index(r['batch']), r['number']))
            for order, r in enumerate(subset, 1):
                r['order'] = order
    rows.sort(key=lambda r: (r['worker_id'], r['tier'] != 'required', r['order']))

    image_summary = []
    for iid in sorted(set(adopted) | {r['image_id'] for r in optional}):
        source = adopted.get(iid, pool.get(iid))
        new = assigned[iid]
        extra = offered[iid]
        clean_reserve = active - seen[iid] - new
        old = len(manual[iid])
        maximum = source.get('planned_manual')
        image_summary.append(dict(image_id=iid, code=f'{images[iid]["building"]}-{images[iid]["number"]:02d}',
                                  group=source.get('group', ' / '.join(source.get('group_codes', []))),
                                  scene=source['scene'], difficulty=source.get('difficulty', '未预判'),
                                  history_manual=old, history_semi=len(semi[iid]), required_new=len(new),
                                  required_plan_total=old + len(new), optional_offered=len(extra),
                                  all_optional_done_total=old + len(new) + len(extra),
                                  user_target=maximum, gap_after_required=max(0, maximum - old - len(new)) if maximum is not None else None,
                                  required_workers=sorted(new), optional_workers=sorted(extra),
                                  alternative_workers=sorted(clean_reserve) if new else [],
                                  alternative_note='仅该图未接触的现有人选，不代表其总工作量仍有余量',
                                  one_dropout_total=old + len(new) - 1 if new else old,
                                  doorway=source['doorway'], in_adopted_pool=iid in adopted))
        if iid in adopted:
            assert old + len(new) + len(extra) <= source['planned_manual']
    room_rows = []
    for group in sorted({r['group'] for r in adopted.values()}):
        rr = [r for r in image_summary if r['in_adopted_pool'] and r['group'] == group]
        room_rows.append(dict(group=group, adopted_images=len(rr), history_manual=sum(r['history_manual'] for r in rr),
                              required_new=sum(r['required_new'] for r in rr),
                              manual_after_required=sum(r['required_plan_total'] for r in rr),
                              views_with_manual=sum(r['required_plan_total'] > 0 for r in rr),
                              views_at_least8=sum(r['required_plan_total'] >= 8 for r in rr),
                              optional_offered=sum(r['optional_offered'] for r in rr)))
    worker_rows = []
    for worker in sorted(active):
        required_rows = [r for r in rows if r['worker_id'] == worker and r['tier'] == 'required']
        optional_rows = [r for r in rows if r['worker_id'] == worker and r['tier'] == 'optional']
        counts = Counter(r['difficulty'] for r in required_rows)
        worker_rows.append(dict(worker_id=worker, language=languages[worker], required=len(required_rows),
                                optional=len(optional_rows), total_offered=len(required_rows) + len(optional_rows),
                                simple=counts['简单'], medium=counts['中等'], hard=counts['困难'],
                                required_rooms=len({r['batch'] for r in required_rows}),
                                submitted_images=sum(w == worker and bool(v['submissions']) for (w, _), v in by_pair.items()),
                                draft_only_images=sum(w == worker and not v['submissions'] and bool(v['drafts']) for (w, _), v in by_pair.items())))
    history_rows = []
    for (worker, iid), info in sorted(by_pair.items()):
        if worker not in active:
            continue
        registry = images.get(iid)
        history_rows.append(dict(worker_id=worker, language=languages[worker], image_id=iid,
                                 code=f'{registry["building"]}-{registry["number"]:02d}' if registry else iid,
                                 in_648=registry is not None, has_submission=bool(info['submissions']),
                                 has_draft=bool(info['drafts']), manual_in_analysis=worker in manual[iid],
                                 semi_exposure=worker in semi[iid], sources=';'.join(sorted(info['sources']))))
    scenarios = []
    for number in [0, 2, 5, 10]:
        outcomes = []
        for people in combinations(english, number):
            counts = Counter(r['image_id'] for r in optional if r['worker_id'] in people)
            outcomes.append((sum(counts.values()), sum(n >= 2 for n in counts.values()), sum(n >= 5 for n in counts.values())))
        scenarios.append(dict(volunteers_finishing20=number, optional_new=number * 20,
                              min_images_with2_new=min(x[1] for x in outcomes), max_images_with2_new=max(x[1] for x in outcomes),
                              min_images_with5_new=min(x[2] for x in outcomes), max_images_with5_new=max(x[2] for x in outcomes),
                              interpretation='枚举哪些英文人员完成全部20张；不是参与率预测，不含历史、不判定收敛'))
    assert sum(r['baseline_credit'] for r in rows) == 480
    assert sum(r['required_plan_total'] for r in image_summary if r['in_adopted_pool']) == 863
    assert scenarios[0]['optional_new'] == 0
    doorway_inventory = []
    for r in current['supplementary_doorway_all_records']:
        iid = r['image_id']
        doorway_inventory.append(dict(image_id=iid, code=f'{r["building"]}-{r["number"]:02d}', groups=' / '.join(r['group_codes']),
                                      doorway=r['doorway'], oos=r['oos']['disposition'], history_manual=len(manual[iid]),
                                      history_semi=len(semi[iid]), clean_english=sum(w not in seen[iid] for w in english),
                                      optional_offered=len(offered[iid]), history_workers=sorted(manual[iid])))
    result = dict(schema='stage1_image_package_proposal_v1', status='建议包_未导入_未派发', optional_pool='mixed',
                  optional_door_count=args.optional_door_count, optional_room_count=20 - args.optional_door_count,
                  selection_source=str(SELECTION), registry_source=str(REGISTRY),
                  external_assignment_source=str(args.external_package / 'results/NOT_FOR_DISPATCH_assignment_witness.csv'),
                  formal_contract_changed=False, user_selection_changed=False,
                  raw_sources=sources, raw_submission_rows=sum(s['submission_rows'] for s in sources),
                  raw_draft_rows=sum(s['draft_rows'] for s in sources),
                  exposure_scope='canonical来源加P1/C1/C2-B/RP1-2阶段当前导出，含所有提交版本和可识别草稿；未覆盖未保存浏览、其他未提供的新导出、旧服务器异名账号',
                  workers=worker_rows, assignments=rows, images=image_summary, rooms=room_rows,
                  history=history_rows, doorway_inventory=doorway_inventory, optional_scenarios=scenarios,
                  counts=dict(required=480, optional_offers=200, required_images=43,
                              optional_images=len({r['image_id'] for r in optional}), rooms=19,
                              required_same_person_repeat_conflicts=0, optional_same_person_repeat_conflicts=0),
                  order_seed=20260913)
    save_json(out / '分配建议与核验.json', result)
    save_csv(out / '逐人人图建议.csv', rows)
    save_csv(out / '历史人员图片记录.csv', history_rows)
    save_csv(out / '原始导出核对范围.csv', sources)
    shutil.copy2(args.external_package / 'results/NOT_FOR_DISPATCH_assignment_witness.csv', out / '必做匹配来源快照.csv')

    for language, folder_name in [('zh', '中文图片包'), ('en', '英文图片包')]:
        folder = out / folder_name
        folder.mkdir(exist_ok=True)
        image_folder = folder / 'images'
        image_folder.mkdir(exist_ok=True)
        selected = [r for r in rows if r['language'] == language]
        image_paths = {r['image_id']: r['image_path'] for r in selected}
        for relative in image_paths.values():
            source = ROOT / relative
            assert source.is_file(), relative
            destination = image_folder / source.name
            shutil.copy2(source, destination)
        links = []
        for worker in sorted(w for w in active if languages[w] == language):
            subset = [r for r in selected if r['worker_id'] == worker]
            worker_page(worker, subset, language, image_paths, folder)
            links.append(f'<li><a href="W{worker:03d}.html">W{worker:03d}</a> — ' + ('30 required + 20 optional' if language == 'en' else '必做20张') + '</li>')
        (folder / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>图片包目录</title><h1>逐人图片建议包</h1><p>这是管理用合集，每个人只对应自己的清单。图片编号不是LS任务编号。英文可选图为待最终选用的候选；未派发。</p><ul>' + ''.join(links) + '</ul>', encoding='utf-8')
        with zipfile.ZipFile(out / (folder_name + '.zip'), 'w', zipfile.ZIP_STORED) as archive:
            for p in sorted(folder.rglob('*')):
                if p.is_file():
                    archive.write(p, p.relative_to(folder).as_posix())
        with zipfile.ZipFile(out / (folder_name + '.zip')) as archive:
            assert archive.testzip() is None
            assert len([n for n in archive.namelist() if n.startswith('images/')]) == len(image_paths)
    print(json.dumps(dict(counts=result['counts'], workers=worker_rows, optional_scenarios=scenarios,
                          sources=len(sources), submission_rows=result['raw_submission_rows'], drafts=result['raw_draft_rows']), ensure_ascii=False))


if __name__ == '__main__':
    main()
