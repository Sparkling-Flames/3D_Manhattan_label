"""将 v2 实际统计与最终几何接入已有离线研究台；不重评分或融合。"""
import gzip
import json
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from collections import Counter

from .build_research_workbench_20261017 import write

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
STATS = ROOT / 'research/statistics/v2_integrated_analysis_20261019'
EVIDENCE = ROOT / 'research/statistics/v2_evidence_audit_20261019'
QUALITY = ROOT / 'research/quality/quality_workers_v2_20261019'
INPUT = ROOT / 'research/data/releases/v2/analysis_input'
SNAPSHOT = 'v2_integrated_analysis_20261019'
SAME_ROOM = ROOT / 'research/same_room/same_room_v2_prediction_20261019'
EXPLORER = PAGE
EXTRA = EXPLORER / 'DISPLAY_TABLES_20261020.json'
MULTIVIEW = ROOT / 'research/same_room/same_room_multiview_20261020'
TAXONOMY = ROOT / 'research/workers/personnel_taxonomy_20261021'
MECHANISMS = PAGE / 'MECHANISM_INTERFACE_20261021.json'
SAME_ROOM_REVIEW = PAGE / 'SAME_ROOM_REVIEW_INTERFACE_20261021.json'
BRIEFING = PAGE / 'BRIEFING_TABLES_20261023.json'
PERSONNEL_MAIN = ROOT / 'research/workers/personnel_main_figures_v2_20261023'
POPULATION_CASES = ROOT / 'research/workers/personnel_population_curves_v2_20261023/cases'
SAME_ROOM_REBUILT = ROOT / 'research/same_room/same_room_large_block_rebuilt_20261023'
DOORWAY_CASE = POPULATION_CASES / 'doorway_full_pool_20261024/CASE_DATA.json'
D10_SENSITIVITY = ROOT / 'research/workers/personnel_d10_formation_sensitivity_20261024'
FUSION_COMMON = ROOT / 'research/fusion/fusion_common_panel_20261024'
QUALITY_VALIDATION = ROOT / 'research/quality/quality_independent_validation_20261024/human_review'
MULTIVIEW_TABLES = ['mean_summary.csv', 'mean_groups.csv', 'individual_summary.csv',
                    'curve_summary.csv', 'replay_behavior.csv', 'group_coverage.csv',
                    'background_buildings.csv']
EXTRA_MODULE_TABS = {
    'same_room': [('多视角预测汇总', 'same_room_multiview__mean_summary'),
                  ('多视角逐组', 'same_room_multiview__mean_groups'),
                  ('个人Q预测汇总', 'same_room_multiview__individual_summary'),
                  ('真实融合曲线汇总', 'same_room_multiview__curve_summary'),
                  ('人数曲线行为', 'same_room_multiview__replay_behavior'),
                  ('覆盖与共同人员', 'same_room_multiview__group_coverage'),
                  ('背景对照', 'same_room_multiview__background_buildings')],
    'workers': [('人员工作标签（Rnew2/F01，仅研究参照）', 'workers__working_labels_60'),
                ('高Q23效率与行为特征', 'workers__high_q_features')],
    'fusion': [('类别块逐建筑', 'fusion__composition_panel_building'),
               ('类别块逐图', 'fusion__composition_panel_image'),
               ('对应角点距离', 'fusion__composition_corner_distances'),
               ('对应角点汇总', 'fusion__composition_corner_summary'),
               ('角点面板汇总', 'fusion__composition_corner_panel'),
               ('独立重抽样区间', 'fusion__audit_bootstrap'),
               ('失败与分母', 'fusion__audit_failure_denominators'),
               ('F01效率重聚合', 'fusion__audit_f01_time')],
}
BRIEFING_MODULE_TABS = {
    'quality': [('局部质量案例', 'quality__case_rows'), ('原分项与参考', 'quality__latest_case_components')],
    'conditions': [('固定结构复杂度', 'difficulty__fixed_complexity_summary'),
                   ('同人固定六转折', 'difficulty__person_fixed6_conditions'),
                   ('人员多数支持', 'difficulty__majority_support'),
                   ('逐图范围支持', 'difficulty__image_scope_support')],
    'workers': [('连续人员画像', 'profiles__continuous'),
                ('同支持人员对', 'profiles__selected_common_pairs')],
    'fusion': [('机制端点对齐', 'fusion_closeout__endpoint_alignment'),
               ('历史人数条件', 'fusion_closeout__count_panel_by_condition')],
    'same_room': [('同房均值对照', 'same_room_pro__direct_mean_summary'),
                  ('选队策略结果', 'same_room_pro__policy_summary'),
                  ('人数停止结果', 'same_room_pro__stopping_summary'),
                  ('源历史获取成本', 'same_room_pro__source_acquisition_summary')],
}


def read(path):
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(raw.decode('utf-8-sig'))


def classification_evidence():
    """只打包已存类中心与名单；类号始终连同方法和排除建筑解释。"""
    source = ROOT / 'research/workers/personnel_classification_guide_20261025/sources'
    guide = read(source.parent / 'GUIDE.json')
    methods = {m['id'] for m in guide['methods']} | {'DSTRUCT_K2'}
    paths = [source / 'NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz',
             source / 'SCOPE_INCREMENT_CLASS_DEFINITIONS_ALL_LOBO.csv.gz',
             ROOT / 'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/06A/research/workers/personnel_exchange_discrimination_20261025/reverse/REVERSE_CLASS_CENTERS_ALL_LOBO.csv.gz']
    definitions = []
    for path in paths:
        frame = pd.read_csv(path)
        frame = frame[frame.method.isin(methods)]
        definitions.extend(frame.astype(object).where(frame.notna(), None).to_dict('records'))
    keys = [(r['method'], r['heldout_building'], r['class_id']) for r in definitions]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate current class definition')
    labels = pd.read_csv(source / 'NEW_METHOD_LABELS_ALL_LOBO.csv.gz')
    coarse = []
    for (fold, class_id), rows in labels[labels.method == 'DSTRUCT_K2'].groupby(['heldout_building', 'class_id']):
        coarse.append(dict(method='DSTRUCT_K2', fold=fold, class_id=class_id,
                           known=bool(rows.known.all()), workers=sorted(rows.worker_id.tolist())))
    by_key = {(r['method'], r['heldout_building'], r['class_id']): r for r in definitions}
    for row in guide['rosters'] + coarse:
        if not row['known']:
            continue
        saved = by_key[(row['method'], row['fold'], row['class_id'])]
        if set(saved['members'].split('|')) != set(row['workers']):
            raise ValueError('current roster/definition mismatch: ' + str(row))
    return dict(schema='current_class_evidence_v1', definitions=definitions, coarse_rosters=coarse,
                sources=[p.relative_to(ROOT).as_posix() for p in paths])


def load_same_room_prediction(source):
    tables = {}
    for filename, columns in read(source / 'FIELD_CONTRACT.json')['tables'].items():
        frame = pd.read_csv(source / filename)
        if list(frame.columns) != columns:
            raise ValueError('same-room display schema drift: ' + filename)
        rows = frame.astype(object).where(frame.notna(), None).to_dict('records')
        for row in rows:
            if 'source_image' in row:
                row.update(image_a=row['source_image'], image_b=row['target_image'])
            if 'image_a' in row:
                row['condition'] = 'manual'
        tables['same_room_prediction__' + Path(filename).stem] = rows
    return tables


def load_contract_tables(source, prefix, include):
    contract = read(source / 'FIELD_CONTRACT.json')['tables']
    tables = {}
    for filename in include:
        if filename not in contract:
            raise ValueError('display table not in FIELD_CONTRACT: ' + filename)
        frame = pd.read_csv(source / filename, encoding='utf-8-sig')
        if list(frame.columns) != contract[filename]:
            raise ValueError('display schema drift: ' + filename)
        tables[prefix + Path(filename).stem] = (
            frame.astype(object).where(frame.notna(), None).to_dict('records'))
    return tables


def load_declared_tables(manifest):
    tables, provenance = {}, {}
    for spec in manifest['tables']:
        path = ROOT / spec['source']
        if not path.is_file():
            raise FileNotFoundError('display source missing: ' + spec['id'] + ' -> ' + spec['source'])
        frame = pd.read_csv(path, encoding='utf-8-sig')
        if list(frame.columns) != spec['columns']:
            raise ValueError('display schema drift: ' + spec['id'] + ' (' + spec['source'] + ')')
        tables[spec['id']] = (
            frame.astype(object).where(frame.notna(), None).to_dict('records'))
        provenance[spec['id']] = spec['source']
    return tables, provenance


def validate_objects(objects, scores):
    annotations = {o['object_id']: o for o in objects if o['object_kind'] == 'annotation'}
    score_map = {r['object_id']: r for r in scores}
    if len(score_map) != len(scores):
        raise ValueError('duplicate score object')
    if annotations.keys() != score_map.keys():
        raise ValueError('annotation inventory mismatch')
    for key, obj in annotations.items():
        if obj['image_id'] != score_map[key]['image_id']:
            raise ValueError('object image mismatch: ' + key)
    return annotations, score_map


def pack_annotation(obj, score, reference_ids):
    target = score.get('rescore_target_id') or score.get('reference_id') or score.get('chosen_target_id')
    if target and target not in reference_ids:
        raise ValueError('missing image reference: ' + target)
    return dict(object_id=obj['object_id'], worker_id=obj['worker_id'], condition=obj['condition'],
                retained=obj['cleaning_disposition'] == 'retained', target_id=target,
                points=obj.get('points_1024x512'), raw_points=obj.get('original_export_points'),
                before_preprocessing_points=obj.get('before_preprocessing_points'),
                ring_confirmed=obj.get('ring_confirmed', False), order_status=obj.get('order_status'),
                geometry_compatible=True, geometry_binding_reasons=[],
                quality_usable=score['quality_usable'],
                quality={k: score.get(k) for k in ('B8L2', 'D10', 'IoU3D100')},
                calculation_status=score.get('calculation_status', score.get('calculation_class', score.get('full_score_state'))),
                quality_exclusion_reasons=score.get('quality_exclusion_reasons', []))


def display_table(out, name, rows, source):
    columns = list(dict.fromkeys(k for r in rows for k in r))
    parts = []
    for start in range(0, len(rows), 2000):
        path = f'tables/{name}_{start // 2000}.json'
        write(out / path, dict(columns=columns, rows=[[r.get(k) for k in columns] for r in rows[start:start+2000]]))
        parts.append(dict(path=path))
    return dict(id=name, row_count=len(rows), columns=columns, parts=parts, path=source)


