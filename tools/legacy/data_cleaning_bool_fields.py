"""
数据清洗代码：布尔字段与 scope/difficulty/model_issue 标准化处理

基于实际 CSV 输出（analyze_quality.py 生成）的字段值，而非 XML 的 choice value。
适用于 notebook 或脚本直接调用。

用法示例：
    import pandas as pd
    from data_cleaning_bool_fields import clean_quality_report
    
    df = pd.read_csv("analysis_results/quality_report_20260117.csv")
    df_clean = clean_quality_report(df)
    df_main = df_clean[df_clean["data_valid_for_main"]].copy()
"""

import pandas as pd
import numpy as np


def clean_quality_report(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    清洗 quality_report CSV，派生标准化字段。
    
    关键原则：
    1. scope 缺失 → NA（不当 False）
    2. difficulty/model_issue 允许空（空=未选=False），但要记录填写率
    3. 门控字段缺失用 "unknown" 而非 NA
    4. 输出"主分析集"过滤标记
    
    Args:
        df: 原始 quality_report DataFrame
        verbose: 是否打印统计摘要
    
    Returns:
        清洗后的 DataFrame（原地修改 + 新增列）
    """
    df = df.copy()
    
    # ========================================
    # 1) task_id / annotator_id 转字符串
    # ========================================
    for col in ["task_id", "annotator_id"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    
    # ========================================
    # 2) scope 清洗（基于 CSV 实际值：alias）
    # ========================================
    def norm_scope(x):
        if pd.isna(x) or str(x).strip() == "":
            return np.nan
        return str(x).strip().lower()
    
    df["scope_clean"] = df["scope"].apply(norm_scope)
    df["scope_missing"] = df["scope_clean"].isna()
    
    # scope 实际值是 alias（normal, oos_*, complex, unknown 等）
    # 注意：XML 里 value 是中文+英文，但导出时用的是 alias
    def scope_is_oos(s):
        """判断 scope 是否为 OOS"""
        if pd.isna(s):
            return np.nan
        s = str(s).strip().lower()
        # OOS alias 前缀
        if s.startswith("oos_"):
            return True
        # 其他可能的 OOS 别名（根据 XML 配置）
        if s in ["oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"]:
            return True
        return False
    
    def scope_is_normal(s):
        """判断 scope 是否为 In-scope"""
        if pd.isna(s):
            return np.nan
        s = str(s).strip().lower()
        return s == "normal"
    
    df["is_oos_clean"] = df["scope_clean"].apply(scope_is_oos)
    df["is_normal_clean"] = df["scope_clean"].apply(scope_is_normal)
    
    # ========================================
    # 3) difficulty / model_issue 填写率
    # ========================================
    df["difficulty_reported"] = df["difficulty"].fillna("").str.strip().ne("")
    df["model_issue_reported"] = df["model_issue"].fillna("").str.strip().ne("")
    
    # model_issue 只对 semi 适用
    if "condition" in df.columns:
        df["model_issue_applicable"] = df["condition"].eq("semi")
    else:
        # 如果没有 condition 列，全部视为适用（保守）
        df["model_issue_applicable"] = True
    
    # ========================================
    # 4) 门控原因缺失修正
    # ========================================
    # layout_used=False 但 gate_reason 为空 → 填 "unknown_gate_reason"
    if "layout_used" in df.columns and "layout_gate_reason" in df.columns:
        mask_gate_missing = (
            df["layout_used"].eq(False) &
            df["layout_gate_reason"].fillna("").str.strip().eq("")
        )
        df.loc[mask_gate_missing, "layout_gate_reason"] = "unknown_gate_reason"
    
    # pointwise_gate_reason 同理
    if "pointwise_rmse_used" in df.columns and "pointwise_gate_reason" in df.columns:
        mask_pw_gate_missing = (
            df["pointwise_rmse_used"].eq(False) &
            df["pointwise_gate_reason"].fillna("").str.strip().eq("")
        )
        df.loc[mask_pw_gate_missing, "pointwise_gate_reason"] = "unknown_gate_reason"
    
    # ========================================
    # 5) 主分析集标记（供过滤用）
    # ========================================
    # 主分析：scope 不缺失 + In-scope + （可选）layout_used
    main_mask_base = (
        df["scope_missing"].eq(False) &
        df["is_oos_clean"].eq(False)
    )
    
    # 如果要求 layout 门控通过（更严格）
    if "layout_used" in df.columns:
        main_mask_strict = main_mask_base & df["layout_used"].eq(True)
        df["data_valid_for_main_strict"] = main_mask_strict
    else:
        df["data_valid_for_main_strict"] = main_mask_base
    
    # 基础版（不要求 layout 门控，只要求 In-scope）
    df["data_valid_for_main"] = main_mask_base
    
    # 一致性集标记（多标注 + In-scope + 有 LOO）
    if all(c in df.columns for c in ["consensus_uid_loo", "iou_to_consensus_loo"]):
        reliability_mask = (
            main_mask_base &
            df["consensus_uid_loo"].notna() &
            df["iou_to_consensus_loo"].notna()
        )
        df["data_valid_for_reliability"] = reliability_mask
    else:
        df["data_valid_for_reliability"] = False
    
    # ========================================
    # 6) 统计摘要（可选）
    # ========================================
    if verbose:
        print("=" * 60)
        print("数据清洗统计摘要")
        print("=" * 60)
        print(f"总样本数: {len(df)}")
        print(f"scope 缺失: {df['scope_missing'].sum()} ({df['scope_missing'].mean():.1%})")
        
        # OOS 比例（排除 scope 缺失）
        valid_scope = df[~df["scope_missing"]]
        if len(valid_scope) > 0:
            oos_rate = valid_scope["is_oos_clean"].sum() / len(valid_scope)
            print(f"OOS 比例 (scope 非空): {valid_scope['is_oos_clean'].sum()}/{len(valid_scope)} ({oos_rate:.1%})")
        
        # difficulty / model_issue 填写率
        print(f"difficulty 填写率: {df['difficulty_reported'].mean():.1%}")
        
        if "model_issue_applicable" in df.columns and df["model_issue_applicable"].sum() > 0:
            semi_rows = df[df["model_issue_applicable"]]
            mi_rate = semi_rows["model_issue_reported"].mean()
            print(f"model_issue 填写率 (仅 semi): {mi_rate:.1%}")
        
        # 主分析集与一致性集
        print(f"\n主分析集样本数 (In-scope + scope 非空): {df['data_valid_for_main'].sum()}")
        if "data_valid_for_main_strict" in df.columns:
            print(f"主分析集样本数 (严格：+ layout_used): {df['data_valid_for_main_strict'].sum()}")
        if "data_valid_for_reliability" in df.columns:
            print(f"一致性集样本数 (多标注 + LOO 可用): {df['data_valid_for_reliability'].sum()}")
        
        # scope 值分布（前 10）
        if not df["scope_missing"].all():
            print("\nscope 值分布 (Top 10):")
            scope_counts = df["scope_clean"].value_counts().head(10)
            for val, cnt in scope_counts.items():
                print(f"  {val}: {cnt}")
        
        print("=" * 60)
    
    return df


def export_filtered_subsets(df: pd.DataFrame, output_dir: str = "analysis_results"):
    """
    导出过滤后的子集 CSV（可选）
    
    Args:
        df: 已清洗的 DataFrame
        output_dir: 输出目录
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # 主分析集
    df_main = df[df["data_valid_for_main"]].copy()
    df_main.to_csv(f"{output_dir}/quality_report_main_inscope.csv", index=False)
    print(f"已导出主分析集: {len(df_main)} 行")
    
    # 一致性集
    if "data_valid_for_reliability" in df.columns:
        df_rel = df[df["data_valid_for_reliability"]].copy()
        if len(df_rel) > 0:
            df_rel.to_csv(f"{output_dir}/quality_report_reliability.csv", index=False)
            print(f"已导出一致性集: {len(df_rel)} 行")


# ========================================
# 示例用法（在 notebook 中运行）
# ========================================
if __name__ == "__main__":
    # 示例：直接运行此脚本
    df = pd.read_csv("../analysis_results/quality_report_20260117.csv")
    df_clean = clean_quality_report(df, verbose=True)
    
    # 导出过滤后的子集（可选）
    # export_filtered_subsets(df_clean)
    
    # 查看清洗后的前几行
    print("\n清洗后的 DataFrame 新增列:")
    new_cols = [
        "scope_clean", "scope_missing", "is_oos_clean", "is_normal_clean",
        "difficulty_reported", "model_issue_reported", "model_issue_applicable",
        "data_valid_for_main", "data_valid_for_reliability"
    ]
    print(df_clean[new_cols].head(10))
