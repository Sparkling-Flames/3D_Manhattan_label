import copy
import numpy as np
import pytest

from tools.thesis_main.analysis import difficulty_wild_run as run
from tools.thesis_main.analysis import difficulty_wild_inputs as inputs
from tools.thesis_main.analysis import difficulty_wild_sampler as sampler
from tools.thesis_main.analysis.difficulty_wild_quality import Evaluator


@pytest.mark.parametrize('n,need', [(0,35),(7,28),(34,1),(35,0),(40,0)])
def test_target_population_and_capped_budget(n,need):
    s=dict(difficulty={'house_a':dict(image='h-01',difficulty_class='困难')},
           counts={'house_a':n}, models={'house_a':{'HoHoNet':{}}})
    row=run.targets(s,20261017)[0]
    assert row['need']==need and row['real_manual_n']==n
    assert row['wild_budget_k']<=need
    if need==0: assert row['wild_budget_k']==0


def test_new_mode_rejects_semi_before_writes(tmp_path):
    from tools.thesis_main.analysis.personality_incremental_run import run_incremental
    with pytest.raises(ValueError,match='manual_only'):
        run_incremental(tmp_path/'run',1,['manual','semi'],'fill-to-35-wild')
    assert not (tmp_path/'run').exists()


def test_profiles_never_see_target_building(monkeypatch):
    records=[dict(worker_id='1',building_id='train'),dict(worker_id='2',building_id='held')]
    def axis(training,field,log=False):
        assert all(r['building_id']=='train' for r in training)
        return {'1':dict(effect=2.,supported=True)}
    monkeypatch.setattr(inputs,'estimate_axis',axis)
    p=inputs.fit_profiles(records,'held')
    assert set(p)=={'1'} and p['1']['quality']=='higher'
    assert p['1']['training_buildings']==['train']
    assert p['1']['quality_version']=='WQ-B8L2-20261015'


def test_bad_gt_not_scored():
    e=object.__new__(Evaluator)
    result=e.evaluate([],dict(difficulty_target_id='bad',gt_error_excluded=True))
    assert result['status']=='gt_error_excluded' and result['B8L2'] is None


def test_floor_reference_never_invents_top():
    e=object.__new__(Evaluator)
    e.sources={'v6_references':{'floor':dict(full_reference_available=False)}}
    result=e.evaluate([],dict(difficulty_target_id='floor',gt_error_excluded=False,reference_full_available=False))
    assert result['status']=='floor_only' and result['B8L2'] is None and result['D10'] is None


def test_missing_reference_explicit():
    e=object.__new__(Evaluator);e.sources={'v6_references':{}}
    result=e.evaluate([],dict(difficulty_target_id='missing',gt_error_excluded=False))
    assert result['status']=='unavailable' and result['B8L2'] is None


def test_empirical_calibration_source_trace():
    d=dict(annotation_id='a',building_id='train',count_offset=-2,delta=[[[1,2],[1,3]]])
    result=sampler.calibrate([d])
    assert result['deletion_counts']==[2] and result['missing_frequency']==1.
    assert result['source_annotation_ids']==['a'] and result['source_buildings']==['train']
    assert result['cap']==[[1.,2.],[1.,3.]]


def test_same_seed_sample_does_not_mutate_sources(monkeypatch):
    # Running the sampler repeatedly must not mutate the shared residual bank.
    points=np.array([p for x in [50,300,550,800] for p in [(x,140),(x,380)]])
    severity=dict(delta=[[[4,5],[4,-5]]],cap=[[10,10],[10,10]],deletion_counts=[1],missing_frequency=.5)
    original=copy.deepcopy(severity)
    a,info=sampler.wild_edit(points,points,np.random.default_rng(8),severity,['partial_corner'])
    b,again=sampler.wild_edit(points,points,np.random.default_rng(8),severity,['partial_corner'])
    assert np.array_equal(a,b) and info==again and severity==original


def test_repeated_template_has_empirically_varied_geometry(monkeypatch):
    points=[[x,y] for x in [50,300,550,800] for y in [140,380]]
    donor=dict(worker_id='1',annotation_id='donor',family='HoHoNet',base_pairs=4,count_offset=0,
               delta=[[[2,3],[2,-3]]]*4,building_id='train',image_id='train_i')
    profile=dict(quality='higher',speed='faster')
    fitted=dict(heldout='held',profiles={'1':profile},quality_donors={'higher':[donor]},
        calibration={'higher':dict(cap=[[10,10],[10,10]],amplitude_iqr=[1.,4.],quantile=.95)},
        times=[dict(worker_id='1',annotation_id='donor',active_time_seconds=10.,lead_time_seconds=12.,
                    lead_time_is_active_time=False,building_id='train')])
    sources=dict(models={'held_i':{'HoHoNet':dict(points=points,layout_id='m')}},
        difficulty={'held_i':dict(image='held-1',gt_error_excluded=False,reference_full_available=True,
            difficulty_class='简单',difficulty_version='test_v6',difficulty_target_id='ref')},
        scope=[dict(image_id='held_i',worker_scope='in_scope',object_id='scope',building_id='held')],
        pending={},manifest={'commit':'fixture'})
    target=dict(image_id='held_i',building_id='held',wild_budget_k=0,need=35,real_manual_n=0)
    monkeypatch.setattr(run,'choose_donor',lambda *a,**kw:(donor,'personal',{'personal':1.}))
    a=run.sample_row(sources,target,fitted,3,0,0)
    b=run.sample_row(sources,target,fitted,3,1,0)
    again=run.sample_row(sources,target,fitted,3,0,0)
    assert a==again and a['points']!=b['points'] and a['export_worker_id']!=b['export_worker_id']
    assert 1<=a['empirical_residual_amplitude']<=4
