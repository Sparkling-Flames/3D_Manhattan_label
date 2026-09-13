import unittest
import json
from pathlib import Path

from tools.thesis_main.analysis.build_stage1_image_packages_20260913 import check_pairs, draft_worker, mild_order, optional_pool


class PackageChecks(unittest.TestCase):
    def test_generated_three_project_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        base = root / 'import_json/scene_stability_stage1_20260913_v2'
        read = lambda name: json.loads((base / name).read_text(encoding='utf-8'))
        rows = read('required_assignments.json')
        exposure = {(r['worker_id'], r['image_id']) for r in read('historical_exposure.json')}
        self.assertEqual(len(rows), 480)
        self.assertFalse({(r['worker_id'], r['image_id']) for r in rows} & exposure)
        pending = {r['image_id'] for r in read('pending_doorway_adoption.json')}
        ids = {}
        for project, count in [('zh_required', 37), ('en_required', 37), ('en_optional', 20)]:
            names = {'zh_required': '任务7', 'en_required': 'Project G', 'en_optional': 'Project H'}
            tasks = read('label_studio_import/' + names[project] + '.json')
            self.assertEqual(len(tasks), count)
            ids[project] = {t['data']['base_task_id'] for t in tasks}
            self.assertFalse(ids[project] & pending)
            for t in tasks:
                self.assertEqual(set(t), {'data'})
                self.assertNotIn('?', t['data']['vis_3d'])
                self.assertEqual(t['data']['vis_3d'], 'http://175.178.71.217:8000/tools/vis_3d.html' if project == 'zh_required' else 'https://label.sparkle0825.top/tools/vis_3d.html')
                self.assertEqual(t['data']['project_display_name'], names[project])
                self.assertEqual(t['data']['annotation_form_version'], 'manual_scope_only_v1')
                self.assertFalse({'scope_gold', 'gt', 'prediction', 'assigned_workers'} & set(t['data']))
        self.assertEqual(ids['zh_required'], ids['en_required'])
        self.assertFalse(ids['en_required'] & ids['en_optional'])
        self.assertEqual(len(pending), 0)
        decision = read('ProjectH_用户复核原文.json')['decisions']
        self.assertTrue({r['image_id'] for r in decision if r['decision'] == '采用到Project H'} <= ids['en_optional'])
        self.assertFalse({r['image_id'] for r in decision if r['decision'] == '备选'} & ids['en_optional'])
        self.assertEqual({p.name for p in (base / 'label_studio_import').glob('*.json')}, {'任务7.json', 'Project G.json', 'Project H.json'})
        project_h = next(p for p in read('projects.json') if p['project_key'] == 'en_optional')
        self.assertIsNotNone(project_h['import_file'])
        self.assertEqual(project_h['personal_hard_cap'], 20)
        self.assertEqual(project_h['image_pool_limit'], 20)
        from collections import Counter
        counts = Counter(r['worker_id'] for r in rows)
        self.assertEqual(set(counts.values()), {20, 30})
        selection = json.loads((root / 'analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json').read_text(encoding='utf-8'))
        image_counts = Counter(r['image_id'] for r in rows)
        selected_groups = {r['batch'] for r in rows}
        self.assertEqual(selected_groups, {'G172','G184','G179','G178','G047','G237'})
        for r in selection['images']:
            if r['status'] == '确定采用' and r['group'] in selected_groups:
                eligible = {w for w in selection['future_workers'] if (w,r['image_id']) not in exposure}
                self.assertEqual(image_counts[r['image_id']], min(r['new_needed'],len(eligible)))

    def test_order_and_open_pool_contract(self):
        rows = [dict(image_id=str(i), batch=str(i // 4), order=i + 1) for i in range(20)]
        ordered, swaps = mild_order(rows, 1, 'zh')
        self.assertEqual({r['image_id'] for r in rows}, {r['image_id'] for r in ordered})
        self.assertEqual(len(swaps), 2)
        self.assertEqual(len({x for pair in swaps for x in pair}), 4)
        self.assertEqual(mild_order(rows, 1, 'zh'), (ordered, swaps))
        pool = optional_pool({'a', 'b'}, {'a'}, {28, 29}, {'a': {28}, 'b': set()})
        self.assertEqual(pool[0]['eligible_workers'], [29])
        self.assertEqual([r['image_id'] for r in pool if r['ready_for_import']], ['a'])
        self.assertNotIn('assigned_workers', pool[0])
        self.assertNotIn('cap', pool[0])

    def test_assignment_rejects_duplicate_exposure_and_inactive_worker(self):
        rows = [dict(worker_id=1, image_id='a'), dict(worker_id=2, image_id='a')]
        check_pairs(rows, {1, 2}, {'a': {3}})
        for bad in [rows + rows[:1], [dict(worker_id=3, image_id='a')]]:
            with self.assertRaises(AssertionError):
                check_pairs(bad, {1, 2, 3}, {'a': {3}})
        with self.assertRaises(AssertionError):
            check_pairs(rows, {1}, {})

    def test_draft_identity_requires_explicit_export_id(self):
        self.assertEqual(draft_worker({'created_username': 'example, 028'}), 28)
        with self.assertRaises(ValueError):
            draft_worker({'created_username': 'example'})


if __name__ == '__main__':
    unittest.main()
