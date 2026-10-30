"""Matched context summaries and a source-linked Chinese report; no new teams."""
from pathlib import Path
import itertools,json,gzip,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage01_half_team'
def read(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def save(x,name):pd.DataFrame(x).to_csv(OUT/name,index=False,encoding='utf-8-sig')
def table(d):
    return '| '+' | '.join(map(str,d.columns))+' |\n|'+'|'.join(['---']*len(d.columns))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in d.itertuples(index=False,name=None))
def fmt(v):return '不可评' if pd.isna(v) else f'{v:+.3f}'
def ray(p):
    az=float(p[0])*2*np.pi/1024;el=(.5-float(p[1])/512)*np.pi
    return np.array([-np.sin(az)*np.cos(el),np.sin(el),np.cos(az)*np.cos(el)])
def main():
    e=pd.read_csv(OUT/'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz',low_memory=False)
    im=pd.read_csv(OUT/'IMAGES_METRIC_SPECIFIC_SUPPORT.csv.gz')
    links=pd.read_csv(OUT/'EXACT_XYZ_14_7_TO_20_7.csv')
    context_images=[];context_summaries=[]
    # Pairwise matched backgrounds are not independent repetitions. First equal
    # weight paired D contexts within exact XYZ, then XYZ, pool, image, building.
    keys=['building_14','image_14','pool_id','X','Y','Z']
    for scope,part in [('all_exact_XYZ',links),('D14_subset_D20',links[links.D14_subset_D20]),('D_also_replaced',links[~links.D14_subset_D20])]:
        for metric in ['gap_A','gap_sym','CB','B8L2_within','B8L2_cross_direct','B8L2_cross_symmetric']:
            cols=[metric+'_14',metric+'_20'];v=part.dropna(subset=cols)
            x=v.groupby(keys,dropna=False)[cols].mean()
            x=x.groupby(level=keys[:3]).mean().groupby(level=keys[:2]).mean().reset_index()
            x['delta_20_minus_14']=x[cols[1]]-x[cols[0]]
            x['scope']=scope;x['metric']=metric
            context_images.extend(x.rename(columns={'building_14':'building','image_14':'image',cols[0]:'value14',cols[1]:'value20'}).to_dict('records'))
            b=x.groupby('building_14')[[*cols,'delta_20_minus_14']].mean()
            context_summaries.append(dict(scope=scope,metric=metric,registered_links=len(part),registered_images=part.image_14.nunique(),registered_buildings=part.building_14.nunique(),valid_links=len(v),valid_images=len(x),valid_buildings=len(b),mean14=x[cols[0]].mean(),mean20=x[cols[1]].mean(),mean_delta=x.delta_20_minus_14.mean(),positive_delta_images=int(x.delta_20_minus_14.gt(1e-10).sum()),negative_delta_images=int(x.delta_20_minus_14.lt(-1e-10).sum()),building_equal14=b[cols[0]].mean(),building_equal20=b[cols[1]].mean(),weight='paired D contexts within exact XYZ, then XYZ/pool/image; building-equal separately'))
    save(context_images,'MATCHED_BACKGROUND_CONTEXT_IMAGES.csv');save(context_summaries,'MATCHED_BACKGROUND_CONTEXT_SUMMARY.csv')
    ordinary_common=[]
    for metric in ['gap_A','gap_sym','CB']:
        a=im[im.n.eq(14)].set_index('image')[metric];b=im[im.n.eq(20)].set_index('image')[metric]
        v=pd.concat({'n14':a,'n20':b},axis=1).dropna()
        ordinary_common.append(dict(metric=metric,valid_images=len(v),mean14=v.n14.mean(),mean20=v.n20.mean(),weight='original within-n background/block/pool/image means, common image subset; not exact-team matching'))
    save(ordinary_common,'COMMON_IMAGES_ORIGINAL_WEIGHTS.csv')
    # Explicitly separate three-score amplitude support from two-score direction.
    statuses=[];supports=[]
    for n,g in e.groupby('n'):
        for a in 'ABC':
            for st,c in g[a+'__score_status'].value_counts(dropna=False).items():statuses.append(dict(n=n,arm=a,score_status=st,events=c))
        for metric in ['gap_A','gap_sym','CB','record_time_CB_pct_source_matched']:
            z=g[g[metric].notna()]
            supports.append(dict(n=n,metric=metric,registered_events=len(g),valid_events=len(z),valid_images=z.image.nunique(),valid_buildings=z.building.nunique()))
    save(statuses,'ENDPOINT_STATUS_COUNTS.csv');save(supports,'KEY_METRIC_SUPPORT.csv')
    # A shared displacement diagnostic is a geometric observation relative to
    # the frozen reference, never an automatic physical/semantic bias label.
    cases=pd.read_csv(OUT/'ALL_EXCEPTION_EVENTS_AND_20_7_CONTEXT.csv.gz',low_memory=False)
    shared=[]
    for ev in cases[cases.n.eq(14)].to_dict('records'):
        p=read(OUT/'case_inputs'/(ev['pool_id']+'.json.gz'))
        ref=np.array(p['reference']['points_1024x512']).reshape(-1,2,2)
        arms={a:read(OUT/'trace_endpoints'/(ev[a+'_team_key']+'.json.gz')) for a in 'ABC'}
        for ri,pair in enumerate(ref,1):
            rv=ray(pair[1]);vals={};tangents=[]
            for a,obj in arms.items():
                groups=[x for x in obj['full_state']['identity_groups'] if x['selected'] and x.get('center') is not None]
                if not groups:continue
                dist=[math.degrees(math.acos(float(np.clip(np.dot(ray(x['center'][1]),rv),-1,1)))) for x in groups]
                idx=int(np.argmin(dist));g=groups[idx];v=ray(g['center'][1]);tv=v-np.dot(v,rv)*rv
                norm=np.linalg.norm(tv);tangents.append(tv/norm if norm>1e-12 else np.zeros(3))
                vals.update({a+'_nearest_selected_group':g['feature_id'],a+'_bottom_error_deg':dist[idx],a+'_support':g['support'],a+'_status':obj['score_status']})
            cos=min((float(np.dot(x,y)) for x,y in itertools.combinations(tangents,2)),default=np.nan)
            flag=len(tangents)==3 and min(vals[a+'_bottom_error_deg'] for a in 'ABC')>5 and cos>.8
            shared.append(dict(event_id=ev['event_id'],image=ev['image'],reference_corner_1based=ri,reference_bottom_json=json.dumps(pair[1].tolist()),all_three_have_selected_groups=len(tangents)==3,minimum_displacement_alignment=cos,shared_large_selected_displacement=flag,**vals))
    save(shared,'SHARED_REFERENCE_DISPLACEMENT_DIAGNOSTIC.csv.gz')
    c=pd.DataFrame(shared).groupby('image').agg(reference_corner_event_rows=('event_id','size'),shared_large_selected_displacement_rows=('shared_large_selected_displacement','sum')).reset_index()
    save(c,'SHARED_REFERENCE_DISPLACEMENT_BY_IMAGE.csv')
    main=pd.read_csv(OUT/'MAIN_CHECKED_SUMMARY.csv').set_index('n')
    ex=pd.read_csv(OUT/'LATEST_HALF_ALL_EXCEPTION_IMAGES.csv')
    metrics=pd.read_csv(OUT/'ALL_METRICS_IMAGE_SUMMARY.csv')
    summ=pd.DataFrame(context_summaries)
    head=[]
    for n in [14,20]:
        q=main.loc[n];head.append({'n/m':f'{n}/7','事件':int(q.events),'登记图/共同Q图':f'{int(q.registered_images)}/{int(q.gap_A_valid_images)}','楼':int(q.buildings),'GA均值/正图':f'{q.gap_A_mean:+.3f} / {int(q.gap_A_positive_images)}/{int(q.gap_A_valid_images)}','GS均值/正图':f'{q.gap_sym_mean:+.3f} / {int(q.gap_sym_positive_images)}/{int(q.gap_sym_valid_images)}','C−B均值/升质图':f'{q.CB_mean:+.3f} / {int(q.CB_positive_images)}/{int(q.CB_valid_images)}'})
    ms=[]
    for met,label in [('D10__delta_CB','D10'),('fusion_turn_n__delta_CB','有效转折数'),('fusion_short_turn_edges__delta_CB','短结构边数'),('ref_node_recall_5__delta_CB','参考节点5°保留率'),('ref_edge_recall_5__delta_CB','参考边5°保留率'),('geometry_area_h2__delta_CB','底面积 h²'),('height_mean_h__delta_CB','平均高度 h'),('record_time_CB_pct_source_matched','记录劳动变化 %')]:
        r=metrics[(metrics.n==14)&(metrics.metric==met)].iloc[0];ms.append({'指标':label,'C−B均值':fmt(r['mean']),'有效图/楼':f'{int(r.valid_images)}/{int(r.valid_buildings)}','增加/减少/零':f'{int(r.positive_images)}/{int(r.negative_images)}/{int(r.zero_images)}'})
    context=[]
    for scope in ['D14_subset_D20','D_also_replaced']:
        for met in ['gap_A','gap_sym','CB']:
            r=summ[(summ.scope==scope)&(summ.metric==met)].iloc[0];context.append({'背景关系':scope,'指标':met,'配对链接/可评图':f'{int(r.valid_links)}/{int(r.valid_images)}','14/7':fmt(r.mean14),'20/7':fmt(r.mean20),'20−14':fmt(r.mean_delta)})
    gs=ex[ex.nonpositive_symmetric];ga=ex[ex.nonpositive_same_origin]
    names='、'.join('`'+x+'`' for x in gs.image.sort_values())
    diag_images=int(c.shared_large_selected_displacement_rows.gt(0).sum())
    report=f'''# 最新半队综合事件：全部反例与机制衔接

## 结论与采用范围

本轮沿用冻结的 TARGET_DSTRUCT K3 楼外标签作为工作分析对象，未重拟合分类，也不作最终分类选型。当前普通 Manual 主目标、主方向 role 2/3 → 3/3 的半队替换，在多数共同可评图上产生比同类换人更大的质量变化幅度，同时 C 相对 B 在 76/83 图升质。结构增加集中于有结构机会的困难图；简单图的质量改变更多伴随定位、尺度或高度变化。记录劳动平均增加，完整输出也可能失去。因此，本结果支持模拟不同类别人群的多维不确定性，不应缩成“换更高Q人员必然更好”。

全部原事件与端点保留。主要统计见 `MAIN_CHECKED_SUMMARY.csv`、`ALL_METRICS_IMAGE_SUMMARY.csv`、`BUILDING_EQUAL_SUMMARY.csv`；逐图源为 `IMAGES_METRIC_SPECIFIC_SUPPORT.csv.gz`。可直接打开 `HOHONET_latest_half_all36_viewer_ZH.html`，切换全部36图、116个原事件及348个精确团队。

## 1. 来源、指标与统计单位

当前仓库提交固定为 `13a7861334749805a86dc19e9ea79fcaa71020c0`。实际来源是当前 release 的 `TARGET_MAIN_EVENTS.csv.gz`、`ADOPTED_CONDITIONS.csv`、`USED_FINAL_LOBO_LABELS.csv.gz` 和 `pools/INPUT_SNAPSHOT.json`，不是旧 focused-only 子集。输入和冻结引擎的135项依赖已核对当前提交；见 `../stage00_intake/CURRENT_FULL_ENGINE_CLOSURE.json` 与 `CURRENT_ENGINE_INPUT_COMPATIBILITY.json`。

A=D∪X，B=D∪Y，C=D∪Z；四块真实互斥，X/Y 同类、Z 跨类，每块7人。所有197个14/7事件和82个20/7事件均重验精确成员、原目标、参考、楼外折和端点键。本文把两种幅度与方向分开：

- 同起点幅度差 GA=|Q_C−Q_A|−|Q_B−Q_A|。
- 对称幅度差 GS=(|Q_C−Q_A|+|Q_C−Q_B|)/2−|Q_B−Q_A|。
- C−B=Q_C−Q_B，才表示升质或降质方向；幅度差正不保证升质。

先在实际背景、替换块、目标池层逐级平均，再给每张图等权；另报建筑等权。不是把事件数多的图给予更多总权重。不同指标各用自己的有效支持；14/7 的 GA/GS 有185事件，C−B有187事件，二者虽都覆盖83图仍不能混用分母。记录劳动只在合法同源支持下计算，并非真实并行完工速度。缺Q保持缺失。

## 2. 最新综合结果与分母

{table(pd.DataFrame(head))}

14/7 的同类幅度均值为4.577 Q，直接跨类幅度8.089，对称跨类幅度7.974。GA中位数1.448、P10 −1.299；GS中位数1.323、P10 −1.516；C−B中位数3.344、P10 +0.480、逐图绝对变化均值7.636。建筑等权 GA +2.578（18/21楼正）、GS +2.728（18/21楼正）、C−B +6.679（20/21楼正）。少数大变化不是唯一依据。

{table(pd.DataFrame(ms))}

几何量“增加”不自动代表更正确。完整的底面方向、遗漏、外扩、质心、底面积、平均高度、边界/方向/高度损失均已逐事件、逐图、逐楼保留；B8L2与D10独立列出。对总体结构数而言，68/83图 C−B有效转折数为零，不能把总体Q多数改善解释为每张图都增加结构。

### 难度条件

简单图59张可评，C−B +4.649 Q（56/59升质），有效转折数59/59不变；中等图15张，C−B +7.470（13/15升质），有效转折均增0.589；困难图9张，C−B +17.732（7/9升质），有效转折均增2.806，9/9增加，参考节点保留率均增0.288，9/9增加。困难图合法劳动仅6张，均增加、均值+18.023%；简单图37张劳动均值+6.512%，中等图12张均值−1.693%。这些分别是条件规律，未把难度误作可干预因果变量。

## 3. 全部非正差图与局部不可评

最新 GS 非正恰为21图，GA非正22图，C−B非正7图，三队共同Q完全不可评2图；这些集合重叠，数值并集32图。再纳入4张逐图均值仍正、但部分原事件不可评的图：`pa4otMbVnkk-14`、`VFuaQ6m2Qom-01`、`zsNo4HB9uLZ-16`、`S9hNv5qa7GM-12`。完整检查总数36图。没有使用旧192事件/22张对称非正的名单。

21张对称非正图如下（各自其他标志见 `LATEST_HALF_ALL_EXCEPTION_IMAGES.csv`，全量逐图解释见 `ALL_36_CASES_ZH.md`）：

{names}

数值解释可以重叠：21张GS非正中17张仍C−B升质；14张至少半数设计权重三队Q都≥90；8张|GS|≤1；11张至少有一个C位于A/B分数之间的事件；11张存在边界、方向、顶部损失方向相反的事件。22张GA非正中18张仍C−B升质。7张C−B降质图都有分项反向的事件，但均非三队都≥90的高分集中图。不能用“全是高分天花板”概括它们。

若某事件C分数位于A/B之间，则 |C−A|+|C−B|=|B−A|，GS自然等于−|B−A|/2；这解释一个数值关系，不证明节点投票的原因。同类内部变化、结构改善但其他分项恶化、公共背景的共同偏差等需要继续看原答和轨迹。

## 4. 从票账到位置和连接：已取得什么证据

先检索107份已有轨迹缓存，未找到这批精确团队的完整命中，再仅重放348个既有团队以补取诊断轨迹，不新增实验队伍。原标量继续作为权威来源；重放状态一致，最大分数/几何标量差1.42×10⁻¹⁴。全部候选节点（含未入选）、真实支持人员、位置聚类、原答点身份、源环投影、可用连接和最终状态已保存。没有声称对未保存的旧完整几何做字节比较。

`mechanism_tables/`含2,210个事件候选组、25,907条实际成员支持、5,430条原答指派、1,539条连接、332条环候选；348个团队全部有完整位置/连接状态。所有已选组的位置估计都存在，部分不可评不能归因于“位置为空”。同一个共同背景原答的点对在不同团队中是否被分到同一身份组，通过原答object_id+pair_index比较，避免用局部node编号硬认同一结构。8张半队案例出现共同D的共分组关系随替换而改变。

MV50用≥ceil(n/2)。14/7时，一块7人的所有成员只有都支持同一候选组，才可独自给该组7票；并非每个结构自动获得7票。表中“D票数达门槛”仅指**当前完整团队已形成的身份分组中D的票数**，不是另行融合D单独团队。20/7阈值升为10，7人替换块不能单独达票，但可与D共同越过门槛，也可能改变位置中位数或连接。

新增 `SHARED_REFERENCE_DISPLACEMENT_DIAGNOSTIC.csv.gz` 将每个参考角的A/B/C最近已选组与底角偏差显式列出：三队都偏离>5°且球面切向位移两两余弦>0.8的候选共有{diag_images}张图出现。该条件只是“相对冻结参考的共同方向偏移”，不能自动证明物理墙体存在共同标注偏差；近邻对应、目标范围与遮挡语义仍应由原图确认。阈值仅为诊断，没有改变Q、分类或正式融合。

### 可直接检查的机制案例

- **S9hNv5qa7GM-09，事件45233d89fc52d766715361de。** A/B为4节点，Q=78.997/77.798；C为6节点，Q=60.282。C的三个新增/改变方向节点各为D1+Z7=8票，Z的7人全部支持；邻近原闭合表达的候选组只有D6+Z0=6票而未入选。C的布局延伸到右侧门口方向，与当前正式闭合走廊参考差异变大。全图四个14/7事件均C−B降质，逐图均值−17.498。这是有清晰结构作用的恶化案例；既有空间归属不因较高Q而改写。
- **jh4fc5c5qoQ-04，事件857d2f8c54deec0c2bcecf31。** A/B/C入选节点8/9/11，Q=76.671/46.211/59.133。C−B升12.922，但C仍介于A/B之间，因此GA −12.922、GS −15.230；同类B相对A已出现很大结构/连接差异。另一个事件B为no_connection，单列不补0。原图及参考短转折、B的斜连和C的残余斜连可直接对照。
- **jh4fc5c5qoQ-12。** 两个事件C−B分别+7.725和−35.591。Z相同，X/Y/D同时变化，说明固定目标核心也会随实际源成员/背景发生响应改变；不是隔离了D的纯背景效应。
- **B6ByNegPMKs-11。** 逐图C−B仅−0.050，但两个事件分别+1.535与−1.635；三队都4节点。近零均值由方向抵消产生，不能写成所有成员组合都没有影响，也不是Q≥90的高分集中。
- **S9hNv5qa7GM-04。** 两个事件B均有6个入选节点却no_connection；存在各自达到半数、支持集合互不相交的入选组，以及没有原答覆盖全部入选节点的情况。节点过票不保证完整源环/可接受连接。是否为真实互斥表达必须看完整原答，而非只看两组都7票。
- **VFuaQ6m2Qom-04。** 四个事件C均no_connection，已选节点数不低却不能完成正式环。镜面/柜体附近的短折和源环不兼容是具体人工查看位置；已完整保留未入选节点、原答顺序和连接诊断，未将其按Q=0进入均值。
- **S9hNv5qa7GM-12。** 有的半队事件A/B仅3节点、below_four，其他事件可评且逐图幅度为正；这一例解释为何必须同时展示逐图均值和全部事件状态。

这些案例的原图PNG、所有合法原答、精确D/X/Y/Z、楼外类别和参考均在本阶段文件内。HTML可切换每个事件与任意原答，也能直接下载所选事件的完整JSON。每张图的具体参考角、像素坐标和人工问题均列在 `ALL_36_CASE_READING_INDEX.csv`，不止上述精选图。

## 5. 与20/7衔接：哪些变化可归于背景条件

相同图、相同精确X/Y/Z可连到100条14→20背景比较，覆盖72图。其中56条/45图是D14真子集D20，即在原7人背景上新增6人；另44条/37图还替换了部分背景人员。这两类不能合并成纯“替换比例效应”。下表在每个精确XYZ内先平均配对背景，再依次对块、池、图等权：

{table(pd.DataFrame(context))}

完整逐图、逐楼权重见 `MATCHED_BACKGROUND_CONTEXT_SUMMARY.csv`、`MATCHED_BACKGROUND_CONTEXT_IMAGES.csv`。共同68张Q可评图按各n原设计权重计算，GA为2.664→0.739，GS为2.631→0.706，C−B为6.176→3.872；该口径是共同图片比较，不是精确团队配对。两种口径都支持较大背景通常削弱这批主方向的幅度/质量差异，但新增背景成员、总人数、MV门槛与替换比例同时改变，不能从观察结果分离各项因果贡献。

## 6. 失败状态与有效支持

14/7：A为193 complete_conditional、3 no_connection、1 below_four；B为191 complete_conditional、5 no_connection、1 below_four；C为191 complete_conditional、6 no_connection。20/7：A为81完整与1 below_four，B为81完整与1 no_connection，C为80完整与2 no_connection。这些837个既有端点没有runtime fusion_exception。完整输出状态沿用冻结引擎的条件标志，并不改称已经人工确认的真值。

没有把“分数缺失”“节点不够”“无可接受完整连接”混为一个技术异常，也没有只用共同可评子集掩盖输出状态。`ENDPOINT_STATUS_COUNTS.csv`、`KEY_METRIC_SUPPORT.csv`给出分母；同房旧ABC的六端点共同可评属于另一个模块和分母。

## 7. 复现与验证

依次运行 `scripts/prepare_half_team.py`、`complete_half_traces.py`（已提供全部轨迹时只验证）、`analyze_half_mechanisms.py`、`finalize_half_report.py`、`build_half_case_viewer.py`；如需原图复核运行 `fetch_half_originals.py`（提供的36张均已CRC/SHA验证）。计算最低输入是本阶段的837个选择后原始标量、当前279事件/标签、当前池快照及随包冻结引擎；不依赖整个旧仓库。保存的原始几何和轨迹使汇总、票账和查看器可离线重建。

代码核验包括严格成员关系、端点标量对照、全体348轨迹数值对照、独立复核197/83/61/62和名单、各候选组真实人员计票、原图CRC/SHA、全部HTML选项/绘图坐标执行。静态原图/几何图已经目视检查。HTML不依赖网络。Node DOM/Canvas执行验证覆盖全部36图、116事件和348团队；另使用Chrome 156实际打开半队、同房、快慢案例和综合报告四个页面，均无脚本错误，中文、原图、几何与控件截图已目视检查。全组合执行与真实浏览器截图是两项分开的验证，详见stage06_synthesis/browser_acceptance。所有科学图和源CSV不依赖该界面才能查看。

原32图数值检查点留在 `checkpoints/numerical_union32/`，最终以36图入口为准。旧v2、旧focused-only及并行ABC成果均保留原身份。
'''
    (OUT/'README.md').write_text(report)
    checks={'context_links':len(links),'nested_links':int(links.D14_subset_D20.sum()),'context_image_rows':len(context_images),'common_direction_diagnostic_images':diag_images,'case_reference_corner_event_rows':len(shared),'metric_support':supports,'no_new_experimental_teams':True,'report_source_tables':['MAIN_CHECKED_SUMMARY.csv','ALL_METRICS_IMAGE_SUMMARY.csv','KEY_METRIC_SUPPORT.csv','MATCHED_BACKGROUND_CONTEXT_SUMMARY.csv','ENDPOINT_STATUS_COUNTS.csv']}
    (OUT/'REPORT_SOURCE_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'contexts':len(context_images),'shared_displacement_images':diag_images,'report_bytes':(OUT/'README.md').stat().st_size}))
if __name__=='__main__':main()
