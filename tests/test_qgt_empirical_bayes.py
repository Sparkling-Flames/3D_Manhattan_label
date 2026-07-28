import math

from tools.thesis_main.analysis.c1_task_adjusted_quality import normal_normal_empirical_bayes


def test_low_precision_worker_shrinks_more_and_intervals_are_nonzero():
    rows, audit = normal_normal_empirical_bayes([.2, .8, .9], [.3, .03, .02])
    assert rows[0]["shrinkage_factor"] < rows[2]["shrinkage_factor"]
    assert .2 < rows[0]["estimate"] < audit["eb_mu"]
    assert all(math.isfinite(row["estimate"]) and row["upper"] > row["lower"] for row in rows)
