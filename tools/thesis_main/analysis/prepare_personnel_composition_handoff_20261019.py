"""整理类别组合研究的现有输入与支持量；不拟合分类或运行融合。"""
import gzip
import json
import subprocess
from collections import Counter
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_composition_handoff_20261019'
A = 'research/workers/personnel_type_discovery_next_20261019'
W = A + '/work_personnel_typing_A_20261019'
OLD = 'research/workers/pro_personnel_v2_archive_20261019'
V = OLD + '/work_v2_20261019'
EVIDENCE = 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
DIFFICULTY = {'简单': 'easy', '中等': 'medium', '困难': 'hard', '单列': 'separate'}


def read(path):
    path = Path(path)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(raw.decode('utf-8-sig'))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def validate_pool(pool, evidence):
    workers = set()
    for row in pool['records']:
        current = evidence[row['object_id']]
        if row['worker_id'] in workers:
            raise ValueError('duplicate pool worker')
        workers.add(row['worker_id'])
        same = (current['quality_usable'] is True and current['worker_id'] == row['worker_id']
                and current['image_id'] == pool['meta']['image_id']
                and current['reference_id'] == pool['meta']['reference_id']
                and current['points_1024x512'] == row['points']
                and all(abs(current[k] - row[k]) < 1e-10 for k in ('B8L2', 'D10')))
        if not same:
            raise ValueError('frozen pool disagrees with current evidence: ' + row['object_id'])


