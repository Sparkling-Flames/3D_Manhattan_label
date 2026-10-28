import json
from tools.thesis_main.analysis.rescore_adopted_references_20261028 import OUT, ADOPT


def test_new_measurements_match_exact_reference_and_keep_missing_states():
    refs={r['target_id']:r for r in json.loads((ADOPT/'REFERENCE_CATALOG.json').read_text(encoding='utf-8'))}
    rows=[json.loads(line) for line in (OUT/'ORIGINAL_MEASUREMENTS.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==2480 and len({r['task']['object_id'] for r in rows})==2480
    for row in rows:
        task,result=row['task'],row['result'];ref=refs[task['current_target_id']]
        assert task['reference_points']==ref['points_1024x512']
        assert task['reference_version']==ref['reference_version']
        if result['score_status']=='complete':
            assert all(result[k] is not None for k in ['B8L2','D10','IoU3D100','dir','Hmean','Hcenter'])
        else:
            assert result['B8L2'] is None and result['IoU3D100'] is None
            assert result['reasons']==['annotation:paired_points_unavailable']
    assert sum(r['result']['score_status']=='complete' for r in rows)==2445
