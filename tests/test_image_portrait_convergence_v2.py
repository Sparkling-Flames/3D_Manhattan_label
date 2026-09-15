"""Semantic/numerical regressions for follow-up uncertainty processes; no images."""
import json,collections,itertools
import numpy as np,pandas as pd,pytest
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay,status_for,partition_stats,snapshot
from tools.thesis_main.analysis.image_portrait.convergence_v2_prefix import fit_predict
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,COMBOS


def fixture_group(n=8):
 g=pd.DataFrame(dict(image_id=['test_fixture']*n,raw_condition=['manual']*n,worker_id=[f'W{i:03}'for i in range(n)],canonical_annotation_id=[f'r{i}'for i in range(n)],geometry_valid=[True]*n,effective_point_count=[8]*n,quality=[.05]*n,scope=['normal']*n))
 dense={f'r{i}':np.array([np.full(1024,100+i%2),np.full(1024,400+i%2)])for i in range(n)}
 return g,dense


def test_actual_eight_people_can_be_observed_unified_without_ten():
 g,b=fixture_group();steps,states,_,s=group_replay(g,b,.1,orders=10)
 assert s['n_valid']==8 and len(steps)==80
 assert all(r['state']=='observed_unified'for r in states)
 assert all(r['onset']<=8 for r in states)


def test_singleton_cannot_be_relabelled_as_never_converges():
 assert status_for(8,0,{'supported_mass':.875,'n_supported_modes':1},True)=='cannot_judge_singletons'


def test_invalid_status_separate_from_current_changes():
 assert status_for(8,1,{'supported_mass':1,'n_supported_modes':1},True)=='cannot_judge_invalid'
 assert status_for(8,0,{'supported_mass':1,'n_supported_modes':1},False)=='current_changes'


def test_duplicate_worker_not_extra_support():
 g,b=fixture_group();g.loc[1,'worker_id']=g.loc[0,'worker_id']
 with pytest.raises(AssertionError):group_replay(g,b,.1,orders=1)


def test_clusters_never_mix_point_counts():
 dm=np.zeros((4,4));pc=np.array([8,8,10,10]);l=cluster(dm,pc,.1)
 assert l[0]==l[1] and l[2]==l[3] and l[0]!=l[2]
 assert len(medoids(dm,l,2))==2


def test_all_singletons_provide_no_supported_medoid():
 dm=np.ones((4,4))-np.eye(4);l=cluster(dm,np.array([8]*4),.1)
 assert len(medoids(dm,l,2))==0 and partition_stats(dm,np.array([8]*4),l)['supported_mass']==0


def test_future_excludes_observed_and_terminal_is_missing():
 g,b=fixture_group(4);dm,pc=pairs_for(g,b);dm[3,:3]=dm[:3,3]=1.;l=cluster(dm,pc,.1)
 a,_=snapshot(dm,pc,np.zeros(4),np.array(['normal']*4),l,np.array([0,1,2]),.1)
 assert a['future_n']==1 and a['future_coverage']==0
 a,_=snapshot(dm,pc,np.zeros(4),np.array(['normal']*4),l,np.arange(4),.1)
 assert a['future_n']==0 and np.isnan(a['future_coverage'])


def test_subset_full_total_variation_bound():
 rng=np.random.default_rng(42)
 for n in [4,8,15,24]:
  labels=rng.integers(5,size=n);pn=np.bincount(labels,minlength=5)/n
  for k in range(1,n+1):
   ix=rng.choice(n,k,replace=False);pk=np.bincount(labels[ix],minlength=5)/k
   assert np.abs(pk-pn).sum()/2<=(n-k)/n+1e-12


def test_prefix_model_never_reads_future_outcomes():
 rng=np.random.default_rng(8);x=rng.normal(size=(10,4));y=rng.uniform(size=(10,2));tr=np.arange(8);te=np.array([8,9]);p=fit_predict(x,y,tr,te,10);y[te]=1e9;q=fit_predict(x,y,tr,te,10)
 np.testing.assert_array_equal(p,q)


def test_one_building_has_no_estimable_between_building_interval():
 p=paired_interval(pd.DataFrame({'building':['b','b'],'delta':[.1,.2]}),'delta')
 assert p['groups']==1 and np.isnan(p['lo'])and np.isnan(p['hi'])


