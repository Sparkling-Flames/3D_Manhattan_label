"""Author checks and figure from saved supplement outputs; no refitting or fusion."""
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.structure_condition_curves_20261028 import OUT, EXT, ROOT


def main():
    h=pd.read_csv(OUT/'CURVE_SOURCE_ROWS.csv.gz')
    g=pd.read_csv(OUT/'GEOMETRY_SOURCE_ROWS.csv.gz')
    for saved,path,keys in [(h,'analysis_precision26/results_stage2/HYBRID_POOLED256_DISPLAY_CURVES.csv.gz',['pool_id','k']),
                            (g,'analysis_geometry26/results_stage2/GEOMETRY_PATH_PRECISION.csv.gz',['pool_id','k','metric'])]:
        source=pd.read_csv(EXT/path)
        source=source[source.cohort.eq('pooled256') & source.pool_id.isin(h.pool_id)]
        pd.testing.assert_frame_equal(saved.sort_values(keys).reset_index(drop=True),source.sort_values(keys).reset_index(drop=True))
    curve=pd.read_csv(OUT/'CURVE_IMAGE_VALUES.csv.gz',dtype={'point':str})
    assert np.isfinite(curve.value).all()
    support=pd.read_csv(OUT/'CURVE_COMMON_SUPPORT.csv')
    for (cap,metric),s in support.groupby(['capacity','metric']):
        z=curve[curve.capacity.eq(cap)&curve.metric.eq(metric)]
        expected=set(s.loc[s.common_curve,'pool_id'])
        assert set(z.point)==set(['1',*map(str,range(3,cap+1)),'full'])
        assert all(set(v.pool_id)==expected for _,v in z.groupby('point'))
    summary=pd.read_csv(OUT/'CURVE_SUMMARY.csv',dtype={'point':str})
    groups=pd.read_csv(OUT/'IMAGE_GROUPS.csv')
    keys=['capacity','scope','group','metric','point']
    expanded=curve.merge(groups,on='pool_id',validate='many_to_many')
    direct=expanded.groupby(keys).value.mean()
    np.testing.assert_allclose(direct,summary.set_index(keys).reindex(direct.index).image_equal,atol=1e-12)
    direct_b=expanded.groupby(keys+['building']).value.mean().groupby(level=keys).mean()
    np.testing.assert_allclose(direct_b,summary.set_index(keys).reindex(direct_b.index).building_equal,atol=1e-12)
    comp=pd.read_csv(OUT/'COMPOSITION_PANEL_RESULTS.csv')
    teams=pd.read_csv(OUT/'COMPOSITION_TEAM_LABELS.csv.gz',usecols=['method','panel_id','team_key'])
    counts=teams.groupby(['method','panel_id']).team_key.agg(['size','nunique'])
    assert len(counts)==4*231 and counts.eq(924).all().all()
    assert teams[teams.method.eq('published')].team_key.nunique()==213442
    np.testing.assert_allclose(comp.total,comp.between+comp.within,atol=1e-10)
    old=pd.read_csv(ROOT/'research/workers/dstruct_composition_bridge_20261026/PANEL_VARIANCE.csv')
    joined=comp[comp.method.eq('published')].merge(old[old.method.eq('DSTRUCT_K3')],on=['panel_id','metric'],validate='one_to_one')
    assert len(joined)==462
    errors=[]
    for col in ['total','between','within']:
        errors.append(float((joined[col]-joined[col+'_variance']).abs().max()))
        np.testing.assert_allclose(joined[col],joined[col+'_variance'],atol=1e-10)
    lab=pd.read_csv(OUT/'LABEL_CHANGES.csv')
    assert lab[lab.method.eq('original_common')].changed.eq(0).all()
    assert lab.people.eq(59).all()
    events=pd.read_csv(OUT/'ABC_RELABELED.csv.gz')
    cached=pd.read_csv(OUT/'ABC_CACHED_SOURCE.csv.gz')
    joined=events.merge(cached[['stage','event_id','A_B8L2','B_B8L2','C_B8L2']],on=['stage','event_id'],validate='many_to_one')
    z=joined[joined.scored]
    np.testing.assert_allclose(z.within,abs(z.B_B8L2-z.A_B8L2),atol=1e-12)
    np.testing.assert_allclose(z.cross,(abs(z.C_B8L2-z.A_B8L2)+abs(z.C_B8L2-z.B_B8L2))/2,atol=1e-12)
    np.testing.assert_allclose(z.CB,z.C_B8L2-z.B_B8L2,atol=1e-12)
    common=events[events.common_legal & events.scored]
    assert common.groupby(['stage','event_id'])[['within','cross','CB']].nunique().eq(1).all().all()
    focus=pd.read_csv(OUT/'ABC_FOCUS_SUMMARY.csv')
    oldfocus=focus[focus.support.eq('own_legal')&focus.phase.eq('selection_heldout_building')&focus.method.eq('published')].iloc[0]
    np.testing.assert_allclose([oldfocus.within_image_equal,oldfocus.cross_image_equal],[3.437510,6.385968],atol=1e-6)
    receipt=dict(status='passed_author_checks_not_independent_acceptance',source_rows=len(h),geometry_rows=len(g),
        source_values_preserved=True,constant_curve_support=True,curve_aggregation_reproduced=True,
        old_composition_rows=462,old_composition_max_error=max(errors),teams_per_panel=924,unique_endpoints=213442,
        original_label_folds=23,ABC_scalar_recomputed_rows=len(z),common_ABC_identical_by_construction=True,
        original_headline_within=float(oldfocus.within_image_equal),original_headline_cross=float(oldfocus.cross_image_equal),
        new_fusion=0,new_scoring=0,formal_labels_changed=False)
    (OUT/'VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    plot(summary)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


def plot(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    names={'plain_H0':'无几何自遮挡、无短边','short_H0':'无几何自遮挡、有短边','H_positive':'有几何自遮挡（可含短边）'}
    colors=['#2967a0','#d07916','#ad4056']
    fig,axes=plt.subplots(2,4,figsize=(15,8),layout='constrained')
    for row,cap in enumerate([30,35]):
        for ax,(metric,title) in zip(axes[row],[('Q_mean','平均 Q'),('Q_p10','Q 的 P10'),('Q_sd_display','图内 Q 标准差'),('V_floor','底面几何 V')]):
            for (group,name),color in zip(names.items(),colors):
                z=summary[summary.capacity.eq(cap)&summary.scope.eq('turn6')&summary.group.eq(group)&summary.metric.eq(metric)&summary.point.ne('full')].copy()
                z['k']=z.point.astype(int);z=z.sort_values('k')
                # k=2 was not executed; do not draw a continuous segment across it.
                ax.scatter(z.loc[z.k.eq(1),'k'],z.loc[z.k.eq(1),'image_equal'],color=color,s=14)
                ax.plot(z.loc[z.k.ge(3),'k'],z.loc[z.k.ge(3),'image_equal'],color=color,label=f'{name}（{int(z.images.iloc[0])}图）')
            ax.set_title(f'N≥{cap}固定图片：{title}',fontsize=11)
            ax.set_xlabel('团队人数 k');ax.grid(alpha=.2);ax.set_xticks([1,6,10,20,cap])
            if metric in ['Q_mean','Q_p10']:ax.set_ylim(0,100)
            else:ax.set_ylim(bottom=0)
        axes[row,0].legend(fontsize=8,loc='lower right')
    fig.suptitle('固定参考转折数为6：不同结构条件下的人数曲线（图等权）\n上行26图，下行16图；1人为单份原答，2人未执行，融合曲线从3人开始',fontsize=13)
    fig.savefig(OUT/'固定六转折_人数曲线.png',dpi=160)
    plt.close(fig)


if __name__=='__main__':main()
