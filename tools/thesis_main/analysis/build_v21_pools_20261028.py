"""在冻结原答/时间/点对身份上接入v2.1评分与参考，登记池依赖。"""
import gzip
import json
from collections import defaultdict, Counter
from .rebuild_v21_20261028 import ROOT, OUT, read, write


def main():
    with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz','rt',encoding='utf-8') as f:
        evidence={r['object_id']:r for r in json.load(f)['records']}
    with gzip.open(ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz','rt',encoding='utf-8') as f:
        old=json.load(f)['images']
    oldmap={(p['meta']['reference_id'],p['meta']['condition']):p for p in old}
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    diffs={r['image_id']:r for r in read(OUT/'difficulty_records.json')['records']}
    groups=defaultdict(list)
    inventory=read(OUT/'quality_inventory.json')
    inventory_counts=Counter((r['reference_id'],r['condition']) for r in inventory)
    for r in inventory:
        if r['quality_usable'] and evidence[r['object_id']]['independent_vote_eligible']:
            groups[r['reference_id'],r['condition']].append(r)
    pools=[];ledger=[]
    for index,((tid,cond),group) in enumerate(sorted(groups.items())):
        first=group[0];ref=refs[tid];before=oldmap.get((tid,cond))
        assert len({r['worker_id'] for r in group})==len(group)
        assert len({r['quality_use'] for r in group})==1
        records=[]
        for r in sorted(group,key=lambda r:r['worker_id']):
            x=evidence[r['object_id']];coord=x['coordinate_evidence']
            records.append(dict(id=x['object_id'],object_id=x['object_id'],worker=x['worker_id'],worker_id=x['worker_id'],
                condition=cond,points=x['points_1024x512'],source_pair_indices=coord.get('ordered_source_pair_indices'),
                source_point_indices=coord.get('ordered_source_point_indices'),ring_confirmed=x['ring_confirmed'],order_status=x['order_status'],
                order_used='frozen_evidence_declared_order_no_additional_sort',geometry_status=x['geometry_status'],origin=x['origin'],
                source_time_seconds=x['source_active_time_seconds'],target_time_seconds=x['target_matched_time_seconds'],
                time_source_kind=x['time_evidence']['source_kind'],quality_usable=True,B8L2=r['B8L2'],D10=r['D10']))
        same_members=bool(before and {r['object_id'] for r in records}=={r['object_id'] for r in before['records']})
        same_geometry=bool(same_members and {r['object_id']:r['points'] for r in records}=={r['object_id']:r['points'] for r in before['records']})
        same_ref=bool(before and before['reference']['points_1024x512']==ref['points_1024x512'])
        pid=before['pool_id'] if before else first['image_code']+'__'+cond+'__v21_'+str(index)
        layer={'ordinary_primary':'ordinary','doorway_quality':'doorway','special_conditional_only':'special'}[first['quality_use']]+'_'+cond
        meta=dict(pool_id=pid,image=first['image_code'],image_id=first['image_id'],condition=cond,building=first['building_id'],
            room_id=evidence[first['object_id']]['room_id'],scene=first['scene'],layer=layer,difficulty=first['current_class'],
            difficulty_aligned=tid==diffs[first['image_id']]['target_version'],reference_id=tid,reference_version=ref['reference_version'],
            pool_n=len(records),source_inventory_n=inventory_counts[tid,cond],source_time_known_n=sum(r['source_time_seconds'] is not None for r in records),
            target_time_known_n=sum(r['target_time_seconds'] is not None for r in records),
            old_member_n=sum(r['origin']=='v1' for r in records),new_member_n=sum(r['origin']=='new' for r in records),data_release='v2.1')
        pools.append(dict(pool_id=pid,meta=meta,records=records,reference={k:ref[k] for k in ['target_id','reference_version','floor_xz_h','points_1024x512','full_reference_available']}))
        ledger.append(dict(pool_id=pid,image=first['image_code'],condition=cond,layer=layer,pool_n=len(records),
            old_pool_n=len(before['records']) if before else 0,same_members=same_members,same_input_geometry=same_geometry,same_reference=same_ref,
            action='reuse_geometry_rescore' if same_geometry and not same_ref else 'reuse_endpoints' if same_geometry else 'new_or_changed_pool',
            added_object_ids=sorted({r['object_id'] for r in records}-({r['object_id'] for r in before['records']} if before else set()))))
    write('pools/INPUT_SNAPSHOT.json',dict(data_release='v2.1',images=pools))
    write('pools/DEPENDENCIES.json',ledger)
    print('pools',len(pools),dict(Counter(r['action'] for r in ledger)),'records',sum(len(p['records']) for p in pools))


if __name__=='__main__':main()
