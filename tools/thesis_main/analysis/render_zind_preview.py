"""Preview roofless room renderings; never overwrite manuscript figures."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PolygonPath
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.ndimage import map_coordinates
from PIL import Image
from render_manuscript_3d import geometry, ROOT

OUT = ROOT / 'docs/thesis_main/论文写作工作资料/previews'
PHOTO = ROOT / 'data/mp3d_layout/test/img/7y3sRwLe3Va_606f9842b8af48daa28f10df8b69d861.png'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42})
photo = np.asarray(Image.open(PHOTO).convert('RGB')) / 255.


def texture(xyz):
    u = (np.arctan2(xyz[...,0], -xyz[...,1]) / (2*np.pi) + .5) * photo.shape[1]
    v = (.5 - np.arctan2(xyz[...,2], np.hypot(xyz[...,0],xyz[...,1])) / np.pi) * photo.shape[0]
    coords = np.array([np.clip(v,0,photo.shape[0]-1), u % photo.shape[1]])
    return np.stack([map_coordinates(photo[...,c],coords,order=1,mode='nearest') for c in range(3)],axis=-1)


def draw(ax, g, textured, color, bounds):
    floor, top = g
    n = len(floor)
    # Remove the two outer walls facing the viewer; retain their floor outlines.
    # Remaining walls (including every fireplace return) use the original vertices.
    mid = (floor + np.roll(floor,-1,axis=0))/2
    omitted = {int(np.argmin(mid[:,0])), int(np.argmin(mid[:,1]))}
    assert len(omitted)==2
    if not textured:
        faces=[floor];colors=['#e8edef']
        for i in range(n):
            if i in omitted: continue
            j=(i+1)%n
            faces.append(np.array([floor[i],floor[j],top[j],top[i]]))
            edge=floor[j]-floor[i]
            normal=np.array([-edge[1],edge[0],0.]);normal/=np.linalg.norm(normal)
            light=np.array([-.5,-.4,.75]);light/=np.linalg.norm(light)
            tone=.84+.14*np.dot(normal,light)
            colors.append(np.clip(np.array([.80,.89,.91])*tone,0,1))
        ax.add_collection3d(Poly3DCollection(faces,facecolors=colors,edgecolors='#587984',linewidth=.65,zsort='average'))
        setup_view(ax,bounds)
        return
    if textured:
        xx,yy = np.meshgrid(np.linspace(floor[:,0].min(),floor[:,0].max(),100), np.linspace(floor[:,1].min(),floor[:,1].max(),100))
        xyz=np.stack([xx,yy,np.full_like(xx,-1.)],axis=-1)
        rgba=np.dstack([texture(xyz),np.ones_like(xx)])
        inside=PolygonPath(floor[:,:2]).contains_points(xyz[:,:,:2].reshape(-1,2),radius=1e-9).reshape(xx.shape)
        valid=inside[:-1,:-1]&inside[1:,:-1]&inside[:-1,1:]&inside[1:,1:]
        rgba[:-1,:-1,3]=valid
        ax.plot_surface(xx,yy,xyz[:,:,2],facecolors=rgba,rstride=1,cstride=1,shade=False,linewidth=0,antialiased=False,rasterized=True)

    for i in range(n):
        j=(i+1)%n
        if i in omitted: continue
        if textured:
            u,v=np.meshgrid(np.linspace(0,1,85),np.linspace(0,1,38))
            base=floor[i]+u[...,None]*(floor[j]-floor[i])
            roof=top[i]+u[...,None]*(top[j]-top[i])
            xyz=base+v[...,None]*(roof-base)
            ax.plot_surface(xyz[:,:,0],xyz[:,:,1],xyz[:,:,2],facecolors=texture(xyz),rstride=1,cstride=1,shade=False,linewidth=0,antialiased=False,rasterized=True)
        ax.plot(*np.array([top[i],top[j]]).T,color=color,lw=1.2)
        for k in [i,j]: ax.plot(*np.array([floor[k],top[k]]).T,color=color,lw=.65)
    ring=np.vstack([floor,floor[0]])
    ax.plot(*ring.T,color=color,lw=1.25)
    setup_view(ax,bounds)


def setup_view(ax,bounds):
    ax.set_proj_type('ortho');ax.view_init(elev=32,azim=-155)
    low,high=bounds
    ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1]);ax.set_zlim(low[2],high[2])
    ax.set_box_aspect(high-low);ax.set_axis_off()


def validate_viewer_projection(points,g):
    p=np.asarray(points)
    vf=(p[1::2,1]/512-.5)*np.pi
    vc=(p[::2,1]/512-.5)*np.pi
    u=p[::2,0]/1024*2*np.pi-np.pi
    dist=1.6/np.tan(np.clip(vf,.01,1.5))
    viewer_floor=np.c_[dist*np.sin(u),np.full(len(u),-1.6),-dist*np.cos(u)]
    viewer_top=viewer_floor.copy();viewer_top[:,1]=-dist*np.tan(np.clip(vc,-1.5,-.01))
    expected=np.array([viewer_floor[:,[0,2,1]],viewer_top[:,[0,2,1]]])/1.6
    assert np.allclose(expected,g,atol=1e-12)
    assert np.allclose(g[0,:,:2],g[1,:,:2])
    # Reproject both boundaries: folding retains each submitted point and ring order.
    for ring,px in zip(g,[p[1::2],p[::2]]):
        uu=(np.arctan2(ring[:,0],-ring[:,1])/(2*np.pi)+.5)*1024
        vv=(.5-np.arctan2(ring[:,2],np.hypot(ring[:,0],ring[:,1]))/np.pi)*512
        assert np.allclose(np.c_[uu,vv],px,atol=1e-9)


def figure4_texture():
    global photo
    saved=photo
    photo=np.asarray(Image.open(ROOT/'data/mp3d_layout/test/img/yqstnuAEVhm_2b3fb4746d414cc6a31729b222ed79b2.png').convert('RGB'))/255.
    d=json.loads((ROOT/'research/quality/quality_pro_return_review_20261014/evidence/J04_interventions.json').read_text(encoding='utf8'))
    gs=[geometry(d[k]) for k in ['reference_points','original_points']]
    for k,g in zip(['reference_points','original_points'],gs):validate_viewer_projection(d[k],g)
    pts=np.concatenate([g.reshape(-1,3) for g in gs]);bounds=(pts.min(0)-.08,pts.max(0)+.08)
    fig=plt.figure(figsize=(10,3.8),facecolor='white')
    ax=fig.add_axes([.015,.28,.29,.44]);ax.imshow(photo);ax.axis('off');ax.set_title('(a) Panorama',fontsize=10)
    for x,g,color,title in zip([.32,.655],gs,['#55616a','#2587bd'],['(b) Reference','(c) Annotation R03274']):
        ax=fig.add_axes([x,.16,.34,.74],projection='3d');draw(ax,g,True,color,bounds);ax.set_title(title,fontsize=10,pad=0)
    fig.text(.5,.10,'Same panorama, viewing angle and scale; each layout retains its own corner positions and heights.',ha='center',fontsize=8,color='#55616a')
    fig.text(.5,.045,'Texture is projected onto the layout surfaces; furniture appearance does not represent reconstructed geometry.',ha='center',fontsize=8,color='#55616a')
    for ext in ['png','pdf']:fig.savefig(OUT/('figure4_textured_preview.'+ext),dpi=220,bbox_inches='tight',pad_inches=.05)
    plt.close(fig);photo=saved


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    s=json.loads((ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text(encoding='utf8'))
    p=next(p for p in s['images'] if p['meta']['image']=='7y3sRwLe3Va-11' and p['meta']['condition']=='manual')
    records=[next(r for r in p['records'] if r['worker']==w) for w in ['W028','W032']]
    gs=[geometry(r['points']) for r in records]
    for r,g in zip(records,gs):
        validate_viewer_projection(r['points'],g)
    assert [g.shape[1] for g in gs]==[4,8]
    pts=np.concatenate([g.reshape(-1,3) for g in gs]);bounds=(pts.min(0)-.08,pts.max(0)+.08)
    # Same geometry, camera and bounds for both visual styles and both people.
    for textured,name in [(False,'zind_style_solid'),(True,'zind_style_textured')]:
        fig=plt.figure(figsize=(9,4.6),facecolor='white')
        ax=fig.add_axes([.01,.34,.29,.37]);ax.imshow(photo);ax.axis('off');ax.set_title('(a) Panorama',fontsize=10)
        for x,g,color,title in zip([.32,.66],gs,['#a65b23','#007f8b'],['(b) A18: 4 corners','(c) A22: 8 corners']):
            ax=fig.add_axes([x+.055,.67,.23,.26])
            floor=g[0];ring=np.vstack([floor,floor[0]])
            ax.fill(ring[:,0],ring[:,1],color='#e8edef')
            ax.plot(ring[:,0],ring[:,1],'-o',color=color,lw=1,ms=2.6)
            ax.set_xlim(-3.5,1.2);ax.set_ylim(-2,2);ax.set_aspect('equal');ax.set_title(title,fontsize=10,pad=7)
            ax.set_xticks([-3,-2,-1,0,1]);ax.set_yticks([-2,-1,0,1,2])
            ax.set_xlabel('x / h',fontsize=8,labelpad=1);ax.set_ylabel('z / h',fontsize=8,labelpad=1)
            ax.tick_params(labelsize=7,pad=1);ax.grid(alpha=.18,lw=.4)
            ax.axhline(0,color='#777',lw=.5,alpha=.6);ax.axvline(0,color='#777',lw=.5,alpha=.6)
            ax=fig.add_axes([x,.065,.34,.55],projection='3d');draw(ax,g,textured,color,bounds)
        fig.text(.5,.055,'Original corner order and individual top heights retained; identical view and scale.',ha='center',fontsize=8,color='#55616a')
        fig.text(.5,.018,'Roof and two near walls hidden for visibility.' + (' Texture is a panorama projection, not reconstructed furniture.' if textured else ''),ha='center',fontsize=8,color='#55616a')
        for ext in ['png','pdf']:fig.savefig(OUT/(name+'.'+ext),dpi=220,bbox_inches='tight',pad_inches=.05)
        plt.close(fig)
    figure4_texture()
    print('Fireplace and J04 previews rendered; viewer projection checks passed; manuscript unchanged.')

if __name__=='__main__':main()
