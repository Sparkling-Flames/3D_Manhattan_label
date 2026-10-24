"""Draw explicit synthetic boundary surfaces; no photographs, GT or research scores."""
from pathlib import Path
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/oos_statistics_20261024/figures'
FONT = Path('C:/Windows/Fonts/msyh.ttc')
INK, EDGE, TEAL, AMBER = '#243b4a', '#8294a0', '#087f8c', '#b76416'
DOORWAY_BLOCKS = [(2.3,3,0,2.8),(.7,2.3,2,2.8),(0,.7,0,2.8)]
TITLES = {
    'standard': ('a', '标准构造参照', '正交墙面；单一水平顶面与地面'),
    'oblique_wall': ('b', '斜墙', '斜段不沿同一组正交方向；角度不指定'),
    'sloped_ceiling': ('c', '斜顶', '同一片顶面连续改变高度'),
    'stepped_ceiling': ('d', '多层天花板', '不同区域的顶面高度不同'),
    'stepped_floor': ('e', '多层地面', '地面经台阶连接到较高平台'),
    'curved_wall': ('f', '曲面／连续折面', '边界持续转向；不等同于全景投影弯曲'),
}


def project(points):
    """One orthographic axonometric projection for every surface and callout."""
    p = np.asarray(points, dtype=float)
    return np.column_stack((.92*p[:, 0]-.55*p[:, 1], .30*p[:, 0]+.48*p[:, 1]+p[:, 2]))


def scene(kind):
    """Ordered visible boundary surfaces: the near walls are intentionally removed."""
    floor = [(0,0), (4,0), (4,3), (0,3)]
    if kind == 'oblique_wall':
        floor = [(0,0), (2,0), (4,1.2), (4,3), (0,3)]
    if kind == 'curved_wall':
        arc = [(2+2*math.cos(t), 1.2+1.2*math.sin(t))
               for t in np.linspace(-math.pi/2, 0, 30)]
        floor = [(0,0), *arc, (4,3), (0,3)]
    def height(x):
        if kind == 'sloped_ceiling': return 2.05+.24*x
        if kind == 'stepped_ceiling': return 2.95 if x < 2 else 2.05
        return 3.35 if kind == 'stepped_floor' else 2.65
    surfaces = []
    def add(label, vertices, color, alpha=1):
        surfaces.append(dict(label=label, vertices=vertices, color=color, alpha=alpha))
    if kind != 'stepped_floor':
        add('floor', [(x,y,0) for x,y in floor], '#e9eff1')
    back_top = [(4,3,height(4)), (0,3,height(0))]
    if kind == 'stepped_ceiling':
        back_top = [(4,3,2.05), (2,3,2.05), (2,3,2.95), (0,3,2.95)]
    add('back wall', [(0,3,0), (4,3,0), *back_top], '#d6e0e5')
    add('side wall', [(4,0,0),(4,3,0),(4,3,height(4)),(4,0,height(4))], '#c1d0d8')
    if kind == 'stepped_floor':
        surfaces[0]['vertices'] = [(0,3,0),(1.2,3,0),(1.2,3,.3),(1.5,3,.3),
            (1.5,3,.6),(1.8,3,.6),(1.8,3,.9),(2.1,3,.9),(2.1,3,1.2),
            (4,3,1.2),(4,3,3.35),(0,3,3.35)]
        surfaces[1]['vertices'] = [(4,0,1.2),(4,3,1.2),(4,3,3.35),(4,0,3.35)]
    if kind in ('oblique_wall','curved_wall'):
        # The right wall begins after the chamfer/arc, not at the missing corner.
        surfaces[-1]['vertices'] = [(4,1.2,0),(4,3,0),(4,3,2.65),(4,1.2,2.65)]
        if kind == 'oblique_wall':
            add('oblique wall', [(2,0,0),(4,1.2,0),(4,1.2,2.65),(2,0,2.65)], '#54a9ad')
        else:
            for a,b in reversed(list(zip(arc[:-1],arc[1:]))):
                shade = (a[0]-2)/2
                color = matplotlib.colors.to_hex((.19+.19*shade,.55+.13*shade,.59+.12*shade))
                add('curved wall', [(*a,0),(*b,0),(*b,2.65),(*a,2.65)], color)
    if kind == 'stepped_floor':
        # Fill the floor in depth order; these are treads and risers, not ramps.
        bounds, levels = [0,1.2,1.5,1.8,2.1,4], [0,.3,.6,.9,1.2]
        for i in reversed(range(5)):
            a,b,z = bounds[i],bounds[i+1],levels[i]
            add('floor level', [(a,0,z),(b,0,z),(b,3,z),(a,3,z)], '#83bfc0' if i else '#e9eff1')
            if i:
                low=levels[i-1]
                add('riser', [(a,0,low),(a,3,low),(a,3,z),(a,0,z)], '#3c9199')
    if kind == 'stepped_ceiling':
        add('high ceiling', [(0,0,2.95),(2,0,2.95),(2,3,2.95),(0,3,2.95)], '#92c5c5', .63)
        add('ceiling step', [(2,0,2.05),(2,3,2.05),(2,3,2.95),(2,0,2.95)], '#3b939a', .85)
        add('low ceiling', [(2,0,2.05),(4,0,2.05),(4,3,2.05),(2,3,2.05)], '#b5d7d6', .52)
    elif kind != 'stepped_floor':
        add('ceiling', [(x,y,height(x)) for x,y in floor], '#a1cbce', .25 if kind != 'sloped_ceiling' else .6)
    return surfaces


