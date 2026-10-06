"""Render complete layouts from supplied coordinates; no original PNG is synthesized.
Each PNG contains one distinct chart. No color palette or plotting style is set.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from arc_excerpt import Ring, footprint, paired_wall_proxy, project, TAU


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def close_xy(xy):
    a=np.asarray(xy);return np.vstack((a,a[0]))

def projected_edges(record: dict, surface: int):
    nodes=paired_wall_proxy(record)[surface]
    chunks=[]
    t=np.linspace(0,1,97)
    for a,b in zip(nodes,np.roll(nodes,-1,axis=0)):
        xy=project(a[None,:]*(1-t[:,None])+b[None,:]*t[:,None])
        # Break only the ERP display seam; do not alter the source edge or point order.
        cuts=np.flatnonzero(abs(np.diff(xy[:,0]))>512)+1
        for piece in np.split(xy,cuts):
            chunks.extend([piece,np.full((1,2),np.nan)])
    return np.vstack(chunks)

def render(root: Path=ROOT, result_dir: Path|None=None, figure_dir: Path|None=None) -> list[Path]:
    rd=result_dir or root/'results';fd=figure_dir or root/'figures';fd.mkdir(parents=True,exist_ok=True)
    names={f.name for f in font_manager.fontManager.ttflist}
    for candidate in ['Noto Sans CJK SC','Noto Sans CJK JP','Noto Serif CJK SC','Noto Serif CJK JP']:
        if candidate in names:
            plt.rcParams['font.family']=candidate;break
    plt.rcParams['axes.unicode_minus']=False
    written=[]
    def finish(fig,name):
        path=fd/name;fig.tight_layout();fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig);written.append(path)
    j=read(root/'inputs/2t7_selected.json');g=footprint(j['reference'])[0]
    fig,ax=plt.subplots(figsize=(9,5.5))
    lee=np.asarray(j['lee']['geometry']['coordinates'][0])
    ax.plot(lee[:,0],lee[:,1],linewidth=4,alpha=.5,label='Lee MV50：11个范围表示节点')
    xy=close_xy(footprint(j['exact'])[0]);ax.plot(xy[:,0],xy[:,1],linestyle='--',linewidth=1.8,label='精确上下弧的底面：与Lee重合')
    xy=close_xy(footprint(j['point'])[0]);ax.plot(xy[:,0],xy[:,1],marker='o',markersize=4,linewidth=1.8,label='点方法：4对（未确认基线）')
    xy=close_xy(g);ax.plot(xy[:,0],xy[:,1],linestyle=':',linewidth=2.2,label='固定原GT：R02502')
    ax.plot([0],[0],marker='x',markersize=8,linestyle='None',label='相机地面投影')
    ax.set(xlabel='相机坐标 x / h',ylabel='相机坐标 z / h',title='2t7-06｜同一3人输入的完整范围；门槛不变')
    ax.set_aspect('equal');ax.legend(loc='upper left',bbox_to_anchor=(0,-.15),ncol=2,fontsize=9)
    finish(fig,'01_2t7_complete_bev.png')

    u=(np.arange(4096)+.5)*TAU/4096;x=u/TAU*1024
    fig,ax=plt.subplots(figsize=(10,5.7))
    for label,r in [('精确弧（25个表示节点）',j['exact']),('点方法（4角点对）',j['point']),('原GT',j['reference'])]:
        y=Ring(r).evaluate(u)
        ax.plot(x,y[0],linewidth=1.6,label=label+'：上界')
        ax.plot(x,y[1],linestyle='--',linewidth=1.6,label=label+'：下界')
    ax.set(xlim=(0,1024),ylim=(512,0),xlabel='全景横坐标（连续坐标，1024 px）',ylabel='全景纵坐标（512 px）',title='2t7-06｜完整上下边界；Lee本身不提供上界')
    ax.legend(loc='center',ncol=2,fontsize=9)
    finish(fig,'02_2t7_complete_boundaries.png')

    s=read(root/'inputs/e9z19_selected.json');r=read(rd/'e9z19_comparison.json')
    fig,ax=plt.subplots(figsize=(9,8.5))
    for ref in s['references']:
        xy=close_xy(ref['footprint']);label='原GT（12对）' if ref['version']=='original' else '修订GT（6对）'
        ax.plot(xy[:,0],xy[:,1],linestyle=':',linewidth=1.5,alpha=.65,label=label)
    labels={'observed_medoid':'完整原作答代表 R02122（6对）','MV50':'完整 MV50 范围（≥12/24区域票）','scope_R01301':'观测scope候选 R01301（5对）'}
    for row,ls,lw in zip(r['results'],['--','-','-.'],[2,2.6,2.1]):
        p=shape(row['geometry']);xy=np.asarray(p.exterior.coords)
        ax.plot(xy[:,0],xy[:,1],linestyle=ls,linewidth=lw,label=labels[row['name']])
    ax.plot([0],[0],marker='x',markersize=8,linestyle='None',label='相机地面投影')
    ax.set(xlabel='相机坐标 x / h',ylabel='相机坐标 z / h',title='e9z-19｜完整原作答、现有共识与有来源的scope候选\n同一坐标系；不删点、不补角、不按GT选候选')
    ax.set_aspect('equal');ax.legend(loc='upper left',bbox_to_anchor=(0,-.11),ncol=2,fontsize=9)
    finish(fig,'03_e9z19_complete_scope.png')

    full=read(rd/'e9z19_complete_layouts.json')
    fig,ax=plt.subplots(figsize=(10,5.7))
    for label,rec in [('原作答代表 R02122',full['observed_medoid']),('scope候选 R01301',full['scope_candidate'])]:
        for surface,ls,txt in [(0,'-','上界'),(1,'--','下界')]:
            xy=projected_edges(rec,surface)
            ax.plot(xy[:,0],xy[:,1],linestyle=ls,linewidth=1.5,label=label+'：'+txt)
        p=np.asarray(rec['points']).reshape(-1,2,2)
        xx=[];yy=[]
        for q in p:
            xx.extend([q[0,0],q[1,0],np.nan]); yy.extend([q[0,1],q[1,1],np.nan])
        ax.plot(xx,yy,linewidth=.6,alpha=.5)
    ax.set(xlim=(0,1024),ylim=(512,0),xlabel='全景横坐标（连续坐标，1024 px）',ylabel='全景纵坐标（512 px）',title='e9z-19｜两份完整原作答按声明邻接重绘\n非原图叠图；保留经度回折，不改成单值环')
    ax.legend(loc='upper left',bbox_to_anchor=(0,-.15),fontsize=9,ncol=2)
    finish(fig,'04_e9z19_complete_observed_boundaries.png')

    o=read(root/'inputs/e9z16_selected.json');g=next(q for q in o['references'] if q['version']=='manual_revision')
    d=(Ring(o['record']).evaluate(u)-Ring(g).evaluate(u))*180/512
    fig,ax=plt.subplots(figsize=(10,4.8))
    ax.plot(x,d[0],linewidth=1.8,label='上界：MAE 1.931°（整体向画布上方偏移）')
    ax.plot(x,d[1],linestyle='--',linewidth=1.8,label='下界：MAE 0.560°')
    ax.axhline(0,linestyle=':',linewidth=.8)
    ax.set(xlim=(0,1024),xlabel='全景横坐标（连续坐标，1024 px）',ylabel='作答−修订参考：纵向角差（°）',title='e9z-16 / R00087（Semi）｜上下拆分增加了什么解释？\nBEV IoU 0.954；内部墙高RMS 0.007h，仍不排除上界偏移')
    ax.legend(loc='lower left',fontsize=9)
    finish(fig,'05_e9z16_upper_lower_error.png')
    return written

if __name__=='__main__':
    for p in render():print(p)
