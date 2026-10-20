import pandas as pd
from tools.thesis_main.analysis.speed_difficulty_mechanisms_20261021 import summarize, actual_pairs


def test_summary_does_not_weight_replicates_or_large_buildings_as_independent_images():
    f = pd.DataFrame([dict(layer='x',building='a',image_id='i',quality_difference=10)]*4+
                     [dict(layer='x',building='a',image_id='j',quality_difference=0),
                      dict(layer='x',building='b',image_id='k',quality_difference=-5)])
    s = summarize(f, ['layer'], ['quality_difference']).iloc[0]
    assert s.quality_difference == 0 and s.images == 3 and s.buildings == 2


def test_unscored_comparison_stays_missing_instead_of_becoming_zero_quality_change():
    f = pd.DataFrame([dict(layer='x',building='a',image_id='i',quality_difference=None,both_scored=False),
                      dict(layer='x',building='a',image_id='j',quality_difference=8,both_scored=True)])
    s = summarize(f, ['layer'], ['quality_difference','both_scored']).iloc[0]
    assert s.quality_difference == 8 and s.scored_comparisons == 1 and s.images_with_any_unscored == 1


def test_pair_exposure_excludes_retained_slow_person():
    r = dict(panel_id='p',base_team_key='b',candidate_team_key='c',image='i',layer='ordinary_manual',
             condition='manual',mechanism='H0_plain',ref_turn5=4,reference_id='r',common_domains=True)
    teams = {'b':{'member_workers':['s0','s1','s2','s3','s4']},
             'c':{'member_workers':['f0','f1','f2','f3','s4']}}
    history = pd.DataFrame([dict(panel_id='p',fast='f'+str(i),slow='s'+str(i)) for i in range(5)])
    p = actual_pairs(pd.DataFrame([r]), teams, history)
    assert len(p)==4 and 's4' not in set(p.slow)
