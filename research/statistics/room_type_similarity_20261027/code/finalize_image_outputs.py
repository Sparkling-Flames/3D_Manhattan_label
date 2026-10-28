#!/usr/bin/env python3
"""Finite support/weighting summaries, no additional fitting or fusion."""
import argparse,json,hashlib,gzip,itertools
from pathlib import Path
import numpy as np
import pandas as pd

def write(d,p):d.to_csv(p,index=False,compression={'method':'gzip','mtime':0} if p.suffix=='.gz' else None)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',type=Path,required=True);z=ap.parse_args();r=z.study/'results/image';d=pd.read_csv(z.study/'inputs/images.csv').set_index('image_key');rows=[]
    gains=pd.read_csv(r/'LOBO_INCREMENT_PER_IMAGE.csv');sp=pd.read_csv(r/'LOBO_TARGET_PURPOSE_SUPPORT.csv');repeat=set(sp.loc[sp.repeated_recorded_purpose,'image_key'])
    for (metric,method,baseline),gg in gains.groupby(['metric','method','baseline']):
        for cohort,g in [('ALL177',gg),('REPEATED_PURPOSE161',gg[gg.image_key.isin(repeat)])]:
            for held in sorted(g.building.unique()):
                h=g[g.building!=held];b=h.groupby('building').gain_mae.mean()
                rows.append(dict(metric=metric,method=method,baseline=baseline,cohort=cohort,removed_evaluation_building=held,n_images=len(h),n_buildings=h.building.nunique(),gain_image_equal=h.gain_mae.mean(),gain_building_equal=b.mean(),improved_images=int((h.gain_mae>1e-10).sum()),worsened_images=int((h.gain_mae<-1e-10).sum()),near_zero_images=int((h.gain_mae.abs()<=1e-10).sum()),improved_buildings=int((b>1e-10).sum()),worsened_buildings=int((b<-1e-10).sum()),note='Sensitivity of already-held-out predictions; does not refit models after deleting this evaluation building'))
    write(pd.DataFrame(rows),r/'LOBO_EVALUATION_BUILDING_DELETION.csv')
    summary=pd.read_csv(r/'LOBO_PREDICTION_SUMMARY.csv');inc=pd.read_csv(r/'LOBO_INCREMENT_SUMMARY.csv');rows=[]
    for z in inc[inc.method.eq('geometry_purpose_rich')].itertuples():
        aa=summary[(summary.metric==z.metric)&(summary.method=='geometry_rich')&(summary.subset==z.subset)].iloc[0];bb=summary[(summary.metric==z.metric)&(summary.method=='geometry_purpose_rich')&(summary.subset==z.subset)].iloc[0]
        rows.append(dict(metric=z.metric,subset=z.subset,images=z.images,buildings=z.buildings,baseline_mae=aa.mae,purpose_mae=bb.mae,mae_gain=z.gain_image_equal,baseline_rmse=aa.rmse,purpose_rmse=bb.rmse,rmse_gain=aa.rmse-bb.rmse,building_equal_gain=z.gain_building_equal,improved_images=z.improved_images,worsened_images=z.worsened_images,improved_buildings=z.improved_buildings,worsened_buildings=z.worsened_buildings,building_boot_p025=z.building_boot_p025,building_boot_p975=z.building_boot_p975))
    write(pd.DataFrame(rows),r/'RICH_GEOMETRY_PURPOSE_MAIN_READOUT.csv')
    hist=pd.read_csv(r/'LOBO_HISTORY_FEATURES.csv.gz');hist=hist[(hist.metric=='Q')&(hist.role=='test')]
    write(hist[['image_key','building','pool_history_relative','pool_history_absolute','pool_history_known_fraction']],r/'CROSSFITTED_POOL_HISTORY_TEST_FEATURES.csv')
    write(hist[['pool_history_relative','pool_history_absolute','pool_history_known_fraction']].describe().T.reset_index(names='metric'),r/'POOL_HISTORY_FEATURE_DISTRIBUTION.csv')
    mi=d[(d.condition=='manual')&(d.layer=='ordinary')];sets={key:set(json.loads(row.workers_json)) for key,row in mi.iterrows()}
    jaccard=[len(sets[aa]&sets[bb])/len(sets[aa]|sets[bb]) for aa,bb in itertools.combinations(sets,2)]
    (r/'POOL_MEMBER_COMPOSITION_SUMMARY.json').write_text(json.dumps({'ordinary_manual_images':len(sets),'distinct_actual_formal_worker_sets':len({tuple(sorted(v)) for v in sets.values()}),'image_mean_Q_standard_deviation':mi.mean_Q.std(),'pairwise_jaccard_p10_median_p90':np.quantile(jaccard,[.1,.5,.9]).tolist(),'pairs_descriptive_only':len(jaccard),'note':'Actual formal-quality member sets; descriptive overlap, not independent pairs or experiment'},indent=2)+'\n')
    rows=[]
    for prefix in ['PAIR','MATCHED']:
        f=r/(prefix+'_CONTRAST_PER_TARGET.csv.gz')
        if not f.exists():continue
        x=pd.read_csv(f)
        for metric,g in x.groupby('metric'):
            regimes=sorted(g.regime.unique());counts=g.groupby('target_key').regime.nunique();common=set(counts[counts==len(regimes)].index)
            for regime,h in g[g.target_key.isin(common)].groupby('regime'):
                rows.append(dict(family=prefix,metric=metric,regime=regime,n_images=len(h),n_buildings=h.building.nunique(),same=h.same.mean(),different=h.different.mean(),effect_image_equal=h.same_minus_different.mean(),effect_building_equal=h.groupby('building').same_minus_different.mean().mean(),negative_images=int((h.same_minus_different<-1e-10).sum()),positive_images=int((h.same_minus_different>1e-10).sum()),zero_images=int((h.same_minus_different.abs()<=1e-10).sum()),support_rule='each target available in all listed regimes for this metric'))
    write(pd.DataFrame(rows),r/'COMPARISON_COMMON_TARGET_SUPPORT.csv')
    f=r/'MATCHED_THREE_IMAGE_EVENTS.csv.gz'
    if f.exists():
        t=pd.read_csv(f,low_memory=False);rows=[]
        assert not t.duplicated(['regime','target_key','source_same_key','source_different_key']).any()
        assert (t.target_building!=t.source_building).all()
        assert (t.source_same_key.map(d.building)==t.source_different_key.map(d.building)).all()
        assert (t.target_key.map(d.room_type_model)==t.source_same_key.map(d.room_type_model)).all()
        assert (t.target_key.map(d.room_type_model)!=t.source_different_key.map(d.room_type_model)).all()
        sets={key:set(json.loads(row.workers_json)) for key,row in d[d.n_formal>0].iterrows()}
        for row in t[['target_key','source_same_key','source_different_key','n_common','common_workers']].itertuples(index=False):
            common=set(row.common_workers.split('|'));assert len(common)==row.n_common and len(common)>=3
            assert common==(sets[row.target_key]&sets[row.source_same_key]&sets[row.source_different_key])
        for metric in ['ref_turn5','ref_H','ref_short_edges','ref_min_horizontal_deg','ref_radius_p90_h']:
            vals=d[metric];t['balance']=abs(t.source_same_key.map(vals)-t.source_different_key.map(vals))
            for regime,g in t.groupby('regime'):
                a=g.groupby(['target_key','target_building','source_building','source_same_key']).balance.mean().reset_index();a=a.groupby(['target_key','target_building','source_building']).balance.mean().reset_index();a=a.groupby(['target_key','target_building']).balance.mean().reset_index()
                rows.append(dict(regime=regime,metric=metric,n_target_images=len(a),n_target_buildings=a.target_building.nunique(),mean_absolute_source_difference=a.balance.mean(),target_median=a.balance.median(),target_p90=a.balance.quantile(.9)))
        write(pd.DataFrame(rows),r/'MATCHING_SOURCE_GEOMETRY_BALANCE.csv')
        # Same difficulty of S/C is the matching design. This separate reaggregation also
        # requires T to have that difficulty; no teams, answers or models are recomputed.
        rows=[];metric_list=['Q_common_mean_absdiff','D10_common_mean_absdiff','Q_common_relative_absdiff','Q_common_spearman','annotation_turn5_common_mean_absdiff','turn_delta_common_mean_absdiff','actual_simplification_common_mean_absdiff','bottom_bias_9_common_mean_absdiff','dir_common_mean_absdiff']
        comparable=t[(t.regime=='source_building_difficulty_geometry')&(t.target_difficulty==t.source_same_difficulty)]
        for metric in metric_list:
            cols=[metric+x for x in ['_same','_different','_contrast']]
            a=comparable.groupby(['target_key','target_building','purpose','source_building','source_same_key'])[cols].mean().reset_index();b=a.groupby(['target_key','target_building','purpose','source_building'])[cols].mean().reset_index();c=b.groupby(['target_key','target_building','purpose'])[cols].mean().reset_index()
            for row in c.itertuples(index=False,name=None):rows.append(dict(target_key=row[0],building=row[1],purpose=row[2],metric=metric,same=row[3],different=row[4],same_minus_different=row[5]))
        cm=pd.DataFrame(rows);write(cm,r/'MATCHED_ALL_THREE_SAME_DIFFICULTY_PER_IMAGE.csv')
        rows=[]
        for metric,g in cm.groupby('metric'):
            for purpose,h in [('ALL',g)]+list(g.groupby('purpose')):
                v=h.same_minus_different.dropna();bb=h.groupby('building').same_minus_different.mean().dropna()
                rows.append(dict(metric=metric,purpose=purpose,n_images=len(v),n_buildings=len(bb),same=h.same.mean(),different=h.different.mean(),effect_image_equal=v.mean(),effect_building_equal=bb.mean(),negative_images=int((v<-1e-10).sum()),positive_images=int((v>1e-10).sum()),near_zero_images=int((v.abs()<=1e-10).sum()),negative_buildings=int((bb<-1e-10).sum()),positive_buildings=int((bb>1e-10).sum())))
        write(pd.DataFrame(rows),r/'MATCHED_ALL_THREE_SAME_DIFFICULTY_SUMMARY.csv')
        (r/'MATCHED_ALL_THREE_SAME_DIFFICULTY_COVERAGE.json').write_text(json.dumps({'events':len(comparable),'target_images':comparable.target_key.nunique(),'target_buildings':comparable.target_building.nunique(),'source_buildings':comparable.source_building.nunique(),'same_source_images':comparable.source_same_key.nunique(),'different_source_images':comparable.source_different_key.nunique(),'common_people_median':comparable.n_common.median(),'common_people_min':int(comparable.n_common.min()),'new_comparisons':0,'method':'Reaggregate existing closest-geometry matched events with target_difficulty == source_same_difficulty == source_different_difficulty'},ensure_ascii=False,indent=2)+'\n')
    # Fixed, explicitly descriptive example search, not an estimator or a new class rule.
    f=r/'CROSS_BUILDING_IMAGE_PAIRS.csv.gz'
    if f.exists():
        p=pd.read_csv(f,low_memory=False);q=p[p.same_purpose&(p.n_common>=20)&(p.Q_common_mean_absdiff<2)].sort_values('Q_common_relative_absdiff',ascending=False)
        cols=['image_a','image_b','purpose_a','difficulty_a','difficulty_b','n_common','Q_common_mean_absdiff','Q_common_relative_absdiff','Q_common_spearman','annotation_turn5_common_mean_absdiff']
        write(q[cols].head(30),r/'EXPLANATORY_MEAN_CLOSE_PERSON_CHANGE_PAIRS.csv')
    checks=[]
    for f in sorted(r.glob('*.csv*')):
        if f.name=='IMAGE_ANALYSIS_FILE_INDEX.csv':continue
        df=pd.read_csv(f,low_memory=False)
        checks.append(dict(file=f.name,rows=len(df),fields=len(df.columns),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    write(pd.DataFrame(checks),r/'IMAGE_ANALYSIS_FILE_INDEX.csv')
    predictions=pd.read_csv(r/'LOBO_IMAGE_PREDICTIONS.csv.gz');models=pd.read_csv(r/'LOBO_MODELS.csv')
    assert not predictions.duplicated(['metric','method','image_key']).any()
    assert predictions.groupby(['metric','method']).image_key.nunique().eq(177).all()
    assert all(row.held_out_building not in row.train_buildings.split('|') for row in models.itertuples())
    for metric,col in [('Q','mean_Q'),('D10','mean_D10')]:
        x=predictions[predictions.metric==metric]
        assert np.allclose(x.actual,x.image_key.map(d[col]),atol=1e-10,rtol=0)
    (r/'COMPLETE_FINAL_IMAGE_ANALYSIS.json').write_text(json.dumps({'prediction_rows':len(predictions),'methods':sorted(predictions.method.unique()),'outer_folds_per_metric_method':22,'fit_model_rows':len(models),'target_images':177,'ordinary_manual_buildings':22,'all_metrics_methods_same_target_keys':True,'target_actuals_match_frozen_image_means':True,'outer_held_building_never_in_train_building_keys':True,'descriptive_complete':(r/'COMPLETE_descriptive.json').exists(),'new_fusion':0,'new_personnel_classification':0,'calculation_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','source_recheck_commit':'b2b0898b90bd631df37f1f2e75e8380800a43cf8','source_core_blobs_identical':True,'execution_note':'Initial model fit completed and saved; a pandas metadata/model-name collision in aggregation was corrected without refitting those models. Two same-family geometry-only controls were then added to isolate model flexibility from personnel-history inputs. Current aggregate tables include all 12 methods.'},ensure_ascii=False,indent=2)+'\n')
    (r/'FINAL_SUPPORT_SUMMARY_COMPLETE.json').write_text(json.dumps({'files_checked_to_EOF':len(checks),'new_models':0,'new_fusion':0,'main_commit_computation':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','latest_source_recheck':'b2b0898b90bd631df37f1f2e75e8380800a43cf8; five core input blobs byte-identical per source/MAIN_UPDATE_SOURCE_CHECK.json'},indent=2)+'\n')
    print('checked',len(checks),'saved CSV/gzip tables to EOF')

if __name__=='__main__':main()
