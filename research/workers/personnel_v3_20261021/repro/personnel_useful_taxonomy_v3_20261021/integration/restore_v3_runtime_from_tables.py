"""Restore one delivered v3 batch for event replay, without fusion or scoring.

Example, from the repository root after extracting a batch package:
  python research/workers/personnel_useful_taxonomy_v3_20261021/integration/restore_v3_runtime_from_tables.py \
    --batch-dir research/workers/personnel_useful_taxonomy_v3_20261021/composition/batches/batch_017 \
    --output research/workers/personnel_useful_taxonomy_v3_20261021/composition/runtime/batch_017

Existing output files are accepted only if their endpoint identities, delivered
scalar values and geometry match. Nothing is overwritten on a conflict.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, itertools, json, math, os
from pathlib import Path

HERE=Path(__file__).resolve().parent
STRING_LISTS={'member_workers','member_object_ids'}
INTEGER_LISTS={'node_supports','ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9'}

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def read_rows(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if len(reader.fieldnames)!=len(set(reader.fieldnames)):raise ValueError('duplicate CSV fields')
        for r in reader:
            if None in r or any(x is None for x in r.values()):raise ValueError('ragged CSV row')
            yield r

def scalar_value(k,v,types):
    if k in STRING_LISTS:return v.split('|') if v else []
    if k in INTEGER_LISTS:return [int(x) for x in v.split('|')] if v else None
    if v=='':return None
    kind=types.get(k,[])
    if 'str' in kind:return v
    if 'bool' in kind:
        if v not in ('True','False'):raise ValueError(('invalid boolean',k,v))
        return v=='True'
    if kind and set(kind)<= {'int','float'}:
        x=float(v)
        if not math.isfinite(x):raise ValueError(('nonfinite delivered scalar',k,v))
        return int(x) if kind==['int'] else x
    raise ValueError(('unregistered scalar type; extend explicit schema',k,v))

def atomic_json_gzip(path,value):
    packed=gzip.compress(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),compresslevel=5,mtime=0)
    tmp=path.with_name(path.name+'.tmp')
    with open(tmp,'wb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    json.loads(gzip.decompress(tmp.read_bytes()))
    tmp.replace(path)

def restore(batch_dir,output,schema_path):
    batch_dir=Path(batch_dir);output=Path(output);schema=json.loads(Path(schema_path).read_text())
    receipt=json.loads((batch_dir/'COMPLETION.json').read_text());bid=receipt['batch_id']
    if receipt['status']!='complete':raise ValueError('batch is not frozen complete')
    sp=batch_dir/'ENDPOINT_SCALARS.csv.gz';gp=batch_dir/'ENDPOINT_GEOMETRY.csv.gz'
    for p,key in [(sp,'scalars'),(gp,'geometry')]:
        if sha(p)!=receipt[key]['sha256']:raise ValueError(('input hash mismatch',str(p)))
    requests={r['team_key']:r for r in read_rows(batch_dir/'REQUESTS.csv.gz')}
    groups=collections.defaultdict(list);seen=set()
    for s,g in itertools.zip_longest(read_rows(sp),read_rows(gp)):
        if s is None or g is None:raise ValueError('unequal aligned table lengths')
        key=s['team_key']
        if key!=g['team_key'] or key in seen or key not in requests:raise ValueError(('wrong or repeated key',key))
        seen.add(key)
        row={k:scalar_value(k,v,schema['field_types']) for k,v in s.items()}
        row['geometry']=json.loads(g['geometry_json'])
        for k in ['pool_id','member_workers','k','score_status','complete_evaluable','minimum_support','reference_id','reference_version']:
            if row.get(k)!=scalar_value(k,g[k],schema['field_types']):raise ValueError(('cross-table mismatch',key,k))
        # Empty supports are a known empty list, unlike an unknown recall list.
        row['node_supports']=[int(x) for x in g['node_supports'].split('|')] if g['node_supports'] else []
        if row['pool_id']!=requests[key]['pool_id']:raise ValueError('request pool mismatch')
        groups[row['pool_id']].append(row)
    if seen!=set(requests) or len(seen)!=receipt['exported']:raise ValueError('incomplete endpoint key coverage')
    output.mkdir(parents=True,exist_ok=True);files=[]
    for pid,rows in sorted(groups.items()):
        hashes={requests[r['team_key']]['pool_input_sha256'] for r in rows}
        if len(hashes)!=1:raise ValueError('conflicting pool inputs')
        target=output/(pid+'.json.gz')
        value={'batch_id':bid,'pool_id':pid,'pool_input_sha256':next(iter(hashes)),
               'fusion_gap':schema['native_fusion_gap'],'teams':rows}
        if target.exists():
            old=json.load(gzip.open(target,'rt'));prior={r['team_key']:r for r in old['teams']}
            if set(prior)!={r['team_key'] for r in rows}:raise ValueError(('existing key conflict',str(target)))
            for r in rows:
                for k,v in r.items():
                    before=prior[r['team_key']].get(k)
                    # CSV cannot distinguish an absent list from a zero-length
                    # list; both encode zero known matching indices.
                    if k in INTEGER_LISTS and v is None and before==[]:continue
                    if before!=v:raise ValueError(('existing value conflict',r['team_key'],k,before,v))
            action='existing_endpoint_values_verified'
        else:
            atomic_json_gzip(target,value);action='restored_from_delivered_tables'
        files.append({'pool_id':pid,'rows':len(rows),'path':str(target),'action':action,'sha256':sha(target)})
    result={'batch_id':bid,'rows':len(seen),'pools':len(files),'missing':0,'fusion_calls':0,'scoring_calls':0,
            'scalar_sha256':sha(sp),'geometry_sha256':sha(gp),'schema_sha256':sha(schema_path),
            'preserved':'team identity, member order, scalar values, failure state, reference, geometry, supports',
            'null_note':'Absent versus explicit-null keys and absent versus empty matched-index lists cannot be distinguished in CSV. This does not change delivered metrics or replay inputs.',
            'files':files}
    (output/'TABLE_RESTORE_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch-dir',required=True);p.add_argument('--output',required=True)
    p.add_argument('--schema',default=str(HERE/'ENDPOINT_CSV_RESTORE_SCHEMA.json'));a=p.parse_args()
    restore(a.batch_dir,a.output,a.schema)
