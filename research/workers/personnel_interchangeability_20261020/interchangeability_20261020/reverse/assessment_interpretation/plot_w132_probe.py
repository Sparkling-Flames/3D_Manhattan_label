#!/usr/bin/env python3
"""Two matched estimands of the single registered post hoc identity probe."""
import os
from pathlib import Path
import pandas as pd
from assessment_summary_common import ROOT,HERE,sha,write_json

def main():
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt,font_manager
    font=ROOT/'analysis/fonts/NotoSansSC-Regular.ttf';font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),
        'font.size':11,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    out=HERE/'w132_probe';src=out/'all_available_aggregate.csv.gz';d=pd.read_csv(src).sort_values('outgoing_class')
    fig,axes=plt.subplots(1,2,figsize=(11.6,5.5));fig.subplots_adjust(top=.76,bottom=.34,wspace=.45,left=.20,right=.97)
    fig.suptitle('W132 同类替代：固定原图片、背景与构成的事后机制检查',fontsize=16,x=.03,y=.975,ha='left')
    fig.text(.03,.905,'先前的删人分析改变了支持；这里逐一替换同一位置的人，其余成员不动。此图不替代主冻结评估。',fontsize=10)
    settings=[('net_B8L2_change','质量方向 C − B（B8L2分）'),('gap_geometry_shape_main','形状分离：同构成通过率 − 跨构成通过率')]
    for ax,(metric,title) in zip(axes,settings):
        for y,r in enumerate(d.itertuples()):
            a=getattr(r,'original_matched_'+metric);b=getattr(r,'replacement_matched_'+metric)
            ax.plot([a,b],[y,y],color='#acacac',lw=3)
            ax.scatter([a],[y],s=65,color='#666666',marker='o',label='原始事件' if y==0 else None,zorder=3)
            ax.scatter([b],[y],s=65,color='#007a8b',marker='D',label='同类替代均值' if y==0 else None,zorder=4)
            ax.annotate(f'{a:+.3f}',(a,y),xytext=(0,12),textcoords='offset points',ha='center',fontsize=10,color='#444')
            ax.annotate(f'{b:+.3f}',(b,y),xytext=(0,-23),textcoords='offset points',ha='center',fontsize=10,color='#006575')
        ax.set_yticks([0,1],['C01→C02\n42原事件，160替代\n26图／6楼','C02→C01\n43原事件，75替代\n26图／6楼'])
        ax.set_ylim(-.7,1.7);ax.invert_yaxis();ax.axvline(0,lw=.7,color='#999');ax.set_xlabel(title);ax.grid(axis='x',alpha=.16)
        if metric=='net_B8L2_change':ax.set_xlim(-8,9)
        else:ax.set_xlim(-.02,.36)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.57,.855),ncol=2,fontsize=10,frameon=False)
    fig.text(.03,.20,'关键位置检查：W132 只在 A 块时，17 原事件／33 替代的 B、C 完全相同，净质量方向逐条不变；',fontsize=11)
    fig.text(.03,.151,'该子集 C−B 仍为 +5.025 分，但 shape 分离从 0.1375 降至 0.0125。质量效用与相近关系受人员影响的方式不同。',fontsize=10)
    fig.text(.03,.075,'口径：同一原事件先等权平均全部可行 C02 替代者，再图内、楼内平均并楼等权；原／新质量为同一有限配对支持。',fontsize=9,color='#555')
    fig.text(.03,.035,'范围：仅既有 n13/m5 双向116原事件；85有替代容量、22无W132、9无可替代成员。没有因结果再选其他人或改变主规则。',fontsize=9,color='#555')
    outputs=[]
    for ext in ['png','pdf']:
        p=out/('W132_MATCHED_MECHANISM_ZH.'+ext);fig.savefig(p,dpi=210 if ext=='png' else None);outputs.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)))
    plt.close(fig);write_json(out/'FIGURE_RECEIPT.json',dict(source_sha256=sha(src),code_sha256=sha(Path(__file__)),outputs=outputs))
    print('W132 matched mechanism figure complete')


if __name__=='__main__':main()