def find_photo(root, record):
    """Resolve the original panorama from a possibly Windows-style path, then repo assets."""
    value = (record.get('photo') or '').strip()
    if value:
        text = value.replace('\\', '/')
        if text.startswith('./'):
            text = text[2:]
        candidate = root / text
        if candidate.is_file():
            return candidate
    image_id = record.get('image_id', '')
    for rel in (f'data/mp3d_layout/valid/img/{image_id}.png',
                f'data/mp3d_layout/test/img/{image_id}.png',
                f'data/mp3d_layout/img_v/{image_id}.jpg',
                f'research/workers/pro_personnel_v2_20261019/previews/{image_id}.jpg'):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def pack_resources(scores, evidence):
    context=read(ROOT/'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz')
    frozen_objects=[dict(object_id=r['object_id'],object_kind='annotation',image_id=r['image_id'],
                         worker_id=r['worker_id'],condition=r['condition'],cleaning_disposition=r['cleaning_disposition'],
                         points_1024x512=r['points_1024x512'],original_export_points=r['original_points'],
                         before_preprocessing_points=r['received_processed_points'],
                         ring_confirmed=r['coordinate_evidence']['ring_confirmed'],order_status=r['coordinate_evidence']['order_status']) for r in evidence]
    objects, score_map = validate_objects(frozen_objects, scores)
    difficulty = {r['image_id']: r for r in context['difficulty_records']}
    refs, annotations = defaultdict(list), defaultdict(list)
    for ref in context['reference_catalog']:
        refs[ref['image_id']].append(ref)
    for obj in objects.values():
        annotations[obj['image_id']].append(obj)
    images = []
    for number, (image_id, d) in enumerate(difficulty.items()):
        reference_ids = {r['target_id'] for r in refs[image_id]}
        answers = [pack_annotation(o, score_map[o['object_id']], reference_ids) for o in annotations[image_id]]
        references = [dict(target_id=r['target_id'], label=f"{i+1} · {r['reference_version']}" + (' · 当前' if r['current_target'] else ''),
                           points=r['points_1024x512'], floor=r['floor_xz_h'], current=r['current_target'],
                           reference_full_available=r['full_reference_available']) for i,r in enumerate(refs[image_id])]
        photo = find_photo(ROOT, d)
        retained = [a for a in answers if a['retained']]
        flags = dict(gt_uncertain=d.get('reference_status')=='uncertain',current_pending=bool(d.get('difficulty_analysis_exclusion')))
        flags.update(oos=any(score_map[a['object_id']].get('is_oos') is True for a in answers),
                     gt_problem=bool(d.get('gt_error_excluded')), image_hold=any(r.get('image_analysis_blocked') for r in refs[image_id]))
        packed = dict(image_id=image_id, image_code=d['image'], building_id=image_id.split('_')[0],
                      difficulty=dict(label=d['current_class'], exclusion=d.get('difficulty_analysis_exclusion')),
                      scene=dict(raw=d['scene'], doorway_status=d['doorway_status'], oos_subtype=d['oos_subtype']),
                      flags=flags, notes=[d.get('evidence',''), d.get('applicability_note','')],
                      spaces=[dict(r, user_candidate=not r['target_id'].startswith('gt:')) for r in references],
                      multiple_spaces=len(references)>1, references=references, annotations=answers,
                      photo='../../../'+photo.relative_to(ROOT).as_posix() if photo else None,
                      photo_status='available' if photo else 'missing',
                      counts=dict(retained_people=len({a['worker_id'] for a in retained}),
                                  retained_records=len(retained), raw_records=len(answers),
                                  quality_records=sum(a['quality_usable'] for a in answers)))
        # Coordinate arrays are in the per-image file only, not repeated in the index.
        packed['spaces'] = [{k:v for k,v in r.items() if k not in ('points','floor')} for r in packed['spaces']]
        path = f'images/{number}.json'
        write(PAGE / 'v2-resources' / path, packed)
        images.append(dict({k:v for k,v in packed.items() if k not in ('references','annotations')}, detail=path))
    assert sum(i['counts']['raw_records'] for i in images) == len(scores)
    summary = dict(raw_records=len(scores), images=len(images), quality_records=sum(r['quality_usable'] for r in scores),
                   retained_people=len({r['worker_id'] for r in scores if r['cleaning_disposition']=='retained'}))
    write(PAGE / 'v2-resources/index.json', dict(schema='research_workbench_display_v1', data_release='v2',
          snapshot_id=SNAPSHOT, built_at=datetime.now(timezone.utc).isoformat(), images=images, pools=[],
          image_summary=summary, geometry_binding_mismatches=0, gallery_score_context=dict(data_release='v2',primary_metric='B8L2',parallel_metric='D10',n1_applied=False),
          fusion_revision='v2_not_run; v1 results available via version selector', dependencies=[],
          historical_offline_files=0, supplement_plan=None))
    return summary


