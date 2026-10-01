"""方法审查的独立最小反例；仅写本审查目录，不修改被审包。
运行：PYTHONPATH=/workspace/scratch/a365811da80c/audit-oct1-deps python 独立反例.py
"""
from pathlib import Path
from collections import Counter
from itertools import combinations
import json, math, sys, os
import numpy as np
from shapely.geometry import Polygon, Point

HERE = Path(__file__).resolve().parent
BUNDLE = Path(os.environ.get('RETURNED_ROOT', HERE.parent / 'reproduction/returned_package'))
sys.path.insert(0, str(BUNDLE / 'src'))
from geometry_core import cross, from_floor, reconstruct, column_mask, iou, polygon_metrics, axis_residual

# 1. 独立枚举全部位集合，保原环序；不调用原包候选枚举器。
p = np.array([[-2.,-2.],[2.,-2.],[2.,2.],[.2,2.],[.2,2.4],[-.2,2.4],[-.2,2.],[-2.,2.]])
P = Polygon(p)
rows, valid_positive = [], 0
for mask in range(1 << len(p)):
    ids = [i for i in range(len(p)) if mask & (1 << i)]
    if len(ids) < 3:
        continue
    q = p[ids]
    Q = Polygon(q)
    if not Q.is_valid or Q.area < 1e-8:
        continue
    valid_positive += 1
    if not Q.contains(Point(0, 0)):
        continue
    e = np.roll(q, -1, axis=0) - q
    orient = 1 if Q.exterior.is_ccw else -1
    rows.append(dict(ids=ids,vertices=len(ids),area=float(Q.area),
        added_area=float(Q.difference(P).area),lost_area=float(P.difference(Q).area),
        exact_new_boundary_length=float(Q.boundary.difference(P.boundary).length),
        camera_in_kernel=bool(np.all(orient * cross(e,-q) >= -1e-9)),
        axis_residual=float(axis_residual(q)['weighted'])))
expected = json.loads((BUNDLE/'results/subtraction_exhaustive.json').read_text())
assert set(tuple(x['ids']) for x in rows) == set(tuple(x['ids']) for x in expected['all_candidates'])
orth = [r for r in rows if r['axis_residual'] < 1e-8]
assert len(rows) == 61 and valid_positive == 195 and len(orth) == 5
single = next(x for x in rows if x['ids']==[0,1,2,4,5,6,7])
assert abs(single['added_area']-.36) < 1e-12 and single['lost_area'] < 1e-12

# 2. 相机严格内部、正交、简单闭合，仍不意味着每条边都有可见证据。
# 只伸长被墙遮挡的拐角后支路；两房间近表面墙带完全相同。
a=np.array([[-2,-2],[2,-2],[2,1],[4,1],[4,3],[3,3],[3,2],[-2,2]],float)
b=a.copy(); b[4:6,1]=7
ag,bg=reconstruct(from_floor(a)),reconstruct(from_floor(b))
am,bm=column_mask(ag,4096),column_mask(bg,4096)
assert ag['camera']==bg['camera']=='inside' and not ag['kernel'] and not bg['kernel']
assert ag['reason'] is None and bg['reason'] is None and iou(am,bm)==1
visibility=dict(a=a.tolist(),b=b.tolist(),area_a=Polygon(a).area,area_b=Polygon(b).area,
    bev_iou=polygon_metrics(a,b)['bev_iou'],column_iou_4096=iou(am,bm),
    column_different_pixels_4096=int(np.count_nonzero(am!=bm)),
    camera_strictly_inside=True,camera_in_kernel_a=ag['kernel'],camera_in_kernel_b=bg['kernel'],
    axis_residual_a=axis_residual(a)['weighted'],axis_residual_b=axis_residual(b)['weighted'],
    interpretation='声明足迹可不同而近表面投影相同；不能要求所有非星形候选失效，但必须标记可见/隐藏证据。')

# 3. 定向局部多数与完整来源频次必须分开。并不宣判未观察模式为错误。
observed=np.array([[1,1,0],[1,0,1],[0,1,1]],int)
mv=(observed.mean(axis=0)>.5).astype(int)
joint=dict(observed=observed.tolist(),majority=mv.tolist(),local_yes=observed.sum(axis=0).tolist(),
    whole_support=int(np.all(observed==mv,axis=1).sum()))
assert joint['whole_support']==0 and joint['local_yes']==[2,2,2]

# 4. 每图一人：人员列都是图片指示列之和，无法识别人员均值差异。
w=np.array([0,1,2,0,1,3,0,2,4,4,1,0]); X=np.column_stack([np.eye(12),np.eye(5)[w]])
delta=np.array([.2,-.1,.4,.05,-.3]); null=np.r_[-delta[w],delta]
identifiability=dict(columns=X.shape[1],rank=int(np.linalg.matrix_rank(X)),
    nullity=int(X.shape[1]-np.linalg.matrix_rank(X)),max_prediction_change=float(np.abs(X@null).max()),
    meaning='此为设计矩阵反例；5个身份仅作示范，不代表真实历史人员。')
assert identifiability['rank']==12 and identifiability['max_prediction_change']==0

# 5. 完全相同的 BEV 并不等于上下墙带一致；作为 B/C 接口命名检查。
f=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
floor_same_top_different=dict(bev_iou=polygon_metrics(f,f)['bev_iou'],
    column_iou_1024=iou(column_mask(reconstruct(from_floor(f,2.7)),1024),column_mask(reconstruct(from_floor(f,3.7)),1024)))
assert floor_same_top_different['column_iou_1024']<1

summary=dict(
    scope='独立数学/几何审查；非新真人数据；可见性与渲染使用包内geometry_core，删点集合由独立位枚举复核。',
    deletion=dict(raw_subsets=sum(math.comb(8,k) for k in range(3,9)),valid_simple_positive=valid_positive,
        strict_camera_subcycles=len(rows),counts_by_vertices=dict(sorted(Counter(x['vertices'] for x in rows).items())),
        added_area_candidates=sum(x['added_area']>1e-8 for x in rows),max_added_area=max(x['added_area'] for x in rows),
        new_boundary_candidates=sum(x['exact_new_boundary_length']>1e-8 for x in rows),
        all_candidates_in_camera_kernel=all(x['camera_in_kernel'] for x in rows),
        zero_residual_candidates=len(orth),single_reflex_deletion=single,all_candidates=rows),
    visibility=visibility,joint_support=joint,identifiability=identifiability,
    same_bev_different_top=floor_same_top_different)
(HERE/'独立反例结果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='deletion'},ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary['deletion'].items() if k!='all_candidates'},ensure_ascii=False,indent=2))
print('全部断言通过；61个集合与被审包逐一一致。')
