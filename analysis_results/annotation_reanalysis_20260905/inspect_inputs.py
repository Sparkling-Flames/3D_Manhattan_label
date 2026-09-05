from pathlib import Path
import hashlib,json
import pandas as pd
root=Path(__file__).parent/'inputs/legacy_rq1'
expect={'formal_time_worker_task_rows.csv':'e3a485d917c89368c930f4615e4cb42da1bc0049','c1_geometry_repair_audit.csv':'2a1dd3e572e15b420404d6fd02b79794a2905fb3','SUMMARY.json':'875287e703b16202a2dd131762a6fcd10f54e074'}
checks=[]
for name,sha in expect.items():
 b=(root/name).read_bytes(); s=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest();checks.append({'file':name,'expected_git_blob_sha_at_main_11a72ff':sha,'actual_git_blob_sha':s,'exact_match':sha==s});assert s==sha
print(checks); (Path(__file__).parent/'input_sha_verification.json').write_text(json.dumps(checks,indent=2))
d=pd.read_csv(root/'formal_time_worker_task_rows.csv');g=pd.read_csv(root/'c1_geometry_repair_audit.csv')
keys=['project_id','runtime_task_id','worker_id','annotation_id','base_task_id','dataset_group']
d=d.merge(g[keys+['raw_point_count','raw_valid']],on=keys,validate='one_to_one')
print('workers',sorted(d.worker_id.unique()),'rows',len(d),'tasks',d.base_task_id.nunique(),'buildings',d.building_id.nunique())
print(d.groupby('dataset_group').agg(rows=('worker_id','size'),workers=('worker_id','nunique'),tasks=('base_task_id','nunique')))
print('time',d.active_time_status.value_counts().to_dict(),d.active_time_seconds.describe().to_dict())
print('support_equal_rows',d.groupby('base_task_id').agg(n=('worker_id','size'),s=('strict_valid_support','first')).eval('n==s').value_counts())
n=d.strict_valid_support
d['peer_distance_mean']=(n*d.task_mask_dispersion-(n-2)*d.leave_one_worker_out_mask_dispersion)/2
print('peer_distance_summary',d.peer_distance_mean.describe().to_dict())
print('mean_identity max error', (d.groupby('base_task_id').peer_distance_mean.mean()-d.groupby('base_task_id').task_mask_dispersion.first()).abs().max())
d['corner_pair_count']=d.raw_point_count/2
d.to_csv(Path(__file__).parent/'c1_targeted_rows.csv',index=False)
print(d.groupby('worker_id').agg(n=('annotation_id','size'),tasks=('base_task_id','nunique'),bld=('building_id','nunique'),peer=('peer_distance_mean','mean'),corners=('corner_pair_count','mean'),time=('active_time_seconds','median')).to_string())
