"""Scientific figures from saved image-level results and exact case geometry."""
from pathlib import Path
import argparse,json,math,os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image
from complete_half_traces import read
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage01_half_team';FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
font_candidates=[Path(os.environ['HOHONET_CJK_FONT'])] if os.environ.get('HOHONET_CJK_FONT') else []
font_candidates += [ROOT/'source/fonts/NotoSansCJKsc-Regular.otf',ROOT.parent/'HOHONET_v21_reaudit_20261029/stage04_cases/six_cases/source/NotoSansCJKsc-Regular.otf']
font=next((f for f in font_candidates if f.is_file()),None)
if font:
    matplotlib.font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
else:
    for family in ['Noto Sans CJK SC','Microsoft YaHei','SimHei','WenQuanYi Zen Hei']:
        try:
            matplotlib.font_manager.findfont(FontProperties(family=family),fallback_to_default=False)
        except ValueError:continue
        plt.rcParams['font.family']=family;break
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
colors={'A':'#176fbc','B':'#8551b6','C':'#d34931'}
def project_line(points):
    p=np.asarray(points,float).reshape(-1,2,2);out=[]
    for i in range(len(p)):
        for side in [0,1]:
            xyz=[]
            for q in [p[i],p[(i+1)%len(p)]]:
                az=q[side,0]/1024*2*np.pi;r=-1/np.tan((.5-q[1,1]/512)*np.pi);el=(.5-q[side,1]/512)*np.pi
                xyz.append(np.array([-np.sin(az)*r,r*np.tan(el),np.cos(az)*r]))
            xyz=np.array(xyz);s=xyz[0]+np.linspace(0,1,80)[:,None]*(xyz[1]-xyz[0]);xx=np.arctan2(-s[:,0],s[:,2])%(2*np.pi)*1024/(2*np.pi);yy=(.5-np.arctan2(s[:,1],np.linalg.norm(s[:,[0,2]],axis=1))/np.pi)*512
            breaks=np.where(abs(np.diff(xx))>512)[0]+1
            for a in np.split(np.column_stack([xx,yy]),breaks):out.append(a)
    for q in p:out.append(q)
    return out
