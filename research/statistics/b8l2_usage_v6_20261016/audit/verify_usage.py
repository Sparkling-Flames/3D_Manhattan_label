"""独立核对已落盘新用途结果；不写主数据，不调用主用途门/汇总器。"""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
P=ROOT/'research/statistics/b8l2_usage_v6_20261016'
S=ROOT/'research/statistics/b8l2_shared_v6_20261016'
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
csv=lambda name:pd.read_csv(P/(name+'.csv'))
F=read(S/'FROZEN_INPUTS.json')
A=csv('shared_records');OLD=pd.read_csv(S/'shared_records.csv')
O={r['object_id']:r for r in F['bundle']['data']['objects'] if r['object_kind']=='annotation'}
B={r['object_id']:r for r in read(S/'inputs/binding_all.json')['affected_records']}
R={r['target_id']:r for r in read(S/'inputs/reference_catalog.json')}
checks={};details_checks=0
def ok(name,condition):
    assert condition,name
    checks[name]=True
def eq(a,b):
    return (pd.isna(a) and pd.isna(b)) or (not pd.isna(a) and not pd.isna(b) and np.isclose(float(a),float(b),atol=1e-8,rtol=1e-10))
def arr(x):
    return json.loads(x) if isinstance(x,str) and x.startswith('[') else []
for c in ['quality_exclusion_reasons','purpose_bypass','pool_analysis_exclusion_reasons']:
    A[c]=A[c].map(arr)
ok('3152_unique_frozen_identity',len(A)==3152 and not A.object_id.duplicated().any() and set(A.object_id)==set(O)==set(B))
for c in ['image_id','worker_id','condition']:
    ok('identity_'+c,all(row[c]==O[row.object_id][c] for _,row in A.iterrows()))
X=A.set_index('object_id');Y=OLD.set_index('object_id').loc[X.index]
for c in ['pool_analysis_eligible','pool_source_workers','ordinary_difficulty_eligible','active_time_seconds','source_active_time_seconds','target_matched_time_seconds']:
    ok('preserved_'+c,((X[c]==Y[c])|(X[c].isna()&Y[c].isna())).all())
hold_fields=['same_target_quality_hold','latest_step_reference_pending','original_holdout','same_target_unconfirmed']
expected=[];states=[];doorflags=[];oosflags=[];specialhold=[];unconfirmed=[]
for row in A.to_dict('records'):
    obj=O[row['object_id']];ref=R.get(B[row['object_id']]['chosen_target_id']);g=obj['main_quality_gate']
    door='doorway' in row['scene'] or row['doorway_status'] in ['annotatable','difficult','suspected_user_review']
    oos='oos' in row['scene'] or row['oos_subtype'] in ['nonorthogonal_annotatable','subtype_not_resolved','suspected_user_review']
    doorflags.append(door);oosflags.append(oos)
    sceneonly=door and ((g['status']=='out_of_primary_scene' and g['reasons']==['doorway_difficult']) or (g['status']=='hold_scene_or_reference' and g['reasons']==['doorway_annotatable']))
    full=bool(ref and ref['full_reference_available'])
    blanket=sceneonly and bool(ref) and full and row['stage']=='doorway' and row['same_target_quality_hold'] not in [True,'True']
    holds=[k for k in hold_fields if row[k] in [True,'True'] and not(k=='same_target_unconfirmed' and blanket)]
    unc=door and g['status']=='hold_scene_or_reference' and g['reasons']==['unconfirmed']
    unique=bool(B[row['object_id']]['chosen_target_id']) and not holds and not unc
    assert row['target_binding_unique']==unique
    assert row['reference_full_available']==full
    state='pending_target' if not unique else 'input_uncomputable' if not row['full_input_available'] else 'pending_reference' if not full else 'computed'
    states.append(state)
    eligible=(obj['cleaning_disposition']=='retained' and obj['independent_vote_eligible'] and row['pool_analysis_eligible'] and
        (g['status']=='candidate_pending_geometry' or sceneonly) and obj['worker_quality_gate'] in ['candidate_pending_geometry',g['status']] and
        unique and full and row['full_input_available'] and ref['current_target'] and row['difficulty_analysis_exclusion']!='user_reported_issue_pending' and not oos and state=='computed')
    expected.append(eligible)
    if door and row['same_target_quality_hold'] in [True,'True']:specialhold.append(row['object_id'])
    if unc:unconfirmed.append(row['object_id'])
