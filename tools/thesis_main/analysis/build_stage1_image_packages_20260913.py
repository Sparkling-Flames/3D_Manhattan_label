"""第一阶段探索性逐人图片建议包；不导入LS，不派发，不计入可选承诺。"""
import argparse
import csv
import gzip
import json
import random
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
SELECTION = ROOT / 'analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json'
REGISTRY = ROOT / 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
VIEW = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
ROSTER = ROOT / 'analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_worker_roster.csv'
PROJECT_NAMES = {'zh_required': '任务7', 'en_required': 'Project G', 'en_optional': 'Project H'}


def chinese_names():
    """只读人员表A列编号、C列姓名信息，保留如张fl这样的原记录。"""
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    result = {}
    with zipfile.ZipFile(ROOT / 'export_label/标注人员.xlsx') as z:
        strings = [''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns)]
        for path in z.namelist():
            if not path.startswith('xl/worksheets/sheet') or not path.endswith('.xml'):
                continue
            for row in ET.fromstring(z.read(path)).findall('.//m:sheetData/m:row', ns):
                cells = {}
                for c in row:
                    v = c.find('m:v', ns)
                    if v is not None:
                        cells[re.sub(r'\d+', '', c.attrib['r'])] = strings[int(v.text)] if c.get('t') == 's' else v.text
                if str(cells.get('A', '')).isdigit() and cells.get('C'):
                    result[int(cells['A'])] = cells['C'].split()[-1]
    return result


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




def mild_order(rows, worker, language):
    """组内轮换后，中文交换2对、英文3对；不优化相邻比例。"""
    rng = random.Random(20260913 + worker)
    groups = defaultdict(list)
    for row in sorted(rows, key=lambda r: r['order']):
        groups[row['batch']].append(dict(row))
    ordered = []
    for group in groups.values():
        rng.shuffle(group)
        ordered.extend(group)
    pairs = [(i, j) for i in range(len(ordered)) for j in range(i + 1, len(ordered))
             if ordered[i]['batch'] != ordered[j]['batch']]
    rng.shuffle(pairs)
    swaps, used = [], set()
    for i, j in pairs:
        if i in used or j in used:
            continue
        ordered[i], ordered[j] = ordered[j], ordered[i]
        swaps.append([i + 1, j + 1])
        used.update([i, j])
        if len(swaps) == (2 if language == 'zh' else 3):
            break
    for i, row in enumerate(ordered, 1):
        row['order'] = i
    return ordered, swaps


def optional_pool(ids, adopted, english, seen):
    return [dict(image_id=iid, ready_for_import=iid in adopted,
                 eligible_workers=sorted(english - seen.get(iid, set())),
                 selection_state='已采用' if iid in adopted else '待用户采用') for iid in sorted(ids)]


