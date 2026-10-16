"""细致查阅表的共同统计：作答权重与视角权重、时间边际与共有集合分开。"""
import pandas as pd

METRICS=('B8L2','active_time_seconds','target_matched_time_seconds')


def distribution(values):
    values=pd.to_numeric(values,errors='raise').dropna()
    return dict(n=len(values),mean=values.mean() if len(values) else None,
        median=values.median() if len(values) else None,
        sd=values.std(ddof=1) if len(values)>1 else None,
        q25=values.quantile(.25) if len(values) else None,
        q75=values.quantile(.75) if len(values) else None)


def summarize_group(frame):
    """输入完整库存切片，质量与有效时间须已由固定快照屏蔽；调用方分条件。"""
    assert frame.condition.nunique()<=1, 'conditions must be summarized separately'
    assert not frame.object_id.duplicated().any(), 'candidate expansion is not an answer denominator'
    source=frame[frame.pool_analysis_eligible]
    scored=frame[frame.B8L2.notna()]
    result=dict(n_inventory_records=len(frame),n_inventory_images=frame.image_id.nunique(),
        n_inventory_workers=frame.worker_id.nunique(),n_source_records=len(source),
        n_source_images=source.image_id.nunique(),n_source_workers=source.worker_id.nunique(),
        n_excluded_records=len(frame)-len(source),n_quality_missing=len(source)-len(scored),
        n_scored_images=scored.image_id.nunique(),n_scored_workers=scored.worker_id.nunique())
    for metric in METRICS:
        result.update({metric+'_'+k:v for k,v in distribution(frame[metric]).items()})
        per_image=frame.groupby('image_id')[metric].mean().dropna()
        result[metric+'_image_equal_mean']=per_image.mean() if len(per_image) else None
    for label,metric in [('source','active_time_seconds'),('target','target_matched_time_seconds')]:
        common=frame[frame.B8L2.notna() & frame[metric].notna()]
        prefix='quality_'+label+'_time_'
        result[prefix+'n']=len(common)
        result[prefix+'images']=common.image_id.nunique()
        result[prefix+'workers']=common.worker_id.nunique()
        for name,column in [('B8L2','B8L2'),('seconds',metric)]:
            result.update({prefix+name+'_'+k:v for k,v in distribution(common[column]).items() if k!='n'})
    return result


def grouped_summary(records,dimensions):
    output=[]
    for keys,frame in records.groupby(dimensions,dropna=False,sort=True):
        keys=keys if isinstance(keys,tuple) else (keys,)
        output.append(dict(zip(dimensions,keys),**summarize_group(frame)))
    return pd.DataFrame(output)
