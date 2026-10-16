"""从已完成参考审计的快照生成B8L2查阅表；不改变资格、参考或评分。"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERSION = 'b8l2_mainline_status_20261016_v1'
METRICS = ['B8L2', 'IoU3D100', 'active_time_seconds', 'target_matched_time_seconds']
FIELDS = ['object_id', 'image_id', 'image_code', 'worker_id', 'condition', 'building_id',
          'difficulty_class', 'analysis_layer', 'pool_source_workers', 'current_quality_eligible',
          'B8L2', 'IoU3D100', 'WQ', 'A10', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter',
          'active_time_seconds', 'target_matched_time_seconds', 'time_status', 'time_source',
          'target_time_interpretation', 'reference_id', 'current_target_id', 'score_version',
          'rescore_status', 'rescore_reference_version', 'difficulty_version', 'doorway_status',
          'oos_subtype', 'scene']


def numeric(value):
    if value is None or value == '':
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('non-finite numeric value')
    return result


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def stats(values):
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                sd=statistics.stdev(values) if len(values) > 1 else None)


def summarize(rows, dimensions):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in dimensions)].append(row)
    output = []
    for keys, members in sorted(groups.items()):
        result = dict(zip(dimensions, keys))
        result.update(n_source_records=len(members),
                      n_source_images=len({r['image_id'] for r in members}),
                      n_source_workers=len({r['worker_id'] for r in members}))
        for metric in METRICS:
            values = [v for r in members if (v := numeric(r.get(metric))) is not None]
            result.update({metric+'_'+k: v for k, v in stats(values).items()})
        scored = [r for r in members if numeric(r.get('B8L2')) is not None]
        result.update(n_quality_missing=len(members)-len(scored),
                      n_scored_images=len({r['image_id'] for r in scored}),
                      n_scored_workers=len({r['worker_id'] for r in scored}),
                      n_quality_target_time_common=sum(numeric(r.get('target_matched_time_seconds'))
                                                       is not None for r in scored))
        images = defaultdict(list)
        for row in scored:
            images[row['image_id']].append(numeric(row['B8L2']))
        result['B8L2_image_equal_mean'] = stats([statistics.mean(v) for v in images.values()])['mean']
        output.append(result)
    return output


def room_pairs(rows, relations):
    lookup = defaultdict(dict)
    for row in rows:
        if numeric(row.get('B8L2')) is not None:
            key = row['image_id'], row['condition']
            assert row['worker_id'] not in lookup[key], 'duplicate scored worker within image/condition'
            lookup[key][row['worker_id']] = numeric(row['B8L2'])
    output, seen = [], set()
    for relation in relations:
        if relation['relation'] != 'confirmed_comparable':
            continue
        a, b = relation['image_a'], relation['image_b']
        assert (a, b) not in seen, 'duplicate direct relation'
        seen.add((a, b))
        for condition in ['manual', 'semi']:
            aa, bb = lookup[a, condition], lookup[b, condition]
            if not aa and not bb:
                continue
            common = sorted(aa.keys() & bb.keys())
            delta = [bb[w]-aa[w] for w in common]
            output.append(dict(image_a=a, image_b=b,
                image_code_a=relation.get('image_code_a', a), image_code_b=relation.get('image_code_b', b),
                condition=condition, relation=relation['relation'], candidate_ids=relation['candidate_ids'],
                n_scored_a=len(aa), n_scored_b=len(bb), n_common_scored_workers=len(common),
                all_a_mean=stats(list(aa.values()))['mean'], all_b_mean=stats(list(bb.values()))['mean'],
                common_a_mean=stats([aa[w] for w in common])['mean'],
                common_b_mean=stats([bb[w] for w in common])['mean'],
                common_worker_delta_mean=stats(delta)['mean'],
                common_worker_absolute_delta_mean=stats([abs(v) for v in delta])['mean'],
                common_worker_ids=';'.join(common)))
    return output


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    assert fields, 'empty table requires explicit schema'
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(source, out, payload):
    contract = json.loads((source/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    raw = read_csv(source/'analysis_records.csv')
    assert len({(r['image_id'], r['condition'], r['worker_id']) for r in raw}) == len(raw)
    rows = [{k: r[k] for k in FIELDS} for r in raw]
    for row in rows:
        for field in METRICS + ['WQ', 'A10', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']:
            row[field] = numeric(row[field])
        row['B8L2_version'] = contract['score_versions']['B8L2']
    scored = [r for r in rows if r['B8L2'] is not None]
    assert all(r['current_quality_eligible'] == 'True' and int(r['pool_source_workers']) >= 3 for r in scored)
    assert all(r['reference_id'] == r['current_target_id'] for r in scored)
    selected_metrics = set(METRICS)
    tables = dict(analysis_records=rows, quality_records=scored,
                  by_worker=summarize(rows, ['condition', 'worker_id']),
                  by_image=summarize(rows, ['condition', 'image_id', 'image_code', 'difficulty_class']),
                  by_worker_difficulty=summarize(rows, ['condition', 'worker_id', 'difficulty_class']),
                  same_room=room_pairs(rows, read_csv(source/'same_room_relations.csv')))
    for table in ['overview', 'by_difficulty', 'by_scene', 'by_building']:
        tables[table] = [r for r in read_csv(source/(table+'.csv')) if r['metric'] in selected_metrics]
    tables['current_images'] = [{k:r[k] for k in ['image_id','image','current_class','target_role',
        'gt_error_excluded','difficulty_analysis_exclusion','full_current_target_geometry_available',
        'doorway_status','oos_subtype','review_disagreement','current_target_id']}
        for r in read_csv(source/'current_images.csv')]
    tables['pending_people'] = read_csv(source/'pending_people.csv')
    tables['remaining_gaps'] = [{k:r[k] for k in ['image_code','worker_id','condition',
        'remaining_reasons','minimal_human_question','object_id','chosen_target_id']}
        for r in read_csv(source/'remaining_gaps.csv')]
    # 对照已审计聚合值，而不是仅检查同一新实现重复运行。
    for prior in tables['overview']:
        if prior['metric'] != 'B8L2':
            continue
        layer, condition = prior['panel'].split('_', 1)
        members = [r for r in raw if r['condition'] == condition and
                   (r['ordinary_difficulty_eligible'] == 'True') == (layer == 'ordinary')]
        values = [v for r in members if (v := numeric(r['B8L2'])) is not None]
        assert len(values) == int(prior['n_valid'])
        if values:
            assert abs(statistics.mean(values)-float(prior['mean'])) < 1e-9
    previous = {r['object_id']:r for r in read_csv(ROOT/'research/statistics/descriptive_statistics_rescored_20261016/quality_records.csv')}
    current = {r['object_id']:r for r in scored}
    common = current.keys() & previous.keys()
    changed = [oid for oid in common if abs(current[oid]['B8L2']-float(previous[oid]['B8L2'])) > 1e-9
               or current[oid]['reference_id'] != previous[oid]['reference_id']]
    checks = dict(version=VERSION, primary_metric='B8L2', score_version=contract['score_versions']['B8L2'],
                  difficulty_version=contract['difficulty_version'],
                  source_snapshot_version=contract['version'], source_rows=len(rows), quality_rows=len(scored),
                  added_ids=sorted(current.keys()-previous.keys()), removed_ids=sorted(previous.keys()-current.keys()),
                  changed_score_or_reference_ids=sorted(changed),
                  changed_difficulty_ids=sorted(oid for oid in common
                      if current[oid]['difficulty_class'] != previous[oid]['difficulty_class']),
                  matched_quality_time_rows=sum(r['target_matched_time_seconds'] is not None for r in scored),
                  source_scoring_checks=json.loads((source/'CHECKS.json').read_text(encoding='utf-8')))
    out.mkdir(parents=True, exist_ok=True)
    for name, records in tables.items():
        write_csv(out/(name+'.csv'), records)
    checks['tables'] = {name:dict(rows=len(records), columns=list(records[0])) for name,records in tables.items()}
    (out/'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    definitions = dict(version=VERSION, score_versions=contract['score_versions'],
        difficulty_version=contract['difficulty_version'],
        primary_metric='B8L2', n_source_records='当前来源池与既有排除合格的记录；不等于有完整评分',
        n_quality_missing='来源记录数减完整B8L2数；不按0分计入',
        B8L2_mean='作答等权均值；不是人员能力', B8L2_image_equal_mean='先逐图均值再图片等权',
        sd='样本标准差；不足2个有效值留空',
        time='秒；active_time_seconds为合格来源采集时间，target_matched_time_seconds另需目标可比；不替代或填0',
        condition='manual、semi、oos分别描述，不混入同一人员平均质量或同房配对',
        same_room='仅confirmed_comparable直接关系；同条件、同worker_id配对，不推导关系传递',
        references='reference_id为实际评分参考；B8L2_version明确算法身份，score_version保留上游原元数据',
        table_fields=checks['tables'])
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(definitions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    payload.parent.mkdir(parents=True,exist_ok=True)
    payload.write_text(json.dumps(dict(tables=tables,checks=checks),ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in checks.items() if k not in ['tables','source_scoring_checks']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.out, args.payload)
