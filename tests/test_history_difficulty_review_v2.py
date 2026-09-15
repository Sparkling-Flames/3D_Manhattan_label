import collections,hashlib,itertools,json,math
import numpy as np,pandas as pd,pytest
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,B,PREV,cluster,cluster_static,rarefy,one_replay
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2 import few_limit,grade
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_discovery_v2 import support_ceiling

def test_current_input_hashes():
 known={'metadata/images.jsonl':'02eebd582fc33aee5936fe69dd45d1853408e803','metadata/relationships.jsonl':'9a6e2c9922ac0dd88797e005e0ba7187b4160b57','metadata/spatial_history.jsonl.gz':'676ddba4e9330ed6b6d484b0cfb03bf377dbf0fd','metadata/spatial_provenance.json':'0d60a109e5ffbf9f7ed4355c017cc3e374fbe2df','human/responses.jsonl.gz':'6261c30d1abf2d7ad0e71702348fc81819e783ad'}
 for path,sha in known.items():
  x=(B/path).read_bytes();assert hashlib.sha1(f'blob {len(x)}\0'.encode()+x).hexdigest()==sha

def test_main_exclusion_and_repairs():
 r=pd.read_csv(OUT/'audit/response_inclusion.csv.gz');v=r[r.analysis_valid]
 assert not v.worker_id.isin(['W019','W026']).any()
 assert 'W011'in set(v.worker_id)
 assert v.raw_condition.isin(['manual','semi']).all()
 assert not (v.effective_point_count%2).any()
 a=r[r.main_worker&r.raw_condition.isin(['manual','semi'])]
 assert a.raw_odd.sum()==17
 assert (a.analysis_valid&a.reviewed_repair).sum()==5
 assert ((a.raw_odd)&~a.analysis_valid).sum()==12
 assert len(v)==2152
 assert a[~a.analysis_valid].shape[0]==20

def test_no_replicated_people():
 r=pd.read_csv(OUT/'audit/response_inclusion.csv.gz');v=r[r.analysis_valid]
 assert not v.duplicated(['image_id','raw_condition','worker_id']).any()

def test_reviewed_addition_only_sensitivity():
 a=pd.read_csv(OUT/'extra/confirmed_addition_sensitivity.csv');assert a.image_id.nunique()==2
 for _,g in a.groupby(['image_id','condition','cut']):
  x=g.set_index('scenario');assert x.loc['with_user_confirmed_addition','n_valid']-x.loc['exclude_confirmed_added_only','n_valid']==1

def test_point_count_hard_separation():
 dm=np.zeros((4,4));pcs=np.array([8,8,10,10]);l=cluster(dm,pcs,.1)
 assert l[0]==l[1]and l[2]==l[3]and l[0]!=l[2]

def test_total_cluster_identity():
 a=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');assert (a.total_clusters==a.supported_clusters+a.singletons).all()

def test_supported_distinct_persons():
 a=pd.read_csv(OUT/'structure/real_mode_memberships.csv.gz')
 for _,g in a.groupby(['image_id','condition','cut','cluster']):
  assert g.worker_id.nunique()==g.cluster_people.iloc[0]

def test_all_images_preserved():
 a=pd.read_csv(OUT/'proposal/per_image_draft_for_user.csv');assert len(a)==230;assert a.image_id.nunique()==205
 assert a.n_excluded.sum()==20
 assert len(a[a.n_excluded>0])>0

def test_fixed_proportion_discreteness():
 assert few_limit(19,'fixed10pct')==1 and few_limit(20,'fixed10pct')==2
 assert few_limit(6,'fixed10pct')==0
 assert few_limit(6)==1 and few_limit(19)==3

def test_count_band_not_a_probability_estimate():
 assert few_limit(8)==1 and few_limit(9)==2
 assert few_limit(16)==2 and few_limit(17)==3

@pytest.mark.parametrize('sizes,k',[([3,2,1],3),([3,2,1],4),([3,2,1],5),([3,2,1],6),([2,2,2],4),([2,2,2],6)])
def test_exact_support_ceiling_matches_enumeration(sizes,k):
 labels=np.concatenate([np.repeat(j,z)for j,z in enumerate(sizes)]);sup=[j for j,z in enumerate(sizes)if z>=2]
 combos=list(itertools.combinations(range(len(labels)),k));truth=np.mean([all(np.sum(labels[list(c)]==j)>=2 for j in sup)for c in combos])
 assert support_ceiling(sizes,k)==pytest.approx(truth)

def test_rare_doubleton_ceiling():
 assert support_ceiling([18,2,2,1],19)==pytest.approx(math.comb(19,4)/math.comb(23,4))
 assert support_ceiling([18,2,2,1],19)<.8