def line(ax, points, color=EDGE, lw=1, dashed=False, **kwargs):
    xy=project(points)
    ax.plot(xy[:,0],xy[:,1], color=color, lw=lw, ls=(0,(4,3)) if dashed else '-', **kwargs)


def callout(ax, text, point, label, size):
    xy=project([point])[0]
    ax.annotate(text, xy, xytext=label, fontsize=size, color=INK, zorder=30,
                ha='left' if label[0]>xy[0] else 'right', va='center',
                arrowprops=dict(arrowstyle='-', color=INK, lw=.7,
                                connectionstyle='angle,angleA=0,angleB=60,rad=0'),
                bbox=dict(facecolor='white', edgecolor='none', pad=1.2, alpha=.94))


def draw(ax, kind, size=10):
    for s in scene(kind):
        curved=s['label']=='curved wall'
        ax.add_patch(Polygon(project(s['vertices']), facecolor=s['color'], alpha=s['alpha'], antialiased=not curved,
                             edgecolor='none' if curved else EDGE, lw=.8, closed=True))
    near_top={'sloped_ceiling':2.05,'stepped_ceiling':2.95,'stepped_floor':3.35}.get(kind,2.65)
    line(ax,[(0,0,0),(0,0,near_top)],EDGE,.9,True,gid=f'{kind}-omitted-front-corner')
    if kind == 'standard':
        line(ax, [(0,0,0),(4,0,0),(4,3,0)], TEAL,1.4)
        line(ax, [(0,0,2.65),(4,0,2.65),(4,3,2.65),(0,3,2.65),(0,0,2.65)], TEAL,1.4)
        callout(ax,'水平顶面',(1.8,1.5,2.65),(.3,6.2),size)
        callout(ax,'水平地面',(1.3,.5,0),(-1.2,-.22),size)
    elif kind == 'oblique_wall':
        line(ax, [(2,0,2.65),(4,0,2.65),(4,1.2,2.65)], AMBER,1.6,True)
        line(ax, [(2,0,0),(4,0,0),(4,1.2,0)], AMBER,1.6,True)
        callout(ax,'斜墙面',(3,.6,1.5),(4.05,2.9),size)
        callout(ax,'正交近似',(4,0,2.65),(4.05,5.4),size)
    elif kind == 'sloped_ceiling':
        line(ax, [(0,0,2.53),(4,0,2.53),(4,3,2.53)], AMBER,1.6,True)
        line(ax, [(0,0,2.05),(4,0,3.01)], TEAL,2)
        callout(ax,'倾斜顶面',(2.3,1.8,2.602),(.2,6.4),size)
        callout(ax,'单一水平顶面近似',(3.5,0,2.53),(3.9,4.8),size-1)
    elif kind == 'stepped_ceiling':
        line(ax, [(0,0,2.5),(4,0,2.5)], AMBER,1.6,True)
        callout(ax,'较高顶面',(.6,2,2.95),(-1.5,6.3),size)
        callout(ax,'较低顶面',(3,1.3,2.05),(4,4.8),size)
    elif kind == 'stepped_floor':
        line(ax, [(0,0,3.35),(4,0,3.35),(4,3,3.35),(0,3,3.35),(0,0,3.35)], EDGE,.9,True)
        callout(ax,'较高平台',(3.1,1.4,1.2),(4.05,3.6),size)
        callout(ax,'台阶连接',(1.6,.2,.6),(-.8,-.2),size)
        ax.text(-2.9,5.7,'顶面仅画轮廓',fontsize=size-1,color=EDGE)
    elif kind == 'curved_wall':
        t=np.linspace(-math.pi/2,0,60)
        arc=[(2+2*math.cos(a),1.2+1.2*math.sin(a)) for a in t]
        for z in [0,2.65]: line(ax,[(*p,z) for p in arc],TEAL,1.5)
        for p in [arc[0],arc[-1]]:line(ax,[(*p,0),(*p,2.65)],TEAL,1.1)
        callout(ax,'持续转向的墙面',(2+math.sqrt(2),1.2-1.2/math.sqrt(2),1.3),(4.05,2.8),size)
        ax.text(-2.8,-.4,'折面也可能持续转向；此处以曲面示意',fontsize=size-1,color=INK)
    ax.set(xlim=(-3.2,6.2),ylim=(-.65,6.8),aspect='equal')
    ax.axis('off')


