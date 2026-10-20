#!/usr/bin/env python3
"""Chinese publication figures from frozen nested summaries, with support curves."""
import os
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from assessment_summary_common import ROOT,HERE,write_json,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font',type=Path,default=ROOT/'analysis/fonts/NotoSansSC-Regular.ttf');args=ap.parse_args()
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt,font_manager
    from matplotlib.lines import Line2D
    font_manager.fontManager.addfont(str(args.font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(args.font)).get_name(),
        'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'axes.unicode_minus':False,
        'pdf.fonttype':42,'axes.spines.right':False,'axes.spines.top':False})
    out=HERE/'nested_new2';src=out/'curves_aggregate.csv.gz';curves=pd.read_csv(src)
    primary=pd.read_csv(out/'primary_n13_aggregate.csv.gz')
    c2='#206a9b';c5='#b8582b';colors={(2,'within'):'#238fbd',(2,'cross'):'#253d79',(5,'within'):'#de9141',(5,'cross'):'#9c302f'}
    outputs=[]
    for oc,ic in [('C01','C02'),('C02','C01')]:
        d=curves[(curves.outgoing_class==oc)&(curves.incoming_class==ic)]
        nat=d[d.cohort.eq('native_support')];fixed=d[d.cohort.eq('fixed_capacity_both_m_n5_to21')]
        p=primary[(primary.outgoing_class==oc)&(primary.incoming_class==ic)].set_index('m')
        fig,ax=plt.subplots(3,2,figsize=(13.6,11.7));fig.subplots_adjust(top=.862,bottom=.135,left=.073,right=.982,hspace=.48,wspace=.26)
        title=f'真实类别块替换：{oc} → {ic}（全新人团队）'
        fig.suptitle(title,x=.06,y=.965,ha='left',fontsize=20,fontweight='bold')
        fig.text(.06,.924,'A、B 保持类别构成，C 改变一个类别块；固定人员块后，同一人按顺序加入三臂共同背景。',fontsize=11)
        fig.text(.06,.900,'每图两条已冻结路径；图内先平均，再按楼等权。主比较 n=13、m=5；m=2 是换人比例较小的对照。',fontsize=10,color='#4a4a4a')
        # A: All feasible n, with m/n shown at fixed nodes below the axis.
        a=ax[0,0]
        for m,color in [(2,c2),(5,c5)]:
            g=nat[nat.m.eq(m)].sort_values('n');a.plot(g.n,g.net_B8L2_change,'o-',ms=3,lw=1.8,color=color,label=f'替换 {m} 人')
        a.axhline(0,color='#888',lw=.7);a.axvline(13,color='#777',ls=':',lw=.8)
        a.set_title('A  类别改变后的质量方向｜全部可行图片',loc='left');a.set_ylabel('C − B 的 B8L2 分数');a.set_xlabel('总人数 n（同一块占比为 m / n）');a.legend(fontsize=9)
        # B/C separate joint vs richer geometric shape and both sides explicitly.
        for a,(letter,metric,title) in zip([ax[0,1],ax[1,0]],[
            ('B','joint_stable_main','联合稳定：分数、底面、原节点与环序'),
            ('C','geometry_shape_main','形状稳定：去冗余节点后的边界与角点')]):
            for m in [2,5]:
                g=nat[nat.m.eq(m)].sort_values('n')
                for arm,linestyle in [('within','-'),('cross','--')]:
                    a.plot(g.n,g[arm+'_'+metric],linestyle,lw=1.7,color=colors[m,arm],
                        label=f'm={m}，'+('同构成 A↔B' if arm=='within' else '跨构成 A↔C'))
            a.set_title(f'{letter}  {title}',loc='left');a.set_ylabel('通过比例');a.set_xlabel('总人数 n');a.set_ylim(-.025,1.04)
            a.axvline(13,color='#777',ls=':',lw=.8);a.legend(ncol=2,fontsize=8,loc='lower right')
        # D: Fixed metadata support guards against changing-image interpretation.
        a=ax[1,1]
        for m,color in [(2,c2),(5,c5)]:
            g=fixed[fixed.m.eq(m)].sort_values('n')
            a.plot(g.n,g.net_B8L2_change,'o-',color=color,lw=1.8,ms=3,label=f'替换 {m} 人')
        a.axhline(0,color='#888',lw=.7);a.axvline(13,color='#777',ls=':',lw=.8)
        a.set_title('D  共同容量子集｜固定 14 图、5 楼',loc='left');a.set_ylabel('C − B 的 B8L2 分数');a.set_xlabel('总人数 n（两方向、两种 m 均可覆盖 5–21 人）');a.legend(fontsize=9)
        # E: Frozen n13 same 29 images. Show stability and signed quality distinctly.
        a=ax[2,0];ys=[3.3,2.6,1.3,.6];labels=['m=2 联合','m=2 形状','m=5 联合','m=5 形状']
        for y,m,metric in zip(ys,[2,2,5,5],['joint_stable_main','geometry_shape_main']*2):
            w=float(p.loc[m,'within_'+metric]);c=float(p.loc[m,'cross_'+metric])
            a.plot([c,w],[y,y],color='#c3c3c3',lw=3)
            a.scatter([w],[y],s=52,color=colors[m,'within'],zorder=3,marker='o')
            a.scatter([c],[y],s=48,color=colors[m,'cross'],zorder=3,marker='s')
            a.text(w,y+.13,f'{w:.3f}',ha='center',fontsize=8);a.text(c,y-.23,f'{c:.3f}',ha='center',fontsize=8)
        a.set_yticks(ys,labels);a.set_xlim(0,1.03);a.set_ylim(.1,3.8);a.set_xlabel('○ 同构成通过率；■ 跨构成通过率')
        a.set_title('E  固定 n=13｜共同 29 图、6 楼',loc='left')
        a.text(.02,.48,f'ΔQ：m=2  {p.loc[2,"net_B8L2_change"]:+.2f} 分\n       m=5  {p.loc[5,"net_B8L2_change"]:+.2f} 分',transform=a.transAxes,fontsize=10,color='#222',bbox=dict(facecolor='white',edgecolor='none',alpha=.9))
        # F: Actual distinct images for every integer n, including unsupported m5 nodes.
        a=ax[2,1]
        for m,color,offset in [(2,c2,1.1),(5,c5,-2.5)]:
            g=nat[nat.m.eq(m)].sort_values('n');a.plot(g.n,g.true_images,'o-',color=color,lw=1.5,ms=2.8,label=f'm={m}')
            for r in g.itertuples():a.text(r.n,r.true_images+offset,str(r.true_images),ha='center',va='center',fontsize=6.8,color=color)
        a.axvline(13,color='#777',ls=':',lw=.8);a.axhline(14,color='#888',lw=.7,ls='--')
        a.set_title('F  每个 n 的真实图片支持｜未测不补零',loc='left');a.set_ylabel('不同 image_id 数');a.set_xlabel('总人数 n');a.set_ylim(0,47);a.legend(fontsize=8,loc='upper right')
        for a in ax.flat:a.grid(alpha=.13)
        for a in [ax[0,0],ax[0,1],ax[1,0],ax[2,1]]:a.set_xticks([3,5,9,13,17,21,25,29,31])
        ax[1,1].set_xticks([5,7,9,11,13,15,17,19,21])
        fig.text(.06,.085,'替换比例示例：n=13 时 m=2 为 15.4%，m=5 为 38.5%；n=21 时分别为 9.5% 和 23.8%。',fontsize=10)
        fig.text(.06,.058,'口径：A–C 用于构成分离，C–B 用于改善/下降方向。质量均值仅使用可评分的成对结果；不完整队仍计入稳定与失败分母。',fontsize=9,color='#444')
        fig.text(.06,.035,'边界：14 图曲线控制图片支持，但两种 m 使用各自冻结的人员块；只有同一路径跨 n 时人员块完全固定。原评估来自既有 v2。',fontsize=9,color='#444')
        for ext,dpi in [('png',210),('pdf',None)]:
            path=out/f'NEW2_{oc}_TO_{ic}_CURVES_ZH.{ext}';fig.savefig(path,dpi=dpi);outputs.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
        plt.close(fig)
    write_json(out/'CHINESE_CURVE_FIGURE_RECEIPT.json',dict(source_aggregate_sha256=sha(src),
        primary_sha256=sha(out/'primary_n13_aggregate.csv.gz'),code_sha256=sha(Path(__file__)),font_sha256=sha(args.font),
        outputs=outputs,all_feasible_n_support_displayed=True,constant_capacity_image_cohort_displayed=True))
    print('Chinese two-direction figures complete',flush=True)


if __name__=='__main__':main()
