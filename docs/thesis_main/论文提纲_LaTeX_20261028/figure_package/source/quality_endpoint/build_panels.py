"""Q-A content as two title-free panels for native LaTeX subcaptions."""
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import build_quality as Q
OUT=Path(__file__).resolve().parents[2]/'panels/quality_endpoint'
OUT.mkdir(parents=True,exist_ok=True)
expected=json.loads((Q.ROOT/'computed_examples.json').read_text(encoding='utf-8'))
for kind in ['lower','upper']:
    p=Q.endpoint_edit(kind,24);m=Q.score(p)
    previous=next(x for x in expected['A'] if x['kind']==kind)
    for key in ['Q','iou2d100','Sb_deg','Ddir_deg','Hmean','Hcenter']:
        assert np.isclose(m[key],previous[key],atol=1e-9),key
    fig=plt.figure(figsize=(10,2.65))
    ax=fig.add_axes([.025,.10,.145,.83]);Q.draw_edit(ax,kind,24)
    ax=fig.add_axes([.18,.10,.19,.83]);Q.draw_plan(ax,p,arrow=kind=='lower')
    ax=fig.add_axes([.365,.04,.27,.92]);_,pt=Q.draw_room(ax,p,highlight=True)
    ax.annotate(f"h = {p.heights[Q.K]:.2f} m",xy=pt[Q.K],xytext=(2.1,4.7),ha='center',color=Q.ORANGE,fontsize=10.5,arrowprops={'arrowstyle':'-','color':Q.ORANGE,'lw':.8})
    ax=fig.add_axes([.66,.08,.32,.88]);Q.measurements(ax,m)
    for ext in ['pdf','svg','png']:fig.savefig(OUT/(kind+'.'+ext),dpi=300)
    plt.close(fig)
fig=plt.figure(figsize=(10,.28))
fig.legend(handles=[Line2D([],[],color=Q.GRAY,ls='--',label='Reference'),Line2D([],[],color=Q.BLUE,label='Edited layout'),Line2D([],[],color=Q.ORANGE,marker='o',label='Moved endpoint / affected geometry')],loc='center',ncol=3,frameon=False,fontsize=10)
for ext in ['pdf','svg','png']:fig.savefig(OUT/('legend.'+ext),dpi=300)
plt.close(fig)
print('Q-A values preserved; title-free panels written.')

