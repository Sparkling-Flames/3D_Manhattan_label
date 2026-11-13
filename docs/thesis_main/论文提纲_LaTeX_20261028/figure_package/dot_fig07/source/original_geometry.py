"""Traceable scientific artwork for revised figures 6 and 7.

Run from any directory. All inputs are in data/; output panels contain no figure
or subfigure captions. Native LaTeX supplies those captions underneath.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle, ConnectionPatch
from PIL import Image

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'data/consensus_case.json').read_text())
OUT=ROOT/'panels'; OUT.mkdir(exist_ok=True)
BLUE='#0072B2'; ORANGE='#D55E00'; INK='#44316E'; GRAY='#90999F'; DARK='#273640'
COLORS=[BLUE,ORANGE]; MARKERS=['o','^']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.0,
                     'axes.linewidth':.6,'pdf.fonttype':42,'ps.fonttype':42,
                     'svg.fonttype':'none','savefig.facecolor':'white'})
checks=[]

def saved(fig,number,name):
    folder=OUT/f'fig{number:02d}';folder.mkdir(exist_ok=True)
    for ext in ['pdf','svg','png']:
        fig.savefig(folder/f'{name}.{ext}',dpi=600,facecolor='white')
    plt.close(fig)

def align(pairs):
    p=np.asarray(pairs,float).reshape(-1,2,2).copy()
    du=(p[:,1,0]-p[:,0,0]+512)%1024-512
    u=(p[:,0,0]+du/2)%1024
    p[:,:,0]=u[:,None]
    return p

def reconstruct(points):
    """Floor y=-1; pair u is the midpoint of the shorter horizontal arc."""
    p=align(points)
    az=2*np.pi*(p[:,0,0]/1024-.5)
    el=np.pi*(.5-p[:,:,1]/512)
    radius=-1/np.tan(el[:,1])
    x=radius*np.sin(az);z=-radius*np.cos(az)
    bottom=np.c_[x,np.full(len(x),-1.),z]
    upper=np.c_[x,radius*np.tan(el[:,0]),z]
    assert np.all(upper[:,1]>-1)
    return bottom,upper

def project_panorama(points):
    p=np.asarray(points);az=np.arctan2(p[:,0],-p[:,2])
    el=np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))
    return np.c_[(az/(2*np.pi)+.5)*1024,(.5-el/np.pi)*512]

def boundary_from_3d(a,b):
    # A physical straight wall edge projects to a spherical arc.
    return project_panorama(np.linspace(a,b,160))

def ray(xy):
    xy=np.asarray(xy);az=2*np.pi*(xy[:,0]/1024-.5);el=np.pi*(.5-xy[:,1]/512)
    return np.c_[np.cos(el)*np.sin(az),-np.cos(el)*np.cos(az),np.sin(el)]

def median_pair(pairs):
    p=align(pairs)
    angular=[]
    for endpoint in [0,1]:
        r=ray(p[:,endpoint]);angular.append(np.rad2deg(np.arccos(np.clip(r@r.T,-1,1))))
    anchor=int(np.argmin(np.maximum(*angular).sum(axis=1)))
    u0=p[anchor,0,0];delta=(p[:,0,0]-u0+512)%1024-512
    u=(u0+np.median(delta))%1024
    return np.array([[u,np.median(p[:,0,1])],[u,np.median(p[:,1,1])]])

def verify():
    for name,t in DATA['teams'].items():
        assert t['n']==len(t['people'])==10
        assert t['threshold']==5
        b,u=reconstruct(t['candidate']['points']);p=np.asarray(t['candidate']['points']).reshape(-1,2,2)
        err=float(np.max(abs(b[:,[0,2]]-np.asarray(t['candidate']['footprint']))))
        rep=np.stack([project_panorama(u),project_panorama(b)],axis=1)
        checks.append({'team':name,'nodes':len(b),'stored_footprint_max_error':err,
                       'reprojection_max_error_pixels':float(abs(rep-p).max()),
                       'vertical_pairs_max_xz_error':float(abs(b[:,[0,2]]-u[:,[0,2]]).max()),
                       'local_wall_heights':(u[:,1]+1).tolist()})
        assert err<1e-12 and abs(rep-p).max()<1e-10
        for node in t['turns']:
            people={m['person'] for m in node['members']}
            assert len(people)==len(node['members'])==node['support']
            assert node['selected']==(2*node['support']>=t['n'])
            actual=median_pair([m['pair'] for m in node['members']])
            error=float(abs(actual-np.asarray(node['pair'])).max())
            assert error<1e-10
            # Both displayed identities are checked against their exact contributors.
            for m in node['members']:
                rec=next(p for p in t['people'] if p['person']==m['person'])
                source=np.asarray(rec['points']).reshape(-1,2,2)[m['pair_index']]
                assert np.array_equal(source,np.asarray(m['pair']))
            checks.append({'team':name,'turn':node['label'],'support':node['support'],
                           'selected':node['selected'],'median_max_error_pixels':error,
                           'all_points_equal_to_saved_observations':True})

def symbol(ax,xy,i,filled=False,size=25,zorder=10,alpha=1):
    xy=np.asarray(xy).reshape(-1,2)
    ax.scatter(xy[:,0],xy[:,1],s=size,marker=MARKERS[i],
               facecolors=COLORS[i] if filled else 'white',edgecolors=COLORS[i],
               linewidths=.8,zorder=zorder,alpha=alpha)

def annotate_id(ax,xy,label,color,offset):
    ax.annotate(label,xy,xytext=offset,textcoords='offset points',ha='center',va='center',
                fontsize=8.5,color=color,weight='bold',zorder=30,
                bbox={'facecolor':'white','edgecolor':'none','pad':.7},
                arrowprops={'arrowstyle':'-','color':color,'lw':.6,'shrinkB':3})

def fig6():
    team=DATA['teams']['Team 2'];bot,top=reconstruct(team['candidate']['points'])
    nodes=team['turns'];colors=COLORS
    # (a) Observed upper endpoints and the output boundary share real pixels.
    fig=plt.figure(figsize=(2.28,2.08));ax=fig.add_axes([.035,.045,.93,.92])
    photo=Image.open(ROOT/'data'/DATA['photo']['filename'])
    ax.imshow(photo,extent=DATA['photo']['extent'],interpolation='none')
    ax.set(xlim=(659,710),ylim=(180,134));ax.set_aspect('equal')
    for j in [2,3,4]:
        curve=boundary_from_3d(top[j],top[(j+1)%len(top)])
        ax.plot(curve[:,0],curve[:,1],color='white',lw=2.4,zorder=4)
        ax.plot(curve[:,0],curve[:,1],color=INK,lw=1.0,zorder=5)
    for i,node in enumerate(nodes):
        observations=np.array([m['pair'][0] for m in node['members']])
        symbol(ax,observations,i,False,18,7,1)
        point=np.asarray(node['pair'])[0];symbol(ax,point,i,True,31,9)
        annotate_id(ax,point,node['label'],colors[i],(-17,15) if i==0 else (17,-11))
    ax.set_xticks([]);ax.set_yticks([])
    for s in ax.spines.values():s.set_color('#8B949B');s.set_linewidth(.55)
    saved(fig,6,'a_upper_evidence')

    # (b) Same paired observations, now shown at their actual floor positions.
    fig=plt.figure(figsize=(2.28,2.08));ax=fig.add_axes([.20,.20,.77,.76])
    for rec in team['people']:
        f,_=reconstruct(rec['points']);q=np.vstack([f,f[:1]])
        ax.plot(q[:,0],q[:,2],c=GRAY,lw=.65,alpha=.5,zorder=1)
    for i,node in enumerate(nodes):
        xy=[]
        for m in node['members']:
            p,_=reconstruct(m['pair']);xy.append(p[0,[0,2]])
        symbol(ax,xy,i,False,20,3)
    q=np.vstack([bot,bot[:1]])
    ax.plot(q[:,0],q[:,2],c='white',lw=3.3,zorder=4)
    ax.plot(q[:,0],q[:,2],c=INK,lw=1.5,zorder=5)
    for i,node in enumerate(nodes):
        b,_=reconstruct(node['pair']);point=b[0,[0,2]];symbol(ax,point,i,True,42,8)
        annotate_id(ax,point,node['label'],colors[i],(-13,13) if i==0 else (12,-13))
    ax.set(xlim=(.51,.91),ylim=(-.60,-.20),xlabel='$x/h$',ylabel='$z/h$')
    ax.set_aspect('equal');ax.set_xticks([.6,.8]);ax.set_yticks([-.6,-.4,-.2]);ax.tick_params(labelsize=7.7,length=2.5)
    ax.spines[['top','right']].set_visible(False)
    saved(fig,6,'b_lower_evidence')

    # (c) One genuine 3D object. Every endpoint uses the same input as (a,b).
    fig=plt.figure(figsize=(2.28,2.08));ax=fig.add_axes([.005,.18,.66,.80]);ax.axis('off');ax.set_aspect('equal')
    azimuth=np.deg2rad(18);elevation=np.deg2rad(25)
    screen=np.array([[np.cos(azimuth),0,np.sin(azimuth)],
        [-np.sin(azimuth)*np.sin(elevation),np.cos(elevation),np.cos(azimuth)*np.sin(elevation)]])
    assert np.allclose(screen@screen.T,np.eye(2),atol=1e-14)
    def proj(xyz):
        p=np.asarray(xyz).copy();p[:,1]+=1
        return p@screen.T
    B,T=proj(bot),proj(top)
    def draw_model(target,detail=False):
        # Cutaway surfaces leave the front open; the complete wireframe remains.
        target.add_patch(Polygon(B,closed=True,facecolor=INK,edgecolor='none',alpha=.055,zorder=0))
        for j in [0,5]:
            k=(j+1)%len(bot);face=np.vstack([B[j],B[k],T[k],T[j]])
            target.add_patch(Polygon(face,closed=True,facecolor=INK,edgecolor='none',alpha=.065,zorder=1))
        face=np.vstack([B[3],B[4],T[4],T[3]])
        target.add_patch(Polygon(face,closed=True,facecolor=ORANGE,edgecolor='none',alpha=.16,zorder=2))
        q=np.vstack([T,T[:1]]);target.plot(q[:,0],q[:,1],c=INK,lw=.9,zorder=3)
        for j in range(len(B)):
            k=(j+1)%len(B)
            target.plot([B[j,0],B[k,0]],[B[j,1],B[k,1]],c=INK,lw=.6 if j in [0,5] else .9,
                    ls=(0,(3,2)) if j in [0,5] else '-',alpha=.55 if j in [0,5] else 1,zorder=3)
        for j in range(len(B)):
            color=colors[j-3] if j in [3,4] else '#879099'
            target.plot([B[j,0],T[j,0]],[B[j,1],T[j,1]],color=color,lw=1.1 if j in [3,4] else .6,
                    ls=(0,(3,2)) if j==0 else '-',zorder=4)
        for i,j in enumerate([3,4]):
            symbol(target,B[j],i,True,8 if detail else 5,6)
            symbol(target,T[j],i,True,14 if detail else 6,6)
            if detail:annotate_id(target,T[j],nodes[i]['label'],colors[i],(-8,9) if i==0 else (10,5))
    draw_model(ax)
    # The wall face is highlighted, not widened or extruded to an average height.
    q=np.vstack([B,T]);lo=q.min(0);hi=q.max(0)
    ax.set(xlim=(lo[0]-.06,hi[0]+.10),ylim=(lo[1]-.07,hi[1]+.08))
    # A square crop of the very same orthographic projection makes the actual
    # shallow wall offset readable without widening the structure itself.
    mid=(T[3]+T[4])/2;side=.36
    detail_bounds=(mid[0]-side/2,mid[1]-.215,side,side)
    ax.add_patch(Rectangle(detail_bounds[:2],side,side,fill=False,edgecolor=DARK,lw=.55,ls=(0,(2,2)),zorder=12))
    ia=fig.add_axes([.66,.075,.33,.42]);ia.set_aspect('equal');draw_model(ia,True)
    ia.set(xlim=(detail_bounds[0],detail_bounds[0]+side),ylim=(detail_bounds[1],detail_bounds[1]+side))
    ia.set_xticks([]);ia.set_yticks([])
    for sp in ia.spines.values():sp.set_linewidth(.6);sp.set_color(DARK)
    for a,bp in [((0,0),(detail_bounds[0]+side,detail_bounds[1])),((0,1),(detail_bounds[0]+side,detail_bounds[1]+side))]:
        fig.add_artist(ConnectionPatch(a,bp,coordsA=ia.transAxes,coordsB=ax.transData,
                         color=DARK,lw=.5,linestyle=(0,(2,2)),zorder=0))
    checks.append({'fig6_3d_orthographic_basis_gram':(screen@screen.T).tolist(),
                   'azimuth_parameter_degrees':18,'elevation_degrees':25,
                   'detail_same_coordinates_and_projection':True,
                   'detail_bounds_in_projection_units':list(detail_bounds)})
    saved(fig,6,'c_actual_layout')

    fig=plt.figure(figsize=(6.8,.28));ax=fig.add_axes([0,0,1,1]);ax.axis('off')
    handles=[Line2D([],[],marker='o',ls='',markerfacecolor='none',markeredgecolor=BLUE,label='Turn A'),
             Line2D([],[],marker='^',ls='',markerfacecolor='none',markeredgecolor=ORANGE,label='Turn B'),
             Line2D([],[],marker='o',ls='',markerfacecolor='none',markeredgecolor=GRAY,label='Open: individual'),
             Line2D([],[],marker='o',ls='',markerfacecolor=DARK,markeredgecolor=DARK,label='Filled: consensus'),
             Line2D([],[],color=INK,lw=1.4,label='Consensus boundary')]
    ax.legend(handles=handles,loc='center',ncol=5,frameon=False,fontsize=7.3,columnspacing=1.,handletextpad=.35,handlelength=1.2)
    saved(fig,6,'legend')

def fig7():
    teams=list(DATA['teams'].items())
    # Exact independent-person support. Rows identify different actual people
    # in each team; no cross-team identity is implied by horizontal alignment.
    fig=plt.figure(figsize=(1.38,2.22));ax=fig.add_axes([.02,.02,.96,.96]);ax.axis('off')
    for tindex,(name,t) in enumerate(teams):
        xs=[.06+tindex*1.10,.42+tindex*1.10]
        for i,node in enumerate(t['turns']):
            supporters={m['person'] for m in node['members']}
            for r,rec in enumerate(t['people']):
                yes=rec['person'] in supporters
                symbol(ax,[xs[i],9-r],i,yes,20,3)
            ax.text(xs[i],10.0,node['label'],ha='center',va='center',fontsize=8.2,color=COLORS[i],weight='bold')
            ax.text(xs[i],-1.0,f"{node['support']}",ha='center',va='center',fontsize=8.2,color=COLORS[i],weight='bold')
        ax.text(np.mean(xs),-2.1,name,ha='center',va='center',fontsize=8.0)
    ax.set(xlim=(-.22,1.85),ylim=(-2.7,10.6))
    saved(fig,7,'a_actual_support')

    ref,_=reconstruct(DATA['reference']);ref=np.vstack([ref,ref[:1]])
    for number,(name,t) in enumerate(teams):
        fig=plt.figure(figsize=(2.70,2.22));ax=fig.add_axes([.145,.18,.46,.78])
        b,_=reconstruct(t['candidate']['points']);q=np.vstack([b,b[:1]])
        # Individual polygons appear in the local inset, keeping the complete
        # footprints clean enough to judge the structural output.
        ax.plot(ref[:,0],ref[:,2],color=GRAY,lw=1.0,ls=(0,(3,2)),zorder=2)
        ax.plot(q[:,0],q[:,2],color=INK,lw=1.6,zorder=3)
        ax.scatter(b[:,0],b[:,2],s=12,c=INK,zorder=4)
        ax.set(xlim=(-.75,1.0),ylim=(-1.18,.88),xlabel='$x/h$',ylabel='$z/h$')
        ax.set_aspect('equal');ax.set_xticks([-.5,0,.5]);ax.set_yticks([-1,-.5,0,.5]);ax.tick_params(labelsize=7.5,length=2.5)
        # Keep the vertical title inside this compact panel without moving or
        # rescaling either the complete footprint or its detail. Its position
        # fits between the -0.5 and 0.0 tick labels in the reserved left margin.
        ax.yaxis.set_label_coords(-.17,.45)
        ax.spines[['top','right']].set_visible(False)
        # Mark the exact region enlarged; identical limits and physical scale.
        zoom=(.50,-.60,.43,.43)
        ax.add_patch(Rectangle(zoom[:2],zoom[2],zoom[3],fill=False,lw=.65,ls=(0,(2,2)),edgecolor=DARK,zorder=5))
        ia=fig.add_axes([.64,.385,.34,.42]);ia.set_facecolor('white')
        for rec in t['people']:
            f,_=reconstruct(rec['points']);p=np.vstack([f,f[:1]])
            ia.plot(p[:,0],p[:,2],c=GRAY,lw=.45,alpha=.65,zorder=1)
        ia.plot(ref[:,0],ref[:,2],color=GRAY,lw=.85,ls=(0,(3,2)),zorder=2)
        ia.plot(q[:,0],q[:,2],color='white',lw=3.0,zorder=3)
        ia.plot(q[:,0],q[:,2],color=INK,lw=1.5,zorder=4)
        for i,node in enumerate(t['turns']):
            p,_=reconstruct(node['pair']);xy=p[0,[0,2]]
            symbol(ia,xy,i,node['selected'],26,6)
            if not node['selected']:
                # Crosses are attached to the two below-threshold clusters.
                ia.scatter([xy[0]],[xy[1]],marker='x',s=13,c=COLORS[i],lw=.6,zorder=7)
            ia.annotate(node['label'],xy,xytext=(0,12) if i==0 else (8,-11),textcoords='offset points',
                        color=COLORS[i],fontsize=7.8,weight='bold',ha='center',va='center',zorder=8)
            if node['selected']:symbol(ax,xy,i,True,17,7)
        ia.set(xlim=(zoom[0],zoom[0]+zoom[2]),ylim=(zoom[1],zoom[1]+zoom[3]));ia.set_aspect('equal')
        ia.set_xticks([]);ia.set_yticks([])
        for sp in ia.spines.values():sp.set_color(DARK);sp.set_linewidth(.65)
        for a,bp in [((0,0),(zoom[0]+zoom[2],zoom[1])),((0,1),(zoom[0]+zoom[2],zoom[1]+zoom[3]))]:
            fig.add_artist(ConnectionPatch(a,bp,coordsA=ia.transAxes,coordsB=ax.transData,
                             color=DARK,lw=.55,linestyle=(0,(2,2)),zorder=1))
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer()
        label_box=ax.yaxis.label.get_window_extent(renderer)
        assert label_box.x0>0 and label_box.x1<fig.bbox.x1
        assert label_box.y0>0 and label_box.y1<fig.bbox.y1
        assert not any(label_box.overlaps(t.get_window_extent(renderer)) for t in ax.get_yticklabels())
        checks.append({'figure':7,'team':name,'vertical_axis_title':'z/h',
                       'ylabel_bbox_pixels':list(label_box.bounds),'figure_dpi':fig.dpi,
                       'ylabel_fully_inside_canvas':True,'ylabel_tick_overlap':False,
                       'axes_and_detail_geometry_unchanged':True})
        saved(fig,7,'b_team1_floor' if number==0 else 'c_team2_floor')

    fig=plt.figure(figsize=(6.8,.30));ax=fig.add_axes([0,0,1,1]);ax.axis('off')
    handles=[Line2D([],[],color=INK,lw=1.5,label='Consensus'),
             Line2D([],[],color=GRAY,lw=1,ls=(0,(3,2)),label='Reference'),
             Line2D([],[],color=GRAY,lw=.5,label='Individual'),
             Line2D([],[],marker='o',ls='',markerfacecolor=DARK,markeredgecolor=DARK,label='Marked'),
             Line2D([],[],marker='o',ls='',markerfacecolor='white',markeredgecolor=DARK,label='Omitted'),
             Line2D([],[],marker='x',ls='',color=DARK,label='Below threshold')]
    ax.legend(handles=handles,loc='center',ncol=6,frameon=False,fontsize=7.1,columnspacing=.85,handlelength=1.2,handletextpad=.35)
    saved(fig,7,'legend')

if __name__=='__main__':
    verify();fig6();fig7()
    (ROOT/'qa/verification.json').write_text(json.dumps({'checks':checks,'new_experiment':False,
        'newly_recomputed_geometry':'Exact projection of saved endpoints, for drawing only',
        'aggregation':'Coordinate medians checked against saved centers; no team reanalysis',
        'spatial_scaling':'Equal x/z scale in every plan-view panel and inset; same limits across teams',
        'top_height':'Separate saved upper endpoint at every retained corner; no mean-height replacement',
        'subfigure_captions_embedded':False,'dpi':600},indent=2)+'\n')
    print(json.dumps(checks,indent=2))
