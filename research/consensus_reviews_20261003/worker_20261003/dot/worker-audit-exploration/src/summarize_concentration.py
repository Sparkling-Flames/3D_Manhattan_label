from pathlib import Path
import argparse
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--restricted',type=Path,required=True)
    a=p.parse_args();g=pd.read_csv(a.results/'group_contrasts_by_image.csv');r=pd.read_csv(a.restricted/'restricted_pool_by_image.csv')
    full=g.query('evaluation_policy==calibration_policy').assign(pool='full24')
    restricted=r.query('evaluation_policy==calibration_policy and excluded_from_candidates_and_backgrounds=="P017|P002"').assign(pool='hypothetical22')
    rows=[];concentration=[]
    for (pool,method,ep),f in pd.concat([full,restricted]).groupby(['pool','method','evaluation_policy']):
        vals=f.higher_minus_lower_replacement;top=f.nlargest(3,'higher_minus_lower_replacement')
        concentration.append(dict(pool=pool,method=method,evaluation_policy=ep,positive_images=int(sum(vals>1e-12)),negative_images=int(sum(vals< -1e-12)),
            image_equal_mean=float(vals.mean()),top3_positive_contrast_sum=float(top.higher_minus_lower_replacement.sum()),
            top3_fraction_of_positive_total=float(top.higher_minus_lower_replacement.sum()/vals[vals>0].sum()),
            top3_images='|'.join(top.image),total_positive_contrast_sum=float(vals[vals>0].sum()),total_negative_contrast_sum=float(vals[vals<0].sum())))
        # Descriptive deletion of evaluated building contributions only: retain
        # each target's pre-existing LOBO calibration, no retraining or new GT use.
        for b in f.building.unique():
            left=f[f.building!=b]
            rows.append(dict(pool=pool,method=method,evaluation_policy=ep,left_out_building=b,
                equal_image=float(left.higher_minus_lower_replacement.mean()),
                equal_building=float(left.groupby('building').higher_minus_lower_replacement.mean().mean())))
    pd.DataFrame(rows).to_csv(a.results/'leave_one_building_contrast_sensitivity.csv',index=False,float_format='%.17g')
    pd.DataFrame(concentration).to_csv(a.results/'image_concentration.csv',index=False,float_format='%.17g')
if __name__=='__main__':main()
