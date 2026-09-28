from tools.thesis_main.analysis.audit_presentation_inventory_20260922 import coverage


def test_coverage_counts_unique_images_and_keeps_missing():
    row = coverage('model', {'a', 'b'}, {'a', 'b', 'c'}, {'b', 'c'}, {'a'})
    assert row['pool_images'] == 2 and row['pool_denominator'] == 3
    assert row['human_images'] == 1 and row['missing_human_ids'] == ['c']
    assert row['prediction_images'] == 1
