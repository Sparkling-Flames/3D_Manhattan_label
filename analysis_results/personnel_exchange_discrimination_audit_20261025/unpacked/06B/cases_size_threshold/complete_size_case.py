#!/usr/bin/env python3
"""Exact n14/n15 mechanism from saved six-endpoint replays; no alternative fusion."""
from pathlib import Path
import gzip,hashlib,importlib.util,io,json,os,shutil,string
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
E14='3b15e1f073610cfe79b11d8a';E15='d8c03de1c870a22a3d448441'
spec=importlib.util.spec_from_file_location('case_common',ROOT/'cases/build_exchange_cases.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def load(eid):return json.load(gzip.open(OUT/eid/'CASE_GEOMETRY.json.gz','rt'))
def readframe(rel):return pd.read_csv(ROOT/rel,low_memory=False)

def save_inputs(a,b):
    events=readframe('design/size_paths/EVENTS_EXACT.csv.gz');pair=events.loc[events.event_id.isin([E14,E15])].sort_values('n');pair.to_csv(OUT/'SIZE_PAIR_EXACT.csv',index=False)
    for key in ['X','Y','Z']:
        assert a['event'][key]==b['event'][key]
    for arm in ['A','B','C']:
        s1=set(a['event'][arm+'_members'].split('|'));s2=set(b['event'][arm+'_members'].split('|'))
        assert s1<s2 and s2-s1=={'W117'}
    metrics=readframe('results/size_paths/EVENT_METRICS.csv.gz');image=metrics.loc[metrics.image.eq('jh4fc5c5qoQ-12')&metrics.method.eq('DSTRUCT_K3')]
    image.to_csv(OUT/'SAME_IMAGE_TWO_PATHS_METRICS.csv.gz',index=False,compression='gzip')
    image.loc[image.path_id.eq(a['event']['path_id'])].to_csv(OUT/'SELECTED_PATH_ALL_N_METRICS.csv',index=False)
    image.loc[image.n.isin([14,15])].to_csv(OUT/'TWO_ANCHOR_N14_N15_METRICS.csv',index=False)
    steps=readframe('analysis/size_paths/PATH_STEP_CHANGES.csv.gz');steps=steps.loc[steps.image.eq('jh4fc5c5qoQ-12')&steps.method.eq('DSTRUCT_K3')];steps.to_csv(OUT/'SAME_IMAGE_ALL_STEPS.csv.gz',index=False,compression='gzip');steps.loc[steps.n.eq(15)&steps.previous_n.eq(14)].to_csv(OUT/'TWO_ANCHOR_STEP_CHANGES.csv',index=False)
    labels=readframe('design/size_paths/FROZEN_LABELS.csv.gz');labels=labels.loc[labels.method.eq('DSTRUCT_K3')&labels.heldout_building.eq('jh4fc5c5qoQ')];labels.to_csv(OUT/'LOBO_LABELS.csv',index=False)
    opp=readframe('recovery/prior_population/research/workers/personnel_population_curves_v2_20261023/inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv');opp=opp.loc[opp.image.eq('jh4fc5c5qoQ-12')];assert opp.reference_id.iloc[0]==a['pool']['reference']['target_id'];opp.to_csv(OUT/'DIFFICULTY_OPPORTUNITY.csv',index=False)
    rows=[]
    for n,eid in [(14,E14),(15,E15)]:
        q=pd.read_csv(OUT/eid/'ABC_SCALARS.csv');q['n']=n;q['event_id']=eid;rows.append(q)
    pd.concat(rows,ignore_index=True).to_csv(OUT/'SIX_ENDPOINT_SCALARS.csv',index=False)
    entrant=next(x for x in b['pool']['records']if x['worker_id']=='W117');(OUT/'ENTRANT_W117_RAW.json').write_text(json.dumps(entrant,ensure_ascii=False,indent=2))
    return image,steps

def across_n(a,b):
    groups=[];links=[];obsrows=[];summ=[];votes=[]
    for n,data,eid in [(14,a,E14),(15,b,E15)]:
        vv=pd.read_csv(OUT/eid/'VOTES.csv');vv['n']=n;votes.append(vv)
        for role,st in data['states'].items():
            for g in st['identity_groups']:
                v=vv.loc[vv.role.eq(role)&vv.feature_id.eq(g['feature_id'])].iloc[0]
                pp=np.asarray([x['points']for x in g['members']]);med=np.median(pp,axis=0);center=np.asarray(g['center'])
                assert np.max(abs(med-center))<1e-7
                groups.append({'n':n,'role':role,'feature_id':g['feature_id'],'reference_corner':v.reference_corner,'support':g['support'],'threshold':st['minimum_support'],'selected':g['selected'],'center_x':center[0,0],'center_top_y':center[0,1],'center_bottom_y':center[1,1],'members':'|'.join(sorted(x['worker']for x in g['members'])),'median_error_px':float(np.max(abs(med-center)))})
                for x in g['members']:
                    obsrows.append({'n':n,'role':role,'feature_id':g['feature_id'],'reference_corner':v.reference_corner,'selected':g['selected'],'worker_id':x['worker'],'object_id':x['id'],'pair_index':x['pair_index'],'raw_x':x['points'][0][0],'raw_top_y':x['points'][0][1],'raw_bottom_y':x['points'][1][1]})
    for role in ['A','B','C']:
        sa,sb=a['states'][role],b['states'][role];summ.append({'role':role,**base.partition_changes(sa,sb)})
        for ga in sa['identity_groups']:
            for gb in sb['identity_groups']:
                common=base.obs(ga)&base.obs(gb)
                if common:links.append({'role':role,'before_group':ga['feature_id'],'after_group':gb['feature_id'],'shared_observations':len(common),'shared_workers':'|'.join(sorted(x['worker']for x in ga['members']if(str(x['id']),int(x['pair_index']))in common)),'before_support':ga['support'],'after_support':gb['support'],'before_selected':ga['selected'],'after_selected':gb['selected']})
    pd.DataFrame(groups).to_csv(OUT/'ALL_GROUP_MEDIANS.csv',index=False);pd.DataFrame(obsrows).to_csv(OUT/'ALL_GROUP_OBSERVATIONS.csv',index=False);pd.DataFrame(links).to_csv(OUT/'GROUP_LINKS_ACROSS_N.csv',index=False);pd.DataFrame(summ).to_csv(OUT/'COMMON_OBSERVATION_REGROUPING_ACROSS_N.csv',index=False)
    v=pd.concat(votes,ignore_index=True);v.to_csv(OUT/'ALL_VOTES_N14_N15.csv',index=False)
    comp=[]
    for role in ['A','B','C']:
        for c in range(1,len(a['pool']['reference']['points_1024x512'])//2+1):
            row={'role':role,'reference_corner':c}
            for n in [14,15]:
                z=v.loc[v.n.eq(n)&v.role.eq(role)&v.reference_corner.eq(c)]
                for field in ['feature_id','support','selected','center_x','center_top_y','center_bottom_y','workers','reference_pair_error_deg']:
                    row[f'n{n}_{field}']=z.iloc[0][field]if len(z)else None
            comp.append(row)
    pd.DataFrame(comp).to_csv(OUT/'REFERENCE_GROUPS_ACROSS_N.csv',index=False)
    return v,pd.DataFrame(summ)

def font_setup():
    target=OUT/'fonts/NotoCJK-Case-Subset.otf';target.parent.mkdir(exist_ok=True)
    if not target.exists():
        from fontTools import subset
        from fontTools.ttLib import TTFont
        source=ROOT/'figures/fonts/NotoSansCJKsc-Regular.otf';font=TTFont(source);opt=subset.Options();opt.name_IDs=['*'];opt.name_legacy=True;opt.name_languages=['*'];sub=subset.Subsetter(options=opt);sub.populate(unicodes=[ord(c)for c in set(Path(__file__).read_text()+string.printable+'−Δ→')]);sub.subset(font);font.save(target);shutil.copy2(ROOT/'figures/fonts/OFL.txt',target.parent/'OFL.txt')
    return target

def plot_comparison(a,b,v,metrics):
    os.environ['MPLCONFIGDIR']=str(OUT/'.mpl');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font=font_setup();font_manager.fontManager.addfont(font);plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'font.size':10,'axes.unicode_minus':False,'svg.fonttype':'path'})
    base.native.setup();ref=a['pool']['reference']['points_1024x512'];c14=a['states']['C']['candidate']['points'];c15=b['states']['C']['candidate']['points'];raw=next(x['points']for x in b['pool']['records']if x['worker_id']=='W117')
    fig=plt.figure(figsize=(18,10.5));gs=fig.add_gridspec(2,3,left=.045,right=.98,bottom=.14,top=.88,wspace=.23,hspace=.31)
    def erp(ax,pp,c,lw=1.7,ls='-'):
        for top in [False,True]:
            for seg in base.segments(pp,top):ax.plot(seg[:,0],seg[:,1],c=c,lw=lw,ls=ls)
        for pair in np.asarray(pp).reshape(-1,2,2):ax.plot(pair[:,0],pair[:,1],c=c,lw=lw*.55,ls=ls)
    def bev(ax,pp,c,lw=1.7,ls='-'):
        f,h=base.layout(pp);q=np.vstack([f,f[0]]);ax.plot(q[:,0],q[:,1],c=c,lw=lw,ls=ls)
    original=plt.imread(OUT/'originals/jh4fc5c5qoQ-12.png')
    for j,(pp,title,c)in enumerate([(c14,'C：14人，7票门槛\nQ 96.60；8个节点','#247c5e'),(c15,'C：15人，8票门槛\nQ 45.46；6个节点','#c35a35'),(raw,'新增的同一人 W117\n原答4节点，同时进入A/B/C','#8960a2')]):
        ax=fig.add_subplot(gs[0,j]);ax.imshow(original,extent=[0,1024,512,0]);erp(ax,ref,'white',2.3,'--');erp(ax,ref,'#24292e',.8,'--');erp(ax,pp,c,2);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(title,fontsize=12)
    ax=fig.add_subplot(gs[1,0]);bev(ax,ref,'#24292e',1.3,'--');bev(ax,c14,'#247c5e',2);bev(ax,c15,'#c35a35',2);fr,_=base.layout(ref)
    for i,offset in [(3,(12,22)),(5,(15,-25))]:ax.annotate('R'+str(i+1),fr[i],xytext=offset,textcoords='offset points',arrowprops={'arrowstyle':'-','color':'#555'},fontsize=10)
    ax.scatter([0],[0],marker='+',c='black');ax.set_aspect('equal');ax.grid(alpha=.2);ax.set_xlabel('x / 相机高度');ax.set_ylabel('z / 相机高度');ax.set_title('丢掉R4/R6后出现斜向连接\n底面IoU 98.15% → 86.34%')
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0],[0],c='#24292e',ls='--',label='参考'),Line2D([0],[0],c='#247c5e',label='14人'),Line2D([0],[0],c='#c35a35',label='15人')],fontsize=9,ncol=3)
    ax=fig.add_subplot(gs[1,1]);xx=np.arange(2)
    for n,off,col in [(14,-.18,'#247c5e'),(15,.18,'#c35a35')]:
        values=[v.loc[v.n.eq(n)&v.role.eq('C')&v.reference_corner.eq(c),'support'].iloc[0]for c in [4,6]];bars=ax.bar(xx+off,values,.31,color=col,label=f'{n}人')
        for j,(bar,val)in enumerate(zip(bars,values)):
            if n==15:bar.set_hatch('///');bar.set_alpha(.7)
            ax.text(j+off,val+.15,str(int(val)),ha='center',fontsize=11)
    ax.axhline(7,c='#247c5e',ls='--',lw=1.1,label='原门槛7');ax.axhline(8,c='#c35a35',ls=':',lw=1.5,label='新门槛8');ax.set_ylim(0,10);ax.set_xticks(xx,['R4：票数不变\n纯门槛失选','R6：少了W115一票\n重对应＋门槛失选']);ax.set_ylabel('真实身份组票数');ax.set_title('不是仅有一种失选原因');ax.legend(ncol=2,fontsize=8)
    ax=fig.add_subplot(gs[1,2]);p=metrics.loc[metrics.path_id.eq(a['event']['path_id'])].sort_values('n')
    for arm,col in [('A','#cc7b23'),('B','#287caa'),('C','#247c5e')]:ax.plot(p.n,p[arm+'_B8L2'],marker='o',ms=3,lw=1.7,c=col,label=arm)
    ax.axvspan(14,15,color='#f5bba7',alpha=.35);ax.set_xticks(p.n.astype(int));ax.set_ylim(0,102);ax.grid(alpha=.2);ax.set_xlabel('人数n；XYZ始终各7人');ax.set_ylabel('Q（B8L2）');ax.set_title('同一固定块与背景增长路径\nA +0.08，B −0.92，C −51.13');ax.legend(ncol=3,fontsize=9)
    fig.suptitle('增加同一个人，为什么较多转折队反而大幅降质？',x=.045,ha='left',y=.98,fontsize=20)
    fig.text(.045,.925,'jh4fc5c5qoQ-12｜困难普通Manual｜DSTRUCT_K3楼外标签｜固定X7/Y7/Z7；W117加入共同背景；没有换掉任何原成员',fontsize=11)
    fig.text(.045,.075,'R4：同7票、同中心，门槛由7升8而失选。R6：W115改与W117成2票组，原组8→7票，在新门槛下失选。',fontsize=11)
    fig.text(.045,.045,'参考背面结构部分被淋浴隔墙／浴帘遮挡，沿既有参考与范围解释。Q下降51.13分不等于底面下降51.13个百分点。',fontsize=11,color='#4a5560')
    for ext in ['png','svg']:
        buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=170,facecolor='white',bbox_inches='tight',pad_inches=.13);(OUT/('SIZE_THRESHOLD_MECHANISM_ZH.'+ext)).write_bytes(buf.getvalue())
    plt.close(fig)

