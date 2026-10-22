#!/usr/bin/env python3
"""Two opposite exact-background mechanisms, actual original B6-47 panorama."""
from pathlib import Path
import collections,io,json,os,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'personnel_exchange_closure_20261022'
sys.path[:0]=[str(OLD/'structure'),str(OLD/'mechanisms')]
import evaluate_structure as es
from export_new_cases import angular
from run_background_gradient import OUT,gs,write_json
from analyze_existing import save
SPECS=[('background_net_gain','4d6de0aa67c65554b8664145'),('background_net_loss','9c22b933a08174c4fce173b3')]

def main():
    P=pd.read_csv(OUT/'MATCHED_BACKGROUND_GRADIENT_PAIRS.csv.gz')
    E=pd.read_csv(OUT/'EVENTS_COMPLETE.csv.gz',low_memory=False).set_index('event_id')
    S=pd.read_csv(OUT/'ENDPOINT_SCALARS.csv.gz',dtype=str,keep_default_na=False)
    G=pd.read_csv(OUT/'ENDPOINT_GEOMETRY.csv.gz',dtype=str,keep_default_na=False)
    needed=set()
    for _,pid in SPECS:
        r=P[P.pair_id.eq(pid)].iloc[0]
        needed|={r['team_'+a+'_'+s] for a in 'ABC' for s in ['low','high']}
    teams={r['team_key']:es.typed(r) for r in S[S.team_key.isin(needed)].to_dict('records')}
    for r in G[G.team_key.isin(needed)].to_dict('records'):teams[r['team_key']]['geometry']=json.loads(r['geometry_json'])
    pools=gs.pool_lookup();fe,_,_,_=gs.setup_engine();rows=[];metrics=[];states=[];members=[];receipt=[]
    with fe.cached_matching():
        for cid,pid in SPECS:
            r=P[P.pair_id.eq(pid)].iloc[0].to_dict();pool=pools[r['pool_id']];by={m['worker_id']:m for m in pool['records']}
            ref=np.asarray(pool['reference']['points_1024x512']);case={'case_id':cid,'pair':r,'reference':pool['reference'],'pool_meta':pool['meta'],'states':[]}
            for level in ['low','high']:
                ev=E.loc[r['event_'+level]]
                for arm in 'ABC':
                    t=dict(teams[r['team_'+arm+'_'+level]]);ws=t['member_workers']
                    state=fe.clean(fe.compact(fe.fuse([by[w] for w in sorted(ws)],gap=fe.WORKING_GAP)['automatic']))
                    assert gs.digest(state['candidate'])==gs.digest(t['geometry'])
                    t['full_state']=state;t['arm']=arm;t['background_level']=level;case['states'].append(t)
                    metrics.append({k:v for k,v in t.items() if not isinstance(v,(dict,list))}|dict(case_id=cid,arm=arm,background_level=level))
                    states.append(dict(case_id=cid,arm=arm,background_level=level,event_id=ev.name,team_key=t['team_key'],members='|'.join(ws),D=ev.common_background,X=ev.outgoing_block_X,Y=ev.same_count_block_Y,Z=ev.changed_count_block_Z))
                    for group in state['identity_groups']:
                        center=np.asarray(group['center']);dist=np.maximum(angular(center[:1],ref[::2]),angular(center[1:],ref[1::2]))[0];j=int(np.argmin(dist))
                        rows.append(dict(case_id=cid,arm=arm,background_level=level,group=group['feature_id'],support=group['support'],selected=group['selected'],threshold=10,
                            nearest_reference_corner=j,reference_alignment='posthoc nearest paired angle; groups are not combined',paired_bound_distance_deg=float(dist[j]),
                            top_x=center[0,0],top_y=center[0,1],bottom_x=center[1,0],bottom_y=center[1,1],
                            member_observation_keys='|'.join(sorted(m['worker']+':'+str(m['pair_index']) for m in group['members'])),
                            member_workers='|'.join(sorted(m['worker'] for m in group['members']))))
            selected=set(r['shared_X'].split('|')+r['shared_Y'].split('|')+r['shared_Z'].split('|')+r['low_D'].split('|')+r['high_D'].split('|'))
            case['members']=[by[w] for w in sorted(selected)]
            for w in sorted(selected):members.append(dict(by[w])|dict(case_id=cid,worker_id=w,role='removed_source' if w==r['background_removed_source'] else 'added_target' if w==r['background_added_target'] else 'shared'))
            write_json(OUT/'cases'/(cid+'.json.gz'),case)
            receipt.append(dict(case_id=cid,pair_id=pid,source_image='B6ByNegPMKs-47',state_replays=6,score_calls=0,saved_geometry_equal=True,selection='解释性事后案例：相同XYZ锚点中正反两种背景成员替换，不用于估计总体效果'))
    save('background_gradient/cases/GROUP_VOTES.csv.gz',pd.DataFrame(rows))
    transitions=[]
    gv=pd.DataFrame(rows)
    for cid,_ in SPECS:
        for corner in range(10):
            d=gv[gv.case_id.eq(cid)&gv.arm.eq('C')&gv.nearest_reference_corner.eq(corner)&gv.selected]
            lo=d[d.background_level.eq('low')];hi=d[d.background_level.eq('high')]
            if len(lo)!=1 or len(hi)!=1:continue
            lo=lo.iloc[0];hi=hi.iloc[0]
            a=set(lo.member_observation_keys.split('|'));b=set(hi.member_observation_keys.split('|'))
            transitions.append(dict(case_id=cid,arm='C',reference_corner=corner,selected_low=bool(lo.selected),selected_high=bool(hi.selected),support_low=int(lo.support),support_high=int(hi.support),
                lost_observations='|'.join(sorted(a-b)),gained_observations='|'.join(sorted(b-a)),
                paired_bound_distance_deg_low=lo.paired_bound_distance_deg,paired_bound_distance_deg_high=hi.paired_bound_distance_deg,
                top_x_change=hi.top_x-lo.top_x,top_y_change=hi.top_y-lo.top_y,bottom_y_change=hi.bottom_y-lo.bottom_y))
    save('background_gradient/cases/LOCAL_GROUP_TRANSITIONS.csv',pd.DataFrame(transitions))
    save('background_gradient/cases/ENDPOINT_METRICS.csv',pd.DataFrame(metrics))
    save('background_gradient/cases/EXACT_EVENTS_AND_MEMBERS.csv',pd.DataFrame(states))
    save('background_gradient/cases/RAW_MEMBER_GEOMETRY.csv.gz',pd.DataFrame(members))
    write_json(OUT/'cases/RECEIPT.json',dict(cases=receipt,score_calls=0,total_state_replays=12))
    render()

