import numpy as np
import pandas as pd
from tools.thesis_main.analysis.worker_rule_triad_20260910 import cluster_profiles, fit_axes


def test_clusters_ignore_units_and_reject_singleton():
    p=pd.DataFrame({'worker_id':list('abcdef'),'edit':[0,1,2,8,9,10],'time':[0,1,2,8,9,10],'quality':[1,2,3,9,10,11]})
    a,status=cluster_profiles(p,['edit','time','quality'],2)
    b,status2=cluster_profiles(p.assign(time=p.time*1000),['edit','time','quality'],2)
    assert status==status2=='usable' and np.array_equal(a,b)
    p['edit']=[0,0,0,0,0,100]
    labels,status=cluster_profiles(p,['edit'],2)
    assert status=='singleton_rejected' and set(labels)=={0}


def test_task_difficulty_and_low_support_do_not_define_workers():
    rows=[dict(worker_id=w,context_key=f'{b}_{i}',image_id=f'{b}_{i}',building_id=str(b),
          edit=100*b+10*i+effect,time=1000*b+100*i+2*effect,quality=20*b+3*i-effect)
          for b in range(4) for i in range(2) for w,effect in [('1',-1),('2',0),('3',1)]]
    rows.append(dict(rows[0],worker_id='sparse'))
    p,status=fit_axes(pd.DataFrame(rows),['edit','time','quality'])
    assert status=='usable' and set(p.worker_id)=={'1','2','3'}
    assert np.allclose(p.set_index('worker_id').loc[['1','2','3'],'edit'],[-1,0,1])
