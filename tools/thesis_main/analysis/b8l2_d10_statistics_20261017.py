"""当前共同评分的双指标描述统计；复用既有细致查阅与人工关系组统计。"""
import argparse
import json
from pathlib import Path

import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from .b8l2_detailed_views_20261016 import build_detail_tables
from .b8l2_detail_summary_20261016 import distribution

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json'
OUT=ROOT/'research/statistics/b8l2_d10_statistics_20261017'
VERSION='b8l2_d10_statistics_20261017_v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_scores(records,expected_ids):
    assert records.object_id.is_unique and set(records.object_id)==set(expected_ids),'inventory mismatch'
    assert records.B8L2.notna().equals(records.D10.notna()),'same score mask required'
    assert records.B8L2.notna().equals(records.quality_usable),'quality mask mismatch'
    assert not (records.is_oos & records.quality_usable).any(),'OOS is diagnostic only'
    assert not (records.quality_usable & ~records.pool_analysis_eligible).any(),'source excluded quality'


def dual_detail_tables(records,bundle,adoption,*,builder=build_detail_tables):
    """两个指标共用行和掩码；非指标列必须完全相同才能并列。"""
    tables=builder(records,bundle,adoption=adoption)
    sensitivity=records.copy()
    sensitivity['B8L2']=records.D10
    sensitivity['B8L2_version']=records.D10_version
    sensitivity['diagnostic_B8L2']=records.diagnostic_D10
    other=builder(sensitivity,bundle,adoption=adoption)
    for name,frame in tables.items():
        if name=='record_lookup':continue
        alt=other[name]
        metric=[c for c in frame if 'B8L2' in c]
        common=[c for c in frame if c not in metric]
        pd.testing.assert_frame_equal(frame[common],alt[common])
        for column in metric:frame[column.replace('B8L2','D10')]=alt[column]
    tables['record_lookup']=records.copy()
    return tables


def coverage_summaries(records):
    rows=[];diagnostics=[]
    for keys,cell in records.groupby(['condition','analysis_layer','quality_use'],dropna=False,sort=True):
        source=cell.pool_analysis_eligible
        row=dict(zip(['condition','analysis_layer','quality_use'],keys),n_inventory=len(cell),
            n_source=int(source.sum()),n_source_excluded=int((~source).sum()),
            n_quality=int(cell.quality_usable.sum()),n_quality_missing_in_source=int((source & ~cell.quality_usable).sum()),
            n_inventory_time=int(cell.source_active_time_seconds.notna().sum()),
            n_inventory_time_missing=int(cell.source_active_time_seconds.isna().sum()),
            n_source_time=int(cell.active_time_seconds.notna().sum()),
            n_source_time_missing=int((source & cell.active_time_seconds.isna()).sum()),
            n_target_time=int(cell.target_matched_time_seconds.notna().sum()),
            n_source_target_time_missing=int((source & cell.target_matched_time_seconds.isna()).sum()))
        rows.append(row)
    for keys,cell in records.groupby(['condition','scene_bucket','quality_use'],dropna=False,sort=True):
        row=dict(zip(['condition','scene_bucket','quality_use'],keys),n_inventory=len(cell),diagnostic_only=True)
        for metric in ['B8L2','D10']:
            row.update({metric+'_'+k:v for k,v in distribution(cell['diagnostic_'+metric]).items()})
        diagnostics.append(row)
    reasons=[]
    for kind,column in [('source','pool_analysis_exclusion_reasons'),('quality','quality_exclusion_reasons')]:
        for _,record in records.iterrows():
            for reason in record[column]:
                reasons.append(dict(object_id=record.object_id,worker_id=record.worker_id,image_id=record.image_id,
                    condition=record.condition,reason_kind=kind,reason=reason))
    return dict(exclusion_time_summary=pd.DataFrame(rows),diagnostic_quality_stats=pd.DataFrame(diagnostics),
        exclusion_reason_hits=pd.DataFrame(reasons),
        cleaning_summary=records.groupby(['condition','cleaning_disposition'],dropna=False).agg(
            n_inventory=('object_id','size'),n_workers=('worker_id','nunique'),n_images=('image_id','nunique')).reset_index(),
        calculation_summary=records.groupby(['condition','calculation_status','quality_use'],dropna=False).size().reset_index(name='n'),
        time_missing_records=records.loc[records.source_active_time_seconds.isna() |
            (records.pool_analysis_eligible & records.target_matched_time_seconds.isna()),[
            'object_id','worker_id','image_id','condition','new_batch','pool_analysis_eligible','quality_usable',
            'source_active_time_seconds','active_time_seconds','target_matched_time_seconds',
            'time_status','time_rule_version','time_binding','target_time_interpretation']])


