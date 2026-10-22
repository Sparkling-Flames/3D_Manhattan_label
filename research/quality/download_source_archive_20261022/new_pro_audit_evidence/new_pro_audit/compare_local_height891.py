"""Compare independently measured old Hcenter against new local_error on hash-identical 891."""
from pathlib import Path
import argparse,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
if args.out.exists():raise FileExistsError(args.out)
old=pd.read_csv(ROOT/'audit_quality_baseline/current891_complete/current891_fixed_reference_geometry_replay.csv').set_index('object_id')
new=pd.read_csv(ROOT/'new_pro_audit/current891_extension/current891_gqs_audit_scores.csv').set_index('object_id')
assert set(old.index)==set(new.index) and len(old)==891
for left,right in [('annotation_points_sha256','annotation_points_sha256'),('reference_points_sha256','reference_points_sha256'),('answer_3d_sha256','answer_sha256'),('reference_3d_sha256','reference_sha256')]:assert (old[left]==new.loc[old.index,right]).all()
x=new[['record_id','image_code','height_local_error']].join(old[['Hcenter','Hmean']])
x['new_minus_old_local']=x.height_local_error-x.Hcenter
x.to_csv(args.out)
d=x.new_minus_old_local.abs();print(json.dumps(dict(rows=len(x),abs_delta_median=float(d.median()),abs_delta_mean=float(d.mean()),abs_delta_max=float(d.max())),indent=2))
