"""Associate each unique requested endpoint with all four LOBO count vectors."""
from __future__ import annotations
import argparse,functools,hashlib,json
from pathlib import Path
import pandas as pd
from register_population_orders import save_csv,write_bytes

@functools.lru_cache(maxsize=100000)
def vector_text(axes,counts):
    return json.dumps(dict(zip(axes,counts)),sort_keys=True,separators=(',',':'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--orders',required=True);ap.add_argument('--links',required=True)
    ap.add_argument('--labels',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    orders=pd.read_csv(a.orders,keep_default_na=False)
    links=pd.read_csv(a.links,usecols=['pool_id','path_id','k','team_key'])
    labels=pd.read_csv(a.labels)
    label_groups={key:g for key,g in labels.groupby(['condition','heldout_building','method'])}
    link_paths={path:g.sort_values('k').team_key.tolist() for path,g in links.groupby('path_id',sort=False)}
    seen=set();rows=[]
    axes_rows=[]
    for pid,paths in orders.groupby('pool_id',sort=False):
        meta=paths.iloc[0];condition=meta.condition;building=meta.building
        specifications=[];families={}
        for prefix,method in [('structure','V3_BEHAVIOR'),('joint','V3_JOINT_QT')]:
            l=label_groups.get((condition,building,method),pd.DataFrame())
            families[prefix+'_family']='|'.join(sorted(l.selected_family.unique())) if len(l) else 'UNKNOWN'
            for tier in ['coarse','fine']:
                col=tier+'_label';name=prefix+'_'+tier
                known=l[l.known.eq(True)] if len(l) else l
                classids=sorted(set(known[col].dropna())|{'UNKNOWN'}) if len(known) else ['UNKNOWN']
                axes=tuple(classids);index={s:i for i,s in enumerate(axes)}
                wl={r.worker_id:index[getattr(r,col)] for r in known.itertuples()}
                specifications.append((name,axes,index['UNKNOWN'],wl))
                axes_rows.append(dict(pool_id=pid,condition=condition,building=building,method=method,tier=tier,
                                      field=name+'_vector',axes='|'.join(axes),selected_family=families[prefix+'_family']))
        for path in paths.itertuples():
            workers=path.worker_order.split('|');keys=link_paths[path.path_id]
            assert len(workers)==len(keys)
            counts=[[0]*len(s[1]) for s in specifications]
            for k,(worker,key) in enumerate(zip(workers,keys),1):
                for spec,c in zip(specifications,counts):c[spec[3].get(worker,spec[2])]+=1
                if key in seen:continue
                seen.add(key)
                row=dict(team_key=key,pool_id=pid,image=meta.image,condition=condition,building=building,k=k,**families)
                for spec,c in zip(specifications,counts):
                    assert sum(c)==k
                    row[spec[0]+'_vector']=vector_text(spec[1],tuple(c))
                    row[spec[0]+'_unknown_n']=c[spec[2]]
                rows.append(row)
    frame=pd.DataFrame(rows)
    assert set(frame.team_key)==set(links.team_key)
    save_csv(frame,out/'ENDPOINT_CLASS_VECTORS.csv.gz')
    save_csv(pd.DataFrame(axes_rows).drop_duplicates(),out/'CLASS_VECTOR_AXES_BY_POOL.csv')
    receipt=dict(unique_endpoints=len(frame),prefix_links=len(links),vector_fields=4,all_vectors_sum_to_k=True,
                 unknown_preserved=True,zero_classes_included=True,labels_target_building_excluded=True,
                 label_source_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),
                 interpretation='counts use local fold identifiers; cross-building grouping must use role definitions, never raw class IDs',
                 vector_scope='all registered endpoint member sets; fusion computation status is separately maintained by root results')
    write_bytes(out/'CLASS_VECTOR_RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(receipt,flush=True)

if __name__=='__main__':main()
