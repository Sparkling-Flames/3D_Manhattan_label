"""Bounded verification: fixed B block against S2 plus frozen-point reconstruction.

This does not claim to rejoin the full current source bundle or identify people.
"""
from pathlib import Path
from collections import Counter
import csv,json,sys,warnings
import numpy as np,shapely

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'worker-audit-original'))
from tools.thesis_main.analysis.research_round_20260929 import prepare_record,reconstruct
from tools.thesis_main.analysis.worker_profiles_20261003 import panel_records,calibrate
base=ROOT/'worker-audit-original/analysis_results'
data=json.loads((base/'worker_profiles_20261003/input.json').read_text())
block=json.loads((base/'worker_profiles_20261003/block.json').read_text())
s2=json.loads((base/'research_panel_inventory_20261003/input.json').read_text())
preselected=json.loads((base/'research_panel_inventory_20261003/next_panels.json').read_text())
assert block==preselected['b']['blocks'][0]
workers,groups=panel_records(data,block)
index={r['id']:r for r in s2['records']+s2['references']};images={r['image']:r for r in s2['images']}
checks=[];notices=[];image_checks=[]
for im in data['images']:
    old=images[im['code']]
    expected={r['id'] for r in s2['records']+s2['references'] if r['image']==im['code']}
    got={r['id'] for r in im['annotations']+im['references']}
    image_checks.append(dict(image=im['code'],same_population=got==expected,metadata_differences=[f for f in ['building','room','difficulty','image_id'] if im[f]!=old[f]]))
    for r in im['annotations']+im['references']:
        old=index[r['id']];prepared=prepare_record(r)
        roundtrip=[f for f in ['points','source_point_indices','source_point_labels','source_pair_indices','order_used','ring_confirmed','order_status'] if r.get(f)!=prepared.get(f)]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',RuntimeWarning)
            g=reconstruct(r)
        notices.extend(dict(image=im['code'],record=r['id'],message=str(w.message)) for w in caught)
        state=g['representations']['declared_footprint']
        delta=None
        if r['footprint'] is not None:
            assert state['status']=='ok'
            delta=float(np.max(abs(np.array(r['footprint'])-g['floor'])))
        compared=dict(image=im['code'],order_used=r['order_used'],bev_ok=state['status']=='ok',bev_reason=state['reason'])
        if 'worker' in r:
            compared.update(worker=r['worker'],condition=r['condition'],independent=r['independent'],consensus_gate=r['main_consensus_gate']['status'],quality_gate=r['main_quality_gate']['status'],quality_candidate=r['quality_candidate'],consensus_candidate=r['independent'] and r['consensus_eligible'])
        else:compared.update(version=r['version'])
        differences=[key for key,val in compared.items() if old[key]!=val]
        checks.append(dict(image=im['code'],record=r['id'],s2_fields_checked=list(compared),s2_differences=differences,preparation_changes=roundtrip,points_available=r['points'] is not None,footprint_available=r['footprint'] is not None,footprint_reconstruction_max_abs_delta=delta,footprint_state_equal=r['footprint_state']==state,order_used=r['order_used']))
npz=np.load(base/'worker_profiles_20261003/subsets.npz');members=npz['members'];masks=npz['masks']
combinations_ok=(members.shape==(10626,4) and len({tuple(x) for x in members})==10626 and bool(np.all(np.diff(members.astype(int),axis=1)>0)) and bool(np.array_equal(masks,np.sum(np.left_shift(np.uint32(1),members.astype(np.uint32)),axis=1))))
foldchecks=[]
for policy in ['original','revised_where_available']:
    rows=list(csv.DictReader((base/f'worker_profiles_20261003/matrix_{policy}_iou.csv').open(encoding='utf-8-sig')))
    buildings=[r['building'] for r in rows];x=np.array([[float(r[w]) for w in workers] for r in rows])
    for target in sorted(set(buildings)):
        c=calibrate(x,buildings,target);mutated=x.copy();test=np.array(buildings)==target;mutated[test]=np.arange(24)[None,:]/23
        alt=calibrate(mutated,buildings,target)
        foldchecks.append(dict(policy=policy,building=target,train_image_n=len(c['train_indices']),target_image_n=int(test.sum()),target_mutation_keeps_calibration=bool(np.array_equal(c['mean'],alt['mean'])),higher_count=int(c['higher'].sum()),composition_counts=np.bincount(c['higher'][members].sum(axis=1),minlength=5).tolist()))
summary=dict(images=len(data['images']),workers=len(workers),buildings=len(set(im['building'] for im in data['images'])),annotations=sum(len(im['annotations']) for im in data['images']),references=sum(len(im['references']) for im in data['images']),candidates=sum(len(rs) for _,rs,_ in groups),records=len(checks),available_coordinates=sum(r['points_available'] for r in checks),unavailable_coordinates=sum(not r['points_available'] for r in checks),s2_record_mismatches=sum(bool(r['s2_differences']) for r in checks),s2_image_mismatches=sum(bool(r['metadata_differences']) or not r['same_population'] for r in image_checks),preparation_changed_records=sum(bool(r['preparation_changes']) for r in checks),max_footprint_coordinate_delta=max(r['footprint_reconstruction_max_abs_delta'] or 0 for r in checks),state_mismatches=sum(not r['footprint_state_equal'] for r in checks),difficulty=dict(Counter(im['difficulty'] for im in data['images'])),order_used=dict(Counter(r['order_used'] for r in checks)),warning_count=len(notices),all_distinct_subsets_and_masks_correct=combinations_ok,all_target_mutations_isolated=all(r['target_mutation_keeps_calibration'] for r in foldchecks),all_composition_counts_correct=all(r['composition_counts']==[495,2640,4356,2640,495] for r in foldchecks))
out=dict(scope='Fixed B vs current-commit S2 snapshot and all frozen-point reconstructions only. Full current-bundle coordinate-source/index rejoin NOT independently performed; no identity/comment/visual audit.',environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__),summary=summary,images=image_checks,records=checks,folds=foldchecks,warnings=notices)
(ROOT/'worker-audit-source-review/bounded_input_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
