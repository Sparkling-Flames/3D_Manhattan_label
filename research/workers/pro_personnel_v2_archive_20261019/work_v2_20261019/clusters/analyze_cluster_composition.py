"""Strict fixed-k local-cluster composition versus identity changes."""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_fusion_clusters import attach_flags,summaries,paired_contrasts,collapse_contrasts
HERE=Path(__file__).resolve().parent;FUSION=HERE.parent/'fusion'

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--input',type=Path,default=FUSION/'composition_comparisons.csv.gz');a=ap.parse_args()
    out=HERE/'fusion_analysis';out.mkdir(exist_ok=True)
    labels=pd.read_csv(HERE/'assignments.csv');labels=labels[labels.method.eq('affinity') & labels.layer.eq('ordinary_manual')]
    label_map={(r.pool_id,int(r.threshold_deg),r.worker_id):r.local_cluster_id for r in labels.itertuples()}
    counts={(r.pool_id,r.worker_id):r.pair_count for r in labels[labels.threshold_deg.eq(9)].itertuples()}
    raw=pd.read_csv(a.input,low_memory=False);raw=raw[raw.comparison_family.eq('cluster_oracle_comparison') & raw.layer.eq('ordinary_manual')].copy()
    frames=[];tables=[];coverage=[];descriptive=[]
    for pid,comp in raw.groupby('pool_id',sort=True):
        comp=attach_flags(comp)
        def rep(ws,cut):
            workers=ws.split('|');co=collections.Counter(label_map[pid,int(cut),w] for w in workers);ct=collections.Counter(counts[pid,w] for w in workers)
            return json.dumps(sorted(co.items()),separators=(',',':')),json.dumps(sorted(ct.items()),separators=(',',':'))
        aa=[rep(ws,t) for ws,t in zip(comp.member_workers_a,comp.threshold)];bb=[rep(ws,t) for ws,t in zip(comp.member_workers_b,comp.threshold)]
        comp['canonical_composition_a']=[x[0] for x in aa];comp['canonical_composition_b']=[x[0] for x in bb]
        comp['point_count_hist_a']=[x[1] for x in aa];comp['point_count_hist_b']=[x[1] for x in bb]
        comp['same_local_composition']=comp.canonical_composition_a.eq(comp.canonical_composition_b)
        assert comp.same_local_composition.eq(comp.same_composition).all()
        comp['same_point_count_hist']=comp.point_count_hist_a.eq(comp.point_count_hist_b);comp['turnover']=comp.k-comp.shared_workers
        comp['threshold_deg']=comp.threshold.astype(int);comp['event_key']=[str(c)+'|'+'|'.join(sorted((x,y))) for c,x,y in zip(comp.threshold,comp.team_id_a,comp.team_id_b)]
        n=len(comp);comp=comp.drop_duplicates('event_key').copy();comp['relation']=np.where(comp.same_local_composition,'same_cluster_composition','different_cluster_composition')
        frames.append(comp)
        for cut,g in comp.groupby('threshold_deg'):
            coverage.append(dict(pool_id=pid,image_id=g.image_id.iloc[0],building_id=g.building_id.iloc[0],threshold_deg=cut,comparison_rows=len(g),
                same_composition=int(g.same_local_composition.sum()),different_composition=int((~g.same_local_composition).sum()),
                same_subset_collisions=int(g.same_subset.sum()),same_point_count_hist=int(g.same_point_count_hist.sum()),
                same_comp_different_people=int((g.same_local_composition & ~g.same_subset).sum()),
                different_comp_equal_hist=int((~g.same_local_composition & g.same_point_count_hist).sum()),
                any_failure=int(g.any_failure.sum()),quality_available=int(g.B8L2_change.notna().sum())))
        comparable=comp[~comp.same_subset & comp.same_point_count_hist].copy()
        by=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','turnover','point_count_hist_a','relation']
        if len(comparable):tables.append(summaries(comparable,by,'relation'))
        descriptive.append(summaries(comp,['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','relation'],'relation'))
    full=pd.concat(frames,ignore_index=True);full.to_csv(out/'composition_cluster_details.csv.gz',index=False)
    pd.DataFrame(coverage).to_csv(out/'composition_coverage.csv',index=False)
    pd.concat(descriptive,ignore_index=True).to_csv(out/'composition_unmatched_descriptive.csv',index=False)
    table=pd.concat(tables,ignore_index=True);table.to_csv(out/'composition_statistics.csv',index=False)
    keys=['threshold_deg','k','pool_id','image_id','image_code','building_id','difficulty','turnover','point_count_hist_a','metric']
    matched=paired_contrasts(table,keys,'relation','same_cluster_composition','different_cluster_composition',
        'changed_composition_minus_same_composition_at_same_turnover_and_point_count_hist')
    collapse_contrasts(matched,out,'composition')
    receipt=dict(input=str(a.input),input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
        ordinary_images=full.pool_id.nunique(),buildings=full.building_id.nunique(),unique_comparison_rows=len(full),
        same_subset_collisions=int(full.same_subset.sum()),retained_all_attempts=True,
        identical_k_turnover_point_count_hist=True,comparisons_are_target_annotation_oracle=True,
        matched_images=matched.image_id.nunique(),matched_buildings=matched.building_id.nunique(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'COMPOSITION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
