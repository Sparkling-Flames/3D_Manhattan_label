"""Figure 7: faithful saved geometry, clearer support-to-structure comparison.
Run python build.py. No repository, network or experiments required.
"""
from pathlib import Path
import json, importlib.util
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

R=Path(__file__).resolve().parent
# Reuse the supplied projection and median checks, with a local data path.
src=(R/'source/original_geometry.py').read_text().replace("ROOT/'data/consensus_case.json'", "ROOT/'consensus_case.json'")
namespace={'__file__':str(R/'source/original_geometry.py'),'__name__':'saved_geometry'}
exec(compile(src,'original_geometry.py','exec'),namespace)
reconstruct=namespace['reconstruct']; DATA=namespace['DATA']; namespace['verify']()
P=R/'panels';P.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':9,'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none','axes.linewidth':.6})
INK='#44316E'; GRAY='#7D878D'; COL=['#0072B2','#D55E00']; MK=['o','^']
def save(f,name):
    for ext in ['pdf','svg','png']:f.savefig(P/f'{name}.{ext}',dpi=600)
    plt.close(f)
def poly(p):
    b,_=reconstruct(p);return np.vstack([b,b[:1]])[:,[0,2]]
ref=poly(DATA['reference']); zoom=(.50,-.60,.43,.43)
qa=[]
for k,(team,t) in enumerate(DATA['teams'].items(),1):
    f=plt.figure(figsize=(49/25.4,49/25.4));a=f.add_axes([.16,.23,.80,.62])
    counts=[n['support'] for n in t['turns']]
    a.barh([1,0],counts,height=.40,color=COL,alpha=.8,zorder=2)
    a.axvline(5,c='#273640',ls='--',lw=.9,zorder=3)
    a.text(5,1.62,'5 required',ha='center',va='bottom',fontsize=8.5)
    for i,n in enumerate(t['turns']):
        a.text(counts[i]+.22,1-i,str(counts[i]),va='center',weight='bold',fontsize=10,color=COL[i])
        a.text(.15,1-i-.32,'retained' if n['selected'] else 'below threshold',va='center',fontsize=8,color='#273640')
    a.set(xlim=(0,10),ylim=(-.65,1.65),yticks=[1,0],yticklabels=['A','B'],xticks=[0,5,10],xlabel='Supporters (of 10)')
    a.tick_params(length=2,labelsize=8);a.spines[['top','right','left']].set_visible(False)
    save(f,f'team{k}_support')
    q=poly(t['candidate']['points'])
    for detail in [False,True]:
        f=plt.figure(figsize=(55/25.4,49/25.4));a=f.add_axes([.25,.24,.72,.73])
        if detail:
            for person in t['people']:
                p=poly(person['points']);a.plot(*p.T,c='#B1B8BD',lw=.55,zorder=1)
        a.plot(*ref.T,c=GRAY,ls=(0,(3,2)),lw=1.1,zorder=2)
        a.plot(*q.T,c='white',lw=3.0,zorder=3);a.plot(*q.T,c=INK,lw=1.7,zorder=4)
        if detail:
            for i,n in enumerate(t['turns']):
                b,_=reconstruct(n['pair']);x,z=b[0,[0,2]]
                a.scatter(x,z,s=32,marker=MK[i],facecolors=COL[i] if n['selected'] else 'white',edgecolors=COL[i],zorder=5)
                if not n['selected']:a.scatter(x,z,s=18,marker='x',c=COL[i],zorder=6)
                a.annotate(n['label'],(x,z),xytext=(-2,12) if i==0 else (9,-13),textcoords='offset points',color=COL[i],weight='bold',fontsize=9,zorder=7)
            a.set(xlim=(.50,.93),ylim=(-.60,-.17),xticks=[.5,.7,.9],yticks=[-.6,-.4,-.2])
        else:
            a.scatter(*q[:-1].T,s=10,c=INK,zorder=5)
            a.add_patch(Rectangle(zoom[:2],zoom[2],zoom[3],fill=False,edgecolor='#273640',ls=':',lw=1))
            a.set(xlim=(-.75,1.0),ylim=(-1.18,.88),xticks=[-.5,0,.5],yticks=[-1,-.5,0,.5])
        a.set_aspect('equal');a.set_xlabel('$x/h$',fontsize=9,labelpad=1);a.set_ylabel('$z/h$',fontsize=9,labelpad=1)
        a.tick_params(labelsize=8,length=2,pad=2);a.spines[['top','right']].set_visible(False)
        f.canvas.draw()
        # Verify every visible tick/axis label fits inside the panel canvas.
        renderer=f.canvas.get_renderer()
        for text in list(a.get_xticklabels())+list(a.get_yticklabels())+[a.xaxis.label,a.yaxis.label]:
            bb=text.get_window_extent(renderer)
            assert bb.x0>=0 and bb.y0>=0 and bb.x1<=f.bbox.x1 and bb.y1<=f.bbox.y1,(k,detail,text.get_text(),bb)
        save(f,f'team{k}_'+('detail' if detail else 'footprint'))
    qa.append({'team':team,'n':t['n'],'support':counts,'threshold':t['threshold'],'corners':len(q)-1,'footprint_equal_scale':True,'detail_bounds':zoom})
f=plt.figure(figsize=(170/25.4,9/25.4));a=f.add_axes([0,0,1,1]);a.axis('off')
a.legend(handles=[Line2D([],[],c=INK,lw=1.7,label='Consensus'),Line2D([],[],c=GRAY,ls='--',label='Reference'),Line2D([],[],c='#B1B8BD',lw=.7,label='Individual'),Line2D([],[],c='#273640',marker='x',ls='',label='Below threshold')],loc='center',ncol=4,frameon=False,fontsize=9,handlelength=1.7,columnspacing=1.4)
save(f,'legend')
(R/'verification.json').write_text(json.dumps({'checks_from_supplied_geometry':namespace['checks'],'display':qa,'data_changed':False,'new_experiments':False,'subcaptions_in_latex_only':True,'final_width_mm':170},indent=2))
