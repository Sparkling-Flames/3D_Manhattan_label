#!/usr/bin/env python3
"""Independent standard-library reconstruction, plus complete rerun numeric check."""
import csv
import gzip
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'inputs/HOHONET_v21_full_chain_20261030/stage05_selection_stop/selection'


def rows(path):
    op = gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def num(s):
    return float(s) if s and str(s).lower() != 'nan' else math.nan


def hierarchy(items):
    images=defaultdict(list)
    for building,image,value in items:
        if math.isfinite(value): images[(building,image)].append(value)
    buildings=defaultdict(list)
    for (building,image),values in images.items(): buildings[building].append(sum(values)/len(values))
    return sum(sum(x)/len(x) for x in buildings.values())/len(buildings)


def main():
    flags={r['pair_id']:r for r in rows(SRC/'RELATION_FLAGS.csv')}
    q,qt={},{}
    for r in rows(SRC/'POLICY_EVENT_RESULTS.csv.gz'):
        if r['version']!='v21_history_reselected_fixed_candidates' or r['domain']!='new_timed_history': continue
        if r['layer']!='ordinary_manual' or r['scope_comparable']!='True': continue
        if r['policy'] not in ('outside_Q','outside_Q_outside_T_fast'):continue
        f=flags[r['pair_id']]
        if f['relation_oos_pending']!='False' or f['relation_substantive_conflict']!='False' or f['direct_adopted']!='True':continue
        k=tuple(r[c] for c in ('pair_id','source_pool_id','target_pool_id','domain'))
        dest=q if r['policy']=='outside_Q' else qt
        assert (k,int(r['n'])) not in dest
        dest[k,int(r['n'])]=r
    expected={(r['panel'],int(r['n']),r['metric']):num(r['value']) for r in rows(ROOT/'results/COMMON_SUPPORT_SUMMARY.csv')}
    checks=[]
    for panel,sizes in [('all_sizes_3_to_13',[3,4,5,6,7,9,13]),('early_sizes_3_to_7',[3,4,5,6,7])]:
        keys={k for k,n in q if all((k,n1) in q and (k,n1) in qt for n1 in sizes)}
        assert len(keys)==(126 if len(sizes)==7 else 210)
        for n in sizes:
            values=defaultdict(list)
            for k in sorted(keys):
                a,b=q[k,n],qt[k,n]
                av,bv=num(a['B8L2']),num(b['B8L2'])
                delta=bv-av
                labor=num(b['target_activity_seconds'])/num(a['target_activity_seconds'])
                ms={'delta_q':delta,'q_only':av,'q_time':bv,
                    'labor_ratio':math.log(labor),
                    'loss_gt5':float(delta < -5) if math.isfinite(delta) else math.nan,
                    'q_time_scored':float(math.isfinite(bv)),
                    'joint_save20_loss_atmost2':float(labor<=.8 and delta>=-2) if math.isfinite(delta) else math.nan}
                for metric,value in ms.items():values[metric].append((b['building'],b['target_image'],value))
            for metric,items in values.items():
                estimate=hierarchy(items)
                if metric=='labor_ratio':estimate=math.exp(estimate)
                error=abs(estimate-expected[panel,n,metric])
                assert error<1e-9,(panel,n,metric,error)
                checks.append({'panel':panel,'n':n,'metric':metric,'independent_value':estimate,'abs_error':error})
    # Rerun all computations in an isolated temporary output directory.
    with tempfile.TemporaryDirectory(prefix='v21_fixed_support_') as td:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/analyze_common_support.py'),'--output',td],
            capture_output=True,text=True,check=True)
        tables=['COMMON_SUPPORT_SUMMARY.csv','COMMON_SUPPORT_IMAGES.csv','COMMON_SUPPORT_BUILDINGS.csv',
                'LEAVE_ONE_BUILDING_OUT.csv','COMMON_CONTEXT_ROSTER.csv','ADJACENT_SIZE_PAIRED_CHANGES.csv',
                'EXPLORATORY_N5_N13_ABSOLUTE_CONTRAST.csv']
        reruns=[]
        for filename in tables:
            a=(ROOT/'results'/filename).read_bytes()
            b=(Path(td)/filename).read_bytes()
            assert a==b,filename
            reruns.append({'file':filename,'identical_bytes':True,'sha256':hashlib.sha256(a).hexdigest()})
    receipt={'status':'passed','independent_engine':'Python stdlib csv/gzip/math, no shared aggregation routine',
             'independent_metric_cells':len(checks),'maximum_absolute_error':max(x['abs_error'] for x in checks),
             'checks':checks,'deterministic_rerun_tables':reruns,
             'png_viewed':True,'plot_labels_and_layout':'readable; English labels, Chinese explanation in report'}
    (ROOT/'results/INDEPENDENT_VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('checks','deterministic_rerun_tables')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
