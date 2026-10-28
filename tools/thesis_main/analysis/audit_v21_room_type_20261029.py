"""从当前原答重核同用途预测目标和全部三图Q对照，不重新拟合。"""
import json
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import OUT,read


def main():
    folder=OUT/'room_type_similarity'
    q=pd.DataFrame(read(OUT/'quality_inventory.json'))
    q=q[q.quality_usable&q.condition.eq('manual')&q.quality_use.eq('ordinary_primary')].copy()
    q['image_key']=q.image_code+'__manual'
    assert len(q)==6512 and q.image_key.nunique()==206
    images=q.groupby(['image_key','building_id']).agg(Q=('B8L2','mean'),D10=('D10','mean'),records=('object_id','size')).reset_index().set_index('image_key')
    predictions=pd.read_csv(folder/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz')
    assert not predictions.duplicated(['metric','method','image_key']).any()
    for (metric,method),d in predictions.groupby(['metric','method']):
        assert set(d.image_key)==set(images.index)
        actual=images.loc[d.image_key,metric].to_numpy()
        assert np.allclose(actual,d.actual,atol=1e-10)
        assert np.allclose(abs(actual-d.predicted),d.absolute_error,atol=1e-10)
        assert np.allclose((actual-d.predicted)**2,d.squared_error,atol=1e-9)
        if method=='training_mean':
            expected=[images.loc[images.building_id.ne(b),metric].mean() for b in d.building]
            assert np.allclose(expected,d.predicted,atol=1e-10)
    evidence=pd.read_csv(folder/'results/image/LOBO_TARGET_PURPOSE_SUPPORT.csv')
    oldnew=pd.read_csv(folder/'COMPARISON_OLD_NEW_SUPPORT.csv')
    summary=[]
    repeated=set(evidence.loc[evidence.repeated_recorded_purpose,'image_key'])
    for metric in ['Q','D10']:
        selected=predictions[predictions.metric.eq(metric)&predictions.method.isin(['geometry_rich','geometry_purpose_rich'])]
        d=selected.pivot(index='image_key',columns='method',values='absolute_error').loc[sorted(repeated)]
        saved=oldnew[(oldnew.version=='v2.1')&(oldnew.study=='image_prediction')&(oldnew.metric==metric)&(oldnew.panel=='repeated_v21')&(oldnew.comparison=='geometry_rich__geometry_purpose_rich')].iloc[0]
        assert np.isclose(d.geometry_rich.mean(),saved.baseline_mae) and np.isclose(d.geometry_purpose_rich.mean(),saved.purpose_mae)
        summary.append(dict(metric=metric,images=len(d),baseline_MAE=d.geometry_rich.mean(),purpose_MAE=d.geometry_purpose_rich.mean()))
    values={(r.image_key,r.worker_id):r.B8L2 for r in q.itertuples()}
    cols=['regime','target_key','target_building','source_same_key','source_different_key','source_building','common_workers','n_common','Q_common_mean_absdiff_same','Q_common_mean_absdiff_different','Q_common_mean_absdiff_contrast']
    events=pd.read_csv(folder/'results/image/MATCHED_THREE_IMAGE_EVENTS.csv.gz',usecols=cols)
    max_error=0.
    for r in events.itertuples():
        workers=r.common_workers.split('|');assert len(workers)==r.n_common and r.n_common>=3 and r.target_building!=r.source_building
        means=[np.mean([values[key,w] for w in workers]) for key in [r.target_key,r.source_same_key,r.source_different_key]]
        a=abs(means[0]-means[1]);b=abs(means[0]-means[2])
        err=max(abs(a-r.Q_common_mean_absdiff_same),abs(b-r.Q_common_mean_absdiff_different),abs(a-b-r.Q_common_mean_absdiff_contrast))
        max_error=max(max_error,err);assert err<1e-9
    result=dict(data_release='v2.1',ordinary_manual_records=len(q),images=len(images),all_prediction_targets_and_errors_checked=len(predictions),training_mean_excludes_target_building=True,
        paired_three_image_events_checked=len(events),maximum_Q_contrast_difference=max_error,reported_support_comparison=summary,
        independent_scope='current raw Q -> image targets / prediction losses / all matched three-image mean-Q contrasts; no refit or fusion',
        limitation='geometry model fitting and nested CV implementation reused; no external validation or new causal claim')
    (folder/'INDEPENDENT_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
