from collections import Counter
import csv
from tools.thesis_main.analysis.audit_order_completion_20260929 import OUT, read


def test_all_batches_closed_without_claiming_unreviewed_or_pairing_complete():
    s=read(OUT/'summary.json')
    assert s['order_queue_complete'] and not s['full_pairing_and_order_complete']
    assert not s['all_annotations_individually_confirmed']
    assert s['pending_order_ids']==s['queue_missing']==[]
    assert s['batches'][1]['changes']=={'unchanged':34,'adjacency_changed':1}
    assert s['current_confirmation_total']==1272 and s['manual_gt_confirmed']==30
    with (OUT/'全量3152份排序闭合审计.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    assert len(rows)==len({r['object_id'] for r in rows})==3152
    assert len({r['image_id'] for r in rows})==259
    assert Counter(r['final_state'] for r in rows)==s['annotation_states']
    assert s['geometry_blocked_ids']==['new_93_3587_7182_W010']
    assert s['next_stage_total']==34 and s['pairing_deferred']==33
    package=read(OUT/'同房汇集_Matterport_当前确认快照.json')
    objects=[o for room in package['rooms'] for image in room['images'].values() for o in image['annotations']]
    assert len(objects)==len({o['object_id'] for o in objects})==1272
    assert package['complete'] is False and package['remaining_order_candidates']==[]
    assert not {o['object_id'] for o in objects}.intersection(package['pairing_deferred']+package['representation_deferred'])