def saved_fusion_examples(resources):
    """连接门洞满员及普通失败端点；不运行融合、评分或重造票账。"""
    folder = DOORWAY_CASE.parent
    with (folder / 'DOORWAY_FULL_POOL_STATUS.csv').open(encoding='utf-8-sig', newline='') as f:
        status = list(csv.DictReader(f))
    keys = {r['team_key'] for r in status}
    if len(status) != 17 or len(keys) != 17:
        raise ValueError('doorway full-pool inventory drift')
    scalar_path = POPULATION_CASES.parent / 'results/ENDPOINT_SCALARS.csv.gz'
    scalars, full_rows, extra = {}, {}, {}
    with gzip.open(scalar_path, 'rt', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['k'] == row['pool_n']:
                full_rows[row['pool_id']] = row
            if row['team_key'] in keys:
                scalars[row['team_key']] = row
            if row['k'] == row['pool_n'] and ((row['image']=='VFuaQ6m2Qom-04' and row['condition']=='manual') or (row['image']=='e9zR4mvMWw7-39' and row['condition']=='semi')):
                extra['full_'+row['image']] = row
            if (row['layer']=='ordinary_manual' and int(row['k'])>=3 and row['score_status'] in ('no_connection','invalid_floor')
                    and (row['score_status']=='invalid_floor' or (row['image']=='7y3sRwLe3Va-03' and int(row['nodes'])>=6))):
                extra.setdefault(row['score_status'], row)
    for kind, row in extra.items():
        scalars[row['team_key']] = row
        keys.add(row['team_key'])
        status.append({k:row[k] for k in ('image','pool_id','pool_n','team_key','nodes','complete_evaluable')})
    geometry_path = scalar_path.with_name('ENDPOINT_GEOMETRY.json.gz')
    geometries = {r['team_key']: r for r in read(geometry_path) if r['team_key'] in keys}
    frozen_path = ROOT / read(DOORWAY_CASE)['sources'][0]
    pools = {p['pool_id']: p for p in read(frozen_path)['images']}
    images = {i['image_code']: i for i in resources['images']}
    if set(scalars) != keys or set(geometries) != keys:
        raise ValueError('doorway saved endpoint not available')
    cases = []
    for item in status:
        row = scalars[item['team_key']]
        pool, stored = pools[item['pool_id']], geometries[item['team_key']]
        detail = read(PAGE / 'v2-resources' / images[item['image']]['detail'])
        lookup = {a['object_id']: a for a in detail['annotations']}
        reference = pool['reference']
        workers = row['member_workers'].split('|')
        pool_members = {r['worker_id']: r['object_id'] for r in pool['records']}
        ref = dict(points=reference['points_1024x512'], floor=reference['floor_xz_h'], target_id=reference['target_id'])
        if (row['condition'] != pool['meta']['condition'] or row['image_id'] != detail['image_id']
                or row['reference_id'] != reference['target_id']
                or len(workers) != int(row['k']) or len(set(workers)) != len(workers) or not set(workers) <= set(pool_members)
                or (row['k']==row['pool_n'] and set(workers)!=set(pool_members))
                or set(row['member_object_ids'].split('|')) != {pool_members[w] for w in workers}
                or any(r['object_id'] not in lookup or lookup[r['object_id']]['worker_id'] != r['worker_id']
                       or lookup[r['object_id']]['points'] != r['points'] for r in pool['records'])):
            raise ValueError('doorway frozen membership/reference drift: ' + item['image'])
        metric = lambda name: float(row[name]) if row.get(name) else None
        geometry = stored['geometry']
        complete = row['complete_evaluable'] == 'True'
        nodes = int(row['nodes'])
        supports = [int(x) for x in row['node_supports'].split('|') if x]
        if (complete != (item['complete_evaluable'] == 'True') or nodes != int(item['nodes'])
                or (geometry['points'] is not None and len(geometry['points']) != 2 * nodes)
                or sorted(supports) != sorted(stored['node_supports'])
                or (not complete and any(metric(k) is not None for k in ('B8L2', 'D10', 'IoU3D100')))):
            raise ValueError('doorway saved status drift: ' + item['image'])
        team = dict(label=('满员 n=' if row['k']==row['pool_n'] else '保存失败 n=') + str(len(workers)), team_key=item['team_key'], workers=workers,
                    member_object_ids=[pool_members[w] for w in workers], nodes=nodes,
                    B8L2=metric('B8L2'), D10=metric('D10'), IoU3D100=metric('IoU3D100'),
                    complete_evaluable=complete, score_status=row['score_status'],
                    points=geometry['points'], footprint=geometry['footprint'],
                    order_status=geometry['order_status'], ring_confirmed=geometry['ring_confirmed'],
                    geometry_status=geometry.get('geometry_status', row['geometry_status']), reason=geometry['reason'],
                    minimum_support=int(row['minimum_support']),
                    identity_groups_n=int(row['identity_groups_n']), unselected_groups_n=int(row['unselected_groups_n']),
                    selected_node_supports=supports, vote_ledger_status='selected_distribution_only',
                    source_state=row['geometry_state_pointer'],
                    provenance={k:row[k] for k in ('data_release','reference_version','endpoint_origin','geometry_origin','geometry_state_pointer')})
        teams = [team]
        if item['image'] == '7y3sRwLe3Va-06':
            for endpoint in read(DOORWAY_CASE)['endpoints'][:-1]:
                g = endpoint['geometry']
                teams.append(dict(label='n=' + str(endpoint['k']), team_key=endpoint['team_key'], workers=endpoint['members'],
                    member_object_ids=[pool_members[w] for w in endpoint['members']], nodes=endpoint['nodes'],
                    **endpoint['metrics'], complete_evaluable=endpoint['complete_evaluable'], score_status=endpoint['score_status'],
                    points=g['points'], footprint=g['footprint'], order_status=g['order_status'], ring_confirmed=g['ring_confirmed'],
                    geometry_status=g.get('geometry_status'), reason=g['reason'], minimum_support=endpoint['minimum_support'],
                    identity_groups_n=endpoint['identity_groups_n'], unselected_groups_n=endpoint['unselected_groups_n'],
                    selected_node_supports=endpoint['selected_node_supports'], vote_ledger_status='selected_distribution_only'))
        doorway = row['layer']=='doorway_manual'
        cases.append(dict(case_id=('D_FULL_' if doorway else 'F_SAVED_') + item['image'] + ('' if row['k']==row['pool_n'] else '_'+row['score_status']), title=item['image'] + (' · 门洞满员保存结果' if doorway else ' · 普通场景保存失败'),
            image_id=detail['image_id'], condition=row['condition'], snapshot_id=SNAPSHOT, reference=ref,
            explanation='已计算的冻结满员池；完整可评、节点不足与连接失败分别解释。库存人数不替代冻结池人数。',
            worker_classes={}, source=(folder / 'README.md').relative_to(ROOT).as_posix() if doorway else 'research/fusion/fusion_paper_closeout_20261022/README.md', teams=teams))
    failed = [c['teams'][0] for c in cases if c['case_id'].startswith('D_FULL_') and not c['teams'][0]['complete_evaluable']]
    if len(failed) != 6 or sorted(t['nodes'] for t in failed) != [2, 3, 3, 3, 3, 3]:
        raise ValueError('doorway full-pool failure denominator drift')
    actual = pd.read_csv(POPULATION_CASES.parent / 'design/ACTUAL_POOLS.csv')
    ordinary = actual[actual.layer=='ordinary_manual']
    curves_path = POPULATION_CASES.parent / 'late_population_20261024/IMAGE_CURVES.csv.gz'
    curves = pd.read_csv(curves_path)
    ever_ids = set(curves[(curves.k>=3)&(curves.failure>0)].pool_id) & set(ordinary.pool_id)
    ever = ordinary[ordinary.pool_id.isin(ever_ids)]
    layers = {layer:dict(pools=int(sum(actual.layer==layer)), incomplete=sum(row['layer']==layer and row['complete_evaluable']=='False' for row in full_rows.values())) for layer in ['ordinary_manual','ordinary_semi','doorway_manual']}
    if layers['ordinary_manual']!={'pools':177,'incomplete':1} or layers['ordinary_semi']!={'pools':32,'incomplete':1} or len(ever_ids)!=54:
        raise ValueError('saved ordinary failure support drift')
    return cases, dict(pools=17, incomplete=6, three_nodes=5, two_nodes=1, layers=layers,
                       ordinary_ever_failure_images=len(ever_ids), ordinary_ever_by_difficulty=dict(Counter(ever.difficulty)),
                       ordinary_images_by_difficulty=dict(Counter(ordinary.difficulty)),
                       ordinary_curve_source=curves_path.relative_to(ROOT).as_posix(),
                       examples=[{k:c[k] for k in ('case_id','image_id','condition','title')} for c in cases if c['case_id'].startswith('F_SAVED_')],
                       source=(folder / 'DOORWAY_FULL_POOL_STATUS.csv').relative_to(ROOT).as_posix(),
                       sources=[p.relative_to(ROOT).as_posix() for p in (frozen_path, scalar_path, geometry_path)])


def pack_comparisons(evidence, resources):
    """仅搬运已有案例和保存状态；不在打包时重新融合或评分。"""
    labels = pd.read_csv(ROOT/'research/workers/personnel_interchangeability_followup_20261020/audit_learning/RESEARCH_WORKING_LABELS_60.csv').fillna('').to_dict('records')
    cases = []
    source = ROOT/'research/workers/personnel_interchangeability_20261020/interchangeability_20261020/cases'
    for path in sorted(source.glob('S*.json')):
        case = read(path)
        cases.append(dict(case_id=case['case_id'], title=case['title'], explanation=case['selection_reason'],
            image_id=case['embedded_pool']['meta']['image_id'], condition='manual',
            reference=dict(points=case['reference']['points_1024x512'],floor=case['reference']['floor_xz_h'],target_id=case['reference']['target_id']),
            worker_classes=case['worker_classes'], source=path.relative_to(ROOT).as_posix(),
            teams=[dict(label=t['label'],workers=t['member_workers'],points=t['geometry']['points'],
                footprint=t['geometry']['footprint'],B8L2=t['B8L2'],D10=t['D10'],
                nodes=t['nodes'],team_key=t['team_key']) for t in case['teams']]))
    marking = ROOT/'research/workers/personnel_marking_patterns_20261020/cases.json'
    if marking.exists():
        for case in read(marking):
            cases.append(dict(case_id=case['case_id'], title=case['title'],
                explanation='已有标法研究局部案例；保留GT问题与非质量作答，不新增墙面语义裁决。',
                image_id=case['image_id'],condition=case['condition'],zoom=case['zoom'],
                source=marking.relative_to(ROOT).as_posix(),worker_classes={},teams=[],
                reference=dict(points=case['reference']['points_1024x512'],floor=case['reference']['floor_xz_h'],target_id=case['reference']['target_id'])))
    # Use the committed frozen audit, rather than an ignored, previously generated view-data.js.
    single_source = ROOT/'research/workers/personnel_type_validation_next_20261019/CASE_SCORE_AUDIT.json'
    single = read(single_source)
    members = set().union(*(set(t['members']) for t in single['teams'].values()))
    bound = [r for r in evidence if r['image_code'] == 'wc2JMjhGNzB-46'
             and r['condition'] == 'manual' and r['worker_id'] in members]
    target_ids = {r['reference_id'] for r in bound}
    if len(target_ids) != 1 or {r['worker_id'] for r in bound} != members:
        raise ValueError('B01 saved-team reference or membership binding mismatch')
    ref = bound[0]['reference_evidence']
    cases.append(dict(case_id='B01_bottom_y', title='局部缺角与bottom-y／3D敏感性',
        explanation='既有25人真实团队对照：局部缺角触发方向重罚；可观察底点y与3D变化。这不是bottom-y单因素因果实验。',
        image_id=bound[0]['image_id'], condition='manual', source=single_source.relative_to(ROOT).as_posix(),
        reference=dict(points=ref['points_1024x512'], floor=ref['floor_xz_h'], target_id=ref['target_id']),
        worker_classes={}, teams=[dict(label=label, workers=t['members'], points=t['points'],
            footprint=[[p[0],p[2]] for p in t['geometry']['bottom3d']],
            B8L2=t['score']['B8L2'], D10=t['score'].get('D10'),
            nodes=len(t['points'])//2, team_key=t['request_id']) for label,t in single['teams'].items()]))
    states = read(MULTIVIEW/'structure_transfer/case_states.json')
    groups = defaultdict(list)
    for state in states:
        before = [r['worker'] for r in state['before']['assignments']]
        after = [r['worker'] for r in state['after']['assignments']]
        groups[state['group_id']].append(dict(image_id=state['image_id'],image_code=state['image'],
            k=state['k'], before=dict(workers=before,geometry=state['before']['candidate'],B8L2=state['quality_before']),
            after=dict(workers=after,geometry=state['after']['candidate'],B8L2=state['quality_after']),
            reference=dict(points=state['reference']['points_1024x512'],floor=state['reference']['floor_xz_h'],target_id=state['reference']['target_id'])))
    for views in groups.values():
        assert all(v['before']['workers']==views[0]['before']['workers'] and v['after']['workers']==views[0]['after']['workers'] for v in views), 'multiview members differ'
    image_ids = {r['image_id'] for r in evidence}
    doorway_cases, doorway_summary = saved_fusion_examples(resources)
    cases.extend(doorway_cases)
    assert all(c['image_id'] in image_ids for c in cases)
    payload=dict(schema='research_workbench_saved_comparisons_v1',display_revision='doorway_full_pool_20261025',
        data_release='v2',snapshot_id=SNAPSHOT,failure_summary=doorway_summary,
        labels=labels,cases=cases,groups=dict(groups),
        group_source='research/same_room/same_room_multiview_20261020/structure_transfer/case_states.json',
        caveat='Saved illustrative cases, not full v2 fusion coverage; reference and eligibility remain unchanged.')
    write(PAGE/'v2-resources/comparisons.json',payload)
    resources.update(display_revision='doorway_full_pool_20261025',comparisons='comparisons.json',
        fusion_failure_summary=doorway_summary,
        fusion_revision='saved_v2_cases_multiview_and_17_doorway_full_pools; all_paths_not_packed')
    write(PAGE/'v2-resources/index.json',resources)


def source_entry(path, label=None):
    """Fingerprint saved inputs; these are read-only display dependencies, not new results."""
    import hashlib
    path = Path(path)
    raw = path.read_bytes()
    return dict(label=label or path.name, path=path.relative_to(ROOT).as_posix(),
                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def frame_records(path):
    frame = pd.read_csv(path, encoding='utf-8-sig')
    return frame.astype(object).where(frame.notna(), None).to_dict('records')


def reference_display(reference):
    return dict(target_id=reference['target_id'],
                points=reference['points_1024x512'], floor=reference.get('floor_xz_h'),
                reference_version=reference.get('reference_version'))


def pack_saved_state(state, image_id, reference_id, by_object, score=None, team_key=None):
    """Keep exact saved coordinates and ledgers, checking every observed vote's binding."""
    score = score or {}
    assignments = state.get('assignments', [])
    for assignment in assignments:
        row = by_object[assignment['id']]
        if (row['image_id'], row['condition'], row['reference_id']) != (image_id, 'manual', reference_id):
            raise ValueError('saved-state input binding mismatch: ' + assignment['id'])
        if row['worker_id'] != assignment['worker']:
            raise ValueError('saved-state worker binding mismatch: ' + assignment['id'])
    assignment_ids = {a['id'] for a in assignments}
    for group in state.get('identity_groups', []):
        for member in group.get('members', []):
            row = by_object[member['id']]
            pair = member['pair_index']
            if (member['id'] not in assignment_ids or member['worker'] != row['worker_id']
                    or member['points'] != row['points_1024x512'][2*pair:2*pair+2]):
                raise ValueError('saved-state source geometry mismatch: ' + member['id'])
    candidate = state.get('candidate') or {}
    return dict(k=state['n'], team_key=team_key,
                workers=[a['worker'] for a in assignments], object_ids=[a['id'] for a in assignments],
                points=candidate.get('points'), footprint=candidate.get('footprint'),
                connected=bool(candidate.get('feature_ids') and candidate.get('points')),
                B8L2=score.get('B8L2'), D10=score.get('D10'), IoU3D100=score.get('IoU3D100'),
                components={k:score.get(k) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')},
                minimum_support=state['minimum_support'], identity_groups=state['identity_groups'],
                assignments=assignments, node_consensus=state.get('node_consensus'),
                ring_diagnostics=state.get('ring_diagnostics'), geometry_status=candidate.get('geometry_status'),
                candidate_status=candidate.get('status'), geometry_reason=candidate.get('reason'),
                ring_confirmed=candidate.get('ring_confirmed'), order_status=candidate.get('order_status'),
                score_status=score.get('score_status'), condition='manual', reference_id=reference_id,
                image_id=image_id, snapshot_id=SNAPSHOT)


def support_counts(rows):
    """Inventory counts are distinct identities, never sums of overlapping display rows."""
    return dict(records=len(rows), images=len({r['image_id'] for r in rows}),
                workers=len({r['worker_id'] for r in rows}),
                buildings=len({r['building_id'] for r in rows}),
                reference_bindings=len({(r['image_id'],r['reference_id']) for r in rows}),
                quality_records=sum(bool(r['quality_usable']) for r in rows),
                independent_vote_records=sum(bool(r['independent_vote_eligible']) for r in rows))


def build_support_payload(evidence):
    matrix = []
    grouped = defaultdict(list)
    for row in evidence:
        grouped[row['image_id'],row['condition'],row['reference_id']].append(row)
    for (image_id, condition, reference_id), rows in sorted(grouped.items()):
        voters = sorted({r['worker_id'] for r in rows if r['independent_vote_eligible']})
        matrix.append(dict(image_id=image_id, image_code=rows[0]['image_code'],
            building_id=rows[0]['building_id'], condition=condition, reference_id=reference_id,
            reference_version=rows[0]['reference_version'], records=len(rows),
            worker_count=len({r['worker_id'] for r in rows}), workers=sorted({r['worker_id'] for r in rows}),
            retained_records=sum(r['cleaning_disposition']=='retained' for r in rows),
            quality_records=sum(bool(r['quality_usable']) for r in rows),
            quality_workers=len({r['worker_id'] for r in rows if r['quality_usable']}),
            independent_vote_workers=len(voters), independent_vote_worker_ids=voters,
            is_doorway=any(r['is_doorway'] for r in rows), is_oos=any(r['is_oos'] for r in rows),
            quality_uses=sorted({r['quality_use'] for r in rows}),
            missing_reasons=sorted({reason for r in rows for reason in r['quality_exclusion_reasons']})))
    conditions = [dict(condition=c,**support_counts([r for r in evidence if r['condition']==c]))
                  for c in sorted({r['condition'] for r in evidence})]
    cohorts = []
    for condition in ('manual','semi'):
        for k in (2,4,8,12,16,20,24,30,35):
            rows = [r for r in matrix if r['condition']==condition and not r['is_oos']
                    and not r['is_doorway'] and r['independent_vote_workers']>=k]
            cohorts.append(dict(condition=condition, minimum_people=k,
                images=len({r['image_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}),
                image_reference_bindings=len(rows),
                image_ids=sorted({r['image_id'] for r in rows}),
                description='固定支持图集的库存准入；不重新生成任何人数曲线，也不声称每图拥有同一批人员。'))
    return dict(totals=support_counts(evidence),
        retained=support_counts([r for r in evidence if r['cleaning_disposition']=='retained']),
        non_oos=support_counts([r for r in evidence if not r['is_oos']]),
        by_condition=conditions, matrix=matrix, constant_support_cohorts=cohorts,
        source='research/statistics/v2_evidence_audit_20261019/records.json.gz',
        unit='image × condition × bound reference; repeated answer and team views are not independent samples',
        limitations=['Manual 与 Semi 分开统计；跨条件时，同一人同一图不代表同一研究条件。',
            '同一图可有多个参考绑定；绑定数不是独立房间数。',
            '固定人数曲线须使用固定图集；此处仅给冻结库存支持范围，不补算融合或预测。'])


def pack_research_evidence(evidence, resources):
    """Expose frozen method evidence and selected real saved paths, without recomputation."""
    by_object = {r['object_id']:r for r in evidence}
    quality_dir = ROOT/'research/quality/v2_structure_quality_interpretation_20261020'
    composition = ROOT/'research/workers/personnel_composition_followup_20261019'
    mechanism = ROOT/'research/fusion/fusion_change_mechanisms_20261020'
    structure = MULTIVIEW/'structure_transfer'
    findings = read(quality_dir/'FINDINGS.json')
    structure_cases = read(composition/'STRUCTURE_CASES.json')
    composition_teams = read(composition/'TEAMS.json.gz')
    quality_cases = []
    titles = {'S1':'删去参考凹口：结构损失', 'S2':'补回参考凹口：局部收益有限',
              'S3':'去掉参考外深凹槽：节点减少但质量改善'}
    for case in structure_cases['cases']:
        answers = []
        first = composition_teams[case['teams']['A']['key']]
        matching = [r for r in evidence if r['image_id']==first['image_id']
                    and r['condition']==first['condition'] and r['reference_id']==case['reference_id']]
        if not matching:
            raise ValueError('structure quality case reference is missing: ' + case['case'])
        for arm, saved in case['teams'].items():
            team = composition_teams[saved['key']]
            if (team['image_id'],team['condition'],team['reference_id']) != (
                    first['image_id'],first['condition'],case['reference_id']):
                raise ValueError('structure quality team binding mismatch')
            for oid in team['member_object_ids']:
                r = by_object[oid]
                if (r['image_id'],r['condition'],r['reference_id']) != (
                        team['image_id'],team['condition'],team['reference_id']):
                    raise ValueError('structure quality member binding mismatch: ' + oid)
            answers.append(dict(label=arm,team_key=saved['key'],workers=team['member_workers'],
                object_ids=team['member_object_ids'], points=team['geometry']['points'],
                footprint=team['geometry']['footprint'], connected=team.get('connection_available',False),
                ring_confirmed=team['geometry'].get('ring_confirmed',False),
                geometry_status=team['geometry'].get('geometry_status'),
                geometry_reason=team['geometry'].get('reason'),
                **{k:team.get(k) for k in ('B8L2','D10','IoU3D100','nodes','score_status',
                                         'ref_node_recall_9','ref_edge_recall_9','order_status')},
                components={k:team.get(k) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')}))
        quality_cases.append(dict(id=case['case'], title=titles[case['case']],
            summary=titles[case['case']], image_id=first['image_id'], image_code=first['image'],
            condition=first['condition'], reference_id=case['reference_id'], snapshot_id=SNAPSHOT,
            reference=reference_display(matching[0]['reference_evidence']), answers=answers,
            event=case['event'], source=(composition/'STRUCTURE_CASES.json').relative_to(ROOT).as_posix(),
            score_source=(composition/'TEAMS.json.gz').relative_to(ROOT).as_posix(),
            limitations=['保存团队的多因素对照；不是只改变结构的单因素实验。',
                         'S1与S2是同一张图；单向参考覆盖率不识别所有额外错误结构。']))
    spotlight = [by_object[oid] for oid in findings['spotlight']]
    if len({(r['image_id'],r['condition'],r['reference_id']) for r in spotlight}) != 1:
        raise ValueError('quality spotlight binding mismatch')
    first = spotlight[0]
    quality_cases.append(dict(id='YQ24',title='同图相近3D代理，方向分项明显不同',
        summary='两份六角Manual，同图同参考；3D代理接近不限定B8L2接近。',
        image_id=first['image_id'],image_code=first['image_code'],condition=first['condition'],
        reference_id=first['reference_id'],snapshot_id=SNAPSHOT,
        reference=reference_display(first['reference_evidence']),
        answers=[dict(object_id=r['object_id'],worker_id=r['worker_id'],label=r['worker_id'],
            workers=[r['worker_id']],points=r['points_1024x512'],nodes=r['point_count']//2,
            connected=bool(r['points_1024x512']),ring_confirmed=r['ring_confirmed'],
            order_status=r['order_status'],geometry_status=r['geometry_status'],
            quality_usable=r['quality_usable'],B8L2=r['B8L2'],D10=r['D10'],IoU3D100=r['IoU3D100'],
            components={k:r['measurements']['same_reference_measurements'].get(k)
                        for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')},
            saved_direction_zero_B8L2=findings['spotlight'][r['object_id']]['B8L2_direction_zero'])
            for r in spotlight],source=(quality_dir/'FINDINGS.json').relative_to(ROOT).as_posix(),
        limitations=['方向置零值是已经保存的归因控制，不是新评分。',
                     '局部墙面语义尚未裁定；不能据此自动认定过罚或修改权重。']))

    states, teams = read(mechanism/'STATES.json.gz'), read(mechanism/'TEAMS.json.gz')
    design = read(mechanism/'DESIGN.json')
    q9_events = sorted([e for e in design['path_events'] if e['image']=='q9vSo1VnCiC-30'],key=lambda e:e['n'])
    if not q9_events or len({e['n'] for e in q9_events}) != len(q9_events):
        raise ValueError('q9 path missing or ambiguous')
    first = q9_events[0]
    nodes = [pack_saved_state(states[e['B_team_key']],e['image_id'],e['reference_id'],by_object,
                             teams[e['B_team_key']],e['B_team_key']) for e in q9_events]
    if [n['k'] for n in nodes] != list(range(nodes[0]['k'],nodes[-1]['k']+1)):
        raise ValueError('q9 integer path has a gap')
    fusion_cases = [dict(id='Q9_REGROUP',title='q9-30：增人重组、失选与连接变化',
        image_id=first['image_id'],image_code=first['image'],condition='manual',
        reference_id=first['reference_id'],snapshot_id=SNAPSHOT,
        reference=reference_display(teams[first['B_team_key']]['reference']),
        summary='固定B臂真实整数路径；16→17人时旧观察重新分组，不能只用门槛升高解释。',
        nodes=nodes,before=next(n for n in nodes if n['k']==16),after=next(n for n in nodes if n['k']==17),
        transitions=[r for r in frame_records(mechanism/'NESTED_STEPS.csv')
                     if r['image']=='q9vSo1VnCiC-30' and r['arm']=='B'],
        saved_identity_control=read(mechanism/'FROZEN_IDENTITY_CONTROL.json'),
        source=(mechanism/'STATES.json.gz').relative_to(ROOT).as_posix(),
        score_source=(mechanism/'TEAMS.json.gz').relative_to(ROOT).as_posix(),
        limitations=['仅一条既有选择路径，不能当总体平均或最优进入顺序。',
                     '身份组是算法对应结果；不是全部已确认的实体墙角。',
                     '保留原保存候选与未确认环序；不生成正式标签。'])]
    group_rows = frame_records(MULTIVIEW/'group_coverage.csv')
    group_names = {r['group_id']:r['source_codes'] for r in group_rows}
    focus = frame_records(structure/'focus_process.csv')
    for saved in read(structure/'case_states.json'):
        if saved['group_id'] not in ('MV0001','MV0003'):
            continue
        ref_id = saved['reference']['target_id']
        packed = [pack_saved_state(saved[key],saved['image_id'],ref_id,by_object,
                  dict(B8L2=saved['quality_'+key]), team_key=None) for key in ('before','after')]
        label = 'G046' if saved['group_id']=='MV0001' else 'G057'
        fusion_cases.append(dict(id=label+'_'+saved['image'],title=label+' · '+saved['image'],
            image_id=saved['image_id'],image_code=saved['image'],group_id=saved['group_id'],
            group_source_codes=group_names.get(saved['group_id']),condition='manual',reference_id=ref_id,
            snapshot_id=SNAPSHOT,reference=reference_display(saved['reference']),
            summary=('必要转折的少数支持与低平台' if label=='G046' else '固定共同人员的8→9人门槛与结构变化'),
            nodes=packed,before=packed[0],after=packed[1],
            aggregate_curve=[r for r in focus if r['group_id']==saved['group_id'] and r['image']==saved['image']],
            source=(structure/'case_states.json').relative_to(ROOT).as_posix(),
            limitations=['几何是第一条已存顺序的最后一步；曲线是全部保存路径平均，二者不可互换。',
                         '图间节点编号没有实体对应；本轮不推导跨视角墙角身份。']))
    for case in fusion_cases:
        case['stages'] = [dict(key=key,label=label,description=description,available=True)
            for key,label,description in (
                ('assignments','原答与对应','逐作答ID、人员及来源点对到身份组的保存映射'),
                ('identity_groups','身份组与支持','组内完整观察、票数、位置与选中状态'),
                ('node_consensus','全队门槛','沿用保存的minimum_support；不现场重投票'),
                ('ring_diagnostics','连接账本','直接边与投影边支持、候选环及未确认状态'),
                ('candidate','保存几何与分数','输出候选和冻结参考评分；失败与缺失原样保留'))]

    context = read(ROOT/'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz')
    difficulty = {r['image_id']:r for r in context['difficulty_records']}
    doorway_cases = []
    for image_id in sorted({r['image_id'] for r in evidence if r['is_doorway']}):
        rows = [r for r in evidence if r['image_id']==image_id]
        d = difficulty[image_id]
        doorway_cases.append(dict(image_id=image_id,image_code=d['image'],title=d['image'],
            conditions=sorted({r['condition'] for r in rows}),
            condition='manual' if any(r['condition']=='manual' for r in rows) else rows[0]['condition'],
            is_oos=any(r['is_oos'] for r in rows),
            reference_ids=sorted({r['reference_id'] for r in rows}),
            observation_status='unknown',optical_center_position_status='unverified',
            reason='现有门洞标签不包含相机拍摄点位相对封闭截面的严格位置证据；不自动判断单室表示不兼容。',
            evidence=dict(doorway_status=d['doorway_status'],scene=d['scene'],oos_subtype=d['oos_subtype'],
                existing_notes=[d.get('old_visual_evidence'),d.get('applicability_note')],
                existing_target_geometry=(d.get('selected') or {}).get('features',{}).get('geometry_status')),
            counts=support_counts(rows),source='research/workers/pro_personnel_v2_20261019/analysis_context.json.gz',
            review_scope='研究观察状态；不修改原门洞/OOS、质量资格或目标参考。'))
    inputs = [quality_dir/'FINDINGS.json',composition/'STRUCTURE_CASES.json',composition/'TEAMS.json.gz',
              mechanism/'STATES.json.gz',mechanism/'TEAMS.json.gz',mechanism/'DESIGN.json',
              mechanism/'NESTED_STEPS.csv',mechanism/'FROZEN_IDENTITY_CONTROL.json',
              structure/'case_states.json',structure/'focus_process.csv',MULTIVIEW/'group_coverage.csv',
              EVIDENCE/'records.json.gz',ROOT/'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz']
    payload = dict(schema='research_workbench_method_evidence_v1',snapshot_id=SNAPSHOT,data_release='v2',
        failure_summary=resources.get('fusion_failure_summary'),
        display_revision='method_evidence_20261020_r1',sources=[source_entry(p) for p in inputs],
        quality=dict(cases=quality_cases,saved_sensitivity_controls=findings['control'],
            pair_support={k:v for k,v in findings.items() if k not in ('spotlight','control','fusion','source')},
            component_notes=['五分项沿用冻结数值和单位；B8L2不是五个可相加扣分条。',
                             'D10是平行敏感性口径；分数增加不意味着几何改善。',
                             'IoU3D100是平均高度棱柱代理；不是实测连续实体体积IoU。']),
        fusion=dict(cases=fusion_cases,packed_integer_nodes=len(nodes),
            limitations=['仅打包可追溯精选状态，不声称全部124924前缀已接入。']),
        doorway=dict(cases=doorway_cases,total_images=len(doorway_cases),
            non_oos_images=sum(not c['is_oos'] for c in doorway_cases),limitations=[
            'Manhattan方向、单室范围、拍摄点位是否严格位于目标内部、星形性及单层高度表示分别判断。',
            '仅见两侧房间或门框居中不足以证明相机拍摄点位在边界；须位姿、平面图或3D证据。']),
        support=build_support_payload(evidence),
        method_boundaries=dict(no_rescoring=True,no_refitting=True,no_fusion=True,no_new_human_judgment=True,
            manual_semi_separate=True,N1_applied=False,
            geometric_scope='Frozen single-room paired top/bottom panorama layout; scene/target/representation uncertainty remains separate.',
            fusion_policy='Saved gap=7.5, full-team MV50 including even half-votes, equal-person coordinate medians and projected source-ring policy; no GT-guided fusion.'))
    write(PAGE/'v2-resources/research_evidence.json',payload)
    resources.update(research_evidence='research_evidence.json',display_revision='method_evidence_20261020_r1')
    write(PAGE/'v2-resources/index.json',resources)
    return payload


def pack_personnel_results(evidence, resources):
    """消费已归档画像/组合接口；不读取下载目录，也不运行研究引擎。"""
    source = ROOT/'research/workers/personnel_profiles_composition_20261020'
    manifest_path = source/'INTEGRATION.json'
    if not manifest_path.is_file():
        raise FileNotFoundError('personnel profiles/composition integration is not archived')
    manifest = read(manifest_path)
    if (manifest['schema'] != 'personnel_profiles_composition_integration_v1'
            or manifest['kind'] != 'profiles_and_composition_not_personnel_classification'):
        raise ValueError('personnel research interface drift')
    declared = {}
    for spec in manifest['tables']:
        frame = pd.read_csv(source/spec['path'], encoding='utf-8-sig')
        if list(frame.columns) != spec['columns'] or len(frame) != spec['rows']:
            raise ValueError('personnel display table drift: ' + spec['id'])
        declared[spec['id']] = frame
    # Original research tables retain separate difficulty, time and review denominators.
    table_sources = dict(profiles='profiles/worker_profiles.csv',
        quality='quality/composition_effects.csv', quality_labor='quality/new_only_n7_labor_summary.csv', growth='quality/growth_common_plot_data.csv',
        speed='speed/main_summary.csv', common_domains='speed/speed_n5_common_target_domains.csv')
    tables = {key: frame_records(source/manifest['source_tables']/path)
              for key, path in table_sources.items()}
    keys = manifest['profile_key']
    expected = {tuple(r[k] for k in keys) for r in declared['profiles'].to_dict('records')}
    actual = [tuple(r[k] for k in keys) for r in tables['profiles']]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('personnel profile source keys differ from curated interface')
    by_object = {r['object_id']: r for r in evidence}
    cases = [read(source/path) for path in manifest['cases']]
    for case in cases:
        records = {r['object_id']: r for r in case['records']}
        for oid, record in records.items():
            current = by_object.get(oid)
            if (not current or current['image_id'] != case['meta']['image_id']
                    or current['condition'] != case['meta']['condition']
                    or current['worker_id'] != record['worker_id']
                    or current['reference_id'] != case['reference']['target_id']
                    or current['points_1024x512'] != record['points']):
                raise ValueError('personnel case binding mismatch: ' + oid)
        for panel in case['panels']:
            if set(panel['object_ids']) != set(panel['score']['member_object_ids']):
                raise ValueError('personnel case team membership mismatch')
            if (not set(panel['object_ids']) <= records.keys()
                    or len(panel['object_ids']) != panel['state']['n']):
                raise ValueError('personnel case missing team records')
    payload = dict(schema='personnel_results_display_v1', snapshot_id=SNAPSHOT,
        classification_status=manifest['classification_status'],
        source=(source/'FIELD_CONTRACT.md').relative_to(ROOT).as_posix(),
        integration=manifest_path.relative_to(ROOT).as_posix(),
        tables_provenance={k:(source/manifest['source_tables']/v).relative_to(ROOT).as_posix()
                           for k,v in table_sources.items()}, cases=cases, **tables)
    write(PAGE/'v2-resources/personnel_results.json', payload)
    resources.update(personnel_results='personnel_results.json')
    write(PAGE/'v2-resources/index.json', resources)
    return payload


def pack_case_story(resources):
    """只搬运已保存端点，按对象身份绑定当前离线原答。"""
    image_index = {image['image_code']: image for image in resources['images']}
    details = {}
    cases = {}

    def append(case_id, image, label, state, score, source):
        candidate = state['candidate']
        assignments = state['assignments']
        if image not in details:
            details[image] = read(PAGE / 'v2-resources' / image_index[image]['detail'])
        answers = {answer['object_id']: answer for answer in details[image]['annotations']}
        if (not candidate.get('points') or not candidate.get('footprint')
                or any(a['id'] not in answers or answers[a['id']]['worker_id'] != a['worker'] for a in assignments)
                or score.get('image') != image):
            raise ValueError('case story geometry/identity drift: ' + case_id + ' ' + image + ' ' + label)
        cases.setdefault(case_id, []).append(dict(image=image, label=label,
            team_key=score['team_key'], reference_id=score['reference_id'],
            members=[dict(worker_id=a['worker'], object_id=a['id']) for a in assignments],
            points=candidate['points'], footprint=candidate['footprint'],
            order_status=candidate.get('order_status'), ring_confirmed=candidate.get('ring_confirmed'),
            B8L2=float(score['B8L2']) if score.get('B8L2') not in ('', None) else None,
            D10=float(score['D10']) if score.get('D10') not in ('', None) else None,
            score_status=score.get('score_status'), source=source))

    for case_id, folder in [('g130', SAME_ROOM_REBUILT / 'engine/first_complete_event'),
                            ('g172', SAME_ROOM_REBUILT / 'cases/structure_mechanism')]:
        with gzip.open(folder / 'STRICT_ABC_EVENT.csv.gz', 'rt', encoding='utf-8-sig', newline='') as stream:
            design = next(csv.DictReader(stream))
        if case_id == 'g130':
            state_files = sorted((folder / 'native/parts').rglob('*.geometry_state.jsonl.gz'))
            score_path = folder / 'CASE_SIX_ENDPOINTS_READABLE.csv'
        else:
            state_files = [folder / 'SIX_TEAM_NATIVE_GEOMETRY.jsonl.gz']
            score_path = folder / 'SIX_TEAM_NATIVE_SCALARS.csv.gz'
        states = {}
        for path in state_files:
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                for line in stream:
                    item = json.loads(line)
                    if item['team_key'] in states:
                        raise ValueError('duplicate saved case team: ' + item['team_key'])
                    states[item['team_key']] = item
        opener = gzip.open if score_path.suffix == '.gz' else open
        with opener(score_path, 'rt', encoding='utf-8-sig', newline='') as stream:
            scores = {row['team_key']: row for row in csv.DictReader(stream)}
        for view in 'ab':
            image = design['image_' + view]
            for arm in 'ABC':
                key = design[f'team_key_{arm}_{view}']
                item, score = states[key], scores[key]
                if item['image'] != image or (score.get('reference_id') and item['reference_id'] != score['reference_id']):
                    raise ValueError('saved case reference drift: ' + key)
                score['reference_id'] = item['reference_id']
                append(case_id, image, arm, item['full_state'], score,
                       score_path.relative_to(ROOT).as_posix())
        if len(cases[case_id]) != 6:
            raise ValueError('incomplete saved ABC case: ' + case_id)

    for case_id, image, selected_k in [('uw12', 'UwV83HsGsw3-12', (3, 4, 5, 6)),
                                       ('b633', 'B6ByNegPMKs-33', (10, 20))]:
        folder = POPULATION_CASES / image
        packed = read(folder / 'CASE_GEOMETRY.json.gz')
        with (folder / 'PATH_SCALARS.csv').open(encoding='utf-8-sig', newline='') as stream:
            scores = {int(row['k']): row for row in csv.DictReader(stream)
                      if row['path_id'] == packed['case']['path_id']}
        for k in selected_k:
            score = scores[k]
            if score['image'] != image:
                raise ValueError('saved population case image drift: ' + image)
            append(case_id, image, f'n={k}', packed['states'][str(k)], score,
                   (folder / 'PATH_SCALARS.csv').relative_to(ROOT).as_posix())
    doorway = read(DOORWAY_CASE)
    image = doorway['image']
    if doorway['schema'] != 'doorway_saved_full_pool_case_v1' or image != '7y3sRwLe3Va-06':
        raise ValueError('unexpected doorway case source')
    detail = read(PAGE / 'v2-resources' / image_index[image]['detail'])
    answers = {answer['object_id']: answer for answer in detail['annotations']}
    people = {answer['worker_id']: answer['object_id'] for answer in doorway['annotations']}
    if (len(people) != 32 or
            doorway['reference']['target_id'] not in {ref['target_id'] for ref in detail['references']} or
            any(a['object_id'] not in answers or answers[a['object_id']]['worker_id'] != a['worker_id']
                or answers[a['object_id']]['points'] != a['points'] for a in doorway['annotations'])):
        raise ValueError('doorway case identity/reference drift')
    for endpoint in doorway['endpoints']:
        geometry = endpoint['geometry']
        has_geometry = geometry['points'] is not None and geometry['footprint'] is not None
        has_score = endpoint['metrics']['B8L2'] is not None and endpoint['metrics']['D10'] is not None
        any_main_score = any(endpoint['metrics'][key] is not None for key in ('B8L2', 'D10', 'IoU3D100'))
        if (len(endpoint['members']) != endpoint['k'] or len(set(endpoint['members'])) != endpoint['k']
                or any(worker not in people for worker in endpoint['members'])
                or endpoint['score_status'] not in ('complete_conditional', 'no_connection', 'below_four')
                or (endpoint['score_status'] == 'complete_conditional') != endpoint['complete_evaluable']
                or (endpoint['score_status'] == 'complete_conditional' and not (has_geometry and has_score))
                or (endpoint['score_status'] == 'no_connection' and
                    (geometry['points'] is not None or geometry['footprint'] is not None or any_main_score))
                or (endpoint['score_status'] == 'below_four' and
                    (endpoint['nodes'] != 3 or not has_geometry or any_main_score))):
            raise ValueError('doorway saved endpoint drift: ' + str(endpoint['k']))
        cases.setdefault('doorway', []).append(dict(image=image, label=f"n={endpoint['k']}",
            team_key=endpoint['team_key'], reference_id=doorway['reference']['target_id'],
            members=[dict(worker_id=worker, object_id=people[worker]) for worker in endpoint['members']],
            points=geometry['points'], footprint=geometry['footprint'],
            order_status=geometry['order_status'], ring_confirmed=geometry['ring_confirmed'],
            B8L2=endpoint['metrics']['B8L2'], D10=endpoint['metrics']['D10'],
            IoU3D100=endpoint['metrics']['IoU3D100'], score_status=endpoint['score_status'],
            nodes=endpoint['nodes'], minimum_support=endpoint['minimum_support'],
            identity_groups_n=endpoint['identity_groups_n'], unselected_groups_n=endpoint['unselected_groups_n'],
            selected_node_supports=endpoint['selected_node_supports'], reason=geometry['reason'],
            source=DOORWAY_CASE.relative_to(ROOT).as_posix()))
    if [team['label'] for team in cases['doorway']] != ['n=3', 'n=10', 'n=20', 'n=32']:
        raise ValueError('incomplete doorway path')
    write(PAGE / 'v2-resources/case_story.json', dict(schema='research_case_story_saved_v1',
          data_release='v2', snapshot_id=SNAPSHOT, cases=cases))
    return {key: len(value) for key, value in cases.items()}


def pack_method_supplements(resources):
    """只搬运已验收结果，并核对展示使用的精确对象与参考。"""
    def rows(folder, name):
        path = folder / name
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    personnel = {name: rows(D10_SENSITIVITY, name + ('.csv.gz' if name in
        ('WORKER_RANK_AND_LABELS', 'SELECTED_TEAM_CROSS_EVALUATION') else '.csv'))
        for name in ('PARTITION_COMPARISON', 'WORKER_RANK_AND_LABELS',
                     'SELECTED_TEAM_CROSS_EVALUATION', 'COMPOSITION_COMMON_COMPARISON',
                     'COMPOSITION_COMMON_PANEL_SUMMARY', 'STRUCTURE_HIGHQ_ROLE_SUMMARY',
                     'ABC_COMMON_PHYSICAL_SUMMARY', 'ABC_LEGALITY_SUMMARY')}
    constant = [r for r in personnel['COMPOSITION_COMMON_PANEL_SUMMARY']
                if r['panel_id'] == 'X7HyMhZNoso-05__semi__5212c0d241__v2__n16']
    if len(constant) != 8 or any(r['B8L2_eta2'] or r['D10_eta2'] for r in constant):
        raise ValueError('constant Semi panel eta2 must remain undefined')

    fusion = {name: rows(FUSION_COMMON, name + '.csv') for name in
        ('TEAM_REGISTRATION', 'METHOD_ENDPOINTS', 'COMMON_TEAM_METRICS',
         'COMMON_SCENE_SUMMARY', 'THREE_METHOD_COMMON_FLOOR',
         'THREE_METHOD_FLOOR_SUMMARY', 'ALL_ATTEMPT_STATUS')}
    fusion['METHOD_GEOMETRY'] = read(FUSION_COMMON / 'METHOD_GEOMETRY.json')
    image_index = {image['image_code']: image for image in resources['images']}
    detail_cache = {}
    def detail(code):
        if code not in detail_cache:
            detail_cache[code] = read(PAGE / 'v2-resources' / image_index[code]['detail'])
        return detail_cache[code]

    if len(fusion['TEAM_REGISTRATION']) != 138 or len(fusion['METHOD_ENDPOINTS']) != 414 or len(fusion['METHOD_GEOMETRY']) != 414:
        raise ValueError('fusion common panel coverage drift')
    for team in fusion['TEAM_REGISTRATION']:
        image = detail(team['image'])
        answers = {a['object_id']: a for a in image['annotations']}
        member_ids = team['member_object_ids'].split('|')
        if (len(member_ids) != int(team['n']) or
                team['reference_id'] not in {r['target_id'] for r in image['references']} or
                any(oid not in answers for oid in member_ids) or
                {answers[oid]['worker_id'] for oid in member_ids} != set(team['member_workers'].split('|'))):
            raise ValueError('fusion team object/reference drift: ' + team['request_id'])
    endpoint_keys = {(e['team_key'], e['method']) for e in fusion['METHOD_ENDPOINTS']}
    if endpoint_keys != {(g['team_key'], g['method']) for g in fusion['METHOD_GEOMETRY']}:
        raise ValueError('fusion endpoint/geometry drift')

    quality = dict(pairs=rows(QUALITY_VALIDATION, 'ANSWER_METRIC_COMPARISON.csv'),
                   directions=rows(QUALITY_VALIDATION, 'METRIC_DIRECTION_SUMMARY.csv'),
                   notes=read(QUALITY_VALIDATION / 'ASSISTANT_VISUAL_NOTES.json')['cases'],
                   controls={name: rows(QUALITY_VALIDATION.parent, name + '.csv') for name in
                             ('HEIGHT_CONTROL_METRICS', 'BOTTOM_POINT_CONTROL_METRICS',
                              'EXPOSED_STRUCTURE_AND_NEAR_SCORE_METRICS')})
    if len(quality['pairs']) != 25 or len(quality['notes']) != 25:
        raise ValueError('quality human review coverage drift')
    for pair in quality['pairs']:
        image = detail(pair['image'])
        if (pair['reference_id'] not in {r['target_id'] for r in image['references']} or
                any(pair[side + '_object_id'] not in {a['object_id'] for a in image['annotations']}
                    for side in ('left', 'right'))):
            raise ValueError('quality review identity/reference drift: ' + pair['review_id'])
    payload = dict(schema='method_supplements_display_20261024_v1', data_release='v2',
                   snapshot_id=SNAPSHOT, personnel=personnel, fusion=fusion, quality=quality)
    write(PAGE / 'v2-resources/method_supplements.json', payload)
    resources['method_supplements'] = 'method_supplements.json'
    write(PAGE / 'v2-resources/index.json', resources)
    return {key: len(value) for key, value in (('fusion_teams', fusion['TEAM_REGISTRATION']),
                                                ('quality_pairs', quality['pairs']))}


def build():
    source_tables = read(STATS / 'tables.json.gz')['tables']
    tables = {k:v for k,v in source_tables.items() if k!='quality__shared_records'}
    evidence = read(EVIDENCE / 'records.json.gz')['records']
    # Heavy provenance and all coordinate stages remain in per-image details and the audit gzip.
    detail_fields = ('time_evidence','binding_evidence','coordinate_evidence','scope_evidence','semi_evidence',
                     'exclusion_attribution','review_evidence','comments','image_comments')
    light = []
    for r in evidence:
        row = {k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        row.update(rescore_target_id=r['reference_id'], calculation_status=r['calculation_class'],
                   quality_exclusion_reasons=r['quality_exclusion_reasons'],
                   IoU3D100=r['IoU3D100'] if r['quality_usable'] else None, diagnostic_IoU3D100=r['IoU3D100'])
        row.update({k:(r['measurements'].get('same_reference_measurements') or {}).get(k)
                    for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')})
        row.update(scope_response=r['scope_evidence']['response'], scope_opportunity=r['scope_evidence']['judgement_opportunity'],
                   scope_correct=r['scope_evidence']['correct'], time_source=r['time_evidence']['source_kind'])
        light.append(row)
    tables['quality__shared_records'] = light
    for filename, table_id in [('profiles','person_profiles_and_evidence'),('reliability','reliability'),
                               ('difficulty_preferences','difficulty_preferences')]:
        tables['workers__'+table_id]=source_tables['statistics__personnel_'+filename]
    scope, semi, exclusions = [], [], []
    for row in evidence:
        identity={k:row[k] for k in ('object_id','image_id','image_code','worker_id','condition','origin','reference_id','quality_usable')}
        scope.append(dict(identity, **{k:v for k,v in row['scope_evidence'].items() if not isinstance(v,(dict,list))}))
        exclusions.append(dict(identity,**{k:v for k,v in row['exclusion_attribution'].items() if not isinstance(v,(dict,list))}))
        if row['condition']=='semi':
            s=row['semi_evidence']
            entry=dict(identity,**{k:v for k,v in s.items() if not isinstance(v,(dict,list))})
            entry.update({f'initial_{k}':v for k,v in (s.get('current_initial_scores') or {}).items()})
            entry.update({f'worker_attributable_gain_{k}':v for k,v in (s.get('current_worker_attributable_gain') or {}).items()})
            semi.append(entry)
    tables.update(workers__scope_opportunities=scope,workers__semi_initialization_scores=semi,workers__exclusion_evidence=exclusions)
    tables.update(load_same_room_prediction(SAME_ROOM))
    extra_manifest = read(EXTRA)
    extra, extra_provenance = load_declared_tables(extra_manifest)
    multiview = load_contract_tables(MULTIVIEW, 'same_room_multiview__', MULTIVIEW_TABLES)
    tables.update(multiview)
    tables.update(extra)
    taxonomy_interface = read(TAXONOMY/'DISPLAY_INTERFACE.json')
    if (taxonomy_interface['schema'] != 'personnel_taxonomy_display_v1'
            or taxonomy_interface['data_release'] != 'v2'
            or taxonomy_interface['classification_status'] != 'working_classification_adopted'):
        raise ValueError('personnel taxonomy display interface drift')
    taxonomy, taxonomy_provenance = load_declared_tables(taxonomy_interface)
    for spec in taxonomy_interface['tables']:
        if len(taxonomy[spec['id']]) != spec['rows']:
            raise ValueError('personnel taxonomy row count drift: ' + spec['id'])
    tables.update(taxonomy)
    mechanism_interface = read(MECHANISMS)
    if mechanism_interface['schema'] != 'research_mechanism_display_v1' or mechanism_interface['data_release'] != 'v2':
        raise ValueError('research mechanism display interface drift')
    mechanisms, mechanism_provenance = load_declared_tables(mechanism_interface)
    for spec in mechanism_interface['tables']:
        if len(mechanisms[spec['id']]) != spec['rows']:
            raise ValueError('research mechanism row count drift: ' + spec['id'])
    tables.update(mechanisms)
    review_interface = read(SAME_ROOM_REVIEW)
    if (review_interface['schema'] != 'same_room_review_display_v1'
            or review_interface['data_release'] != 'v2'
            or review_interface['snapshot_id'] != SNAPSHOT):
        raise ValueError('same-room review display interface drift')
    review, review_provenance = load_declared_tables(review_interface)
    for spec in review_interface['tables']:
        if len(review[spec['id']]) != spec['rows']:
            raise ValueError('same-room review row count drift: ' + spec['id'])
    tables.update(review)
    briefing_interface = read(BRIEFING)
    if briefing_interface['schema'] != 'research_briefing_tables_v1' or briefing_interface['data_release'] != 'v2':
        raise ValueError('research briefing display interface drift')
    briefing, briefing_provenance = load_declared_tables(briefing_interface)
    for spec in briefing_interface['tables']:
        if len(briefing[spec['id']]) != spec['rows']:
            raise ValueError('research briefing row count drift: ' + spec['id'])
    tables.update(briefing)
    personnel_interface = read(PERSONNEL_MAIN / 'CONSUMER_INTERFACE.json')
    personnel_figures = read(PERSONNEL_MAIN / 'FIGURE_MANIFEST.json')
    personnel_glossary = read(PERSONNEL_MAIN / 'GLOSSARY.json')
    if (personnel_interface['data_release'] != 'v2'
            or personnel_interface['version'] != personnel_figures['version']
            or len(personnel_interface['groups']) != 6
            or len(personnel_figures['figures']) != 18
            or len(personnel_glossary['terms']) < 68
            or len({term['id'] for term in personnel_glossary['terms']}) != len(personnel_glossary['terms'])):
        raise ValueError('personnel main display interface drift')
    personnel_specs = [dict(id='personnel_main__' + spec['id'], source=spec['path'],
                            columns=spec['columns'], rows=spec['rows'])
                       for spec in personnel_interface['tables']]
    for source_id in ('mixture_example_members', 'mixture_example_fold_roles'):
        spec = next(s for s in personnel_interface['detail_sources'] if s['id'] == source_id)
        frame = pd.read_csv(ROOT / spec['path'], encoding='utf-8-sig')
        personnel_specs.append(dict(id='personnel_main__' + source_id,
                                    source=spec['path'], columns=list(frame.columns), rows=len(frame)))
    personnel, personnel_provenance = load_declared_tables(dict(tables=personnel_specs))
    for spec in personnel_specs:
        if len(personnel[spec['id']]) != spec['rows']:
            raise ValueError('personnel main row count drift: ' + spec['id'])
    tables.update(personnel)
    source_map = dict(extra_provenance)
    source_map.update(taxonomy_provenance)
    source_map.update(mechanism_provenance)
    source_map.update(review_provenance)
    source_map.update(briefing_provenance)
    source_map.update(personnel_provenance)
    source_map.update({f'same_room_multiview__{Path(f).stem}':
                       f'{MULTIVIEW.relative_to(ROOT).as_posix()}/{f}' for f in MULTIVIEW_TABLES})
    metadata = [display_table(PAGE/'v2-data', name, rows,
                              source_map.get(name, f'{STATS.relative_to(ROOT).as_posix()}/tables.json#{name}'))
                for name, rows in tables.items()]
    next(t for t in metadata if t['id']=='quality__shared_records')['path'] = EVIDENCE.relative_to(ROOT).as_posix()+'/records.json.gz'
    for item in metadata:
        if item['id'].startswith('same_room_prediction__'):
            item['path'] = f'{SAME_ROOM.relative_to(ROOT).as_posix()}/{item["id"].split("__")[1]}.csv'
        elif item['id'].startswith('statistics__'):
            item['path'] = f'{STATS.relative_to(ROOT).as_posix()}/tables.json.gz#{item["id"]}'
        elif item['id'].startswith('workers__'):
            source = {'person_profiles_and_evidence':'profiles', 'reliability':'reliability',
                      'difficulty_preferences':'difficulty_preferences'}.get(item['id'].split('__')[1])
            item['path'] = (f'{STATS.relative_to(ROOT).as_posix()}/tables.json.gz#statistics__personnel_{source}'
                            if source else EVIDENCE.relative_to(ROOT).as_posix()+'/records.json.gz')
    for item in metadata:
        if item['id'] in source_map:
            item['path'] = source_map[item['id']]
    coverage = read(STATS/'COVERAGE.json')
    tables['statistics__requirements_coverage']=coverage['requirements']
    metadata.append(display_table(PAGE/'v2-data','statistics__requirements_coverage',coverage['requirements'],
                                  STATS.relative_to(ROOT).as_posix()+'/COVERAGE.json'))
    modules={
        'data':[('作答明细','quality__shared_records'),('图片库存','statistics__image_inventory'),('人员库存','statistics__worker_inventory')],
        'workers':[('探索性Q/T/难度画像','workers__person_profiles_and_evidence'),('难度适应候选','workers__difficulty_preferences'),
                   ('逐人×难度','statistics__worker_difficulty'),('逐人×场景','statistics__worker_scene'),('独立行为证据','workers__reliability')],
        'taxonomy':[('正式工作分类成员','taxonomy__recommended_labels'),('逐人画像与审核机会','taxonomy__person_class_explanations'),
                    ('按来源Q/T','taxonomy__class_qt_auxiliary_by_source'),('楼外结构表达','taxonomy__lobo_expression_summary'),
                    ('楼外难度分层','taxonomy__lobo_expression_by_difficulty'),('Semi尺度补充','taxonomy__semi_adopted_lobo_summary'),
                    ('A2严格匹配','taxonomy__a_q_source_matched_validation'),('B类原答反例','taxonomy__b_raw_answer_validation'),
                    ('A2正反例','taxonomy__a2_case_candidates'),('B类正反例','taxonomy__b_geometry_case_candidates'),
                    ('换类与同类换人','taxonomy__summary'),('配比与成本','taxonomy__exact_ratio_effects'),
                    ('人数路径汇总','taxonomy__nested_path_summary'),('完整人数路径','taxonomy__nested_composition_paths'),
                    ('换类难度分层','taxonomy__manual_difficulty_effects'),('局部机会','taxonomy__local_opportunities_by_class'),
                    ('机制票账','taxonomy__mechanism_panels'),('图例与逐对象成员','taxonomy__figure_members')],
        'mechanisms':[(spec['group'] + ' · ' + spec['id'].split('__')[-1], spec['id'])
                      for spec in mechanism_interface['tables']],
        'quality':[('作答与几何分项','quality__shared_records'),('固定记录指标敏感性','statistics__fixed_record_metric_sensitivity')],
        'fusion':[('独立票人员池支持','statistics__independent_pool_inventory'),('当前原答分歧','statistics__raw_disagreement_summary')],
        'same_room':[(title, 'same_room_prediction__' + name) for title, name in [
                     ('v2预测与人数曲线','prediction_summary'),('逐建筑预测增益','prediction_gains'),
                     ('逐图对描述与资格','pair_descriptive'),('逐人逐次预测','predictions'),
                     ('门洞单列','doorway_separate'),('模型折与不支持原因','fold_models'),
                     ('预测覆盖','prediction_coverage'),('关系准入审计','relation_coverage')]] +
                    [('直接图对','statistics__direct_pair_summary'),('共同人员双侧明细','statistics__direct_pair_people'),
                     ('关系登记','statistics__room_registry'),('关系组成员','statistics__room_memberships'),('加权敏感性','statistics__room_weighting_sensitivity')],
        'time':[('Semi初始化与增益证据','workers__semi_initialization_scores'),('来源与同目标时间','quality__shared_records'),
                ('时间来源覆盖','statistics__time_provenance_coverage'),('scope裁定机会','workers__scope_opportunities')],
        'coverage':[('可计算与用途','statistics__calculation_coverage'),('逐图人数','statistics__image_inventory'),
                    ('逐人库存','statistics__worker_inventory'),('排除归因','workers__exclusion_evidence'),
                    ('重叠限制原因','statistics__exclusion_reason_hits'),('逐项需求覆盖','statistics__requirements_coverage')]
    }
    modules[review_interface['module']['id']] = [
        (title, table_id) for title, table_id in review_interface['module']['tabs']]
    review_missing = [tid for _, tid in review_interface['module']['tabs'] if tid not in tables]
    if review_missing:
        raise ValueError('missing same-room review tables: ' + ', '.join(review_missing))
    for module, tabs in EXTRA_MODULE_TABS.items():
        modules[module].extend(tabs)
    for module, tabs in BRIEFING_MODULE_TABS.items():
        modules.setdefault(module, []).extend(tabs)
    modules={key:[tab for tab in tabs if tab[1] in tables] for key,tabs in modules.items()}
    missing = [tid for tabs in (*EXTRA_MODULE_TABS.values(), *BRIEFING_MODULE_TABS.values())
               for _, tid in tabs if tid not in tables]
    if missing:
        raise ValueError('missing display tables: ' + ', '.join(missing))
    write(PAGE/'v2-data/index.json', dict(snapshot_id=SNAPSHOT, data_release='v2', tables=metadata,module_tabs=modules,
          documents=[dict(path=spec['path'], content=read(ROOT / spec['path']))
                     for spec in review_interface['documents']] + [
                     dict(path='personnel_classification_guide', content=read(ROOT/'research/workers/personnel_classification_guide_20261025/GUIDE.json')),
                     dict(path='current_class_evidence', content=classification_evidence()),
                     dict(path='personnel_main_interface', content=personnel_interface),
                     dict(path='personnel_main_figures', content=personnel_figures),
                     dict(path='personnel_main_glossary', content=personnel_glossary),
                     dict(path='research/statistics/v2_integrated_analysis_20261019/COVERAGE.json',content=coverage),
                     dict(path=SAME_ROOM.relative_to(ROOT).as_posix()+'/CONSUMER_INTERFACE.json',content=read(SAME_ROOM/'CONSUMER_INTERFACE.json')),
                     dict(path='research/statistics/v2_evidence_audit_20261019/COVERAGE.json',content=read(EVIDENCE/'COVERAGE.json'))]))
    summary = pack_resources(light,evidence)
    by_object = {r['object_id']:r for r in evidence}
    resources = read(PAGE/'v2-resources/index.json')
    for item in resources['images']:
        path = PAGE/'v2-resources'/item['detail']
        image = read(path)
        for annotation in image['annotations']:
            row = by_object[annotation['object_id']]
            annotation['evidence'] = {k:row[k] for k in detail_fields}
        write(path,image)
    pack_case_story(resources)
    resources['case_story'] = 'case_story.json'
    write(PAGE/'v2-resources/index.json', resources)
    pack_method_supplements(resources)
    pack_comparisons(evidence, resources)
    pack_research_evidence(evidence, resources)
    pack_personnel_results(evidence, resources)
    sections = [
        dict(id='quality', title='怎样衡量布局质量？', module='method_supplements', tab=2,
             finding='不同指标保留的信息不同：明确偏好的新Manual五题中，B8L2/D10同向5题，均高IoU同向3题。',
             example='25组完整原答、分项、均高棱柱IoU与高度/底点控制一起看；默认展示漏转折案例。',
             support='25对/25图/15楼，一名人工复核者；5题指新Manual明确左右偏好，Semi另1题与这些指标反向。',
             counterexample='这是按指标关系选出的诊断案例，不是随机样本准确率；接近和各有问题/无法判断不强制二分。',
             source='../../../research/quality/quality_independent_validation_20261024/human_review/REPORT_ZH.md', tables=[]),
        dict(id='consensus', title='融合一定胜过完整原答吗？', module='method_supplements', tab=1,
             finding='共同面板中，普通Manual四人队墙线比代表原答平均高7.11分，16人队却低5.54分。',
             example='n4有16/22图提高；n16为8/23图提高。三法底面比较与完整顶部比较分开。',
             support='固定138队全部尝试；普通Manual n4为24尝试/22共同完整可评，n16为23/23；Lee仅底面。',
             counterexample='门洞n16有5/6图提高，仍因一图大幅下降而均差−4.94；均值、图多数、P10 和失败同时报告。',
             source='../../../research/fusion/fusion_common_panel_20261024/README.md', tables=[]),
        dict(id='difficulty', title='图片结构怎样改变标法？', module='conditions', tab=0,
             finding='固定六个参考转折后，短边和几何自遮挡仍与简化表达有关，分别在32/47、36/47人得到支持。',
             example='黑横线为图片等权均值；H是几何自遮挡量，不是高度。短边、自遮挡、家具遮挡分别解释。',
             visual='../../../research/difficulty/difficulty_mechanisms_v2_20261020/fixed6_conditions.png', visual_alt='固定六参考转折的条件比较',
             support='33张固定结构图；逐图范围支持及同人比较均可查。',
             counterexample='困难、门洞或OOS不预设必然不一致；结构复杂度与人工难度也不是同一变量。',
             source='../../../research/difficulty/difficulty_mechanisms_v2_20261020/RESULTS_SYNTHESIS.md', tables=[dict(id='difficulty__person_fixed6_conditions',label='同人固定结构比较')]),
        dict(id='profiles', title='平均分接近的人，表现也一样吗？', module='profiles', tab=0,
             finding='W109/W112同99图均Q为84.322/84.990，但后者每图更慢；困难15图高8.097分，中等18图低6.784分。',
             example='记录耗时比的几何中位数7.669；平均质量、困难优势、P10 和可靠性记录分别看。',
             visual='../../../research/workers/personnel_profiles_composition_20261020/source/mechanisms/figures/profile_W109_W112.png', visual_alt='同图原答与快慢正反例',
             support='99普通Manual图/21楼、相同参考；全体182格画像另查各自有效分母。',
             counterexample='较慢不必普遍更好；Semi确认/报告错误、scope倾向与审核机会不合成统一错误率。',
             source='../../../research/workers/personnel_profiles_composition_20261020/PROFILE_FINDINGS.md', tables=[dict(id='profiles__continuous',label='完整连续画像')]),
        dict(id='classification', title='哪些标法差异值得分组？', module='personnel_main', tab=0,
             finding='困难结构三类用于主解释：ALL为8/39/12人，二类粗层47/12人；都保留3名未知。',
             example='从分类依据和每折角色中心，点选名单中的人，再在同一图查看完整原答。融合响应类回答怎样影响当前共识。',
             support='当前方法及22个楼外范围；ALL描述与排除目标楼的实验名单分开。',
             counterexample='转折多不是正确率；新分类不冒领旧四分类的完整配比、进入策略和同房实验。',
             source='../../../research/workers/personnel_classification_guide_20261025/README.md', tables=[]),
        dict(id='mixture', title='类别配比和具体成员分别影响什么？', module='personnel_main', tab=1,
             finding='旧结构类n20：困难14图的配比格均值Q跨度11.98分、格内四分位距9.97；简单21图为1.71和1.58。',
             example='同时看不同类别人数比例与同配比中换具体成员的波动；七个实例连接真实成员与完整格。',
             support='旧四分类336个有限面板、13,406配比格，每面板固定背景并枚举924队。',
             counterexample='构成与成员波动都存在；格数不是独立实验次数，此处未按新DSTRUCT重编。',
             source='../../../research/workers/personnel_mixture_comparison_20261022/configurations/README.md', tables=[dict(id='personnel_main__MIXTURE_ALL_MANUAL',label='Manual完整配比')]),
        dict(id='exchange', title='同人数、同背景下，换类与同类换人有多大差别？', module='personnel_main', tab=2,
             finding='DSTRUCT K3 n18/m7：同类Q幅度3.438分、跨类6.386分；31/40图及10/10楼跨类更大。',
             example='RFUSE两类和几何＋质量响应三类分别23/29、16/21图跨类更大；方向与幅度分列，保留降质。',
             support='四重点条件及全部71条件；严格ABC需n+2m名不同人员，三块真实成员互斥。',
             counterexample='各条件图片、n/m与选择方向不同，不作无条件排行榜；直接AC没有同类B队。',
             source='../../../research/workers/personnel_classification_guide_20261025/README.md', tables=[]),
        dict(id='population', title='从低人数到30/35和满员，哪些量在改善？', module='personnel_main', tab=4,
             finding='固定157图3→6人Q平均+5.184分，155/157图提高；20→30仍+0.758，125/157图提高。',
             example='困难27图3→6全部升质，但失败6.944%→12.654%；后段Q可近乎不变，换组波动继续下降。',
             support='固定N≥30的157图、N=35的92图及旧N≥20范围分别保留；30→35质量用91共同可评图。',
             counterexample='30→35共同图Q+0.227，全部92图失败0.725%→1.087%；单人是原答基线，两人未计算不计成败，满员SD/V=0是同成员设计事实。',
             source='../../../research/workers/personnel_population_curves_v2_20261023/late_population_20261024/README.md', tables=[]),
        dict(id='same_room', title='同房跨视角，什么能够重复？', module='same_room', tab=0,
             finding='同房均值预测MAE5.081，对照9.303，9/12楼改善；105/123图对人员排序正相关，42/57人相对同行方向多数重复。',
             example='第三层看混合团队：旧结构混合队跨类幅度多1.960分，61/78图对为正；两端响应超过2分时CA同向率73.01%。',
             support='公共水平123直接图对/64图/12楼；个人2,581配对/57人；构成与大块实验各有原标签及支持域。',
             counterexample='扣公共任务与稳定个人水平后的额外相关仅0.031，不否定前两层相似。未知同建筑关系不当作异房。',
             source='../../../research/statistics/research_closeout_20261022/SAME_ROOM_REASSESSMENT_20261024.md', tables=[dict(id='same_room_pro__direct_mean_summary',label='同房均值与支持')]),
        dict(id='doorway', title='增加人数能解决门洞问题吗？', module='case_story', tab=0, case='doorway',
             finding='门洞17图3→6人平均Q+6.072，15图提高；10→20平均−3.066，11图下降，满员仍6/17不可评。',
             example='7y-06保留32份完整原答与真实满员失败；点位、目标范围、门楣和表示限制分别看。',
             support='固定门洞自然人数范围17图；满员27—35人。个别例子不替代全层分母。',
             counterexample='不能因前段改善就称门洞已解决，也不能因满员失败否认早段增人的价值。',
             source='../../../research/workers/personnel_population_curves_v2_20261023/README.md', tables=[]),
        dict(id='oos', title='超出表示标准时，人们怎样表达？', href='oos-review.html',
             finding='OOS28图、1,222份独立统计：斜顶三图80份新Manual均为四角底面；曲线玻璃同房五视角角点数分歧61.8%。',
             example='看已完成统计，再看28图完整原答；构造图解释表示限制，复核填写和导出留在次级入口。',
             support='新Manual804份用于时间/选择，703份/24图按既有资格整理几何；因素允许重叠。',
             counterexample='327/804选择不可标是响应倾向，不是正确率；GT可能受约束近似，正式质量资格始终为0。',
             source='../../../research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/oos_statistics_20261024/README.md', tables=[]),
    ]
    write(PAGE/'v2-data/overview.json',dict(metadata=dict(snapshot_id=SNAPSHOT),sections=sections,personnel_status='人员第1步：DSTRUCT主解释、融合响应及跨条件对照；第3步：同图大块与容量；旧配比、时间、人数和同房结果继续保留。'))
    print(json.dumps(dict(**summary,tables=len(metadata)),ensure_ascii=True))


if __name__ == '__main__':
    build()
