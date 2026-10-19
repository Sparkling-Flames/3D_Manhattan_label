"""Corresponding-corner diagnostics for the frozen 451-event panel, separate from Q."""
from functools import lru_cache
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tools.thesis_main.analysis.personnel_composition_followup_20261019 import OUT,read,save,csv,modules,building_mean
from tools.thesis_main.analysis.personnel_corner_review_20261020 import project


@lru_cache(maxsize=1)
def metric_module():
    return modules()[2]


def signed_area(bottom):
    x,z=bottom[:,0],bottom[:,2]
    return .5*np.sum(x*np.roll(z,-1)-z*np.roll(x,-1))


def compare(a,b):
    pa,pb=a['geometry']['points'],b['geometry']['points']
    row={'complete':bool(a['complete_evaluable'] and b['complete_evaluable']),
         'same_count':pa is not None and pb is not None and len(pa)==len(pb)}
    if pa is None or pb is None:return dict(row,status='missing_connected_geometry'),[]
    if not row['complete']:return dict(row,status='incomplete_geometry'),[]
    if not row['same_count']:return dict(row,status='different_corner_count'),[]
    pa,pb=np.asarray(pa,float),np.asarray(pb,float)
    ba,ta=project(pa);bb,tb=project(pb)
    n=len(ba);sg=metric_module();old,reason,_=sg.structural_distance(pa,pb)
    assert not reason and signed_area(ba)!=0 and signed_area(bb)!=0
    reverse=bool(np.sign(signed_area(ba))!=np.sign(signed_area(bb)))
    source=np.arange(n)[::-1] if reverse else np.arange(n)
    bp=pb.reshape(n,2,2)[source].reshape(-1,2)
    cost=np.maximum(sg.angular(pa[::2],bp[::2]),sg.angular(pa[1::2],bp[1::2]))
    shifts=np.array([cost[np.arange(n),(np.arange(n)+s)%n].max() for s in range(n)])
    shift=int(shifts.argmin());best=float(shifts[shift]);second=float(np.sort(shifts)[1])
    row.update(corners=n,ring_reversed=reverse,shift=shift,legacy_angle_deg=old,angle_deg=best,second_angle_deg=second,match_gap_deg=second-best)
    if second-best<=1e-9:return dict(row,status='ambiguous_cyclic_match'),[]
    idx=source[(np.arange(n)+shift)%n];bb,tb=bb[idx],tb[idx]
    bottom=np.linalg.norm(bb-ba,axis=1);top=np.linalg.norm(tb-ta,axis=1)
    diagonal=float(np.linalg.norm(np.ptp(ba[:,[0,2]],axis=0)))
    row.update(status='unique_cyclic_candidate',bev_mean_h=float(bottom.mean()),bev_max_h=float(bottom.max()),
               top_mean_h=float(top.mean()),top_max_h=float(top.max()),
               bev_max_pct_diagonal=float(100*bottom.max()/diagonal),top_max_pct_diagonal=float(100*top.max()/diagonal))
    points=[dict(corner_A_index=j,corner_other_index=int(idx[j]),bev_h=float(bottom[j]),top_h=float(top[j]),
                 dx_h=float(bb[j,0]-ba[j,0]),dz_h=float(bb[j,2]-ba[j,2]),height_change_h=float(tb[j,1]-ta[j,1])) for j in range(n)]
    return row,points


