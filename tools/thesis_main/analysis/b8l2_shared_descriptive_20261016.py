"""从共同评分快照追加B8L2查阅统计；不评分、不改参考或准入。"""
import numpy as np
import pandas as pd

from .b8l2_mainline_status_20261016 import summarize as wide_summary
from .descriptive_statistics_current_20261015 import summarize


def add_b8l2_descriptive_tables(tables):
    """原地追加描述表；成员变化及其基线由主生成器另行管理。"""
    analysis=tables['analysis_records']
    assert not analysis.duplicated(['image_id','condition','worker_id']).any()
    panels={f'{"ordinary" if layer=="ordinary_current" else "special"}_{condition}': cell for (layer,condition),cell in analysis.groupby(
        ['analysis_layer','condition'],dropna=False)}
    tables['by_image']=summarize(panels,['image_id','image_code'])
    tables['worker_difficulty']=summarize(panels,['worker_id','difficulty_class'])
    rows=analysis.replace({np.nan:None}).to_dict('records')
    for name,dimensions in [
        ('b8l2_worker_overview',['condition','analysis_layer','worker_id']),
        ('b8l2_image_overview',['condition','analysis_layer','image_id','image_code','difficulty_class']),
        ('b8l2_worker_difficulty',['condition','analysis_layer','worker_id','difficulty_class'])]:
        tables[name]=pd.DataFrame(wide_summary(rows,dimensions))
    timed=analysis.assign(_quality_source=analysis.B8L2.notna() & analysis.active_time_seconds.notna(),
                          _quality_target=analysis.B8L2.notna() & analysis.target_matched_time_seconds.notna())
    tables['time_coverage']=timed.groupby(['condition','analysis_layer','time_status','target_time_interpretation'],
        dropna=False).agg(n_records=('object_id','size'),n_images=('image_id','nunique'),
        n_workers=('worker_id','nunique'),n_source_time=('active_time_seconds','count'),
        n_target_time=('target_matched_time_seconds','count'),n_quality=('B8L2','count'),
        n_quality_source_time=('_quality_source','sum'),n_quality_target_time=('_quality_target','sum')).reset_index()
