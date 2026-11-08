"""门洞竖棱与公开相机平移共同约束的比例草稿；不读取GT。"""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'docs/thesis_main/论文写作工作资料/门洞实景观察_20261107'
OUT=ROOT/'analysis_results/doorway_point_folding_20261107'
DEPTH=ROOT/'analysis_results/doorway_depth_probe_20261107'
IDS={'07':'53937db036374126830e0f1203b04ead','06':'3be66dc4f0fb46449d63b07d92c74f3f','15':'b72b7b78675f429a9f382a44e551cffc'}
# 左右均按07朝向走廊时命名；15看门外，06反向看门内。
OBS=[('07',0,450),('07',1,534),('07',2,1496),('07',3,1590),
     ('15',0,1285),('15',3,1397),('06',1,1681),('06',2,1516)]
NAMES=['L1','L2','R2','R1']
OFFSETS={'07':0.,'15':0.,'06':np.pi/2}
TOP={'15':[[380,266],[650,267],[1397,269],[1656,266]],
     '06':[[377,269],[621,264],[1403,237],[1704,239]]}
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})


def rotation(t):
    return np.array([[np.cos(t),np.sin(t)],[-np.sin(t),np.cos(t)]])


def corners(v):
    cx,cy,t,w,d=v
    return np.array([[-w/2,-d/2],[-w/2,d/2],[w/2,d/2],[w/2,-d/2]])@rotation(t).T+[cx,cy]


def residual(v,positions,observations):
    q=corners(v);out=[]
    for cam,i,u in observations:
        local=(q[i]-positions[cam][:2])@rotation(v[2]+OFFSETS[cam])
        phi=np.arctan2(local[0],local[1]);want=(u/2048-.5)*2*np.pi
        out.append(np.arctan2(np.sin(phi-want),np.cos(phi-want))*2048/(2*np.pi))
    return np.array(out)


def fit(positions,observations):
    return least_squares(residual,[4.18,-2.87,-1.55,.8,.12],args=(positions,observations),
                         bounds=([3.7,-3.2,-2.1,.3,.01],[4.7,-2.4,-.9,2.,.8]))


def ray_xy(uv):
    p=np.asarray(uv,float);lon=2*np.pi*(p[:,0]/2048-.5);lat=np.pi*(.5-p[:,1]/1024)
    return np.column_stack((np.sin(lon),np.cos(lon)))/np.tan(lat)[:,None]


def panorama_path(cam):
    return ROOT/'data/mp3d_layout/valid/img'/f'2t7WUuJeko7_{IDS[cam]}.png'


