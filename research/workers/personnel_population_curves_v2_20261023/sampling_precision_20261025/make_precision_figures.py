#!/usr/bin/env python3
"""Publication/export figures from completed, saved supplemental estimates."""
from pathlib import Path
import argparse, hashlib, io, json, os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_precision_mpl')
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from PIL import Image

COLORS={'简单':'#167E8C','中等':'#D18D20','困难':'#9B4D79'}
VERSIONS={'old24':('原24','#667787'),'new24':('新增24','#AA74A0'),'pooled48':('合并48','#167E8C'),'focus96':('重点96','#D18D20')}

def setup():
    font=Path(os.environ.get('HOHONET_CJK_FONT','/usr/local/share/fonts/panorama/NotoSansCJKsc-Regular.otf'))
    if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'font.size':10,'axes.titlesize':13,'axes.labelsize':10,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.unicode_minus':False,'pdf.fonttype':42,
                         'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})

def save_figure(fig,out,stem):
    out.mkdir(parents=True,exist_ok=True);receipt=[]
    for fmt in ['png','pdf']:
        buff=io.BytesIO();fig.savefig(buff,format=fmt,dpi=180,bbox_inches='tight');raw=buff.getvalue()
        if fmt=='png':Image.open(io.BytesIO(raw)).load()
        path=out/f'{stem}.{fmt}';tmp=path.with_suffix(path.suffix+'.tmp')
        with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        assert tmp.read_bytes()==raw;tmp.replace(path)
        receipt.append(dict(file=path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    plt.close(fig);return receipt

def common_curve(data,metric,pools,difficulty,versions=('old24','new24','pooled48')):
    g=data[data.pool_id.isin(pools)&data.difficulty.eq(difficulty)&data.version.isin(versions)]
    wide=g.pivot(index=['pool_id','k'],columns='version',values=metric).dropna(subset=list(versions))
    return wide.groupby('k').mean(),wide.groupby('k').size()

def natural_figures(root,out):
    p=root/'analysis_precision/new_results'
    d=pd.read_csv(p/'NATURAL_POOL_K_BATCH_PRECISION.csv.gz',low_memory=False)
    s=pd.read_csv(p/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz',low_memory=False)
    pools=set(d.loc[(d.layer=='ordinary_manual')&(d.pool_n>=30),'pool_id'])
    meta=d[d.pool_id.isin(pools)][['pool_id','building','difficulty']].drop_duplicates('pool_id')
    exact_path=p/'EXACT_FINITE_MARGINAL_STATISTICS.csv'
    exact=pd.read_csv(exact_path) if exact_path.exists() else pd.DataFrame()
    fig,axes=plt.subplots(2,2,figsize=(12,8.2),sharex=True)
    metrics=[('Q_mean','平均质量 Q（可评分队）',1),('Q_p10','图内低尾 P10',1),
             ('Q_sd_ddof1','图内质量标准差',1),('failure_rate','实际失败率（%）',100)]
    plotrows=[]
    for ax,(metric,title,mult) in zip(axes.flat,metrics):
        for difficulty,color in COLORS.items():
            curve,count=common_curve(d,metric,pools,difficulty)
            curve=curve.loc[(curve.index>=3)&(curve.index<=30)]
            ax.plot(curve.index,curve.old24*mult,ls='--',lw=1.4,color=color,alpha=.6)
            ax.plot(curve.index,curve.pooled48*mult,lw=2.2,color=color)
            if not exact.empty:
                exfield='Q_sd_population' if metric=='Q_sd_ddof1' else metric
                single=exact[exact.pool_id.isin(pools)&exact.difficulty.eq(difficulty)&exact.k.eq(1)]
                ax.plot([1],[single[exfield].mean()*mult],marker='D',ms=5,color=color,ls='none')
            c=s[(s.domain=='balanced_all')&(s.panel=='fixed_N_ge_30')&(s.kind=='curve')&(s.layer=='ordinary_manual')&
                (s.difficulty==difficulty)&(s.version=='pooled48')&(s.metric==metric)&(s.weighting=='image_equal')&
                (s.resampling=='path_MC_fixed_images')].copy()
            c['k']=pd.to_numeric(c.position,errors='coerce');c=c[c.k.isin([3,6,10,20,30])]
            ax.errorbar(c.k,c.estimate*mult,yerr=np.maximum(0,np.array([c.estimate-c.percentile_2_5,c.percentile_97_5-c.estimate])*mult),
                fmt='o',ms=3,color=color,capsize=2,lw=.8)
            for k,row in curve.iterrows():
                plotrows.append(dict(metric=metric,difficulty=difficulty,k=int(k),old24=row.old24,new24=row.new24,
                    pooled48=row.pooled48,common_images=int(count.loc[k])))
        ax.axvspan(1.7,2.3,color='#E9EEF1',alpha=.7,zorder=0)
        ax.set_title(title,loc='left',pad=10);ax.grid(axis='y',alpha=.15);ax.set_xlim(.4,30.5)
        ax.set_xticks([1,3,6,10,15,20,25,30]);ax.set_xlabel('参与人数 k')
    fig.suptitle(f'独立追加后，人数曲线怎样变化？\n普通 Manual 固定 {len(pools)} 图 / {meta.building.nunique()} 栋建筑',fontsize=17,y=1.02)
    handles=[Line2D([0],[0],color=c,lw=2,label=f'{di}（{sum(meta.difficulty==di)}图）') for di,c in COLORS.items()]
    handles += [Line2D([0],[0],color='#53616C',ls='--',label='原24条'),Line2D([0],[0],color='#53616C',lw=2.2,label='合并48条')]
    fig.legend(handles=handles,loc='lower center',ncol=5,bbox_to_anchor=(.5,-.005),frameon=False)
    fig.text(.01,-.045,'单人菱形：全池原答的精确边际；2人灰带：合同延期。误差线：固定图片路径重抽95%范围。失败用全部尝试，缺Q不填零。',fontsize=9,color='#53616C')
    fig.tight_layout(rect=(0,.045,1,.97))
    receipt=save_figure(fig,out,'F01_NATURAL_FIXED157_OLD24_VS48')
    pd.DataFrame(plotrows).to_csv(out/'F01_PLOT_DATA.csv',index=False)

    fig,axes=plt.subplots(2,2,figsize=(12,8.3),sharex=True)
    focus=set(d.loc[(d.layer=='ordinary_manual')&(d.version=='focus96')&(d.pool_n>=30),'pool_id'])
    ks=[3,6,10,20,30];rows=[]
    for ri,(label,ps,versions) in enumerate([('固定全部图',pools,['old24','pooled48']),('同一批重点图',focus,['old24','pooled48','focus96'])]):
        for ci,(field,title,target) in enumerate([('Q_mean_MCSE_analytic','单图平均Q的标准误',1),('P10_halfwidth','单图P10经验95%半宽',2)]):
            ax=axes[ri,ci];g=d[d.pool_id.isin(ps)].copy();g['P10_halfwidth']=(g.Q_p10_boot95_high-g.Q_p10_boot95_low)/2
            width=.2 if len(versions)==3 else .26
            for j,version in enumerate(versions):
                values=[]
                for k in ks:
                    w=g[g.k.eq(k)&g.version.isin(versions)].pivot(index='pool_id',columns='version',values=field).dropna(subset=versions)
                    x=w[version].to_numpy();values.append(x)
                    rows.append(dict(domain=label,version=version,k=k,metric=field,common_images=len(x),median=np.median(x),p90=np.quantile(x,.9),below_target=int((x<=target).sum())))
                pos=np.arange(len(ks))+(j-(len(versions)-1)/2)*width
                b=ax.boxplot(values,positions=pos,widths=width*.84,patch_artist=True,showfliers=False,whis=[10,90],manage_ticks=False,
                    medianprops={'color':'white','lw':1.5},boxprops={'linewidth':.5},whiskerprops={'linewidth':.8},capprops={'linewidth':.8})
                for box in b['boxes']:box.set_facecolor(VERSIONS[version][1])
            ax.axhline(target,color='#444444',ls=':',lw=1);ax.text(4.5,target,f'工作量尺 {target}',va='bottom',ha='right',fontsize=8)
            ax.set_title(f'{label}（{len(ps)}图）：{title}',loc='left');ax.set_xticks(np.arange(len(ks)),ks)
            ax.set_xlabel('参与人数 k');ax.set_ylabel('Q分');ax.grid(axis='y',alpha=.12);ax.set_ylim(bottom=0)
    handles=[Line2D([0],[0],color=VERSIONS[v][1],lw=7,label=VERSIONS[v][0]) for v in ['old24','pooled48','focus96']]
    fig.legend(handles=handles,loc='lower center',ncol=3,bbox_to_anchor=(.5,-.01),frameon=False)
    fig.suptitle('总体曲线稳定，不代表单图低尾已经精确',fontsize=17,y=1.01)
    fig.text(.01,-.05,'箱体为图间25%—75%，须线为10%—90%；每格各版本使用共同图片。重点图按原24噪声预先选定。',fontsize=9,color='#53616C')
    fig.tight_layout(rect=(0,.04,1,.97));receipt+=save_figure(fig,out,'F02_SINGLE_IMAGE_PRECISION')
    pd.DataFrame(rows).to_csv(out/'F02_PLOT_DATA.csv',index=False)
    return receipt

def policy_figures(root,out):
    p=root/'analysis_policy/results/POLICY_PRECISION_SUMMARY.csv'
    if not p.exists():return []
    d=pd.read_csv(p);d=d[(d.difficulty=='全部')&(d.phase=='early_3_to_half')&(d.weighting=='image_equal')]
    roles=['joint_highq_first','structure_moreturn_first','joint_fast_first','structure_dominant_first']
    names=['历史高Q类优先','较多转折类优先','历史快速类优先','人数最多结构类优先']
    batches=['old8','new8','combined16'];bcolors=['#667787','#AA74A0','#167E8C'];bnames=['原8条配对','新增8条配对','合并16条配对']
    fig,axes=plt.subplots(1,2,figsize=(12.8,5.6),sharey=True)
    for ax,kind,title in [(axes[0],'path','固定图片：路径抽样范围'),(axes[1],'building','固定路径：建筑重抽范围')]:
        for j,(batch,color,label) in enumerate(zip(batches,bcolors,bnames)):
            for i,role in enumerate(roles):
                r=d[(d.batch==batch)&(d.policy==role)&(d.metric=='paired_Q_delta')].iloc[0]
                ax.errorbar(r.estimate,i+(j-1)*.20,xerr=np.maximum(0,[[r.estimate-r[kind+'_lo']],[r[kind+'_hi']-r.estimate]]),fmt='o',ms=5,color=color,capsize=3,label=label if i==0 else None)
        ax.axvline(0,color='#555555',ls=':',lw=1);ax.set_title(title,loc='left');ax.set_xlabel('策略 − 配对自然路径：平均ΔQ')
        ax.grid(axis='x',alpha=.15);ax.set_yticks(range(4),names)
    axes[0].invert_yaxis()
    axes[1].legend(frameon=False,loc='lower right');fig.suptitle('优先进入策略：新增独立基础路径的实际复查',fontsize=16,y=1.02)
    fig.text(.01,-.035,'固定普通Manual四策略共同157图/22楼；每图前段为3≤k≤floor(N/2)，先图内按k平均，再图等权。两种范围分别解释。',fontsize=9,color='#53616C')
    fig.tight_layout();d.to_csv(out/'F03_PLOT_DATA.csv',index=False)
    return save_figure(fig,out,'F03_POLICY_INDEPENDENT_BASES')

def exact_figures(root,out):
    p=root/'analysis_precision/new_results/EXACT_ANCHOR_BATCH_ACCURACY.csv.gz'
    if not p.exists():return []
    all_rows=pd.read_csv(p)
    all_rows=all_rows[(all_rows.k==all_rows.pool_n-1)&(all_rows.pool_n>10)]
    d=all_rows[all_rows.layer=='ordinary_manual']
    fig,axes=plt.subplots(1,3,figsize=(12.8,4.5));rows=[]
    for ax,metric,title,mult in zip(axes,['Q_mean','Q_p10','failure_rate'],['均值绝对误差','P10与目录linear的绝对差','失败率绝对误差（百分点）'],[1,1,100]):
        selected=d[d.metric==metric] if metric!='failure_rate' else all_rows[(all_rows.metric==metric)&(all_rows.exact_value>0)]
        wide=selected.pivot(index='pool_id',columns='version',values='absolute_error').dropna(subset=['old24','new24','pooled48'])
        values=[wide[v].to_numpy()*mult for v in ['old24','new24','pooled48']]
        b=ax.boxplot(values,tick_labels=['原24','独立新24','合并48'],patch_artist=True,showfliers=False,whis=[10,90],medianprops={'color':'white'})
        for box,v in zip(b['boxes'],['old24','new24','pooled48']):box.set_facecolor(VERSIONS[v][1])
        for v,x in zip(['old24','new24','pooled48'],values):rows.append(dict(metric=metric,version=v,images=len(x),median=np.median(x),p90=np.quantile(x,.9),mean=np.mean(x),scope='exact failure probability > 0; ordinary and doorway' if metric=='failure_rate' else 'ordinary Manual N>10'))
        scope=f'真实有失败的{len(wide)}池' if metric=='failure_rate' else f'普通Manual {len(wide)}图'
        ax.set_title(title+'\n'+scope,loc='left');ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.15)
    fig.suptitle('用完整的 N−1 人有限总体，直接检查抽样误差',fontsize=16,y=1.03)
    fig.text(.01,-.04,'每图只有N种缺席一人的团队，已精确枚举。右图单列精确失败率>0的池（含门洞）；箱体25%—75%、须线10%—90%均为图间分布。\n未画10%—90%外的散点；P10最大目录偏差约45分，见报告wc2-46反例及完整误差表。',fontsize=9,color='#53616C')
    fig.tight_layout();pd.DataFrame(rows).to_csv(out/'F04_PLOT_DATA.csv',index=False)
    return save_figure(fig,out,'F04_EXACT_LEAVE_ONE_OUT_ACCURACY')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();setup()
    out=a.root/'figures';receipt=natural_figures(a.root,out)+policy_figures(a.root,out)+exact_figures(a.root,out)
    (out/'FIGURE_EXPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
