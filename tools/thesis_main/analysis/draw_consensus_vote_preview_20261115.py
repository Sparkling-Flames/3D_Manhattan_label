"""Preview the support rule using the existing six-person computed example."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import draw_consensus_method_illustration_20261114 as method

OUT = Path(__file__).resolve().parents[3] / 'docs/thesis_main/论文写作工作资料/共识投票图候选_20261115'


def main():
    obs = method.simulate()
    result = method.run_pipeline(obs, method.G_SKIP)
    groups = {g['truth']: g for g in result['groups']}
    rows = [('BL', 'Main-wall corner', 'W', '#0072B2', 58),
            ('R2', 'Recess corner', 'K', '#D55E00', 38),
            ('S', 'Extra detail', 'E', '#899197', 18)]
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
                         'pdf.fonttype':42, 'svg.fonttype':'none'})
    fig = plt.figure(figsize=(10.5,4.9))
    ax = fig.add_axes([.025,.10,.95,.85])
    ax.set(xlim=(0,100),ylim=(5,103));ax.axis('off')
    columns = np.linspace(28,59,6)
    ax.text(10,101,'Which corner?',ha='center',va='top',fontsize=12)
    ax.text(43.5,101,'Whose layout contains it?',ha='center',va='top',fontsize=12)
    ax.text(77,101,'Support',ha='center',va='top',fontsize=12)
    ax.text(95,101,'Decision',ha='center',va='top',fontsize=12)

    def footprint(person, bounds, focus=None):
        left,bottom,width,height=bounds
        local=fig.add_axes([.025+left*.0095,.10+bottom*.85/103,width*.0095,height*.85/103])
        data=obs[method.NAMES.index(person)]
        xy=np.array([method.floor_point(o['az'],o['low'])[:2] for o in data])
        local.plot(*np.vstack([xy,xy[0]]).T,color='#737D84',lw=1)
        for truth,_,label,color,_ in rows:
            if focus is not None and focus != truth:continue
            found=[i for i,o in enumerate(data) if o['truth']==truth]
            if found:
                pos=xy[found[0]]
                local.plot(*pos,'o',ms=5 if focus else 3.5,mfc='white',mec=color,mew=1.2)
                if focus:local.annotate(label,pos,(4,4),textcoords='offset points',fontsize=9,color=color)
        local.set(xlim=(-3.1,3.1),ylim=(-2.4,3.6),aspect='equal');local.axis('off')

    for x,person in zip(columns,method.NAMES):
        ax.text(x,92,person,ha='center',fontsize=10)
        footprint(person,(x-3,72,6,17))
    ax.plot([0,100],[69,69],color='#CAD0D4',lw=.8)
    ax.add_patch(Rectangle((0,29),100,18,fc='#FFF5ED',ec='none',zorder=-2))
    threshold=66+22*3/6
    ax.text(77,66,'6 people: keep ≥ 3',ha='center',fontsize=10)
    ax.plot([threshold,threshold],[11,63],ls='--',color='#30373C',lw=1,zorder=5)
    record=[]
    for truth,label,tag,color,y in rows:
        group=groups[truth]
        supporters={result['flat'][t]['annotator'] for t in group['members']}
        assert len(supporters)==group['support']
        assert group['retained']==(2*len(supporters)>=len(obs))
        footprint('A5' if truth=='S' else 'A1',(1,y-8,10,17),truth)
        ax.text(12,y+2,label,va='center',fontsize=10)
        ax.text(12,y-3,tag,color=color,va='center',fontsize=10,fontweight='bold')
        for x,person in zip(columns,method.NAMES):
            if person in supporters:
                ax.plot([x-.7,x-.15,x+.9],[y,y-1.4,y+2],color='#30373C',lw=1.65,solid_capstyle='round')
            else:ax.plot(x,y,'.',color='#CBD1D5',ms=4)
        ax.add_patch(Rectangle((66,y-2.2),22,4.4,fc='#EFF1F3',ec='none'))
        end=66+22*len(supporters)/6
        ax.add_patch(Rectangle((66,y-2.2),end-66,4.4,fc=color,ec='none'))
        ax.text(end+.9,y,str(len(supporters)),va='center',fontsize=11)
        retained=group['retained']
        ax.add_patch(Rectangle((91,y-1.9),2.3,3.8,fc=color if retained else 'white',ec=color,
                               hatch=None if retained else '////',lw=.8))
        ax.text(94,y,'Keep' if retained else 'Omit',va='center',fontsize=11)
        if truth=='R2':ax.text(77,y-6.8,'Exactly half: kept',ha='center',fontsize=9,color=color,
                               bbox=dict(fc='#FFF5ED',ec='none',pad=1),zorder=6)
        record.append(dict(corner=tag,supporters=sorted(supporters),count=len(supporters),retained=retained))
    fig.text(.03,.047,'✓  Corner included     ·  Corner not drawn       One vote per person and corner.',fontsize=11)
    fig.text(.03,.011,'Illustrative example, n = 6. Correspondence groups are established before counting.',fontsize=9,color='#59636A')
    OUT.mkdir(parents=True,exist_ok=True)
    for ext in ['pdf','svg','png']:fig.savefig(OUT/f'consensus_vote_preview.{ext}',dpi=240)
    plt.close(fig)
    (OUT/'support_counts.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(record)


if __name__=='__main__':main()