def test_rarefaction_at_full_n():
 a=rarefy([8,5,2,2,1,1],19);assert a==dict(expected_clusters=6,expected_supported=4,expected_singletons=2)

def test_unlabelled_not_classified_from_expert():
 r=dict(n_valid=23,total_clusters=6,supported_clusters=4,singletons=2,min_supported_loo_jaccard=.99,full_p_by_8=0,core15_p_by_19=.5,late_quarter_new=.03,core_tail_15=.7)
 assert grade(dict(r,expert_tag='中等'))==grade(dict(r,expert_tag='困难'))
 assert grade(r)[0]=='medium_candidate';assert grade(r,medium_kind='process')[0]==''

def test_stable_many_clusters_not_hard():
 r=dict(n_valid=23,total_clusters=10,supported_clusters=6,singletons=4,min_supported_loo_jaccard=1.,full_p_by_8=0,core15_p_by_19=.9,late_quarter_new=.2,core_tail_15=.9)
 assert grade(r)[0]==''

def test_replay_not_blocked_by_singleton_fraction():
 pcs=np.array([8,8,10,10,12,14]);dm=np.where(pcs[:,None]==pcs[None,:],.01,2.);np.fill_diagonal(dm,0)
 a,_,_=one_replay(dm,pcs,.1,80,'toy_six_distinct_people','manual');z=pd.DataFrame(a)
 assert z.core_onset_15.notna().any()
 assert (z.core_onset_15.dropna()<6).all()

def test_core_probability_requires_actual_repeated_support():
 a=pd.read_csv(OUT/'process/support_discovery_vs_conditional_stability.csv')
 assert (a.p_stable_core15_unconditional<=a.p_all_modes_seen_twice_replay+1e-10).all()
 assert (a.observed_k<a.n_valid).all()
 assert a.p_stable_core15_given_support.dropna().between(0,1).all()

def test_common18_is_same_real_people():
 a=pd.read_csv(OUT/'extra/exact_common18_panel.csv');assert a.image_id.nunique()==8
 assert a.common_workers.nunique()==1
 people=a.common_workers.iloc[0].split(';');assert len(people)==len(set(people))==18
 assert not set(people)&{'W019','W026'}

def test_blanks_are_not_difficult():
 a=pd.read_csv(OUT/'proposal/per_image_draft_for_user.csv');assert a.draft_grade.isna().sum()>100
 assert (a[a.n_valid<4].draft_grade.isna()).all()
 assert a.user_final_grade.isna().all()

def test_previous_geometry_and_new_recompute_agree():
 a=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');a=a[a.cut==.1];old=pd.read_csv(PREV/'targets/primary_with_robustness.csv');z=a.merge(old,on=['image_id','condition'],suffixes=('','_old'))
 for new,prev in [('n_valid','n_valid_old'),('total_clusters','n_modes'),('supported_clusters','n_supported_modes'),('singletons','n_singletons')]:
  ok=z[[new,prev]].dropna();assert np.allclose(ok[new],ok[prev])

def test_geometry_layers_cover_but_no_fake_replay():
 s=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');assert s.shape[0]==230*6
 p=pd.read_csv(OUT/'process/per_image_growth_summary.csv');assert p[p.n_valid<4].orders.isna().all()

def test_refined_medium_has_both_recovery_checks():
 a=pd.read_csv(OUT/'proposal/final_review_draft_per_image.csv');m=a[a.review_draft_grade=='medium_candidate']
 assert m.min_sub80_jaccard.ge(.75).all()
 assert m.min_supported_loo_jaccard.ge(.85).all()
 assert m.supported_clusters.between(2,4).all()

def test_raw_to_cached_pair_distances():
 import gzip
 from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import normalize_geometry,dense,dmask
 with gzip.open(B/'human/responses.jsonl.gz','rt')as f:raw={r['canonical_annotation_id']:r for r in map(json.loads,f)}
 idx=json.loads((OUT/'cache/group_index.json').read_text());cache=np.load(OUT/'cache/pairwise_geometry.npz',allow_pickle=False)
 selected=[r for r in idx if r['n_valid']>=4][::23]
 for r in selected:
  k=r['key'];ids=cache[k+'_ids'];pcs=cache[k+'_pcs'];dm=cache[k+'_dm'];bd=[]
  for cid in ids:
   norm=normalize_geometry(raw[str(cid)]['effective_points_1024x512']);assert norm['valid'];bd.append(dense(norm['pairs']))
  for a,b in itertools.combinations(range(len(ids)),2):
   val=dmask(bd[a],bd[b])if pcs[a]==pcs[b]else 2.
   assert dm[a,b]==pytest.approx(val,abs=1e-12)
