"""本地模型新信号的回顾性对照；同面板点数单轴是增量参照。"""
from collections import Counter
import json

import numpy as np
from PIL import Image

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from .difficulty_score_20261009 import building_holdout, evaluate_subjective, LABELS
from .difficulty_features_20261009 import SCORE_FEATURES

BASE = ROOT / 'analysis_results/objective_difficulty_20261009'
OUT = BASE / 'model_comparison'
NEW_FEATURES = ('hohonet_replay_pair_count', 'hohonet_rotation_mae_deg', 'bilayout_raw_relative_gap')


def numeric(value):
    if value in ('', None):
        return None
    number = float(value)
    if not np.isfinite(number):
        raise ValueError('nonfinite_model_evidence')
    return number


def join_model_evidence(base, hoho, bilayout):
    h, b = {}, {}
    for source, lookup in ((hoho, h), (bilayout, b)):
        for row in source:
            if row['image'] in lookup:
                raise ValueError('duplicate_model_evidence:' + row['image'])
            lookup[row['image']] = row
    output = []
    for row in base:
        hr, br = h.get(row['image']), b.get(row['image'])
        if any(r is not None and r['image_id'] != row['image_id'] for r in (hr, br)):
            raise ValueError('model_evidence_identity_mismatch:' + row['image'])
        hok, bok = hr is not None and hr['status']=='complete', br is not None and br['status']=='ok'
        output.append(dict(row,
            hohonet_replay_status=hr['status'] if hr else 'missing',
            bilayout_raw_status=br['status'] if br else 'missing',
            hohonet_replay_pair_count=numeric(hr['phase0_pair_count']) if hok else None,
            hohonet_rotation_mae_deg=numeric(hr['raw_boundary_rotation_mae_deg']) if hok else None,
            hohonet_boundary_correction_deg=numeric(hr['phase0_boundary_correction_mae_deg']) if hok else None,
            bilayout_raw_relative_gap=numeric(br['relative_gap']) if bok else None))
    return output


def comparison(rows, panel, features, kind):
    inputs = [dict(image=r['image'], building=r['building'], x=[r[k] for k in features],
                   label=LABELS.get(r['subjective_label'])) for r in rows]
    if len({r['building'] for r in inputs})<2:
        raise ValueError('insufficient_model_comparison_buildings:' + panel)
    predictions = building_holdout(inputs)
    metrics = [dict(panel=panel, kind=kind, complete_images=len(inputs), **r)
               for r in evaluate_subjective(predictions, features)]
    return [dict(panel=panel, kind=kind, **r) for r in predictions], metrics


