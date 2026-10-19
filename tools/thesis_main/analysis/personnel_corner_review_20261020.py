"""Four reviewed cases: corresponding-corner displacements, with unchanged fusion."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from tools.thesis_main.analysis.personnel_composition_followup_20261019 import OUT, read, save, csv, modules


def project(points):
    # Same continuous-coordinate projection as workbench-core.js, camera height = 1.
    p = np.asarray(points,float)
    assert p.ndim==2 and p.shape[1]==2 and len(p)%2==0 and np.isfinite(p).all()
    t,b = p[::2],p[1::2]
    assert np.allclose(t[:,0],b[:,0],atol=1e-8,rtol=0)
    a=(b[:,0]/1024-.5)*2*np.pi
    v=(b[:,1]/512-.5)*np.pi
    assert ((v>0)&(v<np.pi/2)).all()
    r=1/np.tan(v)
    bottom=np.column_stack((r*np.sin(a),-np.ones(len(r)),-r*np.cos(a)))
    top=bottom.copy();top[:,1]=r*np.tan((.5-t[:,1]/512)*np.pi)
    return bottom,top


def pixel_delta(a,b):
    d=b-a
    d[:,0]=(d[:,0]+512)%1024-512
    return d


def main():
    _,_,sg=modules()
    cases=read(OUT/'REVIEW_CASES.json')['cases']
    rows, summaries, matches=[],[],[]
    for number,case in enumerate(cases,1):
        points={k:np.asarray(t['geometry']['points']) for k,t in case['teams'].items()}
        aligned={'A':points['A']}
        for arm in 'BC':
            distance,reason,shift=sg.structural_distance(points['A'],points[arm])
            assert not reason
            n=len(points[arm])//2
            aligned[arm]=points[arm].reshape(n,2,2)[(np.arange(n)+shift)%n].reshape(-1,2)
            alternatives=[]
            for s in range(n):
                idx=(np.arange(n)+s)%n
                cost=np.maximum(sg.angular(points['A'][::2],points[arm][::2]),sg.angular(points['A'][1::2],points[arm][1::2]))
                alternatives.append(float(cost[np.arange(n),idx].max()))
            matches.append(dict(case=number,arm=arm,shift=shift,max_angle_deg=distance,second_best_max_angle_deg=sorted(alternatives)[1],index_mapping=((np.arange(n)+shift)%n).tolist()))
        geometry={k:project(p) for k,p in aligned.items()}
        for arm in 'ABC':
            saved=np.asarray(case['teams'][arm]['geometry']['footprint'])
            raw_bottom,_=project(points[arm])
            np.testing.assert_allclose(raw_bottom[:,[0,2]],saved,atol=1e-8,rtol=0)
        for pair in ['AB','AC','BC']:
            a,b=pair;pa,pb=aligned[a],aligned[b];ba,ta=geometry[a];bb,tb=geometry[b]
            du=pixel_delta(pa[1::2],pb[1::2]);dt=pixel_delta(pa[::2],pb[::2])
            floor=np.linalg.norm(bb-ba,axis=1);top=np.linalg.norm(tb-ta,axis=1)
            radius=np.linalg.norm(ba[:,[0,2]],axis=1)
            radial=np.linalg.norm(bb[:,[0,2]],axis=1)-radius
            diagonal=np.linalg.norm(np.ptp(ba[:,[0,2]],axis=0))
            for j in range(len(ba)):
                rows.append(dict(case=number,image=case['image']['image_code'],pair=pair,corner_A_index=j,
                    dx_px=du[j,0],bottom_dy_px=du[j,1],top_dy_px=dt[j,1],bottom_pixel_distance=np.linalg.norm(du[j]),top_pixel_distance=np.linalg.norm(dt[j]),
                    bev_distance_h=floor[j],top_3d_distance_h=top[j],height_change_h=tb[j,1]-ta[j,1],radial_change_h=radial[j],
                    bev_percent_radius=100*floor[j]/radius[j],bev_percent_diagonal=100*floor[j]/diagonal,
                    from_x_h=ba[j,0],from_z_h=ba[j,2],to_x_h=bb[j,0],to_z_h=bb[j,2]))
            summaries.append(dict(case=number,image=case['image']['image_code'],pair=pair,corners=len(ba),
                bev_mean_h=floor.mean(),bev_max_h=floor.max(),bev_max_corner=int(floor.argmax()),
                top_3d_mean_h=top.mean(),top_3d_max_h=top.max(),top_max_corner=int(top.argmax()),
                max_abs_bottom_dy_px=abs(du[:,1]).max(),max_abs_top_dy_px=abs(dt[:,1]).max(),
                max_bev_percent_radius=(100*floor/radius).max(),max_bev_percent_diagonal=(100*floor/diagonal).max(),
                abs_Q_difference=abs(case['teams'][a]['B8L2']-case['teams'][b]['B8L2'])))
        figure(number,case,geometry)
    csv(OUT/'CORNER_DISTANCES.csv',pd.DataFrame(rows))
    csv(OUT/'CORNER_SUMMARY.csv',pd.DataFrame(summaries))
    save(OUT/'CORNER_MATCHING.json',dict(method='Original frozen bound-cyclic spherical distance, no reverse; align B and C to A. Node IDs are local and not treated as identity proof.',matches=matches,
        projection='workbench-core.js continuous pixel coordinates, camera height h=1; no pixel-center +0.5 in projection. Frozen angular matching keeps its historical +0.5 convention.',units='pixels on 1024x512 ERP; world distances in camera-height h; bottom 3D distance equals BEV distance since all bottom y=-1',scope='four displayed cases only; no new similarity cutoff or population inference'))
    print(pd.DataFrame(summaries).round(4).to_string(index=False))


def figure(number,case,geometry):
    colors={'A':'#087f8c','B':'#b45309','C':'#dc2626','GT':'#7c3aed'}
    gs={**geometry,'GT':project(case['reference']['points'])}
    fig=plt.figure(figsize=(13,6));ax=fig.add_subplot(121);world=fig.add_subplot(122,projection='3d')
    for label,(bottom,top) in gs.items():
        ring=bottom[np.r_[np.arange(len(bottom)),0]];upper=top[np.r_[np.arange(len(top)),0]]
        style='--' if label=='GT' else '-'
        ax.plot(ring[:,0],ring[:,2],style,color=colors[label],marker='.' if label!='GT' else None,label=label,linewidth=1.3)
        for r in (ring,upper):world.plot(r[:,0],r[:,2],r[:,1],style,color=colors[label],linewidth=1)
        for b,t in zip(bottom,top):world.plot([b[0],t[0]],[b[2],t[2]],[b[1],t[1]],color=colors[label],alpha=.5,linewidth=.8)
    for j,p in enumerate(geometry['A'][0]):ax.annotate(str(j),(p[0],p[2]),xytext=(5,5),textcoords='offset points',fontsize=10)
    ax.scatter([0],[0],c='black',s=12);ax.set_aspect('equal');ax.invert_yaxis();ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h (downward, same as workbench)');ax.set_title('BEV: A-index labels; actual displacement')
    allpoints=np.concatenate([p for pair in gs.values() for p in pair]);world.set_box_aspect(np.ptp(allpoints[:,[0,2,1]],axis=0));world.set_xlabel('x / h');world.set_ylabel('z / h');world.set_zlabel('height / h');world.set_title('3D: common camera coordinates, no fitting');world.view_init(elev=22,azim=-60)
    for axis in [world.xaxis,world.yaxis,world.zaxis]:axis.set_major_locator(MaxNLocator(3))
    world.tick_params(labelsize=8)
    fig.suptitle(f'Case {number}: {case["image"]["image_code"]}');fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.96),ncol=4);fig.tight_layout(rect=(0,0,1,.9));fig.savefig(OUT/f'corner_case_{number}.png',dpi=160);plt.close(fig)


if __name__=='__main__':
    main()
