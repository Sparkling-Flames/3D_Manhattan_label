"""从去重端点与冻结请求复核旧全集和 Manual 推荐，不运行融合或拟合。"""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.audit_personnel_adoption_20261022 import (
    ROOT, PACKAGE, abc_members, close, models, members,
)

BASE = ROOT / 'research/workers/personnel_exchange_closure_20261022'


def main():
    scalar = pd.read_csv(BASE / 'delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz', low_memory=False).set_index('team_key')
    geo = pd.read_csv(BASE / 'delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz', dtype=str, keep_default_na=False).set_index('team_key')
    source = pd.read_csv(BASE / 'delivery/endpoints/ENDPOINT_SOURCE_INDEX.csv.gz').set_index('team_key')
    assert len(scalar) == len(geo) == len(source) == 101092
    assert scalar.index.is_unique and geo.index.is_unique and source.index.is_unique
    assert set(scalar.index) == set(geo.index) == set(source.index)
    geo, source = geo.loc[scalar.index], source.loc[scalar.index]
    for name in ['pool_id', 'member_workers', 'score_status', 'node_supports', 'reference_id', 'reference_version']:
        assert scalar[name].astype(str).equals(geo[name]), name
    for name in ['k', 'minimum_support']:
        close(scalar[name], pd.to_numeric(geo[name]))
    assert scalar.complete_evaluable.equals(geo.complete_evaluable.str.lower().eq('true'))
    for name in ['pool_id', 'member_workers', 'k', 'condition', 'score_status']:
        assert scalar[name].equals(source[name]), name
    assert scalar.member_workers.map(lambda s: len(members(s))).eq(scalar.k).all()
    for value in geo.geometry_json:
        if value:
            json.loads(value)
    good = scalar.B8L2.notna()
    assert good.sum() == 100304 and good.equals(scalar.complete_evaluable)
    assert scalar.loc[~good, ['B8L2', 'D10']].isna().all().all()
    inputs = [scalar.loc[good, f].to_numpy() for f in ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']]
    errors = {}
    for name, params in [('B8L2', models.B), ('D10', replace(models.B, direction_scale_deg=10.))]:
        computed = models.score(*inputs, params)
        close(computed, scalar.loc[good, name])
        errors[name] = float(np.max(np.abs(computed - scalar.loc[good, name])))
    report = {'underlying_data_version': 'v2', 'endpoints': {
        'unique': len(scalar), 'scored': int(good.sum()), 'unscored': int((~good).sum()),
        'status_counts': scalar.score_status.value_counts().to_dict(),
        'execution_identity': source.execution_identity.value_counts().to_dict(),
        'score_max_abs_errors': errors, 'scalar_geometry_source_identity_consistent': True},
        'not_run': ['native fusion', 'raw annotation rescoring', 'classification feature reconstruction or refitting', 'human semantic adjudication', 'all pairwise geometry distance reconstruction']}

    refs = 0
    requested = set()
    for path in sorted((BASE / 'native/batches').glob('*/REQUESTS.csv.gz')):
        request = pd.read_csv(path)
        refs += len(request)
        requested.update(request.team_key)
        for name in ['member_workers', 'pool_id']:
            assert scalar.loc[request.team_key, name].reset_index(drop=True).equals(request[name]), (path.name, name)
        close(scalar.loc[request.team_key, 'k'], request.n)
    extras = set(scalar.index) - requested
    repairs = pd.read_csv(BASE / 'delivery/received_core_20261022/GEOMETRY_METADATA_REPAIRS.csv', dtype=str, keep_default_na=False)
    assert refs == 101093 and len(requested) == 101090
    assert extras == set(repairs.team_key) and len(repairs) == 14 and repairs.before.eq('').all()
    for r in repairs.itertuples():
        assert geo.loc[r.team_key, r.field] == r.after
    report['requests'] = {'central_references': refs, 'unique_requested': len(requested), 'legacy_extra_controls': sorted(extras)}
    report['metadata_repair'] = {'rows': 2, 'cells': len(repairs), 'fields': sorted(repairs.field.unique())}

    registered = {}
    paths = {'manual_A': 'manual_joint/EVENTS_REGISTERED.csv.gz',
             'manual_B': 'manual_joint/phase_b_highq_slower/EVENTS_REGISTERED.csv.gz',
             'structure': 'structure/ALL_EVENTS_REGISTERED.csv.gz',
             'semi': 'semi/EVENTS_REGISTERED_ALL.csv.gz'}
    report['registered_events'] = {}
    for name, path in paths.items():
        frame = pd.read_csv(BASE / path, low_memory=False)
        assert frame.event_id.is_unique
        abc_members(frame, 'm_AB')
        assert frame.m_AB.eq(frame.m_AC).all() and frame.m_AB.eq(frame.m_BC).all()
        for arm in 'ABC':
            s = scalar.loc[frame['team_' + arm]].reset_index(drop=True)
            assert s.member_workers.equals(frame[arm + '_member_workers'])
            assert s.k.equals(frame.n) and s.pool_id.equals(frame.pool_id) and s.condition.equals(frame.condition)
        registered[name] = frame
        report['registered_events'][name] = {'rows': len(frame), 'physical_ABC': frame.physical_triple_id.nunique(),
            'images': frame.image.nunique(), 'buildings': frame.building.nunique(), 'all_ABC_members_and_endpoint_keys_checked': True}
    assert sum(len(f) for f in registered.values()) == 146031

    labels = pd.read_csv(BASE / 'manual_joint/INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz').set_index(['heldout_building', 'worker_id'])
    saved = pd.read_csv(BASE / 'manual_joint/COMMON_ABC_SIGNED_EFFECTS.csv')
    report['manual_recommendations'] = []
    for stage, direction in [('A', 'q_up__faster'), ('B', 'q_up__slower')]:
        f = registered['manual_' + stage]
        f = f[f.n.eq(20) & f.m_AB.eq(4) & f.training_QT_direction.eq(direction)].copy().reset_index(drop=True)
        assert f.A_counts.equals(f.B_counts) and f.source_class.ne(f.target_class).all()
        assert f.class_center_delta_q_history.gt(0).all()
        assert (f.class_center_delta_t_history < 0 if stage == 'A' else f.class_center_delta_t_history > 0).all()
        for r in f[['building', 'outgoing_block_X', 'same_count_block_Y', 'changed_count_block_Z', 'source_class', 'target_class']].drop_duplicates().itertuples():
            for block, label in [(r.outgoing_block_X, r.source_class), (r.same_count_block_Y, r.source_class), (r.changed_count_block_Z, r.target_class)]:
                assert all(labels.loc[(r.building, w), 'coarse_label'] == label for w in members(block))
        arms = {a: scalar.loc[f['team_' + a]].reset_index(drop=True) for a in 'ABC'}
        common = np.logical_and.reduce([s.complete_evaluable for s in arms.values()])
        time = np.logical_and.reduce([s.source_time_known_n.eq(20) & s.source_time_total_seconds.gt(0) & s.time_source_kinds.notna() & ~s.time_source_kinds.str.contains('|', regex=False, na=True) for s in arms.values()])
        time &= arms['A'].time_source_kinds.eq(arms['B'].time_source_kinds) & arms['A'].time_source_kinds.eq(arms['C'].time_source_kinds)
        metrics = []
        for pre, a, b in [('same', 'B', 'A'), ('cross', 'C', 'A'), ('net', 'C', 'B')]:
            for field in ['B8L2', 'D10', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']:
                name = pre + '_' + field
                f[name] = (arms[a][field] - arms[b][field]).where(common)
                metrics.append(name)
            name = pre + '_recorded_time_logratio'
            f[name] = np.log(arms[a].source_time_total_seconds / arms[b].source_time_total_seconds).where(common & time)
            metrics.append(name)
        panels = f[common].groupby(['panel_id', 'building', 'image'])[metrics].mean().reset_index()
        images = panels.groupby(['building', 'image'])[metrics].mean().reset_index()
        buildings = images.groupby('building')[metrics].mean()
        values = buildings.mean()
        ref = saved[saved.stage.eq(stage) & saved.view.eq(direction + ';n20;m4')].iloc[0]
        comparable = [m for m in metrics if m in ref.index]
        close(values[comparable], ref[comparable].astype(float))
        assert len(f) == ref.registered_events and common.sum() == ref.common_scored_events
        assert f.panel_id.nunique() == ref.registered_panels and len(panels) == ref.common_scored_panels
        row = {'stage': stage, 'direction': direction, 'n': 20, 'm': 4, 'events': len(f),
               'common_scored': int(common.sum()), 'registered_panels': f.panel_id.nunique(),
               'common_time_events': int((common & time).sum()),
               'failures_all_registered': {a: int((~s.complete_evaluable).sum()) for a, s in arms.items()},
               'means_building_equal': values.to_dict(), 'net_recorded_time_pct': float(100 * np.expm1(values.net_recorded_time_logratio))}
        for level, frame in [('panel', panels), ('image', images), ('building', buildings)]:
            positive = int(frame.net_B8L2.gt(0).sum())
            assert positive == ref[level + '_net_Q_positive'] and len(frame) == ref[level + '_net_Q_known']
            row[level + '_Q_positive'] = positive
            row[level + '_Q_known'] = len(frame)
        report['manual_recommendations'].append(row)

    out = PACKAGE / 'audit/LOCAL_ENDPOINT_AND_MANUAL_CHECK.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=lambda x: x.item()) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2, default=lambda x: x.item()))


if __name__ == '__main__':
    main()
