import json
from collections import Counter

from tools.thesis_main.data_prep.build_cn_first10_import_20260922 import build, ROOT


def test_import_is_plain_manual_and_matches_all_personal_lists():
    tasks,assignments,project,workbook,_=build()
    previous=json.loads((ROOT/'import_json/scene_stability_stage1_20260913_v2/label_studio_import/任务7.json').read_text(encoding='utf8'))
    assert len(tasks)==19 and len(assignments)==90
    assert Counter(r['worker_id'] for r in assignments)=={r['worker_id']:10 for r in workbook['workers']}
    assert len({(r['worker_id'],r['image_id']) for r in assignments})==90
    index={t['data']['base_task_id']:t['data'] for t in tasks}
    for t in tasks:
        assert set(t)=={'data'} and set(t['data'])==set(previous[0]['data'])
        assert t['data']['condition']=='manual' and '?' not in t['data']['vis_3d']
    for r in assignments:
        assert r['package_task_code']==index[r['image_id']]['package_task_code']
        assert r['display_task_code']=='任务8-'+r['package_task_code']
    assert project['project_id'] is None
