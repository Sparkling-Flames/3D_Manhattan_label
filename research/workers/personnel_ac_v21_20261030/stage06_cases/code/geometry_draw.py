#!/usr/bin/env python3
"""Scientific ERP/BEV/3D and vote figures from exact frozen v2.1 ABC traces.
No fitting, scoring, ring repair or target rerouting is performed. Geometry is
camera-height normalized. Original source annotations are displayed in full.
"""
from __future__ import annotations
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_case_mpl')
import argparse,csv,gzip,json,math,io
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib import patheffects
from PIL import Image
from scipy.optimize import linear_sum_assignment

HERE=Path(__file__).resolve().parents[1]
COLORS={'A':'#2471a3','B':'#168c80','C':'#d95f28'}
FONT=HERE/'source/NotoSansCJKsc-Regular.otf'
if FONT.exists():
 font_manager.fontManager.addfont(str(FONT));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})

def read(path):
 with (gzip.open(path,'rt',encoding='utf-8-sig') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as f:return json.load(f)
def save_csv(path,df):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.writing');df.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(path)
def save_figure(fig,path,**kwargs):
 buf=io.BytesIO();fig.savefig(buf,format=path.suffix.lstrip('.'),**kwargs);tmp=path.with_name(path.name+'.writing')
 with tmp.open('wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
 tmp.replace(path)
def number(v,d=2):return '不可评' if v is None or (isinstance(v,float) and not np.isfinite(v)) else f'{float(v):.{d}f}'
def points3d(points):
 p=np.asarray(points,float)
 if p.ndim!=2 or len(p)<6 or len(p)%2:return None
 u=p[1::2,0]*2*np.pi/1024;vf=(p[1::2,1]/512-.5)*np.pi
 if np.any(vf<=0) or np.any(vf>=np.pi/2):return None
 r=1/np.tan(vf);x=-np.sin(u)*r;z=np.cos(u)*r
 ytop=r*np.tan((.5-p[::2,1]/512)*np.pi)
 bottom=np.column_stack([x,z,np.full(len(x),-1.)]);top=np.column_stack([x,z,ytop])
 return top,bottom

def great_arc(p,q,n=50):
 # Directions along the 3D edge's great circle. Split ERP seam explicitly.
 def ray(p):
  u,v=p[0]*2*np.pi/1024,(.5-p[1]/512)*np.pi
  return np.array([-np.sin(u)*np.cos(v),np.cos(u)*np.cos(v),np.sin(v)])
 a,b=ray(p),ray(q);angle=np.arccos(np.clip(a@b,-1,1));t=np.linspace(0,1,n)
 if angle<1e-8:r=(1-t[:,None])*a+t[:,None]*b
 elif abs(np.sin(angle))<1e-8:return [np.array([p,q])]
 else:r=np.sin((1-t)*angle)[:,None]/np.sin(angle)*a+np.sin(t*angle)[:,None]/np.sin(angle)*b
 r=r/np.linalg.norm(r,axis=1)[:,None]
 x=np.mod(np.arctan2(-r[:,0],r[:,1]),2*np.pi)*1024/(2*np.pi)
 y=(.5-np.arcsin(np.clip(r[:,2],-1,1))/np.pi)*512
 xy=np.column_stack([x,y]);cuts=np.where(abs(np.diff(x))>512)[0]+1
 return [a for a in np.split(xy,cuts) if len(a)>1]

def erp(ax,points,color,lw,alpha,linestyle='-'):
 if not points:return
 p=np.asarray(points,float)
 if len(p)%2:return
 seg=[]
 for k in (0,1):
  ring=p[k::2]
  for i in range(len(ring)):seg.extend(great_arc(ring[i],ring[(i+1)%len(ring)]))
 for t,b in zip(p[::2],p[1::2]):seg.extend(great_arc(t,b,15))
 artist=LineCollection(seg,colors=color,linewidths=lw,alpha=alpha,linestyles=linestyle)
 if lw>=1.5:artist.set_path_effects([patheffects.Stroke(linewidth=lw+1.1,foreground='white',alpha=.65),patheffects.Normal()])
 ax.add_collection(artist)

def bev(ax,points,color,lw,alpha,linestyle='-',dots=False):
 xyz=points3d(points)
 if xyz is None:return
 floor=xyz[1][:,:2];closed=np.vstack([floor,floor[0]])
 ax.plot(closed[:,0],closed[:,1],color=color,lw=lw,alpha=alpha,ls=linestyle)
 if dots:ax.scatter(floor[:,0],floor[:,1],s=12,c=color,alpha=alpha,zorder=6)

def xyz_plot(ax,points,color,lw,alpha,linestyle='-'):
 xyz=points3d(points)
 if xyz is None:return
 top,bottom=xyz
 for ring in (top,bottom):
  a=np.vstack([ring,ring[0]]);ax.plot(a[:,0],a[:,1],a[:,2],color=color,lw=lw,alpha=alpha,ls=linestyle)
 for t,b in zip(top,bottom):a=np.stack([t,b]);ax.plot(a[:,0],a[:,1],a[:,2],color=color,lw=lw,alpha=alpha,ls=linestyle)
