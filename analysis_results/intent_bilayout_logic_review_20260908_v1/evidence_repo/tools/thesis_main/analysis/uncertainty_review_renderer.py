"""Generate calibration evidence; generation is NOT visual review. No fitting or ring sorting."""
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from shapely.ops import triangulate
from shapely.geometry import Polygon
from audit import lift,project
FONT=ImageFont.load_default(size=15)
def title(im,text):
 out=Image.new('RGB',(im.width,im.height+32),'white');out.paste(im,(0,32));ImageDraw.Draw(out).text((8,7),text,fill='black',font=FONT);return out

def sample(tex,pts):
 a=project(pts);h,w=tex.shape[:2];x=np.mod(np.rint(a[...,0]/1024*w).astype(int),w);y=np.clip(np.rint(a[...,1]/512*h).astype(int),0,h-1);return tex[y,x]
def perspective(tex,yaw,width=480,height=320,fov=80):
 u=np.deg2rad(yaw);f=np.array([np.sin(u),0,-np.cos(u)]);right=np.array([np.cos(u),0,np.sin(u)]);x=(2*(np.arange(width)+.5)/width-1)*np.tan(np.deg2rad(fov/2));y=(1-2*(np.arange(height)+.5)/height)*np.tan(np.deg2rad(fov/2))*height/width;v=f+x[None,:,None]*right+y[:,None,None]*np.array([0,1,0]);return Image.fromarray(sample(tex,v))
def path(draw,xy,color,width=2):
 for i in range(len(xy)-1):
  if abs(xy[i+1,0]-xy[i,0])<512:draw.line([tuple(xy[i]),tuple(xy[i+1])],fill=color,width=width)
def overlay(tex,points,mapped,point_ids=None):
 im=Image.fromarray(tex).resize((1024,512));dr=ImageDraw.Draw(im);p=np.asarray(points,float);mp=list(range(len(p)))
 if mapped:
  f,t,mp=lift(p)
  for ring in [f,t]:
   for i in range(len(ring)):
    z=ring[i][None,:]*(1-np.linspace(0,1,81)[:,None])+ring[(i+1)%len(ring)][None,:]*np.linspace(0,1,81)[:,None];path(dr,project(z),(255,210,0))
  for i in range(len(f)):path(dr,project(np.stack([f[i],t[i]])),(0,255,240))
 else:
  for off in [0,1]:
   r=p[off::2];path(dr,np.vstack([r,r[0]]),(255,100,100))
 for i,(x,y) in enumerate(p):
  dr.ellipse([x-3,y-3,x+3,y+3],fill=(255,255,255),outline=(0,0,0));dr.text((x+4,y+3),str(i if point_ids is None else point_ids[i]),font=FONT,fill=(255,255,255),stroke_width=1,stroke_fill=(0,0,0))
 return im,mp

def surfaces(f,t):
 poly=Polygon(f[:,[0,2]])
 if not poly.is_valid:raise ValueError('invalid_original_footprint_no_mesh')
 tris=[]
 for tr in triangulate(poly):
  if poly.covers(tr):
   xz=np.array(tr.exterior.coords)[:3];q=np.column_stack([xz[:,0],np.full(3,-1.),xz[:,1]]);tris.append(q)
 for i in range(len(f)):
  j=(i+1)%len(f);tris.extend([np.array([f[i],f[j],t[j]]),np.array([f[i],t[j],t[i]])])
 return tris

def render(tex,f,t,top=False,scale=None,size=440):
 tris=surfaces(f,t);q=np.concatenate([f,t]);target=(q.min(axis=0)+q.max(axis=0))/2;eye=target+(np.array([0,6,0.]) if top else np.array([4.,4.,5.]));forward=(target-eye);forward/=np.linalg.norm(forward);up0=np.array([0.,0.,-1.]) if top else np.array([0.,1.,0.]);right=np.cross(forward,up0);right/=np.linalg.norm(right);up=np.cross(right,forward)
 # Fit the projected bounds, including asymmetric rooms, without changing geometry.
 xx=q@right;yy=q@up;target+=((xx.min()+xx.max())/2-target@right)*right+((yy.min()+yy.max())/2-target@up)*up
 s=scale or max(np.ptp(xx),np.ptp(yy),1)*1.25
 color=np.full((size,size,3),238,np.uint8);dep=np.full((size,size),np.inf)
 def screen(p):return np.stack([(p-target)@right/s*size+size/2,size/2-(p-target)@up/s*size,(p-eye)@forward],axis=-1)
 for tr in tris:
  pr=screen(tr);x0=max(0,int(np.floor(pr[:,0].min())));x1=min(size-1,int(np.ceil(pr[:,0].max())));y0=max(0,int(np.floor(pr[:,1].min())));y1=min(size-1,int(np.ceil(pr[:,1].max())))
  if x0>x1 or y0>y1:continue
  xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5);a,b,c=pr;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-10:continue
  w0=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;w1=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w2=1-w0-w1;zz=w0*a[2]+w1*b[2]+w2*c[2];ok=(w0>=-1e-8)&(w1>=-1e-8)&(w2>=-1e-8)&(zz<dep[y0:y1+1,x0:x1+1]);xyz=w0[...,None]*tr[0]+w1[...,None]*tr[1]+w2[...,None]*tr[2];rgb=sample(tex,xyz);color[y0:y1+1,x0:x1+1][ok]=rgb[ok];dep[y0:y1+1,x0:x1+1][ok]=zz[ok]
 im=Image.fromarray(color);dr=ImageDraw.Draw(im)
 for i,p in enumerate(f):
  x,y,_=screen(p);dr.ellipse([x-3,y-3,x+3,y+3],fill=(255,220,0));dr.text((x+4,y+3),f'pair {i}',font=FONT,fill=(0,0,0),stroke_fill=(255,255,255),stroke_width=1)
 return im
