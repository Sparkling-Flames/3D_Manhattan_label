"""Portable consumption of frozen main evidence, without any re-preprocessing."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import csv as csv_module
import gzip, hashlib, json, math, os, uuid
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE=Path(os.environ.get('PERSONNEL_V2_REPOSITORY',ROOT/'repo_main_20261019'))
COMMIT='82c6164b0d4630de5316199c92aa405930973168'
EVIDENCE=SOURCE/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
ENGINE=SOURCE/'research/statistics/b8l2_shared_v6_20261016/inputs'

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value
def canonical(value):return json.dumps(clean(value),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(path):
    path=Path(path)
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save_gz(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(value).encode();packed=gzip.compress(raw,mtime=0)
    temporary=path.with_name(path.name+'.tmp.'+uuid.uuid4().hex)
    with temporary.open('wb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    assert gzip.decompress(temporary.read_bytes())==raw
    temporary.replace(path)
def csv(path,rows,columns=None):
    rows=list(rows);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if columns is None:columns=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv_module.DictWriter(f,fieldnames=columns,extrasaction='raise');writer.writeheader()
        for row in rows:writer.writerow({k:canonical(v) if isinstance(v,(list,dict,tuple)) else clean(v) for k,v in row.items()})
def number(value):
    try:v=float(value)
    except (TypeError,ValueError):return None
    return v if math.isfinite(v) and v>=0 else None
def subset_id(ids):return '|'.join(sorted(ids))
def team_id(pool_id,ids):return pool_id+'__T'+digest(sorted(ids))[:16]
def pool_id(record):
    reference=json.dumps([record['reference_id'],record['reference_version']],ensure_ascii=False,separators=(',',':'))
    return record['image_code']+'__'+record['condition']+'__'+hashlib.sha256(reference.encode()).hexdigest()[:10]
def load_pools():return read(OUT/'INPUT_SNAPSHOT.json.gz')['images']

def prepare():
    records=read(EVIDENCE)['records']; assert len(records)==10439 and len({x['object_id'] for x in records})==10439
    groups=defaultdict(list);inventory=defaultdict(list)
    for x in records:
        key=(x['image_id'],x['condition'],x['reference_id'],x['reference_version'])
        inventory[key].append(x)
        if x['quality_usable'] and x['independent_vote_eligible']:groups[key].append(x)
    images=[];member_rows=[];ledger=[]
    for key,group in sorted(groups.items()):
        first=group[0]; pid=pool_id(first);reference=first['reference_evidence']
        required_ref=('target_id','reference_version','floor_xz_h','points_1024x512','full_reference_available')
        ref={k:reference[k] for k in required_ref}
        assert ref['target_id']==first['reference_id'] and ref['reference_version']==first['reference_version']
        assert ref['full_reference_available'] and len(ref['points_1024x512'])>=8
        assert len(set(x['worker_id'] for x in group))==len(group)
        assert all({k:x['reference_evidence'][k] for k in required_ref}==ref for x in group)
        assert len(set(x['quality_use'] for x in group))==1
        layer={'ordinary_primary':'ordinary','doorway_quality':'doorway','special_conditional_only':'special'}[first['quality_use']]+'_'+first['condition']
        difficulty_record=first['image_evidence']['difficulty_record']
        aligned=first['reference_id']==difficulty_record['target_version']
        current=[]
        for x in sorted(group,key=lambda x:x['worker_id']):
            points=x['points_1024x512']; coord=x['coordinate_evidence']; indices=coord.get('ordered_source_pair_indices')
            assert points and len(points)%2==0 and np.isfinite(np.asarray(points,float)).all()
            assert indices is None or (len(indices)==len(points)//2 and len(set(indices))==len(indices))
            r=dict(id=x['object_id'],object_id=x['object_id'],worker=x['worker_id'],worker_id=x['worker_id'],
                   condition=x['condition'],points=points,source_pair_indices=indices,
                   ring_confirmed=x['ring_confirmed'],order_status=x['order_status'],
                   order_used='frozen_evidence_declared_order_no_additional_sort',
                   geometry_status=x['geometry_status'],origin=x['origin'],
                   source_time_seconds=number(x['source_active_time_seconds']),target_time_seconds=number(x['target_matched_time_seconds']),
                   time_source_kind=x['time_evidence']['source_kind'],quality_usable=True,B8L2=x['B8L2'],D10=x['D10'],
                   source_point_indices=coord.get('ordered_source_point_indices'))
            current.append(r)
            member_rows.append(dict(pool_id=pid,image_id=x['image_id'],image=x['image_code'],condition=x['condition'],
                building=x['building_id'],room_id=x['room_id'],layer=layer,difficulty=x['current_class'],difficulty_aligned=aligned,
                reference_id=x['reference_id'],reference_version=x['reference_version'],
                object_id=x['object_id'],worker_id=x['worker_id'],origin=x['origin'],point_pairs=len(points)//2,
                B8L2=x['B8L2'],D10=x['D10'],source_time_seconds=r['source_time_seconds'],target_time_seconds=r['target_time_seconds'],
                time_source_kind=r['time_source_kind'],ring_confirmed=x['ring_confirmed'],order_status=x['order_status'],points_sha256=digest(points)))
        meta=dict(pool_id=pid,image=first['image_code'],image_id=first['image_id'],condition=first['condition'],
            building=first['building_id'],room_id=first['room_id'],scene=first['scene'],layer=layer,
            difficulty=first['current_class'],difficulty_aligned=aligned,
            reference_id=first['reference_id'],reference_version=first['reference_version'],
            pool_n=len(current),source_inventory_n=len(inventory[key]),source_time_known_n=sum(r['source_time_seconds'] is not None for r in current),
            target_time_known_n=sum(r['target_time_seconds'] is not None for r in current),old_member_n=sum(r['origin']=='v1' for r in current),
            new_member_n=sum(r['origin']=='new' for r in current))
        images.append(dict(pool_id=pid,meta=meta,reference=ref,records=current))
        ledger.append(dict(meta,**{f'support_k{k}':len(current)>=k for k in (3,4,6,8,12,16,24,32,40)},worker_ids='|'.join(r['worker_id'] for r in current)))
    assert len(images)==229 and sum(len(x['records']) for x in images)==7302
    ordinary=[x for x in images if x['meta']['layer']=='ordinary_manual']
    assert len(ordinary)==177 and sum(len(x['records']) for x in ordinary)==5719
    save_gz(OUT/'INPUT_SNAPSHOT.json.gz',dict(schema='v2_real_fusion_inputs_v1',git_commit=COMMIT,data_release='v2',
        evidence_path=str(EVIDENCE.relative_to(SOURCE)),evidence_sha256=sha(EVIDENCE),images=images,
        conversion='fields renamed only; final geometry, top/bottom binding and declared ring used byte-for-byte as values; no prepare_record or raw export reload',
        fusion_gap=7.5,N1_applied=False))
    csv(OUT/'POOL_MEMBERS.csv',member_rows);csv(OUT/'POOL_ELIGIBILITY.csv',ledger)
    save(OUT/'INPUT_COVERAGE.json',dict(inventory=10439,quality_records=7302,quality_pools=229,quality_images=196,quality_workers=60,
        ordinary_manual_records=5719,ordinary_manual_pools=177,ordinary_manual_buildings=len({p['meta']['building'] for p in ordinary}),
        quality_only_scope='No quality-ineligible voter is assigned zero or treated as low ability; evidence diagnostics remain separate.',
        source_time_known=sum(r['source_time_seconds'] is not None for p in images for r in p['records']),
        target_time_known=sum(r['target_time_seconds'] is not None for p in images for r in p['records']),
        actual_input_sha256=sha(OUT/'INPUT_SNAPSHOT.json.gz')))
    print({'prepared_pools':len(images),'records':len(member_rows),'ordinary_manual_pools':len(ordinary)},flush=True)

if __name__=='__main__':prepare()
