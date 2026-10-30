import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/thesis_main/analysis'))
from correct_doorway_manhattan_20261031 import axis, OUT, PREP


def test_slanted_or_degenerate_cut_rejected():
    for line in [[[0,0],[.01,1]],[[0,0],[0,0]]]:
        with pytest.raises(ValueError):axis({'line':line,'side':1})


def test_submission_priority_and_manhattan_axes():
    rows=json.loads((OUT/'ZIP_USER_CUT_COMPARISON.json').read_text(encoding='utf8'))
    assert len(rows)==20
    assert [r['image'] for r in rows if r['user_differs_from_zip']]==['B6ByNegPMKs-42']
    for r in rows:
        assert r['current_cuts']==r['user_cuts']
        assert axis(r['current_cuts'][0])==axis(r['current_cuts'][1])
    b6=next(r for r in rows if r['image']=='B6ByNegPMKs-42')
    assert axis(b6['current_cuts'][0])==0
    assert [cut['line'][0][0] for cut in b6['current_cuts']]==[.022453955495470402,.125]


def test_oos_and_pending_not_promoted():
    rows=json.loads((OUT/'ALIGNMENT_DECISIONS.json').read_text(encoding='utf8'))
    assert sum(r['status']=='manhattan' for r in rows)==17
    assert sum(r['status']=='excluded' for r in rows)==2
    q9=next(r for r in rows if r['image']=='q9vSo1VnCiC-24')
    assert q9['status']=='uncertain' and q9['cuts'] is None
    assert all(not r['reference_adopted'] for r in rows)
