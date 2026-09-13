"""独立核对外部两阶段提案；只写审查结果，不改变选择或派发。"""
import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'analysis_results/two_stage_independent_review_20260913_v1')
    args = parser.parse_args()
    pkg = args.package
    current = read(ROOT/'analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')
    assert current['schema'] == 'candidate_selection_planning_v2'
    ours = {r['image_id']: r for r in current['images']}
    adopted = {k: r for k, r in ours.items() if r['status'] == '确定采用'}
    external = csv_rows(pkg/'results/all_112_recomputed.csv')
    stage = csv_rows(pkg/'results/stage1_proposed_images_43.csv')
    witness = csv_rows(pkg/'results/NOT_FOR_DISPATCH_assignment_witness.csv')
    assert len(external) == len(ours) == 112
    assert {r['image_id'] for r in external} == set(ours)
    assert {r['image_id'] for r in external if r['status'] == '确定采用'} == set(adopted)
    fields = [('difficulty','difficulty'), ('coarse','scene'), ('collection','collection')]
    counts = [('historical','history_manual'), ('historical_raw','history_raw_manual'),
              ('semi','history_semi'), ('planned_target','planned_manual'), ('new_needed','new_needed'),
              ('capacity_shortfall','capacity_shortfall')]
    differences = []
    for r in external:
        o = ours[r['image_id']]
        assert (r['group'], int(r['number'])) == (o['group'], o['number'])
        for ek, ok in fields + counts:
            if ok not in o:
                continue
            v = int(r[ek]) if (ek, ok) in counts else r[ek]
            if v != o[ok]:
                differences.append(dict(group=o['group'], number=o['number'], field=ek,
                                        external=v, current=o[ok], adopted=r['image_id'] in adopted))
        for field in ['manual_workers','semi_workers','clean_workers']:
            assert json.loads(r[field]) == o[field]

    # 回到本仓库原始导出独立检查，不能用外部包自报的“错误0”替代。
    with gzip.open(ROOT/'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz', 'rt', encoding='utf-8') as f:
        canonical = [json.loads(line) for line in f]
    paths = {r['raw_export_path'] for r in canonical}
    raw_index, seen = {}, defaultdict(set)
    versions = 0
    for path in paths:
        tasks = read(ROOT/path)
        for t in tasks:
            iid = Path(unquote(urlparse(t['data']['image']).path)).stem
            for a in t.get('annotations', []):
                worker = a['completed_by']
                worker = int(worker['id'] if isinstance(worker, dict) else worker)
                key = (path, str(t['id']), str(a['id']))
                assert key not in raw_index
                raw_index[key] = (iid, worker, a)
                seen[iid].add(worker)
                versions += 1
    max_difference = 0
    for r in canonical:
        parts = r['raw_annotation_version_id'].split('|')
        iid, worker, a = raw_index[r['raw_export_path'], parts[2], parts[4]]
        assert iid == r['image_id'] and worker == int(r['worker_id']) == int(parts[3])
        points = [[float(p['value']['x'])*10.24, float(p['value']['y'])*5.12]
                  for p in a['result'] if p.get('type') == 'keypointlabels']
        assert len(points) == len(r['raw_points_1024x512'])
        for p, q in zip(points, r['raw_points_1024x512']):
            max_difference = max(max_difference, *(abs(x-y) for x,y in zip(p,q)))
    assert len(canonical) == 2501 and max_difference < 1e-8

    active = set(current['future_workers'])
    assigned = defaultdict(set)
    work = defaultdict(Counter)
    language = {}
    roster = csv_rows(ROOT/'analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_worker_roster.csv')
    languages = {int(r['annotator_id']): r['language'] for r in roster}
    assert len({(int(r['worker_id']), r['image_id']) for r in witness}) == len(witness) == 480
    for r in witness:
        iid, worker = r['image_id'], int(r['worker_id'])
        assert iid in adopted and worker in active
        assert worker in adopted[iid]['clean_workers'] and worker not in seen[iid]
        assert r['difficulty'] == adopted[iid]['difficulty']
        language[worker] = languages[worker]
        assert r['language_group'] == ('英文任务组' if language[worker]=='en' else '中文任务组')
        assigned[iid].add(worker)
        work[worker][r['difficulty']] += 1
    assert set(work) == active
    assert all(sum(work[w].values()) == (30 if language[w]=='en' else 20) for w in work)
    assert len(stage) == len(assigned) == 43
    assert set(assigned) == {r['image_id'] for r in stage}
    below_upper, stage_totals, shared = [], {}, []
    for r in stage:
        o = adopted[r['image_id']]
        target = o['history_manual'] + len(assigned[r['image_id']])
        assert len(assigned[r['image_id']]) == int(r['stage1_new'])
        assert target == int(r['stage1_target']) <= o['planned_manual']
        assert set(json.loads(r['proposed_workers'])) == assigned[r['image_id']]
        if target < o['planned_manual']:
            below_upper.append(dict(group=o['group'],number=o['number'],user_upper=o['planned_manual'],
                                    stage1=target,current_cap=o['current_roster_cap']))
        after = set(o['manual_workers']) | assigned[r['image_id']]
        assert all(sum(languages[w]==lang for w in after & active)>=2 for lang in ['zh','en'])
        if active <= after:
            shared.append([o['group'], o['number']])
        stage_totals[r['image_id']] = target

    groups = defaultdict(list)
    full_shared, depth, pending = [], [], []
    for iid, o in adopted.items():
        after_n = stage_totals.get(iid, o['history_manual'])
        after_people = set(o['manual_workers']) | assigned[iid]
        if active <= after_people:
            full_shared.append([o['group'], o['number']])
        r = dict(group=o['group'], number=o['number'], image_id=iid, difficulty=o['difficulty'],
                 original_manual=o['planned_manual'], phase1_manual=after_n,
                 phase1_new=len(assigned[iid]), remain=o['planned_manual']-after_n)
        groups[o['group']].append(r)
        if o['new_needed']>0 and not assigned[iid]:
            pending.append(r)
    for group, rows in groups.items():
        depth.append(dict(group=group, adopted=len(rows), original_manual_views=sum(r['original_manual']>0 for r in rows),
                          phase1_any_views=sum(r['phase1_manual']>0 for r in rows),
                          phase1_ge3_views=sum(r['phase1_manual']>=3 for r in rows),
                          phase1_ge8_views=sum(r['phase1_manual']>=8 for r in rows),
                          newly_assigned_views=sum(r['phase1_new']>0 for r in rows),
                          new_total=sum(r['phase1_new'] for r in rows)))
    cohort = []
    for lang in ['zh','en']:
        ww = [w for w in work if language[w]==lang]
        c = sum((work[w] for w in ww), Counter())
        hard_iids = {iid for iid, people in assigned.items() if people and adopted[iid]['difficulty']=='困难'}
        cohort.append(dict(language=lang, workers=len(ww), total=sum(c.values()),
                           counts=dict(c), hard_share=c['困难']/sum(c.values()),
                           hard_available_edges=sum(languages[w]==lang for iid in hard_iids for w in adopted[iid]['clean_workers'])))

    manifest = read(pkg/'PACKAGE_MANIFEST.json')
    assert all((pkg/r['path']).is_file() for r in manifest)
    result = dict(schema='two_stage_independent_audit_v1', package=str(pkg), adopted_images=len(adopted),
                  current_totals=current['totals'], transcription_differences=differences,
                  adopted_transcription_differences=[d for d in differences if d['adopted']],
                  raw_audit=dict(files=len(paths), versions=versions, canonical_checked=len(canonical),
                                 max_coordinate_difference=max_difference),
                  witness=dict(rows=len(witness), images=len(stage), existing_response_conflicts=0,
                               groups=len(groups), buildings=len({adopted[i]['building'] for i in assigned})),
                  stage1_manual_total=sum(stage_totals.get(i,o['history_manual']) for i,o in adopted.items()),
                  below_user_upper=below_upper, deferred_positive_gap_images=pending,
                  remaining=sum(o['planned_manual']-stage_totals.get(i,o['history_manual']) for i,o in adopted.items()),
                  group_depth=depth, newly_completed_current19=shared, all_current19_complete_after=full_shared,
                  cohort_workload=cohort,
                  stage1_new_by_building=dict(Counter(adopted[r['image_id']]['building'] for r in witness)),
                  uniform_floor_costs={str(k):sum(max(0,min(k,o['planned_manual'],o['current_roster_cap'])-o['history_manual']) for o in adopted.values()) for k in [6,8]},
                  manifest_paths_present=len(manifest), partial_package_limitations=['缺少完整用户原始JSON；逐项转录字段不作真源', '未发现工作簿生成脚本或独立raw_exposure_assignment_check生成入口'],
                  current_protocol_or_selection_changed=False)
    assert result['stage1_manual_total'] == 383+480
    assert result['remaining'] == 1072-480
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'独立复核数据.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for key in ['transcription_differences','raw_audit','witness','below_user_upper','group_depth','cohort_workload','uniform_floor_costs','stage1_new_by_building','all_current19_complete_after']:
        print(key,json.dumps(result[key],ensure_ascii=False))


if __name__ == '__main__':
    main()
