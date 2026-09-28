import os,itertools,collections,json,math,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import common as c
c.configure(os.environ.get('PANORAMA_SOURCE',str(c.ROOT/'source_work')))


def test_pool_counts_and_no_duplicated_workers():
    _,_,views,_,_=c.load()
    assert len(views)==240 and sum(x['N'] for x in views.values())==2444
    assert len(set(w for x in views.values() for w in x['workers']))==25
    assert all(len(x['workers'])==len(set(x['workers'])) for x in views.values())
    assert not any(r['imputed_point'] or r['worker_id'] in ['W019','W026'] for x in views.values() for r in x['rows'])


def test_coverage_formula_against_exact_enumeration():
    d=np.array([[0,10,40,40],[10,0,20,40],[40,20,0,40],[40,40,40,0.]])
    for k in [0,1,2,3]:
        vals=[]
        for target in range(4):
            for obs in itertools.combinations([j for j in range(4) if j!=target],k):
                vals.append(not any(d[target,j]<=25.6 for j in obs))
        assert np.isclose(c.next_uncovered(d,k),np.mean(vals))
    assert np.isnan(c.next_uncovered(d,4))


def test_order_does_not_change_fixed_set_partition():
    _,_,views,_,_=c.load();rng=np.random.default_rng(73)
    for v in views.values():
        for method in ['complete','representative']:
            labs,_=c.part(v['d'],v['ids'],method);order=rng.permutation(v['N'])
            labs2,_=c.part(v['d'][np.ix_(order,order)],[v['ids'][j] for j in order],method)
            restore=np.empty_like(labs2);restore[order]=labs2
            assert np.array_equal(labs[:,None]==labs[None,:],restore[:,None]==restore[None,:])


def test_complete_and_representative_are_distinct_contracts():
    d=np.array([[0,20,40],[20,0,20],[40,20,0.]])
    l,_=c.part(d,['A','B','C'],'complete');r,_=c.part(d,['A','B','C'],'representative')
    assert len(set(l))==2 and len(set(r))==1


def test_comparison_implementation_equals_original():
    import importlib.util
    spec=importlib.util.spec_from_file_location('replay',c.ROOT/'code/02_replay.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    # The full historical module imports lib.misc, absent from the handoff.
    # Execute the exact pure function AST without unrelated historical dependencies.
    import ast
    source=(c.SOURCE/'tools/thesis_main/analysis/worker_four_block_exploration_20260910.py').read_text()
    tree=ast.parse(source);fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='compare_bits')
    module=ast.Module(body=[fn],type_ignores=[]);namespace={}
    exec(compile(module,'original_compare_bits','exec'),namespace)
    compare_bits=namespace['compare_bits']
    rng=np.random.default_rng(16)
    for n in range(3,15):
        for k in range(2,n):
            a=rng.integers(0,4,k);b=rng.integers(0,4,n)
            tobits=lambda labs:tuple(sum(1<<j for j,l in enumerate(labs) if l==v) for v in sorted(set(labs)))
            left,right=tobits(a),tobits(b);relation,tv,promotion,repeated=mod.comparisons(left,right)
            state=1 if not repeated else 2 if relation>.1+1e-12 or tv>.1+1e-12 or promotion else 0
            assert state==compare_bits(left,right)


def test_current_and_historical_profiles_exclude_target_building():
    d=pd.read_csv(c.ROOT/'results/worker_lobo_profiles.csv')
    assert not any(r.heldout_building in str(r.train_building_ids).split(';') for r in d.itertuples())
    d=pd.read_csv(c.SOURCE/'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_profiles.csv')
    assert not any(r.heldout_building in str(r.train_building_ids).split('|') for r in d.itertuples())


def test_saved_curves_and_fixed_seed_orders():
    orders=json.loads((c.ROOT/'results/replay_orders.json').read_text());assert orders['n_orders']==200
    for x in orders['orders']:assert len(x)==len(set(x))==25
    for r in json.loads((c.ROOT/'results/replay_curves.json').read_text()):
        lo=np.array(r['L']);hi=np.array(r['U'])
        assert np.all((0<=lo)&(lo<=hi)&(hi<=1))
        assert np.all(np.diff(lo)>=-1e-12) and np.all(np.diff(hi)>=-1e-12)
        assert len(r['ks'])==max(0,r['N']-r['tail']-1)


def test_real_combinations_and_variance_identity():
    d=pd.read_csv(c.ROOT/'results/team_panels.csv')
    assert all(r.evaluated_unique_teams<=math.comb(r.N,r.n) for r in d.itertuples())
    d=pd.read_csv(c.ROOT/'results/team_composition_variance.csv.gz')
    assert np.allclose(d.total_variance,d.within_composition_variance+d.between_composition_variance,atol=1e-12)


def test_no_unfrozen_new_times_used():
    d=pd.read_csv(c.ROOT/'results/frozen_time_panel.csv');assert len(d)==1426
    assert not d.id.str.startswith('new_').any()
    assert d.source.eq('frozen_historical_owner_valid_active_time').all()


def test_preexisting_q9_range_difference_not_new_adjudication():
    g=json.loads((c.ROOT/'results/q9_preexisting_range_review.json').read_text())[0]
    assert g['review_code']=='G145'
    assert g['raw_current']['main_visual_alignment']=='不同' and g['raw_current']['extent_alignment']=='存在明显差异'


def test_approved_mapping_sensitivity_not_default_rewrite():
    x=json.loads((c.ROOT/'results/measurement_summary.json').read_text())['uNb21_approved_mapping']
    assert x['fixed_max']>25.6 and x['reviewed_max']<25.6
    _,rec,views,_,_=c.load();v=next(v for v in views.values() if x['a'] in v['ids'])
    assert np.isclose(v['d'][v['ids'].index(x['a']),v['ids'].index(x['b'])],x['fixed_max'])


def test_model_feature_snapshot_hash():
    p=c.SOURCE/'analysis_results/clustering_release_local_20260920/current/input/supplement/model_image_features.csv'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='03af6cc5f2a6cf7cb8c6f41b53bd884b26ac92d447ffeec13d6070348cc3c007'
