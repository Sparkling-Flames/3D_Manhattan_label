from tools.thesis_main.analysis.difficulty_user_adoption_20261016 import adopt


def row(grade, excluded=False):
    return dict(image_id='i',target_version='t',current_class='中等',conditional_difficulty='中等',
        evidence='旧依据',classification_basis='old',gt_error_excluded=excluded,
        difficulty_analysis_eligible=not excluded,difficulty_analysis_exclusion='gt_error' if excluded else '',
        latest_user_review=dict(image_id='i',target_version='t',grade=grade))


def test_adopts_user_grade_without_changing_old_evidence():
    r=row('困难');adopt(r)
    assert r['current_class']=='困难' and r['class_before_user_adoption']=='中等'
    assert r['difficulty_analysis_eligible'] and r['evidence_before_user_adoption']=='旧依据'


def test_no_grade_or_error_never_unblocks_analysis():
    r=row('');adopt(r);assert r['current_class']=='中等'
    r=row('简单',True);r['current_class']='待修正GT';adopt(r)
    assert r['current_class']=='待修正GT' and not r['difficulty_analysis_eligible']
    r=row('简单');r.update(difficulty_analysis_eligible=False,difficulty_analysis_exclusion='special_or_pending')
    adopt(r)
    assert r['current_class']=='简单' and not r['difficulty_analysis_eligible']
