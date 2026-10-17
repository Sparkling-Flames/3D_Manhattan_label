import csv

from tools.thesis_main.analysis import worker_archetype_quadrants as q


def write_rows(path, rows):
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_manual_speed_rejects_partial_and_nonformal_time(tmp_path, monkeypatch):
    path = tmp_path / 'evidence.csv'
    base = dict(worker_id='001', active_time_seconds='30', assistance_exposure='none',
                time_active_time_formal_available='true', active_time_owner_valid_status='owner_valid_complete')
    write_rows(path, [base, dict(base, active_time_seconds='900', active_time_owner_valid_status='partial_session_coverage_excluded_from_speed'),
                      dict(base, active_time_seconds='500', time_active_time_formal_available='false')])
    monkeypatch.setattr(q, 'EVIDENCE', path)
    result = q.load_time()['W001']
    assert result['times'] == result['manual_times'] == [30.]
    assert result['n'] == 3


def test_quality_uses_only_original_reference(tmp_path, monkeypatch):
    answers, profiles = tmp_path / 'answers.csv', tmp_path / 'profiles.csv'
    write_rows(answers, [dict(worker='P001', version='original', iou='.4'),
                        dict(worker='P001', version='manual_revision', iou='.99')])
    write_rows(profiles, [dict(worker='P001', policy='original', mean_iou='.4', median_iou='.4',
                              descriptive_iou_rank='1', image_n='1')])
    monkeypatch.setattr(q, 'ANSWER_METRICS', answers)
    monkeypatch.setattr(q, 'PROFILES', profiles)
    assert q.load_quality()['P001']['iou'] == [.4]
