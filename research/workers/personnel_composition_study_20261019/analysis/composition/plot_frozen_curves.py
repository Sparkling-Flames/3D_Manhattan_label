"""Export numeric plotting data and exact scientific figures, without refitting labels."""
import argparse,json,gzip,collections,os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/composition_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from fusion_runner import read

COLORS={'discovery':'#2286a6','validation':'#bd5f27'}

def configure(font):
    font_manager.fontManager.addfont(str(font));name=font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'font.family':name,'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':170,'figure.facecolor':'white','axes.labelcolor':'#344456','text.color':'#213145','axes.grid':True,'grid.alpha':.18})

def cell_read(p):
    use=['method_id','domain','pool_id','image','building','difficulty','k','composition','B8L2_mean','B8L2_p10','B8L2_min','B8L2_max','complete_rate','score_available_rate','nodes_mean','diag_corner_recall_05_mean','diag_wall_coverage_05_mean','team_keys']
    cols=pd.read_csv(p,nrows=0).columns
    return pd.read_csv(p,usecols=[c for c in use if c in cols])

def parse(s):return {p.split(':')[0]:int(p.split(':')[1]) for p in s.split('|')}

def balanced_curves(base,out,source_dir=None):
    fig,axs=plt.subplots(2,2,figsize=(11.5,7.6),sharey=True)
    allrows=[];support=[]
    if source_dir:
        saved=pd.read_csv(source_dir/'composition_ratio_plot_data.csv.gz')
        saved_support=pd.read_csv(source_dir/'curve_common_support.csv')
    for row,(method,target,label,prefix) in enumerate([
        ('F_rule_Q_quantile_K3','C03','历史相对 Q 三等分：低类 → 高类','grid_confirm_'),
        ('R_geo9_source_signed_p2_K2','C02','反向历史关系二类：C01 → C02','grid_curves_')]):
      for phase in ['discovery','validation']:
        if source_dir:
            d=saved[saved.method_id.eq(method)&saved.phase.eq(phase)].copy()
        else:
            d=cell_read(base/(prefix+phase)/'cell_summary.csv.gz');d=d[d.method_id.eq(method)].copy()
            d['counts']=d.composition.map(parse)
            if target=='C03':d=d[d.counts.map(lambda z:z.get('C02',0)==0)]
            d['target_n']=d.counts.map(lambda z:z[target])
        for col,k in enumerate([5,9]):
          ax=axs[row,col];g=d[d.k.eq(k)].copy()
          # Fix the image set over the whole declared ratio curve. Unavailable
          # and non-scored positions are counted explicitly, never filled by 0.
          npos=g.groupby('pool_id').target_n.nunique();full=set(npos[npos.eq(k+1)].index)
          bad=set(g.loc[g.B8L2_mean.isna(),'pool_id']);common=full-bad
          h=g[g.pool_id.isin(common)].copy();h['phase']=phase;h['target_fraction']=h.target_n/k
          h['curve_method']=label;allrows.append(h.drop(columns=['counts'],errors='ignore'))
          buildings=h.building.nunique();images=h.image.nunique();support.append(dict(method_id=method,phase=phase,k=k,any_ratio_pools=g.pool_id.nunique(),all_ratios_feasible_pools=len(full),all_ratios_scored_pools=len(common),buildings=buildings,excluded_any_missing_score=len(full & bad)))
          means=h.groupby(['building','target_n'])[['B8L2_mean','B8L2_p10']].mean().groupby('target_n').mean()
          ax.plot(means.index/k,means.B8L2_mean,'o-',color=COLORS[phase],lw=2.0,ms=4,label=('发现新成员' if phase=='discovery' else '建筑留出')+'均值')
          ax.plot(means.index/k,means.B8L2_p10,'--',color=COLORS[phase],lw=1.3,label=('发现' if phase=='discovery' else '留出')+'成员低尾p10')
          ax.text(.02,.07+(phase=='discovery')*.065,('发现' if phase=='discovery' else '留出')+f'：{images}图／{buildings}楼，同一图集',transform=ax.transAxes,fontsize=8.5,color=COLORS[phase])
          ax.set_title(label+f'\nn={k}',fontsize=11,pad=8);ax.set_xlabel('高侧类别人数 / 总人数');ax.set_ylim(35,101);ax.set_xlim(-.025,1.025);ax.set_xticks([0,.2,.4,.6,.8,1])
          if col==0:ax.set_ylabel('冻结 B8L2（0–100）')
    axs[0,0].legend(loc='upper left',ncol=2,fontsize=8,frameon=False)
    fig.suptitle('固定人数、固定图片支持下，类别比例与融合质量',x=.055,ha='left',fontsize=17,fontweight='bold')
    fig.text(.055,.025,'每图先对实际团队取值，再按建筑等权。虚线是每图团队分布的p10再等权，并非置信界。\n仅保留整条比例曲线均有评分的共同图片；缺失与容量排除见 curve_common_support.csv，原始失败仍留账。',fontsize=9,color='#526273')
    fig.subplots_adjust(top=.86,bottom=.17,hspace=.40,wspace=.19);fig.savefig(out/'composition_ratio_curves.png');plt.close(fig)
    if not source_dir:
        pd.concat(allrows,ignore_index=True).to_csv(out/'composition_ratio_plot_data.csv.gz',index=False);pd.DataFrame(support).to_csv(out/'curve_common_support.csv',index=False)

