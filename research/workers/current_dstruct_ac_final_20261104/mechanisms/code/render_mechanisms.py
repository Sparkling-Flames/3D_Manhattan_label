"""Render exact saved geometry and image-balanced diagnostic associations.

Scientific drawings only: saved photographs are unchanged, and paths come from
frozen coordinates. This script does not run fusion, scoring, or a ring repair.
"""
from __future__ import annotations
import argparse, io, os, sys, tempfile
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'hohonet_current_ac_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image
from mechanism_core import ROOT, OUT, read_json, save_json, sha

sys.path.insert(0,str(ROOT/'research/workers/personnel_ac_v21_20261030/stage06_cases/code'))
from geometry_draw import erp,bev,points3d

COLORS={'A':'#246D9C','C':'#D45C27','R':'#172636','B':'#008777'}

def use_font(arg):
    candidates=[arg,os.environ.get('HOHONET_CJK_FONT'),str(OUT/'source/NotoSansCJKsc-Regular.otf'),
                'C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for path in candidates:
        if path and Path(path).is_file():
            font_manager.fontManager.addfont(path)
            name=font_manager.FontProperties(fname=path).get_name()
            plt.rcParams['font.family']=name
            return path
    return None

def number(v,nd=2):
    return '不可评' if v is None or (isinstance(v,float) and not np.isfinite(v)) else f'{float(v):.{nd}f}'

def save(fig,name,svg=True):
    directory=OUT/'figures';directory.mkdir(exist_ok=True)
    for fmt in (['png','svg'] if svg else ['png']):
        b=io.BytesIO();fig.savefig(b,format=fmt,dpi=160,bbox_inches='tight')
        path=directory/(name+'.'+fmt);temporary=path.with_name(path.name+'.writing')
        with temporary.open('wb') as f:f.write(b.getvalue());f.flush();os.fsync(f.fileno())
        temporary.replace(path)
        if fmt=='png':
            with Image.open(path) as im:im.verify()
    plt.close(fig)

def pano(ax,photo,reference,row,arm):
    ax.imshow(photo,extent=[0,1024,512,0]);erp(ax,reference,COLORS['R'],1.6,1,'--')
    points=(row.get('geometry') or {}).get('points')
    if points:erp(ax,points,COLORS[arm],1.8,1)
    for group in row['full_state']['identity_groups']:
        if not group['selected'] or group['center'] is None:continue
        p=np.asarray(group['center']);ax.plot(p[:,0],p[:,1],c=COLORS[arm],lw=.9)
        ax.scatter(p[:,0],p[:,1],s=10,c=COLORS[arm],edgecolors='white',linewidths=.4,zorder=7)
        ax.text(p[1,0]+3,p[1,1]+11,group['feature_id'].replace('node_','g')+f"({group['support']})",color=COLORS[arm],fontsize=7,bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=1))
    ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([])
    ax.set_title(f'{arm}  Q={number(row.get("B8L2"))} · 入选 {row["nodes"]} 节点 · {row["score_status"]}',loc='left',fontsize=11,color=COLORS[arm])

