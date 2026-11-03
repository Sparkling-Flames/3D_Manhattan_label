"""Archive and bind returned human orders; never change formal fusion or scores."""
from pathlib import Path
import argparse,gzip,json,shutil
from collections import Counter
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/fusion/missing_ring_review_20261104'


def validate_order(record,case):
    binding=json.loads(record['binding'])
    oid='missing_ring:'+case['review_id']
    points=[p for n in case['nodes'] for p in n['points']]
    assert binding['id']==oid and binding['points']==points,('binding',oid)
    assert binding['links']==[[i,i+1] for i in range(0,len(points),2)],('pairs',oid)
    order=record['order']
    assert all(type(i) is int for i in order) and sorted(order)==list(range(len(case['nodes']))),('permutation',oid)
    return [case['nodes'][i]['feature_id'] for i in order]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);args=ap.parse_args()
    doc=json.loads(args.source.read_text(encoding='utf-8-sig'))
    assert doc['schema']=='missing_ring_order_review_20261104_v1' and doc['examples_only'] is False
    expected=set(json.loads((BASE/'VALIDATED_REVIEW_IDS.json').read_text()))
    assert set(doc['records'])==set(doc['objects'])=={'missing_ring:'+rid for rid in expected}
    groups=pd.read_csv(BASE/'TARGETED_MANUAL_CASES.csv').set_index('representative_review_id')
    def case(rid):
        with gzip.open(BASE/'prepared'/(rid+'.json.gz'),'rt',encoding='utf-8') as f:return json.load(f)
    rows=[];accepted={}
    for oid,record in doc['records'].items():
        rid=oid.removeprefix('missing_ring:');c=case(rid);meta=doc['objects'][oid]
        order=validate_order(record,c)
        assert record['status'] in {'confirmed','pairing','pending','draft'}
        for field in ['review_id','team_key','image','condition','k','reference_id','reference_version','data_release']:
            assert meta[field]==c[field],(rid,field)
        assert meta['feature_ids']==[n['feature_id'] for n in c['nodes']]
        assert meta['node_supports']==[n['support'] for n in c['nodes']]
        gid=groups.loc[rid,'group_id'];assert gid==meta['geometry_group_id']
        rows.append(dict(group_id=gid,review_id=rid,team_key=c['team_key'],image=c['image'],k=c['k'],nodes=len(c['nodes']),status=record['status'],note=record.get('note',''),manual_feature_order='|'.join(order),updated_at=record.get('updated_at','')))
        if record['status']=='confirmed':accepted[gid]=(c,record)
    targets=pd.read_csv(BASE/'TARGETED_MANUAL_ALL_REFERENCES.csv.gz')
    bindings=[]
    for r in targets[['group_id','review_id','team_key']].drop_duplicates().itertuples(index=False):
        if r.group_id not in accepted:continue
        original,record=accepted[r.group_id];target=case(r.review_id)
        # Coordinate bijection, not local node-number equality, permits exact-group reuse.
        lookup={json.dumps(n['points']):n['feature_id'] for n in target['nodes']}
        assert len(lookup)==len(target['nodes'])==len(original['nodes'])
        assert set(lookup)=={json.dumps(n['points']) for n in original['nodes']}
        assert (target['image_id'],target['reference_id'],target['reference_version'])==(original['image_id'],original['reference_id'],original['reference_version'])
        mapped=[lookup[json.dumps(original['nodes'][i]['points'])] for i in record['order']]
        bindings.append(dict(group_id=r.group_id,review_id=r.review_id,team_key=r.team_key,image=target['image'],manual_feature_order='|'.join(mapped),order_binding=json.dumps(target['nodes'],ensure_ascii=False),application_status='validated_not_applied'))
    out=BASE/'user_order_return';out.mkdir(exist_ok=True)
    dest=out/'融合节点排序_全部图片.json'
    if dest.exists():assert dest.read_bytes()==args.source.read_bytes(),'Existing return differs; preserve separately.'
    else:shutil.copyfile(args.source,dest)
    pd.DataFrame(rows).to_csv(out/'REVIEW_DECISIONS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(bindings).to_csv(out/'VALIDATED_ENDPOINT_ORDERS.csv.gz',index=False,encoding='utf-8-sig')
    joined=targets.merge(pd.DataFrame(bindings)[['group_id','review_id','team_key']],on=['group_id','review_id','team_key'],validate='many_to_one')
    joined.to_csv(out/'AFFECTED_CURRENT_REFERENCES.csv.gz',index=False,encoding='utf-8-sig')
    impact=[]
    for module,g in joined.groupby('module'):
        impact.append(dict(module=module,geometry_groups=g.group_id.nunique(),saved_team_keys=g.team_key.nunique(),source_rows=len(g[['source','source_row']].drop_duplicates()),references=len(g)))
    pd.DataFrame(impact).to_csv(out/'IMPACT_BY_MODULE.csv',index=False,encoding='utf-8-sig')
    receipt=dict(schema=doc['schema'],records=len(rows),statuses=dict(Counter(r['status'] for r in rows)),images=len({r['image'] for r in rows}),expected_groups=len(expected),missing_groups=0,binding_errors=0,validated_endpoint_identities=len(bindings),affected_modules=len(impact),reference_rows=len(joined),formal_results_modified=False,geometry_or_quality_recomputed=False)
    (out/'IMPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False));print(pd.DataFrame(impact).to_string(index=False))


if __name__=='__main__':main()