def counter_member_plot(base,out,source_dir=None):
    pid='yqstnuAEVhm-27__manual__36afe2b79d';rows=[]
    selections=[('初筛4队','DISCOVERY_GRID_REQUESTS.json.gz','runs'),('复查新成员10队','DISCOVERY_CONFIRM_REQUESTS.json.gz','runs_final')]
    chosen={(9,0):'纯R1',(3,6):'3 R1 + 6 R2',(4,5):'4 R1 + 5 R2',(0,9):'纯R2'}
    for stage,req,run in ([] if source_dir else selections):
        d=read(base/req);teams={t['team_key']:t for t in read(base/run/'pools'/(pid+'.json.gz'))['teams']};seen=set()
        for q in d['requests']:
            if q['pool_id']!=pid or q.get('method_id')!='R_role_ward_K5' or q['k']!=9:continue
            cs=q['counts'];pair=(cs['C01'],cs['C02'])
            if pair not in chosen or sum(cs[c] for c in ['C03','C04','C05']):continue
            if q['team_key'] in seen:continue
            seen.add(q['team_key']);t=teams[q['team_key']];rows.append(dict(stage=stage,composition=chosen[pair],team_key=t['team_key'],workers='|'.join(t['member_workers']),B8L2=t.get('B8L2'),D10=t.get('D10'),nodes=t.get('nodes'),score_status=t.get('score_status')))
    D=pd.read_csv(source_dir/'mixture_member_replication_plot_data.csv') if source_dir else pd.DataFrame(rows)
    if not source_dir:D.to_csv(out/'mixture_member_replication_plot_data.csv',index=False)
    fig,ax=plt.subplots(figsize=(11.5,4.7));colors=['#2286a6','#bd5f27']
    for i,(stage,_,_) in enumerate(selections):
      for j,label in enumerate(chosen.values()):
        h=D[D.stage.eq(stage)&D.composition.eq(label)].sort_values('team_key');pos=j+(i-.5)*.25
        ax.scatter(pos+np.linspace(-.055,.055,len(h)),h.B8L2,s=30,alpha=.75,color=colors[i],edgecolor='white',linewidth=.6,label=stage if j==0 else None,zorder=5)
        mean=h.B8L2.mean();ax.plot([pos-.09,pos+.09],[mean,mean],lw=3,color=colors[i]);ax.annotate(f'{mean:.1f}',(pos,mean),xytext=(0,8 if i else -16),textcoords='offset points',ha='center',fontsize=10,color=colors[i],fontweight='bold')
    ax.set_xticks(range(4),list(chosen.values()));ax.set_ylabel('每个真实团队的 B8L2');ax.set_ylim(25,105);ax.legend(ncol=2,frameon=False,loc='upper left');ax.set_title('漂亮的3:6混类优势，未在新成员组合中复现',loc='left',fontsize=17,fontweight='bold',pad=18)
    fig.text(.085,.025,'yqst-27，同一张中等图片、同一 n=9、同一冻结参考。短横线为构成均值；点为实际成员集合。\n3:6 相对较好纯类：初筛 +13.37 → 新成员复查 −2.71。新团队不是新的独立图片；各构成全队及反例均保留。',fontsize=9,color='#526273');fig.subplots_adjust(bottom=.22,top=.84);fig.savefig(out/'mixture_member_replication.png');plt.close(fig)

