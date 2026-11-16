"""Three code-drawn concepts for explaining Q. Synthetic, not participant data.

The copied controlled_q_engine is an independent numerical implementation of the
manuscript equations, not a complete execution of the repository's empirical scorer.
All numeric values below are computed, never hand assigned.
"""
from pathlib import Path
import json, math, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPolygon, Rectangle
from matplotlib.lines import Line2D
from shapely.geometry import Polygon
import controlled_q_engine as E

ROOT=Path(__file__).resolve().parent
BLUE='#0072B2'; ORANGE='#D55E00'; GRAY='#757575'; LIGHT='#E3E7EA'; INK='#202A30'; MUTED='#52646D'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':INK,
 'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,'axes.edgecolor':'#A6B0B7',
 'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','mathtext.fontset':'dejavusans',
 'axes.unicode_minus':False,'savefig.facecolor':'white'})
REF=E.flat(E.square()); K=2
RADIUS=float(np.linalg.norm(REF.xz[K])); UPPER=256-512/math.pi*math.atan2(3-E.CAMERA_HEIGHT,RADIUS)
LOWER=256+512/math.pi*math.atan2(E.CAMERA_HEIGHT,RADIUS)

def closed(a):return np.vstack([a,a[0]])
def score(p):return E.score(p,REF,nb=2048,nh=4096)
def endpoint_edit(kind,delta):
    x=REF.xz.copy();h=REF.heights.copy()
    if kind=='lower':
        r=E.CAMERA_HEIGHT/math.tan(math.pi*((LOWER-delta)/512-.5))
        x[K]=REF.xz[K]*r/RADIUS
        h[K]=E.CAMERA_HEIGHT-r*math.tan(math.pi*(UPPER/512-.5))
    elif kind=='upper':
        h[K]=E.CAMERA_HEIGHT-RADIUS*math.tan(math.pi*((UPPER-delta)/512-.5))
    return E.Layout(x,h)

EXAMPLE_DISPLACEMENT_M = 0.5

def formal_examples():
    """Image edits giving a radial floor shift or a vertical height rise in metres."""
    lower_v = 256 + 512/math.pi*math.atan2(E.CAMERA_HEIGHT, RADIUS+EXAMPLE_DISPLACEMENT_M)
    upper_v = 256 - 512/math.pi*math.atan2(3+EXAMPLE_DISPLACEMENT_M-E.CAMERA_HEIGHT, RADIUS)
    for kind, delta in [('lower', LOWER-lower_v), ('upper', UPPER-upper_v)]:
        yield kind, delta, endpoint_edit(kind, delta)


def add_points(layout,n):
    q,h=[],[]
    # Add collinear paired points to the x=2 (high) wall only.
    for i in range(4):
        q.append(layout.xz[i]);h.append(layout.heights[i])
        if i==1:
            for t in np.linspace(0,1,n-4+2)[1:-1]:
                q.append((1-t)*layout.xz[i]+t*layout.xz[(i+1)%4])
                h.append((1-t)*layout.heights[i]+t*layout.heights[(i+1)%4])
    return E.Layout(np.array(q),np.array(h))

def fig_base(tag,title,subtitle):
    fig=plt.figure(figsize=(12,7.2))
    fig.text(.035,.96,tag,fontsize=17,fontweight='bold',color=BLUE,va='top')
    fig.text(.12,.96,title,fontsize=17,fontweight='bold',va='top')
    fig.text(.035,.906,subtitle,fontsize=10.7,color=MUTED,va='top')
    return fig

def export(fig,name):
    for ext in ['pdf','svg','png']:
        fig.savefig(ROOT/f'{name}.{ext}',dpi=240)
    plt.close(fig)

def project(P):
    x,z=P.xz.T
    b=np.column_stack([.76*x+.50*z,-.23*x+.39*z])
    t=b+np.column_stack([np.zeros(len(x)),.85*P.heights])
    return b,t

