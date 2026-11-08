"""照片和相机基线约束的门洞框架；不使用GT或原答修补几何。"""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/thesis_main/论文写作工作资料/门洞实景观察_20261107'
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'pdf.fonttype': 42, 'axes.unicode_minus': False})
BLUE, SLATE, AMBER, RED = '#397d88', '#657585', '#c17732', '#bb3d37'
SEGMENTS=[]
HEIGHT, DOOR_HEIGHT = 2.65, 2.12
BATH = (-3.9, 1.1, -2.3, -.20)
HALL = (-.80, .80, .20, 5.20)
HALF_DOOR = .575
az, el = np.radians([-62, 30])
PROJ = np.column_stack(([-np.sin(az), np.cos(az), 0],
                       [-np.sin(el)*np.cos(az), -np.sin(el)*np.sin(az), np.cos(el)]))
# 原图中人工定位的同一条水平线，只用来区分平行/横向关系，不估计距离。
TRACES = {
    '浴室护墙线': [[20,601],[128,599],[256,580],[320,560]],
    '浴室顶边': [[30,236],[160,253],[260,291],[340,339]],
    '走廊右饰线': [[1132,391],[1240,300],[1360,244],[1420,229]],
    '走廊左饰线': [[750,176],[830,215],[910,300],[973,400]],
}


def horizontal_direction(points):
    p = np.asarray(points, float)
    lon, lat = 2*np.pi*(p[:,0]/2048-.5), np.pi*(.5-p[:,1]/1024)
    rays = np.column_stack((np.cos(lat)*np.sin(lon), np.cos(lat)*np.cos(lon), np.sin(lat)))
    _, _, basis = np.linalg.svd(rays)
    normal = basis[-1]
    direction = np.array([normal[1], -normal[0]])
    return direction / np.linalg.norm(direction)


def plan(ax):
    for bounds,color in ((BATH,'#eef6f6'),(HALL,'#f1f3f6')):
        x0,x1,y0,y1=bounds
        ax.add_patch(Polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],facecolor=color,edgecolor='none'))
    bx0,bx1,by0,by1=BATH;hx0,hx1,hy0,hy1=HALL
    s0,s1=SCENE['side_opening_y']
    paths = [
        ([[-HALF_DOOR,by1],[bx0,by1],[bx0,by0],[bx1,by0],[bx1,by1],[HALF_DOOR,by1]],BLUE),
        ([[-HALF_DOOR,hy0],[hx0,hy0],[hx0,hy1],[hx1,hy1],[hx1,s1]],SLATE),
        ([[hx1,s0],[hx1,hy0],[HALF_DOOR,hy0]],SLATE),
    ]
    for pts,color in paths:
        p=np.asarray(pts);ax.plot(p[:,0],p[:,1],color=color,lw=2)
    for x in (-HALF_DOOR,HALF_DOOR):
        ax.plot([x,x],[by1,hy0],color=AMBER,lw=5,solid_capstyle='butt')
    ax.scatter(*SCENE['camera'][:2],s=35,color=RED,zorder=6)
    ax.text((bx0+bx1)/2,(by0+by1)/2,f'浴室\n约{bx1-bx0:.1f} × {by1-by0:.1f} m',color=BLUE,fontsize=12,weight='bold',ha='center')
    ax.text((hx0+hx1)/2,(hy0+hy1)/2,f'走廊\n约{hy1-hy0:.1f} × {hx1-hx0:.1f} m',color=SLATE,fontsize=12,weight='bold',ha='center')
    ax.annotate('门洞 / 07相机',xy=SCENE['camera'][:2],xytext=(-2.5,.8),color=RED,fontsize=10,
                arrowprops={'arrowstyle':'-','color':RED,'lw':.8})
    ax.annotate('侧门',xy=(hx1,(s0+s1)/2),xytext=(hx1+.5,(s0+s1)/2),color=SLATE,fontsize=10,
                arrowprops={'arrowstyle':'-','color':SLATE,'lw':.8})
    ax.text(bx0-.05,(by0+by1)/2,'窗',color=BLUE,fontsize=10,ha='right')
    for name,(x,y) in SCENE['door_points_local'].items():
        ax.scatter(x,y,color=AMBER,s=16,zorder=7)
        ax.text(x+(-.12 if name.startswith('L') else .12),y+(-.25 if name.endswith('1') else .18),name,
                fontsize=9,color=AMBER,ha='right' if name.startswith('L') else 'left',va='center')
    ax.text((bx0+bx1)/2,by0-.6,'门洞宽约0.8 m；两面间距约0.1 m\n比例由照片＋相机基线约束',ha='center',va='center',fontsize=10,color='#596b79')
    ax.set(xlim=(bx0-.65,hx1+1.0),ylim=(by0-1,hy1+.5),aspect='equal')
    ax.axis('off')


