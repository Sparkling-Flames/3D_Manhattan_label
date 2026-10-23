#!/usr/bin/env python3
"""Write explanatory tables/Chinese case note from the six saved endpoints."""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json
import numpy as np
import pandas as pd

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--projection-source',type=Path,required=True);a=ap.parse_args();t=a.out/'tables'
    e=pd.read_csv(a.case/'STRICT_ABC_EVENT.csv.gz').iloc[0];d=pd.read_csv(t/'SIX_TEAM_METRICS.csv');g=pd.read_csv(a.case/'geometry/EVENT_GEOMETRY_RESULTS.csv.gz');rows=[]
    metrics=['B8L2','D10','S_bottom_deg','dir','Hmean','Hcenter','iou_2d','omission','extension','boundary_loss','direction_loss','global_height_loss','local_height_loss','height_loss','floor_area_camera_h2','height_mean_h','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
    for view,z in d.groupby('view'):
        x=z.set_index('arm');p=g[g.view.eq(view)].set_index('comparison')
        for m in metrics:
            A=float(x.loc['A',m]);B=float(x.loc['B',m]);C=float(x.loc['C',m]);rows.append(dict(event_id=e.event_id,view=view,image=x.iloc[0].image,metric=m,A=A,B=B,C=C,B_minus_A=B-A,C_minus_A=C-A,C_minus_B=C-B,same_amplitude=abs(B-A),symmetric_cross_amplitude=(abs(C-A)+abs(C-B))/2,extra_cross_amplitude=(abs(C-A)+abs(C-B))/2-abs(B-A)))
        for m in ['bev_mean_h','top_mean_h','angle_deg']:
            AB=float(p.loc['AB',m]);AC=float(p.loc['AC',m]);BC=float(p.loc['BC',m]);rows.append(dict(event_id=e.event_id,view=view,image=x.iloc[0].image,metric='team_pair_'+m,same_amplitude=AB,symmetric_cross_amplitude=(AC+BC)/2,extra_cross_amplitude=(AC+BC)/2-AB))
    diff=pd.DataFrame(rows);diff.to_csv(t/'EXACT_RESPONSE_DIFFERENCES.csv',index=False)
    time=[]
    for view,z in d.groupby('view'):
        x=z.set_index('arm')
        for pair in ['AB','AC','BC']:
            fr,to=pair;f=x.loc[fr];q=x.loc[to];legal=bool(f.recorded_time_eligible and q.recorded_time_eligible and f.time_source_kinds==q.time_source_kinds)
            time.append(dict(event_id=e.event_id,view=view,image=f.image,comparison=pair,from_team_key=f.team_key,to_team_key=q.team_key,from_time_kind=f.time_source_kinds,to_time_kind=q.time_source_kinds,same_semantics_time_pair=legal,from_seconds=f.recorded_time_total_seconds if legal else np.nan,to_seconds=q.recorded_time_total_seconds if legal else np.nan,seconds_delta=q.recorded_time_total_seconds-f.recorded_time_total_seconds if legal else np.nan,time_ratio=q.recorded_time_total_seconds/f.recorded_time_total_seconds if legal else np.nan,missing_reason='' if legal else 'A_contains_mixed_record_semantics'))
    times=pd.DataFrame(time);times.to_csv(t/'EXACT_SAME_SEMANTICS_TIME_PAIRS.csv',index=False)
    lines=[]
    for r in d.itertuples():lines.append(f'|{r.image}|{r.arm}|{r.B8L2:.3f}|{r.D10:.3f}|{r.S_bottom_deg:.4f}|{r.dir:.4f}|{r.Hmean:.5f}|{r.Hcenter:.5f}|{int(r.fusion_turn_n)}|')
    dlines=[]
    for view,z in diff.groupby('view'):
        for r in z[z.metric.isin(['B8L2','D10','team_pair_bev_mean_h'])].itertuples():dlines.append(f'|{r.image}|{r.metric}|{r.same_amplitude:.6f}|{r.symmetric_cross_amplitude:.6f}|{r.extra_cross_amplitude:+.6f}|')
    txt=f'''# 一个完整严格ABC机制例：同样四转折，换人的位置作用随视角变化

**两幅图的六队都保留相同的四转折；跨类队C的Q在两个视角均较高，但“同类换人”B−A从−1.652翻转为+4.728。与此同时，同角点数下跨类几何距离小于同类距离。这个例子说明类别构成造成的质量差异可以通过定位、方向与尺度出现，不必先出现节点增减；几何改变量也不能直接替代参照质量变化。**

本例是新登记大块设计 `same_room_strict_abc_rebuilt_20261023_v1` 中按event_id字典序得到的首个事件 `{e.event_id}`，不是按Q筛出的最佳例，也不是遗失上一轮端点的恢复。图和票账只读取已完成的六个新原生端点，本步骤没有再融合、评分或调类。输入commit `{e.input_commit}`；同房关系版本`{e.relation_version}`。

## 1. 到底是谁换谁

两幅图为`pa4otMbVnkk-42`、`pa4otMbVnkk-44`，既有直接声明组G130，普通Manual、范围可比，难度为简单—简单。当前结构分类V3_BEHAVIOR粗类，楼外折`pa4otMbVnkk`。本折M2按历史非冗余转折中心对齐为“常规转折”，M3为“较多转折”；这里的编号不跨折直接合并。

|块/队|中文角色|实际成员|
|---|---|---|
|D|保留的较多转折成员|W109|
|X|原常规转折块|W030、W101、W103、W113、W131|
|Y|同类新常规转折块|W106、W107、W108、W110、W118|
|Z|跨类较多转折块|W102、W115、W122、W126、W130|
|A=D∪X|5常规+1较多转折|D+X|
|B=D∪Y|5常规+1较多转折|D+Y|
|C=D∪Z|6较多转折|D+Z|

**n=6、m=5、m/n=5/6，D非空。** D/X/Y/Z四块互不重叠，两视角使用完全相同的具体成员。本例是高替换比例混合团队，不代表少于半队替换。共同池34人，27名源类、7名目标类；实际用到16名不同成员，每视角16份原答。

楼外调整Q均值X−3.032、Y−2.164、Z+14.380，Z的历史质量明显较高；因此本例能说明“这一历史类别组织出的实际替换怎样起效”，不能当作排除了历史Q差异的纯结构效应。块历史字段及语义原样保存在严格设计，不按该图Q选择成员。

## 2. 原图、原答和几何

`figures/CASE_OVERVIEW_ERP_BEV.png`并排给出两个实际Release原图与冻结参考/ABC融合，以及每个相机局部坐标的BEV。A蓝、B橙、C绿，参考黑白。`ALL_MEMBERS_RAW_BEV.png`显示六队每位成员的原答，不旋转对齐、不改形状；`LOCAL_RAW_FUSION_REFERENCE.png`显示两图的局部遮挡墙角及原答/融合/参考。

原图可见同一装饰餐厅的大开口、墙板、镜面、天花板装饰和遮挡家具。局部底角落在桌面或家具后方，边界定位需要由可见墙面线索延续。这是对实际可见条件的描述，本轮没有另改范围或参考。两视角局部窗按各自参考角点的ABC几何偏移选取，**没有认定两个裁剪角就是同一物理角**；人员和团队的跨视角身份完全相同。

全景墙边由3D直边采样后反投影为ERP曲线，并在经度接缝处分断；没有直接用全景直线连接角点。参考/原答/保存几何为1024×512坐标，叠到2048×1024原图时缩放2倍。BEV与高度以相机高度h为单位，**不是米**，两幅BEV各用自己的相机坐标，未做跨视角刚性配准。

## 3. 同一块调整，质量作用怎样变化

|视角|队|Q(B8L2)|D10|底面角误差°|方向误差°|Hmean|Hcenter|实际转折|
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

- -42：B−A=−1.652，C−A=+6.142，C−B=+7.794。
- -44：B−A=+4.728，C−A=+7.303，C−B=+2.575。

同类调整两边都发生实际变化，Q符号反向；跨类调整的Q符号同向。它们都不是“两边没变化”的方向一致。六队转折均4，短边转折与冗余点均0。

|视角|量|同类幅度|对称跨类幅度|跨类−同类|
|---|---|---:|---:|---:|
{chr(10).join(dlines)}

Q/D10幅度与同角点平均几何距离的相对顺序不同：C的位置处在更接近参考的区域，但未必离A或B更远。-42的A地面面积偏大、B偏小，C靠近参考；-44的A主要有底面方向偏斜、B仍有范围外扩，C更接近参考。全部分项值保存在`SIX_TEAM_METRICS.csv`，无需由类别名称推断机制。

改善也不要求所有分项同向。-44的C相对B，底面角误差0.1023°对0.2518°、方向0.2710°对0.3047°、Hmean0.00103对0.00376更低，但Hcenter0.00252高于0.00046、local_height_loss也略高。总Q仍提高，不能写成每个边界/高度分项同时改善。

## 4. 票账解释：节点已齐，差异来自位置估计

24个保存身份组（6队×4角）均为**6名不同成员支持，门槛3**，top/bottom/joint支持也均6；24条输出边的直接及投影连接支持也均6，无最高支持并列。因此本例没有因补进某类而把缺失节点推过票数门槛，也没有通过新增转折改善Q。

保存的所有24个组中心，四个ERP坐标均严格等于该身份组全体成员的逐坐标中位数。`MEDIAN_BRACKETS.csv`列出96个坐标中位数的上下秩成员、数值和完整排序；`IDENTITY_MEMBERS.csv`列出144条实际贡献、object_id及原pair索引。换块改变了参与位置中位数的原答，所以即使节点和支持数完全相同，形状、方向与范围仍改变。

这份票账支持群体位置估计的机制，不把中位数附近某一位成员描述为“带动”全队。保存的`ring_confirmed=False`原样保留：几何有完整候选且可评分，但该字段不是新增的人工连接裁定。固定环序仍是“最支持的完整投影原环”；没有改对应、定位或连接规则。

## 5. 时间与失败

A在两图都混合继承v1已核时间与新来源报告时间，因此正式记录劳动无资格；A/B/C三臂时间不能合并比较。B、C各自全员时间齐全且都使用`user_processed_reported_not_raw_log_replayed`，可在同来源上比较：

|视角|B记录劳动秒|C记录劳动秒|C−B秒|
|---|---:|---:|---:|
|-42|516.015|874.797|+358.782|
|-44|632.632|814.434|+181.802|

这是报告记录的劳动合计，不是排队或真实交付时间。BC升质同时增加记录劳动。六次尝试都完整且可评分，新增失败0/6；该分母仅对应这个完整事件，不能代替全实验失败率。

## 6. 可复核数据与运行

本目录新增的是图、票账投影、逐分项差值和说明。完整精确设计及六队全state在`../../engine/first_complete_event/`；完整实际原图在`../originals/`，Release索引与按需取图代码在`../source/`。不重复拷贝原件，`STATE_SOURCE_INDEX.csv`保存团队键到原state文件/行号；`VIEW_IMAGE_INDEX.csv`保存原图SHA、参考ID、裁剪范围；`USED_RAW_ANSWERS.csv`保留32份实际使用原答。

从`work/rebuild_large_block_20261023`根运行：

```bash
python cases/first_event/code/build_case.py --case engine/first_complete_event --originals cases/originals --out cases/first_event
python cases/first_event/code/describe_case.py --case engine/first_complete_event --out cases/first_event --projection-source engine/frozen_repo/research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py
```

运行依赖Python3.12、numpy、pandas、matplotlib、Pillow；不调用native融合环境。`CASE_READ_RECEIPT.json`记录每张小表的完整读取、唯一键与全部输入依赖SHA。图像已实际查看，表中的feature_id只在本团队内有效，不把不同队的node_000直接当作跨视角同一墙角。

**采用位置：** 可作为“历史类别倾向与具体图片响应不同”和“Q、结构数、几何距离不能互相替代”的机制例。它保留一次明确的同类作用视角翻转与两边跨类升质，不据此单例判断总体跨类效应大小，也不把较多转折角色命名为本图补结构专家。
'''
    (a.out/'README_ZH.md').write_text(txt)
    (a.out/'requirements.txt').write_text('numpy==2.3.5\npandas==2.2.3\nmatplotlib==3.10.8\nPillow>=10\n')
    deps=[]
    def dependency(p,purpose):
        b=p.read_bytes();deps.append(dict(path=str(p),purpose=purpose,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    for path,purpose in [(a.case/'STRICT_ABC_EVENT.csv.gz','new_exact_design'),(a.case/'FROZEN_TWO_POOLS.json.gz','original_answers_and_frozen_references'),(a.case/'native/ENDPOINT_SCALARS.csv.gz','six_new_native_scalars'),(a.case/'geometry/EVENT_GEOMETRY_RESULTS.csv.gz','six_native_pair_geometry_metrics'),(a.case/'FROZEN_CLASS_ROLES_AND_MEMBERS.csv','frozen_LOBO_display_roles'),(a.projection_source,'frozen_projection_convention')]:dependency(path,purpose)
    for path in (a.case/'native/parts').rglob('*.geometry_state.jsonl.gz'):dependency(path,'six_new_native_fullstates')
    (a.out/'DEPENDENCIES.json').write_text(json.dumps(dict(source_commit=e.input_commit,dependencies=deps),ensure_ascii=False,indent=2)+'\n')
    counts={};files=[]
    for p in sorted(t.glob('*.csv')):
        data=p.read_bytes();reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''));n=0
        for row in reader:assert None not in row;n+=1
        counts[p.name]=n;files.append(dict(path=p.relative_to(a.out).as_posix(),rows=n,fields=reader.fieldnames,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),read_to_eof=True))
    ids=pd.read_csv(t/'IDENTITY_GROUPS.csv');mem=pd.read_csv(t/'IDENTITY_MEMBERS.csv');raw=pd.read_csv(t/'USED_RAW_ANSWERS.csv');br=pd.read_csv(t/'MEDIAN_BRACKETS.csv');ring=pd.read_csv(t/'RING_EDGES.csv')
    assert not d.duplicated('team_key').any() and not ids.duplicated(['team_key','feature_id']).any();assert set(mem.team_key)==set(d.team_key)==set(ids.team_key);assert set(mem.object_id)==set(raw.object_id);assert ids.identity_support.eq(6).all() and ids.minimum_support.eq(3).all();assert ids[['top_support','bottom_support','joint_support']].eq(6).all().all();assert ring[['direct_support','projected_support']].eq(6).all().all();assert br.matches_saved_center.all();assert d.fusion_turn_n.eq(4).all()
    assert times.same_semantics_time_pair.sum()==2 and times[times.same_semantics_time_pair].comparison.eq('BC').all()
    receipt=dict(status='passed',operation='read_new_case_tables_to_eof_and_exact_key_checks',event_id=e.event_id,files=files,rows=counts,teams=6,original_used_answers=32,identity_groups=24,identity_members=144,median_coordinates=96,original_projection_source_sha=deps[5]['sha256'],new_fusion_in_visualization=0,raw_points_reference_candidate_projection_checks='in build_case.py passed',actual_figures_viewed=['CASE_OVERVIEW_ERP_BEV.png','ALL_MEMBERS_RAW_BEV.png','LOCAL_RAW_FUSION_REFERENCE.png','IDENTITY_SUPPORT.png'])
    (a.out/'CASE_READ_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'event_id':e.event_id,'tables':len(files),'counts':counts,'status':'ready'},ensure_ascii=False))

if __name__=='__main__':main()
