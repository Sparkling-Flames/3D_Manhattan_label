#!/usr/bin/env python3
"""Recompute this extension beside the byte-preserved repaired prior delivery.

Usage from the common extracted root:
  python structure_height_preference_20261012/run_reproduction.py
  python structure_height_preference_20261012/run_reproduction.py --with-review

The previous 386 manifested files and its manifest are checked before and after.
Only the extension's result directories are rewritten. Run in a fresh extraction
to retain a byte-identical delivery copy. No network access is required.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parent


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def verify_sources():
    old=ROOT/'FILE_MANIFEST_SHA256.json'
    if not old.is_file():
        raise RuntimeError('Extract the repaired prior archive first, then the extension into the same root; missing prior manifest.')
    expected='b836c7c6e628b65ee60518666c99509707b59c66ef28f8a42c2a07c03e277174'
    assert sha(old)==expected, 'This reproduction targets the byte-preserved repaired v1 prior delivery.'
    manifest=json.loads(old.read_text())
    verified=[]
    for r in manifest['files']:
        p=ROOT/r['path']
        assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'], 'Prior input changed: '+r['path']
        verified.append(r['path'])
    assert len(verified)==386
    main=json.loads((STUDY/'inputs/main_source_manifest.json').read_text())
    assert main['main_sha']=='a7ff459e992769c944541800dbe3be6e4b83ae4b'
    for r in main['entries']:
        p=STUDY/'inputs/main_snapshot'/r['path']
        b=p.read_bytes()
        assert len(b)==r['bytes'] and sha(p)==r['sha256']
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['git_blob_sha']
    return {'prior_manifest_sha256':expected,'prior_files_checked':len(verified)+1,
            'main_sha':main['main_sha'],'exact_main_files_checked':len(main['entries'])}


TARGETS = [
    'evidence/results/qualification_summary.json',
    'structure/results/synthetic_metrics.csv',
    'structure/results/real39_structural_metrics.csv',
    'structure/results/development907_structural_metrics.csv',
    'structure/results/real39_same_curve_invariance.csv',
    'height/results/candidate_scores_39.json',
    'height/results/candidate_scores_structure_controls.csv',
    'height/results/candidate_scores_prior_height71.csv',
    'height/results/matched_control_scores.csv',
    'height/results/development907_height_profiles.csv',
    'height/results/development907_candidates.json',
    'representation/results/current_input_diagnostics_922.csv',
    'representation/results/controlled_input_vs_result.csv',
    'representation/results/old24_input_score_probes.csv',
    'evidence/new_candidate_comparison/old24_rank_summary.csv',
    'evidence/new_candidate_comparison/same_budget_two_cutpoint_summary.json',
    'evidence/new_candidate_comparison/pending_scenarios.csv',
    'evidence/new_candidate_comparison_log_addendum/old24_rank_summary.csv',
    'evidence/model_results/grouped_summary.csv',
    'evidence/model_extensions/grouped_summary.csv',
    'evidence/model_controls/global_height_failure_summary.json',
    'evidence/fixed_fusion_demo/scored_fixed_rows_71.csv',
    'evidence/fixed_fusion_demo/balanced_three_image_worker_descriptives.csv',
    'analysis/results/key_candidate_comparison.csv',
    'analysis/results/key_real_cases.csv',
    'analysis/results/T20_denominator_audit.json',
]


def read_table(path):
    if path.suffix=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    return json.loads(path.read_text())


def compare(a,b,path='',stats=None):
    if stats is None:stats={'numeric_cells':0,'max_abs_numeric_delta':0.0,'structural_or_text_cells':0}
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b), 'Dictionary keys changed at '+path
        for k in a:compare(a[k],b[k],path+'/'+k,stats)
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b), 'List shape changed at '+path
        for i,(aa,bb) in enumerate(zip(a,b)):compare(aa,bb,path+'/'+str(i),stats)
    else:
        # CSV numeric strings and actual JSON numbers receive the same check.
        # Booleans, missing values, identifiers, labels and qualifications are exact.
        numeric = isinstance(a,(int,float)) and not isinstance(a,bool)
        aa=bb=None
        if isinstance(a,str) and isinstance(b,str):
            try:aa=float(a);bb=float(b);numeric=math.isfinite(aa) and math.isfinite(bb)
            except ValueError:pass
        if numeric:
            aa=float(a) if aa is None else aa;bb=float(b) if bb is None else bb
            if not (math.isfinite(aa) and math.isfinite(bb)):
                assert a==b, 'Nonfinite value changed at '+path
            else:
                delta=abs(aa-bb)
                assert math.isclose(aa,bb,rel_tol=1e-8,abs_tol=1e-7), f'Numeric mismatch at {path}: {aa} != {bb}'
                stats['numeric_cells']+=1;stats['max_abs_numeric_delta']=max(stats['max_abs_numeric_delta'],delta)
        else:
            assert a==b, f'Value changed at {path}: {a!r} != {b!r}'
            stats['structural_or_text_cells']+=1
    return stats


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--with-review',action='store_true',help='Also reconstruct the provided image plates and review HTML from included originals.')
    args=ap.parse_args()
    logs=STUDY/'verification/reproduction_logs';logs.mkdir(parents=True,exist_ok=True)
    before_sources=verify_sources()
    expected={name:read_table(STUDY/name) for name in TARGETS}
    entries=[
        ['evidence/apply_exposure_and_audit.py','--workspace',str(ROOT)],
        ['structure/run_structure_audit.py','--root',str(ROOT),'--exposure-registry',str(STUDY/'inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')],
        ['height/score_existing.py'],
        ['height/run_matched_controls.py'],
        ['height/audit_height_support907.py'],
        ['height/select_height_pairs.py'],
        ['height/summarize_height.py'],
        ['representation/reanalyze_current_input.py','--root',str(ROOT)],
        ['evidence/reproduce_evidence.py','--workspace',str(ROOT)],
        ['analysis/build_summary_outputs.py'],
    ]
    if args.with_review:
        entries += [['height/prepare_review_inputs.py'],['structure/render_structural_cases.py','--root',str(ROOT)],
                    ['structure/prepare_targeted_pairs.py','--root',str(ROOT)],
                    ['structure/verify_structural_delivery.py','--root',str(ROOT)]]
    receipt=[]
    for i,entry in enumerate(entries,1):
        cmd=[sys.executable,str(STUDY/entry[0]),*entry[1:]]
        log=logs/f'{i:02d}_{Path(entry[0]).stem}.log'
        print(f'[{i}/{len(entries)}] {entry[0]}',flush=True)
        start=time.monotonic()
        with log.open('w',encoding='utf-8') as f:
            result=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        receipt.append({'step':i,'script':entry[0],'returncode':result.returncode,
                        'elapsed_seconds':time.monotonic()-start,'log':str(log.relative_to(STUDY)),'log_sha256':sha(log)})
        dump(logs/'execution_manifest.json',receipt)
        if result.returncode:raise RuntimeError(f'Failed {entry[0]}; see {log}')
    comparisons=[]
    for name,table in expected.items():
        stats=compare(table,read_table(STUDY/name))
        comparisons.append({'path':name,'pass':True,**stats})
    after_sources=verify_sources();assert before_sources==after_sources
    output={'status':'pass','source_integrity_before_and_after':after_sources,
        'commands':len(entries),'numerical_result_files_checked':len(comparisons),'results':comparisons,
        'numeric_tolerance':{'absolute':1e-7,'relative':1e-8},
        'row_order_ids_labels_and_qualification_exact':True,
        'independent_validation_claim':False,'review_rebuilt':args.with_review,
        'original_research_files_modified':0,'source_root':str(ROOT)}
    dump(STUDY/'verification/fresh_reproduction_report.json',output)
    print(json.dumps({k:v for k,v in output.items() if k!='results'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
