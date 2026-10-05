"""Three separate stages: construction (no truth), evaluation, real diagnostics.
Run in a new output directory. No original file is mutated.
"""
from pathlib import Path
import sys,json,argparse,itertools,csv,hashlib,collections,math
import numpy as np
from shapely.geometry import Polygon,Point
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'src'))
from finite_paths import *

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def table(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()})

def construct(out):
    out.mkdir(parents=True,exist_ok=False)
    D=load(ROOT/'inputs/domain.json');P=load(ROOT/'inputs/policies.json'); probes={p['id']:p for p in load(ROOT/'inputs/probes.json')};streams=load(ROOT/'inputs/evidence_streams.json')
    sizes=[len(s['paths']) for s in D['segments']];adds,ac=exhaustive_addition(sizes);subs,sc=exhaustive_elimination(sizes)
    assert set(adds)==set(subs)
    carrier=path_loss_tables(D);obs_tables=[];obs_dims=[]
    for j,s in enumerate(D['segments']):
        for p in s['paths']:
            if not p['donors']:continue
            obs_dims.append({'segment':j,'path_id':p['id'],'donors':p['donors']})
            obs_tables.append((j,[max(directed_path_distance(xyz(p,side),xyz(q,side)) for side in ('top','bottom')) for q in s['paths']]))
    C=[]
    for choices in adds:
        c=assemble(D,choices);c['carrier_loss_vector_h']=[carrier[j][q] for j,q in enumerate(choices)]
        c['observed_loss_vector_h']=[row[choices[j]] for j,row in obs_tables]
        c['observed_loss_dimensions']=obs_dims
        c['exact_complete_source_workers']=[s['worker'] for s in D['observed_person_assignments'] if assemble(D,s['choices'])['geometry_key']==c['geometry_key']] if c['geometry_valid'] else []
        c['probe_predictions']={k:evidence_prediction(c,p) for k,p in probes.items()}
        C.append(c)
    dump(out/'all_candidates.json',C)
    table(out/'candidate_ledger.csv',[{k:c[k] for k in ['id','choices','geometry_valid','geometry_issues','compatibility','violated_constraints','unknown_constraints','admissible','pair_count','area_h2','carrier_loss_vector_h','probe_predictions','exact_complete_source_workers']} for c in C])
    decisions=[];search_checks=[]
    by_id={c['id']:c for c in C};C_sub=[by_id['C'+''.join(map(str,q))] for q in subs]
    for policy in P:
        experiments=streams if policy['kind']=='evidence' else [{'id':'all_worlds__observations_only','claims':[]}]
        for stream in experiments:
            a=policy_select(C,D,policy,stream['claims'],probes)
            b=policy_select(C_sub,D,policy,stream['claims'],probes)
            assert set(a['candidate_ids'])==set(b['candidate_ids'])
            a['stream_id']=stream['id'];decisions.append(a)
            search_checks.append({'policy':policy['id'],'stream':stream['id'],'same_optimal_or_admissible_set':True,'size':len(a['candidate_ids'])})
    dump(out/'policy_outputs_before_truth.json',decisions)
    dump(out/'search_equivalence.json',{'addition':ac,'elimination':sc,'domain_size':len(C),'same_domain':True,'policy_checks':search_checks,'finite_budget_search':'not_run_no_directional_claim'})
    # Probe distinguishability without looking at truth. Different full geometries
    # with identical answers remain a joint ambiguity class.
    valid=[c for c in C if c['admissible']]; probe_ids=list(probes);best=[]
    for k in range(len(probe_ids)+1):
        for ids in itertools.combinations(probe_ids,k):
            groups={}
            for c in valid:groups.setdefault(tuple(c['probe_predictions'][p] for p in ids),set()).add(str(c['geometry_key']))
            if all(len(g)==1 for g in groups.values()):best.append(list(ids))
        if best:break
    dump(out/'probe_identification.json',{'candidate_geometry_count':len(dedup_candidates(valid)),'minimum_exact_probe_count':len(best[0]) if best else None,'minimal_probe_sets':best,'not_a_visual_accuracy_guarantee':True})
    # Build union of two complete scope-exclusive candidates, but never select it.
    c1=assemble(D,[0,0,0,1,0,0]);c2=assemble(D,[0,0,0,0,1,0]);cx=assemble(D,[0,0,0,1,1,0])
    u=Polygon(np.array(c1['nodes_xz_top'])[:,:2]).union(Polygon(np.array(c2['nodes_xz_top'])[:,:2]))
    dump(out/'exclusive_union.json',{'left_candidate':c1['id'],'right_candidate':c2['id'],'union_area_h2':u.area,'union_geometry_valid':u.is_valid,'both_paths_candidate':cx['id'],'joint_compatibility':cx['compatibility'],'violated_constraints':cx['violated_constraints'],'never_called_maximum_room':True})
    snapshot={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'inputs').glob('*.json')}
    summary={'raw_candidates':len(C),'valid_geometry':sum(c['geometry_valid'] for c in C),'admissible':len(valid),'admissible_geometries':len(dedup_candidates(valid)), 'geometric_failures':sum(not c['geometry_valid'] for c in C),'known_incompatible':sum(bool(c['violated_constraints']) for c in C),'unknown_among_admissible':sum(c['compatibility']=='unresolved' for c in valid),'policy_outputs':len(decisions),'truth_opened':False,'inputs_sha256':snapshot}
    dump(out/'construction_summary.json',summary);print(summary)

