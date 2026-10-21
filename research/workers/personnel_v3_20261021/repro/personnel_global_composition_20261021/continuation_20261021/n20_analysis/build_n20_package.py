"""Build a compact frozen batch from completed condition-specific n20 analysis."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import pandas as pd
from analyze_n20 import HERE, DESIGN, STUDY, save, js


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def table(d):
    def f(v):
        if pd.isna(v):return '不可估计'
        if isinstance(v,float):return f'{v:.4f}'
        return str(v).replace('|',' / ')
    rows=['| '+' | '.join(map(str,d.columns))+' |','| '+' | '.join(['---']*len(d.columns))+' |']
    rows.extend('| '+' | '.join(f(v) for v in row)+' |' for row in d.itertuples(index=False,name=None))
    return '\n'.join(rows)


def build(condition):
    out=HERE/condition
    contract=json.loads((out/'N20_ANALYSIS_CONTRACT.json').read_text())
    assert json.loads((out/'N20_INTEGRITY_CHECK.json').read_text())['status']=='passed'
    cells=pd.read_csv(DESIGN/'CONFIG_CELLS.csv.gz');cells=cells[cells.condition.eq(condition)]
    universe=pd.read_csv(out/'N20_WEIGHT_UNIVERSE_CHECK.csv')
    coverage=universe.groupby('method_id',as_index=False).agg(pools=('pool_id','size'),cells=('cells','sum'),
        drawn_member_sets=('sampled_draws','sum'),member_set_population=('possible_member_sets','sum'),
        singleton_cells=('singleton_cells','sum'),member_exhaustive_cells=('member_exhaustive_cells','sum'))
    c=cells.groupby('method_id').agg(labelled_pool_min=('labelled_pool_n','min'),labelled_pool_max=('labelled_pool_n','max'))
    coverage=coverage.merge(c,left_on='method_id',right_index=True)
    save(coverage,out/'N20_COVERAGE.csv')
    pred=pd.read_csv(out/'N20_PREDICTION_SUMMARY.csv')
    inc=pd.read_csv(out/'N20_PREDICTION_INCREMENT.csv')
    support=pd.read_csv(out/'N20_COMMON_SUPPORT.csv')
    key=pred[pred.outcome.isin(['B8L2','D10','nodes','failure','IoU3D100','height_mean_h','log_source_time_total'])&
             pred.support_scope.isin(['own_class_supported','common_new_anchor','common_modern_anchor'])&
             pred.model.isin(['QT_source','QT_moments_source','coarse_source','fine_source','coarse_quadratic_source','fine_quadratic_source',
                             'QT_moments_plus_fine_source','QT_moments_team_quadratic_source','QT_moments_plus_fine_quadratic_source'])].copy()
    save(key,out/'N20_KEY_RESULTS.csv')
    ss=support.groupby(['support_scope','design_anchor','status'],dropna=False,as_index=False).agg(
        pools=('pool_id','size'),registered_draws=('registered_draws','sum'),supported_draws=('supported_draws','sum'))
    save(ss,out/'N20_SUPPORT_SUMMARY.csv')
    fits=pd.read_csv(out/'N20_FIT_SUPPORT_ALL.csv.gz')
    rank=fits.groupby(['support_scope','method_id','model'],as_index=False).agg(
        rank_min=('training_rank','min'),rank_max=('training_rank','max'),entered_min=('entered_predictors','min'),entered_max=('entered_predictors','max'),
        train_buildings_min=('train_buildings','min'),train_buildings_max=('train_buildings','max'))
    save(rank,out/'N20_MODEL_COMPLEXITY.csv')
    main=pred[(pred.target_panel=='all')&(pred.support_scope=='own_class_supported')&pred.outcome.isin(['B8L2','D10','failure','nodes'])&
              pred.model.isin(['coarse_source','fine_source','coarse_quadratic_source','fine_quadratic_source'])]
    common=pred[(pred.target_panel=='all')&(pred.support_scope=='common_new_anchor')&pred.outcome.isin(['B8L2','log_source_time_total'])&
                pred.model.isin(['QT_source','QT_moments_source','coarse_source','fine_source'])]
    compact=['method_id','outcome','weighting','model','buildings','images','draws','R2_relative_to_pool_mean']
    findings=(out/'FINDINGS_BODY_ZH.md').read_text()
    lead=('本批支持保留 Manual 结构粗类作为解释入口；M 细类没有稳定的额外质量优势，新批多域细分对效率有实际增量，而连续 QT/个人二阶矩仍是更好的时间预测表达。' if condition=='manual' else '本批保留 Semi 尺度类别解释原答差异，但尚不把其细分升级为一般大团队配方；连续 QT 对时间的外楼预测显著强于现有类别人数向量。')
    report=f'''# {condition.capitalize()}：n=20 完整类别配置与外建筑响应检查

**{lead}**

本批已完成并独立保存：**{contract['unique_native_teams']:,} 个确定性融合终点、{contract['vector_cells']:,} 个完整类别人数向量、{contract['registered_member_references']:,} 条配置—具体团队登记**。所有已有终点直接复用；本分析代码不重新融合、不改评分、人员资格、参考或标签。

本报告的类别数 K、团队人数 n=20、每个配置至多 3 个具体成员集合是三件不同的事。M 采用既有 2 粗/4 细、SP 采用既有 2 粗/3 细、A2 是独立 3 类方法，MV 为既有 2 粗及折内 3–4 细。这些是本批冻结候选，**不是最终类别数上限**。ABC 在其他分析中指三个对照团队，不是限定三种人员类别。

## 一、实际完成的范围

{table(coverage)}

`member_set_population` 是同一方法各图片/参考池的全部可行成员集合数量之和；不同方法域有重叠，不能再跨方法相加为不重复实验总数。所有完整类别配置均已抽到队，只有 `member_exhaustive_cells` 所列配置做了全部成员集合。全体成员子集尚未穷尽，也没有展开加入顺序；确定性融合终点按实际集合去重。

输入及精确端点/成员身份来自 `../next_stage/candidate_n20/CONFIG_MEMBERSHIP.csv.gz`、`CONFIG_CELLS.csv.gz`、`ENDPOINT_REQUESTS.json.gz` 与 `../next_stage/batches/*/ENDPOINT_SCALARS.csv.gz`。人员标签仍为研究原包 `composition/FROZEN_LABELS.csv`，连续历史特征仍为 `multivariate/continuous_features_lobo.csv.gz`。阶段输入 SHA 保存于 `N20_ANALYSIS_CONTRACT.json`，权重恒等式逐池记录于 `N20_WEIGHT_UNIVERSE_CHECK.csv`。

## 二、先评价类别总作用，再检查 QT 增量

本批并列三个分析层次，不能混用分母。

1. `own_class_supported`：只要求该方法的外楼类别和来源标签，不要求 QT 完整；评价该分类在其较宽人员域里的总作用。粗类、细类及固定二次比例/交互模型都在这里实际拟合。
2. `own_design`：在本方法采样设计中限制到类别及四个 QT 字段都有效的成员集合，比较粗/细与连续 QT。
3. `common_modern_anchor` 与 `common_new_anchor`：分别以原结构/SP 网格和新批 MV 网格作抽样锚，要求三种方法与 QT 使用**完全相同的具体终点**。第二个锚是第一个锚支持不足后按人员支持增加的分析，不是按结果择优的锚。

{table(ss)}

`joint_capacity_lt20` 是实际共同标签/QT 人员少于 20；`sampled_support_insufficient` 是有至少两种理论可行成员集合，但原每格至多 3 队的样本没有获得两队共同支持。`missing_outer_map` 是没有合法的目标楼外映射；都保留分母，不记成效果为零。

## 三、怎样加权和验证

- **配置等权**：每张图/参考池的原采样锚登记格权重相同，即原细类完整人数向量（A2 为其单层向量），格内实际队等权。评价粗类模型时仍使用这些原细格权重，**没有把聚合后的不同粗向量重新等权**；共同新批锚采用 MV 原细格权重。
- **成员宇宙估计**：每队权重为该格精确成员数 `∏C(u_c,k_c)` 除以该格登记抽样数。每格最多 3 队，因此这是抽样估计，不是全部成员结果。质量缺失时使用相同设计权重估计有质量结果的条件均值；失败率保留所有终点。
- 两者均再按参考池→图片→建筑等权，避免大建筑或大量配置压过其他图片。每种方法/池的格容量总和已验证等于 `C(labelled_pool_n,20)`。
- 描述表给出格均值间方差与格内成员方差；**单集合格不参加类内成员波动估计**。只有全部抽样结局可用时，才用有限总体均值方差扣除每格至多 3 队造成的抽样噪声；扣后可为负，保留原值。单集合格的均值抽样噪声可为零，这不构成可互换性证据。`within_variance_available_weight` 和相应图片/建筑数说明可估计支持。
- 模型每次留出一个建筑。目标楼外形成的同一套标签和 QT 映射同时用于该折训练池与目标池；标准化、系数都只用其他建筑。所有模型固定 ridge=0.01，无超参数搜索。
- 预测的是**同图同 n 下相对池均值的结果变化**。池均值由该图实际共同样本按相同权重估计，不是新图绝对 Q 预测；R²=1−外楼误差/池内零变化基线误差。R²<0 表示该模型还不如不预测成员差异；结局完全不变时 R² 记未知，不记满分稳定。
- 二次项属于明确记录的探索补充；连续对照同时保留 QT 均值、个人二阶矩与均值二次交互。实际维数和训练秩见 `N20_MODEL_COMPLEXITY.csv`，不宣称所有模型参数数完全相同。
- `N20_COMMON_BASELINE_CHECK.csv.gz` 逐共同终点组验证三种方法的连续基线、误差和权重完全相同。原面板与新增图片使用同一折拟合，再分别汇总。既有候选及已反复看过的 v2 数据仍是探索延伸，不能重新命名为全新盲测。

## 四、类别总作用：较宽原方法人员域

{table(main[compact])}

## 五、共同端点：粗细类别与连续 QT

{table(common[compact])}

{findings}

## 七、指标和边界

本批实际拟合 B8L2、D10、完整可评价失败、角点数、底面 IoU、IoU3D100、底面角度误差 S、方向 dir、Hmean/Hcenter、omission/extension、平均高度、9°参考节点/边召回，以及同时间源且完整记录的源任务总秒数对数。保留原冻结单位与评分定义；结构召回只解释相对冻结参考的表达，不自动裁定新增可见结构为错误。时间不是并行墙钟，也不将不同来源的计时直接相加作同尺度效率。

这是配置响应分析，**不是控制共同背景和实际换人数 m 的 ABC 可互换性检验**；一般格间方差不替代后者。新的配对 ABC 与局部几何机制由单独事件分析交付。这里也不另起同房研究。

质量缺失不当作零分；所有失败队仍进入失败分母。所有方法/指标尝试保存在汇总和逐池表，不只保留正结果。单一池全失败或全成功导致失败响应不变时，外楼失败 R² 不可估计。

## 八、复现与恢复

在仓库环境执行：

```bash
python research/workers/personnel_global_composition_20261021/continuation_20261021/n20_analysis/analyze_n20.py --condition {condition} --phase all
python research/workers/personnel_global_composition_20261021/continuation_20261021/n20_analysis/verify_n20.py --condition {condition}
python research/workers/personnel_global_composition_20261021/continuation_20261021/n20_analysis/build_n20_package.py --condition {condition}
```

所有 CSV 先写临时文件、完整读回检查行列，再原子替换。每个方法族计算结束即单独落表，描述部分先保存；无需等待 Manual/Semi 全部完成。`N20_ANALYSIS_COMPLETION.json` 是计算收据，`N20_INTEGRITY_CHECK.json` 是数值核对收据；本包清单带逐文件 SHA256。

如目录中有 `N20_TARGET_COMPOSITION_SUPPORT.csv`，它进一步区分实际跨粗配置、同粗配置内细分与同细配置内成员变化机会；完整未形成折的失败资格分母仍见 `N20_COMMON_SUPPORT.csv`。`N20_HIERARCHY_QT_INCREMENT.csv` 是已有拟合上的两个直接比较：粗类+QT 对 QT，以及细类+QT 对粗类+QT；不新增模型或择优删指标。

关键独立文件是本报告、`N20_KEY_RESULTS.csv`、`N20_COVERAGE.csv`、`N20_SUPPORT_SUMMARY.csv`、`N20_PREDICTION_INCREMENT.csv` 与完整逐池结果。ZIP 不再打包原图、已有输入、 native 融合缓存和分方法重复表。全部格—指标长表 `N20_CONFIGURATION_CELL_OUTCOMES.csv.gz` 在工作目录单独保留，可由精确输入和脚本恢复；为避免重复派生缓存，本小包不重复包含该长表。
'''
    (out/'N20_FINDINGS_ZH.md').write_text(report,encoding='utf-8')
    names=['N20_FINDINGS_ZH.md','N20_KEY_RESULTS.csv','N20_COVERAGE.csv','N20_SUPPORT_SUMMARY.csv','N20_MODEL_COMPLEXITY.csv',
        'N20_CONFIGURATION_SUMMARY.csv','N20_CONFIGURATION_POOL_RESULTS.csv.gz','N20_COMMON_SUPPORT.csv','N20_FOLD_MAPS.csv.gz',
        'N20_PREDICTION_POOL_RESULTS.csv.gz','N20_PREDICTION_BUILDINGS.csv.gz','N20_PREDICTION_SUMMARY.csv','N20_PREDICTION_INCREMENT.csv',
        'N20_COMMON_BASELINE_CHECK.csv.gz','N20_FIT_SUPPORT_ALL.csv.gz','N20_OUTCOME_SUPPORT_ALL.csv.gz',
        'N20_WEIGHT_UNIVERSE_CHECK.csv','N20_INTEGRITY_CHECK.json','N20_ANALYSIS_CONTRACT.json','N20_ANALYSIS_COMPLETION.json','FINDINGS_BODY_ZH.md']
    paths=[out/n for n in names]+[HERE/'analyze_n20.py',HERE/'verify_n20.py',Path(__file__).resolve()]
    extra=['N20_TARGET_COMPOSITION_SUPPORT.csv','N20_TARGET_COMPOSITION_SUPPORT_SUMMARY.csv','N20_TARGET_COMPOSITION_SUPPORT_RECEIPT.json',
           'N20_HIERARCHY_QT_INCREMENT.csv','N20_HIERARCHY_QT_INCREMENT_RECEIPT.json']
    paths += [out/n for n in extra if (out/n).exists()]
    paths += [HERE/n for n in ['composition_support_n20.py','hierarchy_qt_increment_n20.py','N20_WEIGHTING_CLARIFICATION_ZH.md'] if (HERE/n).exists()]
    rows=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in paths]
    save(pd.DataFrame(rows),out/'N20_PACKAGE_MANIFEST.csv')
    paths.append(out/'N20_PACKAGE_MANIFEST.csv')
    archive=HERE/f'N20_{condition.upper()}_ANALYSIS_BATCH_20261021.zip'
    temporary=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in paths:z.write(p,str(p.relative_to(HERE)))
    with zipfile.ZipFile(temporary) as z:assert z.testzip() is None
    temporary.replace(archive)
    print(archive,archive.stat().st_size,'bytes',len(paths),'files',sha(archive))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--condition',choices=['manual','semi'],required=True)
    build(ap.parse_args().condition)
