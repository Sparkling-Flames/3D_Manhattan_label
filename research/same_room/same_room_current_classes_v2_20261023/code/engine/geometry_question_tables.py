"""Hierarchy-balanced geometry summaries of the paired finite-panel experiment.

Primary: ordinary comparable Manual, replicate 0, clipped floor(N/2).
Average finite-event summaries over panels, direct pairs, adopted groups, and
buildings, in that order. Counts are unweighted support before group expansion.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

RATES = {
 'both_same_count_rate':('both_same_count_n','attempted'),
 'both_complete_rate':('both_complete_comparisons_n','attempted'),
 'joint_distance_available_rate':('joint_valid_distance_n','attempted'),
 'both_exact_geometry_unchanged_rate':('exact_unchanged_both_n','joint_valid_distance_n'),
 'both_cyclic_geometry_unchanged_rate':('cyclic_unchanged_both_n','joint_valid_distance_n'),
 'both_position_small_rate':('position_small_both_n','joint_valid_distance_n'),
 'only_a_position_large_rate':('position_a_large_only_n','joint_valid_distance_n'),
 'only_b_position_large_rate':('position_b_large_only_n','joint_valid_distance_n'),
 'both_position_large_rate':('position_large_both_n','joint_valid_distance_n'),
}
MEANS = [
 'q_abs_effect_difference_mean','geom_abs_effect_difference_mean',
 'bev_mean_h_a_mean','bev_mean_h_b_mean','bev_max_h_a_mean','bev_max_h_b_mean',
 'top_mean_h_a_mean','top_mean_h_b_mean',
 'bottom_angular_mean_deg_a_mean','bottom_angular_mean_deg_b_mean',
 'top_angular_mean_deg_a_mean','top_angular_mean_deg_b_mean',
 'signed_height_change_mean_h_a_mean','signed_height_change_mean_h_b_mean',
 'bev_effect_crossview_corr','q_effect_crossview_corr',
 'bev_vs_absolute_q_effect_corr_a','bev_vs_absolute_q_effect_corr_b',
]
KEYS=['actual_m','net_high_count_change','kind']


def analysis_subsets(d):
    """Same explicit condition layers as analysis/analyze_exact_changes.py."""
    door=d.layer_a.astype(str).str.contains('doorway')|d.layer_b.astype(str).str.contains('doorway')
    ordinary=d.ordinary_comparable.astype(bool);scope=d.scope_comparable.astype(bool)
    return [('ordinary_mid',d[ordinary&(d.n==d.mid_n)&(d.replicate==0)]),
            ('ordinary_all_n',d[ordinary]),
            ('doorway_involved',d[~ordinary&door]),
            ('scope_different',d[~ordinary&~door&~scope]),
            ('other_adoption_state',d[~ordinary&~door&scope])]


def support(g):
    groups=set('|'.join(g.groups.fillna('').astype(str)).split('|'))-{''}
    return dict(panels=int(g.panel_id.nunique()),pairs=int(g.pair_key.nunique()),
        images=len(set(g.image_a)|set(g.image_b)),groups_n=len(groups),
        buildings=int(g.building.nunique()),attempted_contrasts=int(g.attempted.sum()),
        joint_valid_distance_contrasts=int(g.joint_valid_distance_n.sum()),
        four_complete_contrasts=int(g.both_complete_comparisons_n.sum()),
        joint_q_contrasts=int(g.q_joint_n.sum()))


def attach_support(average,source,keys):
    counts=[dict(zip(keys,key if isinstance(key,tuple) else (key,)),**support(g))
            for key,g in source.groupby(keys,dropna=False)]
    return average.merge(pd.DataFrame(counts),on=keys,validate='one_to_one')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--main-m1-input',action='store_true',help='Input is the distributed ordinary-mid replicate-0 m=1 subset; do not label it all-n or other-condition evidence.')
    a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.input)
    if d.empty:raise ValueError('No complete panel summary is available.')
    d['mid_n']=[max(3,int(k),min(int(N)-int(k),int(N)//2)) for k,N in zip(d.k_selected,d.known_common_n)]
    d['kind']=np.where(d.net_high_count_change.eq(0),'same_composition',np.where(d.net_high_count_change.eq(d.actual_m),'pure_class_block','mixed_class_block'))
    for name,(num,den) in RATES.items():d[name]=d[num].div(d[den].replace(0,np.nan))
    d['one_view_position_large_rate']=d.only_a_position_large_rate+d.only_b_position_large_rate
    d['average_view_bev_mean_h']=(d.bev_mean_h_a_mean+d.bev_mean_h_b_mean)/2
    metrics=list(RATES)+['one_view_position_large_rate','average_view_bev_mean_h']+MEANS
    for name in ['q_abs_effect_difference','geom_abs_effect_difference','bev_mean_h_a','bev_mean_h_b']:
        new_name=name+'_panel_p90_mean';d[new_name]=d[name+'_p90'];metrics.append(new_name)
    values=d[list(RATES)].dropna().to_numpy()
    assert (values>=-1e-10).all() and (values<=1+1e-10).all()
    pos=d[['both_position_small_rate','one_view_position_large_rate','both_position_large_rate']].dropna()
    assert np.allclose(pos.sum(axis=1),1.)
    selections=analysis_subsets(d)
    if a.main_m1_input:
        assert d.ordinary_comparable.eq(True).all() and d.replicate.eq(0).all() and d.n.eq(d.mid_n).all() and d.actual_m.eq(1).all()
        selections=[selections[0]]
    main=selections[0][1]
    m1=main[main.actual_m.eq(1)]
    common=set(m1.loc[m1.net_high_count_change.eq(0),'panel_id']) & set(m1.loc[m1.net_high_count_change.eq(1),'panel_id'])
    selections.append(('ordinary_mid_common_m1_panels',m1[m1.panel_id.isin(common)]))
    for family in sorted(main.selected_family.dropna().unique()):
        selections.append(('ordinary_mid_selected_family_'+str(family),main[main.selected_family.eq(family)]))
        selections.append(('ordinary_mid_common_m1_selected_family_'+str(family),m1[m1.panel_id.isin(common)&m1.selected_family.eq(family)]))
    pair_rows=[];group_rows=[];building_rows=[];summary_rows=[];long_rows=[]
    for subset,dd in selections:
        if dd.empty:continue
        pairkeys=KEYS+['building','pair_key','groups','image_a','image_b',
            'ordinary_comparable','relation_tier','scope_comparable','layer_a','layer_b','difficulty_a','difficulty_b',
            'method','selected_family']
        pair=dd.groupby(pairkeys,dropna=False)[metrics].mean().reset_index()
        expanded=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id')
        expanded=expanded[expanded.group_id.notna()&expanded.group_id.ne('')]
        groupkeys=KEYS+['building','group_id','method','selected_family']
        group=expanded.groupby(groupkeys,dropna=False)[metrics].mean().reset_index()
        buildingkeys=KEYS+['building','method','selected_family']
        building=group.groupby(buildingkeys,dropna=False)[metrics].mean().reset_index()
        for key,bb in building.groupby(KEYS,dropna=False):
            select=np.ones(len(dd),dtype=bool)
            for name,val in zip(KEYS,key):select &= dd[name].eq(val).to_numpy()
            sr=dd.loc[select];z=dict(subset=subset,**dict(zip(KEYS,key)),**support(sr))
            z.update({m:float(bb[m].mean()) for m in metrics});summary_rows.append(z)
            ps=np.ones(len(pair),dtype=bool);gs=np.ones(len(group),dtype=bool)
            for name,val in zip(KEYS,key):ps &=pair[name].eq(val).to_numpy();gs &=group[name].eq(val).to_numpy()
            pp,gg=pair.loc[ps],group.loc[gs]
            for metric in metrics:
                fp=sr[sr[metric].notna()];fpa=pp[pp[metric].notna()];fg=gg[gg[metric].notna()];fb=bb[bb[metric].notna()]
                long_rows.append(dict(subset=subset,**dict(zip(KEYS,key)),metric=metric,
                    hierarchy_equal_mean=float(bb[metric].mean()),
                    pair_equal_sensitivity_mean=float(pp[metric].mean()),
                    group_equal_sensitivity_mean=float(gg[metric].mean()),
                    supported_panels=len(fp),supported_pairs=len(fpa),supported_groups=len(fg),supported_buildings=len(fb),
                    building_median=float(fb[metric].median()) if len(fb) else np.nan,
                    building_min=float(fb[metric].min()) if len(fb) else np.nan,
                    building_max=float(fb[metric].max()) if len(fb) else np.nan,
                    total_attempted_contrasts=z['attempted_contrasts'],total_joint_valid_distance_contrasts=z['joint_valid_distance_contrasts']))
        pair=attach_support(pair,dd,pairkeys)
        expanded_panels=dd.assign(group_id=dd.groups.str.split('|')).explode('group_id')
        group=attach_support(group,expanded_panels,groupkeys)
        group['groups_n']=1
        building=attach_support(building,dd,buildingkeys)
        for frame,sink in [(pair,pair_rows),(group,group_rows),(building,building_rows)]:frame['subset']=subset;sink.append(frame)
    pd.concat(pair_rows,ignore_index=True).to_csv(out/'GEOMETRY_BY_PAIR.csv.gz',index=False)
    pd.concat(group_rows,ignore_index=True).to_csv(out/'GEOMETRY_BY_GROUP.csv.gz',index=False)
    pd.concat(building_rows,ignore_index=True).to_csv(out/'GEOMETRY_BY_BUILDING.csv',index=False)
    summary=pd.DataFrame(summary_rows);summary.to_csv(out/'GEOMETRY_SUMMARY_BUILDING_EQUAL.csv',index=False)
    long=pd.DataFrame(long_rows);long.to_csv(out/'GEOMETRY_QUESTION_SUMMARY_LONG.csv',index=False)
    long[long.actual_m.eq(1)].to_csv(out/'GEOMETRY_M1_QUESTION_SUMMARY.csv',index=False)
    definition=dict(source_input=str(Path(a.input).resolve()),completed_panels=int(d.panel_id.nunique()),
      attempted_exact_adjustments=int(d.attempted.sum()),
      source_scope='distributed main-budget m=1 strata only' if a.main_m1_input else 'full saved finite-panel geometry summaries',
      primary_condition='ordinary comparable Manual; replicate 0; n=max(3,k,min(N-k,floor(N/2)))',
      secondary_conditions='ordinary_all_n retains all budgets and replicates; nonordinary strata use doorway_involved, scope_different, other_adoption_state, in that priority order',
      matched_comparison='ordinary_mid_common_m1_panels restricts the one-member r=0/r=1 comparison to the same panels with both adjustment types; all primary data remain separately reported',
      selected_family='TURN/JOINT are internal families of adopted V3_BEHAVIOR; here JOINT combines E/R/G structural-behavior axes, not the independent V3_JOINT_QT quality/time taxonomy. No family is removed from the primary result',
      distance_means='per-view distance means use each view own valid same-count comparisons; geometry effect gap and position-state rates use joint valid correspondence. Do not treat their supports as identical',
      r0='same high/low class counts, actual member replacement',
      r_positive='net increase in historically more-turn class; pure class block only when r=m',
      weighting='finite-event summary within panel/m/r -> equal panels within direct image pair -> equal pairs within adopted group -> equal groups within building -> equal buildings',
      overlap='original groups may overlap; expansion preserves adoption and is not a count of independent rooms',
      support_counts='unweighted finite-event counts before group expansion; group-level support may overlap',
      missing='each metric uses only panels with that metric; supported panel/pair/group/building counts retained',
      percentile='panel_p90_mean is hierarchy-weighted mean of finite-event panel p90s, not pooled p90',
      correlations='descriptive panel correlations arithmetically averaged, not inference or pooled correlation',
      position_small='mean corresponding BEV distance <=0.02 camera heights; unique same-count correspondence in both views',
      unequal_count='unavailable for matched-corner distance; never assigned zero or a large sentinel distance',
      geometry='two within-view before/after comparisons; no cross-camera geometry registration',
      time='no time-cost comparison added here')
    (out/'QUESTION_TABLE_DEFINITION.json').write_text(json.dumps(definition,ensure_ascii=False,indent=2))
    print(json.dumps(dict(input_panels=int(d.panel_id.nunique()),summary_rows=len(summary),long_rows=len(long))))


if __name__=='__main__':main()
