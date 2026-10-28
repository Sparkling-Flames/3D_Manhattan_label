"""沿用已采用的直接同房关系和原选队规则，更新参考可用性与楼外标签。"""
import gzip
import json
import sys
import types
from collections import Counter
import pandas as pd
from .rebuild_v21_20261028 import ROOT,OUT,read
from .prepare_v21_same_room_analysis_20261028 import CURRENT,LARGE
from .register_v21_policies_20261028 import definitions

TARGET=OUT/'same_room_current_capacity'


def annotate_designs():
    original=set(pd.read_csv(CURRENT/'source_index/DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv',usecols=['pair_key']).pair_key)
    for directory,name in [('same_room_current_extended_design','PANELS.csv'),('same_room_current_large_design','STRICT_ABC_EVENTS.csv.gz')]:
        path=OUT/directory/name;d=pd.read_csv(path,low_memory=False)
        d['support_origin']=d.pair_key.map(lambda key:'original_direct_relation' if key in original else 'added_existing_direct_relation')
        d['data_release']='v2.1'
        if 'input_commit' in d:
            if 'algorithm_source_commit' not in d:d['algorithm_source_commit']=d.input_commit
            d['input_commit']=None
        d.to_csv(path,index=False,encoding='utf-8-sig')
        receipt=dict(data_release='v2.1',current_inputs='same_room_current_capacity/INPUT_SNAPSHOT.json.gz',algorithm='frozen_original_design_and_seed',input_commit=None,file_hashes_computed=False,
            support_origin=d.groupby('support_origin').agg(rows=('pair_key','size'),pairs=('pair_key','nunique')).to_dict('index'))
        (OUT/directory/'INPUT_IDENTITY.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')


