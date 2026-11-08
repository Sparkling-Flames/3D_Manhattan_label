import json
import pandas as pd
from tools.thesis_main.analysis.audit_collinear_scores_20261107 import OUT,BASE,ROOT

def test_all_compacted_references_and_saved_scores():
    stages=json.loads((BASE/'orthogonal_v2_user_axes/REFERENCES.json').read_text(encoding='utf-8'))
    adopted=pd.read_csv(OUT/'REFERENCE_ADOPTION.csv')
    assert set(adopted.target_id)=={r['target_id'] for r in stages if r['raw_nodes']!=r['kept_nodes']}
    assert adopted.actual_pool_reference_matches.all() and adopted.pools.gt(0).all()
    scores=pd.read_csv(OUT/'SCORES.csv.gz')
    assert not scores.duplicated(['pool_id','object_id','stage']).any()
    current=scores[scores.stage.eq('current')]
    assert len(current)==203 and current.B8L2.notna().all()
    assert (current.B8L2-current.stored_B8L2).abs().max()<1e-7
    assert (current.D10-current.stored_D10).abs().max()<1e-7
    assert scores.groupby('stage').size().nunique()==1
