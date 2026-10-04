"""只核查已保存输入与审查覆盖；不重算融合、不改变资格。"""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    data = read(ROOT/'analysis_results/research_input_20260929/preprocessed_source.json')
    old = read(ROOT/'analysis_results/research_panel_inventory_20261003/input.json')
    current = read(OUT/'corrected_inventory/input.json')
    assert old['records'] == current['records'], 'annotation_inventory_changed'
    assert old['references'] == current['references'], 'reference_inventory_changed'
    old_images = {r['image']: r for r in old['images']}
    current_images = {r['image']: r for r in current['images']}
    assert set(old_images) == set(current_images)
    for code, before in old_images.items():
        after = current_images[code]
        assert all(after[k] == v for k, v in before.items() if k != 'difficulty'), code
    per_image = defaultdict(list)
    for obj in data['objects']:
        if obj['object_kind'] == 'annotation':
            per_image[obj['image_code']].append(obj)
    assert set(per_image) == set(current_images)
    coverage = []
    for code, annotations in sorted(per_image.items()):
        image_sources = sorted({h['source'] for o in annotations
                                for h in o['review_evidence']['image_review_history']})
        n = sum(o['final_review']['individually_reviewed'] for o in annotations)
        coverage.append(dict(image=code, image_id=annotations[0]['image_id'],
            annotation_n=len(annotations), individually_reviewed_n=n,
            structured_image_history=bool(image_sources), image_history_sources=image_sources,
            confirmed_annotation_rings=sum(o['ring_confirmed'] for o in annotations),
            any_review_record=bool(image_sources) or n > 0,
            difficulty=current_images[code]['difficulty']))
    assert all(r['any_review_record'] for r in coverage)
    old_panel = read(ROOT/'analysis_results/research_panel_inventory_20261003/next_panels.json')['a']
    new_panel = read(OUT/'corrected_inventory/next_panels.json')['a']
    changed_45 = [dict(image=i, before=old_images[i]['difficulty'], after=current_images[i]['difficulty'])
                  for i in old_panel['images'] if old_images[i]['difficulty'] != current_images[i]['difficulty']]
    with (OUT/'corrected_inventory/groups.csv').open(encoding='utf-8-sig', newline='') as f:
        groups = list(csv.DictReader(f))
    high = [g for g in groups if g['condition'] == 'manual' and int(g['candidate_n']) >= 20]
    assert len(high) == len({g['image'] for g in high})
    high_ready = [g for g in high if g['curve_ready'] == 'True' and g['original_bev_ok'] == 'True']
    high_main = [g for g in high_ready if g['reference_quality_compatible'] == 'True']
    reasons = {g['image']: [dict(id=r['id'], quality_gate=r['quality_gate'], quality_reasons=r['quality_reasons'],
                               bev_ok=r['bev_ok'], bev_reason=r['bev_reason'])
                           for r in current['records'] if r['image'] == g['image']
                           and r['condition'] == 'manual' and r['consensus_candidate']
                           and (not r['quality_candidate'] or not r['bev_ok'])]
               for g in high if g not in high_main}
    write('review_coverage.json', coverage)
    write('high_manual_pools.json', dict(all_ge20=high,
        outside_main=[dict(g, affected_records=reasons[g['image']]) for g in high if g not in high_main]))
    history_path = 'analysis_results/human_review_reconciliation_20260918/用户_39图文字审核_原始.json'
    history = read(ROOT/history_path)
    comments = read(ROOT/'analysis_results/research_input_20260929/comments.json')['comments']
    by_id = {r['image_id']: r['image'] for r in coverage}
    historical_notes = []
    for index, note in enumerate(history['image_notes']):
        texts = [c['text'] for c in comments if c['image_id'] == note['image_id']]
        historical_notes.append(dict(note, image=by_id[note['image_id']],
            source_pointer=f'/image_notes/{index}/note',
            verbatim_in_frozen_comment_table=any(note['note'] in text for text in texts)))
    write('historical_image_notes.json', dict(schema='historical_image_notes_supplement_v1',
        source=history_path, saved_at=history['saved_at'], reviewer='user',
        role='历史用户原话检索补充；不覆盖后续裁决，不从文字或旧簇编号生成标签。', records=historical_notes))
    write('summary.json', dict(schema='review_source_audit_20261004_v1', images=len(coverage),
        annotations=sum(r['annotation_n'] for r in coverage),
        individually_reviewed_annotations=sum(r['individually_reviewed_n'] for r in coverage),
        structured_image_history=sum(r['structured_image_history'] for r in coverage),
        images_with_only_individual_history=sum(not r['structured_image_history'] for r in coverage),
        confirmed_annotation_rings=sum(r['confirmed_annotation_rings'] for r in coverage),
        difficulty_before=dict(Counter(i['difficulty'] for i in old_images.values())),
        difficulty_after=dict(Counter(i['difficulty'] for i in current_images.values())),
        historical_annotation_inventory_identical=True, historical_reference_inventory_identical=True,
        all_original_image_fields_except_difficulty_identical=True,
        historical_45_labels_unchanged=not changed_45, historical_45_label_changes=changed_45,
        next_panel_images=len(new_panel['images']), next_panel_difficulty=new_panel['difficulty_counts'],
        next_panel_added=sorted(set(new_panel['images'])-set(old_panel['images'])),
        historical_image_notes=dict(total=len(historical_notes),
            verbatim_in_frozen_comment_table=sum(r['verbatim_in_frozen_comment_table'] for r in historical_notes)),
        manual_ge20=dict(candidate_images=len(high), fully_computable_images=len(high_ready),
                         main_quality_compatible_images=len(high_main)),
        scope='Saved evidence and input binding only; no visual re-review or fusion rerun.'))


if __name__ == '__main__':
    main()
