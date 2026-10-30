import json
from pathlib import Path
import pandas as pd
from PIL import Image

OUT=Path(__file__).resolve().parents[1]/'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031'

def test_every_eligible_alliance_has_native_output():
    d=pd.read_csv(OUT/'ALLIANCE_RESULTS.csv')
    assert len(d)==3160
    assert not d.duplicated(['version','pool_id','classes','unknown_background_included']).any()
    assert d.loc[d.n.ge(3),'status'].notna().all()
    assert d.status.eq('capacity_only').eq(d.n.lt(3)).all()
    checks=json.loads((OUT/'VERIFICATION.json').read_text())
    assert checks['completed_native_requests']==290 and checks['saved_scalar_teams_checked']==12
    assert checks['historical_endpoint_geometry_max_diff']<1e-8
    assert checks['unchanged_alliance_rows']==1166
    resolved=pd.read_csv(OUT/'ALLIANCE_414_RESOLUTION.csv')
    assert len(resolved)==414 and resolved.resolved.all()
    assert resolved.status.eq('capacity_only').sum()==11

def test_full_team_is_fixed_and_comparison_support_is_explicit():
    d=pd.read_csv(OUT/'FULL_VS_BEST_PURE_COMMON.csv')
    assert d.full_Q_frozen.eq(d.full_Q_updated).all()
    p=d[d.scope.eq('primary')&~d.unknown_background_included]
    assert len(p)==205 and p.image.nunique()==205
    assert p.full_minus_best_pure_frozen.lt(-1e-8).sum()==173
    assert p.full_minus_best_pure_updated.lt(-1e-8).sum()==169
    for ext in ['png','pdf','svg']:assert (OUT/f'ALL_CLASS_VS_PURE.{ext}').stat().st_size>1000
    with Image.open(OUT/'ALL_CLASS_VS_PURE.png') as im:assert abs(im.info['dpi'][0]-300)<1
