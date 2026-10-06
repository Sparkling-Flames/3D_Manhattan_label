"""Read delivered ledgers; test signed orientation compatibility per strict group."""
import argparse,collections,gzip,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--delivery',type=Path,default=Path('../oct6-structure-intake/extracted/structure_paths_20261006'));p.add_argument('--out',type=Path,default=Path('orientation_consistency_audit.json'));a=p.parse_args()
rows=[]
for f in sorted((a.delivery/'results').glob('*/*_path_evidence.jsonl.gz')):
    state=json.loads(f.with_name(f.name.replace('_path_evidence.jsonl.gz','.json')).read_text())
    by={tuple(sorted(r['nodes'])):r for r in map(json.loads,gzip.open(f,'rt'))}
    for g in state['path_witness_MV']['groups']:
        ns=g['node_indices'];adj=collections.defaultdict(list);singleton=both=0
        for j,x in enumerate(ns):
            for y in ns[j+1:]:
                r=by[tuple(sorted((x,y)))];assert r['status']=='witnessed'
                signs={w['orientation'] for w in r['witnesses']}
                if len(signs)==1:
                    s=next(iter(signs));adj[x].append((y,s));adj[y].append((x,s));singleton+=1
                else:both+=1
        labels={};conflicts=[]
        for x in ns:
            if x in labels:continue
            labels[x]=1;stack=[x]
            while stack:
                x=stack.pop()
                for y,s in adj[x]:
                    if y in labels:
                        if labels[y]!=labels[x]*s:conflicts.append([x,y,s])
                    else:labels[y]=labels[x]*s;stack.append(y)
        rows.append(dict(source=str(f.relative_to(a.delivery)),group=g['feature_id'],support=g['support'],selected=g['selected'],singleton_orientation_edges=singleton,both_orientation_edges=both,conflicts=conflicts))
a.out.write_text(json.dumps(rows,indent=2))
print(json.dumps({'groups':len(rows),'nonsingleton_groups':sum(r['support']>=2 for r in rows),'orientation_conflict_groups':sum(bool(r['conflicts']) for r in rows)},indent=2))
