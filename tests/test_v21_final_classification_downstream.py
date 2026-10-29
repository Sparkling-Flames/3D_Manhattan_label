import pandas as pd
import pytest

from tools.thesis_main.analysis.continue_v21_final_classification_20261029 import classify_blocks, image_summary


def test_blocks_need_known_homogeneous_distinct_classes():
    labels = {'a': 'C1', 'b': 'C1', 'c': 'C2', 'd': 'C3'}
    assert classify_blocks({'a'}, {'b'}, {'c'}, labels)[0] == '当前适用'
    assert classify_blocks({'a'}, {'c'}, {'d'}, labels)[0] == '需改解释'
    assert classify_blocks({'a'}, {'b'}, {'a'}, labels)[0] == '需改解释'
    assert classify_blocks({'a'}, {'b'}, {'unknown'}, labels)[0] == '冻结历史对照'


def test_equal_background_block_image_weight_and_empty_support():
    # Repeated events in one background must not outweigh a separate background.
    rows = [('i1','b1','d1',0), ('i1','b1','d1',0), ('i1','b1','d2',10),
            ('i1','b2','d3',15), ('i2','b3','d4',30)]
    frame = pd.DataFrame(rows, columns=['image','block_id','background_id','gap_A'])
    frame['building']='building';frame['pool_id']=frame.image
    frame['gap_sym']=frame.gap_A;frame['CB']=frame.gap_A
    result=image_summary(frame)
    assert result['gap_A'] == pytest.approx(20)  # i1=(5+15)/2; i2=30
    assert result['valid_images'] == 2
    empty=image_summary(frame.iloc[:0])
    assert empty['valid_images'] == 0 and pd.isna(empty['gap_A'])
    assert empty['support_state'].startswith('无剩余支持')
