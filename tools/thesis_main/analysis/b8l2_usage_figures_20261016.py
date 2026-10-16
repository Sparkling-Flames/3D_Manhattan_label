"""新用途快照的覆盖、质量和时间图；仅消费已明确用途的统计列。"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

from .descriptive_statistics_figures_20261015 import export

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/statistics/b8l2_usage_v6_20261016'
STATUS={'full_computed':'完整实算','floor_only_computed':'仅底面实算',
    'input_uncomputable':'输入不可算','pending_target':'待目标','pending_reference':'待参考',
    'measurement_failed':'实测失败','not_run':'未运行'}
SCENE={'doorway_only':'仅门洞','oos_only':'仅OOS','both':'门洞且OOS','neither_flagged':'两者均未标记'}


def plot_inputs(records):
    assert records.object_id.is_unique
    assert not (records.is_oos & records.quality_usable).any()
    assert records.loc[~records.quality_usable,['B8L2','WQ','A10','IoU3D100']].isna().all().all()
    assert set(records.calculation_status)<=set(STATUS)
    rows=[]
    for worker,cell in records.groupby('worker_id',sort=True):
        diag=cell.diagnostic_B8L2.notna()
        usable=cell.quality_usable
        rows.append(dict(worker_id=worker,n=len(cell),quality=int(usable.sum()),
            oos_diagnostic=int((diag & cell.is_oos).sum()),
            other_diagnostic=int((diag & ~cell.is_oos & ~usable).sum()),
            no_full_score=int((~diag).sum())))
    coverage=pd.DataFrame(rows)
    assert (coverage[['quality','oos_diagnostic','other_diagnostic','no_full_score']].sum(axis=1)==coverage.n).all()
    return coverage


def build(source=SOURCE):
    records=pd.DataFrame(json.loads((source/'tables.json').read_text(encoding='utf-8'))['shared_records'])
    coverage=plot_inputs(records)
    out=source/'figures'
    out.mkdir(exist_ok=True)
    available={font.name for font in font_manager.fontManager.ttflist}
    font=next(name for name in ['Microsoft YaHei','SimHei','Noto Sans CJK SC'] if name in available)
    plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'font.size':10,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    colors=['#3a8c94','#95c5cb','#bd7270','#d1ab57','#8296b2','#7f4a60','#bfc4c9']
    counts=records.groupby(['condition','scene_bucket','calculation_status']).size().rename('n').reset_index()
    fig,axes=plt.subplots(1,3,figsize=(17,5),sharey=True)
    for ax,condition in zip(axes,['manual','semi','oos']):
        wide=counts[counts.condition.eq(condition)].pivot(index='scene_bucket',columns='calculation_status',values='n')
        wide=wide.reindex(index=list(SCENE),columns=list(STATUS)).fillna(0)
        bottom=np.zeros(4)
        for (status,label),color in zip(STATUS.items(),colors):
            ax.bar(range(4),wide[status],bottom=bottom,label=label,color=color)
            bottom+=wide[status].to_numpy()
        for i,n in enumerate(bottom):
            ax.text(i,n+5,str(int(n)),ha='center',fontsize=9)
        ax.set(title=f'来源条件：{condition}',xticks=range(4),xticklabels=list(SCENE.values()),ylabel='原始作答数')
        ax.tick_params(axis='x',labelrotation=18)
    axes[-1].legend(frameon=False,fontsize=9)
    fig.suptitle(f'全部{len(records)}份作答的实际计算状态（互斥类别）')
    export(fig,out,'01_场景与计算覆盖',counts,'场景依据图片标记，来源condition另列；均未标记不等于已确认普通。仅底面不代表完整质量可用。')

    fig,ax=plt.subplots(figsize=(15,7))
    bottom=np.zeros(len(coverage))
    for col,label,color in [('quality','质量用途可用','#3a8c94'),('oos_diagnostic','OOS完整诊断','#d1ab57'),
        ('other_diagnostic','其它完整诊断','#8296b2'),('no_full_score','无完整实算分','#d0d4d8')]:
        ax.bar(coverage.worker_id,coverage[col],bottom=bottom,label=label,color=color)
        bottom+=coverage[col].to_numpy()
    for i,row in coverage.iterrows():
        ax.text(i,row.n+3,f'{row.quality}/{row.n}',ha='center',rotation=90,fontsize=8)
    ax.set(title=f'{len(coverage)}人全部提交与质量用途覆盖',ylabel='作答数',ylim=(0,max(bottom)*1.22))
    ax.tick_params(axis='x',labelrotation=65)
    ax.legend(frameon=False,ncol=4)
    export(fig,out,'02_全部人员用途覆盖',coverage,'人员按ID排列；标签为质量可用/全部提交。质量覆盖受任务、参考、清洗和场景影响，不是人员能力排名。')

    images=records.groupby(['image_id','image_code','condition'],sort=True).agg(
        n_inventory=('object_id','size'),n_source=('pool_analysis_eligible','sum'),
        n_quality=('quality_usable','sum')).reset_index()
    bubbles=images.groupby(['condition','n_source','n_quality']).size().rename('n_images').reset_index()
    fig,axes=plt.subplots(1,3,figsize=(17,5),sharex=True,sharey=True)
    for ax,condition in zip(axes,['manual','semi','oos']):
        cell=bubbles[bubbles.condition.eq(condition)]
        ax.scatter(cell.n_source,cell.n_quality,s=35+cell.n_images*18,color='#3a8c94',alpha=.5)
        for row in cell.itertuples():
            ax.annotate(str(row.n_images),(row.n_source,row.n_quality),ha='center',va='center',fontsize=8)
        ax.plot([0,images.n_source.max()],[0,images.n_source.max()],color='#b5bac0',linestyle='--',linewidth=1)
        ax.set(title=f'{condition}：逐图覆盖',xlabel='本图合格来源作答数',ylabel='质量用途可用作答数')
    export(fig,out,'05_逐图来源与质量覆盖',images,
        '每个气泡是一种覆盖组合，数字为该条件图片数；同图不同条件另计。来源合格不保证完整参考或质量可用。OOS诊断不进入纵轴。')

    quality=records[records.quality_usable].copy()
    quality['plot_group']=np.where(quality.is_doorway,'可用门洞',np.where(quality.ordinary_difficulty_eligible,
        quality.difficulty_class,'其他单列'))
    groups=['简单','中等','困难','可用门洞','其他单列']
    fig,axes=plt.subplots(1,3,figsize=(17,5),sharey=True)
    for ax,condition in zip(axes,['manual','semi','oos']):
        panel=quality[quality.condition.eq(condition)]
        for i,group in enumerate(groups):
            values=panel.loc[panel.plot_group.eq(group),'B8L2'].dropna()
            if len(values):
                ax.boxplot([values],positions=[i],widths=.6,showfliers=False,
                    medianprops={'color':'#aa5778'},boxprops={'color':'#3a8c94'})
            ax.text(i,3,f'n={len(values)}',ha='center',fontsize=9)
        ax.set(title=f'{condition}：质量用途可用',xticks=range(5),xticklabels=groups,ylim=(0,103),ylabel='B8L2（0–100）')
        if panel.empty: ax.text(.5,.5,'当前无质量用途可用作答',transform=ax.transAxes,ha='center',color='#737b83')
        ax.tick_params(axis='x',labelrotation=20)
    export(fig,out,'03_质量用途分布',quality[['object_id','worker_id','image_id','condition','plot_group','B8L2']],
        'OOS不进入质量分布。箱体为四分位区间、中线为中位数，隐藏离群点；各组任务组成不同，不能作独立难度或能力验证。')

    joint=quality[quality.active_time_seconds.notna()].copy()
    joint['target_time_verified']=joint.target_matched_time_seconds.notna()
    fig,axes=plt.subplots(1,3,figsize=(17,5),sharey=True)
    for ax,condition in zip(axes,['manual','semi','oos']):
        cell=joint[joint.condition.eq(condition)]
        for verified,label,color in [(False,'仅来源时间','#9caab8'),(True,'另有已核同目标时间','#3a8c94')]:
            sub=cell[cell.target_time_verified.eq(verified)]
            ax.scatter(sub.active_time_seconds,sub.B8L2,s=13,alpha=.45,color=color,label=f'{label} n={len(sub)}')
        ax.set_xscale('log')
        if cell.empty:
            ax.set_xlim(1,10000)
            ax.text(.5,.5,'当前无质量/时间共有作答',transform=ax.transAxes,ha='center',color='#737b83')
        ax.set(title=f'{condition}：质量/来源时间交集 n={len(cell)}',xlabel='有效来源 active time（秒，对数轴）',ylabel='B8L2（0–100）',ylim=(0,103))
        ax.legend(frameon=False,fontsize=8)
    export(fig,out,'04_质量与有效时间',joint[['object_id','worker_id','image_id','condition','B8L2',
        'active_time_seconds','target_matched_time_seconds','target_time_verified']],
        '只画实际质量/来源时间交集，不填缺失、不用lead_time；来源时间不自动代表新目标时间。散点仅描述关联，不作因果解释。')
    manifest=dict(version='b8l2_usage_figures_20261016_v1',source=str(source.relative_to(ROOT)),
        usage_version=records.usage_version.iloc[0],input_version=records.input_version.iloc[0],
        n_records=len(records),n_quality=len(quality),n_workers=len(coverage),n_quality_source_time=len(joint),
        n_figures=5,
        scientific_outputs='PNG + editable SVG + underlying CSV',oos_in_quality_distribution=False,
        worker_sort='identity, not ability',score_model_unchanged=True)
    (out/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'FIGURES.md').write_text('# 新用途关键数据图\n\n全部图消费父级用途快照；每图同时保留PNG、SVG与逐项数据CSV。\n\n'
        '1. 场景与计算覆盖：按来源条件和互斥场景查看完整/底面/待定/不可算。\n'
        '2. 全部人员用途覆盖：保留所有人员，包括全量未进入分析者。\n'
        '3. 质量用途分布：OOS诊断不进入任何质量分组。\n'
        '4. 质量与有效时间：只用实际共有集合，来源时间与已核同目标时间分开。\n'
        '5. 逐图来源与质量覆盖：图片层面揭示来源资格与实际质量覆盖的差距。\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=SOURCE)
    build(parser.parse_args().source_dir)
