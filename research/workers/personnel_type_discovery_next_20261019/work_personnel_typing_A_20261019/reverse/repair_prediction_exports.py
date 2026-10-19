#!/usr/bin/env python3
"""Re-export truncated derived predictions from frozen labels/calibration only.

No geometry, personnel relation, partition, inner score or selected method changes.
Uses single-writer UUID temporary files, explicit close/fsync, full CSV read-back,
and atomic publication. The initial failed-export audit is retained.
"""
from pathlib import Path
import gzip, hashlib, json, os, sys, time, uuid
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from discover_reverse_types import normalize_events, DIFFICULTY_MAP, candidates
from selection_common import attach_relation, fit_calibrator, predict_calibrator


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(1<<20):h.update(b)
    return h.hexdigest()


def crc_rows(path):
    n=0
    with gzip.open(path,'rb') as f:
        while b:=f.read(1<<20):n+=b.count(b'\n')
    return n-1


def main():
    started=time.time();p=HERE/'results'
    audit=json.loads((p/'PREDICTION_INITIAL_CRC_AUDIT.json').read_text())
    bad=[r for r in audit['checks'] if not r['crc_ok']]
    ev=normalize_events(HERE.parent/'events/common_events.csv.gz')
    ev['difficulty']=ev.difficulty.replace(DIFFICULTY_MAP)
    repaired=[]
    for failure in bad:
        fold=failure['fold_id'];d=p/'folds'/fold
        output=d/'predictions.csv.gz';before=sha(output)
        if crc_status:=failure['crc_ok']:raise AssertionError(crc_status)
        complete=json.loads((d/'COMPLETE.json').read_text())
        classes=pd.read_csv(d/'classes.csv.gz').fillna({'class_id':'unknown'})
        rates=pd.read_csv(d/'calibration.csv.gz')
        test=ev[ev.building.eq(fold)].copy()
        train=ev[ev.panel_id.eq('Pro_exact_fixed_background_v1') & ev.building.isin(complete['train_buildings'])]
        assert len(test)==complete['n_test_events']
        baseline=fit_calibrator(train,pd.Series('unknown',index=train.index))
        tmp=output.with_name(output.name+'.'+uuid.uuid4().hex+'.writing')
        max_saved_baseline_difference=0.;header=True;count=0
        ordered=[c['method_id'] for c in candidates(True)]+list(complete['selected_candidates'])
        with gzip.open(tmp,'wt',encoding='utf-8',newline='') as handle:
            for method in ordered:
                source=complete['selected_candidates'].get(method,method)
                g=classes[classes.method_id.eq(method)]
                is_global=set(g.domain)=={'global'}
                labels=(g.set_index('worker_id').class_id.to_dict() if is_global else
                        g.set_index(['domain','worker_id']).class_id.to_dict())
                rel=attach_relation(test,labels,'global' if is_global else 'difficulty')
                r=rates[rates.method_id.eq(source)]
                savedcells={(int(v.k),str(v.difficulty)):float(v.probability) for v in r[r.relation.eq('unknown')].itertuples()}
                diffs=[abs(v-baseline['cells'][key]) for key,v in savedcells.items()]
                if diffs:max_saved_baseline_difference=max(max_saved_baseline_difference,max(diffs))
                assert max_saved_baseline_difference<1e-12
                cal=dict(baseline);cal['cells']=savedcells
                cal['rates']={(int(v.k),str(v.difficulty),str(v.relation)):float(v.probability) for v in r[~r.relation.eq('unknown')].itertuples()}
                probability=predict_calibrator(cal,test,rel)
                z=pd.DataFrame({'event_id':test.event_id,'method_id':method,'fold_id':fold,'relation':rel,
                                'predicted_stability':probability,'probability':probability,'training_key':complete['training_key'],
                                'source_candidate_id':source if method in complete['selected_candidates'] else ''})
                z.to_csv(handle,index=False,header=header);header=False;count+=len(z)
        with tmp.open('rb') as f:os.fsync(f.fileno())
        expected=len(test)*len(ordered);assert count==expected
        # Full read-back validates CSV, CRC/footer, finite predictions and counts.
        observed=0;method_counts={}
        for z in pd.read_csv(tmp,compression='gzip',chunksize=50000):
            assert z.fold_id.eq(fold).all()
            assert z.probability.between(0,1).all()
            assert np.array_equal(z.probability.to_numpy(),z.predicted_stability.to_numpy())
            observed+=len(z)
            for m,n in z.method_id.value_counts().items():method_counts[m]=method_counts.get(m,0)+int(n)
        assert observed==expected and set(method_counts)==set(ordered)
        assert set(method_counts.values())=={len(test)}
        # Preserve numerical parity evidence for every readable original prefix.
        prefix_rows=0;prefix_max=0.;old_failed=False
        old=pd.read_csv(output,compression='gzip',chunksize=50000)
        new=pd.read_csv(tmp,compression='gzip',chunksize=50000)
        try:
            while True:
                a=next(old);b=next(new)
                assert len(a)==len(b)
                for col in ['event_id','method_id','fold_id','relation','training_key']:
                    assert a[col].equals(b[col]),(fold,col)
                prefix_max=max(prefix_max,float(np.max(np.abs(a.probability.to_numpy()-b.probability.to_numpy()))))
                assert prefix_max<1e-12
                prefix_rows+=len(a)
        except EOFError:
            old_failed=True
        except StopIteration:
            pass
        finally:
            old.close();new.close()
        assert old_failed,'initial corrupt-file evidence unexpectedly changed'
        digest=sha(tmp);os.replace(tmp,output)
        fd=os.open(d,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        assert crc_rows(output)==expected
        record={'fold_id':fold,'initial_sha256':before,'final_sha256':digest,'rows':expected,
                'label_sha256':sha(d/'classes.csv.gz'),'calibration_sha256':sha(d/'calibration.csv.gz'),
                'max_saved_baseline_difference':max_saved_baseline_difference,'original_prefix_rows_compared':prefix_rows,
                'max_original_prefix_probability_difference':prefix_max,'full_csv_crc_pass':True}
        repaired.append(record);print(record,flush=True)
    manifest=json.loads((p/'PREDICTION_MANIFEST.json').read_text())
    integrity=[]
    for entry in manifest['fold_files']:
        f=p/entry['path'];n=crc_rows(f);receipt=json.loads((f.parent/'COMPLETE.json').read_text())
        assert n==receipt['n_test_events']*69
        entry['sha256']=sha(f)
        integrity.append({'fold_id':entry['fold_id'],'prediction_rows':n,'gzip_crc_pass':True,'sha256':entry['sha256']})
    (p/'PREDICTION_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt={'repair_basis':'frozen per-fold classes and saved calibration; only global/k fallback re-aggregated from registered training panel',
             'personnel_relation_or_partition_refits':0,'inner_selection_reruns':0,'new_fusion_calls':0,
             'readable_original_prefixes_compared':True,'repaired_exports':repaired,'seconds':time.time()-started,
             'underlying_truncation_cause':'not established; no inference from symptoms',
             'writer':'single UUID gzip stream, close, fsync, complete CSV read-back, rename, directory fsync',
             'code_sha256':sha(__file__),'checks':integrity,'total_prediction_rows':sum(x['prediction_rows'] for x in integrity)}
    (p/'PREDICTION_OUTPUT_INTEGRITY.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print({'repaired':len(repaired),'verified':len(integrity),'prediction_rows':receipt['total_prediction_rows'],'seconds':receipt['seconds']},flush=True)


if __name__=='__main__':main()
