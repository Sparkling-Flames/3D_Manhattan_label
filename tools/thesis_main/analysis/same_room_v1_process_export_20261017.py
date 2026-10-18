"""同房模块的窄统计接口和逐对图；只消费已验证记录，不运行融合或拟合人员。"""
import json

import numpy as np
import pandas as pd

from .same_room_v1_process_20261017 import OUT,ROOT,FUSION_OUT,VERSION,number_or_none
from .same_room_quality_curves_20261015 import save

INTERFACE='same_room_process_consumer_20261017_a1'


def consumer_masks(trace,reasons):
    result=trace.copy()
    result['pair_design_reason']=result.request_id.map(reasons)
    assert result.pair_design_reason.notna().all()
    result['primary_design_eligible']=result.pair_design_reason.eq('primary_design')
    result['primary_quality_eligible']=result.execution_status.eq('observed') & result.primary_design_eligible & result.main_comparison_allowed.eq(True)
    result['primary_quality_available']=result[['comparison_B8L2','comparison_D10']].notna().all(axis=1)
    assert not (result.primary_quality_available & ~result.primary_quality_eligible).any()
    result['primary_mask_reason']=np.select([
        result.execution_status.ne('observed'),~result.primary_design_eligible,
        ~result.main_comparison_allowed.eq(True),result.order_status.eq('two_person_sorting_deferred'),
        result.order_status.eq('needs_manual_order'),~result.complete_evaluable.eq(True),
        ~result.primary_quality_available],['not_received',result.pair_design_reason,
        'producer_main_gate_excluded','two_person_sorting_deferred','manual_order_pending',
        'geometry_incomplete','numeric_quality_missing'],default='primary_quality_available')
    return result


def design_reason(pair):
    if pair['reference_quality_primary_eligible']:return 'primary_design'
    if any(not v['reference']['full_reference_available'] for v in pair['views'].values()):return 'diagnostic_missing_full_reference'
    if any(m['bound_reference_id']!=v['reference']['target_id'] for v in pair['views'].values() for m in v['records']):return 'diagnostic_mixed_bound_targets'
    return 'diagnostic_design_excluded'


def summarize_pairs(requests,trace,paired,curves):
    rows=[]
    for pair in requests['pairs']:
        rid=pair['request_id'];n=pair['n_common_process'];replays=len(pair['replays'])
        t=trace[trace.request_id.eq(rid)];p=paired[paired.request_id.eq(rid)]
        c=curves[curves.request_id.eq(rid)].set_index('k');end=t[t.k.eq(n)]
        row=dict(request_id=rid,building=pair['building'],user_group_ids=pair['user_group_ids'],
            image_a=pair['code_a'],image_b=pair['code_b'],condition=pair['condition'],
            scene_layers='|'.join(sorted(t.layer.dropna().unique())),N=n,replays=replays,
            primary_design_eligible=pair['reference_quality_primary_eligible'],pair_design_reason=design_reason(pair),
            planned_side_prefixes=len(t),observed_side_prefixes=int(t.execution_status.eq('observed').sum()),
            complete_side_prefixes=int(t.complete_evaluable.eq(True).sum()),
            planned_paired_prefixes=len(p),both_complete=int(p.both_complete.sum()),both_primary_quality=int(p.both_quality.sum()),
            source_time_complete_prefixes=int(t.cumulative_source_seconds.notna().sum()),
            target_time_complete_prefixes=int(t.cumulative_target_seconds.notna().sum()),
            source_time_complete_full_sides=int(end.cumulative_source_seconds.notna().sum()),
            target_time_complete_full_sides=int(end.cumulative_target_seconds.notna().sum()),
            full_side_opportunities=2*replays,figure='figures/'+pair['user_group_ids']+'.png')
        for metric in ['B8L2','D10']:
            col='primary_mean_absolute_'+metric+'_gap'
            first,last=[number_or_none(c.loc[k,col]) for k in [1,n]]
            row.update({metric+'_gap_k1':first,metric+'_gap_full':last,
                metric+'_gap_full_minus_k1':None if first is None or last is None else last-first,
                metric+'_gap_direction':'unavailable' if first is None or last is None else 'smaller' if last<first else 'larger' if last>first else 'equal'})
        rows.append(row)
    return pd.DataFrame(rows)


