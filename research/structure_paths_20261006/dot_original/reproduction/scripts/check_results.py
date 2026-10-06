"""Independent inventory and structural audit; does not alter source/result files."""
import csv,gzip,hashlib,json,math,sys
from collections import Counter
from pathlib import Path
source,out,dest=map(Path,sys.argv[1:4])
def read(p):
    p=Path(p)
    if p.name.endswith('.jsonl.gz'):
        with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
    return json.loads(p.read_text())
def save(name,data):
    (dest/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}
a,b=inventory(source/'results'),inventory(out)
common=sorted(set(a)&set(b));different=[k for k in common if a[k]!=b[k]]
comparison={'published_file_count':len(a),'rerun_file_count':len(b),'byte_equal_count':sum(a[k]==b[k] for k in common),
            'missing_in_rerun':sorted(set(a)-set(b)),'extra_in_rerun':sorted(set(b)-set(a)),
            'byte_differences':different,'published_hashes':a,'rerun_hashes':b}
save('artifact_comparison.json',comparison)
numeric={'total_numeric_differences':0,'max_absolute_difference':0.,'max_relative_difference':0.,'non_numeric_differences':0,'examples':[]}
def differences(a,b,path=''):
    if type(a)!=type(b):
        numeric['non_numeric_differences']+=1
        if len(numeric['examples'])<40:numeric['examples'].append({'path':path,'published':a,'rerun':b})
    elif isinstance(a,dict):
        if a.keys()!=b.keys():numeric['non_numeric_differences']+=1
        for k in a.keys()&b.keys():differences(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        if len(a)!=len(b):numeric['non_numeric_differences']+=1
        for i,(x,y) in enumerate(zip(a,b)):differences(x,y,path+'/'+str(i))
    elif a!=b:
        if isinstance(a,(int,float)) and not isinstance(a,bool):
            ab=abs(a-b);rel=ab/max(abs(a),abs(b),1e-300)
            numeric['total_numeric_differences']+=1
            numeric['max_absolute_difference']=max(numeric['max_absolute_difference'],ab)
            numeric['max_relative_difference']=max(numeric['max_relative_difference'],rel)
        else:numeric['non_numeric_differences']+=1
        if len(numeric['examples'])<40:numeric['examples'].append({'path':path,'published':a,'rerun':b})
for name in different:
    if name.endswith(('.json','.jsonl.gz')):differences(read(source/'results'/name),read(out/name),name)
save('semantic_differences.json',numeric)
inputs=[read(p) for p in sorted((source/'inputs').glob('*.json')) if p.name!='human_review.json']
counts={'input_rosters':{im['image']:len(im['records']) for im in inputs},
        'record_count':sum(len(im['records']) for im in inputs),
        'distinct_workers':len({r['worker'] for im in inputs for r in im['records']}),
        'original_corner_pairs':sum(len(r['points'])//2 for im in inputs for r in im['records'])}
states=read(out/'summary/all_MV_comparisons.json')
keys=[(r['image'],r['metric'],r['threshold_deg']) for r in states]
expected={(im['image'],m,t) for im in inputs for m in ['pair','top','bottom'] for t in [5,9,12]}
counts.update(settings=len(states),distinct_settings=len(set(keys)),settings_complete=set(keys)==expected,
              previous_baseline_checks=read(out/'summary/previous_baseline_reproduction.json')['checks'])
matches=[];patches=[];patch_setting_counts=[]
for f in sorted((out/'patches').glob('*_local_matches.json')):
    ms=read(f);cs=read(f.with_name(f.name.replace('_local_matches.json','_candidate_rings.jsonl.gz')))
    compatible=[r for r in ms if r['same_raw_endpoint_groups']]
    assert len(cs)==2*len(compatible)
    assert len({r['id'] for r in ms})==len(ms)
    assert len({r['id'] for r in cs})==len(cs)
    matchmap={r['id']:r for r in ms}
    assert all(c['local_match'] in matchmap and matchmap[c['local_match']]['same_raw_endpoint_groups'] for c in cs)
    assert all(sorted(r['path_sizes'])==[2,3] and r['continuous_path_evidence']['status']=='accept' for r in ms)
    patch_setting_counts.append({'file':f.name,'local_matches':len(ms),'compatible':len(compatible),'candidate_records':len(cs)})
    matches+=ms;patches+=cs
counts.update(local_matches=len(matches),compatible_matches=sum(r['same_raw_endpoint_groups'] for r in matches),
              competing_anchor_hypotheses=sum(not r['same_raw_endpoint_groups'] for r in matches),
              candidate_records=len(patches),candidate_statuses=dict(Counter(c['status'] for c in patches)),
              exact_original_edge_absence_count=sum(e['new_edge_not_exact_original'] for c in patches for e in c.get('new_edges',[])),
              post_center_statuses=dict(Counter(c['post_center_compatibility_status'] for c in patches)),patch_settings=patch_setting_counts)
mv=read(out/'evaluation/MV_reference_scores.json');ev=read(out/'evaluation/all_path_patch_reference_scores.json')
counts.update(mv_evaluation_rows=len(mv),mv_evaluation_statuses=dict(Counter(r['status'] for r in mv)),
              patch_evaluation_rows=len(ev),patch_evaluation_statuses=dict(Counter(r['status'] for r in ev)))
counts['reference_versions']=[{'image':im['image'],'versions':[r['version'] for r in im['references']]} for im in read(source/'evaluation/references.json')['images']]
counts['known_rpc_5deg_pair']=[r for r in read(out/'summary/known_development_pair_counts.json') if r['image'].startswith('rPc') and r['metric']=='pair' and r['threshold_deg']==5]
counts['pair_mv_selected_counts']=[{k:r[k] for k in ['image','threshold_deg','raw_selected','path_selected','three_state_selected']} for r in states if r['metric']=='pair']
counts['fixed_hop_subdivision_status']=read(out/'controls/fixed_hop_subdivision_counterexample.json')['result']['status']
counts['dense_kernel_checks']={'total':len(read(out/'controls/independent_kernel_check.json')),
                              'passed':sum(r['within_conservative_bound'] for r in read(out/'controls/independent_kernel_check.json'))}
counts['seam_reversal_checks']={'total':len(read(out/'controls/curve_seam_and_reversal_checks.json')),
                              'passed':sum(r['overlapping_bounds'] for r in read(out/'controls/curve_seam_and_reversal_checks.json'))}
counts['witnesses']=read(out/'summary/post_center_5deg_witnesses.json')
counts['unique_candidate_encodings']=read(out/'summary/unique_candidate_encodings.json')
counts['area_decomposition']=read(out/'summary/patch_area_decomposition.json')
counts['unb_5deg_raw_lower_target_ledger']=[r for r in read(out/'summary/unb_lower_identity_upper_targets.json') if r['threshold_deg']==5 and r['policy']=='raw_MV']
save('independent_counts.json',counts)
assert counts['record_count']==66 and counts['distinct_workers']==24 and counts['original_corner_pairs']==400
assert counts['settings_complete'] and counts['distinct_settings']==36
assert len(counts['previous_baseline_checks'])==12 and all(c['same_partition'] and c['same_centers'] for c in counts['previous_baseline_checks'])
assert (len(matches),counts['compatible_matches'],len(patches),len(mv),len(ev))==(606,262,524,135,524)
assert counts['fixed_hop_subdivision_status']=='not_witnessed'
print(json.dumps({k:counts[k] for k in ['input_rosters','record_count','distinct_workers','original_corner_pairs','settings','local_matches','compatible_matches','candidate_records','mv_evaluation_rows','patch_evaluation_rows','post_center_statuses']},ensure_ascii=False,indent=2))
print('Artifact comparison:',len(a),'published;',len(b),'rerun;',len(different),'byte differences')
print('Numerical/structural differences:',json.dumps(numeric,ensure_ascii=False))
assert set(a)==set(b), 'Artifact file sets differ'
expected_metadata={'analysis/automatic_candidates_frozen_before_human_read.json','evaluation/pre_reference_candidate_digest.json'}
assert set(different)<=expected_metadata, 'Scientific output bytes differ; inspect artifact_comparison.json'
assert numeric['total_numeric_differences']==0, 'Scientific numeric values differ'
assert read(source/'results/analysis/automatic_candidates_frozen_before_human_read.json')==read(out/'analysis/automatic_candidates_frozen_before_human_read.json')
old=read(source/'results/evaluation/pre_reference_candidate_digest.json');new=read(out/'evaluation/pre_reference_candidate_digest.json')
assert old.keys()==new.keys()
assert {k for k in old if old[k]!=new[k]}<={'analysis/automatic_candidates_frozen_before_human_read.json'}
