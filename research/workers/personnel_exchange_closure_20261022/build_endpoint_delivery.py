"""Assemble exact required endpoint exports, preserving failures and cached identity."""
from pathlib import Path
import csv,gzip,hashlib,json,math,os

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=HERE/'delivery/endpoints'

def op(p,mode='rt'):
    enc='utf-8-sig' if 'r' in mode else 'utf-8'
    return gzip.open(p,mode,encoding=enc,newline='') if str(p).endswith('.gz') else open(p,mode,encoding=enc,newline='')
def rows(p):
    with op(p) as f:yield from csv.DictReader(f)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def complete_legacy_geometry(row, scalar):
    result = dict(row)
    for field in ('team_key', 'pool_id', 'member_workers', 'k', 'score_status',
                  'complete_evaluable', 'node_supports', 'minimum_support',
                  'reference_id', 'reference_version'):
        value = scalar[field]
        assert value not in ('', None), (scalar['team_key'], field)
        assert not result.get(field) or result[field] == value, (scalar['team_key'], field)
        result[field] = value
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    folders=sorted((HERE/'native/batches').glob('*'))
    sources=[];expected=set();batch=[]
    for d in folders:
        if not d.is_dir():continue
        if not (d/'REQUESTS.csv.gz').exists():continue
        receipt=json.loads((d/'COMPLETION.json').read_text())
        assert receipt['missing']==0
        req=list(rows(d/'REQUESTS.csv.gz'));expected.update(r['team_key'] for r in req)
        sources.append((d/'ENDPOINT_SCALARS.csv.gz',d/'ENDPOINT_GEOMETRY.csv.gz',None))
        batch.append(dict(batch=d.name,requested=len(req),scalars=str(sources[-1][0].relative_to(ROOT)),geometry=str(sources[-1][1].relative_to(ROOT)),**{k:v for k,v in receipt.items() if k in ['origins','states','immutable_final_checkpoints']}))
    # Two QT controls were already available in the legacy compact cache and were
    # not sent to the native runner. Export them with the necessary endpoint union.
    extra={'7y3sRwLe3Va-13__semi__5b6c87b5f3__09d8b188a17a42aab325',
           'q9vSo1VnCiC-15__semi__6d5ae69ee8__3d2e0a7d6b0586d21e28'}
    old=ROOT/'research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange'
    sources.append((old/'ALL_USED_ENDPOINT_SCALARS.csv.gz',old/'ALL_USED_ENDPOINT_GEOMETRY.csv.gz',extra));expected.update(extra)
    receipts=[];kept_sources={};duplicates=[];origin={};extra_metadata={}
    for kind,idx in [('SCALARS',0),('GEOMETRY',1)]:
        header=[]
        for ss in sources:
            with op(ss[idx]) as f:
                for k in next(csv.reader(f)):
                    if k not in header:header.append(k)
        dst=OUT/('ALL_REQUIRED_ENDPOINT_'+kind+'.csv.gz');tmp=dst.with_name(dst.name+'.writing.gz')
        seen={};statuses={}
        with op(tmp,'wt') as f:
            w=csv.DictWriter(f,fieldnames=header,extrasaction='ignore');w.writeheader()
            for ss in sources:
                p=ss[idx];select=ss[2]
                for r in rows(p):
                    key=r['team_key']
                    if select is not None and key not in select:continue
                    if kind=='SCALARS':
                        if key in extra:extra_metadata[key]=r
                        sig=tuple(float(r[x]) if r.get(x) not in ('',None,'nan') else None for x in ['B8L2','D10','nodes'])
                        # 300 new rows resumed from the pre-adapter checkpoint retain
                        # the old runner's naming. Their current-study source is decisive.
                        is_new=select is None and r.get('endpoint_origin','') in (
                            'new_native_closure_20261022_real_v2',
                            'new_team_for_exchange_conditions_20261022_on_real_v2')
                        origin[key]='new_native' if is_new or origin.get(key)=='new_native' else 'reused_prior'
                    else:
                        if key in extra:r=complete_legacy_geometry(r,extra_metadata[key])
                        sig=hashlib.sha256(json.dumps(json.loads(r['geometry_json']) if r.get('geometry_json') else None,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    if key in seen:
                        if kind=='SCALARS':assert all(a==b or(a is not None and b is not None and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10)) for a,b in zip(sig,seen[key])),key
                        else:assert sig==seen[key],key
                        duplicates.append(dict(kind=kind,team_key=key,duplicate_source=str(p.relative_to(ROOT))))
                        continue
                    seen[key]=sig;w.writerow(r)
                    if kind=='SCALARS':
                        kept_sources[key]=dict(team_key=key,pool_id=r.get('pool_id',''),condition=r.get('condition',''),
                            first_scalar_source=str(p.relative_to(ROOT)),score_status=r.get('score_status',''),
                            member_workers=r.get('member_workers',''),k=r.get('k',''))
                        st=r.get('score_status','');statuses[st]=statuses.get(st,0)+1
        assert set(seen)==expected,(kind,len(expected-set(seen)),len(set(seen)-expected))
        os.replace(tmp,dst)
        receipts.append(dict(kind=kind,path=str(dst.relative_to(HERE)),rows=len(seen),columns=len(header),bytes=dst.stat().st_size,sha256=sha(dst),states=statuses))
    provenance=OUT/'ENDPOINT_SOURCE_INDEX.csv.gz'
    with op(provenance,'wt') as f:
        header=list(next(iter(kept_sources.values())))+['execution_identity']
        w=csv.DictWriter(f,fieldnames=header);w.writeheader()
        for key,r in kept_sources.items():w.writerow(dict(r,execution_identity=origin[key]))
    receipt=dict(status='complete',underlying_data_version='v2',required_unique_endpoints=len(expected),
                 unique_new_native=sum(v=='new_native' for v in origin.values()),unique_reused_prior=sum(v=='reused_prior' for v in origin.values()),
                 central_registered_references=sum(x['requested'] for x in batch),extra_legacy_QT_controls=2,
                 exact_geometry_and_key_alignment=True,no_fusion_or_scoring_in_this_step=True,files=receipts,batches=batch,duplicate_references=duplicates)
    (OUT/'DELIVERY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['required_unique_endpoints','unique_new_native','unique_reused_prior','central_registered_references']}))

if __name__=='__main__':main()
