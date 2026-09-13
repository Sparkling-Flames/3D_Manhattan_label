import unittest

from tools.thesis_main.analysis.build_stage1_image_packages_20260913 import check_pairs, draft_worker


class PackageChecks(unittest.TestCase):
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