def compare_image_sources(first_path, second_path):
    """仅诊断已选输入的像素内容；不对齐或改写推理输入。"""
    with Image.open(first_path) as first, Image.open(second_path) as second:
        first_size, second_size = first.size, second.size
        a = np.asarray(first.convert('RGB').resize(second.size, Image.Resampling.BOX), dtype=float)
        b = np.asarray(second.convert('RGB'), dtype=float)
    if second_size[0] % 4:
        raise ValueError('source_width_not_quarter_divisible')
    maes = [float(np.abs(np.roll(a, k*second_size[0]//4, axis=1)-b).mean()) for k in range(4)]
    return dict(first_size=str(first_size), second_size=str(second_size),
                zero_roll_rgb_mae_255=maes[0], zero_roll_rgb_max_255=float(np.abs(a-b).max()),
                best_quarter_roll=int(np.argmin(maes)), quarter_roll_maes=json.dumps(maes))


def run():
    base = read_csv(BASE/'stratified/features_and_scores.csv')
    hoho = read_csv(BASE/'hohonet_probe/per_image.csv')
    bilayout = read_csv(BASE/'bilayout_probe/research_source/raw.csv')
    summary = json.loads((BASE/'hohonet_probe/summary.json').read_text(encoding='utf-8'))
    if len(hoho) != len(base) or summary['images'] != len(base):
        raise ValueError('model_probe_not_finished')
    rows = join_model_evidence(base, hoho, bilayout)
    bi_inputs = json.loads((BASE/'bilayout_probe/research_source/inputs.json').read_text(encoding='utf-8'))['images']
    bi_sources = {r['image_id']: r['image_source'] for r in bi_inputs}
    source_audit = [dict(image=r['image'], image_id=r['image_id'],
                        hohonet_path=r['image_path'], bilayout_path=bi_sources[r['image_id']],
                        **compare_image_sources(r['image_path'], bi_sources[r['image_id']])) for r in hoho]
    if any(r['hohonet_path'] != r['bilayout_path'] for r in source_audit):
        raise ValueError('comparison_requires_same_research_image_source')
    for row in rows:
        for name in SCORE_FEATURES:
            row[name] = numeric(row[name])
    ordinary = [r for r in rows if r['calibration_panel']=='ordinary_historical_panel']
    expanded = [r for r in ordinary if all(r[k] is not None for k in NEW_FEATURES)]
    common = [r for r in expanded if all(r[k] is not None for k in SCORE_FEATURES)]
    predictions, metrics = [], []
    for panel, subset in (('old_common', common), ('expanded_raw', expanded)):
        p, m = comparison(subset, panel, NEW_FEATURES, 'new_raw_candidates')
        predictions += p
        metrics += m
        if panel == 'old_common':
            p, m = comparison(subset, panel, SCORE_FEATURES, 'original_three_proxy_candidates')
            predictions += p
            metrics += m
    correction = [r for r in ordinary if r['hohonet_boundary_correction_deg'] is not None]
    p, m = comparison(correction, 'correction_available', ('hohonet_boundary_correction_deg',), 'supplementary_single_axis')
    predictions += p
    metrics += [r for r in m if r['score']=='hohonet_boundary_correction_deg']
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT/'joined_features.csv', rows)
    write_csv(OUT/'image_source_audit.csv', source_audit)
    write_csv(OUT/'metrics.csv', metrics)
    write_json(OUT/'holdout_predictions.json', predictions)
    write_csv(OUT/'holdout_predictions.csv', [dict(r,
        weights=json.dumps(r['weights']), training_buildings=json.dumps(r['training_buildings']),
        component_scores=json.dumps(r['component_scores'])) for r in predictions])
    counts = dict(all_images=len(rows), hohonet_complete=sum(r['hohonet_replay_status']=='complete' for r in rows),
        bilayout_raw_complete=sum(r['bilayout_raw_status']=='ok' for r in rows),
        old_common=len(common), old_common_labelled=sum(r['subjective_label'] in LABELS for r in common),
        expanded_raw=len(expanded), expanded_raw_labelled=sum(r['subjective_label'] in LABELS for r in expanded),
        correction_available=len(correction), correction_labelled=sum(r['subjective_label'] in LABELS for r in correction))
    outcomes = []
    for panel in ('old_common', 'expanded_raw'):
        candidate = next(r for r in metrics if r['panel']==panel and r['kind']=='new_raw_candidates' and r['score']=='calibrated_score')
        count = next(r for r in metrics if r['panel']==panel and r['kind']=='new_raw_candidates' and r['score']=='hohonet_replay_pair_count')
        losses = {'candidate_mse':candidate['building_equal_mse'], 'point_count_mse':count['building_equal_mse']}
        outcomes.append(dict(panel=panel, **losses,
            candidate_lower_loss_than_point_only=losses['candidate_mse'] < losses['point_count_mse'],
            weights_frequency=dict(Counter({r['building']: json.dumps(r['weights']) for r in predictions
                if r['panel']==panel and r['kind']=='new_raw_candidates'}.values())),
            evaluated_weights_frequency=dict(Counter({r['building']: json.dumps(r['weights']) for r in predictions
                if r['panel']==panel and r['kind']=='new_raw_candidates' and r['label'] is not None}.values()))))
    source_summary = dict(images=len(source_audit),
        rgb_mae_255_median=float(np.median([r['zero_roll_rgb_mae_255'] for r in source_audit])),
        rgb_mae_255_max=float(max(r['zero_roll_rgb_mae_255'] for r in source_audit)),
        best_nonzero_quarter_roll=sum(r['best_quarter_roll']!=0 for r in source_audit),
        method='RGB uint8, HoHo source BOX resize to Bi source size; four quarter rolls only diagnostic, no input alteration')
    contract = dict(schema='difficulty_model_comparison_20261009_v1', counts=counts,
        features=NEW_FEATURES, feature_directions='larger temporarily means stronger model proxy signal; not validated human difficulty',
        source_paths=['stratified/features_and_scores.csv','hohonet_probe/per_image.csv','bilayout_probe/research_source/raw.csv'],
        primary='同面板普通图的新3候选：重放点数/raw边界yaw变化/Bi raw双头差；嵌套建筑留出，首先对比同折点数单轴',
        supplementary='raw到最终边界综合改变量仅在可计算普通图上单轴检查；多值/相机外/无效底面不补0，不纳入主3轴',
        panel='old_common新旧特征共同可算普通图，双方重新同面板留出；expanded_raw另算更大普通面板，不将样本增多当性能提升',
        fitting='复用既有经验百分位、0.25非负权重网格加等权、内外建筑留出；主观标签0/0.5/1仅为工作损失',
        validation_boundary='看过历史标签/个案后设计特征，嵌套只隔离本轮归一化和选权；非新盲验证，不报告因果或显著性；模型训练/选参独立性未证明',
        deployment='新候选不默认替换首轮分数；特殊图只保存原轴/原始信号，不参与普通主观校准',
        image_source_audit=source_summary,
        superseded_source_comparison='model_comparison_external_source_snapshot retains first comparison on distinct model-local copies; not primary evidence',
        outcomes=outcomes)
    write_json(OUT/'field_contract.json',contract)
    write_json(OUT/'summary.json',dict(counts=counts,outcomes=outcomes,image_source_audit=source_summary))
    lines=['# 图片难度：本地模型信号与点数对照','',
        '2026-10-09。先提取不使用GT／人员作答／难度标签的模型输出，再离线连接主观标签。所有结果仍为回顾性研究候选。','',
        '## 覆盖与面板','',f"全研究图{len(rows)}；旧共同普通面板{len(common)}图/{counts['old_common_labelled']}标签，扩展raw普通面板{len(expanded)}图/{counts['expanded_raw_labelled']}标签。边界修正另有{len(correction)}图/{counts['correction_labelled']}标签可计算。",'',
        '原三个代理和新三个候选在old_common上各自重做同建筑留出；expanded_raw单独计算，不能跨面板比较高低。普通仍含clear和unflagged，未标特殊不认证正常。特殊图原始信号保留、不进主观选权。','',
        '|面板|候选组|评分/单轴|标签图|建筑|Spearman|建筑等权MSE|','|---|---|---|---:|---:|---:|---:|']
    for r in metrics:
        rho='N/A' if r['spearman'] is None else f"{r['spearman']:.4f}"
        mse='N/A' if r['building_equal_mse'] is None else f"{r['building_equal_mse']:.4f}"
        lines.append(f"|{r['panel']}|{r['kind']}|{r['score']}|{r['n']}|{r['buildings']}|{rho}|{mse}|")
    lines += ['', '## 是否超过点数单轴', '']
    for r in outcomes:
        conclusion='损失较低；仍只是候选增量，不是独立认证' if r['candidate_lower_loss_than_point_only'] else '没有更低损失；不据此替换点数基线'
        lines.append(f"- {r['panel']}：{conclusion}；全部预测建筑折权重频次{r['weights_frequency']}，其中有标签的评价建筑折{r['evaluated_weights_frequency']}。")
    lines += ['', '## 输入图像核查', '',
        f"两套模型的{len(source_audit)}图输入源独立保存路径和尺寸。HoHo源用BOX缩小至Bi源尺寸后的RGB像素MAE中位数{source_summary['rgb_mae_255_median']:.6f}/255、逐图MAE最大{source_summary['rgb_mae_255_max']:.6f}/255；四个90°滚动中非零滚动误差最低{source_summary['best_nonzero_quarter_roll']}图。",
        '这只核查源图内容与四分之一周方向，没有修改预测输入；HoHo实际使用torch bilinear，Bi实际使用其原resize流程，不能据此声称预处理或输出完全一致。逐图记录见image_source_audit.csv。']
    lines += ['', '首次比较发现模型各自副本存在内容差异（RGB MAE最高50.93/255），其中uNb-47和zs-05最佳四分之一周滚动非零；这些诊断不能将所有差异归为旋转。首次比较保留于model_comparison_external_source_snapshot。当前主比较已在与HoHo相同研究PNG/JPG路径重新推理Bi raw，全259图同源，保留各模型既定预处理；未旋转修复或改写图片。旧Bi底面/静态代理仍只是历史来源控制，不认证与新同源预测精确等价。']
    lines += ['', '## 解释边界', '',
        '- yaw只有四个90°相位，是模型等变性诊断；低变化不证明难度低或预测正确，相位数不是独立图片数。',
        '- Bi raw是两头radial depth差，最终底面相等不保证raw相同。不是置信度、遮挡或真实范围误差。',
        '- boundary correction包含峰检测、墙拟合、上下高度统一及可能回退；多值边界不强行平均，作为不可计算。',
        '- 原型特征在看过案例后选择，本次内外留出只隔离百分位／权重；不能声称全流程新建筑独立泛化。',
        '- 主观三档口径不统一、部分判断已看过作答；任何相关改善均不等于识别固有难度。',
        '- 首轮/分层分数和参考冻结不改。新信号保留原量纲供解释，未经独立验证不建立简单／中等／困难新阈值。', '',
        '来源：[HoHoNet重放](../hohonet_probe/REPORT.md)、[BiLayout探查](../bilayout_probe/REPORT.md)、[场景分层](../stratified/REPORT.md)。', '',
        '复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_model_comparison_20261009`。', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(counts=counts,outcomes=outcomes)),flush=True)


if __name__=='__main__':
    run()
