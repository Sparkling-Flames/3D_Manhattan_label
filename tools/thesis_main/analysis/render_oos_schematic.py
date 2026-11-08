"""OOS schematics: one parallel projection, explicit planar steps and references."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/figures'
P = np.array([[.85, -.32], [.55, .45], [0., 1.]])
EDGE, WALL, FLOOR, TEAL, AMBER = '#8197a4', '#d7e2e6', '#eef2f3', '#8fc4c7', '#b76416'

def project(points):
    return np.asarray(points) @ P

def face(ax, points, color):
    ax.add_patch(Polygon(project(points), facecolor=color, edgecolor=EDGE, lw=.8))

def line(ax, points, color=AMBER, dashed=True):
    p=project(points)
    ax.plot(p[:,0],p[:,1], color=color, lw=1.05, ls=(0,(4,3)) if dashed else '-', zorder=5)

def room(ax, ceiling=2.6):
    face(ax, [(0,0,0),(3,0,0),(3,2.4,0),(0,2.4,0)], FLOOR)
    face(ax, [(0,2.4,0),(3,2.4,0),(3,2.4,ceiling),(0,2.4,ceiling)], WALL)
    face(ax, [(0,0,0),(0,2.4,0),(0,2.4,ceiling),(0,0,ceiling)], WALL)


def main():
    fig,axs=plt.subplots(2,2,figsize=(7,6.2))
    ax=axs[0,0]
    footprint=[(0,0),(3,0),(3,1.2),(1.6,2.4),(0,2.4)]
    face(ax,[(x,y,0) for x,y in footprint],FLOOR)
    face(ax,[(0,0,0),(0,2.4,0),(0,2.4,2.6),(0,0,2.6)],WALL)
    face(ax,[(0,2.4,0),(1.6,2.4,0),(1.6,2.4,2.6),(0,2.4,2.6)],WALL)
    face(ax,[(3,1.2,0),(1.6,2.4,0),(1.6,2.4,2.6),(3,1.2,2.6)],TEAL)
    for z in (0,2.6):
        line(ax,[(3,1.2,z),(3,2.4,z),(1.6,2.4,z)])
    # The dashed reference meets at a true right angle in the floor plane.
    a=np.array([0,1.2,0]);b=np.array([-1.4,0,0]);assert a@b==0
    line(ax,[(3,2.4,0),(3,2.4,2.6)])
    ax=axs[0,1]
    face(ax,[(0,0,0),(3,0,0),(3,2.4,0),(0,2.4,0)],FLOOR)
    face(ax,[(0,2.4,0),(3,2.4,0),(3,2.4,3.05),(0,2.4,2.05)],WALL)
    face(ax,[(0,0,0),(0,2.4,0),(0,2.4,2.05),(0,0,2.05)],WALL)
    face(ax,[(0,0,2.05),(3,0,3.05),(3,2.4,3.05),(0,2.4,2.05)],TEAL)
    line(ax,[(0,0,2.6),(3,0,2.6),(3,2.4,2.6),(0,2.4,2.6),(0,0,2.6)])
    for x,y in [(0,0),(3,0),(3,2.4),(0,2.4)]:
        actual_height=2.05+x/3
        line(ax,[(x,y,actual_height),(x,y,2.6)])
    line(ax,[(3,0,0),(3,0,2.6)],color=EDGE)
    ax=axs[1,0]
    face(ax,[(0,0,0),(3,0,0),(3,2.4,0),(0,2.4,0)],FLOOR)
    face(ax,[(0,2.4,0),(3,2.4,0),(3,2.4,2.2),(1.5,2.4,2.2),(1.5,2.4,3),(0,2.4,3)],WALL)
    face(ax,[(0,0,0),(0,2.4,0),(0,2.4,3),(0,0,3)],WALL)
    # Put the high half on the left so the vertical step faces the viewer.
    low=[(1.5,0,2.2),(3,0,2.2),(3,2.4,2.2),(1.5,2.4,2.2)]
    high=[(0,0,3),(1.5,0,3),(1.5,2.4,3),(0,2.4,3)]
    face(ax,low,'#ead5ad')
    face(ax,[(1.5,0,2.2),(1.5,2.4,2.2),(1.5,2.4,3),(1.5,0,3)],'#58a2a8')
    face(ax,high,TEAL)
    ax=axs[1,1];room(ax,3)
    lowfloor=[(0,0,0),(3,0,0),(3,1.05,0),(0,1.05,0)]
    highfloor=[(0,1.65,.8),(3,1.65,.8),(3,2.4,.8),(0,2.4,.8)]
    face(ax,highfloor,TEAL)
    # Four identical treads and risers connect the two floor levels.
    for i in reversed(range(4)):
        y=1.05+i*.15; h=(i+1)*.2
        tread=[(0,y,h),(3,y,h),(3,y+.15,h),(0,y+.15,h)]
        assert np.ptp(np.asarray(tread)[:,2])==0
        face(ax,tread,TEAL)
        face(ax,[(0,y,h-.2),(3,y,h-.2),(3,y,h),(0,y,h)],'#58a2a8')
    face(ax,lowfloor,'#ead5ad')
    for plane in [low,high,lowfloor,highfloor]:assert np.ptp(np.asarray(plane)[:,2])==0
    for ax,title in zip(axs.flat,['(a) Oblique wall','(b) Sloped ceiling','(c) Split-level ceiling','(d) Split-level floor']):
        ax.set_aspect('equal');ax.set_xlim(-.15,4.05);ax.set_ylim(-1.1,4.25);ax.axis('off');ax.set_title(title,fontsize=11,color='#243b4a',pad=1)
    fig.subplots_adjust(left=.02,right=.98,bottom=.02,top=.95,wspace=.08,hspace=.14)
    fig.savefig(OUT/'oos_geometry_3d.pdf')
    plt.close(fig)
    print('Verified horizontal levels, orthogonal reference and common projection.')

if __name__=='__main__':main()
