"""Explain pre-frozen mixed vector priorities with source/Q/difficulty support.

This is conditional interpretation after the frozen assessment, not an extra
validation claim or altered vector selection. All frozen candidates are kept
in the main replication tables.
"""
from pathlib import Path
import json,sys
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_mixed as a

def main():
    rows=[];leave=[]
    for phase in ['discovery','assessment']:
        f,_,_=a.load_phase(phase)
        targets={
          'HQ_T_n7_5fast2slow_within':f[(f.method_id=='F20_highQ23_T_qK2')&(f.n==7)&(f.m==7)&(f.A_vector=='C01:5|C02:2|outside_group:0')],
          'HQ_T_n7_5fast2slow_to4fast3slow':f[(f.method_id=='F20_highQ23_T_qK2')&(f.n==7)&(f.m==7)&(f.A_vector=='C01:5|C02:2|outside_group:0')&(f.C_vector=='C01:4|C02:3|outside_group:0')],
          'HQ_T_n4_3fast1slow_to2fast2slow':f[(f.method_id=='F20_highQ23_T_qK2')&(f.n==4)&(f.m==4)&(f.A_vector=='C01:3|C02:1|outside_group:0')&(f.C_vector=='C01:2|C02:2|outside_group:0')],
          'HQ_T_n5_2fast3slow_within':f[(f.method_id=='F20_highQ23_T_qK2')&(f.n==5)&(f.m==5)&(f.A_vector=='C01:2|C02:3|outside_group:0')],
          'Scope_n15_7low8high_within':f[(f.method_id=='F20_new_Scope_qK2')&(f.n==15)&(f.m==15)&(f.A_vector=='C01:7|C02:8|outside_group:0')]}
        for label,g in targets.items():
            if g.empty:continue
            subs={'all':g,'source_matched_assignment':g[g.matching=='source_matched'],'actual_source_matched':g[g.actual_source_match],'source_Qclose3':g[g.actual_source_match&g.all_blocks_history_Q_close3], 'all_teams_new_only':g[g.A_new_n.eq(g.n)&g.B_new_n.eq(g.n)&g.C_new_n.eq(g.n)]}
            subs.update({'difficulty_'+str(level):h for level,h in g.groupby('difficulty')})
            for sub,h in subs.items():
                if h.empty:rows.append(dict(phase=phase,focus_id=label,subset=sub,events=0,images=0,buildings=0));continue
                keys=['phase','method_id','domain','context_id']
                tab=a.aggregate(h,keys,a.CONTRAST_METRICS+['all_blocks_history_Q_close3','within_min_Q'])
                within=a.aggregate(h,keys,a.WITHIN_METRICS,within=True); within=within.rename(columns={c:'dedup_'+c for c in within if c not in keys})
                out=tab.merge(within,on=keys).merge(a.endpoint_table(h,keys),on=keys)
                out['focus_id']=label;out['subset']=sub;rows.extend(out.to_dict('records'))
            if label=='HQ_T_n7_5fast2slow_within':
                for w in sorted({w for ws in g.ab_workers for w in ws}):
                    h=g[~g.ab_workers.map(lambda ws:w in ws)]
                    r=dict(phase=phase,focus_id=label,excluded_worker=w,removed_pairs=len(g)-len(h),remaining_pairs=len(h),remaining_images=h.image.nunique(),remaining_buildings=h.building.nunique())
                    if len(h):
                        metrics=a.aggregate(h,['phase'],['within_joint_stable_main','within_geometry_shape_main'],within=True).iloc[0]
                        r.update({k:metrics[k] for k in ['within_joint_stable_main_building_mean','within_geometry_shape_main_building_mean']})
                    leave.append(r)
    out=HERE/'both_effects';a.csv_write(pd.DataFrame(rows),out/'FOCUSED_CONDITIONS.csv');a.csv_write(pd.DataFrame(leave),out/'HQ_N7_MEMBER_SUPPORT_SENSITIVITY.csv')
    a.write(out/'FOCUS_INTERPRETATION_NOTE.json',dict(role='Post-assessment conditional explanation of previously frozen priority vectors; not a newly validated simple-image rule.',origin='source_matched_assignment enforces class-by-source counts for A/B and overall source count for C. actual_source_matched also includes unrestricted draws that happen to have matching total source counts.',person_deletion='Remove A/B pair whenever either includes the named worker. Loss of finite-population capacity is reported; resulting different image support means this is descriptive dependence, not a causal worker effect or a new post-deletion full population experiment. No C outcomes borrowed for within support.'))
    print(json.dumps(dict(rows=len(rows),member_support_rows=len(leave))))

if __name__=='__main__':main()