def main(case=None):
    im=pd.read_csv(OUT/'IMAGES_METRIC_SPECIFIC_SUPPORT.csv.gz');h=im[im.n==14].dropna(subset=['gap_A','gap_sym'])
    if case is None:
        fig,axs=plt.subplots(1,3,figsize=(16,4.8),layout='constrained')
        for dif,col in [('简单','#457b9d'),('中等','#e99d3b'),('困难','#ae4564')]:
            g=h[h.difficulty==dif];axs[0].scatter(g.B8L2__within,g.B8L2__cross_symmetric,s=30,color=col,label=f'{dif} {len(g)}图',alpha=.85)
        limit=max(h.B8L2__within.max(),h.B8L2__cross_symmetric.max())*1.05;axs[0].plot([0,limit],[0,limit],'--',color='#777',lw=1);axs[0].set(xlabel='同类幅度 |B−A|（Q分）',ylabel='对称跨类幅度（Q分）',title='62/83图：跨类幅度更大');axs[0].legend(frameon=False)
        q=h.sort_values('CB');axs[1].bar(np.arange(len(q)),q.CB,color=np.where(q.CB>0,'#337f7b','#be554c'),width=.9);axs[1].axhline(0,color='#777',lw=1);axs[1].set(xlabel='83张图，按C−B排序',ylabel='C−B（Q分）',title='76/83图升质，7图下降');axs[1].set_xticks([])
        data=[];labels=[]
        for dif in ['简单','中等','困难']:
            z=h[h.difficulty==dif];data.append(z.fusion_turn_n__delta_CB);labels.append(dif+'\n'+str(len(z))+'图')
        axs[2].boxplot(data,tick_labels=labels,showfliers=True,patch_artist=True,boxprops={'facecolor':'#d8e8ef'});axs[2].axhline(0,color='#777',lw=1);axs[2].set(ylabel='C−B有效转折数',title='困难9/9图增加转折；简单59图均不变')
        fig.suptitle('普通Manual · TARGET K3工作分类 · 14人换7人 · 197事件\n图内先背景、块、池等权；质量方向与变化幅度分开，Q缺失不补零',fontsize=14)
        fig.savefig(FIG/'HALF_MAIN_SUMMARY.png',dpi=180);fig.savefig(FIG/'HALF_MAIN_SUMMARY.svg');plt.close(fig)
    choices=['S9hNv5qa7GM-09','jh4fc5c5qoQ-04','B6ByNegPMKs-11','VFuaQ6m2Qom-04','pa4otMbVnkk-42','S9hNv5qa7GM-12']
    if case is not None:
        if case not in choices:raise ValueError('Unknown exact scientific case '+case)
        choices=[case]
    anchors=pd.read_csv(OUT/'CASE_ANCHOR_SELECTION.csv').set_index('image');events=pd.read_csv(OUT/'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz',low_memory=False).set_index('event_id');index=[]
    for image in choices:
        eid=anchors.loc[image,'anchor_event'];e=events.loc[eid];pool=read(OUT/'case_inputs'/(e.pool_id+'.json.gz'));arms={a:read(OUT/'trace_endpoints'/(e[a+'_team_key']+'.json.gz')) for a in 'ABC'}
        photo=Image.open(OUT/'originals'/(image+'.png'))
        fig,axs=plt.subplots(1,2,figsize=(14,5.9),gridspec_kw={'width_ratios':[2.05,1]},layout='constrained');axs[0].imshow(photo,extent=(0,1024,512,0));axs[0].set(xlim=(0,1024),ylim=(512,0),xlabel='全景横坐标（1024）',ylabel='纵坐标（512）')
        for line in project_line(pool['reference']['points_1024x512']):axs[0].plot(line[:,0],line[:,1],color='black',lw=1.6,alpha=.9)
        ref=np.array(pool['reference']['floor_xz_h']);axs[1].plot(*np.vstack([ref,ref[0]]).T,color='black',lw=2,label='冻结参考')
        for i,pt in enumerate(ref):axs[1].text(*pt,'#'+str(i+1),fontsize=8)
        for a,r in arms.items():
            geom=r.get('geometry') or {};complete=r['score_status']=='complete_conditional'
            if complete:
                points=geom.get('points')
                if points:
                    for line in project_line(points):axs[0].plot(line[:,0],line[:,1],color=colors[a],lw=1.4,alpha=.85)
                f=geom.get('footprint')
                if f:
                    f=np.array(f);axs[1].plot(*np.vstack([f,f[0]]).T,'-o',color=colors[a],lw=1.5,markersize=3,label=f'{a} Q='+('缺失' if r['B8L2'] is None else f"{r['B8L2']:.2f}"))
            else:
                # A diagnostic candidate with three points is not an accepted ring.
                # Preserve actual selected corners, but never invent connecting edges.
                centers=[g['center'] for g in r['full_state']['identity_groups'] if g['selected'] and g['center']]
                floor=[]
                for pair in centers:
                    for pt in pair:axs[0].plot(pt[0],pt[1],'x',color=colors[a],ms=7,mew=2)
                    pt=pair[1];az=pt[0]/1024*2*np.pi;radius=-1/np.tan((.5-pt[1]/512)*np.pi)
                    floor.append([-np.sin(az)*radius,np.cos(az)*radius])
                if floor:
                    floor=np.array(floor);axs[1].plot(floor[:,0],floor[:,1],linestyle='None',marker='x',color=colors[a],ms=7,mew=2,label=f'{a}：{r["score_status"]}')
                else:axs[1].plot([],[],color=colors[a],label=f'{a}：{r["score_status"]}')
        axs[1].plot(0,0,'s',color='#142235',ms=5);axs[1].set_aspect('equal',adjustable='datalim');axs[1].set(xlabel='x / 相机高',ylabel='z / 相机高');axs[1].legend(loc='best',fontsize=8,framealpha=.9)
        row=h[h.image==image];ga='缺失' if not len(row) else f'{row.iloc[0].gap_A:+.3f}';gs='缺失' if not len(row) else f'{row.iloc[0].gap_sym:+.3f}';cb='缺失' if not len(row) else f'{row.iloc[0].CB:+.3f}'
        status='；'.join(f'{a} {r["nodes"]}节点 / {r["score_status"]}' for a,r in arms.items())
        fig.suptitle(f'{image} · {pool["meta"]["difficulty"]} · 当前14/7逐图 GA {ga}，GS {gs}，C−B {cb}\n示例事件 {eid}（所有原事件另在查看器保留）',fontsize=12)
        fig.text(.01,.008,status+'。未形成环时只显示入选节点，不编造闭合边。',fontsize=9)
        dest=FIG/(image+'_exact_case.png');temporary=FIG/(image+'_exact_case.tmp');fig.savefig(temporary,format='png',dpi=170,bbox_inches='tight',pad_inches=.18);plt.close(fig)
        with Image.open(temporary) as check:check.verify()
        temporary.replace(dest)
        index.append({'image':image,'event_id':eid,'file':str(dest.relative_to(OUT)),'selection':'six explanatory types after complete 36-image review; not a sample for effect estimation'})
    if case is None:
        pd.DataFrame(index).to_csv(FIG/'FIGURE_SOURCE_INDEX.csv',index=False)
    else:
        old=pd.read_csv(FIG/'FIGURE_SOURCE_INDEX.csv');old=old[old.image!=case]
        pd.concat([old,pd.DataFrame(index)],ignore_index=True).to_csv(FIG/'FIGURE_SOURCE_INDEX.csv',index=False)
    print('figures',len(index)+(case is None))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args();main(args.case)
