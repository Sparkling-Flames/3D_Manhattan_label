from pathlib import Path

import pandas as pd

from research.workers.personnel_profiles_composition_20261020.integrate import common_pair, selected


def test_common_images_never_cross_reference_or_condition():
    frame = pd.DataFrame([
        dict(worker_id='W001', task_key='image|ref1', condition='manual', B8L2=80),
        dict(worker_id='W002', task_key='image|ref1', condition='manual', B8L2=90),
        dict(worker_id='W002', task_key='image|ref2', condition='manual', B8L2=1),
        dict(worker_id='W002', task_key='image|ref1', condition='semi', B8L2=2),
    ])
    for column, value in dict(quality_usable=True, Q_panel='ordinary', panel='ordinary',
                              origin='new', image_id='image', building_id='building',
                              B8L2_peer_recomputed=0).items():
        frame[column] = value
    row = common_pair(frame, 'W001', 'W002', 'manual')
    assert row['images'] == 1 and row['Q_b'] == 90 and row['Q_a'] == 80


def test_archive_omits_raw_review_text_and_repeated_resources():
    assert not selected(Path('tables/profiles/worker_exclusion_reasons.csv'))
    assert not selected(Path('mechanisms/images/original.png'))
    assert not selected(Path('mechanisms/fonts/font.ttf'))
    assert not selected(Path('MANIFEST.json'))
    assert selected(Path('design/quality/requests.json.gz'))
    assert selected(Path('claims/claim_teams.json.gz'))
