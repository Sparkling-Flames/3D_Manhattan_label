"""Review round trips retain text and reject a different run/point set."""
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.thesis_main.analysis.paired_split_research.release_review import SCHEMA, check_ordinals, digest, user_records, validate_review, verify_run


def test_review_binding_roundtrip_and_original_text():
    binding = {'manifest': 'version-one', 'point_sets': {'a': digest([[1, 2]])}}
    answer = {'schema': SCHEMA, 'binding': binding, 'decisions': {
        'image|manual': {'relation': '', 'comment': 'W006 p3 对 W013 p4；范围遗漏仍有研究价值', 'defer': True}}}
    restored = json.loads(json.dumps(answer, ensure_ascii=False))
    assert validate_review(restored, binding, ['image|manual']) == answer['decisions']
    for changed in [{'manifest': 'version-two', 'point_sets': binding['point_sets']},
                    {'manifest': 'version-one', 'point_sets': {'a': digest([[1, 3]])}}]:
        with pytest.raises(ValueError):
            validate_review(restored, changed, ['image|manual'])
    assert user_records({'decisions': {'image|manual|a|b': {'Note': '原文', 'Relation': ''}}}, 'image') == [
        {'key': 'image|manual|a|b', 'original': {'Note': '原文', 'Relation': ''}}]
    bad = copy.deepcopy(answer)
    bad['decisions']['other'] = next(iter(bad['decisions'].values()))
    with pytest.raises(ValueError):
        validate_review(bad, binding, ['image|manual'])
    ordinal = [{'point_index_1based': '1', 'x': '1', 'y': '2'}]
    check_ordinals([[1, 2]], ordinal)
    with pytest.raises(ValueError):
        check_ordinals([[1, 3]], ordinal)
    with pytest.raises(ValueError):
        check_ordinals([[1, 2], [3, 4]], ordinal)


def test_browser_validator_same_contract():
    node = shutil.which('node') or ('D:/nodejs/node.exe' if Path('D:/nodejs/node.exe').is_file() else None)
    if not node:
        pytest.skip('Node unavailable')
    script = Path(__file__).resolve().parents[1]/'tools/thesis_main/analysis/paired_split_research/release_review_panel.js'
    subprocess.run([node, '--check', str(script)], check=True)
    code = '''const assert=require('assert'), {validateReleaseReview:validate}=require(process.argv[1]);
      const b={manifest:'m',point_sets:{a:'p'}},d={'image|manual':{relation:'',comment:'文字完整',defer:true}};
      const v={schema:'clustering_release_visual_review_v1',binding:b,decisions:d};
      assert.deepStrictEqual(validate(JSON.parse(JSON.stringify(v)),b,['image|manual']),d);
      assert.deepStrictEqual(validate(v,{point_sets:{a:'p'},manifest:'m'},['image|manual']),d);
      assert.throws(()=>validate(v,{...b,manifest:'wrong'},['image|manual']));
      assert.throws(()=>validate(v,{...b,point_sets:{a:'changed'}},['image|manual']));
      assert.throws(()=>validate(v,{...b,review_content:'changed-question'},['image|manual']));
      assert.throws(()=>validate(v,b,['wrong']));
      const custom={...v,decisions:{'image|manual':{relation:'多标需删点',comment:'p7',defer:false}}};
      assert.deepStrictEqual(validate(custom,b,['image|manual'],{'image|manual':['多标需删点']}),custom.decisions);
      assert.throws(()=>validate(custom,b,['image|manual']));'''
    subprocess.run([node, '-e', code, str(script)], check=True)


def test_run_rejects_missing_stale_and_mixed_files(tmp_path):
    def write(p, value):
        p.write_text(json.dumps(value), encoding='utf-8')
        return hashlib.sha256(p.read_bytes()).hexdigest()
    inputs, results = tmp_path/'inputs', tmp_path/'results'
    inputs.mkdir(); results.mkdir()
    source_hash = write(inputs/'responses.jsonl.gz', [])
    hashes = {name: write(results/name, {}) for name in ['cache.json', 'memberships.csv', 'point_ordinals.csv', 'minimal_local_check.csv']}
    hashes['PUBLICATION_CHECK.json'] = write(results/'PUBLICATION_CHECK.json', {'run_id': 'one', 'numerical_gate': 'passed'})
    manifest = {'run_id': 'one', 'input_files': {'inputs/responses.jsonl.gz': source_hash}}
    write(tmp_path/'RUN_MANIFEST.json', manifest)
    result_manifest = {'run_id': 'one', 'files': hashes}
    write(results/'RESULT_MANIFEST.json', result_manifest)
    assert verify_run(tmp_path) == manifest
    photo = 'input/source/analysis_results/paired_split_research_received_20260920/history_visual_review/example.jpg'
    manifest['input_files'][photo] = 'display-only-not-present'
    write(tmp_path/'RUN_MANIFEST.json', manifest)
    with pytest.raises(ValueError):
        verify_run(tmp_path)
    assert verify_run(tmp_path, numerical_only=True) == manifest
    manifest['input_files']['inputs/missing_numeric.json'] = 'must-not-ignore'
    write(tmp_path/'RUN_MANIFEST.json', manifest)
    with pytest.raises(ValueError):
        verify_run(tmp_path, numerical_only=True)
    del manifest['input_files'][photo]
    del manifest['input_files']['inputs/missing_numeric.json']
    write(tmp_path/'RUN_MANIFEST.json', manifest)
    write(results/'RESULT_MANIFEST.json', dict(result_manifest, run_id='old'))
    with pytest.raises(ValueError):
        verify_run(tmp_path)
    write(results/'RESULT_MANIFEST.json', result_manifest)
    write(inputs/'responses.jsonl.gz', ['changed'])
    with pytest.raises(ValueError):
        verify_run(tmp_path)
    write(inputs/'responses.jsonl.gz', [])
    (results/'cache.json').unlink()
    with pytest.raises(ValueError):
        verify_run(tmp_path)