def render():
    os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    original=OLD/'mechanisms/originals/B6ByNegPMKs_e26e2cb761894264a4a34b1046701f6b.png'
    panorama=np.asarray(Image.open(original).convert('RGB'))
    for cid,_ in SPECS:
        case=gs.read(OUT/'cases'/(cid+'.json.gz'));r=case['pair'];members={m['worker_id']:m for m in case['members']};ts={(s['arm'],s['background_level']):s for s in case['states']}
        fig=plt.figure(figsize=(14,10),layout='constrained');grid=fig.add_gridspec(2,3,height_ratios=[1.15,1])
        ax=fig.add_subplot(grid[0,:]);ax.imshow(panorama,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0)
        for w,col,lbl in [(r['background_removed_source'],'#30e0e0','removed ordinary'),(r['background_added_target'],'#ffb025','added more-turn')]:
            pts=np.asarray(members[w]['points']);top=pts[::2];bottom=pts[1::2]
            for pp in [top,bottom]:
                qq=np.vstack([pp,pp[:1]])
                for i in range(len(qq)-1):
                    if abs(qq[i+1,0]-qq[i,0])<512:ax.plot(qq[i:i+2,0],qq[i:i+2,1],color=col,lw=1.4,alpha=.9)
            ax.scatter(bottom[:,0],bottom[:,1],s=32,c=col,edgecolors='black',linewidths=.4,label=w+' '+lbl)
        ax.legend(loc='lower right',fontsize=9);ax.set_title('Actual B6-47 panorama: the one changed background member',fontsize=12)
        rf=np.asarray(case['reference']['floor_xz_h']);rr=np.vstack([rf,rf[:1]])
        for j,arm in enumerate('ABC'):
            ax=fig.add_subplot(grid[1,j]);ax.plot(rr[:,0],rr[:,1],color='black',lw=1.5,ls='--',label='Frozen reference')
            for level,col in [('low','#247ba0'),('high','#e27922')]:
                t=ts[arm,level];p=np.asarray(t['geometry']['footprint']);q=np.vstack([p,p[:1]])
                ax.plot(q[:,0],q[:,1],color=col,marker='o',markersize=3,lw=1.7,label=f'{level} target background: Q {t["B8L2"]:.2f}')
            a=ts[arm,'high']['B8L2']-ts[arm,'low']['B8L2'];ax.set_title(f'{arm}: background-only change {a:+.2f} Q\nNodes {ts[arm,"low"]["nodes"]} -> {ts[arm,"high"]["nodes"]}')
            ax.set_aspect('equal');ax.legend(fontsize=8);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height')
        sign='increases' if r['net_change_B8L2']>0 else 'decreases'
        fig.suptitle(f'Fixed XYZ / n=20 / foreground m=7: {r["background_removed_source"]} -> {r["background_added_target"]}\nNet class advantage {sign} by {r["net_change_B8L2"]:+.2f} Q; only 1 member in D changes',fontsize=14)
        dest=OUT/'cases'/(cid+'.png');buf=io.BytesIO();fig.savefig(buf,format='png',dpi=170);plt.close(fig)
        data=buf.getvalue();tmp=dest.with_suffix('.tmp')
        with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
        with Image.open(dest) as im:im.load()
    print('Cases and figures complete',flush=True)

if __name__=='__main__':main()