def draw_figures(requests,trace,curves,stability,original_time):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':9})
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    colors={'a':'#1769aa','b':'#c65d13'}
    titles={'primary_design':'主质量比较','diagnostic_missing_full_reference':'诊断：缺完整顶界参考',
        'diagnostic_mixed_bound_targets':'诊断：成员绑定目标混合','diagnostic_design_excluded':'诊断：设计排除'}
    overview,grid=plt.subplots(3,3,figsize=(13,10),layout='constrained')
    for pair,small in zip(requests['pairs'],grid.flat):
        rid=pair['request_id'];n=pair['n_common_process'];group=pair['user_group_ids']
        c=curves[curves.request_id.eq(rid)].sort_values('k');t=trace[trace.request_id.eq(rid)]
        fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');q,v,complete,time=axes.flat
        reason=design_reason(pair)
        fig.suptitle(f"{group}  {pair['code_a']} / {pair['code_b']}  |  N={n}，4次配对重放，普通场景\n{titles[reason]}",fontsize=12)
        if pair['reference_quality_primary_eligible']:
            for side in ['a','b']:
                for metric,style in [('B8L2','-'),('D10','--')]:
                    q.plot(c.k,c[metric+'_'+side],style,color=colors[side],marker='o',ms=3,label=side.upper()+' '+metric)
            for metric,style in [('B8L2','-'),('D10','--')]:
                small.plot(c.k,c['primary_mean_absolute_'+metric+'_gap'],style,marker='o',ms=3,label=metric)
            q.legend(ncol=2,fontsize=8);small.legend(fontsize=7)
        else:
            for ax in [q,small]:ax.text(.5,.5,titles[reason]+'\n主质量整对掩码；没有补值',transform=ax.transAxes,ha='center',va='center')
        q.set(title='参考质量：双侧共同成功重放条件均值',ylabel='分数（高为好）',ylim=(0,100))
        small.set(title=group+'  N='+str(n),ylabel='两视角质量差绝对值均值',ylim=(0,50))
        for side in ['a','b']:
            s=stability[stability.request_id.eq(rid)&stability.side.eq(side)].sort_values('k')
            v.plot(s.k,s.mean_floor_difference,'o-',color=colors[side],ms=3,label=side.upper())
        v.set(title='同相机内：同人数重放几何差',ylabel='底面 1−IoU（低为稳）',ylim=(0,.5));v.legend(fontsize=8)
        v.text(.02,.96,'k=N集合相同，零差异不是准确性证据',transform=v.transAxes,va='top',fontsize=8)
        complete.plot(c.k,c.planned_replays,':',color='grey',label='计划')
        complete.plot(c.k,c.both_complete,'o-',label='双侧完整',ms=3)
        complete.plot(c.k,c.both_primary_quality,'s--',label='双侧主质量',ms=3)
        complete.set(title='完整率与主质量分母；k=2排序暂缓',ylabel='重放数',ylim=(-.2,4.5),yticks=range(5));complete.legend(fontsize=8)
        for side in ['a','b']:
            part=t[t.side.eq(side)];labels=set()
            for replay,g in part.groupby('replay_id'):
                g=g.sort_values('k')
                for column,style,label in [('cumulative_source_seconds','-','source'),('cumulative_target_seconds','--','target')]:
                    if g[column].notna().any():
                        time.plot(g.k,g[column],style,color=colors[side],alpha=.55,marker='o',ms=2,
                            label=side.upper()+' '+label if label not in labels else None)
                        labels.add(label)
        if time.lines:time.legend(fontsize=8,ncol=2)
        else:time.text(.5,.5,'没有完整已知的累计时间',transform=time.transAxes,ha='center')
        time.set(title='每条重放的累计时间；缺任何成员即留空',ylabel='active_time（秒）')
        for ax in [*axes.flat,small]:
            ax.set(xlabel='共同成员人数 k',xlim=(.7,n+.3),xticks=range(1,n+1));ax.grid(alpha=.2)
        fig.savefig(folder/(group+'.png'),dpi=140);plt.close(fig)
    overview.suptitle('同房质量差距：同人、同顺序；4次相关重放；k=2保留缺口\n7对主比较4缩小/3扩大；另2对诊断；全共同池不是原图全员池',fontsize=13)
    overview.savefig(folder/'quality_gap_overview.png',dpi=140);plt.close(overview)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    for ax,metric,title in zip(axes,['source_time_seconds','target_matched_time_seconds'],['来源 active_time','目标匹配 active_time']):
        d=original_time[(original_time.metric==metric)&(original_time.condition=='manual')&
            (original_time.confirmation=='user_classified_comparable')&(original_time.n_paired>=4)]
        ax.scatter(d.mean_absolute_person_delta,d.absolute_mean_gap,color='#1769aa')
        limit=max([10.,*d.mean_absolute_person_delta.dropna(),*d.absolute_mean_gap.dropna()])*1.1
        ax.plot([0,limit],[0,limit],':',color='grey')
        for row in d.itertuples():
            if row.code_a=='VFuaQ6m2Qom-07' and row.code_b=='VFuaQ6m2Qom-10':
                ax.annotate('VFua-07/10\n逐人97秒；均值0.5秒',(row.mean_absolute_person_delta,row.absolute_mean_gap),xytext=(-18,22),textcoords='offset points',ha='right')
        ax.set(title=f'{title}：{len(d)}对（共同有效时间人员≥4）',xlabel='逐人耗时差绝对值的均值（秒）',
            ylabel='两视角平均耗时之差的绝对值（秒）',xlim=(-3,limit),ylim=(-3,limit));ax.grid(alpha=.2)
    fig.suptitle('平均接近可能来自人员差异抵消；source与target时间分别计数，缺失不补零')
    fig.savefig(folder/'time_cancellation.png',dpi=140);plt.close(fig)


