import numpy as np
import pandas as pd
from tools.thesis_main.analysis.same_room_multiview_20261020 import splits, source_prediction, declared_groups, replay_orders


def test_seven_views_have_35_21_7_majority_splits_and_no_target_overlap():
    rows=list(splits(list('abcdefg')))
    assert [sum(len(h)==m for h,v in rows) for m in (4,5,6)]==[35,21,7]
    assert all(set(h).isdisjoint(v) and set(h)|set(v)==set('abcdefg') for h,v in rows)
    assert list(splits(['a','b']))==[]


def test_source_prediction_ignores_target_and_weights_images_equally():
    values=pd.Series({'a':10.,'b':30.,'target':999.})
    assert source_prediction(values,['a','b'])==20
    values['target']=-100
    assert source_prediction(values,['a','b'])==20


def test_declared_groups_do_not_create_transitive_rooms():
    declarations=[dict(code='ab',images=['a','b']),dict(code='bc',images=['b','c'])]
    relations={('a','b'),('b','c')}
    groups=declared_groups(declarations,{'a','b','c'},relations)
    assert not groups
    declarations.append(dict(code='abc',images=['a','b','c']))
    assert not declared_groups(declarations,{'a','b','c'},relations)
    relations.add(('a','c'))
    assert len(declared_groups(declarations,{'a','b','c'},relations))==1


def test_replay_orders_are_real_permutations_and_reproducible():
    a=replay_orders(['a','b','c'],256)
    assert len(a)==6 and len(set(map(tuple,a)))==6
    assert a==replay_orders(['c','b','a'],256)
    assert all(sorted(x)==['a','b','c'] for x in a)