def evaluate(out):
    C=load(out/'all_candidates.json');decisions=load(out/'policy_outputs_before_truth.json');byid={c['id']:c for c in C};D=load(ROOT/'inputs/domain.json');truths=load(ROOT/'evaluation/synthetic_truth.json');streams={s['id']:s for s in load(ROOT/'inputs/evidence_streams.json')}
    feats=truths['feature_events'];rows=[];candidate_rows=[];events=[]
    for w in truths['worlds']:
        g=assemble(D,w['choices']);G=Polygon(np.asarray(g['nodes_xz_top'])[:,:2]);true_flags={k:w['choices'][j]==q for k,(j,q) in feats.items()};nt=sum(true_flags.values()); detail_keys=[k for k in feats if not k.startswith('range_')];nd=sum(true_flags[k] for k in detail_keys)
        for c in C:
            if not c['geometry_valid']:
                candidate_rows.append({'world':w['id'],'candidate':c['id'],'status':'invalid_geometry','false_deleted':None,'lost_area_h2':None});continue
            F=Polygon(np.asarray(c['nodes_xz_top'])[:,:2]);cf={k:c['choices'][j]==q for k,(j,q) in feats.items()}
            fn=sum(v and not cf[k] for k,v in true_flags.items());fp=sum(not v and cf[k] for k,v in true_flags.items())
            newbad= int(c['choices'][5]==0 and w['choices'][5]==1)
            detail_fn=sum(true_flags[k] and not cf[k] for k in detail_keys)
            detail_fp=sum(not true_flags[k] and cf[k] for k in detail_keys)
            candidate_rows.append({'world':w['id'],'candidate':c['id'],'status':c['compatibility'],'false_deleted':fn,'false_deleted_rate':fn/nt if nt else None,
                'detail_false_deleted':detail_fn,'detail_false_deleted_rate':detail_fn/nd if nd else None,'wrong_observed_detail_retained':detail_fp,'wrong_observed_structure_retained':fp,'wrong_new_connection':newbad,'lost_area_h2':G.difference(F).area,'added_area_h2':F.difference(G).area,
                'iou':F.intersection(G).area/F.union(G).area,'true_geometry':c['geometry_key']==json.loads(json.dumps(g['geometry_key'])),
                'new_no_donor_edge_count':sum(not e['donors'] for e in c['edges']), 'candidate_feature_flags':cf})
        evals={r['candidate']:r for r in candidate_rows if r['world']==w['id']}
        for dec in decisions:
            sid=dec['stream_id']
            if not sid.startswith('all_worlds') and streams[sid]['evaluation_world']!=w['id']:continue
            rr=[evals[c] for c in dec['candidate_ids']];chosen=[byid[c] for c in dec['candidate_ids']]
            row={'world':w['id'],'policy':dec['policy']['id'],'stream':sid.split('__',1)[1],'status':dec['status'],'geometry_count':dec['geometry_count'],
                 'true_geometry_in_returned_set':any(r['true_geometry'] for r in rr),'full_decision_pending':dec['status']!='single_geometry_conditional',
                 'empty_not_a_zero_error':not bool(rr),'true_feature_denominator':nt,'true_detail_denominator':nd}
            for k in ['false_deleted','detail_false_deleted','wrong_observed_detail_retained','wrong_observed_structure_retained','wrong_new_connection','lost_area_h2','added_area_h2','iou','new_no_donor_edge_count']:
                row[k+'_min']=min([r[k] for r in rr],default=None);row[k+'_max']=max([r[k] for r in rr],default=None)
            unresolved=0
            for k,(j,q) in feats.items():
                values={c['choices'][j]==q for c in chosen}
                status='no_feasible' if not values else ('undetermined' if len(values)>1 else ('retain' if True in values else 'replace_or_omit'))
                unresolved+=status in ('undetermined','no_feasible')
                events.append({'world':w['id'],'policy':row['policy'],'stream':row['stream'],'event':k,'decision':status,'true_present':true_flags[k],'event_kind':'scope' if k.startswith('range_') else 'detail',
                    'wrong_decisive_deletion':bool(true_flags[k] and values=={False}), 'wrong_decisive_retention':bool(not true_flags[k] and values=={True})})
            row['event_pending_count']=unresolved;row['event_pending_rate']=unresolved/len(feats)
            rows.append(row)
    table(out/'candidate_truth_evaluation.csv',candidate_rows);table(out/'policy_evaluation.csv',rows);table(out/'event_decisions.csv',events)
    summary=[]
    for policy,stream in sorted(set((r['policy'],r['stream']) for r in rows)):
        rr=[r for r in rows if (r['policy'],r['stream'])==(policy,stream)];ee=[e for e in events if (e['policy'],e['stream'])==(policy,stream)]
        summary.append({'policy':policy,'stream':stream,'worlds':len(rr),'single_geometries':sum(r['status']=='single_geometry_conditional' for r in rr),'multiple':sum(r['status']=='multiple_candidates' for r in rr),'empty':sum(r['status']=='no_feasible_candidate' for r in rr),'true_geometry_covered':sum(r['true_geometry_in_returned_set'] for r in rr),'true_detail_event_denominator':sum(e['true_present'] and e['event_kind']=='detail' for e in ee),'wrong_decisive_detail_deletions':sum(e['wrong_decisive_deletion'] and e['event_kind']=='detail' for e in ee),'wrong_decisive_deletions':sum(e['wrong_decisive_deletion'] for e in ee),'wrong_decisive_retentions':sum(e['wrong_decisive_retention'] for e in ee),'event_pending_rate':sum(r['event_pending_count'] for r in rr)/(7*len(rr))})
    table(out/'evaluation_summary.csv',summary)
    dump(out/'evaluation_notes.json',{'rates_are_fixed_synthetic_mechanisms_not_population':True,'candidate_set_error_ranges_not_GT_selected_output':True,'constructed_worlds':len(truths['worlds']),'policy_world_rows':len(rows),'candidate_world_rows':len(candidate_rows),'truth_only_opened_in_evaluation_stage':True})
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--stage',choices=['construct','evaluate','all'],default='all');args=a.parse_args()
    if args.stage in ('construct','all'):construct(args.out)
    if args.stage in ('evaluate','all'):evaluate(args.out)
