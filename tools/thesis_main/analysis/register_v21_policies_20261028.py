"""同一自然基序下按当前楼外角色重新排列；旧/新增抽样层保持独立。"""
import gzip
import hashlib
import importlib.util
import json
import pandas as pd
from .rebuild_v21_20261028 import OUT,read
from .prepare_v21_natural_inputs_20261028 import BASE,PRIOR,EXT

TARGET=OUT/'current_policy_design'


def definitions(labels):
    rows=[]
    fields=['turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history','q_history','q_downside','t_history']
    for (method,condition,b),g in labels[labels.known].groupby(['method','condition','heldout_building']):
        for tier in ['coarse','fine']:
            for cl,h in g.groupby(tier+'_label'):
                assert h.selected_family.nunique()==1
                rows.append(dict(method=method,condition=condition,heldout_building=b,tier=tier,class_id=cl,selected_family=h.selected_family.iloc[0],people=len(h),members='|'.join(sorted(h.worker_id)),**{c+'_mean':h[c].mean() for c in fields}))
    return pd.DataFrame(rows)


def main():
    TARGET.mkdir(exist_ok=True)
    labels=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    labels=labels[labels.heldout_building.ne('ALL')]
    labels.to_csv(TARGET/'LABELS_LOBO.csv.gz',index=False,encoding='utf-8-sig')
    defs=definitions(labels);defs.to_csv(TARGET/'FOLD_CLASS_DEFINITIONS.csv',index=False,encoding='utf-8-sig')
    olddefs=pd.read_csv(BASE/'inputs/FOLD_CLASS_DEFINITIONS.csv')
    frozen=olddefs[olddefs.method.eq('V3_BEHAVIOR')].merge(defs,on=['method','condition','heldout_building','tier','class_id'],suffixes=('_old','_new'),validate='one_to_one')
    assert len(frozen)==len(olddefs[olddefs.method.eq('V3_BEHAVIOR')])
    assert frozen.members_old.eq(frozen.members_new).all()
    assert (frozen.turn_history_mean_old-frozen.turn_history_mean_new).abs().max()<1e-10
    spec=importlib.util.spec_from_file_location('v21_native_policies',BASE/'code/order_policies.py')
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    roles=native.RoleBook(TARGET/'LABELS_LOBO.csv.gz',TARGET/'FOLD_CLASS_DEFINITIONS.csv')
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    bases=[]
    for batch,path in [('old8',BASE/'design/EXACT_ORDER_DESIGN.csv.gz'),('prior_new8',PRIOR/'design/NEW_EXACT_ORDER_DESIGN.csv.gz'),('new16',EXT/'design26/NEW_EXACT_ORDER_DESIGN.csv.gz')]:
        d=pd.read_csv(path,low_memory=False,dtype={'seed':str});paired=set(d.loc[d.policy.ne('natural_random'),'base_path_id'])
        d=d[d.policy.eq('natural_random')&d.path_id.isin(paired)].copy();d['base_batch']=batch;bases.append(d)
    for dep in read(OUT/'pools/DEPENDENCIES.json'):
        if dep['action']!='new_or_changed_pool' or dep['pool_n']<3:continue
        pid=dep['pool_id'];plan=read(OUT/'new_space_natural256'/pid/'DESIGN.json')
        rows=[dict(pool_id=pid,path_id=pid+'__new256_'+str(r['path_index']),worker_order='|'.join(r['workers']),base_batch='added32',seed=str(plan['seed']),replicate=r['path_index']) for r in plan['paths'][:32]]
        bases.append(pd.DataFrame(rows))
    bases=pd.concat(bases,ignore_index=True)
    assert bases.path_id.is_unique
    orders=[];links=[];requests={};support=[]
    for pid,g in bases.groupby('pool_id'):
        pool=pools[pid];meta=pool['meta'];workers=sorted(r['worker_id'] for r in pool['records'])
        rolemap={policy:roles.pool_role(workers,meta['condition'],meta['building'],policy) for policy in native.ROLE_SPECS}
        for policy,r in rolemap.items():support.append(dict(meta,**r,data_release='v2.1'))
        for base in g.to_dict('records'):
            order=base['worker_order'].split('|');assert sorted(order)==workers
            choices=[('natural_random',order,dict(target_members=[],eligible=True))]
            for policy,role in rolemap.items():
                if not role['eligible']:continue
                po,check=roles.prioritize(order,meta['condition'],meta['building'],policy)
                assert check==role
                choices.append((policy,po,role))
            for policy,po,role in choices:
                pathid=base['path_id']+'__v21_'+policy
                orders.append({**meta,**role,'policy':policy,'path_id':pathid,'base_path_id':base['path_id'],'base_batch':base['base_batch'],'worker_order':'|'.join(po),'base_worker_order':'|'.join(order),'data_release':'v2.1'})
                for k in range(1,len(po)+1):
                    ws=sorted(po[:k]);key=pid+'__'+hashlib.sha256(json.dumps(ws,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
                    requests[key]=dict(team_key=key,pool_id=pid,worker_ids=ws)
                    links.append(dict(pool_id=pid,path_id=pathid,base_path_id=base['path_id'],base_batch=base['base_batch'],policy=policy,k=k,team_key=key,target_present_n=sum(w in role['target_members'] for w in ws)))
    def export(name,frame):
        for c in frame:
            if frame[c].map(lambda x:isinstance(x,list)).any():frame[c]=frame[c].map(lambda x:'|'.join(x) if isinstance(x,list) else x)
        frame.to_csv(TARGET/name,index=False,encoding='utf-8-sig')
    export('ORDERS.csv.gz',pd.DataFrame(orders));export('PREFIX_LINKS.csv.gz',pd.DataFrame(links));export('POOL_ROLE_CAPACITY.csv',pd.DataFrame(support))
    with gzip.open(TARGET/'REQUESTS.json.gz','wt',encoding='utf8') as f:json.dump(list(requests.values()),f)
    checks=dict(data_release='v2.1',bases=len(bases),pools=bases.pool_id.nunique(),orders=len(orders),prefixes=len(links),unique_teams=len(requests),behavior_roles_verified_unchanged=True,selection='current_LOBO_role_centers_stable_partition_of_saved_base_orders',new_sampling=0,new_fusion=0)
    (TARGET/'CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf8');print(json.dumps(checks),flush=True)


if __name__=='__main__':main()
