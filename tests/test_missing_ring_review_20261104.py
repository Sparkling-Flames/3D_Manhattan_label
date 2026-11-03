from tools.thesis_main.analysis.build_missing_ring_review_20261104 import (
    REASON, inspect_row, nested_failures, make_source, selected_records, state_records,
)
import pytest


def test_reason_is_not_all_missing_quality():
    assert inspect_row({'geometry': {'reason': REASON}})
    assert not inspect_row({'B8L2': None, 'geometry': 'unavailable'})
    assert list(nested_failures({'teams': [{'geometry': {'reason': REASON}, 'team_key': 'a'}]}))[0][1] == '/teams/0'


def test_raw_binding_rejects_multiple_coordinate_versions():
    row = {'member_object_ids': ['a']}
    obj = {'a': [({'points': [[0,0]]}, {}), ({'points': [[1,0]]}, {})]}
    with pytest.raises(ValueError, match='多个坐标版本'):
        selected_records(row, {}, obj)


def test_source_keeps_unordered_nodes_and_no_user_answer():
    case=dict(review_id='one',team_key='team',image='im',image_id='pano',condition='manual',k=20,
              sources=[],reference_id='ref',reference_version='v',data_release='v2.1',
              nodes=[dict(feature_id='node_006',support=10,points=[[300,100],[300,400]]),
                     dict(feature_id='node_002',support=20,points=[[100,120],[100,390]])])
    s=make_source(case)
    assert s['feature_ids']==['node_006','node_002']
    assert s['default_preview_order']==[0,1]
    assert s['ring_confirmed'] is False and s['review']=={}
    assert s['points']==[[300,100],[300,400],[100,120],[100,390]]
    assert s['review_metadata']['team_key']=='team'


def test_original_responses_recover_in_source_order():
    state={'identity_groups':[{'members':[dict(id='a',pair_index=1,points=[[5,6],[7,8]]),dict(id='a',pair_index=0,points=[[1,2],[3,4]])]}],
           'assignments':[dict(id='a',worker='W01',feature_ids=['n2','n1'])]}
    assert state_records(state)[0]['points']==[[1,2],[3,4],[5,6],[7,8]]


def test_confirmed_raw_order_uses_pair_binding_not_point_number_sort():
    import json
    from tools.thesis_main.analysis.close_current_ring_audit_20261104 import ordered_points
    record={'binding':json.dumps({'points':[[1,0],[1,1],[2,0],[2,1]],'links':[[2,3],[0,1]]}),'order':[0,1]}
    assert ordered_points(record)==[[2,0],[2,1],[1,0],[1,1]]
    record['order']=[0,0]
    with pytest.raises(AssertionError):ordered_points(record)


def test_pages_require_validated_queue_instead_of_inventory_fallback(tmp_path,monkeypatch):
    from tools.thesis_main.analysis import build_missing_ring_review_20261104 as m
    monkeypatch.setattr(m,'OUT',tmp_path)
    with pytest.raises(FileNotFoundError,match='VALIDATED_REVIEW_IDS'):
        m.build_pages()


def test_returned_order_rejects_changed_coordinates_and_duplicate_nodes():
    import json
    from tools.thesis_main.analysis.import_missing_ring_orders_20261104 import validate_order
    case={'review_id':'x','nodes':[{'feature_id':'n1','points':[[1,2],[1,3]]},{'feature_id':'n2','points':[[4,5],[4,6]]}]}
    binding={'id':'missing_ring:x','points':[[1,2],[1,3],[4,5],[4,6]],'links':[[0,1],[2,3]]}
    record={'binding':json.dumps(binding),'order':[1,0]}
    assert validate_order(record,case)==['n2','n1']
    record['order']=[1,1]
    with pytest.raises(AssertionError):validate_order(record,case)
    record['order']=[1,0];binding['points'][0][0]=99;record['binding']=json.dumps(binding)
    with pytest.raises(AssertionError):validate_order(record,case)


def test_bulk_export_validates_and_preserves_saved_records():
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to test the browser export script')
    root = Path(__file__).resolve().parents[1]
    script = root / 'research' / 'fusion' / 'missing_ring_review_20261104' / 'export_all.js'
    harness = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const schema = 'missing_ring_order_review_20261104_v1';
const source = {object_id:'missing_ring:a', object_kind:'fusion', points:[[1,2],[3,4]], links_zero_based:[[0,1]], feature_ids:['a'], node_supports:[2], review_metadata:{image:'im'}};
const binding = JSON.stringify({id:source.object_id, points:source.points, labels:source.effective_point_labels, links:source.links_zero_based});
const key = schema + ':/pages/a.html';
const saved = JSON.stringify({'missing_ring:a':{binding, status:'confirmed', order:[0]}});
const store = {[key]:saved};
const context = {URL, localStorage:{getItem:k=>store[k] ?? null}, location:{href:'file:///index.html'}, window:{}, setTimeout};
function element(){return {style:{}, append(){}, before(){}, setAttribute(){}, remove(){}};}
context.document = {createElement:element, querySelector:()=>element(), querySelectorAll:()=>[{getAttribute:()=> 'pages/a.html'}], head:{append(script){context.window.STUDIO_DATA={manifest:{export_schema:schema}, cases:[{variants:[{source}]}]};script.onload();}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
 const doc=await context.window.buildMissingRingExport();
 assert.equal(doc.summary.confirmed,1); assert.equal(doc.summary.cases,1);
 assert.equal(doc.records['missing_ring:a'].binding,binding);
 assert.equal(store[key],saved);
 store[key]=JSON.stringify({'missing_ring:a':{binding,status:'confirmed',order:[1]}});
 await assert.rejects(context.window.buildMissingRingExport(), /不匹配/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run([node, '-e', harness, str(script)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_prepared_archive_restore_checks_hash_and_crc(tmp_path):
    import hashlib
    import json
    import zipfile
    from tools.thesis_main.analysis.restore_missing_ring_prepared_20261104 import restore, verify

    archive = tmp_path / 'shards'
    archive.mkdir()
    payload = b'{"review_id":"case"}'
    shard = archive / 'prepared_01.zip'
    with zipfile.ZipFile(shard, 'w', compression=zipfile.ZIP_STORED) as zf:
        zf.writestr('case.json.gz', payload)
    manifest = {'parts':[{'file':shard.name,'bytes':shard.stat().st_size,
        'sha256':hashlib.sha256(shard.read_bytes()).hexdigest(),'files':1,
        'content_bytes':len(payload)}], 'total_files':1,'total_content_bytes':len(payload)}
    (archive / 'PREPARED_SHARDS_MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
    assert verify(archive)['files'] == 1
    target = tmp_path / 'restored'
    restore(target, archive)
    assert (target / 'case.json.gz').read_bytes() == payload
    corrupted = bytearray(shard.read_bytes())
    corrupted[0] ^= 1
    shard.write_bytes(corrupted)
    with pytest.raises(ValueError, match='SHA-256'):
        verify(archive)