def draw_plan(ax,P,arrow=False,label=None,reference=True):
    pr=Polygon(REF.xz);pp=Polygon(P.xz)
    if reference:
        ax.add_patch(MPolygon(REF.xz,closed=True,facecolor='#F6F7F8',edgecolor='none'))
        diff=pr.symmetric_difference(pp)
        geoms=list(diff.geoms) if hasattr(diff,'geoms') else [diff]
        for g in geoms:
            if g.is_empty:continue
            ax.add_patch(MPolygon(np.array(g.exterior.coords),facecolor='#F7DFD2',edgecolor=ORANGE,linewidth=.4,hatch='///',zorder=2))
        ax.plot(*closed(REF.xz).T,color=GRAY,lw=1.2,ls=(0,(4,3)),zorder=4)
    ax.plot(*closed(P.xz).T,color=BLUE,lw=1.8,zorder=5)
    ax.scatter(*P.xz.T,color=BLUE,s=16,zorder=6)
    ax.scatter([0],[0],marker='+',s=44,c=INK,lw=1.2,zorder=6)
    if arrow and np.linalg.norm(P.xz[K]-REF.xz[K])>1e-6:
        for a,b in [(1,2),(2,3)]:ax.plot(*P.xz[[a,b]].T,color=ORANGE,lw=2,zorder=6)
        ax.annotate('',xy=P.xz[K],xytext=REF.xz[K],arrowprops=dict(arrowstyle='->',color=ORANGE,lw=1.6),zorder=7)
        ax.scatter([P.xz[K,0]],[P.xz[K,1]],s=25,color=ORANGE,zorder=8)
    ax.set_xlim(-2.5,3.55);ax.set_ylim(-2.65,3.55);ax.set_aspect('equal');ax.axis('off')
    if label:ax.text(.5,-.01,label,transform=ax.transAxes,ha='center',va='top',fontsize=10.5,color=MUTED)

def draw_room(ax,P,reference=True,highlight=False,point_size=10,limits=None):
    rb,rt=project(REF);pb,pt=project(P)
    ax.add_patch(MPolygon(pb,closed=True,facecolor='#F1F5F7',edgecolor='none',zorder=1))
    # Two adjacent walls carry the edited endpoint or corner. No roof surface is
    # invented for a non-planar upper ring: display wall faces and upper edges only.
    for a,b in [(1,2),(2,3)]:
        color=ORANGE if highlight else BLUE
        ax.add_patch(MPolygon(np.array([pb[a],pb[b],pt[b],pt[a]]),closed=True,facecolor=color,edgecolor='none',alpha=.10,zorder=2))
    if reference:
        ax.plot(*closed(rb).T,color=GRAY,lw=1.2,ls=(0,(4,3)),zorder=3)
        ax.plot(*closed(rt).T,color=GRAY,lw=1.2,ls=(0,(4,3)),zorder=3)
        for b,t in zip(rb,rt):ax.plot([b[0],t[0]],[b[1],t[1]],color=GRAY,lw=1,ls=(0,(4,3)),zorder=3)
    ax.plot(*closed(pb).T,color=BLUE,lw=1.5,zorder=4)
    ax.plot(*closed(pt).T,color=BLUE,lw=1.5,zorder=4)
    for b,t in zip(pb,pt):ax.plot([b[0],t[0]],[b[1],t[1]],color=BLUE,lw=1.1,zorder=4)
    ax.scatter(*pt.T,color=BLUE,s=point_size,zorder=5)
    if highlight:
        for a,b in [(1,2),(2,3)]:ax.plot(*pt[[a,b]].T,color=ORANGE,lw=2,zorder=5)
        ax.scatter([pt[K,0]],[pt[K,1]],color=ORANGE,s=30,zorder=6)
    ax.set_xlim(-3.1,4.1);ax.set_ylim(-1.7,5.05);ax.set_aspect('equal');ax.axis('off')
    if limits:ax.set_xlim(*limits[0]);ax.set_ylim(*limits[1])
    return pb,pt

