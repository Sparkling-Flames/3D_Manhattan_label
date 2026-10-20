import numpy as np
import pandas as pd
from tools.thesis_main.analysis.difficulty_mechanisms_v2_20261020 import reference_traits, paired_conditions


def test_reference_traits_do_not_count_straight_insertions_as_turns():
    box=np.array([[-1,-1],[0,-1],[1,-1],[1,1],[-1,1]])
    x=reference_traits(box)
    assert x['ref_vertices']==5 and x['ref_turn5']==4 and x['ref_short_edges']==0


def test_person_condition_comparison_requires_observed_support_both_sides():
    f=pd.DataFrame([dict(worker_id='w1',image_code='a',mechanism='plain',reduced=False),
                    dict(worker_id='w1',image_code='b',mechanism='hidden',reduced=True),
                    dict(worker_id='w2',image_code='a',mechanism='plain',reduced=False)])
    p=paired_conditions(f,'plain','hidden',minimum_images=1)
    assert len(p)==1 and p.iloc[0].worker_id=='w1' and p.iloc[0].rate_delta==1