def main():
    save(OUT/'PANEL_CORNER_PLAN.json',dict(date='2026-10-20',scope='all existing 451 events; existing labels and teams, no refit',
        user_direction='same corner count permits direct distance comparison; establish correspondence and retain structural mismatches separately',
        distances=['BEV mean and maximum h','top 3D mean and maximum h','max distances / A bounding-box diagonal'],
        matching='normalize winding from signed floor area, then frozen cyclic angular matching; retain legacy no-reverse angle; unique candidate is not semantic proof',
        comparison='A/B and A/C on the same jointly available events; event means within image pool, then equal buildings; all attempts retained in support ledger',
        sensitivities='all common candidates and joint <=9/12 degree neighborhood; existing clustering scales, not newly adopted similarity or success thresholds',
        limitations='post-hoc extension to explored v2; no external validation, no Q threshold tuning'))
    events=pd.read_csv(OUT/'EVENTS.csv.gz');teams=read(OUT/'TEAMS.json.gz')
    pairs,points=[],[]
    for _,event in events.iterrows():
        for arm,letter in [('within','B'),('cross','C')]:
            result,detail=compare(teams[event.A_team_key],teams[event[letter+'_team_key']])
            meta={k:event[k] for k in ['event_id','target','sample','historical_phase','pool_id','building','image','k','m']}
            meta['arm']=arm
            pairs.append(dict(meta,**result))
            points.extend(dict(meta,**p) for p in detail)
    pairs=pd.DataFrame(pairs);csv(OUT/'PANEL_CORNER_PAIRS.csv.gz',pairs);csv(OUT/'PANEL_CORNER_POINTS.csv.gz',pd.DataFrame(points))
    data=events[['event_id','target','sample','historical_phase','pool_id','building','image','k','m']].copy()
    fields=['status','complete','same_count','ring_reversed','angle_deg','match_gap_deg','bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pct_diagonal','top_max_pct_diagonal']
    for arm in ['within','cross']:
        p=pairs[pairs.arm==arm][['event_id']+fields].rename(columns={k:arm+'_'+k for k in fields})
        data=data.merge(p,on='event_id',validate='one_to_one')
    data['both_available']=(data.within_status=='unique_cyclic_candidate')&(data.cross_status=='unique_cyclic_candidate')
    csv(OUT/'PANEL_CORNER_EVENTS.csv.gz',data)
    metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pct_diagonal','top_max_pct_diagonal']
    summary=[];by_building=[]
    for keys,g in data.groupby(['target','sample','historical_phase']):
        for gate in [None,9,12]:
            paired=g[g.both_available].copy()
            if gate is not None:paired=paired[(paired.within_angle_deg<=gate)&(paired.cross_angle_deg<=gate)].copy()
            row=dict(zip(['target','sample','historical_phase'],keys),gate='all_common' if gate is None else f'angle_le_{gate}',attempted_events=len(g),paired_events=len(paired),paired_images=paired.pool_id.nunique(),paired_buildings=paired.building.nunique())
            for metric in metrics:
                within,cross='within_'+metric,'cross_'+metric
                paired['delta_'+metric]=paired[cross]-paired[within]
                paired['cross_larger_'+metric]=(paired[cross]>paired[within]+1e-9).astype(float)
                for field in [within,cross,'delta_'+metric,'cross_larger_'+metric]:row[field]=building_mean(paired,field)
                for arm in ['within','cross']:
                    row[arm+'_'+metric+'_event_median']=paired[arm+'_'+metric].median()
                    row[arm+'_'+metric+'_event_p90']=paired[arm+'_'+metric].quantile(.9)
            summary.append(row)
            cols=[col for col in paired if any(col==prefix+m for m in metrics for prefix in ['within_','cross_','delta_','cross_larger_'])]
            b=paired.groupby(['building','pool_id'])[cols].mean().groupby('building').mean().reset_index()
            for _,br in b.iterrows():by_building.append(dict(zip(['target','sample','historical_phase'],keys),gate=row['gate'],**br.to_dict()))
    csv(OUT/'PANEL_CORNER_SUMMARY.csv',pd.DataFrame(summary));csv(OUT/'PANEL_CORNER_BUILDINGS.csv',pd.DataFrame(by_building))
    support=pairs.groupby(['target','sample','historical_phase','arm','status']).agg(events=('event_id','size'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
    csv(OUT/'PANEL_CORNER_SUPPORT.csv',support)
    anomalies=pairs[(pairs.ring_reversed==True)|(pairs.angle_deg>12)|(pairs.status=='ambiguous_cyclic_match')]
    csv(OUT/'PANEL_CORNER_REVIEW_QUEUE.csv',anomalies)
    assert len(data)==451 and len(pairs)==902 and data.event_id.is_unique
    save(OUT/'PANEL_CORNER_CHECKS.json',dict(events=len(data),pair_attempts=len(pairs),common_events=int(data.both_available.sum()),
        within_candidates=int((data.within_status=='unique_cyclic_candidate').sum()),cross_candidates=int((data.cross_status=='unique_cyclic_candidate').sum()),
        reversed_pairs=int((pairs.ring_reversed==True).sum()),review_queue=len(anomalies),source='Existing frozen final geometries; no fusion or score rerun'))
    plot_buildings(pd.DataFrame(by_building))
    print(pd.DataFrame(summary).query("gate=='all_common'")[[*['target','sample','historical_phase','paired_events','paired_images','paired_buildings'],*['within_bev_mean_h','cross_bev_mean_h','within_bev_max_h','cross_bev_max_h','cross_larger_bev_mean_h']]].round(5).to_string(index=False))


def plot_buildings(frame):
    view=frame[(frame['sample']=='additional_background')&(frame.historical_phase=='validation')&(frame.gate=='all_common')]
    fig,axes=plt.subplots(1,2,figsize=(12,4),sharex=True)
    for ax,(target,g) in zip(axes,view.groupby('target')):
        y=np.arange(len(g));ax.barh(y,g.delta_bev_mean_h,color=['#087f8c' if x>0 else '#b45309' for x in g.delta_bev_mean_h]);ax.set_yticks(y,g.building);ax.axvline(0,color='black',linewidth=.8);ax.grid(axis='x',alpha=.2);ax.set_title(target);ax.set_xlabel('Cross minus within: mean corner displacement / h')
    fig.suptitle('Additional backgrounds on previously held-out images: equal pools per building');fig.tight_layout();fig.savefig(OUT/'panel_corner_buildings.png',dpi=160);plt.close(fig)


if __name__=='__main__':main()