def draw_edit(ax,kind,delta,show_pixels=True):
    fixed=UPPER if kind=='lower' else LOWER
    moving=LOWER if kind=='lower' else UPPER
    after=moving-delta
    ax.plot([0,0],[UPPER,LOWER],color=GRAY,lw=1.3,ls=(0,(4,3)))
    ax.plot([0,0],[min(fixed,after),max(fixed,after)],color=BLUE,lw=1.5)
    ax.axhline(256,color='#B7C1C7',lw=.9,ls=(0,(2,3)))
    ax.text(-.88,256,'horizon',fontsize=9,ha='left',va='bottom',color=GRAY)
    ax.scatter([0],[moving],s=48,facecolor='white',edgecolor=GRAY,linewidth=1.3,zorder=5)
    ax.scatter([0],[after],s=40,color=ORANGE,zorder=6)
    ax.scatter([0],[fixed],s=40,color=BLUE,zorder=6)
    ax.annotate('',xy=(.26,after),xytext=(.26,moving),arrowprops=dict(arrowstyle='->',color=ORANGE,lw=1.4))
    ax.text(.37,(moving+after)/2,f'{delta:.1f} px' if show_pixels else 'up',va='center',ha='left',color=ORANGE,fontsize=11)
    if kind=='lower':
        ax.text(-.1,UPPER,'upper image\npoint fixed',ha='right',va='center',fontsize=9.5)
        ax.text(-.1,after,'lower image\npoint moved',ha='right',va='center',fontsize=9.5,color=ORANGE)
    else:
        ax.text(-.1,LOWER,'lower image\npoint fixed',ha='right',va='center',fontsize=9.5)
        ax.text(-.1,after,'upper image\npoint moved',ha='right',va='center',fontsize=9.5,color=ORANGE)
    ax.text(.5,1.01,'Aligned endpoint pair',transform=ax.transAxes,ha='center',va='bottom',fontsize=9.5,color=MUTED)
    ax.set_xlim(-.95,.95);ax.set_ylim(373,134);ax.axis('off')

def measurements(ax,m):
    ax.axis('off')
    rows=[('Floor IoU',100,m['iou2d100'],'%'),('Boundary distance',0,m['Sb_deg'],'°'),('Orthogonality error',0,m['Ddir_deg'],'°'),('Mean-height error',0,100*m['Hmean'],'%'),('Local-height error',0,100*m['Hcenter'],'%')]
    for i,(label,base,value,unit) in enumerate(rows):
        y=.96-i*.135;changed=abs(base-value)>1e-7
        if changed:ax.add_patch(Rectangle((-.02,y-.065),1.04,.115,transform=ax.transAxes,facecolor='#FCF0E9',edgecolor='none',clip_on=False))
        ax.text(0,y,label,fontsize=10.5,va='center')
        ax.text(1,y,f'{base:.0f} → {value:.2f}{unit}',ha='right',va='center',fontsize=10.5,color=ORANGE if changed else GRAY,fontweight='bold' if changed else 'normal')
    ax.text(0,.14,'Q',fontsize=15,fontweight='bold',color=BLUE,va='center')
    ax.text(1,.14,f'100 → {m["Q"]:.2f}',ha='right',fontsize=17,fontweight='bold',color=BLUE,va='center')

