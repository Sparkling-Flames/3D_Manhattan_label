"""Regenerate figure 6 and 15 artwork; all panel captions are supplied by LaTeX.

Figure 6 uses the exact pre-existing illustrative support matrix and E positions.
Its geometry is an illustrative diagram, not a newly measured annotation.
Figure 15 is a schematic arrangement of complete adjoining rooms, not a
reconstruction of the photographed panorama. The panorama pixels are unchanged.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d import proj3d
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=(HERE.parents[1]/'panels') if HERE.parent.name=='source' else ROOT/'outputs/figure_revision_20261113/figure_package/panels'
BLUE='#0072B2'; ORANGE='#D55E00'; GRAY='#77828B'; DARK='#24343F'; PALE='#CBD2D7'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.2,
                     'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
                     'axes.linewidth':.6,'savefig.facecolor':'white'})
support=np.array([[1,1,1,1,1,1,1],[1,1,1,1,1,1,0],[1,1,1,1,1,1,0],
                  [1,1,1,1,0,1,0],[1,1,1,1,0,0,0],[1,1,1,1,0,0,1]])
assert support.sum(0).tolist()==[6,6,6,6,3,4,2]
cols=[GRAY]*4+[BLUE,ORANGE,GRAY]
E_x=np.array([61.5,65.5,69.3]); E_t=np.array([67.,67.,61.]); E_b=np.array([36.,43.,46.])

def save(fig,number,name):
    target=OUT/f'fig{number:02d}'; target.mkdir(parents=True,exist_ok=True)
    for ext in ['pdf','svg','png']:
        fig.savefig(target/f'{name}.{ext}',dpi=600,facecolor='white')
    plt.close(fig)

def blank(w=2.0,h=2.05):
    fig=plt.figure(figsize=(w,h)); ax=fig.add_axes([.02,.02,.96,.96]);ax.axis('off')
    return fig,ax

def consensus():
    # All six people are visible; a column always denotes the same corner identity.
    fig,ax=blank(2.15,2.12);ax.set(xlim=(-1.3,6.5),ylim=(-.3,6.8))
    for j,x in enumerate(range(7)):
        ax.text(x,6.5,chr(65+j),ha='center',va='center',color=cols[j],weight='bold',fontsize=8.4)
    for person in range(6):
        y=5.82-person*1.05; ax.text(-.83,y,str(person+1),ha='right',va='center',fontsize=8.2)
        xs=np.flatnonzero(support[person]);
        top=y+.23+np.array([.02,.06,.12,.05,-.03,-.05,.03])[xs]
        bot=y-.23+np.array([-.03,.02,.00,-.06,-.10,-.13,-.02])[xs]
        ax.plot(xs,top,color=PALE,lw=.65,zorder=1);ax.plot(xs,bot,color=PALE,lw=.65,zorder=1)
        for x,t,b in zip(xs,top,bot):
            ax.plot([x,x],[t,b],color=cols[x],lw=1.15,zorder=2)
            ax.scatter([x],[t],s=10,c=cols[x],zorder=3)
            ax.scatter([x],[b],s=10,c=cols[x],marker='s',zorder=3)
    save(fig,6,'a_observations')

    fig=plt.figure(figsize=(2.0,2.12));ax=fig.add_axes([.19,.16,.77,.79])
    x=np.arange(7); votes=support.sum(0)
    ax.bar(x,votes,color=cols,width=.62,alpha=.92,edgecolor='none')
    ax.axhline(3,color=DARK,lw=.85,linestyle=(0,(3,2)),zorder=4)
    ax.text(1.9,3.14,'Retain at 3',fontsize=7.1,ha='center',va='bottom',
            bbox={'facecolor':'white','edgecolor':'none','pad':1.0})
    for xx,v in zip(x,votes):ax.text(xx,v+.15,str(v),ha='center',va='bottom',fontsize=8.3,weight='bold')
    ax.set(xticks=x,xticklabels=list('ABCDEFG'),yticks=[0,3,6],ylim=(0,7.1),ylabel='Distinct people')
    for j,t in enumerate(ax.get_xticklabels()): t.set_color(cols[j]);t.set_weight('bold')
    ax.spines[['top','right']].set_visible(False);ax.tick_params(length=2.5,labelsize=7.8)
    # Open cross above minority G is visual rejection, explained in the caption.
    ax.scatter([6],[1.0],marker='x',s=26,c='white',linewidths=1.1,zorder=6)
    save(fig,6,'b_support')

    fig,ax=blank(1.72,2.12); ax.set(xlim=(57.3,73.3),ylim=(24.5,77.5))
    for i,(x,t,b) in enumerate(zip(E_x,E_t,E_b)):
        ax.plot([x,x],[t,b],c=PALE,lw=1.25)
        ax.scatter([x],[t],s=24,c=GRAY,zorder=4)
        ax.scatter([x],[b],s=24,c=GRAY,marker='s',zorder=4)
        ax.text(x,b-3.3,str(i+1),ha='center',va='top',fontsize=7.7,color=GRAY)
    mx,mt,mb=np.median(E_x),np.median(E_t),np.median(E_b)
    ax.plot([mx,mx],[mt,mb],color=BLUE,lw=2.4,zorder=5)
    ax.scatter([mx],[mt],s=46,facecolor=BLUE,edgecolor='white',linewidth=.7,zorder=6)
    ax.scatter([mx],[mb],s=46,facecolor=BLUE,edgecolor='white',linewidth=.7,marker='s',zorder=6)
    ax.annotate('Median',xy=(mx,54),xytext=(70,73),ha='center',fontsize=8,color=BLUE,
                arrowprops={'arrowstyle':'-','color':BLUE,'lw':.75,'connectionstyle':'angle,angleA=90,angleB=0,rad=0'})
    # The endpoint shapes carry meaning; use a compact key, not a subfigure title.
    ax.scatter([58.3],[27.8],s=15,c=DARK);ax.text(59.4,27.8,'Upper',va='center',fontsize=7.3)
    ax.scatter([66.1],[27.8],s=15,c=DARK,marker='s');ax.text(67.2,27.8,'Lower',va='center',fontsize=7.3)
    save(fig,6,'c_location')

    # Retain the original projected closed ring exactly (translation only).
    bottom=np.array([[83,35],[94,35],[97,47],[91,47],[91,57],[83,57]],float)
    top=bottom+np.array([0,22])
    fig,ax=blank(2.1,2.12);ax.set(xlim=(79.5,101),ylim=(28.5,83.5));ax.set_aspect(.42)
    for points in [bottom,top]:
        ring=np.vstack([points,points[0]]);ax.plot(ring[:,0],ring[:,1],c=GRAY,lw=1.15,zorder=1)
    # Distinct fill makes the retained wall turn immediately visible.
    for i in [3,4]:
        j=(i+1)%6;face=np.vstack([bottom[i],bottom[j],top[j],top[i]])
        ax.add_patch(Polygon(face,closed=True,facecolor=BLUE if i==3 else ORANGE,alpha=.12,edgecolor='none'))
    offsets=[(-1.0,-2.9),(1.0,-2.9),(1.4,0),(.0,-3.6),(1.0,2.8),(-1.1,2.8)]
    for i,(b,t) in enumerate(zip(bottom,top)):
        col=cols[i];ax.plot([b[0],t[0]],[b[1],t[1]],color=col,lw=1.35)
        ax.scatter([t[0]],[t[1]],s=20,c=col,zorder=4)
        ax.scatter([b[0]],[b[1]],s=20,c=col,marker='s',zorder=4)
        ax.text(b[0]+offsets[i][0],b[1]+offsets[i][1],chr(65+i),ha='center',va='center',fontsize=8.2,color=col,weight='bold')
    save(fig,6,'d_layout')

def doorway():
    # Native vector isometric cutaway. Near-wall tops are cut to expose the
    # opening while floor boundaries preserve both complete room extents.
    fig=plt.figure(figsize=(4.8,3.20));ax=fig.add_axes([.02,.02,.96,.96]);ax.axis('off');ax.set_aspect('equal')
    W=4.6; y0=-4.1; y1=4.6; H=2.7; dl=1.75; dr=2.85; lintel=2.15
    def p(x,y,z=0):return np.array([.86*x-.58*y,.37*x+.44*y+z])
    def face(verts,color,alpha=1,edge='#89959C',lw=.7,z=1):
        pts=np.array([p(*v) for v in verts]);ax.add_patch(Polygon(pts,closed=True,facecolor=color,edgecolor=edge,lw=lw,alpha=alpha,zorder=z))
    def line(a,b,color=DARK,lw=1,z=10,ls='-'):
        q=np.array([p(*a),p(*b)]);ax.plot(q[:,0],q[:,1],color=color,lw=lw,zorder=z,ls=ls)
    # Full back and left walls and both complete floors.
    face([(0,y0,0),(0,y1,0),(0,y1,H),(0,y0,H)],'#ECEFF1',z=1)
    face([(0,y1,0),(W,y1,0),(W,y1,H),(0,y1,H)],'#DFE4E8',z=2)
    face([(0,y0,0),(W,y0,0),(W,0,0),(0,0,0)],'#E4EFF5',z=3)
    face([(0,0,0),(W,0,0),(W,y1,0),(0,y1,0)],'#F6E9DD',z=3)
    # The shared partition carries the full-height opening.
    face([(0,0,0),(dl,0,0),(dl,0,H),(0,0,H)],'#D3DBE0',z=4)
    face([(dr,0,0),(W,0,0),(W,0,H),(dr,0,H)],'#C4CFD6',z=5)
    face([(dl,0,lintel),(dr,0,lintel),(dr,0,H),(dl,0,H)],'#AFBDC7',edge=DARK,lw=.8,z=6)
    # Low cutaway front walls still trace every exterior floor edge.
    cut=.32
    face([(W,y0,0),(W,y1,0),(W,y1,cut),(W,y0,cut)],'#E4E9ED',z=7)
    face([(0,y0,0),(W,y0,0),(W,y0,cut),(0,y0,cut)],'#D9E1E6',z=7)
    # Remote end pillar makes the enclosure height explicit in the cutaway.
    line((W,y1,cut),(W,y1,H),color='#89959C',lw=.7,z=7)
    for xx in [dl,dr]:line((xx,0,0),(xx,0,lintel),lw=1.8,z=8)
    line((dl,0,lintel),(dr,0,lintel),lw=1.8,z=8)
    cam=((dl+dr)/2,0,1.32);cc=p(*cam);foot=p(cam[0],0,0)
    ax.plot([foot[0],cc[0]],[foot[1],cc[1]],color=BLUE,lw=.65,ls=(0,(2,2)),zorder=9)
    ax.scatter([foot[0]],[foot[1]],s=10,c=BLUE,zorder=9)
    ax.scatter([cc[0]],[cc[1]],s=55,c=BLUE,edgecolor='white',linewidth=.65,zorder=10)
    # Object labels occupy floor regions, with callouts entirely outside geometry.
    for txt,xyz,col in [('Space 1',(2.0,-2.2,.05),BLUE),('Space 2',(2.0,2.45,.05),ORANGE)]:
        q=p(*xyz);ax.text(*q,txt,ha='center',va='center',color=col,fontsize=9.2,zorder=12)
    camlabel=np.array([7.0,1.45]); lintlabel=np.array([5.6,5.2]); lintpoint=p((dl+dr)/2,0,lintel+.14)
    for txt,q,where,col in [('Camera beneath\nthe lintel',cc,camlabel,BLUE),('Lintel',lintpoint,lintlabel,DARK)]:
        ax.annotate(txt,xy=q,xytext=where,fontsize=8.7,ha='left',va='center',color=col,zorder=20,
                    arrowprops={'arrowstyle':'-','lw':.85,'color':col,'connectionstyle':'angle,angleA=0,angleB=80,rad=0'},
                    bbox={'facecolor':'white','edgecolor':'none','pad':1.8})
    ax.set(xlim=(-3.0,10.4),ylim=(-2.1,6.9));fig.patch.set_facecolor('white')
    save(fig,15,'a_doorway_schematic')
    # Optional preserved-model edition: the extracted 918x765 image is embedded
    # unchanged, with all rooms visible and a new vector callout outside it.
    # Camera target is the original PDF arrow tip transformed to native pixels.
    im_model=Image.open(HERE/'source_model.png')
    fig=plt.figure(figsize=(4.5,3.6));ax=fig.add_axes([.02,.02,.96,.96]);ax.axis('off')
    ax.imshow(im_model,interpolation='none',extent=(0,918,765,0))
    cam_px=((83.80762481689453+12.060020446777344)/.24,
            (115.1129150390625-14.139739990234375)/.24)
    ax.scatter([cam_px[0]],[cam_px[1]],s=22,c=BLUE,edgecolor='white',linewidth=.5,zorder=5)
    ax.annotate('Camera beneath\nthe doorframe',xy=cam_px,xytext=(-175,390),
                ha='left',va='center',fontsize=8.7,color=BLUE,zorder=6,
                arrowprops={'arrowstyle':'-','color':BLUE,'lw':.85,'connectionstyle':'angle,angleA=0,angleB=70,rad=0'})
    ax.set(xlim=(-210,930),ylim=(775,-10));ax.set_aspect('equal');fig.patch.set_facecolor('white')
    save(fig,15,'original_model_clean')
    # Preserve the exact source panorama pixels. The PDF embeds its native raster.
    im=Image.open(HERE/'source_panorama.png')
    fig=plt.figure(figsize=(4.8,2.4));ax=fig.add_axes([0,0,1,1]);ax.imshow(im,interpolation='none');ax.axis('off')
    save(fig,15,'b_panorama')
    (OUT/'fig15'/'source_panorama.png').write_bytes((HERE/'source_panorama.png').read_bytes())

if __name__=='__main__':
    consensus();doorway()
    record={
      'fig06':{'support':support.tolist(),'votes':support.sum(0).tolist(),'threshold':3,
       'retained':list('ABCDEF'),'excluded':['G'],'E_observations':{'x':E_x.tolist(),'upper':E_t.tolist(),'lower':E_b.tolist()},
       'E_median':[float(np.median(E_x)),float(np.median(E_t)),float(np.median(E_b))],
       'source':'editorial_tools/recompose_rev11_figures.py, consensus_process()',
       'status':'Existing illustrative support and projected ring; no empirical result changed'},
      'fig15':{'source_pdf':'doorway_boundary_3d_trimmed.pdf','source_panorama_size':list(Image.open(HERE/'source_panorama.png').size),
       'panorama_sha256':hashlib.sha256((HERE/'source_panorama.png').read_bytes()).hexdigest(),
       'schematic':'Complete adjoining rectangular enclosures with doorway; camera below lintel; native vector on white',
       'status':'Schematic arrangement, not reconstruction of the panorama',
       'original_model_option': {'file': 'original_model_clean.pdf', 'native_pixel_size': [918, 765], 'embedded_pixels_identical_after_pdf_row_order': True, 'original_model_sha256': 'ae2430209aa6b7b4cec7c15463ee8728f6e1fc39448753aa2274cf5783277afb', 'camera_pixel': [399.4485219319662, 420.7215627034505], 'pixel_source': 'Original PDF image transform and original callout arrow tip'}},
      'captions_embedded':False,'output_dpi':600}
    (HERE/'provenance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
