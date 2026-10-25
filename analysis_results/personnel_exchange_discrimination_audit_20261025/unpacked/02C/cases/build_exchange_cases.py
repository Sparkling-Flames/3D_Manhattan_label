#!/usr/bin/env python3
"""Exact strict ABC mechanism cases, unchanged v2 geometry/fusion/measurement.
Reference alignment is a post-output diagnostic, never an input to grouping/votes.
"""
from pathlib import Path
import argparse,collections,gzip,hashlib,importlib.util,io,itertools,json,math,os,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));import run_native as native
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
OUT=Path(__file__).resolve().parent
POP=native.POP
OLD_CASES=POP/'cases'
COLORS={'D':'#9299a1','X':'#d55e00','Y':'#0072b2','Z':'#009e73','A':'#d55e00','B':'#0072b2','C':'#009e73','ref':'#20262e'}
METRICS=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','omission','extension','nodes','source_time_total_seconds','reference_node_shortfall','floor_turn5_n','ref_top_pair_mean_deg','ref_bottom_pair_mean_deg']

def read(p):return native.read(p)
def save(p,x):native.save(p,native.base.clean(x))
def csv(p,d):native.csv(p,d)
def figure_save(fig,path,dpi=160):
 buf=io.BytesIO();fig.savefig(buf,format='png',dpi=dpi,facecolor='white',bbox_inches='tight',pad_inches=.12);raw=buf.getvalue()
 from PIL import Image
 Image.open(io.BytesIO(raw)).verify()
 temp=path.with_name(path.name+'.tmp')
 with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 temp.replace(path)
def block(s):return str(s).split('|') if pd.notna(s) and str(s) else []
def obs(g):return {(str(m['id']),int(m['pair_index'])) for m in g['members']}
def mapobs(st):return {o:g['feature_id'] for g in st['identity_groups'] for o in obs(g)}
def partition_changes(sa,sb):
 a,b=mapobs(sa),mapobs(sb);common=sorted(a.keys()&b.keys());split=merge=0
 for x,y in itertools.combinations(common,2):
  aa=a[x]==a[y];bb=b[x]==b[y];split+=aa and not bb;merge+=bb and not aa
 return {'shared_observations':len(common),'same_observation_pairs_split':int(split),'same_observation_pairs_merged':int(merge)}

def resolve_image(image,out):
 dest=out/'originals'/(image+'.png');dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():return dest
 old=OLD_CASES/'originals'/(image+'.png')
 if old.exists():shutil.copy2(old,dest);return dest
 return None