def build_a():
    fig=fig_base('Q-A','Follow one edited endpoint','Same reference room and corner; the paired endpoint stays at its original image pixel.')
    fig.legend(handles=[Line2D([],[],color=GRAY,lw=1.3,ls=(0,(4,3)),label='Reference'),Line2D([],[],color=BLUE,lw=1.5,label='Edited layout'),Line2D([],[],color=ORANGE,lw=1.5,marker='o',ms=4,label='Edit / affected geometry')],loc='lower center',bbox_to_anchor=(.5,.012),ncol=3,frameon=False,fontsize=10)
    for row,(kind,delta,p) in enumerate(formal_examples()):
        bottom=.51 if row==0 else .115
        m=score(p)
        title='a  Move only the lower image endpoint' if kind=='lower' else 'b  Move only the upper image endpoint'
        fig.text(.035,bottom+.315,title,fontsize=12,fontweight='bold')
        ax=fig.add_axes([.045,bottom,.13,.285]);draw_edit(ax,kind,delta,show_pixels=False)
        ax=fig.add_axes([.18,bottom,.19,.285]);draw_plan(ax,p,arrow=kind=='lower',label=f'Corner shift: {EXAMPLE_DISPLACEMENT_M:.2f} m' if kind=='lower' else 'Identical footprint')
        ax=fig.add_axes([.37,bottom-.015,.28,.32]);pb,pt=draw_room(ax,p,highlight=True)
        ax.annotate(f'h = {p.heights[K]:.2f} m',xy=pt[K],xytext=(2.45,4.55),ha='center',va='center',color=ORANGE,fontsize=10.5,arrowprops=dict(arrowstyle='-',color=ORANGE,lw=1.1,shrinkA=5,shrinkB=3))
        ax.text(.46,-.015,'Two adjacent walls change',transform=ax.transAxes,ha='center',va='bottom',fontsize=10.5,color=MUTED)
        ax=fig.add_axes([.695,bottom-.005,.265,.305]);measurements(ax,m)
    fig.add_artist(Line2D([.035,.965],[.475,.475],transform=fig.transFigure,color='#D4DCE1',lw=1))
    export(fig,'Q_A')

def matrix_cases():
    x=REF.xz.copy();x[K,0]+=.8
    single=E.Layout(x,3)
    uniform=E.Layout(E.square(),3.6)
    tilt=E.Layout(E.square(),3+.6*E.square()[:,0]/2)
    dense=add_points(tilt,16)
    return [('One corner shifted 0.8 m','Height held at 3.00 m',single),('All upper corners raised','Uniform height: 3.60 m',uniform),('Opposing upper shifts','2.40 / 3.60 m; mean 3.00 m',tilt),('Add collinear pairs','Same geometry: 4 → 16 pairs',dense)]

def build_b():
    fig=fig_base('Q-B','Read the response of each measurement','One scene, four controlled operations. Orange cells differ from the unchanged reference.')
    xs=[.425,.525,.625,.725,.825,.935]
    headers=[('Floor IoU','%'),('Boundary','degrees'),('Orthogonality','degrees'),('Mean height','error %'),('Local height','error %'),('Q','0–100')]
    for x,(a,b) in zip(xs,headers):
        fig.text(x,.825,a,ha='center',fontsize=10.5,fontweight='bold')
        fig.text(x,.795,b,ha='center',fontsize=9.5,color=MUTED)
    cases=matrix_cases()
    for i,(title,desc,p) in enumerate(cases):
        y=.69-i*.165;m=score(p)
        fig.text(.035,y+.055,title,fontsize=11.7,fontweight='bold',ha='left')
        fig.text(.035,y+.021,desc,fontsize=9.7,color=MUTED,ha='left')
        ax=fig.add_axes([.235,y-.062,.145,.145])
        if i==0:draw_plan(ax,p,arrow=True)
        else:
            draw_room(ax,p,highlight=False,point_size=6,limits=((-3.1,3.1),(-1.55,4.5)))
        values=[m['iou2d100'],m['Sb_deg'],m['Ddir_deg'],100*m['Hmean'],100*m['Hcenter'],m['Q']]
        for j,(x,v) in enumerate(zip(xs,values)):
            changed=abs(v-([100,0,0,0,0,100][j]))>1e-7
            color=BLUE if j==5 else ORANGE if changed else GRAY
            if changed:
                fig.add_artist(Rectangle((x-.044,y-.042),.088,.082,transform=fig.transFigure,facecolor='#EFF6FA' if j==5 else '#FCF0E9',edgecolor='none',zorder=0))
            fig.text(x,y,f'{v:.2f}',ha='center',va='center',fontsize=15 if j==5 else 13.5,color=color,fontweight='bold' if j==5 else 'normal')
        fig.add_artist(Line2D([.035,.975],[y-.08,y-.08],transform=fig.transFigure,color='#DFE5E8',lw=.9))
    fig.text(.035,.065,'Bottom two rows have identical walls and heights: point density changes, Q does not.',fontsize=11,color=BLUE)
    fig.text(.035,.026,'Measurements retain their native units; the columns are not additive shares of the Q decrease.',fontsize=9.5,color=MUTED)
    export(fig,'Q_B')

