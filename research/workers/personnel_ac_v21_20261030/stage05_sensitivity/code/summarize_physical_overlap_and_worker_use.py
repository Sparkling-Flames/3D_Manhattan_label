"""Summarize shared physical evidence and actual worker exposure from all pools."""
from pathlib import Path
import argparse,json,hashlib,gzip,csv
import pandas as pd
from analyze_population_sensitivity import save


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    source=Path(a.results);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    assert len(list((source/'pool_shards').glob('*/COMPLETE.json')))==258
    ov=pd.concat([pd.read_csv(p) for p in sorted((source/'pool_shards').glob('*/PHYSICAL_METHOD_OVERLAP.csv.gz'))],ignore_index=True)
    keys=['scope','condition','layer','method_A','method_B'];rows=[]
    for key,g in ov.groupby(keys,sort=False,dropna=False):
        r=dict(zip(keys,key));r.update(pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
            images_with_shared_pairs=g.loc[g.shared_physical_pairs.gt(0),'image'].nunique(),
            buildings_with_shared_pairs=g.loc[g.shared_physical_pairs.gt(0),'building'].nunique())
        for c in ['A_physical_pairs','B_physical_pairs','shared_physical_pairs','A_unique_teams','B_unique_teams','shared_teams']:r[c]=int(g[c].sum())
        r['pair_jaccard']=r['shared_physical_pairs']/(r['A_physical_pairs']+r['B_physical_pairs']-r['shared_physical_pairs'])
        rows.append(r)
    save(pd.DataFrame(rows),out/'METHOD_PAIR_PHYSICAL_OVERLAP_SUMMARY.csv.gz')
    use=pd.concat([pd.read_csv(p) for p in sorted((source/'pool_shards').glob('*/MEMBER_USAGE.csv.gz'))],ignore_index=True)
    keys=['scope','condition','layer','method'];denom=use.drop_duplicates(keys+['pool_id']).groupby(keys).total_method_unique_endpoints.sum()
    rows=[]
    for key,g in use.groupby(keys+['worker_id'],sort=False,dropna=False):
        r=dict(zip(keys+['worker_id'],key));r.update(used_pools=g.pool_id.nunique(),used_images=g.image.nunique(),used_buildings=g.building.nunique(),
            distinct_frozen_classes_encountered='|'.join(sorted(g.frozen_class.astype(str).unique())),
            member_endpoint_incidences=int(g.unique_used_endpoints.sum()),
            method_total_physical_teams=int(denom.loc[key[:-1]]),
            X_event_exposures=int(g.X_event_exposures.sum()),Z_event_exposures=int(g.Z_event_exposures.sum()),D_event_exposures=int(g.D_event_exposures.sum()),
            image_balanced_endpoint_presence_fraction_when_used=float(g.groupby('image').endpoint_presence_fraction.mean().mean()))
        r['fraction_of_all_method_teams_containing_worker']=r['member_endpoint_incidences']/r['method_total_physical_teams']
        rows.append(r)
    save(pd.DataFrame(rows),out/'WORKER_USAGE_BY_METHOD_AND_SCOPE.csv.gz')
    checks=[]
    for p in out.glob('*.csv.gz'):
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            rd=csv.reader(f);h=next(rd);n=0
            for row in rd:assert len(row)==len(h);n+=1
        checks.append(dict(file=p.name,rows=n,full_gzip_eof=True,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    receipt={'all_pool_checkpoints':258,'input_overlap_rows':len(ov),'input_worker_rows':len(use),
        'warning':'Method-pair intersections overlap each other and must not be summed into a unique shared-evidence total; worker exposures are design incidence, not independent observations.',
        'files':checks,'new_teams':0,'new_scores':0}
    (out/'IDENTITY_SUPPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
