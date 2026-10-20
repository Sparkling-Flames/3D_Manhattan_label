"""小范围问题：同图同参考内，少／多于参考的点数怎样对应质量？"""
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PAT = ROOT / 'research/workers/personnel_marking_patterns_20261020'
SAME = ROOT / 'research/same_room/same_room_multiview_20261020/structure_transfer'


def contrast(frame):
    rows = []
    for (image, ref), group in frame.groupby(['image_id', 'reference_id']):
        equal = group[group.delta == 0]
        for name, selected in [('less', group[group.delta < 0]),
                               ('extra', group[group.delta > 0])]:
            if len(equal) < 2 or len(selected) < 2:
                continue
            rows.append(dict(image_id=image, reference_id=ref, contrast=name,
                             building_id=group.building_id.iloc[0],
                             difficulty=group.difficulty.iloc[0],
                             n_selected=len(selected), n_equal=len(equal),
                             selected_workers='|'.join(sorted(selected.worker_id.unique())),
                             equal_workers='|'.join(sorted(equal.worker_id.unique())),
                             B8L2_delta=selected.B8L2.mean()-equal.B8L2.mean(),
                             D10_delta=selected.D10.mean()-equal.D10.mean()))
    return pd.DataFrame(rows)


def self_check():
    # 两组均需两人；同图的不同参考绝不互相凑分母。
    f = pd.DataFrame(dict(image_id=['i']*5, reference_id=['r']*4+['other'],
                          delta=[0, 0, -2, -2, 1], worker_id=list('abcde'),
                          building_id=['b']*5, difficulty=['hard']*5,
                          B8L2=[80, 100, 50, 70, 100], D10=[81, 101, 51, 71, 100]))
    result = contrast(f)
    assert len(result) == 1 and result.iloc[0].B8L2_delta == -30
    assert result.iloc[0].n_selected == 2