def threshold_plot(base,out,source_dir=None):
    rows=[]
    for phase in ([] if source_dir else ['discovery','validation']):
        t=pd.read_csv(base/('nested_'+phase)/'nested_transitions.csv.gz');rows.append(t)
    if source_dir:sel=pd.read_csv(source_dir/'threshold_transitions_plot_data.csv.gz')
    else:
        T=pd.concat(rows,ignore_index=True);sel=T[T.tag.ne('other')];sel.to_csv(out/'threshold_transitions_plot_data.csv.gz',index=False)
    fig,axs=plt.subplots(2,2,figsize=(11.5,7.8),sharex=True)
    titles=['困难域角色二类','全域角色五类（对照）'];methods=['R_role_ward_difficulty_K2','R_role_ward_K5']
    metrics=[('Q_change','B8L2 变化'),('corner_change','参考转角位置召回变化')]
    for c,method in enumerate(methods):
      for r,(metric,ylabel) in enumerate(metrics):
        ax=axs[r,c]
        for phase in ['discovery','validation']:
          for tag,style,lbl in [('critical_2m_to_2m1','-','门槛上调步'),('earlier_no_threshold_step','--','紧邻前一步')]:
            g=sel[sel.method_id.eq(method)&sel.phase.eq(phase)&sel.tag.eq(tag)];b=g.groupby(['fixed_n','building','image'])[metric].mean().groupby(['fixed_n','building']).mean();means=b.groupby('fixed_n').mean()
            ax.plot(means.index,means.values,style,marker='o' if tag.startswith('critical') else '.',lw=2 if tag.startswith('critical') else 1,color=COLORS[phase],label=('发现' if phase=='discovery' else '留出')+lbl)
            if tag.startswith('critical'):
                for (m,building),v in b.items():ax.scatter(m+(list(b.index.get_level_values(1).unique()).index(building)-2.5)*.027,v,color=COLORS[phase],s=12,alpha=.45,zorder=3)
        ax.axhline(0,color='#4c5968',lw=.8);ax.set_ylabel(ylabel);ax.set_xticks([3,4,5,6]);ax.set_title(titles[c] if r==0 else '',fontsize=12)
        if r==1:ax.set_xlabel('固定细节角色人数 m（具体成员不变）')
    axs[0,0].legend(ncol=2,frameon=False,fontsize=8,loc='lower left')
    for ax in axs[0]:ax.set_ylim(-21,7)
    for ax in axs[1]:ax.set_ylim(-.21,.075)
    fig.suptitle('类别比例与票数门槛交互：n=2m → 2m+1',x=.055,ha='left',fontsize=17,fontweight='bold')
    fig.text(.055,.025,'每条链只加入一名另一角色成员；细点为各建筑均值，连线为建筑等权均值。所有失败保留，数值变化仅用可比输出。\n困难标签源于既有非盲全景／参考复核：这是该条件下的机制复查，非新图自动采集前预测。参考转角是几何诊断，非必要结构语义金标。',fontsize=9,color='#526273')
    fig.subplots_adjust(top=.89,bottom=.17,hspace=.22,wspace=.22);fig.savefig(out/'vote_threshold_interaction.png');plt.close(fig)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,default=Path('analysis/composition'));ap.add_argument('--out',type=Path,default=Path('analysis/figures_summary'));ap.add_argument('--font',type=Path,default=Path('analysis/fonts/NotoSansSC-Regular.ttf'));ap.add_argument('--from-sources',action='store_true');ap.add_argument('--source-dir',type=Path,default=Path('analysis/figures_summary'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);configure(a.font);src=a.source_dir if a.from_sources else None;balanced_curves(a.base,a.out,src);counter_member_plot(a.base,a.out,src);threshold_plot(a.base,a.out,src)

if __name__=='__main__':main()
