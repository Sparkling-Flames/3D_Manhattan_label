"""Reference prior method comparisons without repeating completed experiments."""
from pathlib import Path
import pandas as pd
from compare_saved_exchanges import HERE,ROOT,save


def main():
    old=ROOT/"research/workers/personnel_effective_exchange_conditions_20261022"
    base=ROOT/"research/workers/personnel_mixture_audit_20261022"
    rows=[
        ("F01","manual","完整高Q人群n12配比、时间用途",base/"F01_RECOMPUTED_CONFIGURATIONS.csv","37个完整可行配比；不是四套主分类的替代；与log时间变幅不直接排名"),
        ("F01","manual","配比质量—时间方向与难度",base/"F01_RECOMPUTED_CONTRASTS.csv","已核旧结果；本轮不重复融合或重做快慢枚举"),
        ("M_structure / A2_relation","manual","既有扩大块条件与正反方向",old/"source_archive_20261022/expanded_blocks/analysis/FINAL_READABLE_CONDITIONS.csv.gz","保留n10/m5与m6、n17/m9等具体支持；新n20父内表不覆盖它们"),
        ("M_structure / QTD / A2 / SP","separate_manual_semi","本轮旧n20完整父内×m/r续接",HERE/"legacy_n20/PARENT_FIXED_M_RESPONSE.csv","271331实际事件已读；76条件；与纯类strict ABC分开"),
        ("MV_QTD_manual_new","manual","旧QTD慢类增减时间方向",ROOT/"research/workers/personnel_composition_n20_20261021/matched_n20/checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv","875实际方向事件已核结果沿用；QTD中的域含义保持原记录"),
        ("XCOND_GEOM_QT / XCOND_PAIRED / V3_JOINT_QT","manual","原共同A/D/n/m/r支持的三方法比较",old/"joint_exchange/CROSS_MANUAL_SAME_SUPPORT_SUMMARY.csv","历史共同锚点全/新批域分开；复用负向与效率取舍，不再重训或重复G5"),
        ("XCOND_GEOM_QT / XCOND_PAIRED / V3_JOINT_QT","semi","原共同A/D/n/m/r支持的三方法比较",old/"joint_exchange/CROSS_SEMI_SAME_SUPPORT_SUMMARY.csv","Manual+Semi可共建标签；Semi效果独立，不混两条件终点"),
        ("Rnew2 / F01 / A2 / SP / QTD / old M","separate_manual_semi","各旧方法身份与采用用途",ROOT/"research/workers/personnel_exchange_adoption_followup_20261022/integration/分类方案_采用总表.csv","保留已有关系、联合历史、结构/尺度/效率结果，不拼统一层级；本轮无全面重搜"),
    ]
    result=[]
    for method,condition,use,path,note in rows:
        result.append(dict(method=method,evaluation_condition=condition,use=use,source_file=str(path.relative_to(ROOT)),
                           file_exists=path.exists(),stage="historical_reuse" if "legacy_n20" not in str(path) else "new_reaggregation_of_historical_events",note=note))
    save(pd.DataFrame(result),"HISTORICAL_METHOD_COMPARISON_INDEX.csv")
    common=[]
    for condition in ["MANUAL","SEMI"]:
        p=old/f"joint_exchange/CROSS_{condition}_SAME_SUPPORT_SUMMARY.csv"
        d=pd.read_csv(p);d.insert(0,"source_file",str(p.relative_to(ROOT)))
        d.insert(1,"evidence_stage","prior_cross_condition_shared_anchor_comparison_reused_without_recalculation")
        common.append(d)
    save(pd.concat(common,ignore_index=True),"REUSED_CROSS_CONDITION_SAME_SUPPORT.csv")
    assert pd.DataFrame(result).file_exists.all(),"An index reference is missing"


if __name__=="__main__":main()
