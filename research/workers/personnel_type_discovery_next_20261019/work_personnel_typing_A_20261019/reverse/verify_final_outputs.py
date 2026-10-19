#!/usr/bin/env python3
"""Final streaming integrity and exchange-key checks on frozen reverse outputs."""
from pathlib import Path
import gzip,hashlib,json,time
import pandas as pd

HERE=Path(__file__).resolve().parent


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1<<20):h.update(b)
    return h.hexdigest()


def main():
    start=time.time();checks=[];p=HERE/'results'
    for path in sorted(HERE.rglob('*.csv.gz')):
        if 'input_schema_probe' in path.parts:continue
        n=0
        with gzip.open(path,'rb') as f:
            while b:=f.read(1<<20):n+=b.count(b'\n')
        row={'path':str(path.relative_to(HERE)),'sha256':sha(path),'bytes':path.stat().st_size,'csv_lines_without_header':n-1,'gzip_crc_pass':True}
        if path.name=='predictions.csv.gz':
            complete=json.loads((path.parent/'COMPLETE.json').read_text())
            assert n-1==69*complete['n_test_events']
            row['expected_prediction_rows']=69*complete['n_test_events']
        checks.append(row)
    c=pd.read_csv(p/'all_candidate_classes.csv.gz')
    assert len(c)==186300 and not c.duplicated(['method_id','fold_id','domain','worker_id']).any()
    assert c.groupby(['method_id','fold_id','domain']).size().eq(60).all()
    rel=pd.read_csv(p/'all_pair_relations.csv.gz')
    assert len(rel)==162840 and not rel.duplicated(['fold_id','domain','worker_a','worker_b']).any()
    assert (rel.worker_a<rel.worker_b).all()
    rules=pd.read_csv(HERE/'explanations/rule_classes.csv.gz')
    assert len(rules)==9660 and not rules.duplicated(['method_id','fold_id','domain','worker_id']).any()
    manifests=json.loads((p/'PREDICTION_MANIFEST.json').read_text())['fold_files']
    verified={r['path']:r for r in checks}
    for r in manifests:
        assert r['sha256']==verified['results/'+r['path']]['sha256']
    e=json.loads((HERE/'explanations/RECEIPT.json').read_text())
    for path,expected in e['input_sha256'].items():assert sha(Path(path))==expected
    receipt={'all_checks_passed':True,'checked_gzip_exports':len(checks),'excluded':'input_schema_probe copies separately SHA-checked by PROBE_BOOTSTRAP_PARITY',
             'class_rows':len(c),'class_unique_key':'method_id,fold_id,domain,worker_id','workers_per_method_fold_domain':60,
             'person_pair_rows':len(rel),'person_pair_unique_key':'fold_id,domain,worker_a,worker_b','rule_rows':len(rules),
             'prediction_folds':len(manifests),'prediction_rows':sum(r.get('expected_prediction_rows',0) for r in checks),
             'explanation_input_hashes_still_match':True,'seconds':time.time()-start,'checks':checks}
    (HERE/'FINAL_OUTPUT_INTEGRITY.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print({k:v for k,v in receipt.items() if k!='checks'},flush=True)


if __name__=='__main__':main()
