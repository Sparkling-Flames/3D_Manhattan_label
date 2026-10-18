import pandas as pd
import pytest
import json
import hashlib

from tools.thesis_main.analysis.v1_statistics_revision_20261017 import (
    reconcile_states, validate_room_prefixes, endpoint_process_status,
)


def states():
    return pd.DataFrame(dict(pool_id=['p'], path_id=['a'], k=[1], path_kind=['random'],
        member_workers=['w'], reference_id=['r'], B8L2=[80.], D10=[81.], floor_WQ=[75.]))


def test_revision_preserves_old_keys_fields_and_restoration_boundary():
    old = states(); new = old.copy(); new.loc[0, 'floor_WQ'] = float('nan')
    fields, added = reconcile_states(old, new, require_restored=False)
    assert fields.set_index('field').loc['floor_WQ', 'lost'] == 1 and added.empty
    with pytest.raises(AssertionError, match='changed old field'):
        reconcile_states(old, new)
    new = old.copy(); new.loc[0, 'B8L2'] = 79.
    with pytest.raises(AssertionError, match='changed old field'):
        reconcile_states(old, new, require_restored=False)
    missing = old.copy();missing.loc[0, 'floor_WQ'] = float('nan')
    fields, _ = reconcile_states(missing, old)
    assert fields.set_index('field').loc['floor_WQ','supplemented_old_missing']==1
    with pytest.raises(AssertionError):
        reconcile_states(old, pd.concat([old, old]))
    new = pd.concat([old, old.assign(path_id='b', path_kind='same_room')], ignore_index=True)
    assert len(reconcile_states(old, new)[1]) == 1
    with pytest.raises(AssertionError, match='unexpected state expansion'):
        reconcile_states(old, new.assign(path_kind='worker'))


def room():
    return pd.DataFrame(dict(request_id=['r'], replay_id=[0], k=[2],
        worker_ids_a=['w1|w2'], worker_ids_b=['w1|w2'],
        complete_a=[True], complete_b=[True], both_complete=[True],
        comparison_quality_allowed_a=[True], comparison_quality_allowed_b=[False],
        comparison_B8L2_a=[80.], comparison_D10_a=[81.],
        comparison_B8L2_b=[None], comparison_D10_b=[None], both_quality=[False]))


def test_room_same_members_both_sides_masks_and_missingness():
    d = room()
    assert validate_room_prefixes(d)['both_primary_quality'] == 0
    d.loc[0, 'worker_ids_b'] = 'w2|w1'
    with pytest.raises(AssertionError, match='different cross-view'):
        validate_room_prefixes(d)
    d = room(); d.loc[0, 'comparison_B8L2_b'] = 90.
    with pytest.raises(AssertionError):
        validate_room_prefixes(d)


def test_module_complete_does_not_broadcast_pair_process_completion():
    candidates = pd.DataFrame(dict(image_a=['a','c'], image_b=['b','d'],
        same_room_process_status=['completed_real_paired_process']*2))
    selected = pd.DataFrame(dict(image_a=['a'], image_b=['b'], request_id=['r']))
    received = pd.DataFrame(dict(request_id=['r']))
    out = endpoint_process_status(candidates, selected, received)
    assert out.module_upstream_process_complete.all()
    assert out.pair_process_received.tolist() == [True,False]
    assert out.pair_process_status.iloc[1] == 'no_process_for_this_pair'


def test_snapshot_waits_for_ready_notice_and_replay_checks_bytes(tmp_path, monkeypatch):
    from tools.thesis_main.analysis import v1_statistics_revision_20261017 as m
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m, 'OUT', tmp_path/'revision')
    (tmp_path/'table.csv').write_text('id,value\na,1\n', encoding='utf-8')
    files = [dict(module='statistics', path='table.csv', kind='table')]
    with pytest.raises(AssertionError, match='explicit upstream-ready'):
        m.capture_sources(files)
    manifest = m.capture_sources(files, sources_ready=True)
    assert manifest['data_release'] == 'v1' and 'source_commit' not in manifest
    destination = tmp_path/'replayed'
    m.extract_snapshot(destination)
    assert (destination/'table.csv').read_bytes() == (tmp_path/'table.csv').read_bytes()
    (m.OUT/'SNAPSHOT.zip').write_bytes(b'corrupted')
    with pytest.raises(AssertionError): m.extract_snapshot(tmp_path/'bad')


def test_new_display_keeps_snapshot_identity_nulls_and_private_fields_out(tmp_path, monkeypatch):
    from tools.thesis_main.analysis import v1_statistics_revision_20261017 as m
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m, 'OUT', tmp_path/'revision')
    monkeypatch.setattr(m, 'EXPLORER', tmp_path/'display')
    source=tmp_path/'source';source.mkdir()
    body=b'object_id,B8L2,email,note\n0001,,private@example.test,mail@example.test\n'
    (source/'records.csv').write_bytes(body)
    manifest=dict(files=[dict(module='statistics',path='records.csv',kind='table',
        sha256=hashlib.sha256(body).hexdigest())])
    overview=dict(metadata=dict(snapshot_id=m.REVISION))
    index=m.publish_explorer(source,manifest,{},overview)
    assert index['source_commit'] is None and index['snapshot_id']==m.REVISION
    table=index['tables'][0]
    assert 'email' not in table['columns'] and table['row_count']==1
    part=json.loads((m.EXPLORER/'explorer-data'/table['parts'][0]['path']).read_text(encoding='utf-8'))
    assert part['rows']==[['0001',None,'[redacted email]']]


def test_local_display_files_preserve_json_and_remove_stale_wrappers(tmp_path):
    from tools.thesis_main.analysis.v1_statistics_revision_20261017 import publish_local_data
    data = tmp_path/'explorer-data'
    data.mkdir()
    original = '{"rows":[["0001",null,"</script>\\n中文"]]}'
    (data/'index.json').write_text(original, encoding='utf-8')
    (data/'stale.js').write_text('old', encoding='utf-8')
    assert publish_local_data(data) == 1
    wrapper = (data/'index.js').read_text(encoding='utf-8')
    assert wrapper.endswith(original + ';\n')
    assert not (data/'stale.js').exists()
    assert (data/'index.json').read_text(encoding='utf-8') == original
