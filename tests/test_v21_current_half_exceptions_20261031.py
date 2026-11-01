import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.refresh_v21_half_exceptions_20261031 import OUT, UP, aggregate, classify


def test_current_membership_and_weighting():
    source = pd.read_csv(UP/'HALF_EVENT_LEGALITY.csv.gz', low_memory=False)
    source = source[source.n.eq(14) & source.updated_class_legal]
    events = pd.read_csv(OUT/'CURRENT_147_EVENTS.csv.gz', low_memory=False)
    assert set(source.event_id) == set(events.event_id)
    images = pd.read_csv(OUT/'ALL_69_IMAGE_RESULTS.csv')
    result = aggregate(events, ['gap_A','gap_sym','CB'])
    np.testing.assert_allclose(result[['gap_A','gap_sym','CB']], images[['gap_A','gap_sym','CB']], equal_nan=True)
    counts = json.loads((OUT/'CHECKS.json').read_text(encoding='utf-8'))
    assert counts['GA_nonpositive']==14 and counts['GS_nonpositive']==18
    assert counts['CB_nonpositive']==3 and counts['no_joint_Q']==2
    assert counts['diagnostic_images']==30 and counts['diagnostic_events']==63
    assert counts['GS_nonpositive_but_CB_positive']==17
    assert counts['supplemented_trace_teams']==6 and counts['new_physical_teams']==0


def test_absent_quality_is_not_zero_and_partial_status_is_retained():
    frame = pd.DataFrame({'gap_A':[np.nan,1,-1], 'gap_sym':[np.nan,1,1], 'CB':[np.nan,1,1], 'partial_events':[True,True,False]})
    flags = classify(frame)
    assert flags.GA_nonpositive.tolist()==[False,False,True]
    assert flags.no_joint_Q.tolist()==[True,False,False]
    assert flags.diagnostic.all() and not flags.numeric_exception.iloc[1]


def test_every_case_event_has_exact_arms_votes_and_current_labels():
    html = (OUT/'viewer.html').read_text(encoding='utf-8')
    payload = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)[1])
    events = pd.read_csv(OUT/'DIAGNOSTIC_63_EVENTS.csv.gz',low_memory=False)
    assert set(payload['events'])==set(events.event_id) and len(payload['images'])==30
    assert '最终分类尚未选定' not in html and '197事件综合口径' not in html
    votes = pd.read_csv(OUT/'VOTE_GROUPS.csv.gz')
    assert votes.support.eq(votes.D_support+votes.replacement_support).all()
    assert votes.selected.eq(votes.support.ge(7)).all()
    facts = pd.read_csv(OUT/'ARM_MECHANISM_FACTS.csv')
    assert len(facts)==189 and not facts.duplicated(['event_id','arm']).any()
    for r in events.to_dict('records'):
        p = payload['pools'][r['pool_id']]
        for arm,block in zip('ABC','XYZ'):
            tr = payload['teams'][r[arm+'_team_key']]
            assert set(tr['member_workers']) == set((r['D']+'|'+r[block]).split('|'))
            assert tr['full_state']['minimum_support']==7
            assert p['frozen_lobo_labels'][r[block].split('|')[0]]['class_id'] in ['C2','C3']
        assert payload['events'][r['event_id']]['current_explanation']
    failed = facts[facts.score_status.eq('no_connection')]
    assert failed.source_complete_projected_rings.eq(0).all()
    assert failed.selected_unresolved_locations.eq(0).all()
