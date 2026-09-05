"""Plot historical replay on fixed image support; no population plateau claim."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'analysis_results/annotation_research_decision_audit_20260905_v1'
METRICS = {'full_status_recovery_rate': '恢复已观察全体的结构状态',
           'same_second_mode_recovery_rate_all_tasks': '恢复同一少数模式（有可比较模式的图）'}


def fixed_series(rows, field):
    groups = defaultdict(list)
    for row in rows:
        if str(row['evaluable']).lower() == 'true':
            groups[(row['stage'], row['condition'])].append(row)
    result = []
    for (stage, condition), group in sorted(groups.items()):
        support = {r['base_task_id'] for r in group if int(r['k']) == 20}
        if not support:
            continue
        buildings = {r['building_id'] for r in group if r['base_task_id'] in support}
        values = []
        for k in range(15, 21):
            usable = [r for r in group if r['base_task_id'] in support and int(r['k']) == k]
            if len(usable) != len(support) or {r['base_task_id'] for r in usable} != support:
                raise ValueError(f'nonconstant or duplicated support: {stage}/{condition}, k={k}')
            scores = [float(r[field]) for r in usable]
            if not all(0 <= score <= 1 for score in scores):
                raise ValueError(f'invalid rate: {field}')
            per_building = [mean(float(r[field]) for r in usable if r['building_id'] == b) for b in buildings]
            values.append({'k': k, 'image_equal': mean(scores), 'building_equal': mean(per_building)})
        result.append({'stage': stage, 'condition': condition, 'image_count': len(support),
                       'building_count': len(buildings), 'image_ids': sorted(support), 'values': values})
    return result


def main():
    source = OUTPUT / 'data_audit/full_high_support_k15_20_task.csv'
    with source.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    font = Path('C:/Windows/Fonts/msyh.ttc')
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family': font_manager.FontProperties(fname=font).get_name(),
                         'font.size': 11, 'axes.unicode_minus': False})
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    fig.suptitle('15–20 人：不同历史条件下的有限样本恢复', fontsize=18, y=.96)
    qa = {'source': source.as_posix(), 'support': 'fixed within each stage/condition at k20',
          'old_eligibility_filter': False, 'population_confidence_interval': 'not_computed', 'series': {}}
    names = {'manual': 'Manual', 'semi': '机标人校', 'oos': '历史 OOS'}
    for axis, (field, title) in zip(axes, METRICS.items()):
        metric_rows = rows if field == 'full_status_recovery_rate' else [
            row for row in rows if str(row.get('same_second_mode_evaluable')).lower() == 'true']
        series = fixed_series(metric_rows, field)
        qa['series'][field] = series
        group_order = sorted({(row['stage'], row['condition']) for row in rows})
        for group in series:
            color = f'C{group_order.index((group["stage"], group["condition"])) % 10}'
            label = f"{group['stage']} {names[group['condition']]}：{group['image_count']} 图 / {group['building_count']} 建筑"
            axis.plot(range(15, 21), [r['image_equal'] for r in group['values']], 'o-', color=color, label=label)
            axis.plot(range(15, 21), [r['building_equal'] for r in group['values']], '--', color=color, alpha=.8)
        axis.set(title=title, xlabel='每个图像单元的标注人数 k', ylabel='恢复率', ylim=(-.02, 1.03), xticks=range(15, 21))
        axis.grid(alpha=.2)
        axis.spines[['top', 'right']].set_visible(False)
        axis.legend(loc='upper center', bbox_to_anchor=(.5, -.20), ncol=2, frameon=False, fontsize=9)
    fig.text(.5, .025, '实线：图像等权；虚线：建筑等权。各条件固定 k20 可支持图集；恢复既有全体不等于质量上限。\n'
             '右图仅含全体第二模式至少两票的图，图数另列；该模式不代表真值。Semi 可能共享初始化。\n'
             'OOS 保留历史条件名称。曲线为描述性重放，不含总体置信区间。', ha='center', fontsize=10)
    fig.subplots_adjust(top=.84, bottom=.30, wspace=.23)
    target = OUTPUT / 'historical_k15_20_sensitivity.png'
    fig.savefig(target, dpi=180, facecolor='white')
    plt.close(fig)
    (OUTPUT / 'PLOT_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