def save(fig, stem):
    for ext in ['svg','pdf','png']:
        fig.savefig(OUT/f'{stem}.{ext}',dpi=300,facecolor='white')
    plt.close(fig)


def doorway():
    fig=plt.figure(figsize=(9,6.4))
    ax=fig.add_axes([.03,.16,.94,.72])
    layer=0
    def face(vertices,color,alpha=1):
        nonlocal layer
        layer+=1
        ax.add_patch(Polygon(project(vertices),facecolor=color,edgecolor=EDGE,lw=.8,alpha=alpha,zorder=layer))
    face([(0,0,0),(3,0,0),(3,3,0),(0,3,0)],'#d0e7e5')
    face([(3,0,0),(6,0,0),(6,3,0),(3,3,0)],'#eff2f3')
    face([(0,3,0),(6,3,0),(6,3,2.8),(0,3,2.8)],'#d6e0e5')
    face([(6,0,0),(6,3,0),(6,3,2.8),(6,0,2.8)],'#bdcdd6')
    line(ax,[(3,1.45,1.15),(4.8,1.45,1.15)],'#b34c45',1.7,True,zorder=4.5)
    # Three non-overlapping wall solids around the open doorway.
    for y0,y1,z0,z1 in DOORWAY_BLOCKS:
        color='#83b4bc' if z0==2 else '#b6cbd3'
        face([(3,y0,z0),(3.2,y0,z0),(3.2,y0,z1),(3,y0,z1)],'#7197a6')
        face([(3,y0,z0),(3,y1,z0),(3,y1,z1),(3,y0,z1)],color)
        face([(3,y0,z1),(3.2,y0,z1),(3.2,y1,z1),(3,y1,z1)],'#c4d8dd')
    line(ax,[(1.25,1.45,1.15),(3,1.45,1.15)],TEAL,2,zorder=13.5)
    closure=[(3,.7,0),(3,2.3,0),(3,2.3,2),(3,.7,2),(3,.7,0)]
    face(closure[:-1],'#edbd7f',.22)
    line(ax,closure,AMBER,1.5,True,zorder=15)
    line(ax,[(0,0,2.8),(6,0,2.8),(6,3,2.8),(0,3,2.8),(0,0,2.8)],EDGE,.8,True,zorder=15)
    line(ax,[(0,0,0),(0,0,2.8)],EDGE,.9,True,zorder=15,gid='doorway-omitted-front-corner')
    projection=project([(1.25,1.45,0),(1.25,1.45,1.15)])
    ax.plot(projection[:,0],projection[:,1],color=EDGE,lw=.8,ls=':',zorder=15)
    c=project([(1.25,1.45,1.15)])[0]
    ax.plot(*c,'o',ms=8,color=TEAL,mec='white',mew=1.5,zorder=30)
    callout(ax,'相机拍摄点位',(1.25,1.45,1.15),(-1.8,2.2),11)
    callout(ax,'门洞上方实体',(3,1.5,2.4),(1.6,6.45),11)
    callout(ax,'封闭面：目标定义',(3,1.4,.45),(4.3,.75),11)
    for name,p in [('目标：左室',(.25,1.8,0)),('相邻房间',(4.6,.65,0))]:
        xy=project([p])[0];ax.text(*xy,name,fontsize=11,ha='center',color=INK,zorder=30,
            bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=2))
    ax.set(xlim=(-3.3,7.2),ylim=(-.6,6.9),aspect='equal');ax.axis('off')
    fig.text(.05,.945,'门洞交界：房间、拍摄点位与封闭边界',fontsize=18,color=INK,weight='bold')
    fig.text(.05,.895,'灰虚线：省略的前墙与顶面轮廓；相机下方点线：向地面的垂直投影。',fontsize=10,color=EDGE)
    fig.legend([Line2D([0],[0],color=TEAL,lw=2),Line2D([0],[0],color='#b34c45',lw=1.5,ls='--'),
                Line2D([0],[0],color=AMBER,lw=1.5,ls='--')],
               ['左室内的方向段','越出左室的方向段','人为封闭面：不是实体墙'],
               loc='lower left',bbox_to_anchor=(.04,.07),frameon=False,ncol=3,fontsize=9)
    fig.text(.05,.045,'门洞上方实体的底面低于房间顶界，并不自动构成 OOS；先确定标注目标。',fontsize=10,color=INK)
    fig.text(.05,.016,'合成构造示意 · 非实测、非 GT；不据此推断任何照片中相机的实际位置。',fontsize=8.5,color=EDGE)
    save(fig,'DOORWAY_spatial_boundary')


