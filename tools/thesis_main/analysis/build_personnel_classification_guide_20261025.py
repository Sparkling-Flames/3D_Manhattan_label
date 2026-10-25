"""将已审查的小表整理为人员研究六步的显示数据；不拟合、融合或重评分。"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_classification_guide_20261025'

METHODS = [
    dict(id='DSTRUCT_K3', name='困难结构表达 · 三类', role='主要解释方法',
         question='同样遇到困难结构，哪些人较简化，哪些人保留更多实际转折？',
         inputs='Manual总体、困难及困难−简单的转折、短边、近共线节点和参考对应缺失；不含Q/T。',
         meaning='把主线图片难度接回人员表达，连接原答、混合构成与大块替换。',
         limit='转折多不是结构正确率。新C3的12人来自旧M3的19人，但整套分区不是旧三类的纯细分。'),
    dict(id='RFUSE_GEOM_K2', name='融合几何响应 · 二类', role='核心效果对照',
         question='哪些人员共同进入时，更容易改变当前融合的结构、位置或尺度？',
         inputs='训练楼的自然随机团队；同图同人数内估计人员份额与实际融合几何的关系，再对响应特征聚类。',
         meaning='解释融合响应角色；ALL为55人与4人两类，四人核心可对应具体支持票变化。',
         limit='不是纯个人能力或必然因果贡献；结论与当前融合规则有关。'),
    dict(id='RFUSE_GEOMQ_K3', name='融合几何＋质量响应 · 三类', role='核心效果对照',
         question='哪种人员块既改变输出形状，也有不同的参考质量响应？',
         inputs='自然随机团队的几何响应，加上B8L2、D10、3D IoU等质量响应域；训练目标楼排除。',
         meaning='ALL为20/32/7人；在已检验的n20/m6条件，类内波动小、跨类幅度较大。',
         limit='含质量响应，不作为纯风格证据。与K2共同可评20图上跨/同比约2.06；全部21图约3.09。'),
    dict(id='MSDGEOM_SCOPE_K4', name='Manual＋Semi＋范围判断 · 四类', role='跨条件联合解释',
         question='两种标注方式下的结构、边界与范围判断，能否共同区分人员？',
         inputs='Manual困难结构与边界、Semi终稿结构与边界、scope回答倾向及困难响应；不直接输入Q/T。',
         meaning='用更多行为维度描述同一人；本轮效果仍只评价普通Manual。历史Q/T用于解释或选择方向。',
         limit='scope是判断倾向，不是准确率；终稿特征不是初始化纠错或盲信。尚不能把全部增益归给scope单项。'),
    dict(id='DBOUNDARY_K3', name='边界与尺度 · 三类', role='几何差别解释',
         question='总质量相近时，顶底界位置、空间尺度是否仍以不同方式变化？',
         inputs='Manual顶/底界相对位置、面积、高度及困难−简单响应。',
         meaning='n18/m7同/跨Q幅度约4.058/4.000；顶界角距离约0.440°/0.550°，41/61图跨类更大。',
         limit='Q总分区分弱仍可有几何用途；不能把位置差异直接称为质量增益。'),
    dict(id='DJOINT_K4', name='难度结构＋质量＋时间 · 四类', role='质量与劳动取舍',
         question='表达、历史质量和速度相近或不同时，怎样组织构成比较？',
         inputs='Manual结构、难度响应、历史Q和记录时间。',
         meaning='区别质量相近但速度或表达不同的角色；用于质量—劳动—结构的共同解释。',
         limit='不是纯结构分类，也不能把历史快角色等同于本图实际节时。'),
    dict(id='MSDGEOM_K4', name='Manual＋Semi几何 · 四类', role='跨条件几何对照',
         question='两条件的终稿表达和定位，是否提供互补的人员画像？',
         inputs='Manual结构/边界与Semi终稿结构/边界，不含scope域。',
         meaning='保留跨条件几何差异，并作为含scope方案的来源对照。',
         limit='与含scope方案的图片和方向支持不同，现有数值不等于固定条件下scope消融增量。'),
]

MAIN = [('DSTRUCT_K3', 18, 7, 'largest_to_highest_turn'),
        ('RFUSE_GEOM_K2', 12, 4, 'into_smallest_class'),
        ('RFUSE_GEOMQ_K3', 20, 6, 'into_smallest_class'),
        ('MSDGEOM_SCOPE_K4', 20, 6, 'higher_Q|slower|more_turns')]


def read(name):
    return pd.read_csv(OUT / 'sources' / name)


def records(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False, double_precision=15))


def build():
    labels = pd.concat([read(f) for f in ['NEW_METHOD_LABELS_ALL_LOBO.csv.gz',
                       'SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz', 'REVERSE_LABELS_ALL_LOBO.csv.gz']])
    labels = labels[labels.method.isin([m['id'] for m in METHODS])].copy()
    assert not labels.duplicated(['method', 'heldout_building', 'worker_id']).any()
    assert len(labels) == 7 * 23 * 62
    assert (labels.groupby(['method', 'heldout_building']).size() == 62).all()
    rosters = []
    for (method, fold, cls), g in labels.groupby(['method', 'heldout_building', 'class_id'], dropna=False):
        rosters.append(dict(method=method, fold=fold, class_id=cls if pd.notna(cls) else 'unknown',
                            known=bool(g.known.all()), workers=sorted(g.worker_id.tolist())))
    centers = pd.concat([read('NEW_CLASS_DEFINITIONS_ALL_LOBO.csv.gz'),
                         read('SCOPE_INCREMENT_CLASS_DEFINITIONS_ALL_LOBO.csv.gz')])
    centers = centers[(centers.method == 'DSTRUCT_K3') & (centers.heldout_building == 'ALL')]
    assert sorted(centers.people) == [8, 12, 39]
    compact = read('FINAL_CONDITIONS_COMPACT.csv')
    audit = read('FOUR_MAIN_CONDITIONS.csv').set_index('method')
    selected = []
    for method, n, m, role in MAIN:
        rows = compact[(compact.method == method) & (compact.n == n) & (compact.m == m)
                       & (compact.role == role) & (compact.phase == 'selection_heldout_building')]
        assert len(rows) == 1, (method, n, m, role)
        row = records(rows)[0]
        for key in ['B8L2_within_image_equal', 'B8L2_cross_image_equal', 'B8L2_CB_image_equal',
                    'C_failed_raw_count', 'attempted_events']:
            assert abs(row[key] - float(audit.loc[method, key])) < 1e-10, (method, key)
        selected.append(row)
    adoption = read('METHOD_ADOPTION_DECISIONS.csv')
    payload = dict(schema='personnel_classification_guide_v1', data_release='v2',
                   version='20261025', methods=METHODS, rosters=rosters,
                   dstruct_centers=records(centers[['class_id', 'people', 'm_hard_turn_n', 'm_hard_near_straight_nodes_5deg']]),
                   main_conditions=selected, all_conditions=records(compact),
                   adoption=records(adoption),
                   strict_paths=records(read('SIZE_FIXED_N21_RECALCULATED.csv')),
                   ac_paths=records(read('AC_FIXED_N35_RECALCULATED.csv')),
                   source_map=json.loads((OUT / 'sources/SOURCE_MAP.json').read_text(encoding='utf-8')))
    (OUT / 'GUIDE.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8')
    print(f'guide: {len(METHODS)} methods, {len(labels)} person/fold labels, {len(compact)} conditions')


if __name__ == '__main__':
    build()
