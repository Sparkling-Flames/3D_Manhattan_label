from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis import difficulty_wild_gallery as gallery
from tools.thesis_main.analysis import difficulty_wild_round2 as round2
from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis.difficulty_wild_sampler import VALID, wild_count


def points(shift=0):
    return [[(x+shift)%1024,y] for x in (40,290,550,800) for y in (140,380)]


def record(building, worker, shift):
    iid=building+'_image'; aid=building+':'+worker
    return dict(annotation_id=aid,record_id=aid,image_id=iid,building_id=building,worker_id=worker,
        points=points(shift),active_time_seconds=None,lead_time_seconds=20.+shift,
        submitted_at='2026-09-22T01:00:00Z',source_condition='mixed',scope='in_scope',geometry_status=VALID)


@pytest.fixture
def small():
    rows=[record('held','114',2),record('held','115',6),record('train','114',3),record('train','115',7)]
    models={iid:{f:dict(points=points(),layout_id=iid+':'+f) for f in base.FAMILIES}
            for iid in ('held_image','train_image')}
    t=dict(image_id='held_image',image='held-01',building_id='held',source_condition='mixed',
        workers=rows[:2],annCount=2,scope_votes=dict(in_scope=2,out_of_scope=0),
        real_manual_n=2,need=33,wild_budget_k=1,difficulty='困难',disagreement_px=4.,
        difficulty_thresholds=[2.,3.])
    return dict(usable=rows,models=models), t


@pytest.fixture(scope='module')
def actual():
    return gallery.load_gallery()


def test_exact_frozen_population(actual):
    assert len(actual['tasks'])==378 and len(actual['targets'])==144
    assert sum(t['need'] for t in actual['targets'])==2740
    assert sum(t['real_manual_n'] for t in actual['targets'])==2300
    assert len({t['building_id'] for t in actual['targets']})==15
    assert len({r['building_id'] for r in actual['usable']})==24
    assert {t['need'] for t in actual['targets']}=={19,20}
    for t in actual['targets']:
        assert all(f in actual['models'][t['image_id']] for f in base.FAMILIES)
        assert actual['photos'][t['image_id']].is_file()


def test_thresholds_derived_and_tiers_monotone(actual):
    ts=actual['targets'];values=[t['disagreement_px'] for t in ts]
    cuts=np.quantile(values,[1/3,2/3]).tolist()
    assert cuts==ts[0]['difficulty_thresholds']
    assert cuts==pytest.approx([188.32282914024944,224.99760802728764])
    assert [sum(t['difficulty']==label for t in ts) for label in ('简单','中等','困难')]==[48,48,48]
    ranks={'简单':0,'中等':1,'困难':2}
    order=[ranks[t['difficulty']] for t in sorted(ts,key=lambda t:t['disagreement_px'])]
    assert order==sorted(order)


def test_percentage_parser_preserves_pairs_and_skips_script(tmp_path):
    raw=dict(title='house_hash.jpg',code='house-01',image='fixture',annCount=1,condition='mixed',
        scopeVotes={'in_scope':1},workers=[dict(w='114',kps=[[10,20],[10,80],[30,20],[30,80],[60,20],[60,80],[80,20],[80,80]],
        scope='in_scope',gt=False,t='2026-09-22',lt=3.)])
    path=tmp_path/'gallery.html'
    path.write_text('const DATA = '+json.dumps({'tasks':[raw],'stats':{}})+'; throw new Error("never execute");')
    r=gallery.parse_gallery(path)['tasks'][0]['workers'][0]
    np.testing.assert_allclose(r['points'],np.asarray(raw['workers'][0]['kps'])*[10.24,5.12])
    assert r['submitted_at']=='2026-09-22' and r['active_time_seconds'] is None
    raw['annCount']=2;path.write_text('const DATA = '+json.dumps({'tasks':[raw],'stats':{}}))
    with pytest.raises(ValueError,match='annCount'):gallery.parse_gallery(path)