def export_case(event,out,native_out):
 pid=event['pool_id'];eid=event['event_id'];folder=out/eid;folder.mkdir(parents=True,exist_ok=True)
 pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']};pool=pools[pid]
 cached={r['team_key']:r for r in read(native_out/'endpoints'/(pid+'.json.gz'))['teams']}
 gs,fe,fr,sg=native.setup();rows={};states={};receipts=[]
 with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
  for role in ['A','B','C']:
   ws=block(event[role+'_members']);key=event[role+'_team_key'];assert native.team_key(pid,ws)==key
   prior=cached[key];r=fr.evaluate_one(pool,ws,engine,models,score_cache={},full_state=True)
   state=r.pop('full_state',None);states[role]=state;rows[role]=prior
   deltas={k:float(r[k])-float(prior[k]) for k in ['B8L2','D10','iou_2d','IoU3D100'] if r.get(k) is not None and prior.get(k) is not None}
   assert all(abs(x)<1e-7 for x in deltas.values()),(role,deltas)
   assert (r.get('B8L2') is None)==(prior.get('B8L2') is None)
   receipts.append({'role':role,'team_key':key,'maximum_scalar_replay_difference':max([abs(x) for x in deltas.values()]or[0]),'replayed':True,'state_available':state is not None})
 ref=np.asarray(pool['reference']['points_1024x512'],float);votes=[];links=[];part=[];rawpairs=[]
 wsblocks={name:set(block(event[name])) for name in ['D','X','Y','Z']}
 for role,st in states.items():
  if st is None:continue
  valid=[g for g in st['identity_groups'] if g.get('center') is not None]
  assigned={};nearest={}
  if valid:
   centers=np.asarray([g['center'] for g in valid]);tc=fe.angular(centers[:,0,:],ref[::2]);bc=fe.angular(centers[:,1,:],ref[1::2]);cost=np.maximum(tc,bc)
   ii,jj=linear_sum_assignment(cost)
   assigned={valid[i]['feature_id']:(int(j)+1,float(cost[i,j]),float(tc[i,j]),float(bc[i,j])) for i,j in zip(ii,jj)}
   for i,g in enumerate(valid):
    j=int(np.argmin(cost[i]));nearest[g['feature_id']]=(j+1,float(cost[i,j]))
  for g in st['identity_groups']:
   a=assigned.get(g['feature_id']);near=nearest.get(g['feature_id']);members=[str(m['worker']) for m in g['members']];center=g.get('center')
   row={'event_id':eid,'role':role,'team_key':event[role+'_team_key'],'feature_id':g['feature_id'],'support':g['support'],'threshold':st['minimum_support'],'selected':g['selected'],'margin':g['support']-st['minimum_support'],'workers':'|'.join(sorted(members)),'observations':'|'.join(sorted(str(m['id'])+':'+str(m['pair_index']) for m in g['members'])),'reference_corner':a[0] if a else None,'reference_pair_error_deg':a[1] if a else None,'reference_top_error_deg':a[2] if a else None,'reference_bottom_error_deg':a[3] if a else None,'nearest_reference_corner':near[0] if near else None,'nearest_reference_pair_error_deg':near[1] if near else None,'center_x':center[0][0] if center else None,'center_top_y':center[0][1] if center else None,'center_bottom_y':center[1][1] if center else None,'reference_is_diagnostic_only':True}
   for bn,bw in wsblocks.items():row['votes_'+bn]=len(set(members)&bw)
   votes.append(row)
 for one,two in [('A','B'),('A','C'),('B','C')]:
  sa,sb=states[one],states[two]
  if sa is None or sb is None:continue
  part.append({'event_id':eid,'from':one,'to':two,**partition_changes(sa,sb)})
  for ga in sa['identity_groups']:
   for gb in sb['identity_groups']:
    common=obs(ga)&obs(gb)
    if common:links.append({'event_id':eid,'from':one,'to':two,'from_group':ga['feature_id'],'to_group':gb['feature_id'],'shared_observations':len(common),'shared_workers':'|'.join(sorted({m['worker'] for m in ga['members'] if (str(m['id']),int(m['pair_index'])) in common})),'from_support':ga['support'],'to_support':gb['support'],'from_selected':ga['selected'],'to_selected':gb['selected']})
 for r in pool['records']:
  bn=next((bn for bn,bw in wsblocks.items() if r['worker_id'] in bw),None)
  if bn is None:continue
  pts=np.asarray(r['points'],float);tc=fe.angular(pts[::2],ref[::2]);bc=fe.angular(pts[1::2],ref[1::2]);cost=np.maximum(tc,bc);ii,jj=linear_sum_assignment(cost)
  for i,j in zip(ii,jj):rawpairs.append({'event_id':eid,'block':bn,'worker_id':r['worker_id'],'object_id':r['object_id'],'raw_pair_index':int(i),'reference_corner':int(j)+1,'top_error_deg':tc[i,j],'bottom_error_deg':bc[i,j],'pair_max_error_deg':cost[i,j],'within9':cost[i,j]<=9,'within5':cost[i,j]<=5})
 scalar=pd.DataFrame([{'role':role,'team_key':event[role+'_team_key'],**{k:r.get(k) for k in METRICS},'score_available':r.get('score_available'),'score_status':r.get('score_status'),'minimum_support':r.get('minimum_support')} for role,r in rows.items()])
 csv(folder/'ABC_SCALARS.csv',scalar);csv(folder/'VOTES.csv',pd.DataFrame(votes));csv(folder/'GROUP_LINKS.csv',pd.DataFrame(links));csv(folder/'COMMON_OBSERVATION_REGROUPING.csv',pd.DataFrame(part));csv(folder/'RAW_REFERENCE_PAIRS.csv',pd.DataFrame(rawpairs))
 csv(folder/'BLOCK_MEMBERS.csv',pd.DataFrame([{'block':bn,'worker_id':w,'role': {'D':'common_background','X':'original_source','Y':'same_class_replacement','Z':'cross_class_replacement'}[bn]} for bn,ww in wsblocks.items() for w in sorted(ww)]))
 vd=pd.DataFrame(votes);local=[]
 for corner in range(1,len(ref)//2+1):
  z={'event_id':eid,'reference_corner':corner,'threshold':math.ceil(event['n']/2)}
  for role in ['A','B','C']:
   vv=vd.loc[vd.role.eq(role)&vd.reference_corner.eq(corner)]
   for k in ['feature_id','support','selected','reference_pair_error_deg','reference_top_error_deg','reference_bottom_error_deg','votes_D','votes_X','votes_Y','votes_Z']:
    z[role+'_'+k]=vv.iloc[0][k] if len(vv) else None
  local.append(z)
 csv(folder/'LOCAL_VOTE_CHANGES.csv',pd.DataFrame(local))
 rr=pd.DataFrame(rawpairs)
 rawsupport=rr.groupby(['block','reference_corner']).agg(assigned_raw_pairs=('worker_id','size'),raw_within9=('within9','sum'),raw_within5=('within5','sum'),mean_top_error_deg=('top_error_deg','mean'),mean_bottom_error_deg=('bottom_error_deg','mean')).reset_index()
 rawsupport['block_n']=rawsupport.block.map({k:len(v) for k,v in wsblocks.items()});rawsupport['raw_within9_fraction']=rawsupport.raw_within9/rawsupport.block_n
 csv(folder/'RAW_BLOCK_SUPPORT.csv',rawsupport)
 contrasts=[]
 for a,b in [('A','B'),('A','C'),('B','C')]:
  rr={'event_id':eid,'comparison':b+'-'+a,'from_role':a,'to_role':b,'same_n':event['n'],'actual_m':len(set(block(event[b+'_members']))-set(block(event[a+'_members'])))}
  for k in METRICS:
   av=rows[a].get(k);bv=rows[b].get(k)
   rr['delta_'+k]=float(bv)-float(av) if av is not None and bv is not None else None
  contrasts.append(rr)
 csv(folder/'PAIR_DELTAS.csv',pd.DataFrame(contrasts))

 save(folder/'CASE_GEOMETRY.json.gz',{'event':event,'pool':pool,'states':states,'saved_endpoint_rows':rows,'freeze_contract':'original v2; all group/reference matching after fusion is diagnostic only'})
 save(folder/'REPLAY_RECEIPT.json',{'event_id':eid,'source_commit':'972857b2b3f548316be215400e42d6ef6e639250','data':'v2','native_replays':3,'endpoint_checks':receipts,'roles_failed':[r for r,v in rows.items() if not v.get('score_available')],'exact_blocks_disjoint':all(not(wsblocks[a]&wsblocks[b])for a,b in itertools.combinations(wsblocks,2))})
 resolve_image(event['image'],out)
 return folder

def layout(points):
 from tools.thesis_main.analysis.research_round_20260929 import reconstruct
 d=reconstruct(dict(points=points,ring_confirmed=False,order_status='declared'),coordinate_convention='continuous');return d['floor'],d['heights']
def project(xyz):
 xyz=np.asarray(xyz);return np.c_[(np.arctan2(xyz[:,0],-xyz[:,1])/(2*np.pi)+.5)*1024,(.5-np.arctan2(xyz[:,2],np.linalg.norm(xyz[:,:2],axis=1))/np.pi)*512]
def segments(points,top=False):
 f,h=layout(points)
 if f is None or h is None:return []
 xyz=np.c_[f,h-1 if top else -np.ones(len(f))];out=[]
 for a,b in zip(xyz,np.roll(xyz,-1,axis=0)):
  q=project(a[None,:]+np.linspace(0,1,60)[:,None]*(b-a)[None,:]);cuts=np.r_[0,np.where(np.abs(np.diff(q[:,0]))>512)[0]+1,len(q)]
  out.extend(q[x:y] for x,y in zip(cuts[:-1],cuts[1:]) if y-x>=2)
 return out

def plot_case(folder,out):
 os.environ['MPLCONFIGDIR']=str(out/'.mpl');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 from matplotlib.lines import Line2D
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11})
 native.setup();p=read(folder/'CASE_GEOMETRY.json.gz');e=p['event'];pool=p['pool'];states=p['states'];rows=p['saved_endpoint_rows'];image=e['image'];ref=pool['reference']['points_1024x512'];original=resolve_image(image,out)
 pts={r:states[r]['candidate'].get('points') if states[r] else None for r in ['A','B','C']};by={r['worker_id']:r for r in pool['records']};votes=pd.read_csv(folder/'VOTES.csv');rawref=pd.read_csv(folder/'RAW_REFERENCE_PAIRS.csv')
 fig=plt.figure(figsize=(19,14));gs=fig.add_gridspec(3,3,height_ratios=[1.05,1,1.1],left=.045,right=.98,top=.92,bottom=.105,hspace=.30,wspace=.23)
 def erp(ax,points,color,lw=1.4,alpha=1,ls='-'):
  if points is None:return
  for top in [False,True]:
   for q in segments(points,top):ax.plot(q[:,0],q[:,1],color=color,lw=lw,alpha=alpha,ls=ls)
  for pair in np.asarray(points).reshape(-1,2,2):ax.plot(pair[:,0],pair[:,1],color=color,lw=lw*.6,alpha=alpha,ls=ls)
 def bev(ax,points,color,lw=1.4,alpha=1,ls='-',number=False):
  if points is None:return
  f,h=layout(points)
  if f is None:return
  q=np.vstack([f,f[0]]);ax.plot(q[:,0],q[:,1],color=color,lw=lw,alpha=alpha,ls=ls)
  if number:
   for i,(x,z) in enumerate(f):ax.annotate('R'+str(i+1),(x,z),xytext=(3,3),textcoords='offset points',fontsize=8,color=color)
 for j,(role,bn) in enumerate(zip(['A','B','C'],['X','Y','Z'])):
  ax=fig.add_subplot(gs[0,j]);
  if original:ax.imshow(plt.imread(original),extent=[0,1024,512,0])
  else:ax.set_facecolor('#eeeeee');ax.text(.5,.5,'Original image pending',ha='center',transform=ax.transAxes)
  for w in block(e[bn]):erp(ax,by[w]['points'],COLORS[role],.55,.22)
  erp(ax,ref,'white',2.4,1,'--');erp(ax,ref,COLORS['ref'],1.1,1,'--');erp(ax,pts[role],COLORS[role],2.0)
  ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(role+' = D + '+bn+'  |  '+('Q %.2f'%rows[role]['B8L2'] if rows[role].get('B8L2') is not None else 'not scorable')+'\nLight curves: replacement block raw answers')
  bx=fig.add_subplot(gs[1,j])
  for w in block(e['D']):bev(bx,by[w]['points'],COLORS['D'],.7,.25)
  for w in block(e[bn]):bev(bx,by[w]['points'],COLORS[role],.9,.40)
  bev(bx,ref,COLORS['ref'],1.5,1,'--');bev(bx,pts[role],COLORS[role],2.2)
  bx.set_aspect('equal',adjustable='datalim');bx.scatter([0],[0],c='black',marker='+',s=35);bx.grid(alpha=.2);bx.set_xlabel('x / camera height');bx.set_ylabel('z / camera height');bx.set_title('Raw '+bn+' block + common D (gray)\nThick line: corresponding fused footprint')
 bx=fig.add_subplot(gs[2,0]);bev(bx,ref,COLORS['ref'],1.8,1,'--',True)
 for role in ['A','B','C']:bev(bx,pts[role],COLORS[role],2)
 bx.set_aspect('equal',adjustable='datalim');bx.grid(alpha=.2);bx.set_title('ABC output comparison');bx.set_xlabel('x / h');bx.set_ylabel('z / h');bx.legend(handles=[Line2D([0],[0],color=COLORS[r],lw=2,label=r) for r in ['A','B','C','ref']],fontsize=9,ncol=2)
 vx=fig.add_subplot(gs[2,1]);nr=len(ref)//2;xx=np.arange(1,nr+1)
 for role,dx in [('A',-.25),('B',0),('C',.25)]:
  z=votes[votes.role.eq(role)&votes.reference_corner.notna()].set_index('reference_corner');values=[z.loc[i,'support'] if i in z.index else 0 for i in xx];bars=vx.bar(xx+dx,values,.23,label=role,color=COLORS[role],alpha=.8)
  for i,b in zip(xx,bars):
   if i in z.index and not bool(z.loc[i,'selected']):b.set_hatch('///');b.set_alpha(.4)
   if i in z.index and z.loc[i,'reference_pair_error_deg']>9:vx.text(i+dx,b.get_height()+.15,'*',ha='center',color=COLORS[role])
 vx.axhline(math.ceil(e['n']/2),c='#222222',ls=':',lw=1.5,label='vote threshold');vx.set_xticks(xx,['R'+str(i) for i in xx]);vx.set_ylabel('Votes in reference-assigned identity group');vx.set_title('Local votes (assignment is diagnostic)');vx.legend(ncol=4,fontsize=9);vx.text(0,-.15,'Hatch: unselected group.  *: pair error > 9 degrees.\nAll groups, including unmatched ones, are saved in VOTES.csv.',transform=vx.transAxes,fontsize=8)
 tx=fig.add_subplot(gs[2,2]);tx.axis('off');tab=[]
 for k,name,scale,digits in [('B8L2','Q',1,2),('D10','D10',1,2),('iou_2d','Floor IoU %',100,1),('IoU3D100','3D proxy',1,1),('S_bottom_deg','Bottom error (deg)',1,2),('dir','Axis residual (deg)',1,2),('Hmean','Global height term',1,2),('Hcenter','Local height term',1,2),('omission','Omission %',100,1),('extension','Extension %',100,1),('nodes','Output nodes',1,0),('source_time_total_seconds','Recorded time (s)',1,0)]:
  vals=[rows[r].get(k) for r in ['A','B','C']];tab.append([name]+[f'{float(v)*scale:.{digits}f}' if v is not None and np.isfinite(v) else 'NA' for v in vals])
 table=tx.table(cellText=tab,colLabels=['Frozen measurement','A','B','C'],cellLoc='right',loc='center',colWidths=[.55,.15,.15,.15]);table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.25);tx.set_title('Saved endpoint components')
 fig.suptitle(f'{image} | {e["method"]} | {e["source_class"]} -> {e["target_class"]}\nStrict ABC: n={e["n"]}, m={e["m"]}; common background {len(block(e["D"]))}; target-class seats in D={e["background_target_n"]}',fontsize=16,x=.045,ha='left',y=.985)
 fig.text(.045,.025,'Exploratory case selected after the registered comparison. All A/B/C use the same image, n, m and common D.\nReference matching is diagnostic, not semantic certification. Original points, ring, fusion gate and scores are unchanged.',fontsize=10,color='#444444')
 figure_save(fig,folder/'ABC_ERP_BEV_VOTES.png',160);plt.close(fig)
 fig=plt.figure(figsize=(15,5))
 for j,role in enumerate(['A','B','C']):
  ax=fig.add_subplot(1,3,j+1,projection='3d')
  for pp,col,ls in [(ref,COLORS['ref'],'--'),(pts[role],COLORS[role],'-')]:
   if pp is None:continue
   f,h=layout(pp)
   if f is None or h is None:continue
   q=np.vstack([f,f[0]]);hh=np.r_[h,h[0]];ax.plot(q[:,0],q[:,1],np.zeros(len(q)),c=col,ls=ls);ax.plot(q[:,0],q[:,1],hh,c=col,ls=ls)
   for (x,z),height in zip(f,h):ax.plot([x,x],[z,z],[0,height],c=col,lw=.7,ls=ls)
  ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.set_zlabel('');ax.text2D(.98,.52,'height / h',transform=ax.transAxes,rotation=90,ha='right',va='center',fontsize=9);ax.view_init(elev=25,azim=-55);ax.set_title(role+' | declared 3D wall band')
 fig.suptitle(image+' | reference dashed / fusion colored',fontsize=14);fig.tight_layout();figure_save(fig,folder/'ABC_3D.png',150);plt.close(fig)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--events',type=Path,default=ROOT/'design/screen/EVENTS_EXACT.csv.gz');ap.add_argument('--native',type=Path,default=ROOT/'native');ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--event-id',action='append',required=True);ap.add_argument('--plot-only',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 events=pd.read_csv(a.events,low_memory=False);chosen=events.loc[events.event_id.isin(a.event_id)];assert len(chosen)==len(set(a.event_id)),(len(chosen),a.event_id)
 for e in chosen.to_dict('records'):
  folder=a.out/e['event_id']
  if not a.plot_only:export_case(e,a.out,a.native)
  plot_case(folder,a.out);print('Saved exact mechanism '+e['event_id']+' '+e['image'],flush=True)
 target=a.out/'CASE_SELECTION.csv'
 previous=pd.read_csv(target,low_memory=False) if target.exists() else pd.DataFrame()
 combined=pd.concat([previous,chosen],ignore_index=True).drop_duplicates('event_id',keep='last')
 csv(target,combined)
if __name__=='__main__':main()
