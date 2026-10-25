from pathlib import Path
import pandas as pd,gzip,json,hashlib
from PIL import Image
BASE=Path(__file__).resolve().parent;eid='657ca45c363d898187246206';p=BASE/eid
text='''已实际查看原图、原答和三队叠图。这是缝纫休息室，**当前采用的难度为中等，不归入困难图**。画面接缝附近的高柜挡住 R3/R4 下部和竖直交线，上方墙顶仍提供窄转折线索；当前采用记录也明确写出“高柜遮住接缝附近点3、4的下部和竖角，窄转折需结合上端补足”。本例支持遮挡条件下对既定房间短结构的不同表达，不是把打开的房门外另一个房间扩大纳入。

这是 DSTRUCT_K3 中非常直接的类间结构差别：X、Y 两个互不重叠的源类七人块，分别只有一人进入 R3 组，均没有人进入 R4 组；目标类 Z 中则有 **6/7 人同时进入 R3、R4 组**。这六人是 W102、W109、W112、W122、W126、W130。共同 D 为 W100、W103、W117，对 R3/R4 分别贡献 1/2 票。

因此三队真实组票数为：

| 位置 | A：D+X | B：D+Y | C：D+Z | 共同门槛 |
|---|---:|---:|---:|---:|
| R3 | 2 | 2 | 7 | 5 |
| R4 | 2 | 2 | 8 | 5 |

A/B 均失去两处转折，形成四点围合；C 两处均进入融合，恢复六点形状。这里不是某一个特殊人员提供恰好一票：Z 内六人的重复支持形成了较大票数余量。三队共同 D 的 15 个观察没有拆分或合并，新增结构也不是重分组偶然把相同背景票重新凑出来。

R3/R4 在 ERP 的横向投影仅相隔约 0.13°，但顶部／底部纵向坐标和 BEV 深度不同；它们构成实际的短退台，而不是同一条边上的两个冗余点。冻结几何诊断中 C 有 6 个转折、1 条小于 0.5 相机高度的短边、0 个近共线冗余点，A/B 均为 4 转折。该处下部仍有遮挡，采用的是既有参考及已审阅结构机会，不声称从原图清晰看到了每一个底点。

结构补充之外，原有四个主要角点的中位数底点也改善：例如 R1 底点对参考误差 A/B/C 为 2.118°/1.528°/0.384°，R5 为 2.728°/1.631°/1.275°。因此 C 的变化包括短结构恢复和位置改善。

C−B：Q +13.870，底面 IoU 84.54%→96.53%，三维代理 78.23→94.95，遗漏 15.39%→2.53%，整体高度比 0.925→0.982。方向残差 C 为 2.532°，甚至略差于 A 的 2.259°；本例的明显改善不能只归因于方向项得分。

按不依赖参考的融合形状距离（1−BEV IoU），同类 A/B 为 **0.0612**，对称跨类为 **0.1662**，差 **+0.1049**；同类 Q 绝对变化 7.185，对称跨类 17.463。它是分类在原答结构、融合形状及质量上都能形成差别的一例，整体支持率仍由完整楼外比较给出。

来源记录时间 C 为 1,538.918 秒，B 为 903.631 秒、A 为 1,455.819 秒：相对 B 增加约 70.3%，相对 A 增加约 5.7%。这是明确的结构／质量收益伴随时间成本，不能表述为效率类的省时成果。'''
placeholder='本段应在读取原图与叠图后补充；目前先保存可核对的几何与票数事实。不得仅因新增参考外角点就称为错误结构，也不得将参考匹配直接写成必要结构已经人工确认。'
s=(p/'CASE_NOTE_ZH.md').read_text();assert placeholder in s;s=s.replace(placeholder,text);(p/'CASE_NOTE_ZH.md').write_text(s)
d=json.load(gzip.open(p/'CASE_GEOMETRY.json.gz','rt'));e=d['event'];r=d['saved_endpoint_rows'];qa,qb,qc=[r[k]['B8L2'] for k in 'ABC']
row={'event_id':eid,'image':e['image'],'method':e['method'],'n':e['n'],'m':e['m'],'common_background_n':e['n']-e['m'],'background_target_n':e['background_target_n'],'case_role':'structural_class_seven_person_block_short_turn_recovery','Q_A':qa,'Q_B':qb,'Q_C':qc,'Q_B_minus_A':qb-qa,'Q_C_minus_A':qc-qa,'Q_C_minus_B':qc-qb,'same_abs_Q':abs(qb-qa),'cross_symmetric_abs_Q':(abs(qc-qa)+abs(qc-qb))/2,'manual_photo_review':True,'reference_semantics_newly_changed':False,'group_reassignment_common_D':False}
f=pd.read_csv(BASE/'CASE_MECHANISM_SUMMARY.csv');f=pd.concat([f,pd.DataFrame([row])],ignore_index=True).drop_duplicates('event_id',keep='last');f.to_csv(BASE/'CASE_MECHANISM_SUMMARY.csv',index=False)
source=json.loads((BASE/'CASE_SOURCE.json').read_text());source.update(formal_cases=4,formal_unique_images=4,formal_buildings=3,native_state_replays=12);(BASE/'CASE_SOURCE.json').write_text(json.dumps(source,ensure_ascii=False,indent=2))
di=BASE.parent/'recovery/prior_population/research/workers/personnel_population_curves_v2_20261023/inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv';dd=pd.read_csv(di);dd[dd.image.isin(f.image)].to_csv(BASE/'CASE_DIFFICULTY_OPPORTUNITIES.csv',index=False)
metrics=pd.read_csv(BASE.parent/'results/screen/EVENT_METRICS.csv.gz',low_memory=False);metrics[metrics.event_id.isin(f.event_id)].to_csv(BASE/'CASE_EVENT_METRICS.csv',index=False)
checks=[]
for ce in f.event_id:
 for image in (BASE/ce).glob('*.png'):
  Image.open(image).verify();checks.append({'path':str(image.relative_to(BASE)),'status':'valid_png','bytes':image.stat().st_size,'sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
(BASE/'FIGURE_CHECKS.json').write_text(json.dumps(checks,indent=2))
main=BASE/'MECHANISM_FINDINGS_ZH.md';s=main.read_text().replace('# 三个实际替换机制案例','# 四个实际替换机制案例').replace('本轮已完成三个 DJOINT_K3 的严格 ABC 事件','本轮已完成一个 DSTRUCT_K3 与三个 DJOINT_K3 的严格 ABC 事件').replace('也不是挑三个正例','也不是只挑正例').replace('三个事件的共同 D','四个事件的共同 D').replace('所有三队均已用冻结引擎重放，9个端点','所有三队均已用冻结引擎重放，12个端点').replace('这三个正式案例','这四个正式案例')
s=s.replace('| jtcxE69GiFV-03 |','| pa4otMbVnkk-05 | 结构分类主例：中等图短结构恢复 | 66.296 / 73.481 / 87.351 | 4/4/6 | 源类X/Y对R3/R4仅1/0票，目标Z块6/6票；总票2/2变7/8 |\n| jtcxE69GiFV-03 |',1)
s=s.replace('## 采用解释','## 采用解释\n\n- **pa4-05（DSTRUCT_K3主例）**：中等图，非困难图。六名目标类成员共同保留遮挡短转折，两个七人源类块均大多省略；增加的两点不是近共线冗余。BEV形状距离同类0.0612、对称跨类0.1662，差+0.1049；C−B Q+13.870、底面IoU+11.99个百分点，但记录时间增加约70.3%。这例直接说明结构分类的换块用途及时间成本。')
main.write_text(s)
print('Fourth structural case and unified index saved; figure count',len(checks))