def case_board(case):
    e=case['event'];m=case['current_metrics'];s=case['mechanisms'];ref=case['reference']['points_1024x512']
    photo=Image.open(OUT/'originals'/(e['image']+'.png'))
    fig=plt.figure(figsize=(16,9.8));grid=fig.add_gridspec(2,2,height_ratios=[1,1.03],wspace=.10,hspace=.19)
    for j,arm in enumerate(('A','C')):pano(fig.add_subplot(grid[0,j]),photo,ref,case['arms'][arm],arm)
    ax=fig.add_subplot(grid[1,0]);bev(ax,ref,COLORS['R'],1.5,1,'--',True)
    for arm,row in case['arms'].items():
        points=(row.get('geometry') or {}).get('points')
        if points:bev(ax,points,COLORS[arm],1.7,1,dots=True)
        else:
            # Draw located selected nodes without manufacturing a polygon.
            for g in row['full_state']['identity_groups']:
                if g['selected'] and g['center']:
                    p=np.asarray(g['center'])[1];r=1/np.tan((p[1]/512-.5)*np.pi);u=p[0]*2*np.pi/1024
                    ax.scatter([-np.sin(u)*r],[np.cos(u)*r],s=30,c=COLORS[arm],marker='x')
    ax.scatter([0],[0],marker='^',c='#6B7784',s=25);ax.set_aspect('equal','datalim');ax.grid(alpha=.2)
    ax.set_xlabel('x / 相机高度 h');ax.set_ylabel('z / 相机高度 h')
    ax.set_title('归一化底面：参考黑虚线 · A蓝 · C橙（无环只画点）',loc='left',fontsize=11)
    ax=fig.add_subplot(grid[1,1]);ax.axis('off')
    metrics=[('质量 Q',m['A_B8L2'],m['C_B8L2']),('底面 IoU',m['A_iou_2d'],m['C_iou_2d']),
             ('底边偏差 S / °',m['A_S_bottom_deg'],m['C_S_bottom_deg']),('方向偏差 D / °',m['A_dir'],m['C_dir']),
             ('转折 / 短边',f"{number(m['A_fusion_turn_n'],0)} / {number(m['A_fusion_short_turn_edges'],0)}",f"{number(m['C_fusion_turn_n'],0)} / {number(m['C_fusion_short_turn_edges'],0)}"),
             ('面积 / h²',m['A_geometry_area_h2'],m['C_geometry_area_h2']),
             ('完整投影来源环',s['A_source_complete_rings'],s['C_source_complete_rings'])]
    table=ax.table(cellText=[[k,number(a,3) if not isinstance(a,str) else a,number(c,3) if not isinstance(c,str) else c] for k,a,c in metrics],
                   colLabels=['已有分项与来源支持','A','C'],bbox=[0,.49,1,.48],colWidths=[.50,.25,.25],cellLoc='left')
    table.auto_set_font_size(False);table.set_fontsize(10)
    for (r,col),cell in table.get_celld().items():
        cell.set_edgecolor('#DAE0E5');cell.set_facecolor('#EEF2F6' if r==0 else 'white')
    links=case['D_anchor_links'];cross=[r for r in links if r['link_type']=='exact_same_nonempty_D_observations' and (r.get('threshold_cross_up') or r.get('threshold_cross_down'))]
    if not cross:cross=sorted([r for r in links if r['link_type']=='exact_same_nonempty_D_observations' and r['A_selected'] and r['C_selected']],key=lambda r:abs(r.get('bottom_vertical_shift_deg') or 0),reverse=True)[:4]
    detail=[]
    for r in cross[:6]:
        detail.append(f"{r['A_group'].replace('node_','g')}→{r['C_group'].replace('node_','g')}：{r['A_support']}→{r['C_support']}票；共同D观察 {r['common_D_observations']}" )
    txt=f"ΔQ={number(m['dQ'],3)}；固定门槛={s['minimum_support_A']}票\n稳定锚点跨票：上 {s['stable_threshold_cross_up']} / 下 {s['stable_threshold_cross_down']}；D分组改变：{'是' if s['D_partition_changed'] else '否'}\n"+'\n'.join(detail)
    txt+='\n跨队对应以原答ID+角点索引的同一非空D集合为准。'
    ax.text(0,.43,txt,va='top',fontsize=10,linespacing=1.65)
    fig.suptitle(f"{e['case_id']} · {e['image']} · {e['class_pair'].replace('_','→')} · n={e['n']}, m={e['m']} · {m['official_difficulty']}",fontsize=16,x=.04,ha='left',y=.985)
    fig.text(.04,.018,'原图来自冻结 GitHub Release；坐标使用冻结预处理结果。完整 D/X/Z 成员、逐人原答、票账、上下边界与来源见离线图册。',fontsize=10,color='#536170')
    save(fig,e['case_id']+'_GEOMETRY',svg=e['case_id'] in {'AC07','AC08','AC09','AC11'})

