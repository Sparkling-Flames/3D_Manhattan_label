"""Check only the final unverified strict-bridge fields and global count patch.

The 5,767 completed core checks are not rerun or overwritten.  This supplemental
read-only verification closes the non-mean field coverage explicitly.
"""
from pathlib import Path
import importlib.util
import json

import numpy as np

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit_ac',ROOT/'tools/thesis_main/analysis/audit_manual_order_ac_acceptance_20261104.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
OLD=a.OLD;CACHE=a.CACHE


def main():
    strict=[a.read(CACHE/'STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz'),
            a.read(OLD/'strict_bridge/STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz')]
    changes=a.read(OLD/'strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz')
    computed=[];expected=[]
    for r in changes.to_dict('records'):
        for side,prefix in enumerate(['automatic_','assisted_']):
            d=a.pick(strict[side],r,['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'])
            d=d[d.new_AC_condition_match.eq('both')]
            scalar=r['metric'] not in ['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
            col='strict_signed_CA_mean' if scalar else 'absolute_CA_mean'
            z=d[d[col].notna()&d.new_strict_direction_signed_or_distance_mean.notna()]
            rr=dict(matched_target_pools=len(d),jointly_evaluable_pools=len(z),buildings=z.building.nunique(),
                strict_signed_or_distance_mean=z[col].mean(),direct_AC_signed_or_distance_mean=z.new_strict_direction_signed_or_distance_mean.mean(),
                strict_absolute_CA_mean=z.absolute_CA_mean.mean(),direct_AC_absolute_CA_mean=z.new_absolute_change_mean.mean(),
                strict_within_AB_mean=z.within_AB_mean.mean(),strict_G_A_mean=z.G_A_mean.mean(),strict_G_S_mean=z.G_S_mean.mean(),
                strict_G_A_positive_pools=z.G_A_mean.gt(1e-9).sum(),strict_G_A_valid_pools=z.G_A_mean.notna().sum(),
                direct_AC_positive_pools=z.new_strict_direction_signed_or_distance_mean.gt(1e-9).sum() if scalar else np.nan,
                direct_AC_negative_pools=z.new_strict_direction_signed_or_distance_mean.lt(-1e-9).sum() if scalar else np.nan,
                signed_direction_agreement_pools=(np.sign(z[col])==np.sign(z.new_strict_direction_signed_or_distance_mean)).sum() if scalar else np.nan)
            computed.append(rr);expected.append({c[len(prefix):]:v for c,v in r.items() if c.startswith(prefix)})
    a.compare_record_values('strict_bridge_all_numeric_fields_supplement',computed,expected)
    flags=['Q_missing','fusion_execution_exception','fusion_structural_failure','output_invalid_geometry',
           'fusion_failure_observed','measurement_exception','reference_floor_only','output_not_complete']
    sk=['condition','layer','scope','low_key_output_state','high_key_output_state','low_key_score_status','high_key_score_status']
    sk+=['low_key_'+x for x in flags]+['high_key_'+x for x in flags]
    def patch(base,old,new,keys,fields):
        aa=a.attach_id(base,keys);bb=a.attach_id(old,keys);cc=a.attach_id(new,keys)
        return aa[fields].subtract(bb[fields],fill_value=0).add(cc[fields],fill_value=0)
    name='GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv'
    fields=['unique_physical_pairs','target_pools']
    counts=patch(a.read(CACHE/name),a.read(OLD/'states/automatic'/name),a.read(OLD/'states/assisted'/name),sk,fields)
    actual=a.attach_id(a.read(OLD/'states'/name),sk)
    counts=counts[counts.unique_physical_pairs.gt(0)].reindex(actual.index)
    a.assert_close('global_physical_counts_fresh_frozen_patch',counts,actual[fields],fields=json.dumps(fields))
    name='UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv'
    fields=['unique_requested_teams','target_pools'];tk=['condition','layer','scope','output_state','score_status']+flags
    counts=patch(a.read(CACHE/name),a.read(OLD/'states/automatic'/name),a.read(OLD/'states/assisted'/name),tk,fields)
    actual=a.attach_id(a.read(OLD/'states'/name),tk)
    counts=counts[counts.unique_requested_teams.gt(0)].reindex(actual.index)
    a.assert_close('global_team_counts_fresh_frozen_patch',counts,actual[fields],fields=json.dumps(fields))
    import pandas as pd
    a.save(pd.DataFrame(a.AUDITS),OUT/'SUPPLEMENTAL_CONSUMER_FIELD_CHECKS.csv')
    receipt=dict(status='PASS',checks=len(a.AUDITS),numeric_cells=sum(x['numeric_cells'] for x in a.AUDITS),
                 mismatches=0,original_5767_checks_rerun=False,new_scores=0,
                 coverage=['all numeric fields in 42 affected strict-bridge summary rows, both versions',
                           'global physical-pair and unique-team state counts and target-pool counts from fresh frozen source minus old local plus assisted local'],
                 excluded_fresh_rederivation='Global state-cell building counts retain prior frozen set-membership witnesses in states/BUILDING_SUPPORT_AMBIGUITIES.json; no full-domain event reread claimed.',
                 sources=[str(p.relative_to(ROOT)) for p in sorted(a.RUNTIME_INPUTS)])
    a.jsave(OUT/'SUPPLEMENTAL_CONSUMER_FIELD_CHECKS.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
