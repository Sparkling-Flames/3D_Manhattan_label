"""Separately summarize mean gaps/composition and secondary supports from saved rows."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage02_same_room/prediction'
rows=[];secondary=[]
for scenario in ['v2_frozen','v21_on_v2_records','v21_all']:
    d=pd.read_csv(OUT/scenario/'DIRECT_PAIRS.csv')
    x=d[d.condition.eq('manual')&d.origin.eq('all')&d.layer.eq('ordinary')&d.scope_comparable&~d.substantive_conflict&d.n_common.ge(4)]
    for scope in ['legacy_combined','ordinary_no_relation_oos_pending','relation_oos_pending']:
        z=x if scope=='legacy_combined' else x[x.oos_pending.eq(scope=='relation_oos_pending')]
        for metric,g in z.groupby('metric'):
            cs=['actual_abs_gap','common_abs_gap','composition_abs_shift','actual_minus_common_abs_gap','common_person_abs_gap','common_wasserstein']
            for weight in ['pair_equal','building_equal']:
                s=g[cs].mean() if weight=='pair_equal' else g.groupby('building_id')[cs].mean().mean()
                rows.append(dict(scenario=scenario,scope=scope,metric=metric,weighting=weight,pairs=len(g),buildings=g.building_id.nunique(),**s.to_dict()))
    d=d[d.origin.eq('all')&d.metric.eq('B8L2')&d.n_common.ge(4)]
    d=d[~(d.condition.eq('manual')&d.layer.eq('ordinary'))].copy();d['scenario']=scenario;secondary.append(d)
pd.DataFrame(rows).to_csv(OUT/'COMPOSITION_AND_MEAN_GAP_SUMMARY.csv',index=False)
pd.concat(secondary,ignore_index=True).to_csv(OUT/'SECONDARY_SEMI_DOORWAY_SUPPORT.csv',index=False)
