"""接合同房完整端点；原结构选队不变，联合分类配比独立更新。"""
import gzip
import json
from collections import Counter
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read

CURRENT=ROOT/'research/same_room/same_room_current_classes_v2_20261023'
LARGE=ROOT/'research/same_room/same_room_large_block_rebuilt_20261023'
TARGET=OUT/'same_room_frozen_design'
METRICS=['B8L2','D10','WQ','A10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','height_mean_ratio','boundary_loss','direction_loss','height_loss','global_height_loss','local_height_loss','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','reference_node_shortfall','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']


def main():
    TARGET.mkdir(exist_ok=True)
    patches={}
    for path in (OUT/'same_room_endpoint_rescore/shards').glob('*.jsonl.gz'):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);v={**(r['result'] or {}),**r['reference_dependent_diagnostics']}
                v.update(team_key=r['team_key'],pool_id=r['pool_id'],member_workers=r['member_workers'],reference_id=r['reference_id'],reference_version=r['reference_version'])
                v['complete_evaluable']=r['original_complete_evaluable'] and (r['result'] or {}).get('score_status')=='complete_conditional'
                v['score_status']='no_connection' if r['rescore_state']=='original_no_connection' else (r['result'] or {}).get('score_status',r['original_score_status'])
                patches[r['team_key']]=v
    assert read(OUT/'same_room_geometry_recovery/CHECKS.json')['complete']
    for path in (OUT/'same_room_geometry_recovery').rglob('part_*.jsonl.gz'):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);assert r['team_key'] not in patches;patches[r['team_key']]=r
    pools={p['pool_id']:p['meta'] for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    affected={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    checks=[]
    for name,paths in [('current_classes',sorted((CURRENT/'results/native/parts').glob('*.csv.gz'))),('large_block',[LARGE/'native_endpoints/ENDPOINT_SCALARS.csv.gz'])]:
        d=pd.concat([pd.read_csv(p,low_memory=False) for p in paths],ignore_index=True).set_index('team_key',drop=False)
        assert d.index.is_unique
        keys=set(d[d.pool_id.isin(affected)].index);assert keys<=patches.keys()
        for key in sorted(keys):
            r=patches[key];assert set(d.at[key,'member_workers'].split('|'))==set(r['member_workers'])
            reference_nodes=r.get('reference_nodes')
            if reference_nodes is None:
                reference_nodes=d.at[key,'reference_nodes'] if 'reference_nodes' in d else None
            if reference_nodes is not None and r.get('nodes') is not None:
                r['reference_node_shortfall']=max(0,reference_nodes-r['nodes'])
            for c in METRICS:d.at[key,c]=r.get(c)
            for c in ['complete_evaluable','score_status','reference_id','reference_version']:d.at[key,c]=r[c]
        for c in ['difficulty','reference_id','reference_version']:
            d[c]=d.pool_id.map({pid:meta[c] for pid,meta in pools.items()})
        assert d.reference_id.notna().all()
        d['data_release']='v2.1';folder=TARGET/name/'native';folder.mkdir(parents=True,exist_ok=True)
        d.to_csv(folder/'ENDPOINT_SCALARS.csv.gz',index=False,encoding='utf-8-sig')
        if name=='current_classes':
            (folder/'pools').mkdir(exist_ok=True)
            for pid,g in d.groupby('pool_id'):
                with gzip.open(folder/'pools'/(pid+'.json.gz'),'wt',encoding='utf8') as f:
                    json.dump(dict(pool_id=pid,scalar_only_delivery_adapter=True,teams=g.astype(object).where(pd.notna(g),None).to_dict('records')),f,ensure_ascii=False,allow_nan=False)
        checks.append(dict(study=name,teams=len(d),updated_teams=len(keys),quality_valid=int(d.B8L2.notna().sum()),pools=d.pool_id.nunique()))
    # Selection was exclusively V3 structure; its verified unchanged labels preserve every actual team.
    panels=pd.read_csv(CURRENT/'design/PANELS.csv');links=pd.read_csv(CURRENT/'design/PANEL_TEAM_LINKS.csv.gz')
    labels=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    labels=labels[labels.condition.eq('manual')&labels.heldout_building.ne('ALL')]
    lm={(b,w,m):c for b,w,m,c in labels[labels.known][['heldout_building','worker_id','method','coarse_label']].itertuples(index=False,name=None)}
    buildings=panels.set_index('panel_id').building;vectors=[];known=[]
    for row in links.itertuples():
        b=buildings[row.panel_id];ws=row.member_set_key.split('|')
        structure=Counter(lm[b,w,'V3_BEHAVIOR'] for w in ws)
        assert json.loads(row.structure_vector)==dict(structure)
        ok=all((b,w,'V3_JOINT_QT') in lm for w in ws);known.append(ok)
        vectors.append(json.dumps(dict(sorted(Counter(lm.get((b,w,'V3_JOINT_QT'),'unknown') for w in ws).items())),sort_keys=True,separators=(',',':')))
    changed=int((links.joint_vector!=vectors).sum());links['joint_vector_v2']=links.joint_vector;links['joint_vector']=vectors;links['joint_all_known']=known
    target=OUT/'same_room_current_labels_design';target.mkdir(exist_ok=True)
    for side in ['a','b']:panels['difficulty_'+side]=panels['pool_id_'+side].map({pid:meta['difficulty'] for pid,meta in pools.items()})
    panels.to_csv(target/'PANELS.csv',index=False,encoding='utf-8-sig');links.to_csv(target/'PANEL_TEAM_LINKS.csv.gz',index=False,encoding='utf-8-sig')
    labels.to_csv(target/'LABELS_AND_HISTORIES.csv.gz',index=False,encoding='utf-8-sig')
    (TARGET/'INPUT_CHECKS.json').write_text(json.dumps(dict(studies=checks,updated_joint_vector_links=changed,structure_vectors_all_unchanged=True,actual_members_and_relations_unchanged=True,new_fusion=0),indent=2),encoding='utf8')


if __name__=='__main__':main()
