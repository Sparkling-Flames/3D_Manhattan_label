"""Persist the AI visual observations recorded after viewing all eight panels."""
import json
from pathlib import Path
out=Path(__file__).resolve().parent
rows=json.loads((out/'selection.json').read_text(encoding='utf8'))
observations=[
('疑似遗漏；不能仅据单簇定错','W037仅3对角点；左侧p1/p2标走廊尽头，右侧p3–p6标另一端。W014还在玻璃隔断左端立边设置p3/p4，W037没有对应角点。可见透明/磨砂隔断确有边界，但玻璃是否作为布局边界需协议解释，不能自动判为粗心。','优先核查玻璃隔断范围规则；点数硬门槛导致分开，调25.6无法解决。',[1,2,3,4,5,6]),
('疑似不符合房间包络的质量问题','W037的p21–p24围绕右侧窗框而非该处完整墙角；p2/p4/p6落洗手台台面附近，p14/p16/p19/p20落浴缸上沿附近。p7/p8选择左侧凸柱附近但较W028的完整外角位置偏左。多个物体边缘被当作布局端点的迹象明显；同时此图有门洞和转折，不能把26点整体简单称为乱标。','该作答值得按墙顶/墙地边界定义做独立质量复审；不能直接据此取消W037全部作答资格。',[2,4,6,7,8,14,16,19,20,21,22,23,24]),
('同结构局部定位差异；无足够证据判低质量','两者都表达左侧开口、中央转折、右侧开口，同为6对角点。最大差异是p6对p6，W037落在沙发遮挡后墙脚延长方向较低处，W036较高；其余多数点相近。遮挡使该底角缺少直接可见真值。','28.806px超过阈值3.206px，不宜由此称为独特结构；需要允许遮挡下连续几何误差的语义解释。',[6]),
('范围/结构选择不同，兼有固定对应风险；无法裁决谁错','W037在右侧高柜两边附近设p3/p4和p5/p6，W030在圆弧墙左边与玻璃转折设p3/p4和p5/p6。二者14点但角点身份不同，固定序号距离把W037柜边p3与W030圆弧墙左边p3比较，产生182.846px。W037没有W030玻璃转折那一对。','应先核查柜体是否被当房间边界以及玻璃转折选择；不是单纯将阈值增大即可解决。不能把同点数视为同语义对应。',[3,4,5,6]),
('疑似整图分簇过拆；视觉同结构','两人都选4对相同房间角点，门洞未延伸；p7对p7是最大差异16.688px，门边底点存在少量水平/垂直偏移。未见W037表达额外结构或明显脱离图像。','W037虽complete单簇，但已有阈内近邻，应检查整个簇的直径约束及阻挡成员，不能按孤立标签判坏人。',[7]),
('疑似整图分簇过拆；视觉同结构','两人都是4对相同浴室角点。W037的p8与W021的p4都在洗手柜遮挡区域，横向定位约22.687px差异；其余角点相近。柜后真实墙地角不可直接看清。','已有阈内近邻却complete单簇；不能据此判W037创造了新结构。遮挡区域可保留几何不确定性。',[8]),
('对照：疑似整图分簇过拆；视觉同结构','W012与W036同为6对角点，近处墙柱和远处起居区范围一致。最大差异W012 p4与W036 p1为14.638px，均指近处左侧柱底；没有可见范围改变。','另一高单人簇人员同样出现近邻被complete隔离，说明该现象并非W037特有。',[4]),
('对照：阈值边缘连续差异；无足够证据判结构不同','W034与W035同为4对角点，覆盖左右两个可见区域，范围选择一致。最大差异W034 p2与W035 p8位于左侧被家具遮挡的底角，25.679px只比阈值高0.079px；不能从这一像素差给出两种结构的视觉证据。','用于阈值标定边界案例，不能以略增阈值改善收敛作为独立有效性证据。',[2]),
]
for r,(category,reason,action,points) in zip(rows,observations):
    r.update(visual_reviewed=True,reviewer='AI visual_worker',user_decision=None,category=category,visual_observation=reason,recommendation=action,focus_worker_point_indices_1based=points)
    if r['case'] in [2,5,8]:
        r['overlap_review_by_root']='根智能体实际查看同一面板，同意为质量复审线索（案例2）或同结构局部定位差（案例5、8），不是人工裁决。'
    if r['case']==2:
        r['comparison_caveat']='根重叠核验注意到W028也有部分底点落台面附近；对照只是最大簇成员，不能当标准真值。质量疑点来自与图像边界关系，而不是偏离W028。'
result=dict(scope='8个人工目的性挑选作答对；W037六例、W012及W034各一例；非随机质量率估计',source='固定的20260921独立复算快照，2444作答/240图；不改变原始标注与既有人工作答裁决',method='按完整链接单人簇分类筛选，限定N>=8且基础全景可读取；覆盖无同点数伙伴、同点数远邻和阈内近邻仍单簇。无同点数时对比最大簇中canonical id最小成员，非语义最近人。所有8张双层面板均以view_image实际检查。',limitations=['AI初核不是人工GT；未按整图全员逐份验收','目的性选例不能估计W037或其他工人的错误率','固定对应下的距离不保证角点语义相同','未重新裁决uNb21既有映射或W037的7036原样观察决定'],cases=rows)
(out/'findings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# 单人簇人员的八例视觉初核','','本轮实际查看8张双层全景点位面板。选例覆盖三种单人簇机制，属于目的性诊断，不是随机样本；不能报告总体错误率，也不构成整人剔除裁决。AI意见不是人工GT。“无同点数伙伴”“同点数远邻”“阈内近邻仍单簇”是几何/分簇机制，均不是质量判决。','','核心观察：W037确有值得质量复审的作答（uNb-26含窗框、台面和浴缸上沿端点），同时也有与他人明显表达同一结构而被complete分成单人簇的作答。W012也存在后一种情况。不能将“单人簇多”直接等同“人员标注差”。','','|案例|对象/对照|距离(px)|视觉意见|','|---|---|---|---|']
for r in rows:
    lines.append(f'|{r["case"]} {r["code"]}|{" / ".join(r["workers"])}|{r["distance_px"]:.3f}|{r["category"]}|' if r['distance_px'] is not None else f'|{r["case"]} {r["code"]}|{" / ".join(r["workers"])}|点数不同，不比较|{r["category"]}|')
for r in rows:
    lines.extend(['',f'## {r["case"]}. {r["code"]}', '',f'Canonical IDs：`{r["ids"][0]}` / `{r["ids"][1]}`。有效点数：{r["point_counts"]}。', '',r['visual_observation'],'',r['recommendation']])
    if 'overlap_review_by_root' in r:lines.extend(['',r['overlap_review_by_root']])
    if 'comparison_caveat' in r:lines.extend(['',r['comparison_caveat']])
lines.extend(['','## 使用边界','','阈内近邻被分开是complete的直径约束可能产生的行为，不能直接称实现bug；但若研究把每簇解释成一种不同标法，则存在解释失真风险。反之，增大阈值也不能解决点数不同或同点数、不同语义角点的问题。','','`selection.json`保留全部canonical id、上下绑定与距离极值点号；`recreate_panels.py`从已有快照和内嵌原图重建8张面板并检查选中对象均为complete单人簇。`write_findings.py`保存本次实际视觉观察。临时面板检查后删除。没有改动任何源标注、分簇算法、阈值或人工裁决。'])
(out/'视觉初核简报.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
assert len(result['cases'])==8 and all(r['visual_reviewed'] for r in result['cases'])
print('8 visual findings saved')