def build_c(curves,resampling):
    fig=fig_base('Q-C','Perturb geometry; test invariance','A two-figure story: continuous endpoint perturbation, followed by unchanged-geometry resampling.')
    fig.text(.04,.824,'a  Increase one endpoint displacement',fontsize=12,fontweight='bold')
    fig.text(.665,.824,'b  Add points without changing walls',fontsize=12,fontweight='bold')
    chart_left=.08;chart_width=.47
    for delta,x in [(0,chart_left),(12,chart_left+chart_width/2),(24,chart_left+chart_width)]:
        ax=fig.add_axes([x-.071,.575,.142,.205]);draw_room(ax,endpoint_edit('lower',delta),highlight=delta>0,point_size=6)
        ax.text(.5,.0,f'{delta} px',ha='center',va='top',transform=ax.transAxes,fontsize=10,color=BLUE)
    # Geometry snapshots intentionally retain only their displacement labels.
    ax=fig.add_axes([chart_left,.16,chart_width,.33])
    for kind,color,label in [('lower',BLUE,'Lower endpoint moved'),('upper',ORANGE,'Upper endpoint moved')]:
        points=curves[kind]
        ax.plot([x['pixel_shift'] for x in points],[x['Q'] for x in points],lw=1.8,color=color,label=label)
        for d in [0,12,24]:
            val=next(x['Q'] for x in points if x['pixel_shift']==d)
            ax.scatter([d],[val],s=24,facecolor='white',edgecolor=color,lw=1.3,zorder=5)
        val=points[-1]['Q'];ax.text(23.6,val+(2.7 if kind=='lower' else -5),f'{val:.2f}',color=color,ha='right',fontsize=10.5,fontweight='bold')
    ax.set_xlim(-.5,24.5);ax.set_ylim(45,103);ax.set_xlabel('Vertical image displacement (px)',fontsize=11);ax.set_ylabel('Q',fontsize=12)
    ax.set_xticks([0,6,12,18,24]);ax.set_yticks([50,60,70,80,90,100]);ax.tick_params(labelsize=9.5)
    ax.grid(axis='y',color='#E8ECEF',lw=.6);ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='lower left',frameon=False,fontsize=9.5)
    for d in [12,24]:ax.axvline(d,color='#C2CDD3',ls=(0,(2,3)),lw=.8,zorder=0)
    tilt=matrix_cases()[2][2]
    for n,x in [(4,.66),(16,.825)]:
        a=fig.add_axes([x,.555,.15,.23]);draw_room(a,add_points(tilt,n),reference=False,point_size=8,limits=((-3.1,3.1),(-1.55,4.5)))
        a.text(.5,-.01,f'{n} pairs',transform=a.transAxes,ha='center',fontsize=10.5)
    ax2=fig.add_axes([.695,.16,.265,.33])
    ns=[x['node_count'] for x in resampling];qs=[x['Q'] for x in resampling]
    ax2.plot(ns,qs,'o-',color=BLUE,lw=1.8,ms=4)
    ax2.set_xlim(2,34);ax2.set_ylim(45,103);ax2.set_yticks([50,60,70,80,90,100]);ax2.set_xticks([4,8,16,32]);ax2.set_xlabel('Collinear paired corners',fontsize=10.5);ax2.set_ylabel('Q',fontsize=12)
    ax2.tick_params(labelsize=9.5);ax2.grid(axis='y',color='#E8ECEF',lw=.6);ax2.spines[['top','right']].set_visible(False)
    ax2.text(18,74.0,f'Q = {qs[0]:.2f}',ha='center',fontsize=13,color=BLUE,fontweight='bold')
    ax2.text(18,87.0,'Same distorted geometry',ha='center',fontsize=10,color=MUTED)
    fig.add_artist(Line2D([.63,.63],[.13,.83],transform=fig.transFigure,color='#CCD6DC',lw=1))
    fig.text(.04,.055,'Fixed partner endpoint and reference throughout (a). High-wall subdivisions preserve the geometry in (b).',fontsize=9.7,color=MUTED)
    export(fig,'Q_C')