def diagnostic_figure():
    d=pd.read_csv(OUT/'MECHANISM_QUALITY_ASSOCIATIONS.csv')
    d=d[d.class_pair.eq('ALL_image_equal')&d.mechanism.eq('stable_threshold_cross_any')]
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),sharey=True)
    for ax,n in zip(axes,[14,20]):
        g=d[d.n.eq(n)].sort_values('mechanism_present')
        vals=g.abs_delta_Q_image_mean.to_numpy();lo=g.abs_delta_Q_cluster_ci_low.to_numpy();hi=g.abs_delta_Q_cluster_ci_high.to_numpy()
        ax.bar([0,1],vals,color=['#6E8495','#D45C27'],width=.56)
        ax.errorbar([0,1],vals,yerr=[vals-lo,hi-vals],fmt='none',ecolor='#172636',capsize=5)
        for i,r in enumerate(g.itertuples()):
            ax.text(i,r.abs_delta_Q_cluster_ci_high+1,f'{r.abs_delta_Q_image_mean:.2f}',ha='center',fontweight='bold')
            ax.text(i,-.13,f'{r.physical_pairs} 对 / {r.images} 图 / {r.buildings} 楼\n共同Q {r.jointly_scored_pairs} 对\n≥10分 {r.jump10_pairs}/{r.jointly_scored_pairs} 对',ha='center',va='top',color='#172636',fontsize=9,transform=ax.get_xaxis_transform())
        ax.set_xticks([0,1],['稳定锚点未检测到跨票','稳定锚点检测到跨票']);ax.set_title(f'n={n}, m=7 · 阈值始终 {n//2} 票')
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);ax.set_ylim(0,40)
    axes[0].set_ylabel('先图内平均、再图片等权的 |ΔQ|')
    fig.suptitle('同一票门槛的支持跨越，与更大的质量变化相伴',fontsize=15,y=.99)
    fig.text(.04,.015,'冻结抽样：248 对、116 图、22 楼；图内先汇总，误差条为建筑聚类重抽样区间。分组支持不同，这是描述性关联。\n“未检测”限定于稳定 D 锚点；不把歧义分组计为无机制；失败端点不以 Q=0 参与。',fontsize=10)
    fig.subplots_adjust(bottom=.33,top=.85,wspace=.15)
    save(fig,'VOTE_CROSSING_ASSOCIATION')

def difficulty_figure():
    d=pd.read_csv(OUT/'MECHANISM_DIFFICULTY_ASSOCIATIONS.csv')
    d=d[d.class_pair.eq('C2_C3')&d.mechanism.eq('stable_threshold_cross_any')]
    fig,axes=plt.subplots(1,2,figsize=(12,5.7),sharey=True)
    difficulties=['简单','中等','困难']
    for ax,n in zip(axes,[14,20]):
        for j,present in enumerate([False,True]):
            xs=[];ys=[];labels=[]
            for i,difficulty in enumerate(difficulties):
                g=d[d.n.eq(n)&d.difficulty.eq(difficulty)&d.mechanism_present.eq(present)]
                x=i+(j-.5)*.32
                if g.empty:
                    ax.text(x,1,'无此\n支持',ha='center',fontsize=9,color='#596775');continue
                r=g.iloc[0];xs.append(x);ys.append(r.abs_delta_Q_image_mean);labels.append((x,r))
            ax.bar(xs,ys,width=.30,color=['#6E8495','#D45C27'][j],label=['未检测到跨票','检测到跨票'][j])
            for x,r in labels:ax.text(x,r.abs_delta_Q_image_mean+1,f'{r.abs_delta_Q_image_mean:.1f}\n{int(r.jointly_scored_pairs)}/{int(r.physical_pairs)}对',ha='center',fontsize=9)
        ax.set_xticks(range(3),difficulties);ax.set_ylim(0,54);ax.set_title(f'C2↔C3 · n={n}, m=7');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    axes[0].set_ylabel('共同Q图片等权 |ΔQ|');axes[1].legend(frameon=False,loc='upper left')
    fig.suptitle('跨票关联不只来自一种难度，但小层支持差别很大',fontsize=15,y=.98)
    fig.text(.04,.025,'柱上“共同Q对数 / 全部物理对数”；每个类别对×图片只抽1对。14/7困难层10对全部跨票，缺少同层未跨票对照。\n简单层跨票只有1–2对，适合显示存在性，不足以稳定估计该小格平均幅度；完整图片/建筑计数见CSV。',fontsize=10)
    fig.subplots_adjust(bottom=.22,top=.86,wspace=.15);save(fig,'DIFFICULTY_VOTE_ASSOCIATION')

