#!/usr/bin/env python3
"""Read delivered ZIP bytes and validate exact design/result/geometry joins.

This checks scientific keys after package_and_verify.py has checked CRCs,
all CSV/gzip EOFs and field widths. It can operate on the saved-and-retrieved
P01/P02 packages; optional P03 full native states are checked when supplied.
No local source table substitutes for the bytes in these archives.
"""
from pathlib import Path
import argparse, collections, contextlib, csv, gzip, hashlib, io, json, math, zipfile


class Archives:
    def __init__(self, paths):
        self.zips=[zipfile.ZipFile(p) for p in paths]
        self.names={}
        for z in self.zips:
            for entry in z.infolist():
                if not entry.is_dir():
                    self.names.setdefault(entry.filename,[]).append(z)

    def find(self, suffix, multiple=False):
        found=sorted(n for n in self.names if n.endswith(suffix))
        if not multiple and len(found)!=1:
            raise ValueError(('expected one',suffix,found))
        return found if multiple else found[0]

    @contextlib.contextmanager
    def stream(self, name):
        # Identical utility/manifest copies may occur in more than one package.
        with self.names[name][0].open(name) as binary:
            raw=gzip.GzipFile(fileobj=binary) if name.endswith('.gz') else binary
            with io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as text:
                yield text

    def json(self,name):
        with self.stream(name) as f:return json.load(f)

    def rows(self,names,kind='csv'):
        for name in names:
            with self.stream(name) as f:
                if kind=='csv':
                    reader=csv.DictReader(f)
                    for row in reader:
                        if None in row:raise ValueError(('extra field',name))
                        yield row
                else:
                    for line in f:yield json.loads(line)

    def table(self,filename,kind='csv'):
        plain=[n for n in self.names if n.endswith('/new_endpoints/'+filename)]
        stem=filename.removesuffix('.csv.gz').removesuffix('.jsonl.gz')
        parts=sorted(n for n in self.names if '/new_endpoints/table_shards/'+stem+'/' in n and n.endswith('.gz'))
        if bool(plain)==bool(parts):raise ValueError(('need whole OR shards',filename,plain,parts))
        return self.rows(plain or parts,kind)


def intfield(row,name):return int(float(row[name]))
def finite(x):
    try:return math.isfinite(float(x))
    except (ValueError,TypeError):return False


