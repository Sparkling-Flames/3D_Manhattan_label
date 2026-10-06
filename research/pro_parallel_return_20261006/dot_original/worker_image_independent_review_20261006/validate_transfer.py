#!/usr/bin/env python3
"""Validate transferred arrays internally without claiming source-file certification."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np


def validate(path):
    p=json.loads(path.read_text()); nimg=len(p['image_order']);nw=len(p['worker_order'])
    assert (nimg,nw)==(10,24)
    assert len(set(p['image_order']))==nimg and len(set(p['worker_order']))==nw
    policies={a['policy']:a for a in p['policies']}
    assert set(policies)=={'original','revised_where_available'}
    orig=policies['original']; rev=policies['revised_where_available']
    x={}
    for name,a in policies.items():
        x[name]={m:np.array(a[m],dtype=float) for m in ['O','E','D']}
        for m,arr in x[name].items():
            assert arr.shape==(10,24) and np.isfinite(arr).all() and (arr>=-1e-14).all()
        assert (x[name]['O']<=1+1e-14).all()
        assert np.allclose(x[name]['D'],x[name]['O']+x[name]['E'],rtol=0,atol=1e-14)
        assert len(a['versions'])==nimg and len(a['gt_area_h2'])==nimg
        assert (np.array(a['gt_area_h2'],float)>0).all()
    changes=[i for i in range(nimg) if orig['versions'][i]!=rev['versions'][i]]
    assert len(changes)==4 and all(v=='original' for v in orig['versions'])
    assert all(v in ['original','manual_revision'] for v in rev['versions'])
    unchanged=[i for i in range(nimg) if i not in changes]
    for i in unchanged:
        for m in ['O','E','D']:
            assert orig[m][i]==rev[m][i]
        assert orig['gt_area_h2'][i]==rev['gt_area_h2'][i]
    areas={name:np.array(a['gt_area_h2'],float)[:,None]*(1-x[name]['O']+x[name]['E']) for name,a in policies.items()}
    d=np.abs(areas['original']-areas['revised_where_available'])
    assert d.max()<1e-12
    return {'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'evidence_scope':'Independent statistical recomputation of transferred arrays, not original CSV byte certification','transfer_note':p.get('transfer_note'),'n_unique_person_image_cells':240,'n_policy_evaluations':480,'n_images':nimg,'n_buildings':len(set(p['buildings'])),'n_workers':nw,'changed_reference_images':[p['image_order'][i] for i in changes],'unchanged_reference_images':[p['image_order'][i] for i in unchanged],'max_annotation_area_difference_h2_across_references':float(d.max()),'max_D_minus_O_plus_E_absolute':{name:float(np.abs(a['D']-(a['O']+a['E'])).max()) for name,a in x.items()},'small_negative_values_preserved':[{'policy':name,'metric':m,'image':p['image_order'][i],'worker':p['worker_order'][j],'value':float(arr[i,j])} for name,a in x.items() for m,arr in a.items() for i,j in zip(*np.where(arr<0))],'all_checks_passed':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input_json');p.add_argument('output_json');a=p.parse_args()
    r=validate(Path(a.input_json));Path(a.output_json).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
