"""Freeze corrected membership and enumerate only changed natural-prefix requests."""
import json,gzip,io,zipfile
from pathlib import Path
from collections import Counter
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
P='HOHONET_doorway_v21_20261031/'
def main():
    z1=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_01_POOLS_REFERENCES_EVIDENCE.zip')
    z2=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip')
    z4=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip')
    def table(z,n,**kw):return pd.read_csv(io.BytesIO(gzip.decompress(z.read(P+n))),**kw)
    def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    ledger=json.loads(z1.read(P+'stage01_pools/FINAL_RECORD_LEDGER.json'))
    overlay={r['object_id']:r for r in json.loads((OUT/'CORRECTION_OVERLAY.json').read_text(encoding='utf8'))}
    changes=[]
    for r in ledger:
        if r['object_id'] not in overlay:continue
        o=overlay[r['object_id']];assert not o['correction_reasons']
        old=r['final_scope'];new=o['corrected_scope']
        r['scope_before_correction']=old;r['final_scope']=new
        r['final_scope_code']={'空间1':'space1','空间2':'space2','全部':'whole_compatible'}.get(new,'unresolved' if new is None else 'rejected')
        r['final_compatible_pool_member']=new in ['空间1','空间2','全部']
        r['scope_correction_version']='doorway_visual_scope_20261031_r1'
        if o['correction_status']=='agent_visual_reviewed':r['final_scope_source']='agent_visual_scope_20261031_r1'
        r['ring_confirmation_receipt']='USER_RING_CONFIRMATION.json' if o['ring_confirmed_by_user'] else None
        r['historical_quality_gate_preserved']=True
        if old!=new:changes.append(dict(object_id=r['object_id'],image=r['image'],worker=r['worker'],before=old,after=new))
    save('CORRECTED_RECORD_LEDGER.json',ledger);save('SCOPE_CORRECTIONS_16.json',changes)
    pools=json.loads(z4.read(P+'stage04_computation/design/POOL_DEFINITIONS_WITH_SENSITIVITY.json'))
    orders=table(z2,'stage04_computation/design/BASE_256_ORDERS.csv.gz')
    index=table(z4,'stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz')
    scores=table(z4,'stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=['score_key'])
    cached={(r.image,frozenset(r.member_object_ids.split('|'))):r.physical_team_key for r in index.itertuples()};sk=set(scores.score_key)
    newpools=[];changed=[];requests={};counts=Counter()
    for p in pools:
        if p.get('sensitivity'):continue
        old=set(p['records']);target={'space1':'空间1','space2':'空间2','whole_compatible':'全部'}.get(p['family'])
        if target:
            rows=[r for r in ledger if r['base_candidate'] and r['image']==p['image'] and r['final_scope']==target]
            p=dict(p,records=[r['object_id'] for r in rows],workers=[r['worker'] for r in rows],n=len(rows),
                n_inherited_quality_hold=sum(not r['inherited_quality_eligible'] for r in rows))
        newpools.append(p)
        if set(p['records'])==old:continue
        changed.append(dict(pool_id=p['pool_id'],image=p['image'],family=p['family'],old_n=len(old),new_n=p['n']))
        for r in orders[orders.image==p['image']].itertuples():
            members=[oid for oid in r.base_member_object_ids.split('|') if oid in set(p['records'])]
            for k in range(1,len(members)+1):
                team=tuple(sorted(members[:k]));key=(p['image'],team);phys=cached.get((p['image'],frozenset(team)))
                item=requests.setdefault(key,dict(image=p['image'],members=list(team),k=k,cached_physical_team_key=phys,targets=[]))
                if p['target'] not in item['targets']:item['targets'].append(p['target'])
                counts['prefix_attempts']+=1
    save('CORRECTED_PRIMARY_POOLS.json',newpools);save('CHANGED_POOLS.json',changed)
    save('DELTA_TEAM_REQUESTS.json',list(requests.values()))
    summary=dict(changed_records=len(changes),changed_images=len({r['image'] for r in changes}),changed_pools=changed,
        scope_counts=dict(Counter(r['final_scope'] or 'unresolved' for r in ledger if r['base_candidate'])),
        unique_teams_requested=len(requests),missing_physical_teams=sum(not r['cached_physical_team_key'] for r in requests.values()),
        missing_scores_on_cached_teams=sum(r['cached_physical_team_key']+'::'+t not in sk for r in requests.values() if r['cached_physical_team_key'] for t in r['targets']),
        counts=dict(counts),mixed_before_after_memberships_unchanged=True,geometry_changed=False,
        computation_complete=False,scope='自然256所有人数的改动池请求；精确枚举、区间、敏感性需依新池重新构造；k2保持补充身份')
    save('DELTA_PLAN.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