def main():
    self_check()
    source = ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    with gzip.open(source, 'rt', encoding='utf-8') as stream:
        records = json.load(stream)['records']
    by_id = {r['object_id']: r for r in records}
    assert len(by_id) == len(records)
    f = pd.read_csv(PAT / 'record_expression.csv')
    assert f.object_id.is_unique and set(f.object_id) <= by_id.keys()
    non_oos = [r for r in records if not r['is_oos']]
    assert set(f.object_id) == {r['object_id'] for r in non_oos}
    # 复用已有去重和坐标修复排除；评分与参考仍回读指定逐份真源。
    f = f[(f.personal_comparison == True) & (f.quality_usable == True)
          & (f.condition == 'manual') & (f.layer == 'ordinary')
          & (f.quality_use == 'ordinary_primary')].copy()
    assert not f.duplicated(['image_id', 'reference_id', 'worker_id']).any()
    for column in ['B8L2', 'D10']:
        f[column] = [by_id[o][column] for o in f.object_id]
    refs = [by_id[o]['reference_evidence'] for o in f.object_id]
    assert all(r and r.get('points_1024x512') for r in refs)
    assert all(by_id[o]['reference_id'] == ref for o, ref in zip(f.object_id, f.reference_id))
    f['reference_pairs'] = [len(r['points_1024x512'])/2 for r in refs]
    assert (f.reference_pairs >= 3).all() and f[['B8L2', 'D10']].notna().all().all()
    f['delta'] = f.pair_n-f.reference_pairs
    panels = contrast(f)
    panels.to_csv(OUT / 'detail_quality_panels.csv', index=False, encoding='utf-8-sig')
    # 先同图等权，再建筑等权；同图多参考不增加图片权重。
    image = panels.groupby(['contrast', 'difficulty', 'building_id', 'image_id'])[['B8L2_delta', 'D10_delta']].mean().reset_index()
    building = image.groupby(['contrast', 'building_id'])[['B8L2_delta', 'D10_delta']].mean().reset_index()
    building.to_csv(OUT / 'detail_quality_buildings.csv', index=False, encoding='utf-8-sig')
    stats = {}
    for name, g in panels.groupby('contrast'):
        workers = set('|'.join(g.selected_workers.tolist()+g.equal_workers.tolist()).split('|'))
        b = building[building.contrast == name]
        stats[name] = dict(target_panels=len(g), images=g.image_id.nunique(),
                           buildings=len(b), workers=len(workers),
                           selected_record_occurrences=int(g.n_selected.sum()),
                           equal_record_occurrences=int(g.n_equal.sum()),
                           B8L2_building_mean=float(b.B8L2_delta.mean()),
                           D10_building_mean=float(b.D10_delta.mean()),
                           negative_buildings=int((b.B8L2_delta < 0).sum()),
                           positive_panels=int((g.B8L2_delta > 0).sum()))
    # 现有同人同图面板的条件方向，直接复用已固定人员对照。
    fixed = pd.read_csv(PAT / 'same_people_condition_class_contrasts.csv')
    stats['fixed_people_conditions'] = dict(panels=len(fixed), images=fixed.image_id.nunique(),
        **{c:float(fixed[c].mean()) for c in ['manual_pair_n', 'semi_pair_n',
                                            'manual_short_turn_edges', 'semi_short_turn_edges']})
    stats['universe'] = dict(records=len(non_oos), images=len({r['image_id'] for r in non_oos}),
                             doorway_images=len({r['image_id'] for r in non_oos if r['is_doorway']}),
                             quality_comparison_records=len(f), workers=f.worker_id.nunique(), images_in_quality=f.image_id.nunique())
    (OUT / 'FINDINGS.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'], 'axes.unicode_minus':False,
                         'axes.spines.top':False, 'axes.spines.right':False})
    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    for i, name in enumerate(['less', 'extra']):
        vals = building.loc[building.contrast == name, 'B8L2_delta'].to_numpy()
        ax.scatter(i+np.linspace(-.12, .12, len(vals)), vals, s=32, alpha=.7, color=['#26848e','#bd6834'][i])
        ax.plot([i-.22,i+.22], [vals.mean()]*2, lw=3, color='#222222')
        ax.text(i, .96, f"{stats[name]['images']}图 / {len(vals)}栋 / {stats[name]['workers']}人", ha='center', va='top', transform=ax.get_xaxis_transform())
        ax.text(i+.24, vals.mean(), f'{vals.mean():.2f}', va='center', fontsize=10)
    ax.axhline(0, color='gray', lw=.8)
    ax.set_ylim(top=6)
    ax.set(xticks=[0,1], xticklabels=['点对少于参考 − 与参考同数', '点对多于参考 − 与参考同数'],
           ylabel='同图同参考 B8L2 均值差（分）', title='多画与少画都可能低分：点数不能替代结构语义')
    fig.text(.5,.01,'每点一栋；黑线为建筑等权均值。普通 Manual；两侧各≥2人；描述性比较，非增删点的因果效应。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,1]); fig.savefig(OUT / 'detail_quality.png', dpi=170); plt.close(fig)
    transfer = pd.read_csv(SAME / 'transfer_summary.csv').set_index('metric')
    fig, axes = plt.subplots(1,3,figsize=(12,4))
    axes[0].bar(['Manual','Semi'], [fixed.manual_short_turn_edges.mean(),fixed.semi_short_turn_edges.mean()], color=['#26848e','#bd6834'])
    axes[0].axhline(0,color='gray',lw=.8)
    axes[0].set(title='同一批人，类别差异随条件反向',ylabel='R5 − 其余：短转折边数差')
    for ax, metric, title, unit in [(axes[1],'corner_delta','同房历史有助预测结构保留','点对差 MAE（个）'),
                                   (axes[2],'bottom_bias_9','同房历史不保证定位迁移','底点 y 偏移 MAE（像素）')]:
        row=transfer.loc[metric]
        ax.bar(['本人楼外','本人同房','同房他人'],[row.outside_worker_mae,row.same_room_mae,row.other_people_same_sources_mae], color=['#777777','#26848e','#bd6834'])
        ax.set(title=title,ylabel=unit)
    fig.text(.5,.01,'左：23个固定人员/目标面板，图片等权；右两图：相同目标面板、建筑等权，7栋。各图量纲不同。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,1]); fig.savefig(OUT / 'condition_transfer.png',dpi=170); plt.close(fig)
    print(json.dumps(stats,ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main()
