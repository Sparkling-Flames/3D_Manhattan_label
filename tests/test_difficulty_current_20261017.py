import pandas as pd
from tools.thesis_main.analysis.difficulty_current_20261017 import summarize


def test_compatible_targets_and_diagnostic_scores_do_not_leak():
    rows=[]
    for i, (usable,target,b,d) in enumerate([(True,'a',80,82),(True,'b',90,91),(False,'a',None,None)]):
        rows.append(dict(object_id=str(i),image_id='im',worker_id=str(i),quality_usable=usable,
            rescore_target_id=target,difficulty_target_id='a',B8L2=b,D10=d,diagnostic_B8L2=99,
            calculation_status='full_computed'))
    s=summarize(pd.DataFrame(rows),compatible=True)
    assert s['quality_n']==1 and s['B8L2_mean']==80 and s['D10_mean']==82
    assert s['quality_other_target_n']==1 and s['computed_not_quality_n']==1
    assert s['inventory_n']==3 and s['B8L2_image_equal_mean']==80
