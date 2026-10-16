import copy
import json
from pathlib import Path
import pytest
from tools.thesis_main.analysis.difficulty_scope_resolution_20261016 import receive_records


def test_receipt_only_imports_two_requested_confirmed_spaces():
    repo=Path(__file__).resolve().parents[1]
    receipt=json.loads((repo/'analysis_results/research_input_20260929/scope_receipt_20261016.json').read_text(encoding='utf-8-sig'))
    records=receive_records(receipt)
    assert len(records)==2 and all(r['space_scope_confirmed'] for r in records)
    broken=copy.deepcopy(receipt)
    row=next(r for r in broken['records'] if r['image_code']=='S9hNv5qa7GM-09')
    row['space_regions']['regions'][0]['floor_region_confirmed']=False
    with pytest.raises(ValueError):receive_records(broken)
