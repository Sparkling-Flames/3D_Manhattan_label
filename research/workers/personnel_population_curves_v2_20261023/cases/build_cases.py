"""Exploratory mechanism cases from actual frozen v2 natural prefixes.

No fusion, reference, score, raw point or ring alteration occurs.  Match groups
across prefixes by shared source observations, not unstable node identifiers.
Reference matching is a post-output angular diagnostic, never an input to votes.
"""
from pathlib import Path
import argparse,collections,gzip,hashlib,io,itertools,json,math,os,sys,zipfile
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
BASE=Path(os.environ.get('HOHONET_POPULATION_WORKSPACE', '/workspace/scratch/fe955c3c772c'))
ROOT=Path(os.environ.get('HOHONET_POPULATION_REPO', str(BASE/'HOHONET_population_latest')))
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.paired_split_research.study import angular as angular_pixel_center
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
FUSION=ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
SCORE=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','omission','extension','nodes','source_time_total_seconds','target_time_total_seconds','boundary_loss','direction_loss','global_height_loss','local_height_loss']
DESCRIPTIONS={
 'UwV83HsGsw3-12':('Early structure recovery','Bedroom entry: localized wall return; mirror is not additional room extent.'),
 'pa4otMbVnkk-09':('Position improvement with unchanged four corners','Ceiling moulding exposes the four room corners; furniture occludes lower points.'),
 'UwV83HsGsw3-09':('Persistent missing structure','Closet / bathroom returns and mirrors; inspect reference-aligned minority groups.'),
 'uNb9QFRL6hY-60':('A declining path despite more people','Bathroom glass and wall returns; distinguish threshold losses from regrouping.'),
 'B6ByNegPMKs-33':('Narrower variation at a low plateau','Four-corner corridor: examine shared outward / positional bias.')}

def angular(a,b):
    # Frozen v2 geometry uses continuous pixel coordinates. The older shared
    # angular helper adds a half-pixel; cancel it, as the frozen fusion does.
    return angular_pixel_center(np.asarray(a,float)-.5,np.asarray(b,float)-.5)

def read(p):
    with gzip.open(p,'rt') if str(p).endswith('.gz') else open(p) as f:return json.load(f)
