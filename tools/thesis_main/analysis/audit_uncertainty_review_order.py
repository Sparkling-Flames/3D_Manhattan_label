"""核对50图所有显示坐标与点序；不认定哪种邻接是作者本意。"""
import json
from collections import Counter
from functools import lru_cache

from tools.thesis_main.analysis.prepare_uncertainty_visual_review import OUT, ROOT, helpers, studio_data, write_json
from tools.thesis_main.analysis.upgrade_uncertainty_review_hd import paired_payload, overlay_svg


def ring_edges(order):
    return {tuple(sorted((order[i], order[(i+1) % len(order)]))) for i in range(len(order))}


def audit():
    reader, _ = helpers()
    versions = [json.loads(line) for line in (ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1/raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()]
    canonical = {r['canonical_annotation_id']:r for r in versions if r['selected_canonical_version']=='true'}
    proposals = {(r['case_id'],r['variant']):r for r in json.loads((OUT/'preview_adjustment_proposals.json').read_text(encoding='utf-8')) if 'panel' in r}
    @lru_cache(maxsize=None)
    def raw_export(path):
        return json.loads((ROOT/path).read_text(encoding='utf-8'))
    rows = []
    for case in sorted((OUT/'cases').glob('V*')):
        studio = studio_data((case/'hd/studio/data.js').read_text(encoding='utf-8'))['cases'][0]
        by_source = {v['source']['source_id']:v for v in studio['variants']}
        logs = {r['variant']:r for r in json.loads((case/'render_log.json').read_text(encoding='utf-8'))}
        for path in sorted(case.glob('*_source.json')):
            source = json.loads(path.read_text(encoding='utf-8'))
            name = path.stem.removesuffix('_source'); points = source['points']
            payload = json.loads((case/'hd'/(name+'.json')).read_text(encoding='utf-8'))
            row = dict(case_id=case.name, variant=name, source_id=source['source_id'], points=len(points),
                       role_swapped_pairs=0, role_reading_error='', author_adjacency_verified=False,
                       raw_export_checked=False, raw_export_has_relations=None,
                       preview_proposal=(case.name,name) in proposals)
            try:
                expected = paired_payload(points, reader)
            except ValueError as error:
                row['role_reading_error'] = str(error)
                assert payload['parse_error']==str(error) and payload['unparsed_original_points']==points
                assert payload['ordered_pairs']==[]
            else:
                assert payload==expected
                ids = [int(p['source_pair_id'].split(':')[1].split('/')[0]) for p in payload['ordered_pairs']]
                assert [i//2 for i in ids]==list(range(len(points)//2))
                row['role_swapped_pairs'] = sum(i%2 for i in ids)
            studio_variant = by_source[source['source_id']]
            if 'geometry' not in studio_variant:
                assert row['role_reading_error'] and studio_variant['error'] and payload['ordered_pairs']==[]
            geometry = studio_variant.get('geometry',{'pairs':[]})
            for actual, p in zip(geometry['pairs'],payload['ordered_pairs']):
                assert actual['source_pair_id']==p['source_pair_id']
                assert actual['top']==[p['top']['x'],p['top']['y']]
                assert actual['bottom']==[p['bottom']['x'],p['bottom']['y']]
            assert len(geometry['pairs'])==len(payload['ordered_pairs'])
            assert (case/'hd'/(name+'.svg')).read_text(encoding='utf-8')==overlay_svg(points,reader)
            try:
                reader.footprint(points)
                row['export_order_geometry_status']='computable'
                assert logs[name]['status']=='rendered_unreviewed'
            except ValueError as error:
                row['export_order_geometry_status']=str(error)
                assert logs[name]['status']=='failed'
            if source['name'].startswith('human_'):
                v = canonical[source['source_id']]
                tasks=[t for t in raw_export(v['source_path']) if str(t['id'])==v['runtime_task_id']]
                assert len(tasks)==1
                anns=[a for a in tasks[0]['annotations'] if str(a['id'])==v['raw_annotation_id']]
                assert len(anns)==1
                result=anns[0]['result']; kp=[r for r in result if r.get('type')=='keypointlabels']
                actual=[[r['value']['x']*1024/100,r['value']['y']*512/100] for r in kp]
                assert actual==points==v['points_1024x512']
                row.update(raw_export_checked=True, raw_export_has_relations=any(r.get('type')=='relation' for r in result),
                           raw_result_types=sorted({r.get('type','') for r in result}), source_path=v['source_path'],
                           raw_annotation_id=v['raw_annotation_id'], runtime_task_id=v['runtime_task_id'])
            if row['preview_proposal']:
                proposal=proposals[(case.name,name)]; mapping=proposal['old_point_id_for_new_index']
                assert proposal['original_points']==points
                assert sorted(mapping)==list(range(len(points)))
                assert proposal['preview_points']==[points[i] for i in mapping]
                row.update(proposal_point_map=mapping, proposal_pairing_changed=proposal['pairing_changed'],
                           proposal_ring_edge_set_changed=(True if proposal['pairing_changed'] else ring_edges([i//2 for i in mapping[::2]])!=ring_edges(list(range(len(points)//2)))),
                           proposal_applied_to_hd_or_studio=False)
            rows.append(row)
    assert len(rows)==280 and len({r['case_id'] for r in rows})==50
    summary=dict(images=50,layout_variants=len(rows),human_raw_exports_checked=sum(r['raw_export_checked'] for r in rows),
                 display_coordinate_checks_passed=True,hd_and_studio_group_order_changes=0,
                 role_swapped_layouts=sum(r['role_swapped_pairs']>0 for r in rows),role_swapped_pairs=sum(r['role_swapped_pairs'] for r in rows),
                 role_reading_failures=sum(bool(r['role_reading_error']) for r in rows),
                 preview_proposals=sum(r['preview_proposal'] for r in rows),
                 proposal_cases=sorted({r['case_id'] for r in rows if r['preview_proposal']}),
                 proposal_pairing_changes=sum(r.get('proposal_pairing_changed',False) for r in rows),
                 export_order_status_counts=dict(Counter(r['export_order_geometry_status'] for r in rows)),
                 author_intended_order_verified=0, new_whole_scene_visual_reviews=0)
    write_json(OUT/'ORDER_AUDIT.json',dict(summary=summary,layouts=rows))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    audit()