def annotate(scene):
    im=Image.open(panorama_path('07'))
    fig=plt.figure(figsize=(14,7.8))
    top=fig.add_axes([.025,.12,.95,.80]);top.imshow(im);top.axis('off')
    colors=['#237f9c','#237f9c','#ce6f28','#ce6f28']
    spans=[(280,860),(290,860),(265,880),(285,820)]
    for (_,i,u),color,(a,b) in zip(OBS[:4],colors,spans):
        top.plot([u,u],[a,b],color=color,lw=2)
        top.text(u+(10 if i in (1,3) else -10),210,NAMES[i],ha='left' if i in (1,3) else 'right',
                 color=color,fontsize=13,weight='bold',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    fig.suptitle('07 门洞：两侧固定转折的重新标记',fontsize=18,y=.98)
    fig.text(.5,.045,'L1/R1：浴室侧固定转折；L2/R2：内侧门框边。标记的是竖棱方位，不把遮挡或模糊区当作可见墙地角。',ha='center',fontsize=10,color='#536676')
    fig.savefig(WORK/'doorway_turns_07.png',dpi=170,facecolor='white');plt.close(fig)
    fig=plt.figure(figsize=(7,9))
    titles=['左侧 L1 / L2','右侧 R2 / R1']
    for k,(lo,hi) in enumerate([(385,650),(1380,1655)]):
        ax=fig.add_axes([.10+.48*k,.13,.35,.78]);ax.imshow(im)
        ax.set_xlim(lo,hi);ax.set_ylim(940,190);ax.set_title(titles[k],fontsize=12,pad=10)
        for (_,i,u),color,(a,b) in zip(OBS[:4],colors,spans):
            if not lo<u<hi:continue
            ax.plot([u,u],[a,b],color=color,lw=2)
            ax.plot([u,u],[b,920],color=color,lw=1.2,ls='--')
            ax.text(u+4,245,NAMES[i],color=color,fontsize=12,weight='bold',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
        ax.set_xlabel('原图水平坐标 u / px');ax.set_ylabel('原图竖直坐标 v / px')
        ax.tick_params(labelsize=9)
    fig.text(.5,.04,'实线：可辨认竖棱；虚线：向遮挡／模糊区延伸。',ha='center',fontsize=10,color='#536676')
    fig.savefig(WORK/'doorway_turns_detail.png',dpi=170,facecolor='white');plt.close(fig)
    fig,axs=plt.subplots(2,1,figsize=(13,11))
    for ax,cam in zip(axs,['15','06']):
        ax.imshow(Image.open(panorama_path(cam)))
        for c,i,u in OBS:
            if c!=cam:continue
            ax.plot([u,u],[300,850],color=colors[i],lw=1.8,ls='--')
            ax.text(u+8,280,NAMES[i],color=colors[i],fontsize=12,weight='bold',bbox={'facecolor':'white','edgecolor':'none','alpha':.9})
        pts=np.array(TOP[cam]);ax.scatter(pts[:,0],pts[:,1],s=25,facecolor='white',edgecolor='#415f68',zorder=4)
        ax.set_title(f'{cam}：同一门洞的对应竖棱与顶部交界候选',fontsize=13);ax.axis('off')
    fig.tight_layout();fig.savefig(WORK/'doorway_correspondences.png',dpi=150,facecolor='white');plt.close(fig)


def main():
    source=json.loads((DEPTH/'official_connectivity_selected.json').read_text(encoding='utf-8'))
    records={r['image_id']:r for r in source['selected']}
    positions={k:np.array(records[uid]['camera_center_m']) for k,uid in IDS.items()}
    # 合成已知矩形与同样相机基线，检查尺度和方位能被正确反解。
    truth=np.array([4.20,-2.9,-1.54,.8,.12]);synthetic=[]
    for cam,i,_ in OBS:
        p=(corners(truth)[i]-positions[cam][:2])@rotation(truth[2]+OFFSETS[cam])
        synthetic.append((cam,i,(np.arctan2(p[0],p[1])/(2*np.pi)+.5)*2048))
    assert np.allclose(fit(positions,synthetic).x,truth,atol=1e-6)
    result=fit(positions,OBS);assert result.success and np.max(abs(result.fun))<15
    v=result.x;w,d=v[3:];cam_local={k:np.r_[(p[:2]-v[:2])@rotation(v[2]),p[2]] for k,p in positions.items()}
    bounds={};ceilings={};room_points={}
    for cam in ['15','06']:
        plane=ray_xy(TOP[cam])@rotation(OFFSETS[cam]).T
        near=[1,2] if cam=='15' else [2,3]
        near_y=-d/2 if cam=='15' else d/2
        scale=(near_y-cam_local[cam][1])/plane[near,1].mean()
        assert scale>0
        points=plane*scale+cam_local[cam][:2];room_points[cam]=points
        if cam=='15':
            bb=[points[[0,1],0].mean(),points[[2,3],0].mean(),points[[0,3],1].mean(),near_y]
        else:
            bb=[points[[0,3],0].mean(),points[[1,2],0].mean(),near_y,points[[0,1],1].mean()]
        assert bb[0]<-w/2<w/2<bb[1]
        bounds[cam]=bb;ceilings[cam]=float(positions[cam][2]+scale)
    # shortcut: 两房各采用水平顶面和主轴墙；需要扫描数据时再替换此照片约束草稿。
    height=float(np.mean(list(ceilings.values())))
    door_heights=[]
    for i,top_v in [(2,430),(1,435)]:
        distance=np.linalg.norm(corners(v)[i]-positions['06'][:2])
        door_heights.append(float(positions['06'][2]+distance*np.tan(np.pi*(.5-top_v/1024))))
    side_y=[]
    for u in [1186,1397]:
        phi=2*np.pi*(u/2048-.5);ray=np.array([np.cos(phi),-np.sin(phi)])
        distance=(bounds['06'][1]-cam_local['06'][0])/ray[0]
        side_y.append(float(cam_local['06'][1]+distance*ray[1]))
    checks=[]
    depth=np.asarray(Image.open(DEPTH/f'2t7WUuJeko7_{IDS["07"]}.depth.png'))/1000
    for j,(_,i,u) in enumerate(OBS[:4]):
        pred=float(np.median(depth[245:267,u//2-3:u//2+4]))
        checks.append({'id':NAMES[i],'fitted_horizontal_range_m':float(np.linalg.norm(corners(v)[i]-positions['07'][:2])),
                       'hohonet_median_near_horizon_m':pred,'role':'prediction_crosscheck_not_fit_input'})
    scene={'basis':'照片门洞竖棱＋公开相机平移；水平主轴与平顶假设；GT及深度预测不参加拟合',
           'coordinate_units':'approximate meters from camera translation baseline, not surveyed dimensions',
           'source_camera_positions':source['source'],'observations':[{'view':c,'id':NAMES[i],'u_px':u} for c,i,u in OBS],
           'top_candidates_px':TOP,'local_panorama_yaw_offsets_radians':OFFSETS,
           'door_fit_parameters_world':v.tolist(),'bearing_reprojection_residual_px':result.fun.tolist(),
           'bearing_reprojection_rms_px':float(np.sqrt(np.mean(result.fun**2))),
           'bathroom_bounds_xy':bounds['15'],'hall_bounds_xy':bounds['06'],
           'estimated_ceiling_heights_m':ceilings,'common_height':height,
           'door_half_width':float(w/2),'door_depth':float(d),'door_height':float(np.mean(door_heights)),
           'camera':cam_local['07'].tolist(),'all_cameras_local':{k:p.tolist() for k,p in cam_local.items()},
           'side_opening_y':sorted(side_y),'door_points_local':dict(zip(NAMES,[[-w/2,-d/2],[-w/2,d/2],[w/2,d/2],[w/2,-d/2]])),
           'depth_crosscheck':checks,'not_surveyed':['cabinet-hidden end wall','floor plane z=0 approximately','frame molding thickness','door-leaf angle'],
           'checks':['synthetic metric recovery','positive scales','entry inside both envelopes','bearing residual under 15px']}
    # 保存数字只用于可复现；图上不以小数位暗示测量精度。
    (OUT/'doorway_proportion_fit.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2),encoding='utf-8')
    annotate(scene)
    print(json.dumps({k:scene[k] for k in ['bathroom_bounds_xy','hall_bounds_xy','door_depth','door_half_width','estimated_ceiling_heights_m','bearing_reprojection_rms_px','depth_crosscheck']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