def complete_room_assignment(current, registry, languages, seen):
    """固定人员负载，按采用后视角数优先整房选择；不以收敛结果选房。"""
    import numpy as np
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import lil_matrix
    images = [r for r in current['images'] if r['status'] == '确定采用']
    workers = sorted(current['future_workers'])
    order = {r['group']: i for i, r in enumerate(current['effective_groups'])}
    groups = sorted({r['group'] for r in images}, key=lambda g: (-sum(r['group'] == g for r in images), order[g]))
    need = {r['image_id']: min(r['new_needed'], len(set(workers) - seen[r['image_id']])) for r in images}
    pairs = [(w, r['image_id']) for r in images if need[r['image_id']] for w in workers if w not in seen[r['image_id']]]
    wi = {w: i for i, w in enumerate(workers)}
    ri = {r['image_id']: i + len(workers) for i, r in enumerate(images)}
    matrix = lil_matrix((len(workers) + len(images), len(groups) + len(pairs)))
    bound = np.zeros(matrix.shape[0])
    for w, i in wi.items():
        bound[i] = 30 if languages[w] == 'en' else 20
    for r in images:
        matrix[ri[r['image_id']], groups.index(r['group'])] = -need[r['image_id']]
    for j, (w, iid) in enumerate(pairs, len(groups)):
        matrix[wi[w], j] = matrix[ri[iid], j] = 1
    cost = np.zeros(matrix.shape[1])
    cost[:len(groups)] = [-2 ** (len(groups) - i) for i in range(len(groups))]
    solved = milp(cost, integrality=np.ones(len(cost)), bounds=Bounds(0, 1), constraints=LinearConstraint(matrix.tocsr(), bound, bound), options={'time_limit': 45})
    assert solved.success, f'整房分配未求得最优可行解：{solved.message}'
    chosen = {g for i, g in enumerate(groups) if solved.x[i] > .5}
    lookup = {r['image_id']: r for r in images}
    rows = []
    for j, (w, iid) in enumerate(pairs, len(groups)):
        if solved.x[j] <= .5:
            continue
        r, im = lookup[iid], registry[iid]
        rows.append(dict(worker_id=w, image_id=iid, tier='required', language=languages[w], batch=r['group'], source_groups=r['group'], code=f'{im["building"]}-{im["number"]:02d}', number=im['number'], scene=r['scene'], difficulty=r['difficulty'], doorway=r['doorway'], image_path=im['path'], selection_state='已明确采用', baseline_credit=r['history_manual'], order=len(rows)+1))
    audit = [dict(group=g, priority_rank=i+1, adopted_images=len(rr), selected=g in chosen, requested_new=sum(r['new_needed'] for r in rr), possible_new=sum(need[r['image_id']] for r in rr), assigned_new=sum(need[r['image_id']] for r in rr) if g in chosen else 0, target_shortfall=sum(r['new_needed']-need[r['image_id']] for r in rr) if g in chosen else 0, adopted_numbers='、'.join(str(r['number']) for r in rr), note=next(r['note'] for r in current['effective_groups'] if r['group']==g)) for i,g in enumerate(groups) for rr in [[r for r in images if r['group']==g]]]
    return rows, audit


