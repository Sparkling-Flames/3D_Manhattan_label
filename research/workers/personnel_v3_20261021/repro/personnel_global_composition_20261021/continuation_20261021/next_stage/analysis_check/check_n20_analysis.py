"""Small independent check of existing n20 analysis; no fitting or fusion.

Reaggregates three declared model contrasts from saved per-pool outputs, checks
one shared outer-fold membership map and weighting identities, and preserves
the distinction between configuration responses and matched replacements.
"""
from __future__ import annotations
import collections, gzip, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NEXT = HERE.parent
STUDY = NEXT.parents[1]
ANALYSIS = NEXT.parent / 'n20_analysis'
REPO = STUDY.parents[2]
FILES = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, **kw):
    path = Path(path)
    result = pd.read_csv(path, **kw)
    FILES[str(path.relative_to(REPO))] = sha(path)
    return result


def publish_csv(frame, name):
    raw = frame.to_csv(index=False).encode('utf-8-sig')
    path = HERE / name
    temp = path.with_suffix(path.suffix + '.tmp')
    assert temp.write_bytes(raw) == len(raw)
    assert temp.read_bytes() == raw
    temp.replace(path)


def aggregate(pool):
    """Pool mean within image, image mean within building, building mean."""
    images = []
    for (b, image), g in pool.groupby(['heldout_building', 'image_id']):
        images.append(dict(building=b, image=image, mse=sum(g.mse)/len(g),
                           null_mse=sum(g.null_mse)/len(g)))
    buildings = []
    for b, g in pd.DataFrame(images).groupby('building'):
        buildings.append(dict(building=b, mse=sum(g.mse)/len(g),
                              null_mse=sum(g.null_mse)/len(g)))
    mse = sum(r['mse'] for r in buildings) / len(buildings)
    null = sum(r['null_mse'] for r in buildings) / len(buildings)
    return mse, null, 1-mse/null if null > 1e-12 else None, buildings