def note(a,b,steps,summ):
    q=pd.read_csv(OUT/'SIX_ENDPOINT_SCALARS.csv').set_index(['n','role']);lines=[]
    for key,name,scale in [('B8L2','Q',1),('D10','D10',1),('iou_2d','底面IoU（%）',100),('IoU3D100','三维棱柱代理',1),('dir','方向残差（°）',1),('S_bottom_deg','底界角误差（°）',1),('omission','遗漏比例（%）',100),('extension','外扩比例（%）',100),('nodes','输出节点',1),('source_time_total_seconds','记录总秒数',1)]:
        vals=[q.loc[(n,arm),key]*scale for arm in ['A','B','C']for n in [14,15]];lines.append('|'+name+'|'+'|'.join(f'{x:.3f}'for x in vals)+'|')
    part='；'.join(f'{r.role}：共有{r.shared_observations}观察，拆开{r.same_observation_pairs_split}对、合并{r.same_observation_pairs_merged}对'for r in summ.itertuples())
    text=f'''# 固定七人块，14→15人时发生的真实门槛／对应反转

**图像 jh4fc5c5qoQ-12；普通Manual、困难、留出建筑检查；DSTRUCT_K3，源C2→目标C3。** 本例由已完成规模研究中的大幅下降条件选出，属于机制展示；不以这一例估计发生率，也不因它撤销其它规模多数正向发现。

## 1. 精确改变了什么

n14事件 `{E14}`，n15事件 `{E15}`。X/Y/Z各7人和原有7人背景固定，**同一W117进入A、B、C**，没有移除任何原人员。三队间实际替换m仍为7；它不是换人数从14变15，也不是换入目标类人数增加。

- X：{a['event']['X'].replace('|','、')}。
- Y：{a['event']['Y'].replace('|','、')}。
- Z：{a['event']['Z'].replace('|','、')}。
- n14的D：{a['event']['D'].replace('|','、')}。
- n15的D：上述7人加W117；目标类背景人数仍为0。

W117属于该楼外折的源类C2。其本图原答只有4个节点，个体Q为28.398；该数值描述这份原答，不用来推断其心理或一般能力。其一份角点观察与已有W115相近，改变了重分组结果；其它原观察完全不改。

## 2. 六个端点与结果反转

|指标|A14|A15|B14|B15|C14|C15|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

A的Q **+0.078**，B **−0.918**，C **−51.134**。C−B从 **+8.868** 变为 **−41.347**，净优势变化约 **−50.216**；这与C自身下降51.134分是两个不同量。三队六端点均成功、可评分，不能把本例称为融合失败。

同类Q幅度14.758→13.761，对称跨类幅度16.247→34.467，gap从1.489增至20.705：**区分度扩大来自跨类队退步，不能当成收益扩大。** C底面IoU从98.146%降至86.345%，即−11.801个百分点；三维代理−11.564分。Q大幅下降同时受到方向残差1.113→15.514°的放大，不能把−51.134写成同幅度的几何损失。

每队记录总秒数均恰增加W117的207.534秒，来源是既有用户处理记录；没有新测生产耗时。

## 3. R4：真实的纯门槛失选

C的参考R4身份组在n14、n15均为同一7名人员：**W102/W103/W109/W112/W122/W126/W130**。组中心也完全相同：ERP x=203.160，顶y=122.480，底y=396.977。

n14门槛为7，7票选留；n15门槛升为8，7票失选。W117没有加入这个组，也没有使这个组改位置。这里可以明确归因为门槛改变，证据不依赖“人数增加通常怎样”的先验。

## 4. R6：对应变化与门槛共同作用

n14的R6有8票：W102/W106/W109/W112/**W115**/W122/W126/W130。n15时，W115原观察没有改坐标，却和新W117的邻近观察组成一个2票小组；原R6剩下7票，达不到新门槛8，两个组均未选留。

W115这份观察为x=127.948、顶y=71.142、底y=445.747；W117为x=132.392、顶y=69.068、底y=452.087。它们形成的新组中心为x=130.170、顶y=70.105、底y=448.917。原R6其余七票的中心由125.440/55.114/463.605变为125.327/55.029/464.150。位置变化很小，但失去一票再叠加更高门槛使其不再输出。

因此不能把第二处也称为“完全相同票账下纯门槛丢角”，也不能说W117仅仅没有支持必要结构：其进入还改变了已有W115观察的对应。固定n14组只提高到8票会让R4丢失而R6保留；实际n15又改变了R6的组员。这是组状态的逻辑对照，**没有运行或采用替代门槛的新正式分数**。

跨n对所有原观察的实际关联为：{part}。人数、阈值、对应和中位定位分别保存。

## 5. 结构与图像解释

已有范围是同一盆厕淋浴小室；机会记录为“浴室淋浴隔墙背面转折与浴帘共同挡住关键角线，点3至7密集，不能凭主体四角代替”，参考为8转折。本图画面虽出现通往相邻区域的门，其冻结评价池仍为普通Manual，不能按看到门自行改成门洞交界或扩大目标范围。

n14的C保存8个参考对应节点。n15丢掉R4/R6后，保留节点按既定环序连接，出现斜向捷径，C只有6点；这同时损害局部结构、底面和方向。参考中的密集背面转折不全部直接可见，应沿既有参考和遮挡机会解释，不把本轮看图当作新GT裁定。当前参考、环序和评分均未改变。

![人数、门槛、对应、底面和质量过程](SIZE_THRESHOLD_MECHANISM_ZH.png)

## 6. 同图第二锚点的重复支持

已有另一路径在n14→15加入 **W128**：事件 `b43e5c4da3c36df1cbda5afb`→`4e506fea6926b64c9c7d7b67`。其C的Q为96.125→45.471（−50.654），节点8→7，底面IoU97.452%→87.742%，三维代理97.324→87.656，方向1.109→15.552°；A、B分别约+0.509、+0.948。该路径C的两个端点及ABC标量直接引用已存结果，不再次重放，也不在没有组票账重放时断言它具有完全相同的内部原因。

两锚点支持“本图某些固定七人块在门槛跨档处可强烈反转”，不证明每名新背景人员都造成相同结果。两条完整n10…19路径、所有相邻步及失败状态均保存，未仅保存14→15的低点。

## 7. 交付与复现身份

本目录保存主路径两组ABC的6个原生重放，B8L2/D10/底面/三维与缓存标量最大差均为0。两个事件各有原答—ERP—BEV—票账图及三维图；共同输入、原始W117、LOBO标签、跨n同观察关联、所有组及中位位置另存。这里只新增少量机制重放，没有扩展全库案例、重新建类或改融合方法。
'''
    (OUT/'CASE_NOTE_ZH.md').write_text(text)

def main():
    a,b=load(E14),load(E15);metrics,steps=save_inputs(a,b);v,summ=across_n(a,b);plot_comparison(a,b,v,metrics);note(a,b,steps,summ)
    paths=['design/size_paths/EVENTS_EXACT.csv.gz','results/size_paths/EVENT_METRICS.csv.gz','analysis/size_paths/PATH_STEP_CHANGES.csv.gz','cases/build_exchange_cases.py']
    receipt={'data':'v2','input_commit':'972857b2b3f548316be215400e42d6ef6e639250','case_stage':'fixed_block_size_path_mechanism','chosen_before_event':E14,'chosen_after_event':E15,'native_endpoint_replays':6,'altered_threshold_fusions':0,'entrant':'W117','membership_check':'same XYZ and all previous D; adds same W117 in each arm','case_selection':'selected by root after size analysis to explain a large loss; not random or representative-rate sample','source_hashes':[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()}for p in paths]};(OUT/'CASE_SOURCE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print('Saved fixed-block threshold/correspondence case, both paths and combined figure')

if __name__=='__main__':main()