def test_parser_duplicate_workers_rejected(tmp_path):
    w=dict(w='1',kps=[[10,20],[10,80],[30,20],[30,80],[60,20],[60,80]],scope='in_scope',gt=False,lt=1)
    t=dict(title='a_b.jpg',code='a-01',image='x',condition='mixed',annCount=2,workers=[w,w],scopeVotes={'in_scope':2})
    p=tmp_path/'x.html';p.write_text('const DATA='+json.dumps({'tasks':[t],'stats':{}}))
    with pytest.raises(ValueError,match='worker_or_gt'):gallery.parse_gallery(p)


def test_ordered_distance_periodic_and_partial():
    a=[[1023,100],[1023,400],[300,100],[300,400]]
    b=[[1,100],[1,400]]
    assert gallery.ordered_distance(a,b)==2.
    assert gallery.ordered_distance(b,a)==2.
    assert gallery.disagreement([a,b])==2.
    assert gallery.disagreement([a,a])==0.
    rotated=np.roll(np.asarray(points()).reshape(-1,2,2),1,axis=0).reshape(-1,2)
    assert gallery.ordered_distance(points(),rotated)>0  # source-ring start dependence retained
    with pytest.raises(ValueError):gallery.disagreement([a])


def test_nonfinite_disagreement_rejected():
    with pytest.raises(ValueError):gallery.classify([float('nan')])


def test_invalid_target_count_rejected(small):
    _, t=small
    with pytest.raises(ValueError,match='population'):gallery.select_targets([t],set())


def test_invalid_geometry_still_counts_in_disagreement(actual):
    for t in actual['targets']:
        assert t['annCount']==len(t['workers'])
        assert t['disagreement_px']==gallery.disagreement([r['points'] for r in t['workers']])
    assert all(r['geometry_status']==VALID for r in actual['usable'])
    assert len(actual['usable'])<len(actual['records'])


def test_ids_unique_and_disjoint(actual):
    ids=[round2.synthetic_id(i,slot) for i,t in enumerate(actual['targets']) for slot in range(t['need'])]
    assert len(ids)==2740 and len(set(ids))==2740
    assert ids[0]=='S_MANUAL_200000'
    assert not (set(ids)&actual['first_ids'])
    with pytest.raises(ValueError):round2.synthetic_id(0,35)


@pytest.mark.parametrize('difficulty', ['简单','中等','困难'])
def test_budget_cap(difficulty):
    for seed in range(50):
        for need in (19,20):
            k=wild_count(difficulty,seed,need)
            lo,hi={'简单':(0,2),'中等':(5,7),'困难':(8,20)}[difficulty]
            assert lo<=k<=min(hi,need)


def test_calibration_scalar_only_and_quantiles(small):
    sources,t=small;c=gallery.image_calibration(t,sources['models'][t['image_id']])
    for family,v in c['families'].items():
        assert v['normal_amplitude']==pytest.approx(np.asarray([3.,4.])/np.sqrt(2))
        assert v['wild_amplitude']==pytest.approx(np.asarray([5.,5.8])/np.sqrt(2))
        assert v['missing_frequency']==0
        assert 'delta' not in v
        assert set(v['calibration_annotation_ids'])=={r['annotation_id'] for r in t['workers']}


def test_fold_building_holdout_without_quality_scores(small):
    s,t=small;f=round2.fit_fold(s,'held')
    assert f['training_buildings']==['train']
    assert all(d['building_id']=='train' for d in f['donors'])
    assert all(r['building_id']=='train' for r in f['times'])
    assert all(p['quality']=='uncertain' and not p['axes'] for p in f['profiles'].values())