def clean(v):
    if isinstance(v,dict):return {str(k):clean(a) for k,a in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [clean(a) for a in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def atomic(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def jsonsave(p,v):
    b=json.dumps(clean(v),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    atomic(p,gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def csvsave(p,d):
    b=d.to_csv(index=False).encode('utf-8-sig');atomic(p,gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def observations(g):return {(m['id'],m['pair_index']) for m in g['members']}
def groupmap(state):return {obs:g['feature_id'] for g in state['identity_groups'] for obs in observations(g)}
def partition_changes(a,b):
    am,bm=groupmap(a),groupmap(b);common=sorted(am.keys()&bm.keys());split=merge=0
    for x,y in itertools.combinations(common,2):
        same_a=am[x]==am[y];same_b=bm[x]==bm[y]
        split+=same_a and not same_b;merge+=same_b and not same_a
    return dict(shared_observation_n=len(common),common_observation_pairs_split=int(split),common_observation_pairs_merged=int(merge))

def export_cases():
    candidates=pd.read_csv(BASE/'population_work/difficulty/stage01/CASE_CANDIDATES_STAGE01.csv')
    prefixes=pd.read_csv(BASE/'population_work/reuse/HISTORICAL_UNIFORM_PREFIX_ROWS.csv.gz',low_memory=False)
    pools={p['pool_id']:p for p in read(FUSION/'INPUT_SNAPSHOT.json.gz')['images']}
    arcindex=read(ROOT/'research/workers/pro_personnel_v2_archive_20261019/ARCHIVE_FILE_MAP.json')
    amap={r['path']:r for r in arcindex}
    labels=pd.read_csv(BASE/'HOHONET/research/workers/personnel_mixture_comparison_20261022/inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz')
    combined_events=[];combined_votes=[];combined_links=[];summary=[]
    for case in candidates.to_dict('records'):
        image=case['image'];folder=OUT/image;folder.mkdir(parents=True,exist_ok=True)
        path=prefixes[prefixes.path_id.eq(case['path_id'])].sort_values('k');pid=path.pool_id.iloc[0];pool=pools[pid]
        all_paths=prefixes[prefixes.pool_id.eq(pid)]
        pointer=case['geometry_state_pointer_from'].split('#')[0];entry='work_v2_20261019/fusion/'+pointer;info=amap[entry]
        with zipfile.ZipFile(BASE/'source_recovery/v2_population_original'/info['archive']) as z:raw=z.read(entry)
        assert hashlib.sha256(raw).hexdigest()==info['sha256']
        states={x['team_id']:x['automatic'] for x in json.loads(gzip.decompress(raw))['states']}
        pstate={int(r.k):states[r.legacy_team_id] for r in path.itertuples()}
        ref=np.asarray(pool['reference']['points_1024x512'],float);nref=len(ref)//2
        votes=[];links=[];events=[]
        for r in path.itertuples():
            state=pstate[r.k]
            if state is None:continue
            groups=state['identity_groups'];valid=[g for g in groups if g.get('center') is not None]
            centers=np.asarray([g['center'] for g in valid]);mapping={}
            if len(valid):
                tc=angular(centers[:,0,:],ref[::2]);bc=angular(centers[:,1,:],ref[1::2]);cost=np.maximum(tc,bc)
                ii,jj=linear_sum_assignment(cost)
                mapping={valid[i]['feature_id']:(int(j),float(cost[i,j]),float(tc[i,j]),float(bc[i,j])) for i,j in zip(ii,jj)}
            for g in groups:
                rr=mapping.get(g['feature_id']);center=g.get('center')
                v=dict(case=image,path_id=case['path_id'],pool_id=pid,k=int(r.k),team_key=r.team_key,feature_id=g['feature_id'],
                    threshold=state['minimum_support'],support=g['support'],selected=g['selected'],margin_to_threshold=g['support']-state['minimum_support'],
                    workers='|'.join(sorted(m['worker'] for m in g['members'])),observations='|'.join(sorted(m['id']+':'+str(m['pair_index']) for m in g['members'])),
                    reference_corner=rr[0]+1 if rr else None,reference_pair_max_error_deg=rr[1] if rr else None,
                    reference_top_error_deg=rr[2] if rr else None,reference_bottom_error_deg=rr[3] if rr else None,
                    reference_match_within_5=rr[1]<=5 if rr else False,reference_match_within_9=rr[1]<=9 if rr else False,
                    x_px=center[0][0] if center else None,top_y_px=center[0][1] if center else None,bottom_y_px=center[1][1] if center else None,
                    reference_diagnostic_only=True)
                votes.append(v)
        def event(a,b,kind):
            ra=path[path.k.eq(a)].iloc[0];rb=path[path.k.eq(b)].iloc[0];sa,sb=pstate[a],pstate[b]
            row=dict(case=image,role=case['role'],path_id=case['path_id'],pool_id=pid,condition=case['condition'],building=pool['meta']['building'],
                event_kind=kind,k_from=a,k_to=b,added_n=b-a,team_from=ra.team_key,team_to=rb.team_key,
                members_from=ra.member_workers,members_to=rb.member_workers,
                added_workers='|'.join(sorted(set(rb.member_workers.split('|'))-set(ra.member_workers.split('|')))),
                threshold_from=sa['minimum_support'] if sa else None,threshold_to=sb['minimum_support'] if sb else None,
                score_status_from=ra.score_status,score_status_to=rb.score_status,complete_from=ra.complete_evaluable,complete_to=rb.complete_evaluable,
                reference_pair_count=nref,selection='exploratory from four original uniform orders; no claim of independent validation')
            for f in SCORE:
                row['from_'+f]=ra.get(f);row['to_'+f]=rb.get(f);row['delta_'+f]=rb.get(f)-ra.get(f) if pd.notna(ra.get(f)) and pd.notna(rb.get(f)) else None
            if sa and sb:
                row.update(partition_changes(sa,sb))
                for ga in sa['identity_groups']:
                    for gb in sb['identity_groups']:
                        overlap=observations(ga)&observations(gb)
                        if overlap:links.append(dict(case=image,event_kind=kind,k_from=a,k_to=b,from_group=ga['feature_id'],to_group=gb['feature_id'],from_support=ga['support'],to_support=gb['support'],from_selected=ga['selected'],to_selected=gb['selected'],shared_observations=len(overlap),shared_worker_ids='|'.join(sorted({m['worker'] for m in ga['members'] if (m['id'],m['pair_index']) in overlap}))))
            events.append(row);return row
        primary=event(int(case['k_from']),int(case['k_to']),'primary_case')
        for a in range(1,int(path.k.max())):event(a,a+1,'adjacent_prefix')
        csvsave(folder/'CASE_EVENTS.csv',pd.DataFrame(events));csvsave(folder/'CASE_VOTES.csv',pd.DataFrame(votes));csvsave(folder/'CASE_GROUP_LINKS.csv',pd.DataFrame(links))
        csvsave(folder/'PATH_SCALARS.csv',all_paths.drop(columns=['geometry_state_pointer'],errors='ignore'))
        csvsave(folder/'LOBO_MEMBER_LABELS.csv',labels[labels.condition.eq(case['condition'])&labels.heldout_building.eq(pool['meta']['building'])&labels.worker_id.isin([r['worker_id'] for r in pool['records']])])
        jsonsave(folder/'CASE_GEOMETRY.json.gz',dict(case=case,pool=pool,states={str(k):s for k,s in pstate.items()},source_archive=info['archive'],source_member=entry,source_member_sha256=info['sha256'],source_main='72a44e80c344975962e1071bd54d894dd86bb4b4',native_fusion_calls=0,quality_scores_recomputed=0))
        jsonsave(folder/'CASE_RECEIPT.json',dict(case=image,stages=len(pstate),raw_records=len(pool['records']),vote_rows=len(votes),events=len(events),overlap_links=len(links),native_calls=0,case_kind='exploratory_mechanism',references_unchanged=True))
        combined_events.extend(events);combined_votes.extend(votes);combined_links.extend(links);summary.append(primary)
        print('Saved complete case evidence '+image,flush=True)
    csvsave(OUT/'CASE_EVENTS.csv',pd.DataFrame(combined_events));csvsave(OUT/'CASE_VOTES.csv',pd.DataFrame(combined_votes));csvsave(OUT/'CASE_GROUP_LINKS.csv',pd.DataFrame(combined_links));csvsave(OUT/'CASE_PRIMARY_SUMMARY.csv',pd.DataFrame(summary))

def project_xyz(xyz):
    xyz=np.asarray(xyz,float);u=(np.arctan2(xyz[:,0],-xyz[:,1])/(2*np.pi)+.5)*1024
    v=(.5-np.arctan2(xyz[:,2],np.linalg.norm(xyz[:,:2],axis=1))/np.pi)*512
    return np.c_[u,v]
def layout3d(points):
    q=reconstruct(dict(points=points,ring_confirmed=False,order_status='declared'),coordinate_convention='continuous')
    return q['floor'],q['heights']
def curve3d(points,top=False):
    floor,heights=layout3d(points)
    if floor is None or heights is None:return []
    xyz=np.c_[floor,heights-1 if top else -np.ones(len(floor))];out=[]
    for a,b in zip(xyz,np.roll(xyz,-1,axis=0)):
        q=project_xyz(a[None,:]+np.linspace(0,1,70)[:,None]*(b-a)[None,:]);cuts=np.r_[0,np.where(np.abs(np.diff(q[:,0]))>512)[0]+1,len(q)]
        out.extend(q[x:y] for x,y in zip(cuts[:-1],cuts[1:]) if y-x>=2)
    return out

def plot_cases():
    os.environ['MPLCONFIGDIR']=str(BASE/'population_work/cases/.mpl')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import patheffects
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':12})
    colors={'ref':'#1f2937','before':'#d55e00','after':'#0072b2','raw':'#8a8a8a','added':'#56b4e9'}
    for folder in sorted(OUT.iterdir()):
        if not (folder/'CASE_GEOMETRY.json.gz').exists():continue
        p=read(folder/'CASE_GEOMETRY.json.gz');case=p['case'];pool=p['pool'];image=case['image'];a=int(case['k_from']);b=int(case['k_to']);statea=p['states'][str(a)];stateb=p['states'][str(b)]
        ref=pool['reference']['points_1024x512'];pa=statea['candidate'].get('points');pb=stateb['candidate'].get('points')
        membersa=set(case['member_workers_from'].split('|'));membersb=set(case['member_workers_to'].split('|'));added=membersb-membersa
        endpoint=pd.read_csv(folder/'CASE_EVENTS.csv').query("event_kind == 'primary_case'").iloc[0]
        fig=plt.figure(figsize=(18,14.2));gs=fig.add_gridspec(3,3,height_ratios=[1.42,1,1],left=.055,right=.98,bottom=.065,top=.91,hspace=.3,wspace=.28)
        ax=fig.add_subplot(gs[0,:]);im=plt.imread(OUT/'originals'/(image+'.png'));ax.imshow(im,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([])
        def erp(points,color,lw,alpha=1,ls='-'):
            if points is None:return
            pp=np.asarray(points)
            for top in [False,True]:
                for q in curve3d(points,top):ax.plot(q[:,0],q[:,1],color=color,lw=lw,alpha=alpha,ls=ls,path_effects=[patheffects.Stroke(linewidth=lw+1.2,foreground='white',alpha=.7),patheffects.Normal()])
            for pair in pp.reshape(-1,2,2):ax.plot(pair[:,0],pair[:,1],color=color,lw=lw*.65,alpha=alpha,ls=ls)
        for r in pool['records']:
            if r['worker_id'] in added:erp(r['points'],colors['added'],.7,.45)
        erp(ref,colors['ref'],2.1,ls='--');erp(pa,colors['before'],2.1);erp(pb,colors['after'],2.1)
        ax.set_title('Original ERP + frozen reference / fused layouts; light blue = newly added raw annotations',loc='left',pad=9)
        ax.legend(handles=[Line2D([0],[0],color=colors[c],lw=2.5,ls='--' if c=='ref' else '-',label=l) for c,l in [('ref','Adopted reference'),('before',f'Before n={a}'),('after',f'After n={b}'),('added','Added raw answers')]],loc='lower center',ncol=4,fontsize=10,framealpha=.9)
        def bev(ax,points,color,lw,alpha=1,ls='-',numbers=False):
            if points is None:return
            floor,_=layout3d(points)
            if floor is None:return
            p=np.vstack([floor,floor[0]]);ax.plot(p[:,0],p[:,1],color=color,lw=lw,alpha=alpha,ls=ls)
            if numbers:
                for i,(x,z) in enumerate(floor):ax.annotate('R'+str(i+1),(x,z),xytext=(4,4),textcoords='offset points',fontsize=9,color=color)
        bx=fig.add_subplot(gs[1,0]);be=fig.add_subplot(gs[1,1]);vax=fig.add_subplot(gs[1,2]);qax=fig.add_subplot(gs[2,0]);tax=fig.add_subplot(gs[2,1]);dax=fig.add_subplot(gs[2,2],projection='3d')
        for r in pool['records']:
            if r['worker_id'] in membersb:bev(bx,r['points'],colors['added'] if r['worker_id'] in added else colors['raw'],.8,.55 if r['worker_id'] in added else .28)
        bev(bx,ref,colors['ref'],1.8,ls='--',numbers=True)
        for pp,c,ls in [(ref,'ref','--'),(pa,'before','-'),(pb,'after','-')]:bev(be,pp,colors[c],2,ls=ls,numbers=c=='ref')
        for axis in [bx,be]:axis.scatter([0],[0],marker='+',s=55,color='black');axis.set_aspect('equal',adjustable='datalim');axis.set_xlabel('x / camera height');axis.set_ylabel('z / camera height');axis.grid(alpha=.2)
        bx.set_title('Actual answers: existing gray / entrants blue');be.set_title('Fused footprints: structural and positional change')
        votes=pd.read_csv(folder/'CASE_VOTES.csv');nref=len(ref)//2;xx=np.arange(1,nref+1)
        for kk,col,dx in [(a,'before',-.18),(b,'after',.18)]:
            vv=votes[votes.k.eq(kk)&votes.reference_corner.notna()].set_index('reference_corner');vals=[vv.loc[i,'support'] if i in vv.index else 0 for i in xx];bars=vax.bar(xx+dx,vals,width=.33,color=colors[col],alpha=.85,label=f'n={kk}')
            for i,bar in zip(xx,bars):
                if i in vv.index and not vv.loc[i,'selected']:bar.set_hatch('///');bar.set_alpha(.35)
                if i in vv.index and vv.loc[i,'reference_pair_max_error_deg']>9:vax.text(i+dx,bar.get_height()+.25,'*',ha='center',color=colors[col],fontsize=12)
            threshold=(kk+1)//2;vax.axhline(threshold,color=colors[col],ls=':',lw=1.7)
        vax.set_xticks(xx,['R'+str(x) for x in xx]);vax.set_ylabel('Votes in assigned identity group');vax.set_title('Reference-aligned group votes and thresholds');vax.legend(ncol=2,fontsize=9);vax.text(0,-.2,'Hatch: below threshold.  *: angular error >9°.\nReference assignment is diagnostic only.',transform=vax.transAxes,fontsize=9)
        paths=pd.read_csv(folder/'PATH_SCALARS.csv');selected=paths[paths.path_id.eq(case['path_id'])]
        for _,g in paths.groupby('path_id'):qax.plot(g.k,g.B8L2,color='#aaaaaa',alpha=.55,lw=1)
        qax.plot(selected.k,selected.B8L2,color='#4e3d79',lw=2.2,label='Selected actual order');qax.scatter([a,b],[endpoint.from_B8L2,endpoint.to_B8L2],c=[colors['before'],colors['after']],s=45,zorder=5);qax.set_ylim(0,103);qax.set_xlabel('People in current prefix');qax.set_ylabel('B8L2 Q');qax.set_title('Actual prefix trajectory (four historical orders)');qax.grid(alpha=.2);qax.legend(fontsize=9)
        tax.axis('off');table=[]
        for metric,label,scale,fmt in [('B8L2','Q',1,'.2f'),('D10','D10',1,'.2f'),('iou_2d','Floor IoU',100,'.1f'),('IoU3D100','3D proxy',1,'.1f'),('S_bottom_deg','Bottom error (deg)',1,'.2f'),('dir','Axis residual (deg)',1,'.2f'),('Hmean','Global height term',1,'.2f'),('Hcenter','Local height term',1,'.2f'),('omission','Omission',100,'.1f'),('extension','Extension',100,'.1f'),('nodes','Output corners',1,'.0f')]:
            va=endpoint.get('from_'+metric);vb=endpoint.get('to_'+metric);table.append([label,format(va*scale,fmt) if pd.notna(va) else 'NA',format(vb*scale,fmt) if pd.notna(vb) else 'NA'])
        tab=tax.table(cellText=table,colLabels=['Frozen measurement',f'n={a}',f'n={b}'],loc='center',cellLoc='right',colWidths=[.6,.2,.2]);tab.auto_set_font_size(False);tab.set_fontsize(10);tab.scale(1,1.35);tax.set_title('Saved quality components; unchanged reference')
        for points,col,ls in [(ref,'ref','--'),(pa,'before','-'),(pb,'after','-')]:
            if points is None:continue
            floor,H=layout3d(points)
            if floor is None or H is None:continue
            q=np.vstack([floor,floor[0]]);h=np.r_[H,H[0]]
            dax.plot(q[:,0],q[:,1],np.zeros(len(q)),c=colors[col],ls=ls,lw=1.5);dax.plot(q[:,0],q[:,1],h,c=colors[col],ls=ls,lw=1.5)
            for (x,z),height in zip(floor,H):dax.plot([x,x],[z,z],[0,height],c=colors[col],ls=ls,lw=.8,alpha=.75)
        dax.set_xlabel('x / h');dax.set_ylabel('z / h');dax.set_zlabel('Height / h');dax.view_init(elev=25,azim=-60);dax.set_title('Declared 3D wall band (camera height h=1)')
        title,subtitle=DESCRIPTIONS[image]
        fig.suptitle(f'{image}  |  {title}\nn={a} → {b}; output corners {int(endpoint.from_nodes)} → {int(endpoint.to_nodes)}; Q {endpoint.from_B8L2:.2f} → {endpoint.to_B8L2:.2f}',fontsize=17,x=.055,ha='left',y=.978)
        fig.text(.055,.935,subtitle,fontsize=12)
        fig.text(.055,.015,'Exploratory mechanism chosen from four archived natural orders. Whole-image means/support are reported separately using the completed study.\nCoordinates and declared ring order are unchanged; geometric reference matching does not certify every corner’s semantics.',fontsize=10,color='#404040')
        buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150,facecolor='white');atomic(folder/'MECHANISM_ERP_BEV_VOTES_3D.png',buf.getvalue());plt.close(fig)
        print('Saved figure '+image,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['export','plot','all']);a=p.parse_args()
    if a.action in ('export','all'):export_cases()
    if a.action in ('plot','all'):plot_cases()
