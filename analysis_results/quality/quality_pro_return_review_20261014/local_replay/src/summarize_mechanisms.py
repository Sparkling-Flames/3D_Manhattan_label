"""Summaries of completed experiments; all denominators explicitly recorded."""
from collections import defaultdict,Counter
from itertools import combinations
from core import *
from compare import csv_dump,quant
from mechanisms import align_for_diagnostic

def main():
    co=read(INPUT/'data/cohorts.json');oo=read(INPUT/'data/objects.json');obj={o['object_id']:o for o in oo['objects']}
    bc=read(INPUT/'preparation/BOTTOM_CONTROLS.json')['rows'];decomp=[]
    for sign in [-1,1]:
        for budget in [8,16]:
            r=next(r for r in bc if r['case_id']==f'1x4:distributed_bottom:{sign}:{budget}')
            p=profile(geometry(r['points']));pg=profile(geometry(r['reference_points']));a=np.array(p['edge_angle_deg']);ax=pg['axis_deg'];free=(a-ax+45)%90-45;locked=(a-np.array(pg['edge_angle_deg'])+180)%360-180
            decomp.append(dict(case_id=r['case_id'],sign=sign,budget=budget,**p,
               fixed_axis_free_family_current_weights=float(np.sqrt(np.array(p['weights'])@(free**2))),
               fixed_axis_free_family_reference_weights=float(np.sqrt(np.array(pg['weights'])@(free**2))),
               fixed_axis_locked_family_current_weights=float(np.sqrt(np.array(p['weights'])@(locked**2))),
               fixed_axis_locked_family_reference_weights=float(np.sqrt(np.array(pg['weights'])@(locked**2)))))
    dump(ROOT/'results/axis_family_decomposition.json',decomp)
    mech=read(ROOT/'results/mechanism_controls.json');dense=mech['dense_bottom'];summary={}
    for name in ['historical_tail12_g1','historical_simple8_g1','current_hill08','loss_sum','max_floor']:
        b=defaultdict(list)
        for r in dense:b[(tuple(r['shape']),r['mode'],r['sign'])].append(r)
        windows=[]
        for key,rr in b.items():
            for a,z in zip(rr,rr[1:]):
                if a['status']!='complete' or z['status']!='complete':continue
                if z['scores'][name]['score']>a['scores'][name]['score']+1e-8:windows.append([a['case_id'],z['case_id']])
        summary[name]=dict(upward_steps=len(windows),windows=windows)
    tr=read(ROOT/'results/real_bottom_trajectories.json');rev=tr['reversal_windows']
    trajectories={n:dict(upward_windows=sum(r['score_deltas'][n]>1e-8 for r in rev),records=len({r['record_id'] for r in rev if r['score_deltas'][n]>1e-8})) for n in summary}
    targets=[('J01',['R03346','R03347']),('J04',['R03274']),('Q01',['R03332','R03329']),('Q02',['R02200','R00990']),('Q03',['R01501','R01191'])]
    by={r['record_id']:r for k in ['ordinary','doorway'] for r in co[k]};desc=[]
    for group,ids in targets:
        for rid in ids:
            r=by[rid];ref=r.get('reference_object_id') or r['reference']['object_id'];g=oo['geometries'][r['object_id']];rg=oo['geometries'][ref];h=hm.height_moments(g);hr=hm.height_moments(rg)
            desc.append(dict(group=group,record_id=rid,annotation_pair_count=len(g['bottom3d']),reference_pair_count=len(rg['bottom3d']),D=profile(g)['D'],
                Hmean=abs(h['height_mean_h']/hr['height_mean_h']-1),own_height_std_over_reference_mean=h['height_std_h']/hr['height_mean_h'],
                own_height_range_over_reference_mean=(h['height_max_h']-h['height_min_h'])/hr['height_mean_h'],perimeter_mean_height_ratio=h['height_mean_h']/hr['height_mean_h'],
                height_moments=h,reference_height_moments=hr))
    csv_dump(ROOT/'results/review_group_geometry.csv',desc)
    refs=sorted({r['reference_object_id'] for r in co['ordinary']});ds=[dict(object_id=x,D=profile(oo['geometries'][x])['D']) for x in refs]
    j=read(ROOT/'results/J04_interventions.json');d=np.array(j['point_delta_vs_aligned_reference']);share=float(np.max(d[1::2,1]**2)/np.sum(d[1::2,1]**2))
    cp=read(ROOT/'results/actual_direction_counterpatterns.json')
    summary=dict(dense_bottom_n=len(dense),dense_complete=sum(r['status']=='complete' for r in dense),dense_unavailable=sum(r['status']!='complete' for r in dense),dense_upward_steps=summary,
        trajectories_ordinary_matched=len(tr['matched']),trajectory_states=len(tr['records']),trajectory_statuses=dict(Counter(r['status'] for r in tr['records'])),
        I_down_D_down_windows=len(rev),I_down_D_down_records=len({r['record_id'] for r in rev}),I_down_D_down_Q_up=trajectories,
        actual_submitted_pair_search_n=cp['actual_pairs_tested'],actual_submitted_counterpairs=len(cp['actual_pairs']),derived_rectangle_worsening_windows=len(cp['derived_corner_worsening_windows']),
        J04_largest_bottom_y_squared_error_share=share,reference_D_distribution=quant([r['D'] for r in ds]),reference_D_per_object=ds,
        no_new_human_order_from_controls=True,other_coordinate_errors_and_footprint_matching_can_change=True)
    dump(ROOT/'results/mechanism_summary.json',summary)
    print('mechanism summary complete',summary['dense_complete'],summary['actual_submitted_pair_search_n'],summary['J04_largest_bottom_y_squared_error_share'])
if __name__=='__main__':main()