def build():
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=FONT).get_name(),
                         'svg.fonttype':'path','pdf.fonttype':42,'axes.unicode_minus':False})
    OUT.mkdir(parents=True,exist_ok=True)
    for kind,(letter,title,meaning) in TITLES.items():
        fig=plt.figure(figsize=(6.8,5.5))
        ax=fig.add_axes([.03,.13,.94,.75]);draw(ax,kind,12)
        fig.text(.055,.94,f'{letter}  {title}',fontsize=17,color=INK,weight='bold')
        fig.text(.055,.055,meaning,fontsize=11,color=INK)
        fig.text(.055,.018,'合成示意 · 非 GT；前墙移去、顶面半透明；灰虚线为省略轮廓',fontsize=8.3,color=EDGE)
        save(fig,f'OOS_{kind}')
    fig=plt.figure(figsize=(10,13.1))
    for i,(kind,(letter,title,meaning)) in enumerate(TITLES.items()):
        col,row=i%2,i//2
        x,y=.04+col*.49,.675-row*.302
        fig.text(x,y+.245,f'{letter}  {title}',fontsize=13,color=INK,weight='bold')
        ax=fig.add_axes([x-.01,y+.012,.48,.235]);draw(ax,kind,9.5)
        fig.text(x,y-.004,meaning,fontsize=8.4,color=INK)
    fig.text(.04,.971,'标注标准与真实构造的差异',fontsize=20,color=INK,weight='bold')
    fig.text(.04,.945,'统一轴测视角；前墙移去、顶面半透明；灰虚线补足省略轮廓。',fontsize=10,color=INK)
    fig.legend([Line2D([0],[0],color=TEAL,lw=2),Line2D([0],[0],color=AMBER,lw=1.7,ls='--')],
               ['需要关注的真实构造（示意）','为满足约束所作的一种近似（非实际 GT）'],
               loc='lower left',bbox_to_anchor=(.03,.017),frameon=False,ncol=2,fontsize=9)
    fig.text(.04,.012,'所有尺寸仅用于构造图例；不据此重新判定任何真实图片的类别或评分资格。',fontsize=8.2,color=EDGE)
    save(fig,'OOS_construction_plate')
    doorway()


if __name__ == '__main__':
    build()