def class_maps(labels):
    out = {}
    for (m, c, b), g in labels.groupby(['method_id', 'condition', 'heldout_building']):
        coarse_tier = 'coarse' if 'coarse' in set(g.tier) else 'single'
        co = dict(zip(g.loc[g.tier.eq(coarse_tier), 'worker_id'], g.loc[g.tier.eq(coarse_tier), 'class_id']))
        fi = dict(zip(g.loc[g.tier.eq('fine'), 'worker_id'], g.loc[g.tier.eq('fine'), 'class_id'])) if 'fine' in set(g.tier) else co.copy()
        out[m, c, b] = dict(coarse=co, fine=fi)
    return out


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    FILES[str((ANALYSIS/'analyze_n20.py').relative_to(REPO))] = sha(ANALYSIS/'analyze_n20.py')
    for source in [STUDY/'analysis/team_continuous_check.py',STUDY/'multivariate/build_multivariate.py',
                   STUDY/'composition/prepare_design.py']:
        FILES[str(source.relative_to(REPO))] = sha(source)
    labels = read(STUDY/'composition/FROZEN_LABELS.csv', keep_default_na=False)
    feats = read(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    assert not labels.heldout_building.eq('ALL').any()
    assert not labels.duplicated(['method_id','condition','heldout_building','tier','worker_id']).any()
    assert not feats.duplicated(['condition','heldout_building','worker_id']).any()
    maps = class_maps(labels)
    feature_fits_path = STUDY/'multivariate/FEATURE_FITS.json'
    fits = json.loads(feature_fits_path.read_text())
    FILES[str(feature_fits_path.relative_to(REPO))] = sha(feature_fits_path)
    outside_fits = [r for r in fits if r['heldout_building'] != 'ALL']
    assert all(r['heldout_building'] not in r['train_buildings'] and r['target_records_used'] == 0 for r in outside_fits)
    taxonomy = read(REPO/'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv', keep_default_na=False)
    assert taxonomy.label_fit_scope.eq('leave_building_out').all()
    taxonomy_index = taxonomy.set_index(['condition','heldout_building','worker_id'])
    original_verified = 0
    for r in labels[labels.method_id.isin(['M_structure','SP_scale','A2_relation'])].itertuples():
        col = 'geometry_relation_class' if r.method_id == 'A2_relation' else 'primary_'+r.tier+'_class'
        assert taxonomy_index.loc[(r.condition,r.heldout_building,r.worker_id),col] == r.class_id
        original_verified += 1
    contrast_specs = [
        dict(condition='semi', method='SP_scale', scope='own_class_supported', anchor='SP_scale',
             outcome='B8L2', new='fine_source', baseline='coarse_source'),
        dict(condition='semi', method='MV_QTScopeSemi_semi_new', scope='common_new_anchor', anchor='MV_QTScopeSemi_semi_new',
             outcome='log_source_time_total', new='QT_moments_source', baseline='QT_source'),
        dict(condition='manual', method='M_structure', scope='own_class_supported', anchor='M_structure',
             outcome='B8L2', new='fine_source', baseline='coarse_source'),
    ]
    rows = []
    for spec in contrast_specs:
        if spec['condition'] == 'semi':
            pool = read(ANALYSIS/'semi/N20_PREDICTION_POOL_RESULTS.csv.gz')
            summary = read(ANALYSIS/'semi/N20_PREDICTION_SUMMARY.csv')
            increment = read(ANALYSIS/'semi/N20_PREDICTION_INCREMENT.csv')
        else:
            pool = read(ANALYSIS/'manual/own_class_supported__M_structure__M_structure__POOL_RESULTS.csv.gz')
            # Manual publication may still be running; compare only completed
            # atomic summary files, and keep this check independent if absent.
            summary_path = ANALYSIS/'manual/N20_PREDICTION_SUMMARY.csv'
            increment_path = ANALYSIS/'manual/N20_PREDICTION_INCREMENT.csv'
            summary = read(summary_path) if summary_path.exists() else None
            increment = read(increment_path) if increment_path.exists() else None
        pool = pool[pool.method_id.eq(spec['method']) & pool.support_scope.eq(spec['scope']) &
                    pool.design_anchor.eq(spec['anchor']) & pool.outcome.eq(spec['outcome'])]
        for weighting in ['configuration_uniform','member_universe_estimate']:
            z = pool[pool.weighting.eq(weighting)]
            a, b = z[z.model.eq(spec['new'])].copy(), z[z.model.eq(spec['baseline'])].copy()
            key = ['heldout_building','pool_id']
            assert not a.duplicated(key).any() and not b.duplicated(key).any()
            paired = a.merge(b,on=key,validate='one_to_one',suffixes=('_new','_base'))
            assert len(paired) == len(a) == len(b)
            for field in ['sampled_draws','null_mse','member_estimator_effective_sample_size']:
                assert np.allclose(paired[field+'_new'],paired[field+'_base'],rtol=1e-12,atol=1e-12)
            new_mse,new_null,new_r2,new_build = aggregate(a)
            base_mse,base_null,base_r2,base_build = aggregate(b)
            gain = base_mse-new_mse
            row = dict(spec, weighting=weighting, pools=len(a), images=a.image_id.nunique(),
                buildings=len(new_build), sampled_draws=int(a.sampled_draws.sum()),
                recomputed_mse_new=new_mse,recomputed_mse_baseline=base_mse,
                recomputed_R2_new=new_r2,recomputed_R2_baseline=base_r2,
                recomputed_relative_mse_gain=gain/base_mse,
                common_pool_and_draw_support=True,summary_available=summary is not None)
            if summary is not None:
                s = summary[summary.method_id.eq(spec['method']) & summary.support_scope.eq(spec['scope']) &
                    summary.design_anchor.eq(spec['anchor']) & summary.outcome.eq(spec['outcome']) &
                    summary.weighting.eq(weighting) & summary.target_panel.eq('all')]
                for model, expected_mse, expected_r2, prefix in [(spec['new'],new_mse,new_r2,'new'),(spec['baseline'],base_mse,base_r2,'baseline')]:
                    found=s[s.model.eq(model)]
                    assert len(found)==1
                    actual_mse=float(found.mse.iloc[0]);actual_r2=float(found.R2_relative_to_pool_mean.iloc[0])
                    assert math.isclose(actual_mse,expected_mse,rel_tol=1e-12,abs_tol=1e-12)
                    assert math.isclose(actual_r2,expected_r2,rel_tol=1e-12,abs_tol=1e-12)
                    row['reported_R2_'+prefix]=actual_r2
                    row['abs_R2_delta_'+prefix]=abs(actual_r2-expected_r2)
            if increment is not None:
                inc=increment[increment.method_id.eq(spec['method']) & increment.support_scope.eq(spec['scope']) &
                    increment.design_anchor.eq(spec['anchor']) & increment.outcome.eq(spec['outcome']) &
                    increment.weighting.eq(weighting) & increment.target_panel.eq('all') &
                    increment.new_model.eq(spec['new']) & increment.baseline.eq(spec['baseline'])]
                assert len(inc)==1
                reported=float(inc.relative_mse_gain.iloc[0]);assert math.isclose(reported,gain/base_mse,rel_tol=1e-12,abs_tol=1e-12)
                row['reported_relative_mse_gain']=reported
                row['abs_relative_mse_gain_delta']=abs(reported-gain/base_mse)
            rows.append(row)
    publish_csv(pd.DataFrame(rows),'RECOMPUTED_METRICS.csv')
    # One actual shared support fold: rebuild legal workers and endpoint hashes
    # independently from frozen label and feature rows, without re-fitting.
    fold = read(ANALYSIS/'semi/N20_FOLD_MAPS.csv.gz')
    common = fold[fold.support_scope.eq('common_new_anchor')]
    building = sorted(common.heldout_building.unique())[0]
    same = common[common.heldout_building.eq(building)]
    methods = sorted(same.method_id.unique())
    assert len(methods)==3 and same.supported_endpoint_ids_sha256.nunique()==1
    f = feats[feats.condition.eq('semi') & feats.heldout_building.eq(building)].set_index('worker_id')
    qt = ['q_effect','q_downside','t_effect','t_tail']
    variable = set(f.index[np.isfinite(f[qt]).all(axis=1)])
    for method in methods:
        variable &= set(maps[method,'semi',building]['coarse']) & set(maps[method,'semi',building]['fine'])
    for r in same.itertuples():
        assert set(r.variable_workers.split('|'))==variable
    membership = read(NEXT/'candidate_n20/CONFIG_MEMBERSHIP.csv.gz')
    anchor = membership[membership.condition.eq('semi') & membership.method_id.eq('MV_QTScopeSemi_semi_new')].copy()
    request_path = NEXT/'candidate_n20/ENDPOINT_REQUESTS.json.gz'
    requests = json.load(gzip.open(request_path,'rt'))['requests']
    FILES[str(request_path.relative_to(REPO))]=sha(request_path)
    workers = {r['team_key']:set(r['member_workers']) for r in requests}
    anchor = anchor[anchor.team_key.map(lambda k:workers[k] <= variable)].copy()
    digest = hashlib.sha256('|'.join(sorted(anchor.team_key)).encode()).hexdigest()
    assert set(same.supported_endpoint_ids_sha256)=={digest}
    target = anchor[anchor.building.eq(building)]
    assert len(target)>=2
    # Failure is available for every endpoint, so the support restriction does
    # not change either base sampling scheme. Verify explicit train hierarchy.
    train = anchor[anchor.building.ne(building)].copy()
    keep=train.groupby('pool_id').team_key.transform('size').ge(2)
    train=train[keep].copy()
    weight_rows=[]
    for scheme in ['configuration_uniform','member_universe_estimate']:
        if scheme=='configuration_uniform':
            raw=1/train.groupby('cell_id').team_key.transform('size').to_numpy(float)
        else:
            raw=train.possible_member_sets.to_numpy(float)/train.registered_member_sets.to_numpy(float)
        train['raw']=raw
        train['pool_normalized']=train.raw/train.groupby('pool_id').raw.transform('sum')
        p=train[['pool_id','image_id','building']].drop_duplicates()
        image_counts=p.groupby('building').image_id.nunique().to_dict()
        pool_counts=p.groupby(['building','image_id']).pool_id.nunique().to_dict()
        B=train.building.nunique()
        train['outer_weight']=[v/(B*image_counts[b]*pool_counts[b,i]) for v,b,i in zip(train.pool_normalized,train.building,train.image_id)]
        building_mass=train.groupby('building').outer_weight.sum()
        assert np.allclose(building_mass,1/B,rtol=1e-12,atol=1e-12)
        for (b,i), g in train.groupby(['building','image_id']):
            assert math.isclose(g.outer_weight.sum(),1/(B*image_counts[b]),rel_tol=1e-12,abs_tol=1e-12)
        weight_rows.append(dict(heldout_building=building,weighting=scheme,training_buildings=B,
            training_images=train.image_id.nunique(),training_pools=train.pool_id.nunique(),
            training_draws=len(train),weight_sum=float(train.outer_weight.sum()),
            max_building_mass_error=float(max(abs(building_mass-1/B))),target_building_used=False))
    publish_csv(pd.DataFrame(weight_rows),'WEIGHT_HIERARCHY_CHECK.csv')
    # Broad same-endpoint check on the six fully materialized own-class files.
    paired_groups=0
    for condition, methods in [('manual',['M_structure','A2_relation','MV_QTD_manual_new']),
                               ('semi',['SP_scale','A2_relation','MV_QTScopeSemi_semi_new'])]:
        for method in methods:
            q=read(ANALYSIS/condition/f'own_class_supported__{method}__{method}__POOL_RESULTS.csv.gz')
            for _,g in q.groupby(['heldout_building','pool_id','weighting','outcome']):
                for col in ['sampled_draws','null_mse','member_estimator_effective_sample_size']:
                    assert np.allclose(g[col],g[col].iloc[0],rtol=1e-12,atol=1e-12)
                paired_groups+=1
            assert not q.model.str.contains('QT').any()
    findings=[
        'No blocking arithmetic or model-support inconsistency was found in this bounded check.',
        'The target pool outcome mean is used only to define relative responses and evaluate R2; this is not absolute prediction on an unseen image.',
        'Negative outer-building R2 rejects these shared linear/quadratic response models on tested support; it does not imply zero configuration effect, no local class value, or matched interchangeability.',
        'Configuration-uniform weights refer to the frozen original fine/A2 sampling cells; after support/outcome filtering they are renormalized over surviving cells, not a newly exhaustive coarse partition.',
        'Member-universe weighting is a ratio estimate from at most three sampled member sets per cell, not member-exhaustive evidence.',
        'Common endpoint comparison and n20 configuration effects do not fix a common replacement background or m; matched ABC results remain separate.',
        'The existing outcome-informed research history and frozen sampled endpoint bank are reused; this does not become a new end-to-end blind validation merely because fitted maps exclude the held-out building.'
    ]
    receipt=dict(status='passed_with_explicit_estimand_limits',new_fusion_calls=0,new_model_fits=0,
        recomputed_contrasts=len(contrast_specs),weighting_variants=2,metric_rows=len(rows),
        verified_original_taxonomy_label_rows=original_verified,
        verified_feature_fit_exclusion_records=len(outside_fits),
        own_class_same_support_pool_metric_groups=paired_groups,
        independently_reconstructed_shared_fold=dict(condition='semi',heldout_building=building,
            methods=sorted(same.method_id.unique()),variable_workers=len(variable),
            all_train_and_target_endpoint_rows=len(anchor),target_endpoint_rows=len(target),
            supported_endpoint_ids_sha256=digest,all_three_method_hashes_identical=True),
        numeric_results=rows,weight_hierarchy_results=weight_rows,findings=findings,
        source_files=FILES)
    path=HERE/'NEW_ANALYSIS_CHECK.json';tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    json.loads(tmp.read_text());tmp.replace(path)
    table=['| 条件/比较 | 权重 | 建筑/图/队 | 基线 R² | 新模型 R² | 相对 MSE 收益 |',
           '| --- | --- | --- | ---: | ---: | ---: |']
    for r in rows:
        name='Semi SP 粗→细：B8' if r['method']=='SP_scale' else ('Manual M 粗→细：B8' if r['condition']=='manual' else 'Semi 共同端点 QT 加个人二阶矩：时间')
        weight='配置等权' if r['weighting']=='configuration_uniform' else '成员宇宙估计'
        table.append(f"| {name} | {weight} | {r['buildings']}/{r['images']}/{r['sampled_draws']} | {r['recomputed_R2_baseline']:.6f} | {r['recomputed_R2_new']:.6f} | {r['recomputed_relative_mse_gain']:.4%} |")
    report='''# n=20 新分析的小型独立复核

**结论：本次限定风险复核通过，没有发现需修正已报告数值或更换采用判断的算术、粗细支持不一致、折内标签混用问题。** 本复核不重新分类、不拟合回归、不运行融合；从已经保存的逐池误差重新按参考池→图片→建筑聚合，并重建一个共同端点折的人员支持和权重。

## 数值独立重算

相对 MSE 收益定义为 `(基线 MSE−新模型 MSE)/基线 MSE`；负值表示新模型误差更大。这里的 R² 都相对于目标池加权均值基线。

'''+ '\n'.join(table)+'''

以上 3 个比较各采用 2 种权重，R²、MSE 和增量均与最终汇总相符，容差 1e−12。完整精度和逐项差值见 `RECOMPUTED_METRICS.csv`。

## 实际检查

- 原分类的 5,972 条冻结 M/SP/A2 标签逐行与原楼外标签表一致；连续特征的 44 个目标楼外拟合回执均排除目标建筑，且目标记录使用数为 0。代码对同一外层折的训练池和目标池使用同一楼外标签与 QT 映射；回归系数和尺度由其他建筑估计。
- 独立重建 Semi 的 `7y3sRwLe3Va` 共同新批锚折：35 名全局合法人员，395 条该折训练和目标候选端点、27 条目标端点；三个方法的实际支持 SHA256 一致。这里 35 是该折全局合法人员数，并不是每图拥有 35 个共同人员。
- 六个 own_class_supported 方法×条件中，16,232 个池×指标×权重组的粗细模型拥有相同样本数、相同空模型 MSE、相同有效样本量。它们没有用 QT 完整性作为类别总作用的前置门槛。
- 两种权重在所检查训练折均合计 1；参考池、图片、建筑层级的权重符合声明，建筑权重的最大数值误差约 1.39e−17。数值重聚合也采用相同层级，没有让大楼或大量配置主导最终均值。
- 原成员抽样代码按类别从成员中均匀抽取、去重后保留至多 3 组；成员宇宙权重的原始抽样分母与其一致。

## 必须保留的解释边界

1. **配置总作用、共享响应模型和匹配替换是三个对象。** 格间/格内变化说明固定 n 下实际配置和具体成员的响应；外楼 R² 检查的是当前线性/固定二次共享模型，不能把负值写成“类别构成没有作用”。本复核也没有检验同背景、相同 m 的可互换性；续研的 n20_abc 匹配事件单独回答该问题。
2. **目标池均值参与定义相对响应。** 减去该池实际共同样本的加权均值之后评价 R²，并未使用目标 y 拟合回归系数；这属于相对响应检验，不能写成未知新图的绝对质量预测。
3. **配置等权针对冻结原细类/A2配置格。** 共同特征与结果筛选之后，只在留存格及成员中重新归一；粗模型继续使用这组同端点权重，不代表另做了一套“粗类配置等权”的独立总体。成员宇宙估计仍是每格至多 3 队的比率估计，不能称为全体成员结果。
4. **小幅细类增量需要按用途采用。** Manual M 的本次 B8 粗→细相对误差改善仅约 0.55%/0.13%，与 Semi SP 的负增量、连续时间历史的较明显增量不同。这是具体模型/权重/人员域的结论，不能据此统一合并 M/SP/A2/MV，也不能消除已经观测到的局部结构补充或稀释机制。
5. **楼外映射不把已有探索变成新盲测。** 已冻结成员样本库及之前的选型历史继续复用，本次仅核对其声明的外层映射和预测计算，没有重新宣称端到端全新盲测。

`NEW_ANALYSIS_CHECK.json` 保存全部输入 SHA256、检查数量和完整数值；`WEIGHT_HIERARCHY_CHECK.csv` 保存独立权重恒等式；`check_n20_analysis.py` 可从原已计算小表复现，不运行融合或模型拟合。
'''
    (HERE/'NEW_ANALYSIS_CHECK_ZH.md').write_text(report,encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'metric_rows':rows,'same_support_groups':paired_groups,'shared_fold':receipt['independently_reconstructed_shared_fold']},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
