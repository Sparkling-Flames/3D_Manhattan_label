"""Identity, approved-processing and output conservation checks (not semantic validation)."""
from pathlib import Path
import gzip,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1]
def run():
    p=R/'inputs/frozen/human/responses.jsonl.gz';a={r['canonical_annotation_id']:r for r in (json.loads(l)for l in gzip.open(p,'rt'))}
    q=R/'model_snapshot/sop_sources/analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
    b={r['canonical_annotation_id']:r for r in (json.loads(l)for l in gzip.open(q,'rt'))}
    assert a.keys()==b.keys()
    fields=['effective_points_1024x512','processing_status','calculation_included','imputed_point']
    for cid in a:
        for field in fields:assert a[cid][field]==b[cid][field],(cid,field)
    au=pd.read_csv(R/'results/all_response_audit.csv');mem=pd.read_csv(R/'results/memberships.csv');ps=pd.read_csv(R/'results/pointset_memberships.csv')
    assert len(au)==2501 and au.id.nunique()==2501
    assert not mem.worker.isin(['W019','W026']).any() and not ps.worker.isin(['W019','W026']).any()
    assert mem.groupby('method').id.nunique().eq(2364).all()
    assert ps.groupby('method').id.nunique().eq(2381).all()
    x=mem[(mem.code=='X7HyMhZNoso-19')&(mem.condition=='manual')&(mem.method=='A3_cyclic_cut08')]
    groups={frozenset(v.worker)for _,v in x.groupby('cluster')}
    assert groups=={frozenset(['W011','W015','W033']),frozenset(['W034']),frozenset(['W037'])}
    md=pd.read_csv(R/'results/human_model_distances.csv');assert md.id.nunique()==len(md)==2299
    val={'canonical_identity_match':2501,'SOP_fields_equal':fields,'source_human_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_reviewed_sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'workers_excluded_before_clustering':['W019','W026'],'paired_records_per_configuration':2364,'pointset_records_per_configuration':2381,'paired_configurations':mem.method.nunique(),'pointset_configurations':ps.method.nunique(),'x7_cut8_exact_worker_partition_verified':True,'semantic_validation':False,'new_visual_review_all214':False,'raw_or_main_mutated':False}
    (R/'results/source_and_invariance_tests.json').write_text(json.dumps(val,ensure_ascii=False,indent=2))
    print(json.dumps(val,indent=2))
if __name__=='__main__':run()
