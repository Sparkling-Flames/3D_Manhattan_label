import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.build_v21_composition_evidence_20261029 import (
    macro, moments_and_distributions, numeric_check, vector, verify_method,
)


def test_full_vector_includes_zero_classes():
    assert vector("C1:0|C2:3") == {"C1":0,"C2":3}


def test_population_decomposition_and_singleton_distribution():
    values=np.array([0.,2.,4.,np.nan,8.])
    result,dist=moments_and_distributions(values,np.array(["a","a","b","b","c"]))
    assert result["valid_teams"]==4
    assert result["within_variance"]==.5
    assert result["between_variance"]+result["within_variance"]==result["total_variance"]
    by={r["class_counts"]:r for r in dist}
    assert by["a"]["median"]==1 and by["a"]["sd"]==1
    assert by["b"]["teams"]==2 and by["b"]["missing_teams"]==1
    assert np.isnan(by["b"]["sd"]) and np.isnan(by["c"]["range"])


def test_unknown_metric_preserves_missingness():
    result,dist=moments_and_distributions(np.array([np.nan]),np.array(["a"]))
    assert result["valid_teams"]==0 and np.isnan(result["total_variance"])
    assert dist[0]["missing_teams"]==1 and np.isnan(dist[0]["mean"])


def test_numeric_check_rejects_missing_keys():
    a=pd.DataFrame({"id":[1],"v":[2.]})
    b=pd.DataFrame({"id":[2],"v":[2.]})
    with pytest.raises(AssertionError):numeric_check(a,b,["id"],["v"])


def test_macro_is_building_equal_not_team_weighted():
    base=dict(method="m",condition="manual",support="shared_known",metric="B8L2",time_source="not_time")
    rows=[base|dict(building=b,image=i,pool_id=i,total_variance=t,within_variance=t/2,between_variance=t/2)
          for b,i,t in [("A","a",2.),("A","b",6.),("B","c",20.)]]
    result=macro(pd.DataFrame(rows)).iloc[0]
    assert result.total_variance==12 and result.between_share==.5


def test_method_with_no_known_team_retains_empty_distribution_schema():
    panel=dict(panel_id="p",pool_id="q",image="i",building="b",condition="semi",n=1)
    data=dict(vectors={"m":pd.DataFrame([dict(class_counts="",known=False,shared_known=False)])},
              label_maps={"m":{("b","other"):"C1"}},
              prepared=[(panel,np.array([0]),["t"],["unknown"],np.ones((1,1),dtype=np.int16))],
              endpoints=pd.DataFrame([dict(team_key="t",B8L2=np.nan,fusion_turn_n=np.nan,
                                          recorded_time_total_seconds=np.nan,time_source_kinds="unknown")]).set_index("team_key"))
    rows,dist=verify_method(data,"m")
    assert len(rows)==4 and rows.valid_teams.eq(0).all()
    assert dist.empty and "class_counts" in dist and "mean" in dist
