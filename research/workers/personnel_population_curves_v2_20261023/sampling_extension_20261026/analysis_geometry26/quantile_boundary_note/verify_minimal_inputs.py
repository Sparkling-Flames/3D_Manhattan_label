"""Recompute note using only its complete 50-team input and 512 saved orders."""
from pathlib import Path
import argparse,csv,gzip,hashlib,inspect,io,json,os,sys,zipfile
import numpy as np
import pandas as pd
from scipy.stats import binom
from finite_quantile_expectation import finite_quantile_expectation

BATCHES={'old48':{'old24','prior_new24'},'stage1_104':{'extension_stage1_104'},'stage2_104':{'extension_stage2_104'},
'new208':{'extension_stage1_104','extension_stage2_104'},'pooled256':{'old24','prior_new24','extension_stage1_104','extension_stage2_104'}}

def main(root,make_zip):
    q=pd.read_csv(root/'SELECTED_EXACT_TEAM_VALUES.csv.gz');p=pd.read_csv(root/'REGISTERED_K1_PATH_BINDINGS.csv.gz',dtype={'seed':str,'master_seed':str})
    expected=pd.read_csv(root/'P10_ANALYTIC_EXPECTATION.csv');observed=pd.read_csv(root/'ACTUAL_REGISTERED_P10_BOUNDARY_COMPARISON.csv');scan=pd.read_csv(root/'BOUNDARY_SEARCH.csv')
    assert len(q)==50 and len(p)==512 and len(observed)==10 and len(expected)==12 and len(scan)==28
    assert not q.team_key.duplicated().any() and not p.path_id.duplicated().any()
    largest=scan.sort_values(['gap','pool_id','k'],ascending=[False,True,True]).head(2)
    assert set(largest.pool_id)==set(q.pool_id)
    values=q.set_index('team_key')
    for r in p.to_dict('records'):
        t=values.loc[r['team_key']];assert t.pool_id==r['pool_id'];assert t.member_workers==r['first_worker']==r['worker_order'].split('|')[0]
        assert t.member_object_ids==r['member_object_ids'];assert abs(t.B8L2-r['B8L2'])<1e-12
        assert len(r['worker_order'].split('|'))==int(t.pool_n)
    errors=[]
    for r in expected.to_dict('records'):
        values=q[q.pool_id.eq(r['pool_id'])].B8L2.to_numpy(float);L,I=finite_quantile_expectation(values,int(r['R_valid_iid_draws']))
        errors.extend([abs(L-r['expected_sample_P10_linear']),abs(I-r['expected_sample_P10_inverse_cdf'])])
        n=r['R_valid_iid_draws'];lo=r['lower_order_rank'];hi=r['upper_order_rank']
        errors.extend([abs(binom.sf(hi-1,n,.1)-r['prob_both_interpolation_orders_low_side']),
            abs(binom.cdf(lo-1,n,.1)-r['prob_both_interpolation_orders_high_side']),
            abs(binom.pmf(lo,n,.1)-r['prob_orders_straddle_boundary'])])
    for r in observed.to_dict('records'):
        a=p[p.pool_id.eq(r['pool_id'])&p.batch.isin(BATCHES[r['cohort']])];values=a.B8L2.to_numpy(float)
        assert len(a)==r['paths'];assert int((values<=r['lower_Q']).sum())==r['low_side_count']
        errors.extend([abs(float(np.quantile(values,.1,method='linear'))-r['observed_P10_linear']),
            abs(float(np.quantile(values,.1,method='inverted_cdf'))-r['observed_P10_inverse_cdf'])])
    assert max(errors)<1e-12
    receipt=dict(finite_teams=len(q),registered_paths=len(p),analytic_rows=len(expected),observed_rows=len(observed),
        max_absolute_numeric_difference=max(errors),all_path_first_people_and_team_objects_match=True,new_orders=0,new_fusions=0,simulations=0)
    if make_zip:
        out=root.parent/'HOHONET_20261026_QUANTILE_BOUNDARY_NOTE.zip';tmp=out.with_suffix('.zip.writing')
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for f in sorted(root.iterdir()):
                if f.is_file() and f.suffix not in ['.log'] and f.name!='MINIMAL_RECOMPUTE_RECEIPT.json':z.write(f,'quantile_boundary_note/'+f.name)
        tmp.replace(out)
        readback=[]
        with zipfile.ZipFile(out) as z:
            assert z.testzip() is None
            for name in z.namelist():
                body=z.read(name);r={'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
                if name.endswith('.gz'):body=gzip.decompress(body);r['gzip_eof_verified']=True
                if name.endswith(('.csv','.csv.gz')):
                    rows=list(csv.reader(io.StringIO(body.decode('utf-8-sig'))));assert all(len(row)==len(rows[0]) for row in rows)
                    r['rows']=len(rows)-1;r['fields']=rows[0]
                if name.endswith('.json'):json.loads(body)
                readback.append(r)
        receipt.update(zip=out.name,zip_bytes=out.stat().st_size,zip_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),zip_file_checks=readback)
    output=root/'MINIMAL_RECOMPUTE_RECEIPT.json';tmp=output.with_suffix('.json.writing');body=json.dumps(receipt,ensure_ascii=False,indent=2).encode()
    with tmp.open('wb') as f:assert f.write(body)==len(body);f.flush();os.fsync(f.fileno())
    tmp.replace(output);print(json.dumps({k:v for k,v in receipt.items() if k!='zip_file_checks'},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--make-zip',action='store_true');a=p.parse_args();main(a.root.resolve(),a.make_zip)
