#!/usr/bin/env python3
"""Check immutable input binding and key Q/T results against original records."""
from pathlib import Path
import ast
import re
import json
import hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent

def main():
    for p in list((BASE/'basis').glob('*.py'))+list(OUT.glob('*.py')):
        ast.parse(p.read_text(encoding='utf-8'))
    links=[]
    for p in [BASE/'basis/README_ZH.md',OUT/'REPORT_ZH.md']:
        for ref in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if not ref.startswith(('https:','http:','#')) and not (p.parent/ref).exists():
                links.append({'doc':str(p.relative_to(ROOT)),'link':ref})
    assert not links,links
    manifests=[]
    for folder in [BASE/'basis',OUT]:
        for r in pd.read_csv(folder/'INPUT_MANIFEST.csv').itertuples():
            assert hashlib.sha256((ROOT/r.path).read_bytes()).hexdigest()==r.sha256, r.path
            manifests.append(r.path)
    raw=pd.read_csv(ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz')
    labels=pd.read_csv(BASE/'basis/WORKER_LABELS_ALL_LOBO.csv.gz')
    saved=pd.read_csv(OUT/'Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv')
    checks=[]
    conditions=[('RFUSE_GEOM_K2','C1','C2','new'),('OPPJOINT_K4','C2','C3','new'),('OPPJOINT_K4','C2','C3','v1'),('TARGET_DSTRUCT_K3','C2','C3','new'),('TARGET_DSTRUCT_K3','C1','C2','v1')]
    for method,ca,cb,origin in conditions:
        d=raw[(raw.layer=='ordinary_manual')&(raw.scope=='primary')&(raw.origin==origin)&(raw.source_active_time_seconds>0)&raw.B8L2.notna()].copy()
        lab=labels[(labels.method==method)&(labels.heldout_building!='ALL')]
        d=d.merge(lab[['worker_id','heldout_building','class_id']],left_on=['worker_id','building'],right_on=['worker_id','heldout_building'],validate='many_to_one')
        d['lt']=np.log(d.source_active_time_seconds)
        # Primary target: each image has one legal target and one record per worker.
        assert not d.duplicated(['image_id','worker_id']).any()
        g=d[d.class_id.isin([ca,cb])].groupby(['building','image_id','class_id'])[['B8L2','lt']].mean().unstack('class_id').dropna()
        dq=g[('B8L2',cb)]-g[('B8L2',ca)]
        dt=g[('lt',cb)]-g[('lt',ca)]
        x=saved[(saved.method==method)&(saved.class_A==ca)&(saved.class_B==cb)&(saved.condition=='manual')&(saved.scope=='primary')&(saved.difficulty=='ALL')&saved.source_stratum.str.startswith(origin+'|')].iloc[0]
        assert len(g)==x.n_images
        assert abs(dq.mean()-x.image_equal_delta_Q)<1e-10
        assert abs(np.exp(dt.mean())-x.image_equal_geometric_time_ratio)<1e-10
        assert abs(dq.groupby(level='building').mean().mean()-x.building_equal_delta_Q)<1e-10
        checks.append(dict(method=method,A=ca,B=cb,origin=origin,images=len(g),Q=float(dq.mean()),T_ratio=float(np.exp(dt.mean()))))
    report=dict(source_independent_QT_checks=checks,python_syntax_ok=True,owned_report_links_all_resolve=True,input_manifest_hashes_verified=len(manifests),unique_input_paths_verified=len(set(manifests)),new_fusion=0,new_scoring=0,new_classification_fit=0)
    (OUT/'VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
