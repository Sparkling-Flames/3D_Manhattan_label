"""Render the corrected onset figure and add saved evidence to the existing workbench."""
from pathlib import Path
import os
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR', str(Path(os.environ['TEMP'])/'hohonet_image_response_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
TOP=ROOT/'research/workers/image_response_v21_20261101'
SRC=TOP/'HOHONET_v21_image_response_20261101'
OUT=TOP/'integration'


def main():
    OUT.mkdir(exist_ok=True)
    data=pd.read_csv(SRC/'stage08_figures/01_Onset_by_Difficulty_data.csv.gz')
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    colors=['#2276a5','#a86b08','#a64967']
    titles=['Mean quality: remaining range ≤ 2 points','P10 quality: remaining range ≤ 2 points','Quality SD: remaining range ≤ 1 point','Floor diversity: all later mean 1−IoU ≤ 0.10']
    for ax,metric,title in zip(axes.flat,['B8L2_mean','B8L2_p10','B8L2_sd','V_floor'],titles):
        for group,n,color,style in zip(['Easy','Medium','Hard'],[130,39,37],colors,['-','--',':']):
            rows=data[data.metric.eq(metric)&data.difficulty.eq(group)].sort_values('k')
            assert len(rows)==33 and rows.all_images.eq(n).all()
            assert ((rows.proportion-rows.onsets_at_or_before_k/n).abs()<1e-12).all()
            ax.step(rows.k,100*rows.proportion,where='post',label=f'{group} (n={n})',color=color,linestyle=style,lw=2)
        ax.set(title=title,xlabel='Annotators at onset (k)',ylabel='Share within each difficulty group (%)',ylim=(0,101),xlim=(3,35))
        ax.grid(alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Cumulative onset proportions across team sizes for ordinary Manual images',fontsize=15)
    fig.supxlabel('Retrospective onset; all later counts qualify, with at least max(5, ceil(0.15 N)) further annotators observed.',fontsize=9)
    for ext in ['png','pdf','svg']:
        fig.savefig(OUT/f'01_Onset_by_Difficulty.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)
    base='../../workers/image_response_v21_20261101/'
    source=base+'HOHONET_v21_image_response_20261101/'
    section='''<section id="image-response"><h2>逐图人数响应：均值、低尾与稳定性</h2><p>普通Manual 206图中，163图找到平均Q尾段范围≤2分的起点：简单123/130、中等25/39、困难15/37；找到起点的图片中位人数为9、16、17。其余43图也保留在逐图入口。起点是回看完整曲线得到的描述，不是在线停标规则。</p><p>固定171图20→30人，平均Q +0.500，P10 +2.848（166图提高），Q标准差 −2.031（168图降低），底面波动170图降低。困难27图平均Q −0.174，但逐图变化绝对值平均4.772，16升11降，只有7图在±2分内：总体均值掩盖了逐图升降。</p><p>当前门洞584/439筛后17图，3→6人每图可评Q均提高，完整可评输出却由3770降至3516/4352；10→14均Q +0.324，逐图绝对变化3.185。质量采用可评团队，状态采用全部尝试；整体和单侧空间使用各自人员池与参考。</p>'''
    names=['01_Onset_by_Difficulty','02_Fixed171_Count_Response','03_Image_Changes_20_to_30','04_Doorway_Common14_Screening','05_Stability_Is_Not_Accuracy','06_Doorway_Geometry_Response']
    captions=['各难度组内累计起点比例；分母130/39/37，未找到起点仍在分母内。','同171图的早段与后段均值、低尾和波动。','逐图20→30变化：均值不能代替升降分布。','门洞同17图、共同人数3—14：质量和输出状态分开。','稳定的质量曲线可以停在较低质量水平。','门洞几何波动与相邻人数响应；全部路径配对不等于穷举全部团队。']
    for i,(name,caption) in enumerate(zip(names,captions)):
        path=base+'integration/'+name if i==0 else source+'stage08_figures/'+name
        section+=f'<details><summary>{caption}</summary><figure><a href="{path}.png"><img src="{path}.png" loading="lazy" alt="{caption}"></a><figcaption>{caption} <a href="{path}.pdf">PDF</a> · <a href="{path}.svg">SVG</a> · <a href="{source}stage08_figures/{name}_data.csv.gz" download>源表</a></figcaption></figure></details>'
    links=[('stage08_figures/IMAGE_ATLAS_ZH.html','223图可筛选图册：普通206图＋门洞17图'),('stage09_report/IMAGE_RESULTS_INDEX_ZH.html','逐图完整指标、起点及人数区间'),('stage05_cases/manual/VFuaQ6m2Qom-04/VIEWER.html','VFua-04：满员35人仍不足四节点'),('stage05_cases/manual/e9zR4mvMWw7-17/VIEWER.html','e9z-17：节点全票，位置仍变化'),('stage05_cases/manual/pa4otMbVnkk-11/VIEWER.html','pa4-11：相对当前四角目标的共同偏离'),('stage04_doorway_cases/DOORWAY_LATE_RESPONSE_EVIDENCE.html','uNb-47与jh4-09：近满员门洞响应')]
    section+='<h3>全部图片与精确案例</h3><ul>'+''.join(f'<li><a href="{source}{p}">{label}</a></li>' for p,label in links)+'</ul>'
    section+=f'<p><a href="{base}README.md">独立验收与全部定义</a> · <a href="{base}integration/README.md">v2→v2.1变化与接入记录</a></p><p>自然256路径保持原身份；普通、Semi、其它目标和门洞分开。接近满员时团队重合更多，满员只有一队。本轮未改分类或验证新进入策略。</p></section>'
    page=ROOT/'research/statistics/research_explorer_v1_r2_20261017/v21-results.html'
    text=page.read_text(encoding='utf-8')
    if '<section id="image-response">' in text:
        a=text.index('<section id="image-response">');b=text.index('</section>',a)+len('</section>');text=text[:a]+section+text[b:]
    else:
        assert '<section id="admitted-space">' in text
        text=text.replace('<section id="admitted-space">',section+'\n<section id="admitted-space">',1)
        text=text.replace('<a href="#population">人数曲线</a>','<a href="#population">人数曲线</a><a href="#image-response">逐图人数响应</a>',1)
    page.write_text(text,encoding='utf-8')


if __name__=='__main__':
    main()
