"""当前难度、合格来源池与参考门下的科研图；空间重评分快照另画分层覆盖。"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

from .descriptive_statistics_figures_20261015 import export, DIFFICULTIES, COLORS, METRICS

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT/'research/statistics/descriptive_statistics_current_20261015'


def ordinary_manual(records):
    panel = records[records.condition.eq('manual') & records.analysis_layer.eq('ordinary_current')].copy()
    assert panel.pool_source_workers.ge(3).all()
    assert not panel.duplicated(['image_id','worker_id']).any()
    return panel


def scope_quality_coverage(catalog, affected, audit):
    """逐图参考与逐作答准入分轴；绝不把多空间展开表当成人数。"""
    assert affected.object_id.is_unique
    current=catalog[catalog.current_target & catalog.image_id.isin(affected.image_id)].copy()
    assert current.image_id.is_unique
    assert set(current.image_id)==set(affected.image_id)
    matched=affected.set_index('object_id')
    chosen=matched.chosen_target_id.notna() & matched.chosen_target_id.ne('')
    complete=chosen & matched.chosen_target_id.map(catalog.set_index('target_id').full_reference_available).eq(True)
    on_current=matched.chosen_target_id.eq(matched.current_target_id)
    geometry=matched.score_input_eligible
    gates=matched.person_quality_restriction_clear & matched.pool_analysis_eligible
    available=audit.set_index('object_id').reindex(matched.index)
    new_quality=available.current_quality_eligible & available.rescore_status.eq('complete')
    return pd.DataFrame([
        dict(layer='参考',state='完整参考ready',n=int(current.full_reference_available.sum()),unit='当前目标图片数'),
        dict(layer='参考',state='完整参考待补',n=int((~current.full_reference_available).sum()),unit='当前目标图片数'),
        dict(layer='绑定',state='唯一目标已绑定',n=int(chosen.sum()),unit='原始作答数'),
        dict(layer='绑定',state='目标绑定待定',n=int((~chosen).sum()),unit='原始作答数'),
        dict(layer='资格',state='当前目标绑定且参考/几何ready',n=int((complete & on_current & geometry).sum()),unit='原始作答数'),
        dict(layer='资格',state='再通过人员与图片门',n=int((complete & on_current & geometry & gates).sum()),unit='原始作答数'),
        dict(layer='资格',state='已实算且纳入当前质量',n=int(new_quality.sum()),unit='原始作答数'),
    ])


def build(source, out):
    out.mkdir(parents=True, exist_ok=True)
    available = {font.name for font in font_manager.fontManager.ttflist}
    font = next(name for name in ['Microsoft YaHei','SimHei','Noto Sans CJK SC'] if name in available)
    plt.rcParams.update({'font.family':font, 'axes.unicode_minus':False,'font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    read = lambda name: pd.read_csv(source/f'{name}.csv', encoding='utf-8-sig')
    pools, images, analysis, quality = [read(name) for name in ['source_pools','current_images','analysis_records','quality_records']]
    inventory, audit, pairs = [read(name) for name in ['inventory_all','record_audit','same_room_pairs']]
    contract = json.loads((source/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    manual = ordinary_manual(analysis)
    manual_quality = ordinary_manual(quality)
    assert quality.current_quality_eligible.eq(True).all()
    assert quality[METRICS].notna().all().all()
    if 'rescore_status' in quality:
        assert quality.loc[quality.new_space_target,'rescore_status'].eq('complete').all()
    else:
        assert not quality.new_space_target.any()
    assert not analysis.gt_error_excluded.any()
    assert analysis.loc[analysis.new_space_target,'target_matched_time_seconds'].isna().all()
    assert images.image_id.is_unique
    manifest = dict(version='descriptive_statistics_current_figures_20261015_v1',
        source_contract=str(source/'FIELD_CONTRACT.json'),difficulty_version=contract['difficulty_version'],
        source_pool_rule=contract['pool_rule_version'],quality_metrics=METRICS,
        score_versions=contract['score_versions'],score_version_column='仅原WQ绑定上下文，不是A10/B8L2版本',
        units=dict(WQ='0-100',A10='0-100',B8L2='0-100',IoU3D100='0-100; mean-height prism',
            active_time_seconds='seconds; qualified-source collection time, not automatically new-target time',
            target_matched_time_seconds='seconds; unchanged or verified current target context'),
        inputs=['inventory_all.csv','record_audit.csv','source_pools.csv','current_images.csv',
                'analysis_records.csv','quality_records.csv','same_room_pairs.csv'],
        historical_metrics_plotted=False,long_score_interface_consumed=False,
        reuse_scope='当前统计schema快照可复用；分母动态读取；当前质量面板固定四指标。')
    if (source/'space_reference_catalog.csv').exists():
        manifest['inputs'] += ['space_reference_catalog.csv','affected_records.csv']
        manifest['scope_quality_coverage'] = dict(reference_unit='affected current-target images only',
            response_unit='unique original object_id; never expanded target rows',
            layers=['full reference readiness','unique pre-score target binding','current quality eligibility'])
    (out/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

    fig, axes = plt.subplots(1,2,figsize=(14,5.8))
    stages=[]
    for condition in ['manual','semi','oos']:
        p = pools[pools.condition.eq(condition)]
        stages.append(dict(condition=condition,已有作答池=int(p.n_annotation_records.gt(0).sum()),
            有效真人至少3=int(p.pool_min3_pass.sum()),通过图片门=int(p.pool_analysis_eligible.sum()),
            普通难度池=int(p.ordinary_difficulty_eligible.sum())))
    stages = pd.DataFrame(stages)
    stages.set_index('condition').plot.bar(ax=axes[0],color=['#b8bec4','#7ba6ba','#447b9d','#3a8c94'],rot=0)
    axes[0].set(title='来源池逐层覆盖（同图、同条件独立真人去重）',ylabel='图片×条件来源池数',xlabel='采集条件')
    axes[0].legend(fontsize=8,frameon=False)
    for container in axes[0].containers: axes[0].bar_label(container,fontsize=8,padding=2)
    cover=[]
    for (condition,layer),cell in analysis.groupby(['condition','analysis_layer']):
        cover.append(dict(condition=condition,analysis_layer=layer,n_records=len(cell),
            n_quality=cell.WQ.notna().sum(),n_missing_quality=cell.WQ.isna().sum()))
    cover=pd.DataFrame(cover)
    labels=[f'{r.condition}\n'+('普通' if r.analysis_layer=='ordinary_current' else '特殊/待定单列') for r in cover.itertuples()]
    axes[1].bar(range(len(cover)),cover.n_quality,label='当前完整WQ',color='#3a8c94')
    axes[1].bar(range(len(cover)),cover.n_missing_quality,bottom=cover.n_quality,label='无当前完整WQ',color='#d2d5d9')
    for i,r in enumerate(cover.itertuples()): axes[1].text(i,r.n_records+20,f'{r.n_quality}/{r.n_records}',ha='center',fontsize=9)
    axes[1].set_xticks(range(len(cover)),labels,fontsize=9)
    axes[1].set(title=f'可分析作答与当前质量覆盖（库存{len(inventory)}行）',ylabel='作答行数',ylim=(0,cover.n_records.max()*1.18))
    axes[1].legend(frameon=False,fontsize=9)
    export(fig,out,'01_当前来源池与质量覆盖',pd.concat([stages.assign(table='source_pools'),cover.assign(table='quality_coverage')],ignore_index=True),
        'GT/既有排除优先；来源池≥3不代表每个指标有≥3个有效值。各条件分别统计；当前质量缺失不回填历史分。')

    fig,axes=plt.subplots(1,4,figsize=(16,5.6),sharey=True)
    for ax,metric in zip(axes,METRICS):
        groups=[manual[manual.difficulty_class.eq(d)] for d in DIFFICULTIES]
        values=[g[metric].dropna() for g in groups]
        ax.boxplot(values,positions=range(3),widths=.5,showfliers=False,medianprops={'color':'black'})
        for i,(group,color) in enumerate(zip(groups,COLORS)):
            v=group.sort_values('object_id')[metric].dropna()
            ax.scatter(i+np.random.default_rng(15).uniform(-.18,.18,len(v)),v,s=6,alpha=.25,color=color,rasterized=True)
        ax.set_xticks(range(3),[f'{d}\n有效{g[metric].notna().sum()}/{len(g)}行\n{g.loc[g[metric].notna(),"image_id"].nunique()}/{g.image_id.nunique()}图' for d,g in zip(DIFFICULTIES,groups)],fontsize=9)
        ax.set(title=metric if metric!='IoU3D100' else '均高棱柱IoU ×100',ylim=(0,103))
        ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('分数（0—100）')
    fig.suptitle('当前v3普通manual：质量分布及缺失分母（未用历史分填补）',fontsize=14)
    export(fig,out,'02_当前难度质量分布',manual[['object_id','image_id','worker_id','difficulty_class','current_target_id','reference_id','score_version']+METRICS],
        '点为有效作答；箱体P25—P75、线为中位数。标签分别给有效/全部作答与图片数；重复人员/图片不独立。')

    fig,axes=plt.subplots(1,2,figsize=(14,6))
    timegroups=[]
    for (new,role),cell in analysis.groupby(['new_space_target','target_role']):
        timegroups.append(dict(new_space_target=new,target_role=role,n_records=len(cell),
            n_source=cell.active_time_seconds.notna().sum(),n_target=cell.target_matched_time_seconds.notna().sum()))
    timegroups=pd.DataFrame(timegroups)
    y=np.arange(len(timegroups));h=.34
    axes[0].barh(y-h/2,timegroups.n_source,height=h,label='合格来源采集时间',color='#447b9d')
    axes[0].barh(y+h/2,timegroups.n_target,height=h,label='当前稳定目标语境时间',color='#3a8c94')
    rolelabels={'selected_gt':'原选定GT','confirmed_scope':'已确认新空间范围','user_revised_gt':'用户修订参考'}
    axes[0].set_yticks(y,[f'{rolelabels.get(r.target_role,r.target_role)}\n共{r.n_records}行' for r in timegroups.itertuples()])
    for i,r in enumerate(timegroups.itertuples()):
        axes[0].text(r.n_source+12,i-h/2,str(r.n_source),va='center',fontsize=9)
        axes[0].text(r.n_target+12,i+h/2,str(r.n_target),va='center',fontsize=9)
    axes[0].set(title='来源采集时间 ≠ 新目标耗时',xlabel='有值作答行数',xlim=(0,timegroups.n_source.max()*1.25))
    axes[0].legend(frameon=False,fontsize=9,loc='upper right')
    for difficulty,color in zip(DIFFICULTIES,COLORS):
        cell=manual[manual.difficulty_class.eq(difficulty)].dropna(subset=['WQ','target_matched_time_seconds'])
        axes[1].scatter(cell.target_matched_time_seconds,cell.WQ,s=12,alpha=.4,color=color,label=f'{difficulty} n={len(cell)}',rasterized=True)
    axes[1].set_xscale('log')
    axes[1].set(title='普通manual：当前目标时间与WQ',xlabel='target_matched_time_seconds（秒，对数）',ylabel='原WQ（0—100）',ylim=(0,103))
    axes[1].legend(frameon=False,fontsize=9)
    axes[1].grid(alpha=.2)
    export(fig,out,'03_来源时间与当前目标时间',analysis[['object_id','image_id','worker_id','condition','analysis_layer','difficulty_class','new_space_target','target_role','active_time_seconds','target_matched_time_seconds','target_time_interpretation','time_status','WQ']],
        '新空间/修订目标作答匹配未确认时，当前目标时间留空；来源采集时间不能改称新目标耗时。右图只用双侧有值，不作因果解释。')
    timegroups.to_csv(out/'03_来源与目标时间覆盖汇总.csv',index=False,encoding='utf-8-sig')

    matrix=manual.pivot_table(index='worker_id',columns='image_code',values='WQ',aggfunc='mean')
    matrix=matrix.reindex(index=sorted(manual.worker_id.unique()),columns=sorted(manual.image_code.unique()))
    fig,ax=plt.subplots(figsize=(17,7.5))
    cmap=plt.colormaps['viridis'].copy();cmap.set_bad('#e4e4e4')
    artist=ax.imshow(matrix,aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='nearest')
    ax.set_yticks(range(len(matrix)),matrix.index)
    ticks=list(range(0,len(matrix.columns),6))
    ax.set_xticks(ticks,matrix.columns[ticks],rotation=65,ha='right',fontsize=7)
    ax.set(title=f'当前普通manual：{matrix.shape[0]}人 × {matrix.shape[1]}图的WQ覆盖（ID排序）',xlabel='全部普通manual来源池图片，含无当前质量者',ylabel='人员ID（非能力排名）')
    fig.colorbar(artist,ax=ax,label='当前原WQ',pad=.01,shrink=.8)
    export(fig,out,'04_当前人员图片质量覆盖',matrix.rename_axis('worker_id').reset_index(),
        '灰色含未作答/当前质量缺失，不是0分；图纳入全部合格普通manual来源池图片，禁止用historical_*填色。任务组成差异不等于人员能力差异。')

    fig,axes=plt.subplots(2,3,figsize=(14,8),sharey='row')
    for i,metric in enumerate(METRICS[1:]):
        cell=manual_quality.dropna(subset=['WQ',metric]);delta=cell[metric]-cell.WQ
        axes[0,i].scatter(cell.WQ,cell[metric],s=7,alpha=.25,color='#447b9d',rasterized=True)
        axes[0,i].plot([0,100],[0,100],color='#888888',lw=1)
        axes[0,i].set(title=f'{metric}（n={len(cell)}）',xlabel='原WQ',ylabel=metric,xlim=(0,100),ylim=(0,100))
        axes[1,i].hist(delta,bins=30,color='#3a8c94',alpha=.85)
        axes[1,i].axvline(0,color='#888888',lw=1)
        axes[1,i].set(title=f'差值中位数{delta.median():.2f}',xlabel=f'{metric} − WQ',ylabel='作答行数')
    fig.suptitle('当前普通manual：同输入、同参考、同资格的算法数值比较',fontsize=14)
    export(fig,out,'05_当前同集合算法差异',manual_quality[['object_id','image_id','worker_id','reference_id','score_version']+METRICS],
        '不将公式数值更高称为更正确；A10/B8L2版本分别见manifest，score_version仅原WQ。均高棱柱IoU与复合分数度量对象不同。')

    selected=pairs[(pairs.relation=='confirmed_comparable')&(pairs.metric=='WQ')&(pairs.n_pairs>0)].sort_values(['candidate_ids','image_code_a','image_code_b'])
    keys=selected[['image_a','image_b']]
    fig,axes=plt.subplots(1,3,figsize=(16,max(8,len(selected)*.29)),sharey=True)
    y=np.arange(len(selected))
    labels=[f'{r.candidate_ids} · {r.image_code_a.split("-")[-1]}—{r.image_code_b.split("-")[-1]} (Q n={r.n_pairs})' for r in selected.itertuples()]
    data=[]
    for ax,metric in zip(axes[:2],['WQ','B8L2']):
        cell=keys.merge(pairs[pairs.metric.eq(metric)],on=['image_a','image_b'],validate='one_to_one')
        ax.hlines(y,cell.paired_a_mean,cell.paired_b_mean,color='#aaaaaa')
        ax.scatter(cell.paired_a_mean,y,s=27,label='视角A',color='#447b9d')
        ax.scatter(cell.paired_b_mean,y,s=27,label='视角B',color='#ba6657',marker='s')
        ax.set(title=metric,xlabel='指标双侧有效共同人员均值',xlim=(0,100))
        ax.legend(frameon=False,loc='lower left',fontsize=9);data.append(cell)
    times=keys.merge(pairs[pairs.metric.eq('active_time_seconds')],on=['image_a','image_b'],validate='one_to_one')
    axes[2].barh(y,times.n_pairs,color='#3a8c94')
    for i,r in enumerate(times.itertuples()):axes[2].text(r.n_pairs+.1,i,f'{r.n_pairs}/{r.n_common_workers}',va='center',fontsize=9)
    axes[2].set(title='来源池采集时间覆盖',xlabel='时间双侧有效 / 来源共同人员',xlim=(0,max(times.n_common_workers.max(),times.n_pairs.max())+2))
    axes[0].set_yticks(y,labels,fontsize=8);axes[0].invert_yaxis()
    data.append(times)
    fig.suptitle(f'确认可比直接图对：{len(selected)}对有当前质量（含1/2人小样本，非独立房间）',fontsize=14)
    export(fig,out,'06_当前同房共同人员质量与时间',pd.concat(data,ignore_index=True),
        '来源池先按同图同条件≥3真人；图对共同人数另报，不机械删掉1/2人。每对共同人员不同，多对共享人员/视角，时间为来源采集口径。')
    if (source/'space_reference_catalog.csv').exists():
        coverage=scope_quality_coverage(read('space_reference_catalog'),read('affected_records'),audit)
        fig,axes=plt.subplots(1,3,figsize=(16,5.8))
        for ax,layer in zip(axes,['参考','绑定','资格']):
            cell=coverage[coverage.layer.eq(layer)]
            positions=np.arange(len(cell))
            ax.barh(positions,cell.n,color=['#447b9d','#aaaeb5','#3a8c94'][:len(cell)])
            ax.set_yticks(positions,cell.state,fontsize=9)
            ax.invert_yaxis()
            ax.set(title=layer+'层覆盖',xlabel=cell.unit.iloc[0],xlim=(0,max(cell.n.max()*1.18,1)))
            for i,value in enumerate(cell.n):ax.text(value+max(cell.n.max()*.02,.1),i,str(value),va='center')
        export(fig,out,'07_scope_quality_coverage',coverage,
            '仅受影响图片；参考按当前目标图片去重，绑定/资格按原始object_id去重。多空间目标展开不新增人员或作答；ready不等于已绑定或已准入。')
    notes=f'''# 当前口径关键数据图

输入难度：`{contract['difficulty_version']}`；来源池：`{contract['pool_rule_version']}`。本目录是新快照图，旧图未覆盖。
生成：`python -m tools.thesis_main.analysis.descriptive_statistics_current_figures_20261015 --source-dir {source.as_posix()} --out {out.as_posix()}`。

|图|用途及分母|
|---|---|
|01 当前来源池与质量覆盖|先审同图同条件真人池，再审图片门与普通层；可分析{len(analysis)}行，当前完整质量{len(quality)}行，特殊层质量缺失不补旧分。|
|02 当前难度质量分布|普通manual：{len(manual)}来源作答，当前质量{len(manual_quality)}行、{manual_quality.image_id.nunique()}图。每格展示有效/全部分母及真实分布。|
|03 来源时间与当前目标时间|来源采集时间有效{analysis.active_time_seconds.notna().sum()}行；当前稳定目标时间{analysis.target_matched_time_seconds.notna().sum()}行。新空间{int(images.new_space_target.sum())}图不可使用旧采集耗时冒称新目标耗时。|
|04 当前人员图片质量覆盖|所有普通manual合格来源图片均纳入；灰色为未作答或无当前质量，不把旧分换标签显示。|
|05 当前同集合算法差异|仅普通manual当前质量同输入/同参考集合；保留WQ/A10/B8L2/均高棱柱IoU的不同版本和度量对象。|
|06 当前同房共同人员质量与时间|{len(selected)}个确认可比直接图对有当前质量；图对共同人数按指标报告，1/2人结果保留并显式标样本量，不当独立房间。|

`FIGURE_MANIFEST.json`声明输入、版本与单位。原CSV的`score_version`仅原WQ绑定上下文；A10/B8L2各有版本。算法面板当前四指标，不自动消费新long-score接口。PNG/SVG为正式交付；未生成QA临时截图。无人员能力排名、算法优劣验证或时间因果结论。
'''
    if (source/'space_reference_catalog.csv').exists():
        notes+='\n新增[07 新空间三层覆盖](07_scope_quality_coverage.png)：受影响当前目标参考ready、原作答唯一绑定和人员/图片资格分别统计；目标展开不作为人数分母。\n'
    (out/'FIGURES.md').write_text(notes,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=DEFAULT)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    build(args.source_dir,args.out or args.source_dir/'figures')
