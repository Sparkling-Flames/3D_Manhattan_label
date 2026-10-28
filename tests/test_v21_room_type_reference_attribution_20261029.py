import numpy as np
import pandas as pd
import json
from tools.thesis_main.analysis.room_type_v21_reference_attribution_20261029 import BASE, OUT, TARGET


def test_saved_predictions_and_same_image_support():
    p=pd.read_csv(TARGET/'PREDICTIONS.csv.gz')
    support=pd.read_csv(BASE/'results/image/LOBO_TARGET_PURPOSE_SUPPORT.csv')
    keys=set(support.loc[support.repeated_recorded_purpose,'image_key']);assert len(keys)==161
    g=p[p.image_key.isin(keys)]
    assert g.groupby(['experiment','method']).size().eq(161).all()
    assert np.allclose(g.absolute_error,abs(g.predicted-g.actual),atol=1e-10)
    saved=pd.read_csv(BASE/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz')
    saved=saved[(saved.metric=='Q')&saved.method.isin(['geometry_rich','geometry_purpose_rich'])]
    old=p[p.experiment.eq('v2_original177_fixed_hyperparameters')]
    matched=old.merge(saved,on=['image_key','method'],validate='one_to_one',suffixes=('_check','_source'))
    assert len(matched)==354 and np.allclose(matched.predicted_check,matched.predicted_source,atol=1e-8,rtol=0)
    summary=pd.read_csv(TARGET/'MODEL_COMPARISON.csv').set_index(['experiment','method'])
    for (exp,method),z in g.groupby(['experiment','method']):
        assert np.isclose(z.absolute_error.mean(),summary.loc[(exp,method),'mae'],atol=1e-10)


def test_each_fold_excludes_target_and_keeps_old_configuration():
    folds=pd.read_csv(TARGET/'FIXED_FOLDS.csv')
    config=pd.read_csv(BASE/'results/image/LOBO_MODELS.csv');config=config[(config.metric=='Q')&config.method.isin(['geometry_rich','geometry_purpose_rich'])]
    merged=folds.merge(config,on=['method','held_out_building'],validate='many_to_one',suffixes=('_new','_old'))
    assert len(merged)==132 and (merged.family_new==merged.family_old).all() and (merged.alpha_new==merged.alpha_old).all()
    images=pd.read_csv(OUT/'inputs/SUPPORT.csv');original=images[images.support.eq('original_support')]
    for r in merged.itertuples():
        sample=images if r.experiment=='v21_all206_fixed_hyperparameters' else original
        assert r.train_images==int(sample.building.ne(r.held_out_building).sum())
        assert r.test_images==int(sample.building.eq(r.held_out_building).sum())


def test_nested_selection_uses_only_original_candidates_and_building_folds():
    folds=pd.read_csv(TARGET/'NESTED_FOLDS.csv');tuning=pd.read_csv(TARGET/'NESTED_TUNING.csv');splits=pd.read_csv(TARGET/'NESTED_INNER_SPLITS.csv')
    expected={('ridge',.1),('ridge',1.),('ridge',10.),('ridge',100.),('ridge_quadratic',10.),('ridge_quadratic',100.),('hgb',0.)}
    assert len(folds)==44 and len(splits)==110
    for (held,method),g in tuning.groupby(['held_out_building','method']):
        assert set(zip(g.family,g.alpha))==expected and g.inner_folds.eq(5).all()
        chosen=folds[(folds.held_out_building==held)&(folds.method==method)].iloc[0]
        best=g.iloc[g.inner_mae.to_numpy().argmin()]
        assert chosen.family==best.family and chosen.alpha==best.alpha
    for r in splits.itertuples():
        train=set(r.train_buildings.split('|'));validation=set(r.validation_buildings.split('|'))
        assert not train&validation and r.held_out_building not in train|validation
    check=json.loads((TARGET/'NESTED_ENVIRONMENT_CHECKS.json').read_text(encoding='utf8'))
    assert check['results']['v21_all206']['prediction_rows']==412
    assert check['results']['v21_all206']['prediction_rows_above_1e_8']==0
    assert check['results']['v21_all206']['candidate_rows_above_1e_8']==0
