"""Identity-only historical worker holdouts, with no metric or convergence fitting."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

BASE='analysis_results/uncertainty_cloud_inputs_20260906_v1'
OUTPUT='analysis_results/building_holdout_exploration_20260908_v1/census'
SEED=20260908
SCHEMES=[('two_thirds',2/3),('sixty_percent',.6)]
IDENTITY=['building_id','context_key','image_id','stage','block_index','raw_condition']


def read(path):return pd.read_csv(path,dtype=str,keep_default_na=False)
def js(value):return json.dumps(value,ensure_ascii=False)


def prepare_index(a,lineage):
    if not a.canonical_annotation_id.is_unique or a.duplicated(['context_key','worker_id']).any():raise ValueError('duplicate_canonical_or_worker_context')
    if a[['canonical_annotation_id','worker_id',*IDENTITY]].eq('').any().any():raise ValueError('blank_identity')
    if not lineage.raw_annotation_version_id.is_unique:raise ValueError('duplicate_raw_version')
    if set(lineage.canonical_annotation_id)!=set(a.canonical_annotation_id):raise ValueError('lineage_canonical_universe_differs')
    if not a.current20_member.str.lower().isin(['true','false']).all():raise ValueError('unknown_current20_status')
    if (a.groupby('worker_id').current20_member.nunique()!=1).any():raise ValueError('conflicting_current20_status')
    if any((a.groupby('context_key')[c].nunique()!=1).any() for c in IDENTITY if c!='context_key'):raise ValueError('context_metadata_conflict')
    index=a.copy();index['raw_version_count']=index.canonical_annotation_id.map(lineage.groupby('canonical_annotation_id').size())
    index['nonindependent_revision_count']=index.raw_version_count-1
    return index


def splits(index,replicates=200):
    rng=np.random.default_rng(SEED);roster=sorted(index.worker_id.astype(int).unique().tolist())
    orders=[dict(replicate=i,worker_ids=list(map(str,rng.permutation(roster).tolist()))) for i in range(replicates)]
    buildings={b:set(g.worker_id) for b,g in index.groupby('building_id')}
    cached={b:[({c:g.iloc[0][c] for c in IDENTITY},dict(zip(g.worker_id,g.canonical_annotation_id)))
               for _,g in bg.groupby('context_key')] for b,bg in index.groupby('building_id')}
    people=[]
    for order in orders:
        for b,workers in buildings.items():
            ordered=[w for w in order['worker_ids'] if w in workers]
            for scheme,fraction in SCHEMES:
                n=math.floor(len(ordered)*fraction);history=ordered[:n];validation=ordered[n:]
                people.append(dict(split_id=f"{order['replicate']}|{b}|{scheme}",replicate=order['replicate'],building_id=b,
                    scheme=scheme,history_fraction=fraction,building_worker_count=len(ordered),history_worker_count=n,
                    validation_worker_count=len(validation),history_worker_ids_json=js(history),validation_worker_ids_json=js(validation)))
    def contexts():
        for p in people:
            h=json.loads(p['history_worker_ids_json']);v=json.loads(p['validation_worker_ids_json'])
            for meta,ids in cached[p['building_id']]:
                hh=[w for w in h if w in ids];vv=[w for w in v if w in ids]
                status=('history_empty' if not hh else 'validation_empty' if not vv else 'history_single_with_validation' if len(hh)==1 else 'history_pair_with_validation')
                yield dict(**meta,split_id=p['split_id'],replicate=p['replicate'],scheme=p['scheme'],history_fraction=p['history_fraction'],
                    raw_worker_count=len(ids),history_raw_worker_count=len(hh),validation_raw_worker_count=len(vv),
                    history_worker_ids_json=js(hh),validation_worker_ids_json=js(vv),
                    history_canonical_ids_json=js([ids[w] for w in hh]),validation_canonical_ids_json=js([ids[w] for w in vv]),
                    raw_support_status=status,geometry_support_status='not_evaluated_in_census')
    return orders,people,contexts()


def census_rows(index,keys):
    rows=[]
    for key,g in index.groupby(keys):
        key=key if isinstance(key,tuple) else (key,)
        r=dict(zip(keys,key));r.update(images=g.image_id.nunique(),contexts=g.context_key.nunique(),workers=g.worker_id.nunique(),
            current20_workers=g[g.current20_member.str.lower()=='true'].worker_id.nunique(),canonical_responses=len(g),
            raw_versions=int(g.raw_version_count.sum()),nonindependent_revisions=int(g.nonindependent_revision_count.sum()),
            historical_eligibility_counts_json=js(g.historical_primary_eligibility_status.value_counts(dropna=False).to_dict()),
            legacy_exclusion_reason_counts_json=js(g.legacy_exclusion_reason.value_counts(dropna=False).to_dict()),
            worker_ids_json=js(sorted(g.worker_id.unique(),key=int)),
            minimum_context_workers=int(g.groupby('context_key').worker_id.nunique().min()),
            maximum_context_workers=int(g.groupby('context_key').worker_id.nunique().max()))
        for condition in ['manual','semi','oos']:r[condition+'_canonical_responses']=int((g.raw_condition==condition).sum())
        rows.append(r)
    return pd.DataFrame(rows)


def main(root,out):
    out.mkdir(parents=True,exist_ok=True)
    a=read(root/BASE/'annotations.csv.gz');lineage=read(root/BASE/'facts/annotation_version_lineage.csv.gz')
    index=prepare_index(a,lineage);index.to_csv(out/'canonical_index.csv.gz',index=False)
    lineage.to_csv(out/'annotation_version_lineage.csv.gz',index=False)
    census_rows(index,['building_id']).to_csv(out/'building_census.csv',index=False)
    census_rows(index,['building_id','stage','raw_condition']).to_csv(out/'building_stage_condition_census.csv',index=False)
    orders,people,contexts=splits(index)
    (out/'global_worker_orders.jsonl').write_text('\n'.join(js(r) for r in orders)+'\n',encoding='utf-8')
    pd.DataFrame(people).to_csv(out/'worker_splits.csv.gz',index=False)
    count=0
    with gzip.open(out/'context_splits.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=None
        for row in contexts:
            if writer is None:writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
            writer.writerow(row);count+=1
    qa=dict(seed=SEED,replicates=200,schemes=dict(SCHEMES),canonical=len(index),raw_versions=len(lineage),
        nonindependent_revisions=int(index.nonindependent_revision_count.sum()),buildings=index.building_id.nunique(),
        images=index.image_id.nunique(),contexts=index.context_key.nunique(),workers=index.worker_id.nunique(),
        worker_split_rows=len(people),context_split_rows=count,
        selection='global numeric worker permutation filtered by building, floor(history_fraction*N), same permutations across fractions',
        old_eligibility_filter=False,candidate_responses_included=False,new_workers=False,actual_time_order=False,
        replicates_are_independent_experiments=False,metric_fitting=False,
        sources=[BASE+'/annotations.csv.gz',BASE+'/facts/annotation_version_lineage.csv.gz'])
    (out/'CENSUS_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(js(qa))


def verify(root,out):
    original=read(root/BASE/'annotations.csv.gz');index=read(out/'canonical_index.csv.gz');lineage=read(out/'annotation_version_lineage.csv.gz')
    assert set(index.canonical_annotation_id)==set(original.canonical_annotation_id)
    pd.testing.assert_frame_equal(index[original.columns].sort_values('canonical_annotation_id').reset_index(drop=True),
                                  original.sort_values('canonical_annotation_id').reset_index(drop=True))
    versions=lineage.groupby('canonical_annotation_id').size()
    assert index.canonical_annotation_id.is_unique and not index.duplicated(['context_key','worker_id']).any()
    assert index.raw_version_count.astype(int).tolist()==index.canonical_annotation_id.map(versions).tolist()
    assert int(index.nonindependent_revision_count.astype(int).sum())==len(lineage)-len(index)
    roster=sorted(index.worker_id.astype(int).unique().tolist());rng=np.random.default_rng(SEED)
    orders=[json.loads(x) for x in (out/'global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(orders)==200
    for i,r in enumerate(orders):assert r['replicate']==i and r['worker_ids']==list(map(str,rng.permutation(roster).tolist()))
    workers={b:set(g.worker_id) for b,g in index.groupby('building_id')}
    people=read(out/'worker_splits.csv.gz');assert people.split_id.is_unique and len(people)==200*2*len(workers)
    groupmap={}
    for r in people.to_dict('records'):
        h=json.loads(r['history_worker_ids_json']);v=json.loads(r['validation_worker_ids_json']);b=r['building_id']
        order=[w for w in orders[int(r['replicate'])]['worker_ids'] if w in workers[b]]
        fraction=dict(SCHEMES)[r['scheme']];n=math.floor(len(order)*fraction)
        assert h==order[:n] and v==order[n:] and not set(h)&set(v) and set(h+v)==workers[b]
        assert float(r['history_fraction'])==fraction and int(r['history_worker_count'])==len(h) and int(r['validation_worker_count'])==len(v)
        groupmap[r['split_id']]=(h,v,b)
    contextmap={c:(dict(zip(g.worker_id,g.canonical_annotation_id)),g.building_id.iloc[0]) for c,g in index.groupby('context_key')}
    metadata=index.drop_duplicates('context_key').set_index('context_key')
    seen=set();statuses={}
    with gzip.open(out/'context_splits.csv.gz','rt',encoding='utf-8') as stream:
        for r in csv.DictReader(stream):
            key=(r['split_id'],r['context_key']);assert key not in seen;seen.add(key)
            h,v,b=groupmap[r['split_id']];ids,expected_b=contextmap[r['context_key']];assert b==expected_b==r['building_id']
            assert all(r[c]==metadata.loc[r['context_key'],c] for c in IDENTITY if c!='context_key')
            hh=[w for w in h if w in ids];vv=[w for w in v if w in ids]
            assert json.loads(r['history_worker_ids_json'])==hh and json.loads(r['validation_worker_ids_json'])==vv
            assert json.loads(r['history_canonical_ids_json'])==[ids[w] for w in hh]
            assert json.loads(r['validation_canonical_ids_json'])==[ids[w] for w in vv]
            assert len(hh)+len(vv)==int(r['raw_worker_count'])==len(ids)
            assert len(hh)==int(r['history_raw_worker_count']) and len(vv)==int(r['validation_raw_worker_count'])
            expected_status=('history_empty' if not hh else 'validation_empty' if not vv else 'history_single_with_validation' if len(hh)==1 else 'history_pair_with_validation')
            assert r['raw_support_status']==expected_status and r['geometry_support_status']=='not_evaluated_in_census'
            statuses[r['raw_support_status']]=statuses.get(r['raw_support_status'],0)+1
    assert len(seen)==200*2*len(contextmap)
    result=dict(status='passed',canonical=len(index),versions=len(lineage),global_permutations=200,
        worker_splits=len(people),context_splits=len(seen),raw_support_status_counts=statuses,
        identity_only=True,new_metric_calculation=False)
    (out/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'FILE_LIST.json').write_text(json.dumps([dict(path=p.name,bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file() and p.name!='FILE_LIST.json'],ensure_ascii=False,indent=2),encoding='utf-8')
    print(js(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);parser.add_argument('--out',type=Path)
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    (verify if args.verify_only else main)(args.root.resolve(),args.out or args.root/OUTPUT)
