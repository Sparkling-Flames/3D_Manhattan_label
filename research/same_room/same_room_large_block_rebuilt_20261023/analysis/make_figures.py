"""Static scientific figures from completed tables; no outcome selection."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

LABELS={'ordinary_all':'All designs','ordinary_pure':'Pure blocks (D empty)',
        'ordinary_mixed':'Mixed teams (D nonempty)',
        'ordinary_mixed_more_half':'Mixed, m/n > 1/2',
        'ordinary_mixed_half':'Mixed, m/n = 1/2',
        'ordinary_mixed_less_half':'Mixed, m/n < 1/2'}

def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=190,bbox_inches='tight')
    fig.savefig(out/(name+'.pdf'),bbox_inches='tight');plt.close(fig)

def main(root):
    root=Path(root);out=root/'figures';out.mkdir(exist_ok=True)
    allover=pd.read_csv(root/'results/OVERALL_CONDITIONS.csv')
    over=allover[(allover.method=='V3_BEHAVIOR')&(allover.condition=='manual')].set_index('subset')
    pair=pd.read_csv(root/'results/PAIR_METRICS.csv.gz')
    pair=pair[(pair.method=='V3_BEHAVIOR')&(pair.condition=='manual')]
    names=[x for x in ['ordinary_pure','ordinary_mixed','ordinary_mixed_more_half','ordinary_mixed_half','ordinary_mixed_less_half'] if x in over.index]
    fig,axes=plt.subplots(1,2,figsize=(14,5.3),layout='constrained')
    y=np.arange(len(names));z=over.loc[names]
    axes[0].barh(y-.16,z['pair_equal__B8L2_within'],height=.3,color='#b2bec3',label='Within: |B-A|')
    axes[0].barh(y+.16,z['pair_equal__B8L2_cross'],height=.3,color='#2d709a',label='Cross: (|C-A|+|C-B|)/2')
    axes[0].set_yticks(y,[LABELS[n]+f'\n{int(over.loc[n,"Q_pairs"])} pairs / {int(over.loc[n,"Q_buildings"])} buildings' for n in names])
    axes[0].invert_yaxis();axes[0].set_xlabel('B8L2 points, equal physical-pair weighting');axes[0].legend(fontsize=9)
    axes[0].set_title('Matched within/cross-class magnitude')
    colors=plt.get_cmap('tab10');blds=sorted(pair[pair.subset=='ordinary_all'].building.unique());bc={b:colors(i%10) for i,b in enumerate(blds)}
    for i,name in enumerate(names):
        p=pair[pair.subset==name].dropna(subset=['B8L2_extra']).sort_values('pair_key')
        offset=np.linspace(-.13,.13,len(p)) if len(p)>1 else [0]
        axes[1].scatter(p.B8L2_extra,i+np.asarray(offset),s=15,c=[bc[b] for b in p.building],alpha=.65)
        axes[1].scatter(over.loc[name,'pair_equal__B8L2_extra'],i,s=95,marker='D',color='black',label='Pair equal' if i==0 else None,zorder=3)
        axes[1].scatter(over.loc[name,'building_equal__B8L2_extra'],i,s=110,marker='x',linewidth=2,color='#bb3e03',label='Building equal' if i==0 else None,zorder=4)
    axes[1].axvline(0,color='gray',lw=1);axes[1].set_yticks(y,[LABELS[n] for n in names]);axes[1].invert_yaxis()
    axes[1].set_xlabel('Cross magnitude minus within magnitude (Q points)');axes[1].legend(fontsize=9)
    axes[1].set_title('One dot per physical pair; color = building')
    fig.suptitle('Current Manual structure classes | strict ABC in both views\nSubgroup supports differ; differences between rows are not a replacement-size effect',fontsize=12)
    save(fig,out,'01_PURE_MIXED_MATCHED_MAGNITUDES')

    buildings=pd.read_csv(root/'results/BUILDING_METRICS.csv.gz')
    buildings=buildings[(buildings.method=='V3_BEHAVIOR')&(buildings.condition=='manual')&(buildings.weighting=='pair_then_building')]
    fig,ax=plt.subplots(figsize=(12,5.2),layout='constrained');x=np.arange(len(blds))
    for shift,name,color in [(-.18,'ordinary_mixed','#2d709a'),(.18,'ordinary_mixed_less_half','#d78833')]:
        s=buildings[buildings.subset==name].set_index('building').reindex(blds)
        ax.bar(x+shift,s.B8L2_extra,width=.34,label=LABELS[name],color=color)
    ax.axhline(0,color='black',lw=.8);ax.set_xticks(x,blds,rotation=40,ha='right');ax.set_ylabel('Cross-minus-within Q magnitude (points)')
    ax.set_title('Each building separately | configurations then pairs within building');ax.legend()
    save(fig,out,'02_BUILDING_EFFECTS')

    r=over.loc['ordinary_mixed'];fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    groups=[('both_near_zero','Both near zero','#bbc0c5'),('both_gain','Both improve','#26856b'),
            ('both_loss','Both decline','#9b393b'),('opposite','Opposite responses','#df9b31'),('one_response','One view responds','#8064a2')]
    for ax,eps in zip(axes,['eps0','eps2']):
        bottom=np.zeros(3)
        for key,label,color in groups:
            vals=np.array([r[f'pair_equal__{eps}_{c}_{key}'] for c in ['BA','CA','CB']],float)*100
            ax.bar(np.arange(3),vals,bottom=bottom,label=label,color=color,width=.58)
            for j,v in enumerate(vals):
                if v>=7:ax.text(j,bottom[j]+v/2,f'{v:.1f}%',ha='center',va='center',fontsize=9,color='white' if key in ['both_gain','both_loss','one_response'] else 'black')
            bottom+=vals
        ax.set_xticks(np.arange(3),['Within B-A','Cross C-A','Cross C-B']);ax.set_ylim(0,100)
        ax.set_ylabel('Percent of matched adjustments, configuration / pair equal')
        ax.set_title('Exact zero threshold' if eps=='eps0' else 'Response requires |delta Q| > 2')
    axes[1].legend(loc='upper left',bbox_to_anchor=(1,1),fontsize=9)
    fig.suptitle('Mixed teams (D nonempty): the same actual adjustment in both views | six endpoints jointly evaluable',fontsize=12)
    save(fig,out,'03_CROSS_VIEW_RESPONSE_STATES')

    directions=pd.read_csv(root/'results/DIRECTION_RESULTS.csv')
    d=directions[(directions.method=='V3_BEHAVIOR')&(directions.condition=='manual')&(directions.subset=='ordinary_mixed')].copy()
    def english(x):
        for a,b in [('常规转折','regular turns'),('较少转折','fewer turns'),('较多转折','more turns'),('较少近共线分段','less redundant'),('较多近共线分段','more redundant'),('、',', ')]:x=x.replace(a,b)
        return x
    d=d.sort_values(['pairs','source_role_key','target_role_key'],ascending=[False,True,True]);y=np.arange(len(d))
    fig,axes=plt.subplots(1,2,figsize=(14,max(4.5,len(d)*.7)),layout='constrained')
    labels=[english(a)+' -> '+english(b)+f'\n{int(p)} pairs / {int(k)} buildings' for a,b,p,k in zip(d.source_role_key,d.target_role_key,d.Q_pairs,d.Q_buildings)]
    for ax,col,title,color in [(axes[0],'pair_equal__B8L2_CS','Signed C - (A+B)/2','#26856b'),(axes[1],'pair_equal__B8L2_extra','Cross magnitude minus within','#2d709a')]:
        ax.barh(y,d[col],color=color);ax.axvline(0,color='black',lw=.8);ax.invert_yaxis();ax.set_xlabel('B8L2 points');ax.set_title(title)
    axes[0].set_yticks(y,labels,fontsize=9);axes[1].set_yticks(y,['']*len(d))
    fig.suptitle('Actual class directions in mixed teams | role alignment retains family and class count',fontsize=12)
    save(fig,out,'04_CLASS_DIRECTION_EFFECTS')
    (out/'FIGURE_RECEIPT.json').write_text(json.dumps({'new_calculations':'display of saved summaries only',
       'figures':4,'input_tables':['results/OVERALL_CONDITIONS.csv','results/PAIR_METRICS.csv.gz',
       'results/BUILDING_METRICS.csv.gz','results/DIRECTION_RESULTS.csv'],
       'magnitude_row_contrasts':'descriptive on different supports, not a scale causal estimate',
       'axes':'Q in 0-100 point units; no smoothed outcomes or selective missing-value replacement'},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');a=p.parse_args();main(a.root)