@pytest.mark.parametrize('slot', [0,1])
def test_generation_geometry_provenance_time_and_replay(small,slot):
    s,t=small;f=round2.fit_fold(s,'held');c=gallery.image_calibration(t,s['models'][t['image_id']])
    snapshot=copy.deepcopy(f)
    a=round2.make_row(t,s['models'][t['image_id']],f,c,20261017,slot,0)
    b=round2.make_row(t,s['models'][t['image_id']],f,c,20261017,slot,0)
    assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
    assert a['geometry_status']==VALID and base.geometry_status(a['points'])==VALID
    assert a['residual_donor_building_id']==a['lead_time_donor_building_id']=='train'
    assert a['calibration_building_id']=='held'
    assert a['evaluation'] is None and a['evaluation_reason']=='no_gt_reference'
    assert a['active_time_seconds'] is None and a['lead_time_seconds']>0
    assert a['wild']==(slot==0)
    assert not np.array_equal(a['points'],points())
    assert f['donors']==snapshot['donors']
    assert not any('B8L2' in k for k in a)


def test_scope_tie_and_oos_flags(small):
    s,t=small;t=copy.deepcopy(t);t['scope_votes']={'in_scope':1,'out_of_scope':1}
    assert gallery.image_calibration(t,s['models'][t['image_id']])['scope_majority']=='tie'
    t['scope_votes']={'in_scope':0,'out_of_scope':2}
    assert gallery.image_calibration(t,s['models'][t['image_id']])['scope_oos_majority']


def test_export_no_gt_and_empirical_metadata(small,tmp_path):
    s,t=small;f=round2.fit_fold(s,'held');c=gallery.image_calibration(t,s['models'][t['image_id']])
    r=round2.make_row(t,s['models'][t['image_id']],f,c,1,1,0)
    ids,summary=round2.export_samples([r],{t['image_id']:{'image_url':'fixture.jpg'}},tmp_path)
    assert len(ids)==1 and summary['rejected']==0
    a=json.loads((tmp_path/'label_studio_synthetic.json').read_text())[0]['annotations'][0]
    assert a['ground_truth'] is False and a['active_time_seconds'] is None
    assert a['difficulty_wild_metadata']['difficulty_basis']==gallery.BASIS
    assert a['difficulty_wild_metadata']['evaluation_reason']=='no_gt_reference'
    assert a['difficulty_wild_metadata']['gt_none'] is True


def test_round1_export_contract_unchanged(tmp_path):
    rows=base.read_jsonl(gallery.FIRST/'simulations.jsonl')
    original=json.loads((gallery.FIRST/'label_studio_synthetic.json').read_text())
    task=original[0];iid=task['data']['image_id']
    selected=[r for r in rows if r['image_id']==iid]
    round2.export_samples(selected,{iid:{'image_url':task['data']['image']}},tmp_path)
    assert json.loads((tmp_path/'label_studio_synthetic.json').read_text())==[task]


def test_source_integrity_includes_gallery_bank_photos_and_first(actual):
    hashes=gallery.source_hashes(actual)
    assert str(gallery.GALLERY.resolve()) in hashes and str(gallery.BANK.resolve()) in hashes
    assert all(str(p.resolve()) in hashes for p in actual['photos'].values())
    assert all(str(p.resolve()) in hashes for p in gallery.FIRST.rglob('*') if p.is_file())
    assert all(base.digest(Path(p))==h for p,h in hashes.items())


def test_new_mode_rejects_semi_without_writes(tmp_path):
    from tools.thesis_main.analysis.personality_incremental_run import run_incremental
    with pytest.raises(ValueError,match='manual_only'):
        run_incremental(tmp_path/'x',1,['semi'],'fill-144-gallery')
    assert not (tmp_path/'x').exists()


def test_existing_output_rejected_before_reading(tmp_path):
    with pytest.raises(FileExistsError):round2.run(tmp_path)


def test_replay_verifies_and_refuses_differences(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    for p in (a,b):
        base.dump(p/'VALIDATION.json',{'reproducibility':'pending'})
        base.dump(p/'summary.json',{'generated':2740})
    assert round2.verify_replay(a,b)['passed']
    base.dump(b/'summary.json',{'generated':0})
    with pytest.raises(ValueError,match='bytes_differ'):round2.verify_replay(a,b)
