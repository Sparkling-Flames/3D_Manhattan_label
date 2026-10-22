#!/usr/bin/env python3
"""Explain one useful difficulty interaction without selecting only good events.

The 2,810 registered strict triples remain the sampling frame.  Counts of
events, distinct endpoint sets, images and buildings are kept separate.
The small pa4 example is nearest the full image's net-Q median, not its maximum.
All geometry/quality is read from existing caches; no re-fusion or re-scoring.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_difficulty_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from analyze_difficulty import HERE,ROOT,save,write_json

CID='ca2a651478a2ab2966a4'
IMAGE='pa4otMbVnkk-18'
BUILDING='pa4otMbVnkk'
SUB='case_qdown_pa4'
OUT=HERE/SUB

def csv(df,name):save(df,SUB+'/'+name)
def js(obj,name):write_json(SUB+'/'+name,obj)

def atomic(path,data):
    t=path.with_name(path.name+'.partial')
    with open(t,'wb') as f:
        assert f.write(data)==len(data);f.flush();os.fsync(f.fileno())
    os.replace(t,path);assert path.read_bytes()==data

def figsave(fig,name):
    p=OUT/name;fmt=p.suffix[1:];buf=io.BytesIO()
    fig.savefig(buf,format=fmt,dpi=180)
    data=buf.getvalue()
    if fmt=='png':Image.open(io.BytesIO(data)).load()
    atomic(p,data)

def support(g):
    r={'events':len(g),'oriented_triples':g.actual_oriented_ABC.nunique(),
       'physical_triples':g.actual_physical_ABC.nunique(),
       'images':g.image.nunique(),'buildings':g.building.nunique(),
       'backgrounds':g.background_key.nunique(),
       'source_partitions':g.source_partition_id.nunique()}
    for arm in 'ABC':
        u=g.drop_duplicates('team_'+arm)
        assert not g.groupby('team_'+arm)[arm+'_failure'].nunique().gt(1).any()
        r[arm+'_distinct_endpoints']=len(u)
        r[arm+'_distinct_failed_endpoints']=int(u[arm+'_failure'].sum())
        r[arm+'_failed_events']=int(g[arm+'_failure'].sum())
    for pre in ['same','cross','net']:
        q=g[pre+'_B8L2'].dropna()
        r.update({pre+'_Q_known_events':len(q),pre+'_Q_up_events':int(q.gt(1e-9).sum()),
                  pre+'_Q_zero_events':int(q.abs().le(1e-9).sum()),
                  pre+'_Q_down_events':int(q.lt(-1e-9).sum()),
                  pre+'_loss_gt5_events':int(q.lt(-5).sum()),
                  pre+'_loss_gt10_events':int(q.lt(-10).sum()),
                  pre+'_event_equal_Q_mean':q.mean(),pre+'_event_Q_median':q.median()})
    return r

def floor(points):
    b=np.asarray(points,dtype=float)[1::2]
    u=2*np.pi*(b[:,0]/1024-.5);v=np.pi*(.5-b[:,1]/512)
    rad=-1/np.tan(v)
    return np.c_[rad*np.sin(u),-rad*np.cos(u)]

def closed(p):p=np.asarray(p);return np.vstack([p,p[0]])

def main():
    OUT.mkdir(exist_ok=True)
    base=HERE.parent/'exchanges';src=base/'manual_joint_A'
    links=pd.read_csv(src/'EXACT_EVENT_LINKS.csv.gz',low_memory=False)
    outcomes=pd.read_csv(src/'EVENT_OUTCOMES.csv.gz',low_memory=False)
    links=links[links.condition_id.eq(CID)];outcomes=outcomes[outcomes.condition_id.eq(CID)]
    keys=['event_id','condition_id','actual_oriented_ABC','actual_physical_ABC']
    e=links.merge(outcomes,on=keys,validate='one_to_one')
    assert len(e)==2810 and e.actual_physical_ABC.is_unique
    assert e[['actual_m_AB','actual_m_AC','actual_m_BC']].eq(3).all().all()
    assert e.n.eq(20).all() and e.condition.eq('manual').all()
    img=pd.read_csv(base/'ALL_IMAGE_EFFECTS.csv.gz');img=img[img.condition_id.eq(CID)]
    core=pd.read_csv(HERE/'exchange_difficulty_core.csv');core=core[core.condition_id.eq(CID)]
    counts=[];bs=[]
    for (d,i,b),g in e.groupby(['difficulty','image','building']):
        counts.append(dict(difficulty=d,image=i,building=b,**support(g)))
    counts=pd.DataFrame(counts)
    csv(counts,'EXACT_IMAGE_COUNTS.csv')
    csv(img,'ALL_IMAGE_EFFECTS.csv')
    for (d,i,b,bg),g in e.groupby(['difficulty','image','building','background_key']):
        row=dict(difficulty=d,image=i,building=b,background_key=bg,
                 source_classes='|'.join(sorted(set(g.source_class))),
                 target_classes='|'.join(sorted(set(g.target_class))),
                 common_background=g.common_background.iloc[0],**support(g))
        bs.append(row)
    bs=pd.DataFrame(bs);csv(bs,'EXACT_BACKGROUND_COUNTS.csv')
    summ=[]
    for d,g in e.groupby('difficulty'):
        ii=img[img.difficulty.eq(d)];bb=ii.groupby('building').net_B8L2.mean().dropna()
        bg=bs[bs.difficulty.eq(d)];bv=bg.net_event_equal_Q_mean.dropna()
        r=dict(difficulty=d,**support(g),
               Q_known_images=int(ii.net_B8L2.notna().sum()),Q_up_images=int(ii.net_B8L2.gt(0).sum()),
               Q_known_buildings=len(bb),Q_up_buildings=int(bb.gt(0).sum()),
               Q_known_backgrounds=len(bv),Q_up_backgrounds=int(bv.gt(0).sum()))
        cc=core[core.current_difficulty.eq(d)].iloc[0]
        for k in ['same_B8L2','cross_B8L2','net_B8L2','net_D10','within_abs_B8L2',
                  'cross_abs_B8L2','A_failure','B_failure','C_failure','net_loss_gt5','net_loss_gt10',
                  'net_recorded_time_pct','net_nodes','net_fusion_turn_n','net_fusion_short_turn_edges',
                  'net_fusion_redundancy_n','net_dir','net_iou_2d','net_IoU3D100','net_S_bottom_deg',
                  'net_Hmean','net_Hcenter']:
            r[k+'_building_equal']=cc[k]
        summ.append(r)
    csv(pd.DataFrame(summ),'DIFFICULTY_SUPPORT_AND_RISK.csv')
    # The entire image is retained and its full median defines the case.
    g=e[e.image.eq(IMAGE)].copy();median=g.net_B8L2.median()
    g['distance_to_image_net_Q_median']=(g.net_B8L2-median).abs()
    sel=g.sort_values(['distance_to_image_net_Q_median','event_id']).iloc[0]
    csv(links[links.event_id.eq(sel.event_id)],'EXACT_EVENT_LINK.csv')
    csv(outcomes[outcomes.event_id.eq(sel.event_id)],'EVENT_OUTCOME.csv')
    cols=['event_id','team_A','team_B','team_C','source_partition_id','background_key',
          'outgoing_block_X','same_count_block_Y','changed_count_block_Z','same_B8L2','cross_B8L2','net_B8L2',
          'A_failure','B_failure','C_failure','net_recorded_time_logratio']
    csv(g[cols],'ALL_100_IMAGE_EVENTS.csv')
    ep=ROOT/'research/workers/personnel_exchange_closure_20261022/delivery/endpoints'
    teamkeys={sel['team_'+a] for a in 'ABC'}
    scal=pd.read_csv(ep/'ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz',low_memory=False)
    scal=scal[scal.team_key.isin(teamkeys)].copy();assert len(scal)==3
    expressions=pd.read_csv(HERE.parent/'inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz').set_index('team_key')
    for f in ['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']:
        derived=scal.team_key.map(expressions[f])
        if scal[f].notna().any():
            assert np.allclose(scal.loc[scal[f].notna(),f],derived[scal[f].notna()])
        scal[f]=scal[f].fillna(derived)
    geom=pd.read_csv(ep/'ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz',low_memory=False)
    geom=geom[geom.team_key.isin(teamkeys)].copy();assert len(geom)==3
    csv(scal,'ENDPOINT_SCALARS.csv');csv(geom,'ENDPOINT_GEOMETRY.csv')
    labs=pd.read_csv(ROOT/'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz')
    labs=labs[labs.condition.eq('manual')&labs.method.eq('V3_JOINT_QT')&labs.heldout_building.eq(BUILDING)]
    csv(labs,'FOLD_LABELS_AND_HISTORY.csv')
    features=['q_history','q_downside','t_history','turn_history','short_history','redundancy_history',
              'area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history']
    # Match original register_design.py: centers use all known members in this
    # Manual fold; actual experiment members are restricted to new origin.
    cent=labs[labs.known].groupby('coarse_label')[features].mean().reset_index()
    cent=cent.merge(labs[labs.known].groupby('coarse_label').agg(
        known_people=('worker_id','size'),members=('worker_id',lambda x:'|'.join(sorted(x)))),on='coarse_label')
    csv(cent,'TRAINING_CLASS_CENTERS.csv')
    cm=cent.set_index('coarse_label')
    for f in features:
        assert abs(cm.loc[sel.target_class,f]-cm.loc[sel.source_class,f]-sel['class_center_delta_'+f])<1e-8
    with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz','rt') as f:raw=json.load(f)['records']
    objects=set('|'.join(scal.member_object_ids).split('|'))
    raw=[r for r in raw if r['object_id'] in objects];assert len(raw)==len(objects)==26
    ref=raw[0]['reference_evidence'];js(ref,'REFERENCE.json')
    assert np.allclose(floor(ref['points_1024x512']),ref['floor_xz_h'],atol=1e-9)
    keep=['object_id','worker_id','image_id','image_code','building_id','condition','origin','data_release',
          'current_class','quality_usable','quality_use','independent_vote_eligible','B8L2','D10','reference_id',
          'reference_version','source_active_time_seconds','time_evidence','points_1024x512','geometry_status',
          'order_status','ring_confirmed','measurements']
    js([{k:r.get(k) for k in keep} for r in raw],'RAW_MEMBER_GEOMETRY.json')
    roles={'D':sel.common_background.split('|'),'X':sel.outgoing_block_X.split('|'),
           'Y':sel.same_count_block_Y.split('|'),'Z':sel.changed_count_block_Z.split('|')}
    assert len(set(roles['D']))==17
    assert len(set(sum(roles.values(),[])))==26
    byworker={r['worker_id']:r for r in raw}
    op=pd.read_csv(HERE/'record_opportunity_index.csv.gz')
    op=op[op.object_id.isin(objects)]
    membership=[]
    for block,workers in roles.items():
        for w in workers:
            r=byworker[w];l=labs[labs.worker_id.eq(w)].iloc[0]
            membership.append(dict(worker_id=w,object_id=r['object_id'],block=block,coarse_label=l.coarse_label,
                                   fine_label=l.fine_label,target_B8L2=r['B8L2'],target_D10=r['D10'],
                                   recorded_seconds=r['source_active_time_seconds'],**{k:l[k] for k in features}))
    mem=pd.DataFrame(membership).merge(op[['object_id','turn_n','short_turn_edges','near_straight_nodes_5deg',
                                         'ref_turn5','unmatched_ref_9','abs_bottom_bias_9']],on='object_id',validate='one_to_one')
    csv(mem,'EXACT_MEMBERS_AND_FEATURES.csv')
    comps=[]
    for m in ['B8L2','D10','IoU3D100','iou_2d','dir','S_bottom_deg','Hmean','Hcenter','omission','extension',
              'nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','minimum_support',
              'ref_node_recall_9','ref_edge_recall_9','geometry_area_h2','height_mean_h','top_y_mean_px','bottom_y_mean_px',
              'source_time_total_seconds']:
        vals={a:scal[scal.team_key.eq(sel['team_'+a])][m].iloc[0] for a in 'ABC'}
        comps.append(dict(metric=m,**vals,same_B_minus_A=vals['B']-vals['A'],cross_C_minus_A=vals['C']-vals['A'],
                          net_C_minus_B=vals['C']-vals['B']))
    csv(pd.DataFrame(comps),'COMPONENT_CHANGES.csv')
    # Plot original point geometries, preserving their frozen ring order.
    fig,axs=plt.subplots(2,3,figsize=(13,8),layout='constrained')
    rf=closed(ref['floor_xz_h']);colors={'A':'#7C74AF','B':'#D47923','C':'#087D97'}
    for j,block in enumerate('XYZ'):
        ax=axs[0,j];ax.plot(rf[:,0],rf[:,1],'k--',lw=1,label='Reference')
        for k,w in enumerate(roles[block]):
            f=closed(floor(byworker[w]['points_1024x512']))
            ax.plot(f[:,0],f[:,1],'-o',lw=1,ms=3,label=f'{w} (Q {byworker[w]["B8L2"]:.1f})')
        ax.set_title(f'{block}: {"source J4" if block!="Z" else "target J2"}\n'+ '|'.join(roles[block]),fontsize=10)
        ax.legend(fontsize=8,frameon=False,loc='upper right')
    for j,arm in enumerate('ABC'):
        ax=axs[1,j];s=scal[scal.team_key.eq(sel['team_'+arm])].iloc[0]
        gg=json.loads(geom[geom.team_key.eq(sel['team_'+arm])].geometry_json.iloc[0]);p=closed(gg['footprint'])
        ax.plot(rf[:,0],rf[:,1],'k--',lw=1,label='Reference')
        ax.plot(p[:,0],p[:,1],'-o',color=colors[arm],lw=1.8,ms=4,label=arm)
        for k,(xy,votes) in enumerate(zip(np.asarray(gg['footprint']),str(s.node_supports).split('|'))):
            ax.annotate(f'{k}: {votes}',xy,xytext=(4,4),textcoords='offset points',fontsize=8,color=colors[arm])
        ax.set_title(f'{arm} = D + {"XYZ"[j]}, Q {s.B8L2:.3f}, D10 {s.D10:.3f}\n'
                     f'{int(s.nodes)} nodes; dir {s["dir"]:.3f}°, bottom {s.S_bottom_deg:.3f}°',fontsize=10)
    for ax in axs.ravel():
        ax.grid(alpha=.2);ax.set_aspect('equal');ax.set_xlim(-2.6,2);ax.set_ylim(-4.7,.8)
        ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height')
    for ax in axs[0,:]:ax.set_xlim(-3.25,2.35)  # retain every raw point, including target-block extensions
    fig.suptitle('pa4otMbVnkk-18 · Manual · difficult · strict n20 / m3\n'
                 'All 100 triples retained; this event is closest to the full-image median net Q',fontsize=13,weight='bold')
    figsave(fig,'RAW_BLOCKS_AND_ABC_BEV.png');figsave(fig,'RAW_BLOCKS_AND_ABC_BEV.svg');plt.close(fig)
    receipt=dict(status='saved',condition_id=CID,data_version='v2',input_commit='ef148c82df18582228b2d23837faa2659e79eba7',
                 registered_events=len(e),retained_images=e.image.nunique(),retained_buildings=e.building.nunique(),
                 exact_backgrounds=e.background_key.nunique(),case_image=IMAGE,case_event_id=sel.event_id,
                 case_selection='minimum absolute distance to net-Q median of all 100 registered pa4-18 triples; event_id tie break',
                 case_image_net_Q_median=float(median),case_net_Q=float(sel.net_B8L2),case_cross_Q=float(sel.cross_B8L2),
                 case_image_positive_net_events=int(g.net_B8L2.gt(0).sum()),case_image_total_events=len(g),
                 new_fusion=0,new_scoring=0,
                 support_note='Raw event and unique endpoint counts differ from equal-background/image/building rates; both preserved.',
                 class_center_scope='all known Manual people in the target-building-excluded fold, matching registered direction; teams new_only_labelled',
                 geometry_sha256=hashlib.sha256((OUT/'ENDPOINT_GEOMETRY.csv').read_bytes()).hexdigest())
    js(receipt,'RECEIPT.json');print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
