"""用v2.1已存原答与参考特征复算连续几何/二档/三档比较，不修改难度标签。"""
import json
import numpy as np
import pandas as pd
from . import difficulty_computable_comparison_20261028 as native
from .rebuild_v21_20261028 import OUT,read

TARGET=OUT/'difficulty_computable_comparison'


def inputs():
    d=pd.read_csv(OUT/'condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
    d=d[d.pool_layer.eq('ordinary_manual')].copy();assert d.object_id.is_unique
    d['difficulty']=d.difficulty_coarse
    d['has_short']=d.ref_short_edges.gt(0).astype(float)
    assert d.loc[d.has_short.eq(1),'ref_short_min_horizontal_deg'].notna().all()
    d['conditional_short_span']=d.ref_short_min_horizontal_deg.fillna(0)
    d['reduced']=(d.turn_n<d.ref_turn5).astype(float)
    d['turn_deficit']=(d.ref_turn5-d.turn_n).clip(lower=0)
    d['bottom_bias_abs']=d.bottom_bias_9.abs();d['unmatched']=d.unmatched_ref_9;d['Q']=d.B8L2
    t=pd.read_csv(native.SOURCE/'inputs/RECORD_ELIGIBILITY_TIME_LINK.csv.gz',usecols=['object_id','time_status','source_active_time_seconds'])
    d=d.merge(t,on='object_id',validate='one_to_one',suffixes=('','_frozen'))
    np.testing.assert_allclose(d.source_active_time_seconds,d.source_active_time_seconds_frozen,equal_nan=True)
    d['source']=d.time_source.map({'inherited_v1_audited_source':'old','user_processed_reported_not_raw_log_replayed':'new'});assert d.source.notna().all()
    for name,source,status in [('time_old','old','usable'),('time_new','new','reported_processed')]:
        mask=d.source.eq(source)&d.time_status.eq(status)&d.source_active_time_seconds.gt(0)
        d[name]=np.log(d.source_active_time_seconds.where(mask))
    unchanged={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_endpoints'}
    old=native.load_data();common=d[d.pool_id.isin(unchanged)].merge(old,on='object_id',suffixes=('_new','_old'),validate='one_to_one')
    assert len(common)>0
    for field in native.GEOMETRY+list(native.LOSSES):np.testing.assert_allclose(common[field+'_new'],common[field+'_old'],atol=1e-8,rtol=1e-10,equal_nan=True,err_msg=field)
    good=np.isfinite(d[native.GEOMETRY]).all(axis=1)
    d.loc[~good].to_csv(TARGET/'EXCLUDED_NONFINITE_GEOMETRY.csv',index=False,encoding='utf-8-sig')
    d=d[good].copy()
    (TARGET/'INPUT_CHECKS.json').write_text(json.dumps(dict(data_release='v2.1',records=len(d),images=d.image_id.nunique(),unchanged_records_verified=len(common),excluded_missing_geometry=int((~good).sum()),official_labels_changed=False,reference_features_reused=True)),encoding='utf8')
    return d


def main():
    TARGET.mkdir(exist_ok=True);source=native.OUT
    plan=json.loads((source/'PLAN.json').read_text(encoding='utf8'));plan.update(data_release='v2.1',original_plan=str(source/'PLAN.json'))
    (TARGET/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    d=inputs();native.OUT=TARGET;native.load_data=lambda:d;native.main()


if __name__=='__main__':main()