def build_figures(records,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from .descriptive_statistics_figures_20261015 import export
    from .b8l2_usage_figures_20261016 import STATUS
    fonts={f.name for f in font_manager.fontManager.ttflist}
    font=next(f for f in ['Microsoft YaHei','SimHei','Noto Sans CJK SC'] if f in fonts)
    plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    out=out/'figures';out.mkdir(exist_ok=True)
    rows=[]
    fig,axes=plt.subplots(1,2,figsize=(12,5),sharey=True)
    for ax,condition in zip(axes,['manual','semi']):
        for x,level in enumerate(['简单','中等','困难']):
            source=records[records.condition.eq(condition)&records.ordinary_difficulty_eligible&
                records.pool_analysis_eligible&records.difficulty_class.eq(level)]
            cell=source[source.quality_use.eq('ordinary_primary')]
            ax.text(x,3,f'n={len(cell)}/{len(source)}',ha='center',fontsize=9)
            for metric,offset,color in [('B8L2',-.10,'#247b91'),('D10',.10,'#bd6547')]:
                stats=distribution(cell[metric]);rows.append(dict(condition=condition,difficulty=level,
                    metric=metric,n_source=len(source),**stats))
                if stats['n']:
                    ax.vlines(x+offset,stats['q25'],stats['q75'],color=color,lw=4,alpha=.5)
                    ax.scatter(x+offset,stats['mean'],color=color,marker='D',s=34,
                        label=metric if x==0 else None)
                    ax.scatter(x+offset,stats['median'],color=color,marker='_',s=85)
        ax.set(title=condition,xticks=range(3),xticklabels=['简单','中等','困难'],ylim=(0,100),ylabel='质量分数')
        ax.legend(frameon=False,loc='lower center',bbox_to_anchor=(.5,.11),ncol=2)
    fig.suptitle('普通用途：B8L2 主指标与 D10 敏感性（同分母）')
    export(fig,out,'01_普通难度双指标',pd.DataFrame(rows),
        '菱形=作答等权均值，短横=中位数，竖线=25%–75%分位；n=质量可用/该难度合格来源。任务组成不同，不解释为难度因果效应。')
    usable=records.quality_usable;diag=records.diagnostic_B8L2.notna()
    uses={'普通质量':records.quality_use.eq('ordinary_primary'),
        '门洞质量':records.quality_use.eq('doorway_quality'),'其它条件质量':records.quality_use.eq('special_conditional_only'),
        'OOS完整诊断':records.is_oos&diag,'其它完整诊断':~usable&~records.is_oos&diag,'无完整实算分':~diag}
    assert pd.DataFrame(uses).sum(axis=1).eq(1).all(),'coverage categories must partition inventory'
    assert set(records.calculation_status)<=set(STATUS),'unlabelled calculation status'
    states=records.calculation_status.value_counts()
    fig,axes=plt.subplots(1,2,figsize=(14,6))
    a=pd.DataFrame([dict(category=k,n=int(v.sum()),denominator=len(records)) for k,v in uses.items()])
    b=pd.DataFrame([dict(category=STATUS[k],n=int(states.get(k,0)),denominator=len(records)) for k in STATUS
        if states.get(k,0)])
    for ax,data,title in zip(axes,[a,b],['质量用途与诊断（互斥）','几何计算覆盖（互斥）']):
        ax.barh(data.category,data.n,color='#4b8f99')
        for i,row in data.iterrows():ax.text(row.n+12,i,f'{row.n}/{len(records)}',va='center',fontsize=9)
        ax.invert_yaxis();ax.set(title=title,xlabel='作答数',xlim=(0,float(data.n.max())*1.24))
    fig.suptitle(f'全部 {len(records)} 份库存：质量、诊断与缺失计算覆盖')
    export(fig,out,'02_质量与计算覆盖',pd.concat([a.assign(axis='用途'),b.assign(axis='计算')]),
        '两面板各自完整覆盖库存，不能跨面板相加；完整实算含诊断，不能当质量可用；OOS不进入质量均值。待目标/仅底面不补造顶界。')
    (out/'FIGURES.md').write_text('# 双指标关键图\n\n'
        '![普通难度双指标](01_普通难度双指标.png)\n\n'
        '![质量与计算覆盖](02_质量与计算覆盖.png)\n\n'
        '每图附SVG和原始绘图CSV；n、分母和分位均来自当前共同输入。正式研究图保留，没有临时检查截图。\n',encoding='utf-8')
    return ['figures/01_普通难度双指标.png','figures/02_质量与计算覆盖.png']


def run(source=SOURCE,out=OUT):
    source=source.resolve();out=out.resolve()
    cross=read(source)
    bundle=load_current_bundle(ROOT/cross['input_manifest'])
    records=pd.read_csv(ROOT/cross['full_inventory_with_metric_eligibility'],encoding='utf-8-sig')
    for column in ['pool_analysis_exclusion_reasons','quality_exclusion_reasons']:
        records[column]=records[column].map(json.loads)
    for column in ['pool_analysis_eligible','quality_usable','is_oos','ordinary_difficulty_eligible',
        'current_quality_eligible','difficulty_analysis_eligible','new_batch']:
        assert records[column].isin([True,False]).all(),column
        records[column]=records[column].astype(bool)
    expected={o['object_id'] for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    validate_scores(records,expected)
    assert records.analysis_layer.notna().all(),'missing analysis layer'
    assert set(records.input_version)=={bundle['manifest']['effective_input_revision']},'input version drift'
    for metric in ['B8L2','D10']:
        assert set(records[metric+'_version'])=={cross['parameters'][metric]['version']},'metric version drift'
    assert len(records)==cross['counts']['inventory']
    assert int(records.quality_usable.sum())==cross['counts']['quality_rows']
    # 任务人员时间仍可登记；分析均值只使用来源资格通过的时间。
    records.loc[~records.pool_analysis_eligible,['active_time_seconds','target_matched_time_seconds']]=None
    assert records.loc[records.new_batch,'target_matched_time_seconds'].isna().all(),'new time is task-worker only'
    manifest=read(ROOT/cross['current_relation_adoption_manifest'])
    assert manifest['status'] in ['ready_for_same_room_and_statistics_consumers','frozen_for_same_room_and_statistics_consumers']
    adoption=dict(version=manifest['version'],**{k:read(ROOT/manifest[p]) for k,p in
        [('groups','original_groups'),('candidates','candidate_adoption'),('relations','relations')]})
    tables=dual_detail_tables(records,bundle,adoption)
    tables.update(coverage_summaries(records))
    out.mkdir(parents=True,exist_ok=True)
    for name,frame in tables.items():
        encoded=frame.copy()
        for col in encoded:
            encoded[col]=encoded[col].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v)
        encoded.to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
    checks=dict(version=VERSION,score_input_version=cross['version'],input_manifest=cross['input_manifest'],
        inventory=len(records),images=records.image_id.nunique(),workers=records.worker_id.nunique(),
        quality_rows=int(records.quality_usable.sum()),quality_use=records.quality_use.value_counts().to_dict(),
        source_rows=int(records.pool_analysis_eligible.sum()),
        inventory_time_rows=int(records.source_active_time_seconds.notna().sum()),
        source_time_rows=int(records.active_time_seconds.notna().sum()),
        target_time_rows=int(records.target_matched_time_seconds.notna().sum()),
        new_batch=int(records.new_batch.sum()),new_task_worker_seconds=float(records.loc[records.new_batch,'source_active_time_seconds'].sum()),
        new_target_time_rows=0,relation_version=adoption['version'],same_metric_denominator=True,
        old_snapshots_modified=False,tables={name:len(frame) for name,frame in tables.items()})
    checks['figures']=build_figures(records,out)
    contract=dict(version=VERSION,primary_metric='B8L2',sensitivity_metric='D10',D10_is_A10=False,
        metric_parameters=cross['parameters'],source=str(source.relative_to(ROOT)),
        inventory='all current manifest annotations, including excluded; unique object_id',
        quality='B8L2 and D10 share exact same eligibility and nonmissing mask; OOS diagnostic only',
        missing='no zero imputation; n=0 estimates null; sample SD ddof=1; quantiles linear',
        weighting='answer equal and image equal means separate; condition summaries never pooled',
        time='seconds; source task-worker total and audited target matched time separate; new target time null',
        intersections='quality_source_time/quality_target_time columns use actual nonmissing intersections for each metric',
        relations='existing full user classifications; original groups, retained groups, direct pairs separate; overlaps not additive',
        reason_hits='multiple reasons per answer, not additive exclusion counts',
        diagnostic_quality_stats='unmasked computed diagnostics only; never qualified quality estimates',
        fields={name:list(frame.columns) for name,frame in tables.items()})
    for name,value in [('CHECKS.json',checks),('FIELD_CONTRACT.json',contract),
        ('INPUTS.json',dict(cross_module_inputs=cross,relations=manifest))]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (out/'README.md').write_text(f'''# 当前共同输入的 B8L2 / D10 统计

本包从[共同评分入口](../../quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json)重新生成，版本 `{cross['version']}`；当前 {len(records)} 份库存、{records.image_id.nunique()} 图、{records.worker_id.nunique()} 名源身份，质量可用 {int(records.quality_usable.sum())} 份。两指标相同作答、参考和资格，B8L2 为工作主指标，D10 是仅方向尺度 8°→10° 的敏感性，**不是 A10**。数量和字段以 [CHECKS.json](CHECKS.json)、[FIELD_CONTRACT.json](FIELD_CONTRACT.json) 为准。

逐人/逐图总库存见 `worker_inventory.csv`、`image_inventory.csv`，分条件分布见 `worker_condition_stats.csv`、`image_condition_stats.csv`。人员×难度见 `worker_difficulty.csv`，人员×门洞/OOS/场景见 `worker_special_axes.csv`；`difficulty_overview.csv` 与 `time_quality_focus.csv` 保留难度分层和质量时间共有集合。

每张表的 B8L2、D10 均值、中位数、样本标准差、四分位和有效 n 并列；作答等权与视角等权均值分别列示。普通、门洞和其它用途单列，manual/semi/oos 不混成均值。OOS 已计算的数值仅在 `diagnostic_quality_stats.csv` 诊断表和逐条诊断字段显示，不恢复质量资格。无数据为 n=0、估计空值。

按用户已有完整分类：`user_original_group_summary.csv` / `user_original_worker_groups.csv` 为人工原组与人员×原组，`room_group_summary.csv` / `room_worker_groups.csv` 为采用工作分组，`room_group_views.csv` 为逐视角贡献，`room_direct_pair_summary.csv` / `room_worker_direct_pairs.csv` 为直接关系对。登记表保留原始分类、成员与分组证据；采用版本 `{adoption['version']}`，不新增逐组确认门，不跨组做传递推断。组可重叠，原组/子组/图对不能相加；未记录同房不等于确认异房。

全部作答含排除和未评分见 `record_lookup.csv`。清洗移出与来源分析不合格分开看 `cleaning_summary.csv`、`exclusion_time_summary.csv`；清洗 retained 尚含重复独立票限制，不能当独立保留人数。逐条多重理由 `exclusion_reason_hits.csv` 不可相加为人数。计算状态见 `calculation_summary.csv`。时间缺失定位 `time_missing_records.csv`，来源时间与同目标时间分别保留，不用 lead_time 或零补缺失。新增70份合计 {checks['new_task_worker_seconds']:g} 秒只是任务人员总耗时，新增同目标耗时全部空；既有核实的同目标时间保留，两种时间均只用各自真实非空交集。

运行 `python -m tools.thesis_main.analysis.b8l2_d10_statistics_20261017`。复用既有细致统计和关系描述 helper；在新目录生成，旧冻结评分/统计包未覆盖。4项新边界测试和10项既有细致/关系统计测试通过，覆盖指标同掩码、库存漂移、OOS隔离、分母漂移与新增目标时间空值。地图与目录由统筹线程统一登记。

[两张关键图](figures/FIGURES.md)包含普通难度双指标分布和全部库存的质量/计算覆盖，附n、分母、绘图CSV与SVG；不画人员能力排名。

本包描述当前观察，不训练人员模型、不根据均值修改难度，也不固定论文大纲。未跑全仓测试；任务组成、参考/资格差异和时间口径仍限制跨组因果解释。
''',encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    return tables,checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();run(args.source,args.out)