def position_focus(case):
    ref=case['reference']['points_1024x512'];photo=Image.open(OUT/'originals'/(case['event']['image']+'.png'))
    fig,axes=plt.subplots(1,2,figsize=(12,5.2))
    ax=axes[0];ax.imshow(photo,extent=[0,1024,512,0]);erp(ax,ref,COLORS['R'],1.5,1,'--')
    for arm,row in case['arms'].items():
        erp(ax,row['geometry']['points'],COLORS[arm],1.8,1)
        p=np.asarray(row['geometry']['points']);ax.scatter(p[:,0],p[:,1],c=COLORS[arm],s=20)
    ax.set_xlim(229,285);ax.set_ylim(296,263);ax.set_title('远端底角局部（原1024×512坐标）');ax.set_xlabel('x像素');ax.set_ylabel('y像素')
    ax=axes[1];bev(ax,ref,COLORS['R'],1.5,1,'--',True)
    for arm,row in case['arms'].items():bev(ax,row['geometry']['points'],COLORS[arm],1.8,1,dots=True)
    ax.set_xlim(-5.85,-5.25);ax.set_ylim(-.62,.52);ax.grid(alpha=.2);ax.set_aspect('equal');ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.set_title('同一局部的归一化底面')
    fig.suptitle('AC09：节点、20票支持和连接相同，几何仍可明显改变',fontsize=15,y=.99)
    fig.text(.04,.015,'局部底角 y：284.258→285.079 px（参考285.730）；底面 (-5.685,-0.531)→(-5.522,-0.501)。\n全输出方向偏差3.873→1.865°，Q77.408→92.579。该局部展示投影敏感性，不把全部Q变化归因于一个点。',fontsize=10)
    fig.subplots_adjust(bottom=.22,top=.84,wspace=.25);save(fig,'AC09_POSITION_FOCUS')

def appendix():
    c=read_json(OUT/'cases/APPENDIX_EXISTING_ABC.json.gz');photo=Image.open(OUT/'originals'/(c['image']+'.png'))
    fig,axes=plt.subplots(2,3,figsize=(15,7.8),gridspec_kw={'height_ratios':[1,1]})
    ref=c['reference']['points_1024x512']
    for j,arm in enumerate(['A','B','C']):
        row=c['endpoints'][arm];ax=axes[0,j];ax.imshow(photo,extent=[0,1024,512,0]);erp(ax,ref,COLORS['R'],1.4,1,'--');erp(ax,row['geometry']['points'],COLORS[arm],1.7,1)
        ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(f'{arm}：Q {row["B8L2"]:.3f} / {row["nodes"]}节点')
        ax=axes[1,j];bev(ax,ref,COLORS['R'],1.4,1,'--',True);bev(ax,row['geometry']['points'],COLORS[arm],1.7,1,dots=True);ax.set_aspect('equal','datalim');ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h')
    fig.suptitle('引用第12批既有严格ABC：jtcxE69GiFV-13（n=8, m=4）',fontsize=15,y=.98)
    fig.text(.04,.015,f'原保存逐图 GS = {c["image_mean_GS"]:.4f}；所示为原代表事件A/B/C，均未达到90分。高分压缩不能解释全部同类变化较大的图片。\n只复制原图、几何与参考；不重算GS，不计入本轮248对AC诊断样本。',fontsize=10)
    fig.subplots_adjust(top=.88,bottom=.16,hspace=.21,wspace=.20);save(fig,'APPENDIX_EXISTING_ABC')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font');a=ap.parse_args();font=use_font(a.font)
    plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'path','savefig.facecolor':'white'})
    cases=[read_json(p) for p in sorted((OUT/'cases').glob('AC[0-9][0-9].json.gz'))]
    for case in cases:case_board(case)
    diagnostic_figure();difficulty_figure();position_focus(next(c for c in cases if c['case_id']=='AC09'));appendix()
    files=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((OUT/'figures').glob('*'))]
    save_json(OUT/'FIGURE_RECEIPT.json',dict(figures=files,font_source=font,font_sha256=sha(font) if font else None,scientific_coordinates_only=True,new_scores=0,new_fusions=0))
    print(f'Rendered {len(files)} exact scientific figures.')

if __name__=='__main__':main()