def build_v2():
    parser = argparse.ArgumentParser(description='保留已审议必做人图，生成三个独立项目准备包；不派发。')
    parser.add_argument('--previous-package', type=Path, default=ROOT / 'analysis_results/stage1_person_image_packages_20260913_v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'analysis_results/stage1_person_image_packages_20260913_v2')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    old = read(args.previous_package / '分配建议与核验.json')
    assert old['schema'] == 'stage1_image_package_proposal_v1'
    current = read(SELECTION)
    assert current['schema'] == 'candidate_selection_planning_v2'
    assert current['source_user'] == read(SELECTION.parent / '用户审查原始记录.json')
    registry = {r['image_id']: r for r in read(REGISTRY)['images']}
    adopted = {r['image_id']: r for r in current['images'] if r['status'] == '确定采用'}
    active = set(current['future_workers'])
    languages = {int(r['annotator_id']): r['language'] for r in csv_rows(ROSTER)}
    assert len(active) == 19 and not active & {11, 19, 26}
    english = {w for w in active if languages[w] == 'en'}
    with gzip.open(VIEW, 'rt', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    seen, by_pair, sources = exposure(records)
    manual, semi = defaultdict(set), defaultdict(set)
    for r in records:
        w, iid = int(r['worker_id']), r['image_id']
        if w in {19, 26}:
            continue
        if r['unassisted_manual_included']:
            manual[iid].add(w)
        if r['assistance_exposure'] == 'model_preannotation':
            semi[iid].add(w)
    # v1仅提供已审议的匹配和候选快照，采用、资格和历史人数重新核对。
    required, room_audit = complete_room_assignment(current, registry, languages, seen)
    check_pairs(required, active, seen)
    assert len(required) == 480
    assigned = defaultdict(set)
    for r in required:
        source = adopted[r['image_id']]
        assert source['oos']['disposition'] == '保留候选' and r['worker_id'] in source['clean_workers']
        assert (r['batch'], r['number'], r['scene'], r['difficulty']) == (source['group'], source['number'], source['scene'], source['difficulty'])
        r.pop('optional_kind', None)
        r['project_key'] = r['language'] + '_required'
        assigned[r['image_id']].add(r['worker_id'])
    for iid, source in adopted.items():
        assert set(source['manual_workers']) == manual[iid]
        if iid in assigned:
            assert len(assigned[iid]) == min(source['new_needed'], len(active - seen[iid]))
    rows, ordering = [], []
    for w in sorted(active):
        subset = [r for r in required if r['worker_id'] == w]
        assert len(subset) == (30 if languages[w] == 'en' else 20)
        ordered, swaps = mild_order(subset, w, languages[w])
        rows.extend(ordered)
        ordering.append(dict(worker_id=w, swapped_positions=swaps))
    pool_ids = {r['image_id'] for r in old['assignments'] if r['tier'] == 'optional'}
    pool = optional_pool(pool_ids, adopted, english, seen)
    doors = {r['image_id']: r for r in current['supplementary_doorway_candidates']}
    for r in pool:
        iid = r['image_id']
        source = adopted[iid] if iid in adopted else doors[iid]
        assert source['oos']['disposition'] == '保留候选'
        im = registry[iid]
        r.update(code=f'{im["building"]}-{im["number"]:02d}', image_path=im['path'],
                 group=source.get('group', ' / '.join(source.get('group_codes', []))), scene=source['scene'],
                 kind='同房补充' if iid in adopted else '门洞补充', history_manual=len(manual[iid]),
                 history_semi=len(semi[iid]), project_key='en_optional')
    assert len(pool) == 25 and sum(r['ready_for_import'] for r in pool) == 12
    review_path = ROOT / 'import_json/scene_stability_stage1_20260913_v2/ProjectH_用户复核原文.json'
    review = read(review_path)
    decisions = {r['image_id']: r for r in review['decisions']}
    assert len(decisions) == len(review['decisions']) == 13
    assert set(decisions) == {r['image_id'] for r in pool if r['kind'] == '门洞补充'}
    selected_doors = {iid for iid, r in decisions.items() if r['decision'] == '采用到Project H'}
    assert len(selected_doors) == 12 and review['fixed_pool_size'] == 20
    room_candidates = sorted((r for r in pool if r['kind'] == '同房补充' and r['image_id'] not in assigned), key=lambda r: (-len(r['eligible_workers']), r['code']))
    selected_rooms, group_counts = [], Counter()
    while len(selected_rooms) < 20 - len(selected_doors):
        remaining = [r for r in room_candidates if r['image_id'] not in selected_rooms]
        pick = min(remaining, key=lambda r: (group_counts[r['group']], -len(r['eligible_workers']), r['code']))
        selected_rooms.append(pick['image_id'])
        group_counts[pick['group']] += 1
    selected_h = selected_doors | set(selected_rooms)
    for r in pool:
        r['ready_for_import'] = r['image_id'] in selected_h
        r['user_review'] = decisions.get(r['image_id'])
        r['selection_state'] = '本次纳入H' if r['ready_for_import'] else ('用户备选' if r['image_id'] in decisions else '转入本次必做')
        r['history_submitted'] = len({w for (w, iid), info in by_pair.items() if iid == r['image_id'] and info['submissions'] and w not in {19, 26}})
    assert len(selected_h) == 20
    assert not selected_h & set(assigned)
    images = [dict(image_id=iid, code=f'{registry[iid]["building"]}-{registry[iid]["number"]:02d}', group=r['group'], scene=r['scene'], difficulty=r['difficulty'], history_manual=len(manual[iid]), history_semi=len(semi[iid]), required_new=len(assigned[iid]), required_plan_total=len(manual[iid])+len(assigned[iid]), user_target=r['planned_manual'], gap_after_required=max(0,r['planned_manual']-len(manual[iid])-len(assigned[iid])), required_workers=sorted(assigned[iid]), in_adopted_pool=True) for iid,r in adopted.items()]
    for r in images:
        iid = r['image_id']
        assert r['history_manual'] == len(manual[iid]) and r['history_semi'] == len(semi[iid])
        assert r['required_new'] == len(assigned[iid])
        r['alternative_workers'] = sorted(active - seen[iid] - assigned[iid]) if assigned[iid] else []
    rooms = [dict(group=g, adopted_images=len(rr), history_manual=sum(r['history_manual'] for r in rr), required_new=sum(r['required_new'] for r in rr), manual_after_required=sum(r['required_plan_total'] for r in rr), views_with_manual=sum(r['required_plan_total']>0 for r in rr), views_at_least8=sum(r['required_plan_total']>=8 for r in rr)) for g in sorted({r['group'] for r in images}) for rr in [[r for r in images if r['group']==g]]]
    workers = [{k: v for k, v in r.items() if k not in ['optional', 'total_offered']} for r in old['workers']]
    names = chinese_names()
    for r in workers:
        personal = [x for x in required if x['worker_id'] == r['worker_id']]
        r.update(simple=sum(x['difficulty']=='简单' for x in personal), medium=sum(x['difficulty']=='中等' for x in personal), hard=sum(x['difficulty']=='困难' for x in personal), required_rooms=len({x['batch'] for x in personal}))
        if r['language'] == 'zh':
            r['name'] = names[r['worker_id']]
        r['optional_planning_count'] = 20 if r['language'] == 'en' else 0
        w = r['worker_id']
        r['submitted_images'] = sum(worker == w and bool(info['submissions']) for (worker, _), info in by_pair.items())
        r['draft_only_images'] = sum(worker == w and not info['submissions'] and bool(info['drafts']) for (worker, _), info in by_pair.items())
    history = []
    for (w, iid), info in sorted(by_pair.items()):
        if w not in active:
            continue
        im = registry.get(iid)
        history.append(dict(worker_id=w, language=languages[w], image_id=iid,
            code=f'{im["building"]}-{im["number"]:02d}' if im else iid,
            in_648=im is not None, has_submission=bool(info['submissions']), has_draft=bool(info['drafts']),
            manual_in_analysis=w in manual[iid], semi_exposure=w in semi[iid], sources=';'.join(sorted(info['sources']))))
    # 只复制实际记录的图片地址；不带参考点、预测、旧任务身份或scope_gold。
    urls = {}
    url_sources = [ROOT / r['path'] for r in sources] + [ROOT / 'export_label/groudTruth.json', ROOT / 'import_json/mp3d_validation_gt_audit_20260809/mp3d_validation_all_gt_import.json']
    for source in url_sources:
        for task in read(source):
            url = task['data']['image']
            urls.setdefault(Path(unquote(urlparse(url).path)).stem, url)
    imports = ROOT / 'import_json/scene_stability_stage1_20260913_v2'
    imports.mkdir(parents=True, exist_ok=True)
    task_imports = imports / 'label_studio_import'
    task_imports.mkdir(exist_ok=True)
    pending_imports = imports / 'pending_review'
    pending_imports.mkdir(exist_ok=True)
    projects = []
    for key, language in [('zh_required', 'zh'), ('en_required', 'en'), ('en_optional', 'en')]:
        ids = sorted({r['image_id'] for r in rows if r['project_key'] == key}) if key != 'en_optional' else sorted(r['image_id'] for r in pool if r['ready_for_import'])
        template = ROOT / ('import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json' if language == 'zh' else 'import_json/stage1_prescreen_foreign_https_20260609/stage1_prescreen_manual_import_v2_foreign_https.json')
        vis = read(template)[0]['data']['vis_3d'].split('?')[0]
        tasks = []
        for i, iid in enumerate(ids, 1):
            assert iid in urls, f'缺少已记录图片URL：{iid}'
            tasks.append(dict(data=dict(image=urls[iid], vis_3d=vis, base_task_id=iid,
                title=Path(unquote(urlparse(urls[iid]).path)).name, condition='manual',
                dataset_group='scene_stability_stage1', project_key=key,
                annotation_form_version='manual_scope_only_v1', package_task_code=f'{i:03d}')))
        for task in tasks:
            task['data']['project_display_name'] = PROJECT_NAMES[key]
        target_file = task_imports / f'{PROJECT_NAMES[key]}.json'
        save_json(target_file, tasks)
        code_map = {iid: f'{i:03d}' for i, iid in enumerate(ids, 1)}
        for r in rows if key != 'en_optional' else pool:
            if r['project_key'] == key and r['image_id'] in code_map:
                r['package_task_code'] = code_map[r['image_id']]
                r['display_task_code'] = PROJECT_NAMES[key] + '-' + code_map[r['image_id']]
        projects.append(dict(project_key=key, project_display_name=PROJECT_NAMES[key], language=language, images=len(ids),
            import_file=target_file.relative_to(ROOT).as_posix(),
            draft_file=None,
            release_status='ready_for_runtime_binding',
            project_id=None, project_binding_status='pending_post_import', image_urls_status='observed_in_repository_not_network_checked',
            selection_mode='free_choice' if key == 'en_optional' else 'required_manifest',
            personal_hard_cap=20 if key == 'en_optional' else None, image_pool_limit=20 if key == 'en_optional' else None, image_hard_cap=None))
    save_json(imports / 'projects.json', projects)
    save_json(imports / 'pending_doorway_adoption.json', [])
    save_json(imports / 'ProjectH_本次选图与备选.json', pool)
    save_json(imports / 'required_assignments.json', rows)
    save_json(imports / 'historical_exposure.json', [dict(worker_id=w, image_id=iid) for (w, iid) in sorted(by_pair) if w in active])
    result = dict(schema='stage1_image_package_proposal_v2', status='本地准备完成_未导入_未派发',
        selection_source=str(SELECTION), registry_source=str(REGISTRY), previous_proposal=str(args.previous_package),
        assignments=rows, workers=workers, images=images, rooms=rooms, optional_pool=pool, projects=projects,
        history=history, raw_sources=sources, exposure_scope=old['exposure_scope'],
        optional_policy=dict(mode='free_choice_separate_project', individual_assignments=False, planning_per_english_worker=20,
                             guaranteed_new=0, personal_hard_cap=20, image_pool_limit=20, image_hard_cap=None, fixed_kind_ratio=False,
                             release_status='ready_for_runtime_binding'),
        ordering=dict(seed=20260913, method='组内轮换后中文2对英文3对跨组交换；无最小间隔约束', workers=ordering),
        counts=dict(required=480, required_images=len({r['image_id'] for r in required}), optional_ready_images=20, optional_pending_images=0, optional_reserve_images=5, rooms=len({r['batch'] for r in required})),
        formal_contract_changed=False, user_selection_changed=False)
    save_json(out / '分配建议与核验.json', result)
    save_json(out / '必做整房核查.json', room_audit)
    save_csv(out / '必做整房核查.csv', room_audit)
    save_csv(out / '必做逐人人图清单.csv', rows)
    save_json(out / '英文自愿候选池.json', pool)
    save_csv(out / '原始导出核对范围.csv', sources)
    coverage = []
    required_ids = {r['image_id'] for r in rows}
    optional_ids = {r['image_id'] for r in pool if r['ready_for_import']}
    for group in current['effective_groups']:
        rr = [r for r in current['images'] if r['group'] == group['group']]
        accepted = [r for r in rr if r['status'] == '确定采用']
        number_text = lambda a: '、'.join(f'{r["number"]:02d}' for r in a) or '—'
        coverage.append(dict(group=group['group'], adoption=group['adoption'], reviewed=len(rr), adopted=len(accepted),
            required=number_text([r for r in accepted if r['image_id'] in required_ids]),
            optional=number_text([r for r in accepted if r['image_id'] in optional_ids]),
            history_only_now=number_text([r for r in accepted if r['image_id'] not in required_ids | optional_ids and r['history_manual'] > 0]),
            not_scheduled=number_text([r for r in accepted if r['image_id'] not in required_ids | optional_ids and r['history_manual'] == 0])))
    save_json(out / '逐组使用核对.json', coverage)
    report = ['# 已筛选图片实际用到了哪里', '', '本轮改为优先完整覆盖部分房间，旧版分散覆盖19组的480份配对已被替换。已采用19组102张中，本轮必做覆盖6组44张：7张仅复用历史、37张新增480份。', '',
        '排序先限于明确采用、非OOS的图片，再按剔除不采用图后的房间视角数降序；同数时沿用原审查表顺序。原记录没有另一个明确的数字优先级，不把表顺序宣称为用户优先级。固定中文每人20张、英文每人30张，排除本人历史接触；只选择能够整房安排的组合。G090虽有7张，但在更高顺位房间及固定个人负载均保留时无法一起装入480份，故本轮暂缓。', '',
        '入选G172/G184/G179/G178/G047/G237。G184的18、26、41、59、88最多19人，距目标20人各缺1人；没有伪称全部达到原目标。实际退出还会带来进一步缺口。', '',
        'Project H另为12张已复核门洞＋8张同房补充，20张固定池。选做不能作为完整覆盖的承诺；G178原4张选做已转入必做，H保留其余8张同房图。', '',
        '| 组 | 审过图数 | 已采用 | 必做图片编号 | H拟保留同房 | 当前复用历史Manual | 暂未安排新增Manual且无历史Manual |',
        '|---|---:|---:|---|---|---|---|']
    report += [f'| {r["group"]} | {r["reviewed"]} | {r["adopted"]} | {r["required"]} | {r["optional"]} | {r["history_only_now"]} | {r["not_scheduled"]} |' for r in coverage]
    report += ['', '完成采集后，以图为单位检验同房其他视角的预测，不把同图的随机顺序重排当成新增独立图片。完整视角覆盖有助于研究，但不保证相似或收敛。当前尚未导入或派发，旧版分发表不要混用。']
    (out / '逐组使用核对.md').write_text('\n'.join(report), encoding='utf-8')
    for lang, name in [('zh', '中文必做包'), ('en', '英文必做包')]:
        folder = out / name
        folder.mkdir(exist_ok=True)
        links = []
        combined = []
        for w in sorted(w for w in active if languages[w] == lang):
            rr = [r for r in rows if r['worker_id'] == w]
            intro = 'Required list. Project links will be supplied after setup. The separate optional project is voluntary.' if lang == 'en' else '必做清单。项目创建并核对编号后另行提供任务入口。'
            content = ''.join(f'<tr><td>{r["order"]}</td><td>{r["display_task_code"]}</td><td>{escape(r["code"])}</td></tr>' for r in rr)
            if lang == 'en':
                path = folder / f'W{w:03d}.html'
                path.write_text(f'<!doctype html><meta charset="utf-8"><title>W{w:03d}</title><style>body{{font:17px/1.6 Arial;max-width:900px;margin:32px auto}}td,th{{padding:6px 24px;text-align:left}}</style><h1>W{w:03d} · {len(rr)}</h1><p>{intro}</p><p>Package code ≠ Label Studio task ID. Runtime binding pending.</p><table><tr><th>Order</th><th>Package code</th><th>Image</th></tr>{content}</table>', encoding='utf-8')
                links.append(f'<li>W{w:03d} — <a href="Project_G_W{w:03d}.xlsx">Excel</a> · <a href="W{w:03d}.html">HTML</a></li>')
            else:
                combined.append(f'<h2 id="W{w:03d}">{escape(names[w])} · W{w:03d} · 任务7必做20张</h2><table><tr><th>个人顺序</th><th>包内编号</th><th>图片编号</th></tr>{content}</table>')
                links.append(f'<a href="#W{w:03d}">W{w:03d}</a>')
        index = folder / 'index.html'
        if lang == 'zh':
            index.write_text('<!doctype html><meta charset="utf-8"><title>中文必做汇总</title><style>body{font:17px/1.6 Arial;max-width:1000px;margin:32px auto}td,th{padding:5px 24px;text-align:left}nav{position:sticky;top:0;background:white;padding:12px}nav a{padding:8px}</style><h1>中文必做任务汇总 · 9人各20张</h1><p>在这一份文件内找到自己的编号，按个人顺序标注。包内编号不是线上任务ID，项目创建后另行提供入口。</p><nav>' + ' '.join(links) + '</nav>' + ''.join(combined), encoding='utf-8')
        else:
            index.write_text('<!doctype html><meta charset="utf-8"><h1>管理目录 · Individual English lists</h1><p>每人只发送自己的文件。</p><ul>' + ''.join(links) + '</ul>', encoding='utf-8')
    import os
    gallery = []
    for iid in sorted({r['image_id'] for r in rows} | pool_ids, key=lambda iid: (registry[iid]['group_codes'], registry[iid]['number'])):
        r = registry[iid]
        path = ROOT / r['path']
        assert path.is_file()
        relative = Path(os.path.relpath(path, out)).as_posix()
        gallery.append(f'<figure><figcaption>{escape(" / ".join(r["group_codes"]))} · {r["building"]}-{r["number"]:02d}</figcaption><img loading="lazy" width="100%" src="{escape(relative)}"></figure>')
    (out / '管理用原图总览.html').write_text('<!doctype html><meta charset="utf-8"><h1>管理用原图总览</h1><p>含本次必做、选做及1张门洞备选；不是人员分发表。门洞复核原话另存。原图来自仓库，移动本页需保留路径。</p>' + ''.join(gallery), encoding='utf-8')
    (out / '.gitignore').write_text('*.zip\n工作簿检查/\n*.inspect.ndjson\n', encoding='utf-8')
    print(json.dumps(result['counts'], ensure_ascii=False))


if __name__ == '__main__':
    build_v2()