def main():
    requests=json.loads((OUT/'PAIR_PROCESS_REQUESTS.json').read_text(encoding='utf-8'))
    result=json.loads((OUT/'PROCESS_RESULTS.json').read_text(encoding='utf-8'))
    trace=pd.read_csv(OUT/'process_trace_validated.csv',low_memory=False)
    paired=pd.read_csv(OUT/'process_paired_prefixes.csv',low_memory=False)
    curves=pd.read_csv(OUT/'process_paired_curves.csv');stability=pd.read_csv(OUT/'process_same_k_summary.csv')
    reasons={p['request_id']:design_reason(p) for p in requests['pairs']}
    trace=consumer_masks(trace,reasons)
    assert len(trace)==result['planned_side_prefixes']
    assert trace.execution_status.eq('observed').sum()==result['validated_side_prefixes']
    paired_key=['request_id','replay_id','k']
    availability=trace.pivot(index=paired_key,columns='side',values='primary_quality_available').all(axis=1)
    received=paired.set_index(paired_key)
    assert received.index.is_unique and len(received)==result['paired_prefixes']
    assert availability.sort_index().equals(received.both_quality.sort_index())
    assert received.both_complete.sum()==result['both_complete'] and received.both_quality.sum()==result['both_primary_quality']
    keys=['request_id','replay_id','side','k','pool_id','path_id','subset','image','layer','reference_id','reference_version',
        'member_workers','member_object_ids','execution_status','order_status','geometry_status','complete_evaluable',
        'main_comparison_allowed','primary_design_eligible','primary_quality_eligible','primary_quality_available',
        'primary_mask_reason','pair_design_reason','comparison_B8L2','comparison_D10',
        'cumulative_source_seconds','cumulative_target_seconds','geometry_source']
    save(OUT,'consumer_prefixes.csv',trace[keys])
    summary=summarize_pairs(requests,trace,paired,curves);save(OUT,'consumer_pair_summary.csv',summary)
    original_time=pd.read_csv(OUT/'endpoint_explanation.csv')
    original_time=original_time[original_time.metric.isin(['source_time_seconds','target_matched_time_seconds'])]
    save(OUT,'consumer_original_time_pairs.csv',original_time)
    draw_figures(requests,trace,curves,stability,original_time)
    producer=json.loads((ROOT/FUSION_OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    current=json.loads((ROOT/FUSION_OUT/'CURRENT.json').read_text(encoding='utf-8'))
    assert current['analysis_revision']==producer['analysis_revision']==result['producer_analysis_revision']
    interface=dict(schema=INTERFACE,data_release='v1',analysis_revision=VERSION,producer_version=producer['version'],
        producer_analysis_revision=producer['analysis_revision'],producer_current=FUSION_OUT+'/CURRENT.json',
        status='ready_for_statistics',
        source_manifest=FUSION_OUT+'/MANIFEST.json',source_validation='PROCESS_RESULTS.json',
        files=dict(prefixes='consumer_prefixes.csv',pairs='consumer_pair_summary.csv',curves='process_paired_curves.csv',
            within_view_stability='process_same_k_summary.csv',original_times='consumer_original_time_pairs.csv',
            overview='figures/quality_gap_overview.png',time_example='figures/time_cancellation.png'),
        keys=dict(prefixes=['request_id','replay_id','side','k'],pairs=['request_id'],curves=['request_id','k']),
        coverage={k:result[k] for k in ['pairs','buildings','planned_side_prefixes','validated_side_prefixes','paired_prefixes','both_complete','both_primary_quality']},
        scene_layers=summary.groupby('scene_layers').size().to_dict(),
        mask_counts=trace.primary_mask_reason.value_counts().to_dict(),
        validation=dict(prefix_key_unique=True,paired_mask_reconciled=True,counts_reconciled=True,
            figures=11,new_tests=2,independent_prediction_validation=False),
        rules=dict(primary_quality='use comparison_B8L2/comparison_D10 only when primary_quality_available; eligible is a gate, not numeric availability',
            paired_curves='both views and both metrics use the same successful replay intersection; planned/received/complete denominators retained',
            diagnostic='whole-pair exclusion overrides favorable producer prefixes; no diagnostic-to-primary promotion',
            time='source and target cumulative times separate; any missing member means full sum missing; never sum replay costs as new labor',
            scene='all nine process pairs are ordinary; doorway original other-scope relations are not doorway process observations',
            replication='9 pairs/7 buildings, 4 dependent replays; repeated full sets are not independent endpoints',
            scores='B8L2 primary, D10 direction-scale sensitivity; no training or selection changes'),
        human_decisions_required=[],remaining_issues=[
            '72 two-person ordering-deferred and 4 manual-order-pending side prefixes retained, not an approval prerequisite',
            'no new prediction validation; target time sparse; two diagnostic pairs not promoted'])
    save(OUT,'CONSUMER_INTERFACE.json',interface)
    contract=json.loads((OUT/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    contract.update(tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')},
        consumer_interface=INTERFACE,consumer_masks='primary_design_eligible + producer main gate + observed -> eligible; available additionally requires both metric values; mask reason prioritizes whole-pair diagnosis',
        figures='NaN gaps retained; per-pair panels; time trajectories show known full-prefix sums only; no confidence intervals or cross-camera geometry')
    save(OUT,'FIELD_CONTRACT.json',contract)
    print(json.dumps(dict(schema=INTERFACE,coverage=interface['coverage'],mask_counts=interface['mask_counts'],figures=11),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
