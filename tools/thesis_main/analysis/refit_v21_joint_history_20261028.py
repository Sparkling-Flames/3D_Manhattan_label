"""原答结构输入未变则复用V3结构标签；仅重拟合质量历史确有变化的V3联合分类。"""
import importlib.util
import json
import sys
import types
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read

SOURCE = ROOT / 'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy'
TARGET = OUT / 'joint_history_classification'


def modules():
    # Archived script used its former directory depth; only its source root changes.
    path = SOURCE / 'discover_behavior_classes.py'
    source = path.read_text(encoding='utf-8')
    assert source.count('REPO = HERE.parents[3]') == 1
    base = types.ModuleType('discover_behavior_classes'); base.__file__ = str(path)
    sys.modules[base.__name__] = base
    exec(compile(source.replace('REPO = HERE.parents[3]', 'REPO = Path(' + repr(str(ROOT)) + ')'), str(path), 'exec'), base.__dict__)
    spec = importlib.util.spec_from_file_location('v21_joint_native', SOURCE / 'discover_joint_qt.py')
    joint = importlib.util.module_from_spec(spec); spec.loader.exec_module(joint)
    return base, joint


def main():
    TARGET.mkdir(exist_ok=True)
    base, joint = modules(); original = base.load(); x = original.copy()
    quality = pd.DataFrame(read(OUT / 'quality_inventory.json')).set_index('object_id')
    for field in ['quality_usable', 'quality_use', 'reference_id', 'reference_version', 'B8L2', 'D10']:
        x[field] = x.object_id.map(quality[field])
    x['reference_id'] = x.reference_id.replace('', np.nan)
    x['difficulty'] = x.object_id.map(quality.current_class)
    qok = x.quality_usable & ((~x.layer.eq('ordinary')) | x.quality_use.eq('ordinary_primary'))
    for field in ['B8L2', 'D10']:
        x.loc[~qok, field] = np.nan
        x[field + '_peer_delta'] = x[field] - x.loc[qok].groupby(base.KEY, dropna=False)[field].transform('mean')
    invariant = base.KEY + base.RAW + base.HIST + base.CONTEXT + [
        'behavior_usable', 'complex_opportunity', 'personal_comparison', 'primary_expression',
        'source_active_time_seconds', 'time_source_kind', 'log_time_peer_delta']
    pd.testing.assert_frame_equal(original[invariant], x[invariant])
    x.to_csv(TARGET / 'BEHAVIOR_RECORDS.csv.gz', index=False, encoding='utf-8-sig')
    oldlabels = pd.read_csv(ROOT / 'research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz')
    oldlabels = pd.concat([oldlabels, pd.read_csv(SOURCE / 'ALL_METHOD_LABELS_ALL_DATA.csv')], ignore_index=True)
    labels = []; selections = []; registries = []; inner = []
    behavior = base.Study(x); study = joint.Joint(x)
    for condition in ['manual', 'semi']:
        for building in ['ALL'] + study.buildings:
            checkpoint = TARGET / f'{condition}_{building}_LABELS.csv.gz'
            if checkpoint.exists():
                labels.append(pd.read_csv(checkpoint, low_memory=False))
                selections.append(read(TARGET / f'{condition}_{building}_SELECTION.json'))
                registries.append(pd.read_csv(TARGET / f'{condition}_{building}_REGISTRY.csv'))
                inner.append(pd.read_csv(TARGET / f'{condition}_{building}_INNER.csv.gz'))
                continue
            old = oldlabels[(oldlabels.method == 'V3_BEHAVIOR') & (oldlabels.condition == condition) & (oldlabels.heldout_building == building)].copy()
            assert not old.empty
            features = behavior.features(condition, () if building == 'ALL' else (building,)).set_index('worker_id')
            for c in features.columns:
                if c in old and c != 'condition': old[c] = old.worker_id.map(features[c])
            rows = study.inner(condition, building); choice, candidates = study.choose(condition, building, rows)
            new = study.labels(choice)
            frame = pd.concat([old, new], ignore_index=True); frame['data_release'] = 'v2.1'
            frame.to_csv(checkpoint, index=False, encoding='utf-8-sig')
            candidates.to_csv(TARGET / f'{condition}_{building}_REGISTRY.csv', index=False, encoding='utf-8-sig')
            pd.DataFrame(rows).to_csv(TARGET / f'{condition}_{building}_INNER.csv.gz', index=False, encoding='utf-8-sig')
            (TARGET / f'{condition}_{building}_SELECTION.json').write_text(json.dumps(choice, ensure_ascii=False), encoding='utf-8')
            labels.append(frame); selections.append(choice); registries.append(candidates); inner.append(pd.DataFrame(rows))
            print('V3 joint', condition, building, choice['family'], choice['fine_k'], flush=True)
    pd.concat(labels, ignore_index=True).to_csv(TARGET / 'ALL_METHOD_LABELS_LOBO.csv.gz', index=False, encoding='utf-8-sig')
    pd.concat(registries, ignore_index=True).to_csv(TARGET / 'CANDIDATE_REGISTRY.csv.gz', index=False, encoding='utf-8-sig')
    (TARGET / 'CHECKS.json').write_text(json.dumps(dict(data_release='v2.1',
        behavior_feature_columns_verified_equal=invariant, behavior_labels_reused=True,
        joint_folds=len(selections), raw_records=len(x), new_fusion=0,
        reference_root_adaptation_only=True), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
