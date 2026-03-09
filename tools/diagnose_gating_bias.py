#!/usr/bin/env python3
"""
快速诊断脚本：评估n_pairs_mismatch门控的Selection Bias风险

Usage:
    python diagnose_gating_bias.py --csv path/to/quality_report.csv
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path


def _pick_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    for name in candidates:
        if name in columns:
            return name
    return None


def _to_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    if pd.api.types.is_numeric_dtype(s):
        return s.fillna(0).astype(int).astype(bool)
    # common CSV patterns: True/False, true/false, 1/0, yes/no
    mapped = (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
                "y": True,
                "n": False,
                "nan": False,
                "none": False,
                "": False,
            }
        )
    )
    return mapped.fillna(False)


def diagnose_gating_bias(csv_path: str, verbose: bool = True):
    """诊断门控逻辑造成的selection bias"""
    
    df = pd.read_csv(csv_path)
    
    columns = list(df.columns)
    col_scope_missing = _pick_first_existing(columns, ["scope_missing", "scope_missing_clean"])
    col_is_oos = _pick_first_existing(columns, ["is_oos", "is_oos_clean"])
    col_layout_used = _pick_first_existing(columns, ["layout_used_clean", "layout_used"])
    col_gate_reason = _pick_first_existing(columns, ["layout_gate_reason", "gate_reason", "layout_gate_reason_clean"])
    col_condition = _pick_first_existing(columns, ["condition_clean", "condition"])

    # 基础统计
    n_total = len(df)

    if col_is_oos is None:
        is_oos = pd.Series(False, index=df.index)
    else:
        is_oos = _to_bool_series(df[col_is_oos])

    if col_scope_missing is not None:
        scope_missing = _to_bool_series(df[col_scope_missing])
    elif "scope" in df.columns:
        scope_missing = df["scope"].isna() | (df["scope"].astype(str).str.strip() == "")
    else:
        scope_missing = pd.Series(False, index=df.index)

    mask_inscope = (~scope_missing) & (~is_oos)
    df_inscope = df.loc[mask_inscope].copy()
    n_inscope = len(df_inscope)
    
    if verbose:
        print("=" * 70)
        print("🔍 Selection Bias 诊断报告")
        print("=" * 70)
        print(f"\n总样本数: {n_total}")
        print(f"In-scope样本数: {n_inscope} ({100*n_inscope/n_total:.1f}%)")
    
    # 1. 覆盖率分析
    if col_layout_used is None:
        layout_used = pd.Series(False, index=df_inscope.index)
    else:
        layout_used = _to_bool_series(df_inscope[col_layout_used]).fillna(False)
    n_layout_used = int(layout_used.sum())
    coverage = n_layout_used / n_inscope if n_inscope > 0 else 0
    
    if verbose:
        print(f"\n【覆盖率分析】")
        print(f"layout_used=True: {n_layout_used}/{n_inscope} ({100*coverage:.1f}%)")
        print(f"⚠️  有 {n_inscope - n_layout_used} 个样本被排除主分析")
    
    # 2. 门控原因分布
    df_gated = df_inscope.loc[~layout_used]
    if len(df_gated) > 0:
        if col_gate_reason is None:
            gate_reasons = pd.Series(dtype=int)
        else:
            gate_reasons = df_gated[col_gate_reason].value_counts()
        mismatch_count = gate_reasons.get('n_pairs_mismatch', 0)
        mismatch_rate = mismatch_count / len(df_gated) if len(df_gated) > 0 else 0
        mismatch_rate_inscope = mismatch_count / n_inscope if n_inscope > 0 else 0
        
        if verbose:
            print(f"\n【门控原因分布】")
            for reason, count in gate_reasons.items():
                pct = 100 * count / len(df_gated)
                marker = "🔴" if reason == 'n_pairs_mismatch' else "  "
                print(f"{marker} {reason}: {count} ({pct:.1f}%)")

            print(
                f"\n(mismatch比例) gated内={100*mismatch_rate:.1f}% | inscope内={100*mismatch_rate_inscope:.1f}%"
            )
            
            if mismatch_rate > 0.3:
                print(f"\n⚠️  WARNING: {mismatch_rate:.1%} 的失败是 n_pairs_mismatch")
                print("   这意味着大量'强纠错'样本被系统性排除！")
    
    # 3. mismatch样本特征
    if 'pred_n_pairs' in df.columns and 'ann_n_pairs' in df.columns and col_gate_reason is not None:
        df_mismatch = df_inscope[df_inscope[col_gate_reason] == 'n_pairs_mismatch'].copy()
        if len(df_mismatch) > 0:
            df_mismatch['delta_n'] = abs(df_mismatch['pred_n_pairs'] - df_mismatch['ann_n_pairs'])
            
            if verbose:
                print(f"\n【mismatch样本特征】")
                print(f"样本数: {len(df_mismatch)}")
                print(f"平均Δn_pairs: {df_mismatch['delta_n'].mean():.2f}")
                print(f"Δn分布: {dict(df_mismatch['delta_n'].value_counts().head(5))}")
                
                if 'active_time' in df_mismatch.columns:
                    time_mismatch = df_mismatch['active_time'].median()
                    time_matched = df_inscope.loc[layout_used, 'active_time'].median()
                    print(f"耗时对比: mismatch={time_mismatch:.0f}s vs matched={time_matched:.0f}s")
                    print(f"🔴 mismatch样本耗时更长 → 这是'高工作量'样本！")
    
    # 4. 按condition分层
    if col_condition is not None:
        if verbose:
            print(f"\n【按condition分层覆盖率】")
        
        for cond in df_inscope[col_condition].unique():
            if pd.isna(cond):
                continue
            df_cond = df_inscope[df_inscope[col_condition] == cond]
            cov = float(layout_used.loc[df_cond.index].mean()) if len(df_cond) > 0 else 0.0
            if col_gate_reason is None:
                mismatch_rate_cond = 0.0
            else:
                mismatch_rate_cond = float((df_cond[col_gate_reason] == 'n_pairs_mismatch').mean())
            
            if verbose:
                marker = "🔴" if cov < 0.7 else "✅"
                print(f"{marker} {cond}: coverage={100*cov:.1f}%, mismatch={100*mismatch_rate_cond:.1f}%")
    
    # 5. 按annotator分层
    if 'annotator_id' in df.columns:
        if verbose:
            print(f"\n【按annotator分层覆盖率】")
        
        annotator_stats = []
        for uid in df_inscope['annotator_id'].unique():
            df_user = df_inscope[df_inscope['annotator_id'] == uid]
            cov = float(layout_used.loc[df_user.index].mean()) if len(df_user) > 0 else 0.0
            n_tasks = len(df_user)
            annotator_stats.append({
                'annotator': uid,
                'n_tasks': n_tasks,
                'coverage': cov
            })
        
        annotator_stats = sorted(annotator_stats, key=lambda x: x['coverage'])
        
        if verbose:
            for stat in annotator_stats:
                marker = "🔴" if stat['coverage'] < 0.7 else "✅"
                print(f"{marker} {stat['annotator']}: {stat['n_tasks']}任务, coverage={100*stat['coverage']:.1f}%")
    
    # 6. 风险评估
    risk_score = 0
    risk_factors = []
    
    if coverage < 0.7:
        risk_score += 3
        risk_factors.append(f"低覆盖率 ({100*coverage:.1f}%)")
    
    if mismatch_rate > 0.3:
        risk_score += 3
        risk_factors.append(f"高mismatch比例 ({100*mismatch_rate:.1f}%)")
    
    if col_condition is not None:
        semi_mask = df_inscope[col_condition] == 'semi'
        if semi_mask.any():
            semi_cov = float(layout_used.loc[semi_mask.index[semi_mask]].mean())
            if semi_cov < 0.6:
                risk_score += 2
                risk_factors.append(f"Semi条件低覆盖 ({100*semi_cov:.1f}%)")
    
    if verbose:
        print(f"\n{'=' * 70}")
        print(f"【Selection Bias 风险评分】: {risk_score}/8")
        
        if risk_score >= 5:
            level = "🔴 HIGH RISK - 论文会被reject"
        elif risk_score >= 3:
            level = "🟡 MEDIUM RISK - 审稿人会质疑"
        else:
            level = "🟢 LOW RISK - 可接受"
        
        print(f"风险等级: {level}")
        if risk_factors:
            print(f"风险因素:")
            for factor in risk_factors:
                print(f"  - {factor}")
        
        print(f"\n{'=' * 70}")
        print("📋 建议行动:")
        print("  1. 立即实施双口径报告（见 docs/GATING_ANALYSIS_PLAN.md 方案1）")
        print("  2. 在论文中报告覆盖率与失败原因分布（方案2）")
        print("  3. 进行敏感性分析（方案4）")
        print("=" * 70)
    
    return {
        'n_total': n_total,
        'n_inscope': n_inscope,
        'n_layout_used': n_layout_used,
        'coverage': coverage,
        'mismatch_rate': mismatch_rate if len(df_gated) > 0 else 0,
        'risk_score': risk_score,
        'risk_level': 'HIGH' if risk_score >= 5 else ('MEDIUM' if risk_score >= 3 else 'LOW')
    }


def main():
    parser = argparse.ArgumentParser(description='诊断门控逻辑的Selection Bias风险')
    parser.add_argument('--csv', type=str, required=True, help='quality_report CSV路径')
    parser.add_argument('--quiet', action='store_true', help='只输出风险评分')
    args = parser.parse_args()
    
    if not Path(args.csv).exists():
        print(f"错误: 文件不存在 {args.csv}")
        return
    
    result = diagnose_gating_bias(args.csv, verbose=not args.quiet)
    
    if args.quiet:
        print(f"Risk Score: {result['risk_score']}/8 ({result['risk_level']})")


if __name__ == '__main__':
    main()
