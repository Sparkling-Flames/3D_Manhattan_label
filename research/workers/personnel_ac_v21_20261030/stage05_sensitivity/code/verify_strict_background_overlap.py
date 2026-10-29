"""Identify shared background comparisons and verify opposite sign conventions."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from analyze_population_sensitivity import save

MAP={'B8L2':'B8L2_CA','D10':'D10_CA','IoU3D100':'IoU3D100_CA','S_bottom_deg':'S_bottom_deg_CA',
 'omission':'omission_CA','extension':'extension_CA','fusion_turn_n':'fusion_turn_n_CA',
 'fusion_short_turn_edges':'fusion_short_turn_edges_CA','geometry_bev_distance':'geometry_bev_distance_AC',
 'geometry_centroid_distance':'geometry_centroid_distance_AC',
 'fusion_failure_risk':'fusion_failure_observed_risk_change_CA','incomplete_output_risk':'output_not_complete_risk_change_CA'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--broad',required=True);ap.add_argument('--strict',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    broad=pd.read_csv(a.broad);strict=pd.read_csv(a.strict);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    bm=set(broad.background_comparison_id);sm=set(strict.background_comparison_id)
    bp=set(broad.physical_background_comparison_id);sp=set(strict.physical_background_comparison_id)
    shared=bm&sm;rows=[]
    for sid in sorted(shared):
        br=broad[broad.background_comparison_id.eq(sid)].iloc[0]
        for _,sr in strict[strict.background_comparison_id.eq(sid)&strict.metric.isin(MAP)].iterrows():
            value=br[MAP[sr.metric]+'__effect_difference'];other=sr.F_minus_B_effect
            assert pd.isna(value)==pd.isna(other),(sid,sr.metric,value,other)
            error=value+other if pd.notna(value) else np.nan
            if pd.notna(error):assert abs(error)<1e-8,(sid,sr.metric,error)
            rows.append(dict(background_comparison_id=sid,physical_background_comparison_id=br.physical_background_comparison_id,
                pool_id=br.pool_id,method=br.method,metric=sr.metric,broad_outside_minus_neutral=value,
                strict_F_minus_B=other,sign_reversal_error=error))
    save(pd.DataFrame(rows),out/'STRICT_SHARED_BACKGROUND_SIGN_VALIDATION.csv.gz')
    receipt={'broad_method_comparisons':len(bm),'strict_method_comparisons':len(sm),'overlapping_method_comparisons':len(shared),
        'union_method_comparisons':len(bm|sm),'broad_physical_comparisons':len(bp),'strict_physical_comparisons':len(sp),
        'overlapping_physical_comparisons':len(bp&sp),'union_physical_comparisons':len(bp|sp),
        'shared_method_ids':sorted(shared),'metric_checks':len(rows),'all_shared_signs_verified':True,
        'sign_convention':'broad = delta_outside - delta_neutral; strict = delta_F_neutral - delta_B_outside. Shared signed values are negatives, symmetric absolute amplitudes agree.',
        'broad_sha256':hashlib.sha256(Path(a.broad).read_bytes()).hexdigest(),
        'strict_sha256':hashlib.sha256(Path(a.strict).read_bytes()).hexdigest()}
    (out/'STRICT_BACKGROUND_OVERLAP_VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
