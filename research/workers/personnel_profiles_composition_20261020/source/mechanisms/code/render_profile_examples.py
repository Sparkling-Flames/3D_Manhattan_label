"""Render paired-worker examples directly from current processed input evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/personnel_profile_mechanism_mpl')
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from render_cases import visual_module

WORKER_COLORS={'W109':'#00bfea','W112':'#f57728'}
REF_ERP='#e5ffae'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--records',type=Path,required=True)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--image-dir',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--font',type=Path)
    args=ap.parse_args();v=visual_module(args.repo,args.font)
    records=json.loads(args.records.read_text(encoding='utf8'))
    panels=[dict(code='b8cTxDM8gDG-07',bounds=[125,240,110,390],title='可见转折清楚：质量接近，耗时相差8.3倍',
                 description='两人均表达6对角点；W109与W112的B8L2分别98.42、97.00。'),
            dict(code='yqstnuAEVhm-29',bounds=[15,205,125,395],title='困难图的额外收益：慢者保留更多参考转折',
                 description='W109为11对，W112与参考均14对；该例分差+50.40，但需多用27.5分钟。'),
            dict(code='jh4fc5c5qoQ-04',bounds=[225,365,120,400],title='困难图关键反例：点数相同，定位偏差仍受重罚',
                 description='两人均12对；W112多用9.6分钟，B8L2反而低50.23分。')]
    fig=plt.figure(figsize=(16.4,15.4))
    outer=fig.add_gridspec(3,1,left=.035,right=.985,top=.84,bottom=.10,hspace=.47)
    summary=[]
    for i,p in enumerate(panels):
        rr=sorted([r for r in records if r['image_code']==p['code']],key=lambda r:r['worker_id'])
        assert len(rr)==2 and rr[0]['reference_id']==rr[1]['reference_id']
        ref=rr[0]['reference_evidence'];photo=np.asarray(Image.open(args.image_dir/(rr[0]['image_id']+'.png')).convert('RGB'))
        gs=outer[i].subgridspec(1,3,width_ratios=[1.65,.75,1.05],wspace=.17)
        ax=fig.add_subplot(gs[0]);v._erp_background(ax,photo)
        for r in rr:v._erp_edges(ax,r['points_1024x512'],WORKER_COLORS[r['worker_id']],linewidth=1.4,markers=True)
        v._erp_edges(ax,ref['points_1024x512'],REF_ERP,linewidth=.85,reference=True)
        ax.add_patch(Rectangle((p['bounds'][0],p['bounds'][2]),p['bounds'][1]-p['bounds'][0],p['bounds'][3]-p['bounds'][2],fill=False,edgecolor='white',ls='--',lw=1.2))
        ax.set_title(f"{p['code']} · {rr[0]['current_class']}\n{p['title']}",fontsize=12,pad=12)
        stats=[]
        for r in rr:
            stats.append(f"{r['worker_id']}  Q={r['B8L2']:.2f}  D10={r['D10']:.2f}  {r['source_active_time_seconds']:.1f}s  {len(r['points_1024x512'])//2}对")
            summary.append({k:r[k] for k in ['object_id','worker_id','image_id','image_code','current_class','B8L2','D10','source_active_time_seconds','reference_id','reference_version']})
        ax.text(0,-.065,'\n'.join(stats),transform=ax.transAxes,va='top',fontsize=9.3,linespacing=1.45)
        ax=fig.add_subplot(gs[1]);v._erp_background(ax,photo,p['bounds'])
        v._erp_edges(ax,ref['points_1024x512'],REF_ERP,linewidth=1.7,reference=True)
        for r in rr:v._erp_edges(ax,r['points_1024x512'],WORKER_COLORS[r['worker_id']],linewidth=1.6,markers=True)
        ax.set_title('局部原标注对照',fontsize=10)
        ax=fig.add_subplot(gs[2]);geoms=[]
        for r in rr:
            g=v.viewer_geometry(r['points_1024x512']);geoms.append(g)
            v._bev_ring(ax,g['floor'],WORKER_COLORS[r['worker_id']],linewidth=1.7)
        rg=v.viewer_geometry(ref['points_1024x512'],ref['floor_xz_h']);geoms.append(rg)
        v._bev_ring(ax,rg['floor'],'#202a37',linewidth=1.4,reference=True)
        arr=np.concatenate([g['floor'] for g in geoms]);lo=arr.min(axis=0);hi=arr.max(axis=0);pad=np.maximum(.06*(hi-lo),.08)
        v._style_bev(ax,[lo[0]-pad[0],hi[0]+pad[0],lo[1]-pad[1],hi[1]+pad[1]])
        ax.set_title('底面：原位置，未做配准',fontsize=10)
    fig.suptitle('相似总体质量可以对应不同速度；慢速的局部收益与失误必须同时保留',fontsize=17,y=.981)
    fig.text(.035,.948,'W109 / W112 的三个同图对照；均为普通 Manual、同一有效参考。案例用于解释画像，不能作为平均效应估计。',fontsize=10.5)
    fig.legend(handles=[Line2D([0],[0],color=WORKER_COLORS['W109'],lw=2,label='W109 原标注'),Line2D([0],[0],color=WORKER_COLORS['W112'],lw=2,label='W112 原标注'),Line2D([0],[0],color=REF_ERP,lw=3,label='固定参考（全景）'),Line2D([0],[0],color='#202a37',ls='--',lw=1.5,label='固定参考（底面）')],loc='upper left',bbox_to_anchor=(.031,.928),ncol=4,frameon=False,fontsize=10)
    fig.text(.035,.035,'原标注线使用当前研究处理点，沿既定环序绘制；此图未运行融合。耗时是新批次报告的处理后任务活动时间，未重放原始日志，亦非排队或交付时间。\n代表例按画像差异事后选择；保留一个“慢而更好”正例与一个“慢而失准”反例。完整逐人统计与15张共同困难图结果见画像表。',fontsize=9.3,va='top',linespacing=1.5)
    args.out.parent.mkdir(parents=True,exist_ok=True);fig.savefig(args.out,dpi=160);plt.close(fig)
    args.out.with_suffix('.json').write_text(json.dumps(dict(case_selection=panels,record_summary=summary),ensure_ascii=False,indent=2),encoding='utf8')
    print(args.out)

if __name__=='__main__':main()