def main():
    data={'scope':'Controlled synthetic geometry for method illustration, not participant observations.',
      'engine':'Unmodified independent numerical implementation of current manuscript equations; not a full empirical scorer run.',
      'engine_sha256':hashlib.sha256((ROOT/'controlled_q_engine.py').read_bytes()).hexdigest(),
      'reference':REF.data(),'camera_height_m':E.CAMERA_HEIGHT,'panorama_size':[1024,512],
      'edited_corner_index_zero_based':K,'original_upper_v_px':UPPER,'original_lower_v_px':LOWER,
      'boundary_samples_each_direction':2048,'height_samples_each_direction':4096,'A':[],'B':[],'C':{},'verification':{}}
    for kind,delta,p in formal_examples():
        m=score(p)
        data['A'].append({'kind':kind,'pixel_shift':delta,'geometry':p.data(),'floor_corner_displacement_m':float(np.linalg.norm(p.xz[K]-REF.xz[K])),**m})
    for title,desc,p in matrix_cases():data['B'].append({'operation':title,'description':desc,'geometry':p.data(),**score(p)})
    curves={}
    for kind in ['lower','upper']:
        curves[kind]=[{'pixel_shift':float(d),**score(endpoint_edit(kind,float(d)))} for d in np.linspace(0,24,49)]
    tilt=matrix_cases()[2][2]
    resampling=[{'node_count':n,**score(add_points(tilt,n))} for n in [4,8,16,32]]
    data['C']={'curves':curves,'resampling':resampling}
    data['verification']['reference_self_Q']=score(REF)['Q']
    data['verification']['resampling_Q_range']=float(np.ptp([x['Q'] for x in resampling]))
    data['verification']['upper_edit_floor_metrics_unchanged']=all(abs(data['A'][1][k]-v)<1e-9 for k,v in [('iou2d100',100),('Sb_deg',0),('Ddir_deg',0)])
    conv=[]
    for kind,delta,p in formal_examples():
        hi=E.score(p,REF,8192,16384);lo=score(p)
        conv.append({'kind':kind,'abs_Q_difference':abs(hi['Q']-lo['Q']),'abs_Sb_difference':abs(hi['Sb_deg']-lo['Sb_deg']),'abs_Hc_difference':abs(hi['Hcenter']-lo['Hcenter'])})
    data['verification']['fourfold_sampling']=conv
    assert data['verification']['resampling_Q_range']<1e-5
    assert data['verification']['upper_edit_floor_metrics_unchanged']
    assert max(r['abs_Q_difference'] for r in conv)<.01
    (ROOT/'computed_examples.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    build_a();build_b();build_c(curves,resampling)
    print(json.dumps({'A':[{k:r[k] for k in ['kind','pixel_shift','floor_corner_displacement_m','Q']} for r in data['A']], 'verification':data['verification']},indent=2))

if __name__=='__main__':main()
