"""Direct-download event parts and a row locator, preserving all requests.

Only a completed, EOF/key-validated event table is split. Large tables target
100 MB compressed parts; this is a physical publication operation, not event
subsampling or a new statistical analysis.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from pathlib import Path
from multin_design import HERE,gs,sha
from consolidate_deliverables import GzipCsv

OUT=HERE/'delivery/events'

def publish(stage,condition):
    prefix=stage.upper();cond=condition.upper()
    source=HERE/('paths' if stage=='path' else 'matched')/(
        f'{cond}_ALL_PATH_EDGES.csv.gz' if stage=='path' else f'{prefix}_{cond}_COMPLETE_EVENTS.csv.gz')
    receipt_path=source.with_suffix('.json')
    if not source.exists() or not receipt_path.exists():raise RuntimeError('Wait for complete event publication: '+str(source))
    source_receipt=gs.read(receipt_path);source_hash=sha(source)
    if source_hash!=source_receipt['sha256']:raise ValueError('changed completed source event table')
    OUT.mkdir(parents=True,exist_ok=True);manifest=OUT/f'{prefix}_{cond}_EVENT_MANIFEST.json'
    if manifest.exists():
        prior=gs.read(manifest)
        if prior.get('source_sha256')==source_hash and all((HERE/r['path']).exists() and sha(HERE/r['path'])==r['sha256'] for r in prior['parts']+[prior['index']]):
            print(json.dumps(dict(stage=stage,condition=condition,status='already_published',rows=prior['rows'])),flush=True);return
    total=int(source_receipt['rows']);split=source.stat().st_size>150_000_000
    nparts=math.ceil(source.stat().st_size/100_000_000) if split else 1;part_rows=math.ceil(total/nparts)
    fields=['index_key','stage','event_id','condition','pool_id','image','building','method_id','tier','design_scope',
      'result_file','row_number','n','m_AB','m_AC','m_BC','n_from','n_to','team_A','team_B','team_C','team_from','team_to',
      'all_complete','all_scored','A_score_status','B_score_status','C_score_status','from_status','to_status',
      'request_result_present']
    index=GzipCsv(OUT/f'{prefix}_{cond}_EVENT_INDEX.csv.gz',fields,key='index_key');index_keys=set()
    seen=set();parts=[];writer=None;part_keys=set();current_part=-1;in_part=0;source_fields=None
    with gzip.open(source,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);source_fields=reader.fieldnames
        for i,r in enumerate(reader):
            eid=r['event_id']
            if eid in seen:raise ValueError('duplicate completed event key')
            seen.add(eid);part=i//part_rows if split else 0
            if part!=current_part:
                if writer is not None:parts.append(writer.finish(part_keys))
                current_part=part;in_part=0;part_keys=set()
                target=OUT/f'{prefix}_{cond}_COMPLETE_EVENTS.part{part+1:03d}.csv.gz' if split else source
                writer=GzipCsv(target,source_fields,key='event_id') if split else None
            in_part+=1;part_keys.add(eid)
            if writer is not None:writer.add(r)
            ik=prefix+'|'+eid;index_keys.add(ik);row={k:r.get(k,'') for k in fields}
            row.update(index_key=ik,stage=prefix,condition=condition,result_file=str(target.relative_to(HERE)),row_number=in_part,
              all_complete=r.get('all_complete',r.get('both_complete','')),
              A_score_status=r.get('A_score_status',r.get('endpoint_A__score_status','')),
              C_score_status=r.get('C_score_status',r.get('endpoint_C__score_status','')),request_result_present=True)
            index.add(row)
    if len(seen)!=total:raise ValueError('source receipt count changed')
    if writer is not None:parts.append(writer.finish(part_keys))
    if not split:parts=[dict(path=str(source.relative_to(HERE)),rows=total,columns=len(source_fields),bytes=source.stat().st_size,sha256=source_hash,gzip_EOF_verified=True,unique_keys=True)]
    ir=index.finish(index_keys)
    final=dict(status='complete',stage=prefix,condition=condition,rows=total,columns=len(source_fields),
      physical_parts=len(parts),complete_source_file=str(source.relative_to(HERE)),source_sha256=source_hash,
      source_request_sha256=source_receipt.get('request_sha256'),all_events_present_once=True,
      no_subsampling=True,native_calls=0,parts=parts,index=ir)
    gs.save(manifest,final);print(json.dumps(final,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['panel','large','pure','pure_cross','path']);p.add_argument('--condition',choices=['manual','semi'])
    a=p.parse_args()
    for c in [a.condition] if a.condition else ['manual','semi']:publish(a.stage,c)