def class_counts(pairs):
    result, seen = {}, set()
    for worker, label in pairs:
        if worker in seen:
            raise ValueError('duplicate worker label')
        seen.add(worker)
        key = str(label) if pd.notna(label) and str(label).lower() != 'unknown' else 'unknown'
        result.setdefault(key, []).append(worker)
    return result


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        'current_public_input': 'research/statistics/v2_evidence_audit_20261019/INPUTS.json',
        'record_evidence': EVIDENCE,
        'evidence_contract': 'research/statistics/v2_evidence_audit_20261019/field_contract.json',
        'statistics': 'research/statistics/v2_integrated_analysis_20261019/CONSUMER_INTERFACE.json',
        'quality': 'research/quality/quality_workers_v2_20261019/CROSS_MODULE_INPUTS.json',
        'image_reference_context': 'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz',
        'image_release_index': 'research/workers/pro_personnel_v2_20261019/IMAGE_INDEX.csv',
        'frozen_pools': V + '/fusion/INPUT_SNAPSHOT.json.gz',
        'frozen_fusion': V + '/fusion/fusion_engine.py',
        'previous_restore': OLD + '/bootstrap.py',
        'part_a_restore': A + '/bootstrap.py',
        'part_a_requirements': A + '/requirements.txt',
        'portraits_FULL_description_only': W + '/assessment/WORKER_PORTRAITS_60.csv',
        'selected_and_baseline_labels': W + '/assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',
        'all_forward_fold_candidates': W + '/forward/candidate_classes_by_fold.csv.gz',
        'all_forward_fold_candidates_D10': W + '/forward/candidate_classes_by_fold_D10.csv.gz',
        'fold_features': W + '/forward/fold_features.csv.gz',
        'training_features': W + '/forward/worker_features_by_training_set.csv.gz',
        'feature_domains': W + '/forward/FEATURE_DOMAINS.json',
        'feature_refit_code': W + '/forward/build_features.py',
        'reverse_design': W + '/reverse/REGISTRATION.json',
        'reverse_code': W + '/reverse/discover_reverse_types_fast.py',
        'part_a_report': A + '/REPORT_ZH.md',
        'part_a_independent_review': 'research/workers/personnel_type_independent_review_20261019/REVIEW_ZH.md',
        'part_b_acceptance': 'research/workers/personnel_type_validation_next_20261019/part_a_acceptance/README.md',
        'part_b_design': 'research/workers/personnel_type_validation_next_20261019/DESIGN.json.gz',
        'part_b_code': 'tools/thesis_main/analysis/personnel_type_validation_20261019.py',
        'local_cluster_composition': V + '/clusters/fusion_analysis/composition_summary.csv',
        'local_cluster_report': V + '/clusters/REPORT_ZH.md',
        'same_room_separate_context': 'research/same_room/same_room_v2_prediction_20261019/CONSUMER_INTERFACE.json',
    }
    missing = [path for path in sources.values() if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(missing)
    for source in sources.values():
        directory = ROOT
        for part in Path(source).parts:
            if part not in {p.name for p in directory.iterdir()}:
                raise ValueError('path case is not portable: ' + source)
            directory /= part
    ignored = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT,
                             input=('\n'.join(sources.values())+'\n').encode(), capture_output=True)
    if ignored.returncode not in (0, 1) or ignored.stdout:
        raise ValueError('handoff depends on ignored sources: ' + ignored.stdout.decode())
    tracked = set(subprocess.check_output(['git','ls-files','--',*sources.values()],cwd=ROOT).decode().splitlines())
    records = read(ROOT / EVIDENCE)['records']
    evidence = {r['object_id']: r for r in records}
    if len(evidence) != len(records):
        raise ValueError('duplicate evidence object')
    snapshot = read(ROOT / sources['frozen_pools'])
    context = read(ROOT / sources['image_reference_context'])
    references = {r['target_id']: r for r in context['reference_catalog']}
    pools = snapshot['images']
    members, inventory = [], []
    for pool in pools:
        validate_pool(pool, evidence)
        m = pool['meta']; reference = references[m['reference_id']]
        for key in ('points_1024x512', 'floor_xz_h'):
            if pool['reference'][key] != reference[key]:
                raise ValueError('reference geometry mismatch: ' + pool['pool_id'])
        inventory.append({k: m[k] for k in ('pool_id','image_id','image','building','layer','condition','difficulty','pool_n','reference_id')})
        for r in pool['records']:
            members.append(dict(pool_id=pool['pool_id'], object_id=r['object_id'], worker_id=r['worker_id'],
                                origin=r['origin'], image_id=m['image_id'], building=m['building'],
                                layer=m['layer'], reference_id=m['reference_id']))
    ids = [r['object_id'] for r in members]
    qualified = {r['object_id'] for r in records if r['quality_usable']}
    if len(ids) != len(set(ids)) or set(ids) != qualified:
        raise ValueError('pool union is not the current quality population')
    labels = pd.read_csv(ROOT / sources['selected_and_baseline_labels'], low_memory=False)
    candidates = pd.read_csv(ROOT / sources['all_forward_fold_candidates'])
    candidates['heldout_building'] = candidates.heldout_building.fillna('FULL')
    candidates['difficulty'] = candidates.difficulty.replace({'all': 'global'})
    support = []
    for family, frame in [('selected_or_baseline', labels), ('forward_candidate', candidates)]:
        for (building, method, domain), group in frame.groupby(['heldout_building','method_id','difficulty']):
            # FULL is descriptive; validation support uses only the target-building-excluded labels.
            if building == 'FULL':
                continue
            class_counts(zip(group.worker_id, group.class_id))
            mapping = group.set_index('worker_id').class_id.to_dict()
            for pool in pools:
                meta = pool['meta']
                if meta['building'] != building or meta['layer'] != 'ordinary_manual':
                    continue
                if domain not in ('global', DIFFICULTY[meta['difficulty']]):
                    continue
                counts = class_counts((r['worker_id'], mapping.get(r['worker_id'])) for r in pool['records'])
                for label, workers in counts.items():
                    support.append(dict(family=family, method_id=method, domain=domain, heldout_building=building,
                                        pool_id=pool['pool_id'], class_id=label, is_known=label != 'unknown',
                                        n_workers=len(workers), worker_ids='|'.join(sorted(workers))))
    portraits = pd.read_csv(ROOT / sources['portraits_FULL_description_only'])
    feature_coverage = []
    for domain, features in read(ROOT / sources['feature_domains']).items():
        for feature in features:
            for origin, group in portraits.groupby('person_origin'):
                feature_coverage.append(dict(domain=domain, feature=feature, origin=origin, people=len(group),
                                             nonmissing=int(group[feature].notna().sum()), missing=int(group[feature].isna().sum())))
    for name, rows in [('POOL_INVENTORY.csv', inventory), ('POOL_MEMBERS.csv.gz', members),
                       ('POOL_CLASS_SUPPORT.csv.gz', support), ('FEATURE_COVERAGE.csv', feature_coverage)]:
        pd.DataFrame(rows).to_csv(OUT / name, index=False, encoding='utf-8',
                                 compression={'method': 'gzip', 'mtime': 0} if name.endswith('.gz') else None)
    image_index = pd.read_csv(ROOT / sources['image_release_index'])
    checks = dict(status='ready_in_worktree_not_remote_submission', inventory=len(records), quality_records=len(ids),
                  quality_images=len({r['image_id'] for r in members}), quality_workers=len({r['worker_id'] for r in members}),
                  pools=len(pools), pool_layers=dict(Counter(p['meta']['layer'] for p in pools)),
                  ordinary_manual_records=sum(len(p['records']) for p in pools if p['meta']['layer']=='ordinary_manual'),
                  portraits=len(portraits), selected_method_ids=int(labels.method_id.nunique()),
                  forward_candidate_methods=int(candidates.method_id.nunique()), pool_class_support_rows=len(support),
                  feature_coverage_rows=len(feature_coverage), image_release_status=image_index.original_status.value_counts().to_dict(),
                  sources_not_yet_tracked=[p for p in sources.values() if p not in tracked],
                  source_paths_case_checked_and_not_ignored=True,
                  points_scores_references_and_quality_population_agree=True, new_classification=False, new_fusion=False)
    write('CHECKS.json', checks)
    write('INPUTS.json', dict(schema='personnel_composition_handoff_v1', data_release='v2', sources=sources,
          unknown='unknown labels have no class meaning; missing features retain opportunity/support counts',
          support_scope='POOL_CLASS_SUPPORT is ordinary_manual only; conditional domain labels follow pool difficulty; other layers require own supported labels',
          field_contract={name: list(pd.read_csv(OUT/name, nrows=0).columns) for name in
                          ['POOL_INVENTORY.csv','POOL_MEMBERS.csv.gz','POOL_CLASS_SUPPORT.csv.gz','FEATURE_COVERAGE.csv']}))
    print(json.dumps(checks, ensure_ascii=True))


if __name__ == '__main__':
    build()
