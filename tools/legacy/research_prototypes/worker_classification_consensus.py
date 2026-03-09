"""
Worker Classification and Weighted Consensus Experiment
======================================================
融合文献1+2的核心创新：
1. 对workers进行分类（Reliable/Normal/Sloppy/Unreliable）
2. 实现加权共识，提高quality while 降低cost
3. 展示model_issue samples需要更多关注的证据

用户：葛佳玮 (Gareth)
日期：2026-02-08
"""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']

class WorkerClassificationAnalysis:
    """基于现有数据的worker分类和加权共识分析"""
    
    def __init__(self, data_path):
        self.df = pd.read_csv(data_path)
        self.workers = []
        self.worker_classes = {}
        self.results = {}
        
    def step1_identify_workers_and_reliability(self):
        """Step1: 从现有数据中识别workers并计算可靠度r_u"""
        print("=" * 80)
        print("STEP 1: Worker Identification and Reliability Estimation")
        print("=" * 80)
        
        # 假设有iou_to_consensus_loo列
        if 'iou_to_consensus_loo' not in self.df.columns:
            print("[WARNING] iou_to_consensus_loo not found, using alternative metric")
            # 备选方案：用iou_to_others_median
            reliability_col = 'iou_to_others_median'
        else:
            reliability_col = 'iou_to_consensus_loo'
        
        # 按annotator_id分组计算
        worker_stats = self.df.groupby('annotator_id').agg({
            reliability_col: ['mean', 'median', 'std', 'count'],
            'iou': ['mean', 'median']
        }).round(4)
        
        print("\nWorker Statistics:")
        print(worker_stats)
        
        # 计算每个worker的r_u（reliability）
        self.worker_reliability = self.df.groupby('annotator_id')[reliability_col].median()
        print("\nWorker Reliability (r_u = median consensus agreement):")
        for worker, r_u in self.worker_reliability.items():
            print(f"  Worker {worker}: r_u = {r_u:.4f}")
        
        self.results['worker_reliability'] = self.worker_reliability
        return self.worker_reliability
    
    def step2_classify_workers(self, thresholds=None):
        """Step2: 按可靠度分类workers"""
        print("\n" + "=" * 80)
        print("STEP 2: Worker Classification")
        print("=" * 80)
        
        if thresholds is None:
            # 默认阈值（基于文献2清华论文的做法）
            thresholds = {
                'reliable': 0.85,      # r_u > 0.85
                'normal': 0.70,        # 0.70 < r_u <= 0.85
                'sloppy': 0.50,        # 0.50 < r_u <= 0.70
                # < 0.50: unreliable
            }
        
        print(f"\nClassification Thresholds:")
        print(f"  Reliable: r_u > {thresholds['reliable']}")
        print(f"  Normal: {thresholds['normal']} < r_u <= {thresholds['reliable']}")
        print(f"  Sloppy: {thresholds['sloppy']} < r_u <= {thresholds['normal']}")
        print(f"  Unreliable: r_u <= {thresholds['sloppy']}")
        
        self.worker_classes = {}
        for worker_id, r_u in self.worker_reliability.items():
            if r_u > thresholds['reliable']:
                cls = 'Reliable'
            elif r_u > thresholds['normal']:
                cls = 'Normal'
            elif r_u > thresholds['sloppy']:
                cls = 'Sloppy'
            else:
                cls = 'Unreliable'
            
            self.worker_classes[worker_id] = {
                'class': cls,
                'r_u': r_u
            }
            print(f"  Worker {worker_id}: {cls} (r_u={r_u:.4f})")
        
        self.results['worker_classes'] = self.worker_classes
        return self.worker_classes
    
    def step3_define_weights(self, weight_scheme=None):
        """Step3: 定义权重方案（可固定或可学习）"""
        print("\n" + "=" * 80)
        print("STEP 3: Weight Definition")
        print("=" * 80)
        
        if weight_scheme is None:
            # 默认权重方案（基于文献2的启发）
            weight_scheme = {
                'Reliable': 1.0,
                'Normal': 0.7,
                'Sloppy': 0.3,
                'Unreliable': 0.0
            }
        
        print(f"\nWeight Scheme:")
        for cls, w in weight_scheme.items():
            print(f"  {cls}: w = {w}")
        
        # 计算每个worker的权重
        self.worker_weights = {}
        for worker_id, info in self.worker_classes.items():
            self.worker_weights[worker_id] = weight_scheme[info['class']]
        
        print(f"\nComputed Weights:")
        for worker_id, w in self.worker_weights.items():
            print(f"  Worker {worker_id}: weight = {w}")
        
        self.results['weight_scheme'] = weight_scheme
        self.results['worker_weights'] = self.worker_weights
        return self.worker_weights
    
    def step4_compute_weighted_consensus(self):
        """Step4: 计算加权共识，与原始共识对比"""
        print("\n" + "=" * 80)
        print("STEP 4: Compute Weighted vs Unweighted Consensus")
        print("=" * 80)
        
        # 获取所有有效的IoU列
        iou_cols = [col for col in self.df.columns if 'iou' in col.lower() and 'consensus' in col.lower()]
        if not iou_cols:
            print("[WARNING] No consensus IoU found, using raw iou")
            metric_col = 'iou'
        else:
            metric_col = iou_cols[0]  # 通常是iou_to_consensus_loo
        
        print(f"\nUsing metric column: {metric_col}")
        
        # 简化：为了演示，我们假设有多个标注者的数据
        # 在实际数据中，可能需要pivot操作
        
        # 按task分组，计算每个task的共识
        results = []
        
        for task_id, task_data in self.df.groupby('task_id'):
            if len(task_data) < 2:
                continue  # 跳过只有1个标注的样本
            
            # 原始共识（无权重）
            iou_values = task_data['iou'].values
            raw_consensus = np.median(iou_values)
            
            # 加权共识
            weights = []
            weighted_ious = []
            for _, row in task_data.iterrows():
                worker_id = row['annotator_id']
                w = self.worker_weights.get(worker_id, 1.0)
                weights.append(w)
                weighted_ious.append(row['iou'] * w)
            
            sum_weights = sum(weights)
            if sum_weights > 0:
                weighted_consensus = np.sum(weighted_ious) / sum_weights
            else:
                weighted_consensus = raw_consensus
            
            # 计算该task的model_issue信息（如果有）
            model_issue = task_data['model_issue'].iloc[0] if 'model_issue' in task_data.columns else None
            has_issue = pd.notna(model_issue) if model_issue is not None else False
            
            results.append({
                'task_id': task_id,
                'n_annotators': len(task_data),
                'raw_consensus': raw_consensus,
                'weighted_consensus': weighted_consensus,
                'improvement': weighted_consensus - raw_consensus,
                'has_model_issue': has_issue,
                'iou_values': iou_values.tolist(),
                'weights': weights
            })
        
        results_df = pd.DataFrame(results)
        
        print(f"\nConsensus Comparison (n={len(results_df)} tasks):")
        print(f"  Raw Consensus:     mean={results_df['raw_consensus'].mean():.4f}, median={results_df['raw_consensus'].median():.4f}")
        print(f"  Weighted Consensus:mean={results_df['weighted_consensus'].mean():.4f}, median={results_df['weighted_consensus'].median():.4f}")
        print(f"  Average Improvement: {results_df['improvement'].mean():.4f}")
        
        # T检验
        t_stat, p_val = stats.ttest_rel(results_df['weighted_consensus'], results_df['raw_consensus'])
        print(f"  Paired t-test: t={t_stat:.4f}, p={p_val:.4f} {'***显著' if p_val < 0.05 else '不显著'}")
        
        self.results['consensus_comparison'] = results_df
        return results_df
    
    def step5_analyze_by_model_issue(self):
        """Step5: 分析weighted consensus对model_issue样本的帮助"""
        print("\n" + "=" * 80)
        print("STEP 5: Analysis by Model Issue Status")
        print("=" * 80)
        
        if 'consensus_comparison' not in self.results:
            print("[ERROR] Run step4 first")
            return
        
        results_df = self.results['consensus_comparison']
        
        # 按model_issue分组
        has_issue = results_df[results_df['has_model_issue'] == True]
        no_issue = results_df[results_df['has_model_issue'] == False]
        
        print(f"\nWithout Model Issue (n={len(no_issue)}):")
        print(f"  Raw Consensus:     mean={no_issue['raw_consensus'].mean():.4f}")
        print(f"  Weighted Consensus:mean={no_issue['weighted_consensus'].mean():.4f}")
        print(f"  Improvement: {(no_issue['weighted_consensus'] - no_issue['raw_consensus']).mean():.4f}")
        
        print(f"\nWith Model Issue (n={len(has_issue)}):")
        print(f"  Raw Consensus:     mean={has_issue['raw_consensus'].mean():.4f}")
        print(f"  Weighted Consensus:mean={has_issue['weighted_consensus'].mean():.4f}")
        print(f"  Improvement: {(has_issue['weighted_consensus'] - has_issue['raw_consensus']).mean():.4f}")
        
        # 对比两组improvement的差异
        if len(has_issue) > 0 and len(no_issue) > 0:
            t_stat, p_val = stats.ttest_ind(
                has_issue['weighted_consensus'] - has_issue['raw_consensus'],
                no_issue['weighted_consensus'] - no_issue['raw_consensus']
            )
            print(f"\nImprovement Difference Test: t={t_stat:.4f}, p={p_val:.4f}")
    
    def visualize_worker_reliability(self, save_path=None):
        """可视化worker可靠度和分类"""
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        
        # 图1: Worker可靠度
        worker_ids = sorted(self.worker_reliability.index)
        r_us = [self.worker_reliability[w] for w in worker_ids]
        classes = [self.worker_classes[w]['class'] for w in worker_ids]
        
        colors = {
            'Reliable': '#2ecc71',
            'Normal': '#f39c12', 
            'Sloppy': '#e74c3c',
            'Unreliable': '#c0392b'
        }
        
        worker_colors = [colors[c] for c in classes]
        axes[0].bar(range(len(worker_ids)), r_us, color=worker_colors)
        axes[0].axhline(y=0.85, color='r', linestyle='--', label='Reliable Threshold')
        axes[0].axhline(y=0.70, color='orange', linestyle='--', label='Normal/Sloppy Threshold')
        axes[0].set_xlabel('Worker ID')
        axes[0].set_ylabel('Reliability (r_u)')
        axes[0].set_xticks(range(len(worker_ids)))
        axes[0].set_xticklabels([f'W{w}' for w in worker_ids])
        axes[0].set_title('Worker Reliability Distribution')
        axes[0].legend()
        axes[0].grid(axis='y', alpha=0.3)
        
        # 图2: Worker分类
        class_counts = pd.Series([c['class'] for c in self.worker_classes.values()]).value_counts()
        class_order = ['Reliable', 'Normal', 'Sloppy', 'Unreliable']
        class_counts = class_counts.reindex(class_order, fill_value=0)
        
        axes[1].bar(class_counts.index, class_counts.values, color=[colors[c] for c in class_counts.index])
        axes[1].set_ylabel('Count')
        axes[1].set_title('Worker Classification Distribution')
        axes[1].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"[Saved] {save_path}")
        else:
            plt.show()
        
        return fig
    
    def generate_report(self):
        """生成完整报告"""
        print("\n" + "=" * 80)
        print("FINAL REPORT")
        print("=" * 80)
        
        print("\n[Summary]")
        print(f"Total Workers: {len(self.worker_classes)}")
        
        class_dist = {}
        for info in self.worker_classes.values():
            cls = info['class']
            class_dist[cls] = class_dist.get(cls, 0) + 1
        
        for cls in ['Reliable', 'Normal', 'Sloppy', 'Unreliable']:
            if cls in class_dist:
                print(f"  {cls}: {class_dist[cls]}")
        
        if 'consensus_comparison' in self.results:
            df = self.results['consensus_comparison']
            improvement = (df['weighted_consensus'] - df['raw_consensus']).mean()
            print(f"\n[Improvement]")
            print(f"  Average Consensus Improvement: {improvement:+.4f}")
            
            if improvement > 0:
                print(f"  → Weighted consensus achieves {improvement:.1%} better agreement")
            else:
                print(f"  → No improvement found (consider alternative weight schemes)")
        
        print("\n[Recommendations for Paper]")
        print("1. Title: 'Worker-Aware Consensus Estimation for Cost-Effective Annotation'")
        print("2. Novelty: Combine worker classification + weighted consensus + model_issue routing")
        print("3. Experiments: Compare unweighted vs weighted vs per-worker average")
        print("4. Ablation: Show improvement from removing spammer weights")


if __name__ == "__main__":
    # 使用示例
    data_path = "d:\\Work\\HOHONET\\analysis_results\\quality_report_20260126.csv"
    
    analyzer = WorkerClassificationAnalysis(data_path)
    
    # 执行分析流程
    print("\n【基于现有数据的Worker分类和加权共识分析】\n")
    
    # Step 1: 计算worker可靠度
    analyzer.step1_identify_workers_and_reliability()
    
    # Step 2: 分类workers
    analyzer.step2_classify_workers()
    
    # Step 3: 定义权重
    analyzer.step3_define_weights()
    
    # Step 4: 计算加权共识
    analyzer.step4_compute_weighted_consensus()
    
    # Step 5: 按model_issue分析
    analyzer.step5_analyze_by_model_issue()
    
    # 可视化
    analyzer.visualize_worker_reliability(
        save_path="d:\\Work\\HOHONET\\paper_figures\\worker_classification.png"
    )
    
    # 生成报告
    analyzer.generate_report()
    
    print("\n[Done] Analysis complete!")
