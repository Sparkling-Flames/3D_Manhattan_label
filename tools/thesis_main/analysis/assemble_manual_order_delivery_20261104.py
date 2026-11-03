"""Assemble the version contract, sourced conclusion index and module map.

This is a reporting operation over verified saved results, not a statistical
estimator or a replacement for the original study's aggregation functions.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

OUT = ROOT / 'research/fusion/manual_order_impact_20261104'


def main():
    rows = []

    def add(id, topic, status, finding, sources, change_layer='support_expansion', scope='fixed_coordinate_assisted'):
        rows.append(dict(id=id, topic=topic, status=status, finding=finding, sources=sources,
                         analysis_scope=scope, change_layer=change_layer,
                         original_automatic_preserved=True,
                         original_scored_values_changed=False,
                         missing_Q_imputed_as_zero=False))

    add('M01','方法身份','条件变化','原自动分支已正确使用既有来源顺序；本次是额外的定向人工连接辅助，不是恢复原已授权但漏接的输入。原自动实验、分母及方法身份保留。','endpoints/FIELD_CONTRACT.json|../missing_ring_review_20261104/CURRENT_REAUDIT.md','connection_method')
    add('M02','57组可评性','条件变化','固定436个节点及其坐标、票数、团队、参考；57组中56组新增完整条件评分，1组底面自交仍无Q。原57组Q均缺失，不能计算从0提高的分数。','endpoints/ENDPOINT_SCORES.csv|endpoints/CHECKS.json')
    add('M03','几何与可见性','条件变化','56个可评端点中36个相机在可见核内，20个保留camera_visibility_unresolved诊断。可计算条件分数不等于物理布局、遮挡或GT已被人工证实。','endpoints/ENDPOINT_GEOMETRY.csv.gz|endpoints/README.md','geometry_acceptance')
    add('P01','完整预处理链','保持','10,730份冻结对象中10,597份可用对象的shared-x、点对、源索引和最终视图复算一致；129份不可用及4份阻断保持缺失。57队源记录与436个融合节点坐标差均为0，没有遗漏预处理。','preprocessing_audit/REPORT_ZH.md|preprocessing_audit/CHECKS.json','input_invariance')
    add('P02','F2/F9坐标候选','条件变化','单独将F2/F9上下点x置438.8037，完整评分B8L2=39.615619、D10=41.305788；自交消除，camera_in_visible_kernel仍为false。该候选增加坐标干预，未并入主57组。','coordinate_candidate/CANDIDATE_SCORE_COMPARISON.csv|coordinate_candidate/README.md','coordinate_intervention','coordinate_candidate_not_adopted')
    add('P03','坐标候选下游','条件变化','50条AC引用中44条新增可评、6条仍因另一端缺Q；两个联盟引用新增Q，但最佳纯类、比较池和全员−最佳纯类摘要不变。','ac/coordinate_candidate/README.md|alliances/coordinate_candidate/CHECKS.json','candidate_support_expansion','coordinate_candidate_not_adopted')
    add('H01','50%换人 · 14/7','幅度变化','147合法事件中三队共同Q由136增至146，图67→69；GA +4.037387→+3.531657，GS +3.766842→+3.440645，C−B +6.380314→+6.711615。均值方向保持；同类幅度3.590820→4.200013，跨类直接幅度7.628208→7.731670。','half_qonly/HALF_SUMMARY.csv|half_qonly/HALF_SUPPORT.csv')
    add('H02','扩大背景 · 20/7','幅度变化','20/7为35%替换。61事件的三队共同Q 58→60、图52→53；GA +2.432706→+3.108480，GS +1.779999→+2.460035。C−B只需B/C，支持58→61、图52→54，均值+3.800959→+4.213539。','half_qonly/HALF_SUMMARY.csv|half_qonly/HALF_SUPPORT.csv')
    add('H03','仍不可评的ABC','保持','14/7的S9-12事件A/B仅3节点；20/7的x8-08事件A仅3节点。排序不补点，三队共同Q仍缺失。20/7的B/C可评不代表该事件三队可评。','half_qonly/REPORT_ZH.md|half_qonly/HALF_SUPPORT.csv','unaffected_failure')
    add('H04','14→20的额外幅度','需改写','相同X/Y/Z的全集20−14 GA由−1.915067变+0.258069；D也替换子集的GA/GS均翻正。不能继续写一律随人数增加而减弱；背景D14包含于D20子集仍为负。人数、背景及MV50门槛并变，不是纯人数因果效应。','half_qonly/HALF_MATCHED_BACKGROUND_SUMMARY.csv')
    add('H05','难度分层','需改写','20/7中等层C−B由+2.808751变−1.296996，支持9→10图；困难层仍仅2图且保持。14/7困难GA/GS幅度下降但均值仍正。难度标签一图一个，未更改。','half_qonly/HALF_DIFFICULTY.csv')
    add('H06','反例清单与解释','条件变化','重新应用相同诊断条件，原30图全部保留历史记录，辅助诊断集合28图，无新进入图；2图退出，6图解释变化。部分原未连接问题转为可评价的定位、方向或结构偏差。','half_qonly/COUNTEREXAMPLE_TRANSITIONS.csv|half_qonly/COUNTEREXAMPLE_EVENT_EXPLANATIONS.csv')
    add('Q01','DSTRUCT与Q-only · 14/7','幅度变化','结构−Q_RAW +0.061904→−0.034303，95%建筑簇区间仍跨0；对Q_PEER +0.228738→+0.061952，亦跨0。未显示额外平均Q优势的判断保持，不等于两政策已证实等效。','half_qonly/QONLY_SUMMARY.csv|half_qonly/QONLY_SUPPORT.csv')
    add('Q02','DSTRUCT与Q-only · 20/7','需改写','结构−Q-only −0.113543→−0.482499，原95%区间[−0.385915,+0.000516]变为[−1.219601,−0.000866]，上界刚低于0。在该定向辅助扩展支持下出现Q-only更高的证据，不能仍写成区间跨0。','half_qonly/QONLY_SUMMARY.csv')
    add('Q03','不同选员事件','条件变化','20/7新增S9-09事件：结构Q39.914405、Q-only79.988704，差−40.074298；边界和方向损失较大，高度损失差很小。不同选员子集均差−1.998106→−7.437562，仍是事后子集。','half_qonly/QONLY_DIFFERENT_SELECTION_EVENTS.csv.gz|half_qonly/QONLY_DIFFERENT_SELECTION_SUMMARY.csv')
    add('S01','同房K3 C2→C3 · 10/5','幅度变化','六端共同Q 295→318/322事件；19图对的GA4.875999→4.524849、GS5.158088→4.786979、C−B10.753257→10.330883。正图对17/19、16/19、19/19均保持；18/19图对两视角C−B同正保持。','same_room/QUALITY_COMPONENT_REPETITION_SUMMARY.csv|same_room/PAIR_DIRECTION_STATES.csv|same_room/SUPPORT_CHANGES.csv')
    add('S02','同房跨视角相关','幅度变化','主K3的C−B Pearson 0.372346→0.446163、Spearman 0.626316→0.619298。两种相关没有一致上升；它们是既有图对的描述，不能据此宣称预测或泛化能力提升。','same_room/QUALITY_COMPONENT_REPETITION_SUMMARY.csv')
    add('S03','同房角点支持','保持','新增六端Q没有扩大主K3的六对角点对应支持，仍为240。节点数量、逐角点绑定的共同支持与完整Q支持须分开。12/6、14/7及有限配比同房输入未命中。','same_room/ORIGINAL_COMMON_SUPPORT_PARITY.csv|same_room/EXACT_DEPENDENCY_INTERSECTIONS.csv','metric_specific_support')
    add('S04','原答同房质量/同用途','保持','原答均值、个人Q、时间与同用途数据不读取这57个新融合分数；沿原结果保留。历史Q条件消费者472行保持，实际条件交集为0。','same_room/REPORT_ZH.md|dependencies/INDIRECT_DEPENDENCIES.csv','no_actual_dependency')
    add('S05','同房方向细状态','条件变化','主K3的GA跨视角异号图对5→4、两视角同负0→1；GA正均值图对仍17/19，原4个诊断图对集合保持。主要均值方向保持不等于全部跨视角方向细状态不变。','same_room/PAIR_DIRECTION_STATES.csv|same_room/PAIR_COUNTEREXAMPLE_TRANSITIONS.csv')
    add('A01','AC当前登记实验','条件变化','339个方法事件对应245个物理对；新增257个可评方法事件、193个可评物理对，82方法事件仍缺Q。原团队、容量及登记设计不变；重复方法引用不能增加独立样本数。','ac/AFFECTED_EVENT_METRICS_ASSISTED.csv.gz|ac/REPORT_ZH.md')
    add('A02','AC主目标50%条件','保持','主目标中立50%直接AC在n14/16/18/20/22没有新增Q变化；主目标变化集中在n28/m7、N−m边界和纯类，不能把其它目标变化泛化到全部换人条件。','ac/MAIN_SUMMARY_CHANGES.csv.gz|ac/REPORT_ZH.md','unhit_condition')
    add('A03','AC增加剩余成员的补偿','需改写','primary TARGET K3/3→1/all_outside_D的addition均值+0.197560→−0.152840（57→58图），该条件的平均补偿表述需改写；3→2仍为正+2.685634→+2.386840（197→199图），部分补偿判断保持。','ac/sensitivity/three_leg_common_support_v2/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY_CHANGES.csv.gz')
    add('A04','AC方法幅度排序','需改写','primary共同池n28/m7，RAW3相对OPPSTRUCT的|ΔQ|均差+1.054490→−0.103143，RAW3相对TARGET K2 +0.038760→−1.156838；条件内的幅度排序可翻转，不支持无条件方法优劣排序，也不启动分类重选。','ac/context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz')
    add('A05','AC精确背景','条件变化','other/admitted的TARGET K3/2→3/n4m2同XZ背景效应差−2.164310→+4.972688，但支持只有1→2图；primary精确背景Q不变。小支持翻向不能外推。','ac/sensitivity/exact_outside_background/SUMMARY_CHANGES.csv.gz')
    add('A06','AC固定块增大背景','需改写','固定X/Z、m5、n20→28，primary TARGET K3的1→3和2→3的ΔQ阶差分别−0.170801→+4.271162、−0.755925→+3.823113，仅3→4图；m7的TARGET K3仍−1.889315→−0.786955（60→61图）。不能无条件保持背景增大会稀释换人效果。','ac/sensitivity/SENSITIVITY_SUMMARY_CHANGES.csv.gz')
    add('L01','主目标纯类与全员','保持','原205图支持不变；冻结标签纯类更优173/205，更新标签169/205，均保持。冻结/更新是标签快照，不能与自动/人工连接版本混为一轴。403可执行联盟和11容量记录保持。','alliances/FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv|alliances/CHECKS.json','unaffected_primary_comparison')
    add('L02','其它目标纯类与全员','条件变化','更新标签共同池24→25、仍23图，全员−最佳纯类均值−0.077642→+0.049069；纯类更优7图、全员更优9图、平7图保持。小均差翻向来自支持/候选扩展，最佳纯类是事后选择。','alliances/FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv|alliances/POOL_SUPPORT_AND_SELECTION_CHANGES.csv')
    add('C01','配比与成员波动','幅度变化','67有限面板、11冻结方法下TARGET K3宏观配比间方差占比32.439565%→32.534050%；同配比内部占比仍约67.47%。两者都重要，配比不能替代实际成员身份。','composition/ALL_METHOD_COMPARISON.csv|composition/REPORT_ZH.md')
    add('C02','两个受影响有限面板','幅度变化','rPc-06/n4可评34→35，配比间占比74.069736%→77.344724%；uNb-88/n3可评9→10，71.891028%→73.972361%。保留全部原团队和标签支持，原共同指标统计差0。','composition/AFFECTED_PANEL_VARIANCE.csv.gz|composition/CHECKS.json')
    add('C03','新增配比的成员稳定性','尚不能判断','在TARGET_DSTRUCT_K3下，rPc的2:2:0混合配比及uNb的0:3:0纯类配比各由0队可评变1队可评。各只有一个实际成员组合，无法据单队估计同配比内部变动或证明稳定。','composition/AFFECTED_CONFIGURATION_COUNTS.csv.gz|composition/AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz')
    add('N01','主目标人数及停止','保持','主目标206个自然路径源表、当前k2补件、门洞各版本、OOS和停止端点均无精确团队命中；不重算这些模块，不把旧k2延期与当前k2结果混用。','dependencies/UNHIT_CURRENT_MODULES.csv|natural/DOWNSTREAM_CONSUMERS.csv','no_actual_dependency')
    add('N02','其它目标自然路径','幅度变化','rPc-06的k4均Q73.467623→72.556038，P10 53.601518→44.857986、SD14.013133→14.699284；uNb-88的k3均Q45.420856→44.478358，P10 30.940435→32.416707、SD11.388243→11.190052。保留8/25次重复路径引用频率。','natural/AFFECTED_K_COMPARISON.csv')
    add('N03','两个小池的平台人数','尚不能判断','N=7和5均未满足原平台最小人数与后续成员要求；新Q不产生足够平台证据。均值、低尾、波动和失败率需更新，停止人数不因此得出。','natural/CHECKS.json|natural/REPORT_ZH.md')
    add('N04','小池无门槛起点诊断','条件变化','uNb有两格不要求后续观察门槛的诊断起点4→3，但正式平台onset仍为空。这是诊断统计变化，不能解释为正式平台提前。','natural/REPORT_ZH.md|natural/CHECKS.json')
    add('T01','旧角色进入策略','幅度变化','仅x8-08的n28、new16、structure_dominant_first一条前缀受影响。pooled32后段图等权Q差−0.776979→−0.778220，建筑等权−1.078062→−1.082493；点估计和区间的方向判定保持，早段/全队无变化。','policy/LATE_GLOBAL_COMPARISON.csv|policy/REPORT_ZH.md')
    add('T02','新DSTRUCT进入策略','尚不能判断','命中的策略属于旧角色设计，不是当前DSTRUCT新策略验证；本轮不开展新大池策略或新同房ABC。','policy/CHECKS.json|dependencies/INDIRECT_DEPENDENCIES.csv','different_experiment')
    add('I01','RFUSE训练特征与标签','保持','读取28,312个既有RFUSE训练端点，与57个精确团队键交集为0。DSTRUCT、历史Q选人、JOINT原答画像及图片难度也无输入变化；固定标签，不重新拟合或选型。','dependencies/RFUSE_EXACT_TRAINING_INTERSECTION.csv|dependencies/INDIRECT_DEPENDENCIES.csv','no_actual_dependency')
    add('I02','原标注劳动','保持','原每条记录时间及来源签名不变；Q条件支持扩展后，条件时间汇总可改变。原作答劳动与新增人工排序劳动分开记录。','half_qonly/QUALITY_CONDITIONED_ANNOTATION_LABOR.csv|dependencies/INDIRECT_DEPENDENCIES.csv','conditional_support_only')
    add('I03','含人工的总成本效益','尚不能判断','人工排序和候选坐标修正没有耗时记录；保存时间戳不是劳动时长，不能设人工时间为0，不能计算完整人工辅助成本收益。','dependencies/INDIRECT_DEPENDENCIES.csv|endpoints/ENDPOINT_SCORES.csv','unmeasured_labor')
    add('I04','门洞、OOS及GT','保持','当前门洞、OOS独立路径和GT参考无本批实际依赖；不扩派人工队列、不改参考、不新增筛除。连接成功不证明参考物理正确，也不取消表示和OOS边界。','dependencies/UNHIT_CURRENT_MODULES.csv|preprocessing_audit/REPORT_ZH.md','no_actual_dependency')
    add('I05','原共同支持与推断边界','保持','原自动结果和分母全部保留；原已评分端点值不变，各模块原指标共同支持统计复现通过。新增可评结果进入扩展支持后才出现均值、区间或最佳候选变化。57定向案例不估计全部无环可修复率。','half_qonly/CHECKS.json|composition/CHECKS.json|same_room/ORIGINAL_COMMON_SUPPORT_PARITY.csv','original_support_invariance')
    add('I06','预测、选队与完整停止路径','保持','同房预测及选队历史读取固定原答质量/劳动；完整停止曲线虽读取融合Q，但其124924行、60129唯一团队、43池与57队交集仍为0。不能仅凭1534行参考补丁表判断全停止依赖；完整来源核查后无需重算。','dependencies/INDIRECT_PREDICTION_STOP_AUDIT.md|dependencies/INDIRECT_PREDICTION_STOP_AUDIT.csv','no_actual_dependency')
    with (OUT/'CONCLUSION_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    module_to_report={'ac_registered':'ac','changed_alliances':'alliances','composition_other':'composition',
                      'current_half':'half_qonly','q_only':'half_qonly','current_same_room_half':'same_room',
                      'same_room_large_registered':'same_room','legacy_role_policy':'policy',
                      'natural_ordinary_manual_extra_target':'natural'}
    with (OUT/'dependencies/MODULE_REFERENCE_SCOPE.csv').open(encoding='utf-8-sig') as f:
        matrix=list(csv.DictReader(f))
    for r in matrix:
        folder=module_to_report[r['module']]
        r.update(result_directory=folder,report=f'{folder}/REPORT_ZH.md',status='targeted_reaggregation_complete',
                 automatic_preserved=True,original_common_scored_values_changed=False,
                 classification_refit=False,coordinates_changed_in_main=False,
                 source_reference_scope='exact_team_key + reference + existing_current_gate')
    with (OUT/'MODULE_IMPACT_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
    input_paths=[OUT.parent/'missing_ring_review_20261104/user_order_return'/name for name in
                 ['PRO_PROMPT_ZH.md','README.md','IMPORT_RECEIPT.json','VALIDATED_ENDPOINT_ORDERS.csv.gz','AFFECTED_CURRENT_REFERENCES.csv.gz','IMPACT_BY_MODULE.csv']]
    inputs=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in input_paths]
    with gzip.open(OUT/'endpoints/ENDPOINTS.jsonl.gz','rt') as f: endpoints=[json.loads(x) for x in f]
    contract=dict(source_repository='https://github.com/Sparkling-Flames/3D_Manhattan_label',source_commit=BASE_COMMIT,
                  study_id='manual_order_impact_20261104',release='v2.1',
                  primary_analysis='v21_targeted_manual_order_assisted_20261104_v1',
                  automatic_method='original_MV50_gap7.5_source_ring',
                  assisted_method='same_selected_nodes_votes_coordinates_team_reference_formula + confirmed_manual_order',
                  method_relation='separate_targeted_human_assisted_sensitivity',
                  manual_coordinate_candidate='separate_not_adopted_F2_F9_x438.8037',
                  main_coordinates_unchanged=True,classification_labels_frozen=True,classification_refit=False,
                  endpoint_identities=len(endpoints),images=len(set(e['image'] for e in endpoints)),
                  conclusion_rows=len(rows),
                  fixed_nodes=sum(len(e['fixed_nodes']) for e in endpoints),main_complete_evaluable=sum(bool(e['complete_evaluable']) for e in endpoints),
                  original_missing_Q=57,original_Q_zero_imputation=False,current_reference_rows=536,
                  human_order_seconds=None,human_coordinate_candidate_seconds=None,
                  source_inputs=inputs)
    (OUT/'VERSION.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'conclusions':len(rows),'modules':len(matrix),'fixed_nodes':contract['fixed_nodes'],'scored':contract['main_complete_evaluable']},ensure_ascii=False))


if __name__=='__main__':main()
