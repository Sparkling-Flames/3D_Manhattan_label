"""Physical-displacement Q examples, with native LaTeX subcaptions."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import build_quality as Q

OUT=Path(__file__).resolve().parents[2]/'panels/quality_endpoint'
OUT.mkdir(parents=True,exist_ok=True)
record_path=Q.ROOT/'computed_examples.json'
data=json.loads(record_path.read_text(encoding='utf-8'))
cases=[]
convergence=[]
assert np.isclose(Q.score(Q.REF)['Q'],100)
for kind,delta,p in Q.formal_examples():
    m=Q.score(p)
    floor_shift=float(np.linalg.norm(p.xz[Q.K]-Q.REF.xz[Q.K]))
    if kind=='lower':
        assert np.isclose(floor_shift,Q.EXAMPLE_DISPLACEMENT_M)
        fixed_upper=256-512/math.pi*math.atan2(p.heights[Q.K]-Q.E.CAMERA_HEIGHT,np.linalg.norm(p.xz[Q.K]))
        assert np.isclose(fixed_upper,Q.UPPER)
    else:
        assert np.allclose(p.xz,Q.REF.xz)
        assert np.isclose(p.heights[Q.K]-Q.REF.heights[Q.K],Q.EXAMPLE_DISPLACEMENT_M)
        assert all(np.isclose(m[k],v) for k,v in [('iou2d100',100),('Sb_deg',0),('Ddir_deg',0)])
    high=Q.E.score(p,Q.REF,8192,16384)
    check={'kind':kind,'abs_Q_difference':abs(high['Q']-m['Q']),
           'abs_Sb_difference':abs(high['Sb_deg']-m['Sb_deg']),
           'abs_Hc_difference':abs(high['Hcenter']-m['Hcenter'])}
    assert check['abs_Q_difference']<.01
    convergence.append(check)
    cases.append({'kind':kind,'pixel_shift':delta,'geometry':p.data(),
                  'floor_corner_displacement_m':floor_shift,**m})
    fig=plt.figure(figsize=(10,2.65))
    ax=fig.add_axes([.025,.10,.145,.83]);Q.draw_edit(ax,kind,delta,show_pixels=False)
    ax=fig.add_axes([.18,.10,.19,.83]);Q.draw_plan(ax,p,arrow=kind=='lower',
        label=f'Corner shift: {floor_shift:.2f} m' if kind=='lower' else 'Unchanged footprint')
    ax=fig.add_axes([.365,.04,.27,.92]);_,pt=Q.draw_room(ax,p,highlight=True)
    ax.annotate(f"h: 3.00 → {p.heights[Q.K]:.2f} m",xy=pt[Q.K],xytext=(1.2,4.7),ha='center',color=Q.ORANGE,fontsize=10.5,arrowprops={'arrowstyle':'-','color':Q.ORANGE,'lw':.8})
    ax=fig.add_axes([.66,.08,.32,.88]);Q.measurements(ax,m)
    for ext in ['pdf','svg','png']:fig.savefig(OUT/(kind+'.'+ext),dpi=300)
    plt.close(fig)
data['A']=cases
data['verification']['fourfold_sampling']=convergence
data['verification']['upper_edit_floor_metrics_unchanged']=True
record_path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
fig=plt.figure(figsize=(10,.28))
fig.legend(handles=[Line2D([],[],color=Q.GRAY,ls='--',label='Reference'),Line2D([],[],color=Q.BLUE,label='Edited layout'),Line2D([],[],color=Q.ORANGE,marker='o',label='Moved endpoint / affected geometry')],loc='center',ncol=3,frameon=False,fontsize=10)
for ext in ['pdf','svg','png']:fig.savefig(OUT/('legend.'+ext),dpi=300)
plt.close(fig)
print(json.dumps([{'kind':c['kind'],'pixel_shift':c['pixel_shift'],'Q':c['Q'],
                   'floor_shift_m':c['floor_corner_displacement_m'],
                   'wall_height_m':c['geometry']['wall_heights_m'][Q.K]} for c in cases],indent=2))
print('Physical edit, fixed partner, unchanged upper-case footprint and numerical convergence checks passed.')