def run(paths,check_full=False):
    a=Archives(paths)
    deps={};source=collections.Counter()
    for r in a.rows([a.find('/design/ENDPOINT_DEPENDENCIES.csv.gz')]):
        key=r['team_key']
        if key in deps:raise ValueError(('duplicate dependency',key))
        members=tuple(r['member_workers'].split('|'))
        assert len(set(members))==len(members)==intfield(r,'n')
        objects=tuple(r['member_object_ids'].split('|'))
        assert len(objects)==len(members)
        deps[key]=(r['pool_id'],intfield(r,'n'),members,r['endpoint_source'])
        source[r['endpoint_source']]+=1
    expected_new={k for k,v in deps.items() if v[3]!='inherited_population_20261023'}
    new={};status=collections.Counter()
    for r in a.table('NEW_ENDPOINT_SCALARS.csv.gz'):
        key=r['team_key'];assert key in expected_new and key not in new
        pid,n,members,_=deps[key]
        assert r['pool_id']==pid and intfield(r,'k')==n
        assert set(r['member_workers'].split('|'))==set(members)
        new[key]=(r.get('B8L2'),r.get('score_status'))
        status[r.get('score_status','')]+=1
    assert set(new)==expected_new
    geometry=set();gstatus=collections.Counter()
    for r in a.table('NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz','jsonl'):
        key=r['team_key'];assert key in expected_new and key not in geometry
        assert r['pool_id']==deps[key][0] and r['k']==deps[key][1]
        geometry.add(key);gstatus[str(r.get('score_status'))]+=1
    assert geometry==expected_new
    orders={}
    for r in a.rows([a.find('/design/NEW_EXACT_ORDER_DESIGN.csv.gz')]):
        key=r['path_id'];assert key not in orders
        order=tuple(r['worker_order'].split('|'));assert len(set(order))==len(order)==intfield(r,'pool_n')
        orders[key]=(r['pool_id'],order,r['base_path_id'],r['policy'])
    links={};by_path=collections.Counter()
    for r in a.rows([a.find('/design/NEW_PREFIX_TEAM_LINKS.csv.gz')]):
        p,k=r['path_id'],intfield(r,'k');key=(p,k)
        assert key not in links
        endpoint=r['team_key'];pid,n,members,_=deps[endpoint]
        assert orders[p][0]==pid and n==k
        assert set(orders[p][1][:k])==set(members)
        assert r['entrant_worker']==orders[p][1][k-1]
        links[key]=endpoint;by_path[p]+=1
    assert set(orders)==set(by_path)
    assert all(by_path[p]==len(orders[p][1]) for p in orders)
    seen=set();prefixstatus=collections.Counter();new_q_checked=0
    for r in a.table('NEW_PREFIX_VALUES_COMPACT.csv.gz'):
        key=(r['path_id'],intfield(r,'k'));endpoint=r['team_key']
        assert key not in seen and links[key]==endpoint
        seen.add(key);prefixstatus[r.get('score_status','')]+=1
        if endpoint in new:
            q=new[endpoint][0]
            assert finite(q)==finite(r['B8L2'])
            if finite(q):assert math.isclose(float(q),float(r['B8L2']),rel_tol=1e-12,abs_tol=1e-10)
            new_q_checked+=1
    assert seen==set(links)
    exact={}
    for r in a.rows([a.find('/design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz')]):
        key=(r['pool_id'],intfield(r,'k'),r['team_key'])
        assert key not in exact and deps[key[2]][:2]==key[:2]
        exact[key]=float(r['marginal_weight'])
    exactseen=set();weights=collections.defaultdict(float)
    for r in a.table('EXACT_MARGINAL_VALUES.csv.gz'):
        key=(r['pool_id'],intfield(r,'k'),r['team_key'])
        assert key in exact and key not in exactseen
        exactseen.add(key);weights[key[:2]]+=float(r['marginal_weight'])
    assert exactseen==set(exact)
    assert all(abs(v-1)<1e-9 for v in weights.values())
    full_count=None
    if check_full:
        raw_names=sorted(n for n in a.names if '/new_endpoints/parts/' in n and n.endswith('.geometry_state.jsonl.gz'))
        raw=set()
        for r in a.rows(raw_names,'jsonl'):
            key=r['team_key'];assert key not in raw
            assert key in deps and deps[key][3]=='new_native_required_20261025'
            raw.add(key)
        assert raw=={k for k,v in deps.items() if v[3]=='new_native_required_20261025'}
        full_count=len(raw)
    return dict(source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
        archives=[dict(path=str(p.resolve()),bytes=p.stat().st_size,
            sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()) for p in paths],
        provenance='All checked rows came from the supplied downloaded ZIP files, not source directories.',
        dependencies=len(deps),endpoint_sources=dict(source),new_scalar_rows=len(new),new_compact_geometry_rows=len(geometry),
        new_orders=len(orders),new_prefix_links=len(links),new_prefix_values=len(seen),prefix_values_with_new_Q_checked=new_q_checked,
        exact_marginal_rows=len(exact),exact_pool_k_weight_sums_checked=len(weights),
        full_native_geometry_rows=full_count,score_status_counts=dict(status),
        duplicate_keys=0,missing_keys=0,member_prefix_mismatches=0,exact_weight_errors=0,
        all_read_to_gzip_eof=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--zip',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--check-full-geometry',action='store_true')
    x=p.parse_args();receipt=run(x.zip,x.check_full_geometry)
    x.out.parent.mkdir(parents=True,exist_ok=True);x.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='archives'},ensure_ascii=False))
