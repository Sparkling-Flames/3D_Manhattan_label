"""Compare all source audit rows to the independent delivery's metric probes.

No original clustering code is imported. Spherical angles are independently
computed with 3D unit vectors and atan2(cross-norm, dot). This checks saved group
relations against the delivery, not an independent replay of full clustering.
"""
from __future__ import annotations
import argparse, collections, hashlib, itertools, json, math
from pathlib import Path

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def vector(point):
    lon=(point[0]/1024-.5)*2*math.pi
    lat=(.5-point[1]/512)*math.pi
    return (math.cos(lat)*math.sin(lon), math.sin(lat), -math.cos(lat)*math.cos(lon))

def angle(a,b):
    a,b=vector(a),vector(b)
    dot=sum(x*y for x,y in zip(a,b))
    c=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    return math.degrees(math.atan2(math.sqrt(sum(x*x for x in c)),dot))

def normalize_conflicts(d):
    return {w:sorted(tuple(x) for x in members) for w,members in d.items()}

def main():
    ap=argparse.ArgumentParser()
    here=Path(__file__).resolve().parent
    ap.add_argument('--source-audit',type=Path,default=here/'sources/analysis_results/point_route_review_20261006/correspondence_audit.json')
    ap.add_argument('--human-review',type=Path,default=here/'sources/research/point_route_review_20261006/human_review.json')
    ap.add_argument('--delivery',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'full_source_crosscheck.json')
    a=ap.parse_args()
    path=a.source_audit
    audit=read(path); probes=read(a.delivery/'results/domains/development_probes.json')
    human=read(a.human_review)
    human={r['case_id']:r for r in human['reviews']}
    bykey={(r['image'],float(r['threshold']),r['metric']):r for r in probes}
    all_records={}
    for image in {r['image'] for r in audit['rows']}:
        records=read(a.delivery/'inputs'/f'{image}.json')['records']
        all_records[image]={r['id']:r for r in records}
    checks=collections.Counter();failures=[];maxerr=0.;rows=[];witness_order_differences=0
    def check(label,truth,ctx,actual=None,expected=None):
        checks[label]+=1
        if not truth:failures.append(dict(check=label,context=ctx,actual=actual,expected=expected))
    def scalar(label,x,y,ctx):
        nonlocal maxerr
        err=abs(float(x)-float(y));maxerr=max(maxerr,err)
        check(label,err<=1e-9,ctx,x,y)
    def points(image,member):
        r=all_records[image][member[0]];return r['points'][2*member[1]:2*member[1]+2]
    def diameters(image,members):
        out={}
        for name,j in [('top',0),('bottom',1)]:
            out[name]=max(angle(points(image,x)[j],points(image,y)[j]) for x,y in itertools.combinations(members,2))
        out['pair']=max(out.values());return out
    def verify_geometry(row,probe,members,label):
        ctx=[row['case_id'],row['threshold_deg'],row['route'],row['side'],label]
        got=diameters(row['image'],members)
        for side in ('top','bottom','pair'):scalar('independent_local_diameter',got[side],probe['diameters_deg'][side],ctx+[side])
        check('independent_local_feasibility',probe['local_group_feasible']==(got[row['metric']]<=row['threshold_deg']+1e-9),ctx)
        witness=probe['whole_group_diameter_witness']; wd=diameters(row['image'],witness)[row['metric']]
        scalar('independent_whole_group_witness_distance',wd,probe['whole_group_merge_diameter_deg'],ctx)
        check('whole_group_threshold_status',probe['whole_group_merge_exceeds_threshold']==(probe['whole_group_merge_diameter_deg']>row['threshold_deg']+1e-9),ctx)
        for conflict in probe['same_worker_merge_conflicts']:
            check('conflict_worker_binding',all(all_records[row['image']][v[0]]['worker']==conflict['worker'] for v in conflict['members']),ctx)
    for source in audit['rows']:
        ctx=[source['case_id'],source['threshold_deg'],source['route'],source['side']]
        key=(source['image'],float(source['threshold_deg']),source['metric']); d=bykey[key];p=source['probe']; h=human[source['case_id']]
        check('requested_members',source['requested_members']==d['members'],ctx)
        check('human_relation',source['relation']==h['relation'],ctx)
        check('human_bottom_relation',source['bottom_relation']==h.get('bottom_relation'),ctx)
        check('group_ids',p['member_group_ids']==d['member_groups'],ctx)
        check('same_group',p['same_group']==d['same_group'],ctx)
        check('local_feasibility',p['local_group_feasible']==d['local_feasible'],ctx)
        target={g['feature_id']:g for g in p['target_groups']}
        check('target_group_coverage',set(target)==set(d['member_groups']),ctx)
        check('support_counts',[target[g]['support'] for g in d['member_groups']]==d['supports'],ctx)
        n=len(all_records[source['image']]); gate=math.ceil(n/2)
        check('unchanged_full_pool_selection',all(v['selected']==(v['support']>=gate) for v in target.values()),ctx)
        c=normalize_conflicts({x['worker']:x['members'] for x in p['same_worker_merge_conflicts']})
        check('same_worker_conflicts',c==normalize_conflicts(d['same_worker_conflicts']),ctx)
        for side in ('top','bottom','pair'):scalar('delivery_local_diameter',p['diameters_deg'][side],d['local_diameters_deg'][side],ctx+[side])
        scalar('delivery_whole_group_diameter',p['whole_group_merge_diameter_deg'],d['whole_union_diameter'],ctx)
        if p['whole_group_diameter_witness']!=d['whole_union_witness']:witness_order_differences+=1
        check('unordered_whole_group_witness',sorted(p['whole_group_diameter_witness'])==sorted(d['whole_union_witness']),ctx)
        verify_geometry(source,p,source['requested_members'],'requested')
        if source['rejected_combination_probe'] is not None:
            rejected=source['rejected_combination_probe']; members=[v[:] for v in source['requested_members']];members[-1][1]=h['rejected_previous_purple_processed_pair_index']
            check('rejected_triple_same_group',rejected['same_group']==d['wrong_triple_same_group'],ctx)
            verify_geometry(source,rejected,members,'rejected_rpc_old_purple')
        expected_mixed=[]
        for i,j in h.get('different_upper_target_indices',[]):
            if p['member_group_ids'][i]==p['member_group_ids'][j]:expected_mixed.append(dict(members=[source['requested_members'][i],source['requested_members'][j]],feature_id=p['member_group_ids'][i]))
        check('known_upper_target_mixing',source['different_upper_targets_in_same_group']==expected_mixed,ctx)
        rows.append(dict(case_id=source['case_id'],route=source['route'],threshold_deg=source['threshold_deg'],side=source['side'],metric=source['metric'],development_probe_key=list(key),status='pass' if not any(f['context'][:4]==ctx for f in failures) else 'fail'))
    out=dict(source_commit='4716aef3c8453779633a0a4aadf44105afb3b733',source_audit_git_blob_sha=hashlib.sha1(b'blob '+str(len(path.read_bytes())).encode()+b'\0'+path.read_bytes()).hexdigest(),source_rows=len(audit['rows']),delivery_unique_metric_probes=len(probes),mapped_unique_metric_keys=len({tuple(r['development_probe_key']) for r in rows}),checked_source_requested_and_rejected_probes=100,checks=dict(checks),total_scalar_and_relation_checks=sum(checks.values()),failures=failures,max_absolute_scalar_difference_deg=maxerr,witness_order_only_differences=witness_order_differences,rows=rows,scope='All 75 source requested-triple rows mapped to all 45 delivery metric probes. Also independent raw-coordinate local and witness angles for 75 requested and 25 rejected-triple probes. Group membership/support are cross-artifact checks, not an independent full clustering replay; full target-group member lists not fetched. No visual labels inferred; no inputs or upstream outputs changed.')
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ['rows','scope']},ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
