#!/usr/bin/env python3
"""Summarize saved v2.1 team results; never select, fuse, score, or refit.

Run from a populated HOHONET checkout, or pass --root.  Source paths are explicit.
The only new calculation is finite-table aggregation, distributions and identity
checks.  Missing quality remains missing.  Source CSVs are never changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HEAD = '48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CUR = 'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
OLD = 'research/workers/personnel_v21_reselection_20261029'
AC = 'research/workers/personnel_ac_v21_20261030'
AUX = 'research/fusion/manual_order_impact_20261104'
METHODS = ['TARGET_DSTRUCT_K3', 'RFUSE_GEOM_K2', 'OPPJOINT_K3', 'OPPJOINT_K4']
ALL_METHODS = ['TARGET_DSTRUCT_K2'] + METHODS
SOURCES = {}
CHECKS = {}
METRICS = ['B8L2', 'D10', 'IoU3D100', 'fusion_turn_n', 'fusion_short_turn_edges',
           'fusion_redundancy_n', 'geometry_area_h2', 'height_mean_h',
           'centroid_x_h', 'centroid_z_h', 'S_bottom_deg', 'omission', 'extension',
           'failure', 'connection_available', 'log_recorded_time',
           'recorded_time_total_seconds']

def read(path, **kwargs):
    p = ROOT / path
    data = p.read_bytes()
    SOURCES[path] = {'path': path, 'sha256': hashlib.sha256(data).hexdigest(),
        'bytes': len(data), 'source_commit': HEAD,
        'url': 'https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/' + HEAD + '/' + path}
    return pd.read_csv(p, **kwargs)

def save(frame, name):
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig', float_format='%.12g')

def composition_path(method, filename):
    if method.startswith('OPPJOINT'):
        return OLD + '/additional_delivery/packages/03B_03/composition/primary_manual45/by_method/' + method + '/' + filename
    return CUR + '/composition/primary/by_method/' + method + '/' + filename

def label_version(method):
    return 'OPPJOINT_20261029_unchanged_current' if method.startswith('OPPJOINT') else 'image_difficulty_20261030_current'

def hierarchy_mean(frame, values):
    return (frame.groupby(['building', 'image', 'pool_id'])[values].mean()
        .groupby(['building', 'image'])[values].mean()
        .groupby('building')[values].mean().mean())

def overlay(original, patch, keys, label):
    """Keyed replacement of affected saved summary cells, preserving all others."""
    original=original.copy();patch=patch.copy()
    for c in keys:
        if c in ['n','m','n_from','n_to','m_from','m_to']:
            for d in [original,patch]:
                d[c]=pd.to_numeric(d[c],errors='coerce').map(lambda x: '' if pd.isna(x) else f'{x:g}')
        else:
            original[c]=original[c].fillna('').astype(str)
            patch[c]=patch[c].fillna('').astype(str)
    a=original.set_index(keys);b=patch.set_index(keys)
    assert not a.index.duplicated().any(),label+'_original_duplicates'
    assert not b.index.duplicated().any(),label+'_patch_duplicates'
    missing=b.index.difference(a.index)
    assert not len(missing),(label,'unexpected_patch_keys',list(missing[:3]))
    CHECKS[label+'_patched_rows']=len(b)
    return pd.concat([a.drop(b.index),b]).reset_index()

def saved_sensitivity():
    path=AC+'/stage05_sensitivity/results_v1/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz'
    chunks=[]
    for d in read(path,chunksize=50000,low_memory=False):
        x=d[d.method.isin(METHODS)&(d.scope=='primary')&(d.condition=='manual')&d.metric.str.contains('B8L2')].copy()
        chunks.append(x)
    original=pd.concat(chunks,ignore_index=True)
    original['source']=path;original['endpoint_version']='saved_automatic_unhit'
    ppath=AUX+'/ac/sensitivity/assisted_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz'
    p=read(ppath);p=p[p.method.isin(METHODS)&(p.scope=='primary')&(p.condition=='manual')&p.metric.str.contains('B8L2')].copy()
    p['source']=ppath;p['endpoint_version']='manual_assisted_expanded'
    keys=list(original.columns[:18])
    d=overlay(original,p,keys,'sensitivity')
    d['label_version']=d.method.map(lambda m:'AC_frozen_TARGET_not_current_relabel' if m.startswith('TARGET') else 'AC_labels_current_identity_on_covered_LOBO_folds')
    save(d,'EXISTING_COALITIONS_MEMBERS_BACKGROUND_Q.csv.gz')
    path=AC+'/stage05_sensitivity/exact_outside_background_v1/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz'
    outside=read(path);outside=outside[outside.method.isin(METHODS)&(outside.scope=='primary')&(outside.condition=='manual')&outside.metric.str.contains('B8L2')].copy()
    outside['source']=path;outside['endpoint_version']='automatic_primary_conditions_unhit'
    save(outside,'EXACT_FIXED_BLOCK_BACKGROUND_PRIMARY_Q.csv')
    path=AC+'/stage05_sensitivity/three_leg_common_support_v2/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz'
    three=read(path);three=three[three.method.isin(METHODS)&(three.scope=='primary')&(three.condition=='manual')&(three.metric=='B8L2_CA')].copy()
    three['source']=path;three['endpoint_version']='saved_automatic_unhit'
    ppath=AUX+'/ac/sensitivity/three_leg_common_support_v2/assisted/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz'
    p=read(ppath);p=p[p.method.isin(METHODS)&(p.scope=='primary')&(p.condition=='manual')&(p.metric=='B8L2_CA')].copy()
    p['source']=ppath;p['endpoint_version']='manual_assisted_expanded'
    three=overlay(three,p,list(three.columns[:9]),'three_leg')
    assert np.nanmax(np.abs(three.total_image_mean-three.equal_image_mean-three.addition_image_mean))<1e-9
    save(three,'UNEQUAL_COMPLETE_CLASSES_THREE_LEG_Q.csv')
    return d,outside,three

def make_figures(common_summary, summaries):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['DSTRUCT K3','RFUSE K2','JOINT K3','JOINT K4']
    colors=['#24577e','#4d8a82','#b58331','#8a5a90']
    fig,axs=plt.subplots(1,3,figsize=(10.8,3.8),constrained_layout=True)
    for ax,(metric,title,foot) in zip(axs,[('B8L2','Quality Q','174 panels / 32 images'),('fusion_turn_n','Retained turns','174 panels / 32 images'),('log_recorded_time','Log recorded team labor','130 panels / 31 images')]):
        d=common_summary[(common_summary.summary_axis=='all')&(common_summary.metric==metric)].set_index('method')
        vals=[100*d.loc[m,'between_share'] for m in METHODS]
        bars=ax.bar(labels,vals,color=colors,width=.65)
        ax.bar_label(bars,fmt='%.1f%%',padding=4,fontsize=9)
        ax.set_ylim(0,44);ax.set_title(title,fontsize=12);ax.set_ylabel('Between-composition share (%)')
        ax.tick_params(axis='x',labelrotation=35,labelsize=9)
        ax.text(.5,.98,foot,ha='center',va='top',transform=ax.transAxes,fontsize=8,color='#555555')
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(OUT/'COMMON_TEAM_COMPOSITION_VARIANCE.png',dpi=220,bbox_inches='tight')
    fig.savefig(OUT/'COMMON_TEAM_COMPOSITION_VARIANCE.svg',bbox_inches='tight');plt.close(fig)
    d=pd.concat(summaries)
    d=d[(d.method=='TARGET_DSTRUCT_K3')&(d.summary_axis=='difficulty')&(d.metric=='B8L2')].set_index('summary_value')
    levels=['简单','中等','困难'];x=np.arange(3)
    fig,ax=plt.subplots(figsize=(6.5,3.8),constrained_layout=True)
    a=[d.loc[z,'between_variance'] for z in levels];b=[d.loc[z,'within_variance'] for z in levels]
    ax.bar(x,a,label='Between class compositions',color='#24577e');ax.bar(x,b,bottom=a,label='Members within a composition',color='#aac3d5')
    ax.set_xticks(x,['Easy (22 images)','Medium (3 images)','Hard (15 images)']);ax.set_ylabel('Quality variance (Q points squared)')
    ax.set_title('DSTRUCT K3: both sources of variation increase on hard images')
    ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,fontsize=9)
    fig.savefig(OUT/'DSTRUCT_DIFFICULTY_VARIANCE.png',dpi=220,bbox_inches='tight')
    fig.savefig(OUT/'DSTRUCT_DIFFICULTY_VARIANCE.svg',bbox_inches='tight');plt.close(fig)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summaries=[]; panels={}; configurations={}
    for method in ALL_METHODS:
        path=composition_path(method, 'SUMMARY.csv')
        d=read(path)
        d=d[(d.support=='method_known') & d.metric.isin(METRICS)].copy()
        d['source']=path; d['label_version']=label_version(method)
        d['endpoint_version']='v2.1_saved_automatic_primary_unaffected_by_57_orders'
        summaries.append(d)
        if method not in METHODS: continue
        path=composition_path(method,'PANEL_VARIANCE.csv.gz')
        d=read(path); d=d[(d.support=='method_known') & d.metric.isin(METRICS)].copy()
        d['source']=path; panels[method]=d
        path=composition_path(method,'CONFIGURATION_DISTRIBUTIONS.csv.gz')
        c=read(path); c=c[(c.support=='method_known') & (c.metric=='B8L2')].copy()
        c['source']=path; configurations[method]=c
        # Independent reconstruction of saved building-balanced variance summary.
        vals=['total_variance','within_variance','between_variance']
        q=d[(d.metric=='B8L2') & (d.valid_teams>0)]
        got=hierarchy_mean(q,vals)
        expected=summaries[-1][(summaries[-1].summary_axis=='all') & (summaries[-1].metric=='B8L2')].iloc[0]
        CHECKS['saved_summary_parity_'+method]=float(np.max(np.abs(got-expected[vals].astype(float))))
        assert CHECKS['saved_summary_parity_'+method]<1e-9
    save(pd.concat(summaries,ignore_index=True),'PRIMARY_COMPOSITION_ALL_METRICS.csv')

    # Restrict to full 12-choose-6 panels: identical exact team census, not only
    # same image IDs.  Partial-known OPPJOINT panels cannot be compared by merely
    # intersecting their panel names with the complete TARGET/RFUSE panels.
    fullsets=[set(d[(d.metric=='B8L2') & (d.teams==924) & (d.expected_known_panel_teams==924)].panel_id) for d in panels.values()]
    common=set.intersection(*fullsets)
    CHECKS['common_complete_924_team_panels']=len(common)
    checkcols=['total_variance','valid_teams','teams']
    baseline=None
    for method,d in panels.items():
        x=d[d.panel_id.isin(common)].set_index(['panel_id','metric','time_source'])[checkcols].sort_index()
        if baseline is None: baseline=x
        else:
            assert baseline.index.equals(x.index), method
            dif=(baseline-x).abs().max()
            CHECKS['common_total_variance_max_difference_'+method]=float(dif['total_variance'])
            assert dif['total_variance']<1e-8 and dif['valid_teams']==0 and dif['teams']==0
    meta=panels[METHODS[0]]
    save(meta[(meta.metric=='B8L2')&meta.panel_id.isin(common)][['panel_id','pool_id','image','building','n','difficulty','teams','valid_teams']], 'COMMON_COMPLETE_PANEL_SUPPORT.csv')
    rows=[]
    for method,d in panels.items():
        d=d[d.panel_id.isin(common)]
        for axis in ['all','difficulty']:
            groups=[('all',d)] if axis=='all' else d.groupby('difficulty')
            for value,g in groups:
                for (metric,time_source),s in g.groupby(['metric','time_source']):
                    s=s[(s.valid_teams>0)&s.total_variance.notna()]
                    if s.empty: continue
                    vals=hierarchy_mean(s,['total_variance','within_variance','between_variance'])
                    rows.append(dict(method=method,scope='primary',condition='manual',
                        label_version=label_version(method),endpoint_version='automatic_primary_unaffected',
                        support='common_full_924_team_panels',summary_axis=axis,summary_value=value,
                        metric=metric,time_source=time_source,panels=len(s),images=s.image.nunique(),
                        buildings=s.building.nunique(),valid_team_links=int(s.valid_teams.sum()),
                        **vals.to_dict(),between_share=vals.between_variance/vals.total_variance if vals.total_variance else np.nan,
                        between_rms=np.sqrt(vals.between_variance),within_rms=np.sqrt(vals.within_variance),
                        weighting='panel_then_pool_then_image_then_building_equal',source=composition_path(method,'PANEL_VARIANCE.csv.gz')))
    common_summary=pd.DataFrame(rows)
    save(common_summary,'COMMON_COMPLETE_PANEL_METRICS.csv')

    # Each row describes one finite panel, not an independent population sample.
    rows=[]
    for method,c in configurations.items():
        for panel,s in c.groupby('panel_id'):
            s=s[s.valid_teams>0]
            if s.empty: continue
            est=s[s.valid_teams>=2]
            r=s.iloc[0]
            rows.append(dict(method=method,panel_id=panel,image=r.image,building=r.building,
                n=r.n,difficulty=r.difficulty,common_complete_panel=panel in common,
                configurations=len(s),estimable_configurations=len(est),valid_team_links=int(s.valid_teams.sum()),
                configuration_Q_mean_min=s['mean'].min(),configuration_Q_mean_max=s['mean'].max(),
                configuration_Q_mean_range=s['mean'].max()-s['mean'].min(),
                within_sd_median=est.sd.median(),within_sd_max=est.sd.max(),
                within_p05_p95_width_median=(est.p95-est.p05).median(),
                within_p05_p95_width_max=(est.p95-est.p05).max(),
                singleton_configurations=int((s.valid_teams==1).sum()),source=r.source))
    member=pd.DataFrame(rows);save(member,'MEMBER_VARIATION_BY_PANEL_Q.csv')
    desc=[]
    for method,g in member.groupby('method'):
        for support,s in [('own_known_panels',g),('common_complete_panels',g[g.common_complete_panel])]:
            for metric in ['configuration_Q_mean_range','within_sd_median','within_sd_max','within_p05_p95_width_median']:
                x=s[metric].dropna();desc.append(dict(method=method,support=support,metric=metric,panels=len(x),
                    mean=x.mean(),p10=x.quantile(.1),median=x.median(),p90=x.quantile(.9),
                    minimum=x.min(),maximum=x.max(),weighting='descriptive_panel_distribution_not_macro_effect'))
    save(pd.DataFrame(desc),'MEMBER_VARIATION_DISTRIBUTIONS.csv')

    halfpath=AUX+'/half_qonly/HALF_SUMMARY.csv'
    h=read(halfpath);h=h[h.scope=='updated_labels_legal_subset'].copy();h['source']=halfpath
    h['method']='TARGET_DSTRUCT_K3';h['label_version']='image_difficulty_20261030_current_legal_subset'
    save(h,'STRICT_ABC_CURRENT_METRICS.csv')
    hi=read(AUX+'/half_qonly/HALF_IMAGES.csv.gz');hi=hi[hi.scope=='updated_labels_legal_subset']
    rows=[]
    for (version,n),s in hi.groupby(['version','n']):
        for metric in ['gap_A','gap_sym','CB']:
            x=s[metric].dropna()
            rows.append(dict(method='TARGET_DSTRUCT_K3',version=version,n=n,m=7,metric=metric,
                valid_images=len(x),positive=int((x>0).sum()),negative=int((x<0).sum()),exact_zero=int((x==0).sum()),
                below_minus_0_5=int((x<-.5).sum()),between_minus_0_5_plus_0_5=int(x.between(-.5,.5).sum()),above_plus_0_5=int((x>.5).sum()),
                mean=x.mean(),median=x.median(),p10=x.quantile(.1),p90=x.quantile(.9),
                units='Q_points',near_zero_band_is_descriptive='yes_not_significance_test',
                source=AUX+'/half_qonly/HALF_IMAGES.csv.gz'))
    save(pd.DataFrame(rows),'STRICT_ABC_IMAGE_DIRECTION_DISTRIBUTIONS.csv')
    m=read(AUX+'/half_qonly/HALF_MATCHED_BACKGROUND_SUMMARY.csv')
    m=m[m.label_scope=='updated_labels_legal_subset'].copy();m['source']=AUX+'/half_qonly/HALF_MATCHED_BACKGROUND_SUMMARY.csv'
    save(m,'STRICT_ABC_MATCHED_BACKGROUND.csv')
    d=read(AUX+'/half_qonly/HALF_DIFFICULTY.csv');d=d[d.scope=='updated_labels_legal_subset'].copy()
    save(d,'STRICT_ABC_DIFFICULTY.csv')

    path=AUX+'/same_room/QUALITY_COMPONENT_REPETITION_SUMMARY.csv'
    room=read(path);room['source']=path
    save(room[room.version=='assisted_expanded_support'],'SAME_ROOM_STRICT_ABC_CURRENT.csv')
    path=AUX+'/same_room/geometry/CURRENT_SUMMARY.csv';d=read(path);d['source']=path
    save(d,'SAME_ROOM_STRICT_GEOMETRY_CURRENT.csv')
    rooms=[]
    for method in ['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','RFUSE_GEOM_K2']:
        path=CUR+'/same_room_composition/'+method+'_SUMMARY.csv'
        d=read(path);d=d[(d.budget=='mid_n_rep0')&(d.analysis_layer=='ordinary_comparable')].copy()
        d['source']=path;rooms.append(d)
    save(pd.concat(rooms),'SAME_ROOM_COMPOSITION_CURRENT.csv')

    # Main AC patch contains only affected conditions.  Overlay by full condition
    # key so unhit OPPJOINT/RFUSE conditions remain their saved original results.
    origpath=AC+'/stage05_main/KEY_OUTCOME_SUMMARY.csv.gz'
    ac=read(origpath);ac['source']=origpath;ac['endpoint_version']='saved_automatic_unhit'
    patchpath=AUX+'/ac/main_assisted_affected_conditions/KEY_OUTCOME_SUMMARY.csv.gz'
    patch=read(patchpath);patch['source']=patchpath;patch['endpoint_version']='manual_assisted_expanded'
    key=['analysis_view','scope','condition','layer','method','role_direction','n_condition','m_condition','metric']
    for k in key:ac[k]=ac[k].astype(str);patch[k]=patch[k].astype(str)
    ac=ac.set_index(key);patch=patch.set_index(key)
    assert not ac.index.duplicated().any() and not patch.index.duplicated().any()
    missing=patch.index.difference(ac.index);assert not len(missing)
    ac=ac.drop(patch.index);ac=pd.concat([ac,patch]).reset_index()
    ac=ac[ac.method.isin(ALL_METHODS)].copy()
    ac['label_version']=ac.method.map(lambda m:'AC_frozen_TARGET_20261030_not_current_relabel' if m.startswith('TARGET') else 'AC_frozen_labels_exact_current_identity_on_covered_LOBO_folds')
    save(ac,'DIRECT_AC_EXISTING_CONDITIONS.csv.gz')

    path=OLD+'/independent_review/reaudit_20261029/ALL_DIRECTION_RECOMPUTED.csv'
    hist=read(path);hist=hist[hist.method.isin(METHODS)].copy();hist['source']=path
    hist['label_version']='reaudit_20261029_frozen_labels';hist['endpoint_version']='saved_automatic_historical'
    hist['support_unit']='images';save(hist,'STRICT_ABC_FROZEN_OTHER_METHODS.csv')
    path=AUX+'/alliances/MANUAL_ASSISTED_FULL_VS_BEST_PURE_SUMMARY.csv'
    alliance=read(path);alliance['source']=path;save(alliance,'TARGET_K3_FULL_VS_BEST_PURE.csv')
    path=AUX+'/alliances/MANUAL_ASSISTED_CLASS_METRIC_SUMMARY.csv'
    d=read(path);d['source']=path;save(d,'TARGET_K3_ALLIANCE_METRICS.csv')
    for f in ['CASE_OVERVIEW.csv','ALL_CONFIGURATIONS_Q_READABLE.csv','LOBO_ROLE_DEFINITIONS_AND_MEMBERS.csv']:
        path=OLD+'/composition/OPPJOINT_K4_complete_configuration_cases/'+f
        d=read(path);d['source']=path;save(d,'JOINT_EXISTING_'+f)

    sensitivity,outside,three=saved_sensitivity()

    # Compact integration table: quantitative meanings and provenance travel with
    # every entry; support is never silently substituted between modalities.
    evidence=[]
    def add(**kw):
        defaults=dict(scope='primary',condition='manual',n='varies',k='',m='',support='',
            effect='',units='',source='',interpretation='',label_version='',endpoint_version='',decision='保持')
        defaults.update(kw);evidence.append(defaults)
    for _,r in common_summary[common_summary.summary_axis=='all'].iterrows():
        add(method=r.method,layer='fixed_n_composition',k=r.method.rsplit('K',1)[-1],
            metric=r.metric, support=f'{r.panels} complete panels/{r.images} images/{r.buildings} buildings/{r.valid_team_links} valid team-links',
            effect=100*r.between_share,units='percent_of_finite_panel_variance',source=r.source,
            label_version=r.label_version,endpoint_version=r.endpoint_version,
            interpretation='固定已有团队、人数和背景下，类别配比组织的波动份额；其余为同配比具体成员波动。')
    for _,r in h[(h.version=='assisted_expanded')&h.metric.isin(['gap_A','gap_sym','CB','fusion_turn_n__gap_S','record_time_CB_pct_source_matched'])].iterrows():
        add(method='TARGET_DSTRUCT_K3',layer='strict_ABC',k=3,n=int(r.n),m=int(r.m),metric=r.metric,
            support=f'{r.valid_events}/{r.registered_events} events; {r.images} images; {r.buildings} buildings',
            effect=r['mean'],units='recorded_labor_percent' if 'time' in r.metric else ('turn_count' if 'turn' in r.metric else 'Q_points'),
            source=r.source,label_version=r.label_version,endpoint_version=r.version,
            interpretation='G为跨类额外变化幅度；CB为质量方向；劳动使用自身同源有效支持。',decision='幅度变化' if 'time' not in r.metric else '保持')
    for _,r in room[(room.version=='assisted_expanded_support')&(room.metric=='B8L2')].iterrows():
        add(method=r.method_updated,layer='same_room_strict_ABC',k=r.method_updated.rsplit('K',1)[-1],n=int(r.n),m=int(r.m),metric=r.contrast,
            support=f'{r.common6_events}/{r.events} six-endpoint-Q events; {r.valid_pairs} physical pairs; {r.valid_buildings} buildings',
            effect=r.pair_mean,units='Q_points',source=r.source,label_version=r.scope,endpoint_version=r.version,
            interpretation=f'{r.updated_direction}; 正/负图对={r.positive_pairs}/{r.negative_pairs}；两视角均正={r.both_positive_pairs}。')
    selected=ac[(ac.scope=='primary')&(ac.condition=='manual')&(ac.metric=='B8L2_CA')&(
        ((ac.analysis_view=='A_fixed_n')&ac.n_condition.isin(['20','28'])&ac.m_condition.isin(['4','7','10'])) |
        (ac.analysis_view=='whole_unequal_no_background') |
        ((ac.analysis_view=='A_fixed_n_pure_class')&ac.n_condition.isin(['4','8'])))]
    for _,r in selected.iterrows():
        add(method=r.method,layer='direct_AC_'+r.analysis_view,k=r.method.rsplit('K',1)[-1],n=r.n_condition,m=r.m_condition,
            metric='Q_C_minus_Q_A',support=f'{r.valid_pairs} physical comparisons/{r.valid_images} images/{r.valid_buildings} buildings',
            effect=r.image_mean,units='Q_points',source=r.source,label_version=r.label_version,endpoint_version=r.endpoint_version,
            interpretation=f'{r.role_direction}; {r.positive_images}正/{r.negative_images}负; 平均绝对变化{r.image_balanced_mean_absolute:.6g}分。',
            decision='条件变化' if r.method.startswith('TARGET') else '保持')
    for _,r in alliance[alliance.version=='updated'].iterrows():
        add(method='TARGET_DSTRUCT_K3',layer='all_class_union_vs_best_scoreable_pure',scope=r.scope,k=3,
            metric='full_minus_best_pure_Q',support=f'{r.pools} pools/{r.images} images; unknown_background={r.unknown_background_included}',
            effect=r.mean_full_minus_best_pure,units='Q_points',source=r.source,label_version='updated_image_difficulty',endpoint_version='manual_assisted',
            interpretation=f'纯类更好{r.pure_better_images}图、全类更好{r.full_better_images}图、持平{r.tied_images}图；最佳纯类为事后描述。',decision='保持' if r.scope=='primary' else '幅度变化')
    # Keep the complete available coalition and background Q results in the
    # unified table, rather than showing only selected favorable directions.
    for _,r in sensitivity[sensitivity.analysis_table.isin(['COMPLETE_COALITIONS','FIXED_BLOCK_BACKGROUND_STEPS','BACKGROUND_CHANGES'])].iterrows():
        add(method=r.method,layer=r.analysis_table.lower(),k=r.method.rsplit('K',1)[-1],n=r.n,m=r.m,
            metric=r.metric,support=f'{r.valid_images} images/{r.valid_buildings} buildings/{r.analysis_rows} analysis rows',
            effect=r.image_mean,units='Q_points',source=r.source,label_version=r.label_version,endpoint_version=r.endpoint_version,
            interpretation=f'{r.role_direction}; number={r.number_condition}; unknown_background={r.unknown_background_included}; n={r.n_from}→{r.n_to}; m={r.m_from}→{r.m_to}; comparison={r.comparison}; {r.positive_images}正/{r.negative_images}负',
            decision='条件变化' if r.method.startswith('TARGET') else '保持')
    save(pd.DataFrame(evidence),'UNIFIED_EVIDENCE_MATRIX.csv')
    make_figures(common_summary,summaries)
    CHECKS['new_teams']=0;CHECKS['new_fusion_or_scoring']=0;CHECKS['new_classification_fits']=0
    CHECKS['missing_quality_imputed_as_zero']=False
    CHECKS['common_variance_identity_max_error']=float((common_summary.total_variance-common_summary.within_variance-common_summary.between_variance).abs().max())
    assert CHECKS['common_variance_identity_max_error']<1e-8
    CHECKS['source_commit']=HEAD
    (OUT/'CHECKS.json').write_text(json.dumps(CHECKS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(pd.DataFrame(SOURCES.values()),'SOURCES.csv')
    print(json.dumps({'output':str(OUT),'common_complete_panels':len(common),'evidence_rows':len(evidence),'sources':len(SOURCES),'checks':'passed'},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    if args.root: ROOT=args.root.resolve()
    main()
