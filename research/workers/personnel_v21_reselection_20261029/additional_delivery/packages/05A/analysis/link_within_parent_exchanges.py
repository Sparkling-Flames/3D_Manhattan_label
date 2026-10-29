"""Identify genuine within-parent fine-class exchanges under frozen fold labels."""
from pathlib import Path
import argparse,json,re
from collections import Counter
import pandas as pd
from measure_registered_events import save,jsave

def main():
 p=argparse.ArgumentParser();p.add_argument('--labels',required=True);p.add_argument('--events',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);l=pd.read_csv(a.labels,low_memory=False);e=pd.read_csv(a.events,low_memory=False);methods=set(l.method)
 parents={}
 for method in methods:
  m=re.match(r'^(.*)_K([3-9])$',method)
  if m and f'{m[1]}_K{int(m[2])-1}' in methods:parents[method]=f'{m[1]}_K{int(m[2])-1}'
  if method.endswith('_FINE') and method[:-5]+'_COARSE' in methods:parents[method]=method[:-5]+'_COARSE'
 known=l[l.known.astype(str).str.lower().isin(['true','1','1.0'])]
 maps={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in known.groupby(['method','heldout_building'])}
 hierarchy=[]
 for child,parent in parents.items():
  for (m,b),g in known[known.method.eq(child)].groupby(['method','heldout_building']):
   pm=maps[parent,b]
   for c,cg in g.groupby('class_id'):
    pp={pm[w] for w in cg.worker_id if w in pm}
    hierarchy.append(dict(child_method=child,parent_method=parent,heldout_building=b,child_class=c,parent_classes='|'.join(sorted(pp)),
      nested=len(pp)==1 and all(w in pm for w in cg.worker_id),workers=len(cg),parent_known_workers=sum(w in pm for w in cg.worker_id)))
 rows=[]
 for r in e.itertuples():
  parent=parents.get(r.method)
  if not parent:continue
  pm=maps[parent,r.heldout_building]
  def vec(s):
   z=Counter(pm.get(w,'unknown') for w in s.split('|'));return '|'.join(f'{k}:{v}' for k,v in sorted(z.items()))
  x={pm.get(w,'unknown') for w in r.X.split('|')};y={pm.get(w,'unknown') for w in r.Y.split('|')};z={pm.get(w,'unknown') for w in r.Z.split('|')}
  va,vb,vc=[vec(getattr(r,k+'_members')) for k in 'ABC'];fixed=va==vb==vc and x==y==z and len(x)==1 and 'unknown' not in x
  rows.append(dict(event_id=r.event_id,method=r.method,heldout_building=r.heldout_building,parent_method=parent,fine_exchange_fixed_parent=fixed,
   X_parent='|'.join(sorted(x)),Y_parent='|'.join(sorted(y)),Z_parent='|'.join(sorted(z)),A_parent_vector=va,B_parent_vector=vb,C_parent_vector=vc))
 save(out/'METHOD_HIERARCHY_ALL_LOBO.csv',pd.DataFrame(hierarchy));links=pd.DataFrame(rows);save(out/'EVENT_PARENT_LINKS.csv.gz',links)
 jsave(out/'RECEIPT.json',dict(events_with_parent=len(links),events_fixed_parent=int(links.fine_exchange_fixed_parent.sum()),
    child_methods=len(parents),design='Same D,n,m and same full parent-class count vector; child-class source X/Y differs from Z',new_fusions=0))
 print(json.dumps(dict(events_with_parent=len(links),fixed_parent=int(links.fine_exchange_fixed_parent.sum()))),flush=True)
if __name__=='__main__':main()
