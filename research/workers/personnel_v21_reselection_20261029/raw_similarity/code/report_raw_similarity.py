#!/usr/bin/env python3
"""Summarize all frozen methods' heldout-building raw-answer distances."""
from pathlib import Path
import json,os,io
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_raw_mpl')
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
def save_figure(fig,path,**kwargs):
 buf=io.BytesIO();fig.savefig(buf,format=path.suffix.lstrip('.'),**kwargs);tmp=path.with_name(path.name+'.writing')
 with tmp.open('wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
 tmp.replace(path)

W=Path(__file__).resolve().parents[2];O=W/'raw_similarity'
font=W/'cases/source/NotoSansCJKsc-Regular.otf'
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
d=pd.read_csv(O/('RAW_CLASS_DISTANCE_SUMMARY.csv' if (O/'RAW_CLASS_DISTANCE_SUMMARY.csv').exists() else 'RAW_CLASS_DISTANCE_SUMMARY.csv.gz'))
z=d[(d.condition=='manual')&(d.layer=='ordinary_manual')&(d.support=='common45_known')&(d.scope_summary=='ALL_TARGETS')&(d.difficulty_summary=='ALL')].copy()
z.to_csv(O/'MANUAL_COMMON45_ALL_METHOD_RESULTS.csv',index=False,encoding='utf-8-sig')
focus=['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3','OPPSTRUCT_K4','OPPGEOM_K3','OPPJOINT_K3','MSDGEOM_SCOPE_K3','RFUSE_GEOM_K2','TARGET_RFUSE_GEOM_K3','TARGET_RFUSE_GEOMQ_K3','V3_JOINT_QT_FINE','Q_MEDIAN2']
t=z[z.method.isin(focus)&z.metric.isin(['geometry_pair_angle','geometry_bev_distance'])&z.subset.eq('same_corner_count')]
t.to_csv(O/'MAIN_RAW_SAME_COUNT_COMPARISON.csv',index=False,encoding='utf-8-sig')
fig,axs=plt.subplots(1,2,figsize=(14,7.5),sharey=True)
for ax,metric,title in zip(axs,['geometry_pair_angle','geometry_bev_distance'],['同底点数：顶/底联合匹配角距（度）','同底点数：1−底面 IoU']):
 rows=t[t.metric.eq(metric)].set_index('method').reindex(focus)
 y=np.arange(len(rows))
 for pos,r in zip(y,rows.itertuples()):ax.plot([r.image_within,r.image_cross],[pos,pos],color='#b2bec3',lw=2)
 ax.scatter(rows.image_within,y,c='#2471a3',s=34,label='同类原答');ax.scatter(rows.image_cross,y,c='#d95f28',s=34,label='跨类原答')
 ax.set_title(title,fontsize=12);ax.set_yticks(y,focus,fontsize=9);ax.grid(axis='x',alpha=.2);ax.invert_yaxis();ax.set_xlabel('先目标、后图片等权的平均距离')
axs[0].legend(loc='lower right');fig.suptitle('45套分类共同人员支持上的原答相似性：代表家族并列，完整45法另见表',fontsize=14)
fig.tight_layout();save_figure(fig,O/'RAW_SAME_COUNT_FAMILY_COMPARISON.png',dpi=170);save_figure(fig,O/'RAW_SAME_COUNT_FAMILY_COMPARISON.pdf');plt.close(fig)
# Main usable numerical prose, generated directly from the complete summary.
lines=['# 新版原答相似性：类别能否描述同图的真实标法','',
'这一项使用 v2.1 全部合法目标池内的原始完整标注。不同空间不互相配对；全部原答对的几何仅计算一次，再套用已经冻结的45套楼外标签。它回答的是“同类的人是否在未参与建类的建筑上画得更相近”，不代替实际融合换人检验。','',
'## 实际范围与比较口径','',
'原答距离库存共有 **134,197 对、294 个目标池**。Manual、Semi、普通、门洞与特殊范围分别汇总。每法自身全部已知人员与45法共同已知人员各保存一套结果。未知不补类别；同一池至少有4个可用类内对和4个跨类对才计算该池对照，未估计的池/方法/子集及原因全部列入缺口表。','',
'每个池先对类内各类均值等权，再对跨类各无序类别对均值等权；随后图内合法目标等权、图片等权，并另保存建筑等权结果。单人类没有可估的类内距离，不以零波动计入。几何角距使用完整顶底点对的球面 Hungarian 匹配；同底点数子集单列。9°水平对应诊断与整份原答旧分簇/融合阈值是不同参数。','',
'## Manual 普通目标：同底点数时的代表结果','',
'以下采用共同已知人员支持、全部合法目标、楼外标签；距离越小表示原答越相近。这里的206是可比较的合法普通Manual图片数，不能写成“原主目标206池全覆盖”。完整45法和所有难度/条件均见结果表。','',
'|方法|图片/建筑|同类联合角距°|跨类联合角距°|跨类更远图片|同类1−IoU|跨类1−IoU|','|---|---:|---:|---:|---:|---:|---:|']
for m in focus:
 a=t[(t.method==m)&(t.metric=='geometry_pair_angle')].iloc[0];b=t[(t.method==m)&(t.metric=='geometry_bev_distance')].iloc[0]
 lines.append(f'|{m}|{int(a.images)}/{int(a.buildings)}|{a.image_within:.3f}|{a.image_cross:.3f}|{int(a.images_cross_larger)}/{int(a.images)}|{b.image_within:.4f}|{b.image_cross:.4f}|')
lines += ['', '![同点数原答距离](RAW_SAME_COUNT_FAMILY_COMPARISON.png)','',
'## 解释和用途','',
'45套名单是本轮Manual主任务的冻结候选。Semi表是同一套标签在Semi原答中的辅助观察；它与Semi自身V3分类的独立构成实验分别解释，不将两者合并。','',
'结构类输入本就包含结构表达，因此“同类转折数接近”主要是类别解释。楼外同点数原答的顶/底匹配角距和底面形状差异更直接说明，类别是否还关联了位置与形状倾向。角距、BEV距离、时间和质量差距分别保留；质量接近不自动等于形状相近。','',
'联合匹配角距只对可配对的角点求平均，异点数时还必须看未匹配节点和结构差；不把该角距单独称为完整形状距离。因此本文专列同底点数子集。','',
'这些原答结果允许一套分类在“解释怎样标”上有用，即便其融合换类效应只在部分规模/背景成立。最终主方法仍需结合已冻结 ABC、配比和失败结果选择；本文没有按原答距离单独宣布分类优胜，也没有从此推断成员完全可互换。','',
'## 文件与复算','',
'- `RAW_PAIR_DISTANCES.csv.gz`：所有134,197个实际配对的端点身份、几何、结构、Q/D10及来源内时间差；几何未重算质量。',
'- `RAW_CLASS_DISTANCE_BY_POOL.csv.gz`、`RAW_CLASS_DISTANCE_BY_IMAGE.csv.gz`：逐目标/逐图类内、类间值与真实分母。',
'- `RAW_CLASS_DISTANCE_SUMMARY.csv`：全部45方法、条件、范围、难度、支持口径和同点数子集。',
'- `RAW_CLASS_DISTANCE_UNESTIMABLE.csv.gz`：不满足类内/跨类配对机会的具体行。',
'- `COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz`：与DSTRUCT K3、Q二分在完全相同目标和人员支持上的差异。',
'- `COMMON45_BASELINE_PAIRED_SUMMARY.csv`：上述完全配对比较按目标→图→楼汇总；由 `code/summarize_paired_baselines.py` 生成。',
'- `MANUAL_COMMON45_ALL_METHOD_RESULTS.csv`、`MAIN_RAW_SAME_COUNT_COMPARISON.csv`：主报告可直接用的小表。',
'- `code/compare_v21_raw_pairs.py --part compare` 从已有配对/方法检查点恢复；逐池表完整后直接运行 `code/complete_from_pool_rows.py` 逐方法保存全部汇总，无需再计算原答几何。`code/report_raw_similarity.py` 重建本说明与图。','']
difficulty=pd.read_csv(O/'RAW_MAIN_DIFFICULTY_TABLE.csv')
focus_d=difficulty[(difficulty.method=='DSTRUCT_K3')&(difficulty.subset=='same_corner_count')]
insert=['## 难度与结构机会：不要求所有分项同向','',
'DSTRUCT K3 的同底点数角距，在正式困难条件下平均分离更大，但同向图片比例并不比简单条件更高。这与“困难图应全面更分离”不是同一个结论。中等条件的底面差异则接近零。','',
'|目标难度|图片数|同类联合角距°|跨类联合角距°|跨类更远图片|同类1−IoU|跨类1−IoU|','|---|---:|---:|---:|---:|---:|---:|']
for grade in ['简单','中等','困难','未分级']:
 a=focus_d[(focus_d.difficulty==grade)&(focus_d.metric=='geometry_pair_angle')].iloc[0]
 b=focus_d[(focus_d.difficulty==grade)&(focus_d.metric=='geometry_bev_distance')].iloc[0]
 insert.append(f'|{grade}|{int(a.images)}|{a.within:.3f}|{a.cross:.3f}|{int(a.positive_images)}/{int(a.images)}|{b.within:.4f}|{b.cross:.4f}|')
insert += ['',
'全部点数的困难图中，非冗余转折数差同类/跨类为 1.625/2.574，33/37 图跨类更大；简单图同类/跨类仅 0.101/0.129，109/130 图在这个结构差分项没有类间优势。这说明该结构分类的区别需要结构机会才能充分显示，不该要求多数四角简单目标也画出不同的结构。',
'未知难度行只来自实际未正式分级的目标，不继承原主空间标签；同一图片在不同目标难度行可能重复出现，不能把各行图片数直接相加作为独立总数。','']
pos=lines.index('## 文件与复算');lines[pos:pos]=insert
paired=pd.read_csv(O/'COMMON45_BASELINE_PAIRED_SUMMARY.csv')
matched=paired[(paired.condition=='manual')&(paired.layer=='ordinary_manual')&(paired.subset=='same_corner_count')&(paired.metric=='geometry_pair_angle')&(paired.scope_summary=='ALL_TARGETS')]
insert=['## 与Q二分及旧DSTRUCT的共同图片对照','',
'方法各自可比较的图片和目标不完全相同，不能直接相减上表均值。以下先保留双方都可比较的同一目标、相同共同人员支持，再图内目标等权。比较量为“跨类角距−同类角距”，单位是度；它衡量标法区分，不表示融合质量收益。','',
'|候选/对照|共同图片|候选间隔|对照间隔|间隔增量|候选间隔较大图片/建筑|','|---|---:|---:|---:|---:|---:|']
for method,baseline in [('DSTRUCT_K3','Q_MEDIAN2'),('TARGET_DSTRUCT_K3','Q_MEDIAN2'),('OPPSTRUCT_K3','Q_MEDIAN2'),('OPPGEOM_K3','Q_MEDIAN2'),('TARGET_DSTRUCT_K3','DSTRUCT_K3')]:
 a=matched[(matched.method==method)&(matched.baseline==baseline)].iloc[0]
 insert.append(f'|{method} / {baseline}|{int(a.images)}|{a.candidate_gap_image_mean:.3f}|{a.baseline_gap_image_mean:.3f}|{a.gap_gain_image_mean:+.3f}|{int(a.candidate_gap_larger_images)}/{int(a.images)}图；{int(a.candidate_gap_larger_buildings)}/{int(a.buildings)}楼|')
insert+=['',
'DSTRUCT及机会结构/几何类在多数共同图片上，比简单Q二分更能描述同点数标法距离。TARGET_DSTRUCT相对原DSTRUCT的平均间隔略大，但只在89/206图较大；原答相似性这一用途并不支持“接上新目标后普遍更优”的说法。其是否更适合实际换类，还要看同目标的真实ABC和构成结果。','']
pos=lines.index('## 文件与复算');lines[pos:pos]=insert
(O/'RAW_ANSWER_SIMILARITY_ZH.md').write_text('\n'.join(lines),encoding='utf-8')
print('saved',len(z),'summary rows',flush=True)
