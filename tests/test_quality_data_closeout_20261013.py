from tools.thesis_main.analysis.quality_data_closeout_20261013 import permitted_use


def test_computable_score_never_restores_exclusion_or_holdout():
    assert permitted_use('held_or_diagnostic',True,True)=='historical_diagnostic_only'
    assert permitted_use('manual_development_candidate',True,True)=='historical_diagnostic_only'
    assert permitted_use('severe_exception_candidate',False,True)=='separate_reviewed_severe_diagnostic'


def test_manual_and_semi_keep_separate_even_when_both_computable():
    assert permitted_use('manual_development_candidate',False,True)=='manual_conditional_comparison'
    assert permitted_use('semi_secondary_candidate',False,True)=='separate_semi_conditional_diagnostic'
    assert permitted_use('manual_development_candidate',False,False)=='explicitly_unavailable_no_score_imputed'