def test_primary_exclusions_and_distinct_real_ids():
 r=read_responses();r=r[r.main_worker_included]
 assert len(r)==2388 and set(r.worker_id).isdisjoint({'W019','W026'})and 'W011'in set(r.worker_id)
 assert not r.duplicated(['image_id','raw_condition','worker_id']).any()


def test_all_information_combinations_and_training_exclusion():
 assert len(COMBOS)==16
 a=pd.DataFrame(core.load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));a=a[a.main_worker_included].copy();a['value']=a.value.astype(float);excluded=sorted(a.building_id.unique())[:2]
 p,_=ProfileCache(a).fit(excluded);q,_=ProfileCache(a[~a.building_id.isin(excluded)]).fit([]);q=q.reindex(index=p.index,columns=p.columns)
 np.testing.assert_allclose(p,q,equal_nan=True,atol=1e-8)


def test_original_folds_remain_disjoint():
 for f in core.load(BUNDLE/'evaluation/folds.jsonl.gz'):
  assert set(f['train']).isdisjoint(f['test'])
  if f['design']!='same_room_leave_view':assert {i.split('_')[0]for i in f['train']}.isdisjoint({i.split('_')[0]for i in f['test']})


def test_all_n_states_and_curve_denominators():
 d=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');assert len(d)==690
 assert ((d.n_valid+d.n_invalid)==d.n_observed).all()
 s=pd.read_csv(OUT/'process/image_state_probabilities.csv');a=s.groupby(['image_id','condition','cut','rule']).fraction.sum();np.testing.assert_allclose(a,1,atol=1e-10)
 c=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');assert (c.k<=c.n_valid_full).all();assert c[c.k==c.n_valid_full].future_coverage.isna().all()


def test_real_prefix_people_and_future_people_are_disjoint():
 d=pd.read_csv(OUT/'prefix/observed_prefix_and_future.csv.gz')
 for r in d.itertuples():
  p=r.prefix_workers.split(';');q=r.future_workers.split(';');assert len(set(p))==r.prefix_k and len(set(q))==r.future_n and set(p).isdisjoint(q)


def test_real_combinations_have_no_self_coverage():
 d=pd.read_csv(OUT/'combinations/real_combinations_external_future.csv.gz')
 assert len(d)==96756 and not d.combo_id.duplicated().any()
 for r in d.itertuples():
  w=r.workers.split(';');f=str(r.future_workers).split(';')if pd.notna(r.future_workers)else[]
  assert len(w)==r.people==len(set(w))and set(w).isdisjoint(f)


def test_matched_controls_match_valid_observed_people():
 d=pd.read_csv(OUT/'subgroups/equal_n_untyped_controls.csv');assert(d.actual_workers.str.count(';')+1==d.n_subgroup).all()


def test_fixed_roster_split_training_targets_disjoint():
 s=pd.read_csv(OUT/'subgroups/fixed_disjoint_split_selected.csv')
 for r in s.itertuples():assert set(r.training_buildings.split(';')).isdisjoint(r.target_buildings.split(';'))


def test_prior_results_preserved():
 a=json.loads((OUT/'audit/final_preservation_check.json').read_text());assert a['passed'] and not a['modified_or_missing']


def test_strict_image_only_prediction_declares_no_target_n():
 p=OUT/'strict_cold/method.json'
 if not p.exists():pytest.skip('strict image-only fit still executing')
 x=json.loads(p.read_text());assert x['no_actual_valid_n_predictor']and x['no_target_annotations']


def test_two_person_mode_support_is_not_simple_discovery():
 from tools.thesis_main.analysis.image_portrait.convergence_v2_mode_latency import no_seen,exactly_one
 p0=no_seen(24,2,8);p1=exactly_one(24,2,8)
 assert abs((1-p0)-.5652173913043479)<1e-12
 assert abs((1-p0-p1)-.10144927536231885)<1e-12


def test_numeric_modes_are_not_automatically_well_separated():
 a=pd.read_csv(OUT/'structure/same_point_mode_separation.csv');r=a[(a.image_id=='X7HyMhZNoso_987fd31155514f6facb131bd5c14881d')&(a.cut==.1)].iloc[0]
 assert abs(r.cross_pairs_compatible_at_cut-102/108)<1e-10 and r.medoid_distance<.1


def test_cold_prediction_records_unique_image_algorithm_targets():
 d=pd.read_csv(OUT/'strict_cold/predictions.csv.gz');assert not d.duplicated(['image_id','condition','feature','algorithm','target']).any()
