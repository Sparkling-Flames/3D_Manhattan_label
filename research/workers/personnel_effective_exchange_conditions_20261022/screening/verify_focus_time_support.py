"""Confirm the actual time units, complete-member coverage and source parity."""
from __future__ import annotations
from common_screening import *

def main():
    focus=pd.read_csv(HERE/'FOCUS_EVENT_MEMBERSHIP.csv.gz')
    focus=focus[focus.focus_id.str.startswith(('MV_manual','MV_semi','F01_'))]
    wanted=set(focus.event_id)
    fields=['event_id','pool_id','image','building','condition','source_domain','n','common_background','team_A','team_B','team_C',
            'cross_recorded_time_pct','same_recorded_time_pct','recorded_time_pct']
    fields += [f'endpoint_{a}__{s}' for a in 'ABC' for s in ['source_time_known_n','source_time_total_seconds','time_source_kinds','time_source_table']]
    parts=[]
    for stage,condition,path in event_sources(stages=['PURE','PURE_CROSS']):
        d=pd.read_csv(path,usecols=lambda c:c in fields,low_memory=False)
        z=d[d.event_id.isin(wanted)].copy()
        if len(z):parts.append(z)
    d=focus.merge(pd.concat(parts,ignore_index=True),on='event_id',validate='many_to_one')
    rows=[]
    for r in d.to_dict('records'):
        arms='ABC' if r['comparison']=='ABC_matched' else 'AC'
        sources=[r[f'endpoint_{a}__time_source_kinds'] for a in arms]
        complete=all(r[f'endpoint_{a}__source_time_known_n']==r['n'] for a in arms)
        same_source=len(set(sources))==1 and not pd.isna(sources[0]) and '|' not in sources[0]
        ta=r['endpoint_A__source_time_total_seconds'];tc=r['endpoint_C__source_time_total_seconds']
        reported=r.get('cross_recorded_time_pct',np.nan)
        if pd.isna(reported):reported=r.get('recorded_time_pct',np.nan)
        pct=100*(tc/ta-1) if ta>0 and tc>0 else np.nan
        r.update(time_units='seconds',time_measure='sum of complete member recorded times',
          cross_arm_all_member_times_known=complete,all_available_arms_same_single_source=same_source,
          independent_C_minus_A_percent=pct,archived_C_minus_A_percent=reported,
          abs_recompute_difference=abs(pct-reported),
          interpretation='Recorded person-seconds from processed reporting; not raw-log replay or elapsed wall-clock time.')
        assert complete and same_source and abs(pct-reported)<1e-9,r['event_id']
        rows.append(r)
    table=pd.DataFrame(rows)
    receipt=save_csv('FOCUS_TIME_SOURCE_AND_TOTALS.csv',table)
    rows=[]
    for key,g in table.groupby(['focus_id','orientation','comparison']):
        image=g.groupby(['building','image']).independent_C_minus_A_percent.mean()
        b=image.groupby('building').mean()
        rows.append(dict(zip(['focus_id','orientation','comparison'],key),events=len(g),images=g.image.nunique(),
          buildings=g.building.nunique(),complete_member_times_all_events=bool(g.cross_arm_all_member_times_known.all()),
          same_single_source_all_events=bool(g.all_available_arms_same_single_source.all()),
          time_source_kinds='|'.join(sorted(g.endpoint_A__time_source_kinds.unique())),unit='seconds',
          mean_CminusA_pct_building=b.mean(),median_CminusA_pct_building=b.median(),
          time_reduced_images=int(image.lt(0).sum()),time_increased_images=int(image.gt(0).sum()),
          time_reduced_buildings=int(b.lt(0).sum()),time_increased_buildings=int(b.gt(0).sum()),
          max_recompute_difference=g.abs_recompute_difference.max()))
    summary=pd.DataFrame(rows);sr=save_csv('FOCUS_TIME_SUPPORT_SUMMARY.csv',summary)
    save_json('FOCUS_TIME_VERIFICATION.json',dict(status='complete',files=[receipt,sr],native_calls=0,
      source_table='research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz',
      raw_time_field='source_active_time_seconds',endpoint_sum_field='source_time_total_seconds',
      new_source_kind='user_processed_reported_not_raw_log_replayed',all_focus_time_members_known=True,
      all_available_arms_same_time_source=True,all_percentages_independently_recomputed=True,
      not_wallclock_or_parallel_elapsed_time=True))
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