def direction_evidence():
    # 已知方向的水平直线，先投影再反解，检查方位推导没有交换两个轴。
    for p,axis in ((np.array([[-1,1,.4],[0,1,.4],[1,1,.4]]),[1,0]),
                   (np.array([[-1,1,.4],[-1,2,.4],[-1,3,.4]]),[0,1])):
        uv=np.column_stack(((np.arctan2(p[:,0],p[:,1])/(2*np.pi)+.5)*2048,
                            (.5-np.arctan2(p[:,2],np.hypot(p[:,0],p[:,1]))/np.pi)*1024))
        assert abs(float(horizontal_direction(uv)@axis)) > 1-1e-10
    source=ROOT/'data/mp3d_layout/valid/img/2t7WUuJeko7_53937db036374126830e0f1203b04ead.png'
    directions={name:horizontal_direction(pts) for name,pts in TRACES.items()}
    angles=[]
    for name1 in ('浴室护墙线','浴室顶边'):
        for name2 in ('走廊右饰线','走廊左饰线'):
            cosine=abs(float(directions[name1]@directions[name2]))
            assert cosine < .1
            angles.append(float(np.degrees(np.arccos(np.clip(cosine,0,1)))))
    fig,ax=plt.subplots(figsize=(15,8))
    ax.imshow(Image.open(source))
    for name,pts in TRACES.items():
        p=np.asarray(pts);color=BLUE if name.startswith('浴室') else AMBER
        ax.plot(p[:,0],p[:,1],'o-',color=color,lw=2,ms=5,label=name)
    ax.legend(ncol=4,loc='lower center',bbox_to_anchor=(.5,-.09),frameon=False,fontsize=11)
    ax.set_title('07原图：用可见水平线核对延伸方向',fontsize=17,pad=15)
    ax.axis('off')
    fig.text(.5,.025,'蓝色：浴室墙线；橙色：走廊饰线。仅核对方向，不据此标定尺寸或修订GT。',ha='center',fontsize=11,color='#596b79')
    fig.subplots_adjust(left=.02,right=.98,top=.91,bottom=.11)
    fig.savefig(OUT/'wall_direction_check.png',dpi=160,facecolor='white')
    plt.close(fig)
    return {'source':source.relative_to(ROOT).as_posix(),'manually_read_pixels':TRACES,
            'interpretation':'在原全景水平校准、所取饰线为水平直线的前提下，两组方向接近垂直，支持偏心T形关系；不是精确角度测量。',
            'approximate_cross_angles_degrees':angles}


def project(points):
    return np.asarray(points, dtype=float) @ PROJ


def line(ax, points, color=SLATE, lw=1.3, dashed=False, alpha=1):
    SEGMENTS.append(np.asarray(points,float))
    p = project(points)
    ax.plot(p[:, 0], p[:, 1], color=color, lw=lw,
            ls=(0, (4, 3)) if dashed else '-', alpha=alpha,
            solid_capstyle='round', zorder=4)


def floor(ax, bounds, color):
    x0, x1, y0, y1 = bounds
    p = [(x0,y0,0), (x1,y0,0), (x1,y1,0), (x0,y1,0)]
    ax.add_patch(Polygon(project(p), facecolor=color, edgecolor='none', zorder=0))