ok('scene_flags_independent',np.array_equal(A.is_doorway,doorflags) and np.array_equal(A.is_oos,oosflags))
ok('all_3152_quality_gate_independent',np.array_equal(A.quality_usable,expected) and np.array_equal(A.current_quality_eligible,expected))
ok('all_3152_fullscore_state_independent',np.array_equal(A.full_score_state,states))
ok('specific_scope_holds_10',len(specialhold)==10 and not X.loc[specialhold].quality_usable.any())
ok('door_unconfirmed_6',len(unconfirmed)==6 and X.loc[unconfirmed].full_score_state.eq('pending_target').all())
ok('doorway_blanket_115',sum('old_doorway_same_target_not_certified_blanket' in x for x in A.purpose_bypass)==115)
metrics=['WQ','A10','B8L2','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
ok('all_normal_metrics_masked_unqualified',A.loc[~A.quality_usable,metrics].isna().all().all())
ok('OOS_412_all_normal_metrics_masked',A.is_oos.sum()==412 and A.loc[A.is_oos,metrics].isna().all().all())
ok('188_door_actual_complete',len(A[A.quality_usable & A.is_doorway])==188 and A.loc[A.quality_usable&A.is_doorway,'calculation_status'].eq('full_computed').all())
oldset=set(OLD.loc[OLD.current_quality_eligible,'object_id']);newset=set(A.loc[A.quality_usable,'object_id'])
retained=sorted(oldset&newset);added=sorted(newset-oldset);removed=sorted(oldset-newset)
delta=float((X.loc[retained,metrics]-Y.loc[retained,metrics]).abs().max().max())
ok('old_retained1599_scores_unchanged',len(retained)==1599 and delta<1e-9)
ok('added188_doorway_removed23_OOS',len(added)==188 and X.loc[added].is_doorway.all() and len(removed)==23 and X.loc[removed].is_oos.all())
ok('quality_1787',len(newset)==1787 and A.loc[A.quality_usable,metrics].notna().all().all())
ok('time1750_440_1107',A.active_time_seconds.count()==1750 and A.target_matched_time_seconds.count()==440 and A.loc[A.quality_usable,'active_time_seconds'].count()==1107)
ok('source_time_not_quality_gated',A.loc[~A.quality_usable,'active_time_seconds'].notna().any())
ok('unmarkable_choice_unknown',A.worker_unmarkable_choice.eq('unknown_not_independently_recorded').all())
ok('all_sources_27workers',A.worker_id.nunique()==27 and set(A.worker_id)==set(csv('worker_usage_summary').worker_id))
PORDER=['old_cleaning_excluded','cleaning_pending','independent_response_ineligible','source_pool_below3','gt_error','target_unresolved','reference_unavailable','full_input_unavailable','oos_diagnostic_only','other_quality_restriction','measurement_failed','not_run','floor_only_no_full_score','calculated_not_usable','quality_usable']
ok('primary_first_true',all(row.primary_reason==next(k for k in PORDER if row['hit_'+k]) for _,row in A.iterrows()))
primary=csv('worker_primary_reasons');hits=csv('worker_reason_hits');summary=csv('worker_usage_summary')
for row in primary.to_dict('records'):
    cell=A[A.worker_id.eq(row['worker_id'])];n=int(cell.primary_reason.eq(row['primary_reason']).sum())
    assert n==row['n_records'] and len(cell)==row['n_submissions'] and eq(n/len(cell),row['ratio'])
for row in hits.to_dict('records'):
    cell=A[A.worker_id.eq(row['worker_id'])]
    n=cell['hit_'+row['reason']].sum() if row['reason_kind']=='semantic_hit' else sum(row['reason'] in r for r in cell.quality_exclusion_reasons)
    assert n==row['n_records'] and len(cell)==row['n_submissions'] and eq(n/len(cell),row['ratio'])
for row in summary.to_dict('records'):
    cell=A[A.worker_id.eq(row['worker_id'])];assert row['n_submissions']==len(cell)
    for k in PORDER:
        if 'n_'+k in row:assert row['n_'+k]==cell['hit_'+k].sum()
    for c,v in row.items():
        if c.startswith('ratio_'):assert eq(v,row['n_'+c[6:]]/len(cell))
ok('primary405_reasonhits733_worker27_denominators',len(primary)==405 and len(hits)==733 and primary.n_records.sum()==3152)
for name,dims in [('worker_scene_usage',['worker_id','condition','scene_bucket']),('scene_usage',['condition','scene_bucket'])]:
    for row in csv(name).to_dict('records'):
        cell=A
        for d in dims:cell=cell[cell[d].eq(row[d])]
        assert row['n_submissions']==len(cell) and row['n_quality_usable']==cell.quality_usable.sum()
        assert row['n_full_computed']==cell.calculation_status.eq('full_computed').sum()
    ok(name+'_independent_slices',csv(name).n_submissions.sum()==3152)

def distribution_assert(row,cell):
    global details_checks
    assert row['n_inventory_records']==len(cell)
    assert row['n_source_records']==cell.pool_analysis_eligible.sum()
    for metric in ['B8L2','active_time_seconds','target_matched_time_seconds']:
        v=cell[metric].dropna();assert row[metric+'_n']==len(v)
        for stat,value in [('mean',v.mean()),('median',v.median()),('sd',v.std(ddof=1))]:
            assert eq(row[metric+'_'+stat],value),(metric,stat,row[metric+'_'+stat],value)
    for label,metric in [('source','active_time_seconds'),('target','target_matched_time_seconds')]:
        joint=cell[cell.B8L2.notna()&cell[metric].notna()];pre='quality_'+label+'_time_'
        assert row[pre+'n']==len(joint)
        for name,column in [('B8L2','B8L2'),('seconds',metric)]:
            v=joint[column].dropna()
            for stat,value in [('mean',v.mean()),('median',v.median()),('sd',v.std(ddof=1))]:assert eq(row[pre+name+'_'+stat],value)
    details_checks+=1
A['comparison_stratum']=np.where(A.ordinary_difficulty_eligible,'ordinary_'+A.difficulty_class,np.where(A.pool_analysis_eligible,'special_or_pending','inventory_excluded'))
for name,dims in [('worker_condition_stats',['worker_id','condition','analysis_layer']),('time_quality_focus',['worker_id','condition','comparison_stratum'])]:
    for row in csv('details/'+name).to_dict('records'):
        cell=A
        for d in dims:cell=cell[cell[d].eq(row[d])]
        distribution_assert(row,cell)
    ok('new_details_'+name,True)
lookup=csv('details/record_lookup').set_index('object_id')
ok('details_lookup3152_no_drift',len(lookup)==3152 and set(lookup.index)==set(X.index) and np.allclose(lookup.loc[X.index,'B8L2'],X.B8L2,equal_nan=True))
for name in ['overview','by_difficulty']:
    for row in csv(name).to_dict('records'):
        layer,condition=row['panel'].split('_',1)
        cell=A[A.pool_analysis_eligible & A.condition.eq(condition) & A.ordinary_difficulty_eligible.eq(layer=='ordinary')]
        if name=='by_difficulty':cell=cell[cell.difficulty_class.eq(row['difficulty_class'])]
        v=cell[row['metric']].dropna()
        assert row['n_records']==len(cell) and row['n_valid']==len(v)
        for stat,value in [('mean',v.mean()),('median',v.median()),('sd',v.std(ddof=1))]:assert eq(row[stat],value)
    ok('main_'+name+'_all_cells',True)
for row in csv('peer_comparisons').to_dict('records'):
    base=X.loc[row['object_id']]
    peers=A[A.quality_usable&A.condition.eq(base.condition)&A.image_id.eq(base.image_id)&A.reference_id.eq(base.reference_id)&A.worker_id.ne(base.worker_id)][row['metric']].dropna()
    assert row['n_peers']==len(peers) and eq(row['peer_mean'],peers.mean())
ok('all_peer_n_mean',True)
members=csv('details/room_group_memberships')
groupids={g:set(c.image_id) for g,c in members.groupby('group_id')}
for name in ['room_group_summary','room_worker_groups','room_group_views']:
    for row in csv('details/'+name).to_dict('records'):
        cell=A[A.image_id.isin(groupids[row['group_id']])&A.condition.eq(row['condition'])&A.analysis_layer.eq(row['analysis_layer'])]
        if 'worker_id' in row:cell=cell[cell.worker_id.eq(row['worker_id'])]
        if 'image_id' in row:cell=cell[cell.image_id.eq(row['image_id'])]
        distribution_assert(row,cell)
        for metric in ['B8L2','active_time_seconds','target_matched_time_seconds']:
            assert eq(row[metric+'_image_equal_mean'],cell.groupby('image_id')[metric].mean().dropna().mean())
    ok('new_details_'+name+'_all_cells',True)
ordinarymanual=A[A.pool_analysis_eligible&A.ordinary_difficulty_eligible&A.condition.eq('manual')].copy()
ordinarymanual['iou_3d']=ordinarymanual.IoU3D100/100
byimage={i:f.set_index('worker_id') for i,f in ordinarymanual.groupby('image_id')}
empty=ordinarymanual.set_index('worker_id').iloc[:0]
lowcommon=0
for row in csv('same_room_pairs').to_dict('records'):
    a=byimage.get(row['image_a'],empty);b=byimage.get(row['image_b'],empty);common=a.index.intersection(b.index)
    av=a[row['metric']].dropna();bv=b[row['metric']].dropna()
    pair=pd.concat([a.loc[common,row['metric']],b.loc[common,row['metric']]],axis=1).dropna();pair.columns=['a','b']
    assert row['n_records_a']==len(a) and row['n_records_b']==len(b) and row['n_common_workers']==len(common) and row['n_pairs']==len(pair)
    assert eq(row['all_a_mean'],av.mean()) and eq(row['all_b_mean'],bv.mean()) and eq(row['delta_b_minus_a_mean'],(pair.b-pair.a).mean())
    lowcommon+=int(row['n_common_workers'] in [1,2] and row['n_pairs']>0)
ok('same_room_all_counts_means_newmask',True)
print('base checks complete',flush=True)
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine,score_task
from tools.thesis_main.analysis.b8l2_calculation_status_20261016 import inspect_geometry
sampleids=[]
for mask in [A.object_id.isin(added)&A.same_target_unconfirmed.eq(True),A.object_id.isin(added)&~A.same_target_unconfirmed.eq(True),A.is_oos&A.diagnostic_B8L2.notna()]:
    sampleids.extend(A.loc[mask,'object_id'].head(2))
sample_deltas=[]
with scoring_engine(S/'inputs/measurement_engine.zip',S/'inputs/working_models.py') as (engine,models):
    for row in A.to_dict('records'):
        geom=inspect_geometry(O[row['object_id']],engine)
        assert geom['full_input_available']==row['full_input_available'] and geom['floor_input_available']==row['floor_input_available']
        state=row['full_score_state'];ref=R.get(B[row['object_id']]['chosen_target_id'])
        calc='full_computed' if state=='computed' else state
        if state!='computed' and row['target_binding_unique'] and geom['floor_input_available'] and ref and engine.valid.validate_footprint(ref['floor_xz_h'],role='reference')['available']:calc='floor_only_computed'
        assert calc==row['calculation_status']
    for oid in sampleids:
        row=X.loc[oid];ref=R[B[oid]['chosen_target_id']]
        measured=score_task(dict(object_id=oid,image_id=row.image_id,worker_id=row.worker_id,condition=row.condition,current_target_id=ref['target_id'],reference_version=ref['reference_version'],annotation_points=O[oid]['points_1024x512'],reference_points=ref['points_1024x512']),engine,models)
        diff=max(abs(measured[m]-row['diagnostic_'+m]) for m in metrics);assert diff<1e-8
        sample_deltas.append(dict(object_id=oid,is_oos=bool(row.is_oos),same_target_unconfirmed=None if pd.isna(row.same_target_unconfirmed) else bool(row.same_target_unconfirmed),max_abs_delta=diff))
ok('all3152_geometry_reexecuted_no_repair',True);ok('six_fixed_reference_engine_spotchecks',len(sample_deltas)==6)
result=dict(version='independent_b8l2_usage_audit_20261016_v2',checks=checks,counts=dict(inventory=len(A),quality=len(newset),complete=int(A.full_score_state.eq('computed').sum()),scene_buckets=A.scene_bucket.value_counts().to_dict(),calculation_status=A.calculation_status.value_counts().to_dict(),full_score_state=A.full_score_state.value_counts().to_dict(),quality_use=A.quality_use.value_counts().to_dict(),retained=len(retained),added=len(added),removed=len(removed),source_time=int(A.active_time_seconds.count()),target_time=int(A.target_matched_time_seconds.count()),quality_source_time=int(A.loc[A.quality_usable,'active_time_seconds'].count()),OOS_full_diagnostic=int((A.is_oos&A.diagnostic_B8L2.notna()).sum())),old_retained_max_abs_delta=delta,specific_scope_hold_ids=specialhold,door_unconfirmed_ids=unconfirmed,score_spotchecks=sample_deltas,details_cells_recomputed=details_checks)
(P/'audit/USAGE_SCORING_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