def main():
    TARGET.mkdir(exist_ok=True)
    snapshot=read(OUT/'pools/INPUT_SNAPSHOT.json')
    pools={p['meta']['image_id']:p for p in snapshot['images'] if p['meta']['condition']=='manual' and len(p['records'])>=3}
    labels=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    labels=labels[labels.condition.eq('manual')&labels.heldout_building.ne('ALL')]
    defs=definitions(labels);coarse=defs[defs.tier.eq('coarse')].copy()
    coarse['turn_center_order']=coarse.groupby(['method','heldout_building']).turn_history_mean.rank(method='first').astype(int)
    lm={(r.method,r.heldout_building,r.worker_id):r for r in labels.itertuples()}
    cm={(r.method,r.heldout_building,r.class_id):r._asdict() for r in coarse.itertuples(index=False)}
    frozen=pd.read_csv(CURRENT/'source_index/DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv')
    original={frozenset([r.image_id_a,r.image_id_b]):r for r in frozen[frozen.method.eq('V3_BEHAVIOR')].itertuples()}
    capacity=[];members=[];seen=set()
    for relation in read(ROOT/'research/same_room/relation_adoption_20261016/relations.json'):
        old=original.get(frozenset([relation['image_a'],relation['image_b']]))
        if not relation['physical_adopted'] or relation['substantive_conflict'] or (relation['oos_pending'] and old is None):continue
        if relation['image_a'] not in pools or relation['image_b'] not in pools:continue
        if old:a,b=pools[old.image_id_a],pools[old.image_id_b]
        else:a,b=sorted([pools[relation['image_a']],pools[relation['image_b']]],key=lambda p:p['pool_id'])
        key=a['pool_id']+'||'+b['pool_id'];assert key not in seen;seen.add(key)
        common=sorted({r['worker_id'] for r in a['records']}&{r['worker_id'] for r in b['records']})
        if old:assert set(common)==set(old.common_members.split('|'))
        building=a['meta']['building'];assert building==b['meta']['building']
        meta=dict(pair_key=key,condition='manual',building=building,groups='|'.join(sorted(relation['user_group_ids'])),physical_adopted=True,scope_comparable=relation['scope_comparable'],substantive_conflict=False,oos_pending=relation['oos_pending'],relation_tier=relation['tier'])
        for side,pool in [('a',a),('b',b)]:
            for field in ['image','image_id','reference_id','layer','difficulty']:meta[field+'_'+side]=pool['meta'][field]
            meta['pool_id_'+side]=pool['pool_id'];meta['pool_n_'+side]=len(pool['records'])
        meta['ordinary_comparable']=meta['scope_comparable'] and meta['layer_a']==meta['layer_b']=='ordinary_manual'
        if old:
            for field in ['groups','physical_adopted','scope_comparable','substantive_conflict','oos_pending','relation_tier','ordinary_comparable']:meta[field]=getattr(old,field)
        for method in ['V3_BEHAVIOR','V3_JOINT_QT']:
            assigned={w:(lm[method,building,w].coarse_label if (method,building,w) in lm and lm[method,building,w].known else 'unknown') for w in common}
            counts=Counter(assigned.values());unknown=[w for w in common if assigned[w]=='unknown']
            fold=labels[labels.method.eq(method)&labels.heldout_building.eq(building)&labels.known]
            assert fold.selected_family.nunique()==1
            capacity.append(dict(meta,method=method,common_n=len(common),known_common_n=len(common)-len(unknown),unknown_common_n=len(unknown),n_available_classes=len(counts)-int('unknown' in counts),n_classes_with_ge2=sum(n>=2 for cl,n in counts.items() if cl!='unknown'),selected_family=fold.selected_family.iloc[0],coarse_k=fold.coarse_label.nunique(),fine_k=fold.fine_label.nunique(),class_counts=json.dumps({c:n for c,n in sorted(counts.items()) if c!='unknown'},sort_keys=True),common_members='|'.join(common),unknown_members='|'.join(unknown)))
            for cl,n in sorted(counts.items()):
                center=cm.get((method,building,cl),{})
                members.append(dict(meta,method=method,class_id=cl,n_common=n,members='|'.join(w for w in common if assigned[w]==cl),selected_family=fold.selected_family.iloc[0],**{c:v for c,v in center.items() if c.endswith('_mean') or c=='turn_center_order'}))
    cap=pd.DataFrame(capacity);mem=pd.DataFrame(members)
    old_behavior=frozen[frozen.method.eq('V3_BEHAVIOR')]
    now=cap[cap.method.eq('V3_BEHAVIOR')].set_index('pair_key')
    assert set(old_behavior.pair_key)<=set(now.index)
    for r in old_behavior.itertuples():assert json.loads(r.class_counts)==json.loads(now.loc[r.pair_key,'class_counts']),(r.pair_key,r.class_counts,now.loc[r.pair_key,'class_counts'])
    for name,frame in [('DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv',cap),('DIRECT_PAIR_CLASS_MEMBERS.csv',mem),('CURRENT_MANUAL_LABELS_LOBO.csv',labels),('CURRENT_MANUAL_FOLD_CENTERS.csv',defs)]:frame.to_csv(TARGET/name,index=False,encoding='utf-8-sig')
    with gzip.open(TARGET/'INPUT_SNAPSHOT.json.gz','wt',encoding='utf8') as f:json.dump(snapshot,f,ensure_ascii=False)
    added=cap[~cap.pair_key.isin(frozen.pair_key)&cap.method.eq('V3_BEHAVIOR')]
    added.to_csv(TARGET/'ADDED_DIRECT_PAIRS.csv',index=False,encoding='utf-8-sig')
    checks=dict(data_release='v2.1',direct_pairs=cap.pair_key.nunique(),original_pairs=frozen.pair_key.nunique(),added_pairs=len(added),added_scope_comparable=int(added.scope_comparable.sum()),old_structure_members_verified_unchanged=True,relation_source='existing_adopted_direct_relations_no_transitive_expansion')
    (TARGET/'CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf8');print(checks,flush=True)
    source=CURRENT/'code/design/build_design.py';code=source.read_text(encoding='utf8')
    old="repo / 'research/workers/personnel_mixture_comparison_20261022/inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz'"
    assert code.count(old)==1
    module=types.ModuleType('v21_same_room_design');module.__file__=str(source)
    exec(compile(code.replace(old,"capacity_dir / 'CURRENT_MANUAL_LABELS_LOBO.csv'"),str(source),'exec'),module.__dict__)
    module.build(ROOT,TARGET,OUT/'same_room_current_extended_design')
    oldpan=pd.read_csv(CURRENT/'design/PANELS.csv');newpan=pd.read_csv(OUT/'same_room_current_extended_design/PANELS.csv')
    assert set(oldpan.panel_id)<=set(newpan.panel_id)
    compare=oldpan.merge(newpan,on='panel_id',suffixes=('_old','_new'),validate='one_to_one')
    for field in ['core','candidates','n','k_selected']:assert compare[field+'_old'].fillna('').eq(compare[field+'_new'].fillna('')).all()
    source=LARGE/'design/code/build_strict_abc_design.py';module=types.ModuleType('v21_same_room_large_design');module.__file__=str(source)
    exec(compile(source.read_text(encoding='utf8'),str(source),'exec'),module.__dict__)
    module.sha256=lambda path:None
    sys.argv=[str(source),'--input-dir',str(TARGET),'--snapshot',str(TARGET/'INPUT_SNAPSHOT.json.gz'),'--output',str(OUT/'same_room_current_large_design')]
    module.main()
    annotate_designs()


if __name__=='__main__':main()
