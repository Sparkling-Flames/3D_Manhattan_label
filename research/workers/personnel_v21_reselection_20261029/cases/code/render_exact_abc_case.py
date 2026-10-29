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

def votes(case):
 e=case['event'];pool=case['pool'];own={r['object_id']:r['worker_id'] for r in pool['records']};reference=np.asarray(case['reference']['points_1024x512'],float)
 D=set(e['D'].split('|')) if e['D'] else set();out=[]
 for arm in 'ABC':
  row=case['arms'][arm];groups=(row.get('full_state')or{}).get('identity_groups',[])
  for g in groups:
   who=[m.get('worker') or own.get(m.get('id'),'unknown') for m in g.get('members',[])]
   points=np.asarray(g.get('center'),float);az=points[1,0] if points.shape==(2,2) else np.nan
   delta=abs((reference[1::2,0]-az+512)%1024-512)*360/1024
   ri=int(np.argmin(delta)) if np.isfinite(az) else -1
   out.append(dict(event_id=e['event_id'],arm=arm,feature_id=g.get('feature_id'),support=g.get('support'),selected=g.get('selected'),
    minimum_support=row.get('minimum_support'),D_support=len(set(who)&D),replacement_support=len(set(who)-D),
    workers='|'.join(sorted(set(who))),center_json=json.dumps(g.get('center'),separators=(',',':')),azimuth_px=az,
    nearest_reference_node_1based=ri+1 if ri>=0 else None,nearest_reference_azimuth_deg=float(delta[ri]) if ri>=0 else None,
    raw_observation_signature='|'.join(sorted(str(m.get('id'))+':'+str(m.get('source_pair_index')) for m in g.get('members',[]))),
    D_observation_signature='|'.join(sorted(str(m.get('id'))+':'+str(m.get('source_pair_index')) for m in g.get('members',[]) if (m.get('worker') or own.get(m.get('id'))) in D))))
 return pd.DataFrame(out)

def common_background_links(v):
 out=[]
 if v.empty:return pd.DataFrame()
 for arm in ['B','C']:
  for a in v[v.arm=='A'].itertuples():
   sa=set(a.D_observation_signature.split('|'))-{''}
   for b in v[v.arm==arm].itertuples():
    sb=set(b.D_observation_signature.split('|'))-{''};overlap=len(sa&sb)
    if overlap:
     out.append(dict(event_id=a.event_id,other_arm=arm,A_feature=a.feature_id,other_feature=b.feature_id,
      common_D_observations=overlap,A_D_observations=len(sa),other_D_observations=len(sb),exact_same_D_signature=sa==sb,
      A_support=a.support,other_support=b.support,A_selected=a.selected,other_selected=b.selected))
 return pd.DataFrame(out)