def wall(ax, a, b, color, opening=None):
    """墙体线框；opening为沿墙距离起止、开口底高/顶高。"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    length = np.linalg.norm(b-a)
    def point(t, z):
        return [*(a+(b-a)*t/length), z]
    line(ax, [point(0,HEIGHT), point(length,HEIGHT)], color, alpha=.6)
    for t in (0, length):
        line(ax, [point(t,0), point(t,HEIGHT)], color, alpha=.72)
    if opening is None:
        line(ax, [point(0,0), point(length,0)], color)
        return
    s, e, bottom, top = opening
    assert 0 < s < e < length and 0 <= bottom < top < HEIGHT
    if bottom == 0:
        for l, r in ((0,s), (e,length)):
            line(ax, [point(l,0), point(r,0)], color)
    else:
        line(ax, [point(0,0), point(length,0)], color)
        line(ax, [point(s,bottom), point(e,bottom)], color)
    line(ax, [point(s,bottom), point(s,top), point(e,top), point(e,bottom)], color)


def label(ax, text, point, offset, color=SLATE, ha='left'):
    p = project(point)
    ax.annotate(text, xy=p, xytext=p+offset, color=color, fontsize=12, ha=ha, va='center',
                arrowprops={'arrowstyle':'-', 'color':color, 'lw':.8},
                bbox={'boxstyle':'round,pad=.14', 'facecolor':'white', 'edgecolor':'none', 'alpha':.96},
                zorder=10)


def main():
    global BATH,HALL,HEIGHT,DOOR_HEIGHT,HALF_DOOR,SCENE
    SCENE=json.loads((ROOT/'analysis_results/doorway_point_folding_20261107/doorway_proportion_fit.json').read_text(encoding='utf-8'))
    BATH=SCENE['bathroom_bounds_xy'];HALL=SCENE['hall_bounds_xy']
    HEIGHT=SCENE['common_height'];DOOR_HEIGHT=SCENE['door_height'];HALF_DOOR=SCENE['door_half_width']
    bx0,bx1,by0,by1=BATH;hx0,hx1,hy0,hy1=HALL;s0,s1=SCENE['side_opening_y']
    cam=np.array(SCENE['camera'])
    SEGMENTS.clear()
    OUT.mkdir(parents=True, exist_ok=True)
    # shortcut: 两侧估计顶高相差约3cm，图中采用均值；扫描复原时分别采用实测面。
    assert np.allclose(PROJ.T @ PROJ, np.eye(2), atol=1e-12)
    assert BATH[1]-BATH[0] > BATH[3]-BATH[2]
    assert -HALF_DOOR > HALL[0] and HALF_DOOR < HALL[1]
    assert BATH[0] < -HALF_DOOR < HALF_DOOR < BATH[1]
    evidence=direction_evidence()
    fig=plt.figure(figsize=(15.5,8.4))
    plan_ax=fig.add_axes([.025,.12,.30,.72])
    plan(plan_ax)
    ax=fig.add_axes([.345,.12,.64,.72])
    floor(ax, BATH, '#eef6f6')
    floor(ax, HALL, '#f1f3f6')
    floor(ax, (-HALF_DOOR, HALF_DOOR, by1, hy0), '#f5e3ce')

    # 完整浴室：开口位于长墙靠近右端，窗在相反的短墙上。
    wall(ax, (bx0,by0), (bx1,by0), BLUE)
    wall(ax, (bx1,by0), (bx1,by1), BLUE)
    wall(ax, (bx0,by0), (bx0,by1), BLUE, ((by1-by0)*.2,(by1-by0)*.8,1.10,2.20))
    wall(ax, (bx0,by1), (bx1,by1), BLUE, (-bx0-HALF_DOOR,-bx0+HALF_DOOR,0,DOOR_HEIGHT))

    wall(ax, (hx0,hy0), (hx0,hy1), SLATE)
    wall(ax, (hx1,hy0), (hx1,hy1), SLATE, (s0-hy0,s1-hy0,0,DOOR_HEIGHT))
    wall(ax, (hx0,hy1), (hx1,hy1), SLATE, (.14,hx1-hx0-.14,0,2.65))
    line(ax, [(hx0+.14,hy1,2.15),(hx1-.14,hy1,2.15)], SLATE, lw=1)
    wall(ax, (hx0,hy0), (hx1,hy0), SLATE, (-hx0-HALF_DOOR,-hx0+HALF_DOOR,0,DOOR_HEIGHT))

    # 门洞两面及连接侧面；底部保持通行，不画横跨开口的实体墙。
    for y in (by1,hy0):
        line(ax, [(-HALF_DOOR,y,0),(-HALF_DOOR,y,DOOR_HEIGHT),
                  (HALF_DOOR,y,DOOR_HEIGHT),(HALF_DOOR,y,0)], AMBER, lw=2.3)
    for x in (-HALF_DOOR,HALF_DOOR):
        for z in (0,DOOR_HEIGHT):
            line(ax, [(x,by1,z),(x,hy0,z)], AMBER, lw=1.6)
    for name,(x,y) in SCENE['door_points_local'].items():
        xy=project([x,y,.06]);ax.scatter(*xy,s=23,color=AMBER,zorder=9)
        ax.annotate(name,xy=xy,xytext=xy+[-.3 if name.startswith('L') else .35,-.45 if name.endswith('1') else -.18],
                    color=AMBER,fontsize=10,ha='center',arrowprops={'arrowstyle':'-','color':AMBER,'lw':.6},zorder=10)

    # 门扇独立于墙线，向走廊内打开。
    hinge = np.array([-HALF_DOOR,hy0])
    tip = hinge + 2*HALF_DOOR*np.array([np.cos(np.radians(94)),np.sin(np.radians(94))])
    line(ax, [[*hinge,0],[*hinge,DOOR_HEIGHT],[*tip,DOOR_HEIGHT],[*tip,0],[*hinge,0]], '#a4a9ae', lw=1.1)

    # 仅示意通往右侧房间，未知的房间远侧不封闭。
    for y in (s0,s1):
        for z in (0,DOOR_HEIGHT):
            line(ax, [(hx1,y,z),(hx1+1.,y,z)], '#b5bec5', lw=1, dashed=True)
    center=project(cam)
    ax.scatter(*center, s=57, c=RED, edgecolor='white', linewidth=1.3, zorder=12)
    line(ax, [(*cam[:2],0),cam], RED, lw=.9, dashed=True, alpha=.5)
    floorpoint=project([*cam[:2],0])
    ax.scatter(*floorpoint,s=14,facecolor='white',edgecolor=RED,zorder=10)

    for text, point, color in [('浴室',[(bx0+bx1)/2,(by0+by1)/2,.02],BLUE),('走廊',[(hx0+hx1)/2,(hy0+hy1)/2,.02],SLATE)]:
        xy=project(point)
        ax.text(*xy,text,color=color,fontsize=17,weight='bold',ha='center',va='center',zorder=8,
                bbox={'facecolor':'white','edgecolor':'none','pad':2,'alpha':.8})
    label(ax,'窗',[bx0,(by0+by1)/2,1.7],[-.5,.20],BLUE,ha='right')
    label(ax,'近侧长墙由同房照片补充',[(bx0+bx1)/2,by1,HEIGHT],[-.4,.5],BLUE,ha='center')
    label(ax,'R1：补回右侧固定转折',[HALF_DOOR,by1,DOOR_HEIGHT],[1.15,.65],AMBER,ha='left')
    label(ax,'07 相机',cam,[1.2,.05],RED)
    label(ax,'打开的门扇', [*tip,1.2],[-.9,-.35],'#7b858c',ha='right')
    label(ax,'走廊尽头的门',[(hx0+hx1)/2,hy1,2.65],[.20,.5])
    label(ax,'另一房间入口',[hx1+.8,(s0+s1)/2,1.0],[.5,.05])
    ax.set_aspect('equal')
    ax.set_xlim(-4.5,3.8)
    ax.set_ylim(-1.6,5.4)
    ax.axis('off')
    fig.suptitle('门洞两侧的空间关系：照片与相机位置约束的比例草稿',fontsize=19,weight='bold',color='#263b49',y=.965)
    fig.text(.18,.872,'(a) 俯视关系',ha='center',fontsize=13,color='#596b79')
    fig.text(.665,.872,'(b) 同一构造的三维框架',ha='center',fontsize=13,color='#596b79')
    fig.text(.5,.035,'L1/R1：浴室侧转折；L2/R2：内侧门框边。尺寸为多视角近似恢复；柜后端墙、装饰厚度和门扇角仍未定准。',
             ha='center',fontsize=11,color='#677783')
    fig.savefig(OUT/'room_framework.png',dpi=180,facecolor='white')
    fig.savefig(OUT/'room_framework.svg',facecolor='white')
    plt.close(fig)
    obj=['# Approximate metric candidate; Z up; +Y toward hall; NOT surveyed GT',
         '# Blender import: forward -Y, up Z; includes schematic window/leaf and side-entry guides']
    offset=1
    for points in SEGMENTS:
        obj.extend('v '+' '.join(f'{c:.8f}' for c in point) for point in points)
        obj.append('l '+' '.join(str(offset+i) for i in range(len(points))))
        offset+=len(points)
    (ROOT/'analysis_results/doorway_point_folding_20261107/doorway_framework_metric_candidate.obj').write_text('\n'.join(obj)+'\n',encoding='utf-8')
    (OUT/'framework_geometry.json').write_text(json.dumps({**SCENE,'orientation_evidence':evidence},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Framework PNG/SVG saved; projection and opening checks passed.')


if __name__ == '__main__':
    main()
