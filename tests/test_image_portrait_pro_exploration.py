"""Regression tests for the new numerical investigation, no images or inference."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler
from tools.thesis_main.analysis.image_portrait.pro_core import OUT,BUNDLE,load,topology_clusters
from tools.thesis_main.analysis.image_portrait.pro_predict import CONFIGS,numeric_grid,clip_predictions
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,COMBOS

@pytest.mark.parametrize('n,p',[(12,5),(12,40),(40,18)])
def test_all_21_grid_fits_match_sklearn(n,p):
    rng=np.random.default_rng(129+p);x=rng.normal(size=(n+3,p));y=rng.uniform(.2,.8,size=(n+3,2));tr=np.arange(n);te=np.arange(n,n+3)
    got,_=numeric_grid(x,y,tr,te,['reference_geometry_error','point_count_disagreement'])
    for j,cfg in enumerate(CONFIGS):
        scaler=StandardScaler().fit(x[tr]);a=scaler.transform(x[tr]);b=scaler.transform(x[te])
        if cfg['pca'] is not None:
            pc=PCA(n_components=min(cfg['pca'],n-1,p),svd_solver='full').fit(a);a=pc.transform(a);b=pc.transform(b)
        m=Ridge(alpha=cfg['parameter']) if cfg['algorithm']=='ridge' else KNeighborsRegressor(n_neighbors=min(cfg['parameter'],n))
        expected=np.clip(m.fit(a,y[tr]).predict(b),0,1)
        np.testing.assert_allclose(got[j],expected,rtol=1e-8,atol=1e-8)


def test_heldout_target_values_do_not_affect_any_fit():
    rng=np.random.default_rng(3);x=rng.normal(size=(13,8));y=rng.uniform(.2,.8,(13,1));tr=np.arange(10);te=np.arange(10,13)
    a,_=numeric_grid(x,y,tr,te,['reference_geometry_error']);y[te]=1e8;b,_=numeric_grid(x,y,tr,te,['reference_geometry_error']);np.testing.assert_array_equal(a,b)


def test_point_counts_never_merge_and_singletons_remain():
    dm=np.array([[0,.01,.001,.8],[.01,0,.001,.8],[.001,.001,0,.8],[.8,.8,.8,0]])
    lab=topology_clusters(dm,[8,8,10,8],.1)
    assert lab[0]==lab[1] and lab[2]!=lab[0] and lab[3]!=lab[0]
    assert sorted(pd.Series(lab).value_counts())==[1,1,2]


def test_all16_information_candidates_retained():
    assert len(COMBOS)==16 and 'quality_time_edit'in COMBOS and 'QTSB'in COMBOS


def test_frozen_folds_exclude_buildings_and_pending_components():
    folds=load(BUNDLE/'evaluation/folds.jsonl.gz');rooms={r['room_id']:r for r in load(BUNDLE/'evaluation/room_components.jsonl')}
    for f in folds:
        assert not set(f['train'])&set(f['test'])
        if f['design']=='same_room_leave_view':
            r=rooms[f['room_id']];assert r['status']=='supported_component';assert set(f['train'])|set(f['test'])==set(r['image_ids'])
        else:assert not {i.split('_')[0]for i in f['train']}&{i.split('_')[0]for i in f['test']}


def test_main_people_identity_and_missing_reference_policy():
    r=pd.read_csv(OUT/'human/response_metrics.csv.gz');q=r[r.main_worker_included]
    assert len(r)==2501 and 'W011'in set(q.worker_id) and not set(q.worker_id)&{'W019','W026'}
    assert not q.duplicated(['image_id','raw_condition','worker_id']).any()
    assert q[q.image_id=='zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b'].quality.isna().all()
    assert len(q[q.raw_condition=='manual'])==1634 and len(q[q.raw_condition=='semi'])==538


def test_profile_cache_matches_physically_filtered_training_rows():
    a=pd.DataFrame(load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));a=a[a.main_worker_included].copy();a['value']=a.value.astype(float)
    excluded=sorted(a.building_id.unique())[:2]
    p,_=ProfileCache(a).fit(excluded);q,_=ProfileCache(a[~a.building_id.isin(excluded)]).fit([])
    p=p.sort_index().sort_index(axis=1);q=q.reindex(index=p.index,columns=p.columns)
    np.testing.assert_allclose(p,q,rtol=1e-8,atol=1e-8,equal_nan=True)


def test_true_combinations_do_not_duplicate_workers():
    a=pd.read_csv(OUT/'E/real_worker_combinations.csv.gz')
    assert len(a)>0
    for n,w in zip(a.people,a.workers):
        ids=w.split(';');assert len(ids)==n==len(set(ids));assert not set(ids)&{'W019','W026'}
    assert not a.combo_id.duplicated().any()


def test_da3_failure_is_reported_not_zero_imputed():
    a=pd.read_csv(OUT/'D/pair_geometry_audit.csv');assert len(a)==316
    c=[k for k in a if 'rotation' in k and ('20' in k)];assert c
    assert not a[c[0]].any()


def test_all_feature_runs_have_explicit_coverage():
    reg=json.loads((OUT/'features/registry.json').read_text());assert len(reg)==72
    for name in reg:
        for suffix in ['.csv.gz','.inner.csv.gz','.coverage.csv']:assert (OUT/'prediction'/(name+suffix)).is_file()
    a=pd.read_csv(OUT/'prediction/DX_target_feedback_matched.csv.gz');assert a.prediction.isna().any()


def test_no_spurious_numeric_epsilon_composition_effect():
    a=pd.read_csv(OUT/'E/fixed_number_marginal_matched_compositions.csv');z=a[a.linear_identity_by_definition]
    assert len(z)>0 and (z.difference==0).all()


def test_strict_mode_stability_cannot_exceed_mass_only_version():
    a=pd.read_csv(OUT/'stability/mode_mass_image_results.csv')
    x=a.pivot(index=['image_id','condition','cut','tv_tolerance'],columns='criterion',values='stability_order_fraction').dropna()
    assert len(x)>0 and (x.every_supported_mode_seen_twice<=x.mass90_only+1e-12).all()
    k=a.dropna(subset=['conditional_median_k']);assert (k.conditional_median_k<=k.n_workers-2).all()


def test_packaged_visual_identity_without_original_images():
    images={a['image_id']for a in load(BUNDLE/'metadata/images.jsonl')};traits=load(BUNDLE/'visual/visual_traits.json');checks=load(BUNDLE/'visual/resolution_recheck.json')['images']
    assert len(images)==len(traits)==648 and images=={a['image_id']for a in traits}
    assert len(checks)==21 and {a['image_id']for a in checks}<=images