def render(path,out,originals):
 case=read(path);e=case['event'];pool=case['pool'];arms=case['arms'];ref=case['reference']['points_1024x512'];image=pool['meta']['image']
 pic=originals/(image+'.png');assert pic.exists(),pic
 im=Image.open(pic).convert('RGB');canvas=np.asarray(im.resize((1024,512),Image.Resampling.LANCZOS))
 out=out/e['event_id'];out.mkdir(parents=True,exist_ok=True)
 members={r['worker_id']:r for r in pool['records']};D=e['D'].split('|') if e['D'] else [];block={'A':e['X'].split('|'),'B':e['Y'].split('|'),'C':e['Z'].split('|')}
 fig,axs=plt.subplots(2,3,figsize=(18,9.1),gridspec_kw={'height_ratios':[1.05,1.]})
 allpoints=[ref]+[(r.get('geometry')or{}).get('points') for r in arms.values()]
 rawpoints=[members[w]['points'] for w in sorted(set(D+sum(block.values(),[])))]
 floors=[points3d(p)[1] for p in allpoints+rawpoints if p and points3d(p)is not None]
 xyzvalues=[np.vstack(points3d(p)) for p in allpoints if p and points3d(p)is not None]
 zlow=min(float(v[:,2].min()) for v in xyzvalues) if xyzvalues else -1.
 zhigh=max(float(v[:,2].max()) for v in xyzvalues) if xyzvalues else 1.
 zpad=.12*max(zhigh-zlow,1.)
 outputxy=np.concatenate(xyzvalues)[:,:2] if xyzvalues else np.array([[-2,-2],[2,2]])
 lo3,hi3=outputxy.min(0),outputxy.max(0);pad3=.15*max(max(hi3-lo3),1.)
 xy=np.concatenate(floors)[:,:2] if floors else np.array([[-2,-2],[2,2]]);lo=xy.min(0);hi=xy.max(0);span=np.maximum(hi-lo,1);pad=.15*max(span)
 for i,arm in enumerate('ABC'):
  color=COLORS[arm];row=arms[arm];p=(row.get('geometry')or{}).get('points');title={'A':'A 原队：D＋X','B':'B 同类换人：D＋Y','C':'C 跨类换人：D＋Z'}[arm]
  ax=axs[0,i];ax.imshow(canvas,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0)
  for w in D:erp(ax,members[w]['points'],'white',.45,.10)
  for w in block[arm]:erp(ax,members[w]['points'],color,.8,.40)
  erp(ax,ref,'#111111',1.55,.95,'--');erp(ax,p,color,2.0,1.);ax.set_title(title+'\nQ='+number(row.get('B8L2'))+'  D10='+number(row.get('D10'))+'  入选节点='+str(row.get('nodes')),fontsize=12)
  if not p:ax.text(.5,.06,'未形成完整融合环',transform=ax.transAxes,ha='center',color='#a52a2a',fontsize=12,bbox=dict(facecolor='white',alpha=.88,edgecolor='none'))
  ax.set_xlabel('ERP 水平像素');ax.set_ylabel('ERP 竖直像素')
  ax=axs[1,i]
  for w in D:bev(ax,members[w]['points'],'#999999',.5,.08)
  for w in block[arm]:bev(ax,members[w]['points'],color,.7,.22)
  bev(ax,ref,'#111111',1.8,.95,'--',True);bev(ax,p,color,2.5,1.,dots=True)
  ax.plot(0,0,'k+',ms=8);ax.set_aspect('equal',adjustable='box');ax.set_xlim(lo[0]-pad,hi[0]+pad);ax.set_ylim(lo[1]-pad,hi[1]+pad)
  ax.set_xlabel('x / 相机高');ax.set_ylabel('z / 相机高');ax.grid(alpha=.15)
  ax.set_title('底面：完整原答细线；融合粗线\n'+('融合不可评：'+str(row.get('score_status')) if row.get('B8L2')is None else '门槛 '+str(row.get('minimum_support'))+'  原答块：'+', '.join(block[arm])),fontsize=9)
 handles=[Line2D([0],[0],color='#111111',ls='--',lw=1.7,label='当前目标参考'),Line2D([0],[0],color='#666666',lw=.8,alpha=.4,label='原答完整边界'),Line2D([0],[0],color=COLORS['C'],lw=2.5,label='融合完整边界')]
 fig.legend(handles=handles,loc='lower center',ncol=3,bbox_to_anchor=(.5,.01),frameon=False)
 fig.suptitle(f"{image}  |  {e['method']}  |  Manual  |  n={e['n']}，m={e['m']}\n同一合法目标；参考版本：{pool['meta'].get('reference_version','v2.1')}（完整目标身份见配套表）",fontsize=13,y=.995)
 fig.tight_layout(rect=[0,.055,1,.965],h_pad=2.6);save_figure(fig,out/'ERP_BEV.png',dpi=160);save_figure(fig,out/'ERP_BEV.pdf');plt.close(fig)
 v=votes(case);save_csv(out/'VOTE_GROUPS_WITH_BLOCKS.csv',v);save_csv(out/'COMMON_D_GROUP_LINKS.csv',common_background_links(v))
 fig=plt.figure(figsize=(18,9.5));gs=fig.add_gridspec(2,3,height_ratios=[1.2,1.],hspace=.32,wspace=.22)
 for i,arm in enumerate('ABC'):
  row=arms[arm];p=(row.get('geometry')or{}).get('points');color=COLORS[arm]
  ax=fig.add_subplot(gs[0,i],projection='3d');xyz_plot(ax,ref,'#111111',1.1,.8,'--');xyz_plot(ax,p,color,2.0,1.)
  if not p:
   selected=[g['center'] for g in (row.get('full_state')or{}).get('identity_groups',[]) if g.get('selected')]
   xyz=points3d(np.concatenate(selected).tolist()) if len(selected)>=3 else None
   if xyz is not None:
    top,bottom=xyz
    for point in [top,bottom]:ax.scatter(point[:,0],point[:,1],point[:,2],c=color,s=24)
    for t,b in zip(top,bottom):segment=np.stack([t,b]);ax.plot(segment[:,0],segment[:,1],segment[:,2],color=color,lw=1.,alpha=.6)
   ax.text2D(.02,.96,'未形成完整环；仅画入选点，未补连边',transform=ax.transAxes,color='#a52a2a',fontsize=10)
  ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.set_zlabel('y / h');ax.set_title(arm+' 三维代理：地面固定 −1h',fontsize=12);ax.view_init(elev=24,azim=-54)
  if floors:
   ax.set_xlim(lo3[0]-pad3,hi3[0]+pad3);ax.set_ylim(lo3[1]-pad3,hi3[1]+pad3)
  ax.set_zlim(zlow-zpad,zhigh+zpad)
  ax.set_box_aspect((max(hi3[0]-lo3[0]+2*pad3,.1),max(hi3[1]-lo3[1]+2*pad3,.1),max(zhigh-zlow+2*zpad,.1)))
  ax=fig.add_subplot(gs[1,i]);vv=v[v.arm.eq(arm)].sort_values('azimuth_px') if not v.empty else pd.DataFrame()
  if len(vv):
   xx=np.arange(len(vv));alpha=np.where(vv.selected,.94,.25)
   for pos,rr in zip(xx,vv.itertuples()):
    al=.94 if rr.selected else .25
    ax.bar(pos,rr.D_support,color='#8b97a4',alpha=al,width=.75)
    ax.bar(pos,rr.replacement_support,bottom=rr.D_support,color=color,alpha=al,width=.75)
    ax.text(pos,rr.support+.13,str(int(rr.support)),ha='center',va='bottom',fontsize=8)
   ax.axhline(row['minimum_support'],color='#b72d33',ls='--',lw=1.4,label='实际门槛')
   labels=[str(r.feature_id).replace('node_','g')+(f'\nr{int(r.nearest_reference_node_1based)}' if r.nearest_reference_azimuth_deg<=9 else '\n无9°近邻') for r in vv.itertuples()]
   ax.set_xticks(xx,labels,fontsize=7,rotation=0);ax.set_ylim(0,max(vv.support.max(),row['minimum_support'])+1.7)
  else:ax.text(.5,.5,'此端点未保存投票状态',transform=ax.transAxes,ha='center')
  ax.set_title(arm+' 候选对应组票数（浅色＝未选中）',fontsize=11);ax.set_ylabel('独立人员支持票');ax.grid(axis='y',alpha=.15)
 fig.suptitle(image+'：具体成员如何通过对应组、门槛和连接进入输出',fontsize=14)
 handles=[Line2D([0],[0],color='#8b97a4',lw=8,label='共同背景 D'),Line2D([0],[0],color=COLORS['C'],lw=8,label='替换块 X / Y / Z'),Line2D([0],[0],color='#b72d33',ls='--',label='实际门槛')]
 fig.legend(handles=handles,loc='lower center',ncol=3,bbox_to_anchor=(.5,.01),frameon=False);save_figure(fig,out/'3D_VOTES.png',dpi=160,bbox_inches='tight');save_figure(fig,out/'3D_VOTES.pdf',bbox_inches='tight');plt.close(fig)
 annotation=[]
 for name in ['D','X','Y','Z']:
  for w in (e[name].split('|') if e[name] else []):
   r=members[w];annotation.append(dict(block=name,worker=w,object_id=r['object_id'],bottom_points=len(r['points'])//2,Q=r.get('B8L2'),D10=r.get('D10'),source_time_seconds=r.get('source_time_seconds'),time_source_kind=r.get('time_source_kind'),points_json=json.dumps(r['points'],separators=(',',':'))))
 save_csv(out/'RAW_ANSWERS.csv',pd.DataFrame(annotation))
 values=[]
 for arm,r in arms.items():
  row={'arm':arm,'members':e[arm+'_members'],'team_key':e[arm+'_team_key']};row.update({k:v for k,v in r.items() if k in ['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','boundary_loss','direction_loss','height_loss','omission','extension','height_mean_h','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','source_time_total_seconds','time_source_kinds','minimum_support','score_status','geometry_status','connection_available']});values.append(row)
 save_csv(out/'ABC_COMPONENTS.csv',pd.DataFrame(values));(out/'CASE_PROVENANCE.json').write_text(json.dumps({'event_id':e['event_id'],'case_source':str(path),'original_file':str(pic),'reference_id':pool['meta']['reference_id'],'data_release':'v2.1','new_scores':0,'new_fusions':0,'no_ring_or_point_changes':True,'geometry':'camera-height normalized; 3D conditional proxy, not measured physical room dimensions','erp_curve':'great-circle between stored corners; seam split; original full point order'},ensure_ascii=False,indent=2))
 return {'event_id':e['event_id'],'image':image,'method':e['method'],'n':e['n'],'m':e['m'],'ERP_BEV':str(out/'ERP_BEV.png'),'3D_VOTES':str(out/'3D_VOTES.png')}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',required=True,type=Path);ap.add_argument('--out',type=Path,default=HERE/'figures');ap.add_argument('--originals',type=Path,default=HERE/'originals');a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=True);index=a.out/'CASE_FIGURE_INDEX.csv'
 old=pd.read_csv(index).to_dict('records') if index.exists() else [];rows={r['event_id']:r for r in old};completed=[]
 for p in a.cases:
  r=render(p,a.out,a.originals);rows[r['event_id']]=r;completed.append(r)
  save_csv(index,pd.DataFrame(rows.values()));print('saved_case',r['event_id'],flush=True)
 print(json.dumps(completed,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
