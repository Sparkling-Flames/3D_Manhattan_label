#!/usr/bin/env python3
"""Extract one already-scored strict ABC event. Never generate/evaluate teams.

Native source geometry lines are copied unchanged, with their original shard,
line and hash recorded. Inputs can be the complete new run or a completed pool.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json
import pandas as pd

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def csv_records(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)

def save_csv(path,rows):
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(path,index=False,compression={'method':'gzip','mtime':0} if str(path).endswith('.gz') else None)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--event-id',required=True);ap.add_argument('--design',type=Path,required=True);ap.add_argument('--native',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--roles',type=Path);ap.add_argument('--time-index',type=Path);ap.add_argument('--effects',type=Path);ap.add_argument('--geometry-events',type=Path);ap.add_argument('--selection-receipt',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    matches=[x for x in csv_records(a.design) if x['event_id']==a.event_id];assert len(matches)==1,('event_not_unique',len(matches));e=matches[0]
    blocks={x:set(filter(None,e[x+'_members'].split('|'))) for x in 'DXYZ'}
    for i,left in enumerate('DXYZ'):
        for right in 'DXYZ'[i+1:]:assert not blocks[left]&blocks[right],('non_strict_overlap',left,right)
    assert all(len(blocks[b])==int(e['m']) for b in 'XYZ')
    assert all(set(e[arm+'_members'].split('|'))==blocks['D']|blocks[block] for arm,block in zip('ABC','XYZ'))
    needed={e[f'team_key_{arm}_{view}'] for arm in 'ABC' for view in 'ab'};assert len(needed)==6
    pids={e['pool_id_a'],e['pool_id_b']};found={};scalar_parts=[];index=[];deps=[dict(path=str(a.design),sha256=sha(a.design),purpose='new_registered_exact_design')]
    for pid in sorted(pids):
        folder=a.native/'parts'/pid
        for receipt_file in sorted(folder.glob('part_*.receipt.json')):
            receipt=json.loads(receipt_file.read_text());want=set(receipt['team_keys'])&needed
            if not want:continue
            scalar_file=folder/receipt['scalar_file'];geometry_file=folder/receipt['geometry_file'];assert sha(scalar_file)==receipt['scalar_sha256'];assert sha(geometry_file)==receipt['geometry_sha256']
            s=pd.read_csv(scalar_file,low_memory=False);sub=s[s.team_key.isin(want)];assert len(sub)==len(want);scalar_parts.append(sub)
            with gzip.open(geometry_file,'rb') as f:
                for line_no,line in enumerate(f,1):
                    z=json.loads(line);key=z['team_key']
                    if key not in want:continue
                    assert key not in found;found[key]=line
                    index.append(dict(team_key=key,pool_id=pid,source_native_root=str(a.native),source_shard=geometry_file.relative_to(a.native).as_posix(),source_line_1based=line_no,source_shard_sha256=receipt['geometry_sha256'],native_line_sha256=hashlib.sha256(line).hexdigest(),full_state_present=z.get('full_state') is not None,score_status=z.get('score_status'),score_available=z.get('score_available'),complete_evaluable=z.get('complete_evaluable')))
            deps.extend([dict(path=str(receipt_file),sha256=sha(receipt_file),purpose='native_part_receipt'),dict(path=str(scalar_file),sha256=receipt['scalar_sha256'],purpose='native_scalars'),dict(path=str(geometry_file),sha256=receipt['geometry_sha256'],purpose='native_geometry_fullstates')])
    assert set(found)==needed,('missing_geometry',sorted(needed-set(found)))
    s=pd.concat(scalar_parts,ignore_index=True);assert len(s)==6 and not s.team_key.duplicated().any();save_csv(a.out/'SIX_TEAM_NATIVE_SCALARS.csv.gz',s)
    order=sorted(found);(a.out/'SIX_TEAM_NATIVE_GEOMETRY.jsonl.gz').write_bytes(gzip.compress(b''.join(found[k] for k in order),compresslevel=4,mtime=0))
    for row in index:row['case_geometry_line_1based']=order.index(row['team_key'])+1
    save_csv(a.out/'SOURCE_STATE_INDEX.csv',index);save_csv(a.out/'STRICT_ABC_EVENT.csv.gz',matches)
    snapshot=json.load(gzip.open(a.snapshot,'rt'));pools=[p for p in snapshot['images'] if p['pool_id'] in pids];assert len(pools)==2
    for pool in pools:
        raw={r['worker_id']:r for r in pool['records']};assert set.union(*blocks.values())<=set(raw)
    (a.out/'FROZEN_TWO_POOLS.json.gz').write_bytes(gzip.compress(json.dumps({'images':pools},ensure_ascii=False,separators=(',',':')).encode(),mtime=0));deps.append(dict(path=str(a.snapshot),sha256=sha(a.snapshot),purpose='frozen_raw_and_reference_snapshot'))
    if a.time_index:
        ids={r['object_id'] for p in pools for r in p['records']};times=[x for x in csv_records(a.time_index) if x['object_id'] in ids];save_csv(a.out/'RECORD_TIME_SOURCES.csv.gz',times);deps.append(dict(path=str(a.time_index),sha256=sha(a.time_index),purpose='recorded_time_source_index'))
    if a.roles:
        roles=[x for x in csv_records(a.roles) if x['heldout_building']==e['building'] and x['method']==e['method'] and x['condition']==e['condition']];assert roles;save_csv(a.out/'FROZEN_CLASS_ROLES_AND_MEMBERS.csv',roles);deps.append(dict(path=str(a.roles),sha256=sha(a.roles),purpose='frozen_LOBO_roles'))
    for source,name in [(a.effects,'EXACT_EVENT_EFFECTS.csv.gz'),(a.geometry_events,'SIX_GEOMETRY_COMPARISONS.csv.gz')]:
        if source:
            rows=[x for x in csv_records(source) if x['event_id']==a.event_id];assert rows;save_csv(a.out/name,rows);deps.append(dict(path=str(source),sha256=sha(source),purpose=name))
    selection=json.loads(a.selection_receipt.read_text()) if a.selection_receipt else {'event_id':a.event_id,'selection':'explicit event_id supplied; no selection implemented in extractor'}
    (a.out/'CASE_SELECTION.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
    receipt=dict(event_id=a.event_id,operation='extract_already_existing_exact_native_case_not_replay',input_commit=e['input_commit'],design_version=e['design_version'],new_fusion=0,new_scoring=0,new_labels=0,views=2,endpoints=6,full_state_count=sum(r['full_state_present'] for r in index),frozen_records=sum(len(p['records']) for p in pools),geometry_lines_copied_byte_exact=True,dependencies=deps)
    (a.out/'EXTRACTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='dependencies'},ensure_ascii=False))

if __name__=='__main__':main()
