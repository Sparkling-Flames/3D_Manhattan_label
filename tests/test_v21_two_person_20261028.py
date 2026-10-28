import gzip
import json
import math
import pandas as pd
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT, read
from tools.thesis_main.analysis.fuse_v21_new_pools_20261028 import adapter
from tools.thesis_main.analysis.ring_correspondence_20261007 import build
from tools.thesis_main.analysis import wall_consensus_quality_20261015 as quality


def test_two_person_uses_original_nodes_and_scores_connected_geometry():
    pid='7y3sRwLe3Va-26__manual__c9d0cbdd90'
    pool=next(x for x in read(OUT/'pools/INPUT_SNAPSHOT.json')['images'] if x['pool_id']==pid)
    with gzip.open(OUT/'two_person_natural256/pools'/(pid+'.json.gz'),'rt',encoding='utf8') as f:
        row=json.load(f)['teams'][0]
    members={r['worker_id']:r for r in pool['records']}
    records=[members[w] for w in row['member_workers']]
    native=adapter()
    with native.Engine() as engine:
        with_defer=engine.fe.fuse(records,gap=engine.fe.WORKING_GAP)['automatic']
        raw=build(records,gap=engine.fe.WORKING_GAP)
        assert with_defer['candidate']['status']=='deferred'
        assert raw['node_consensus']==with_defer['node_consensus']
        third=next(r for r in pool['records'] if r['worker_id'] not in row['member_workers'])
        assert engine.fe.fuse(records+[third],gap=engine.fe.WORKING_GAP)['automatic']['candidate']==build(records+[third],gap=engine.fe.WORKING_GAP)['candidate']
        assert row['node_supports']==[n['support'] for n in raw['node_consensus']['nodes']]
        assert row['single_support_nodes']+row['joint_support_nodes']==row['nodes']
        classify=quality.classify_output
        quality.classify_output=lambda k,n,c,f: classify(3 if k==2 else k,n,c,f)
        try: result=engine.fe.compute_score(engine.fe.compact(raw),pool,engine.engine,engine.models)
        finally: quality.classify_output=classify
    assert result['score_status']==row['score_status']
    assert math.isclose(result['B8L2'],row['B8L2'],abs_tol=1e-8)


def test_output_classification_keeps_unconnected_and_short_results():
    assert quality.classify_output(3,4,False,True)=='no_connection'
    assert quality.classify_output(3,3,True,True)=='below_four'
    assert quality.classify_output(3,4,True,False)=='floor_only_reference'


def test_path_results_preserve_frequency_and_pairwise_missingness():
    root=OUT/'two_person_natural256'
    paths=pd.read_csv(root/'PAIRED_PATH_RESULTS.csv.gz')
    images=pd.read_csv(root/'IMAGE_RESULTS.csv').set_index('pool_id')
    assert len(paths)==223*256 and paths.groupby('pool_id').size().eq(256).all()
    assert paths['delta_1_2'].notna().equals(paths['Q1'].notna() & paths['Q2'].notna())
    assert paths['delta_2_3'].notna().equals(paths['Q2'].notna() & paths['Q3'].notna())
    assert paths.loc[paths.k2_score_status.eq('no_connection'),'Q2'].isna().all()
    pid=paths.pool_id.iloc[0]; sample=paths[paths.pool_id.eq(pid)]
    assert math.isclose(images.loc[pid,'Q2'],sample.Q2.mean(),abs_tol=1e-8)
    assert images.loc[pid,'unique_teams']==sample.k2_team_key.nunique()
