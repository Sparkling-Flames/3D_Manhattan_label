"""Read-only source/claim audit; write a bounded readiness receipt, not new results."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/releases/v2.1'
OUT=BASE/'research_readiness_20261031'
UP=BASE/'admitted_space_extension/image_difficulty_20261030'

def read(path):return json.loads(path.read_text(encoding='utf8'))

def main():
    matrix=pd.read_csv(OUT/'MODULE_MATRIX.csv');assert len(matrix)==21 and matrix.module.is_unique
    paths=sorted(set(matrix.entry)|set(matrix.evidence));checked=[]
    for name in paths:
        p=ROOT/name;assert p.exists(),name
        r=dict(path=name,kind='directory' if p.is_dir() else p.suffix,readable=True,rows=None)
        if p.is_dir():assert any(p.iterdir())
        elif p.name.endswith(('.csv','.csv.gz')):
            header=pd.read_csv(p,nrows=0);assert len(header.columns)>0
            r['rows']=sum(len(c) for c in pd.read_csv(p,usecols=[0],chunksize=50000));assert r['rows']>0
            r['columns']='|'.join(header.columns)
        elif p.suffix=='.json':
            d=read(p);r['rows']=len(d);assert len(d)>0
        else:assert p.read_text(encoding='utf8').strip()
        checked.append(r)
    pd.DataFrame(checked).to_csv(OUT/'SOURCE_READ_CHECKS.csv',index=False,encoding='utf-8-sig')
    claims=[]
    def check(name,value,expected,source,tolerance=0):
        ok=abs(value-expected)<=tolerance
        claims.append(dict(claim=name,observed=float(value),expected=float(expected),tolerance=tolerance,passed=bool(ok),source=str(source.relative_to(ROOT))))
        assert ok,(name,value,expected)
    p=BASE/'quality_inventory.csv';q=pd.read_csv(p,usecols=['object_id','quality_usable']);check('inventory',len(q),10439,p);check('primary_quality',q.quality_usable.sum(),8154,p)
    p=UP/'INPUT_CHECKS.json';d=read(p)
    for k,v in [('pools',31),('images',28),('records',231)]:check('other_'+k,d[k],v,p)
    p=UP/'HALF_SUMMARY.csv';d=pd.read_csv(p)
    r=d[d.n.eq(14)&d.scope.eq('updated_labels_legal_subset')].iloc[0]
    for k,v in [('events',147),('registered_images',69),('valid_images',67)]:check('half14_'+k,r[k],v,p)
    check('half14_CB',r.CB,6.380314,p,1e-6)
    p=UP/'SAME_ROOM_HALF_SUMMARY.csv';d=pd.read_csv(p);d=d[d.method.eq('TARGET_DSTRUCT_K3')&d.direction.eq('C2→C3')]
    for n,v in [(10,19),(12,7),(14,2)]:check('same_room_'+str(n)+'_pairs',d[d.n.eq(n)].iloc[0].valid_pairs,v,p)
    p=UP/'speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv';d=pd.read_csv(p);r=d[d.method.eq('TARGET_DSTRUCT_K3')&d.condition.eq('manual')&d.origin.eq('new')&d.metric.eq('turn_n')].iloc[0];check('speed_current_pairs',r.valid_pair_rows,100,p)
    p=BASE/'closeout_20261030/alliance_completion_20261031/ALLIANCE_414_RESOLUTION.csv';d=pd.read_csv(p);check('changed_alliances',len(d),414,p)
    p=BASE/'fusion_common_panel/METHOD_ENDPOINTS.csv';d=pd.read_csv(p);check('fusion_method_rows',len(d),414,p);check('fusion_teams',d.team_key.nunique(),138,p)
    p=BASE/'q_only_exchange_20261031/EVALUATION_CHECKS.json';d=read(p)
    for k,v in [('unique_endpoints',670),('reused',624),('native_missing',46)]:check('Q_only_'+k,d[k],v,p)
    p=BASE/'q_only_exchange_20261031/diagnostic_20261031/WORKER_DIFFICULTY_CURRENT.csv';d=pd.read_csv(p);d=d[d.condition.eq('manual')]
    for scope,n in [('primary',6512),('all_admitted',6739)]:check('person_difficulty_'+scope,d[d.scope.eq(scope)].records.sum(),n,p)
    p=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv';d=pd.read_csv(p);r=d[d.metric.eq('B8L2')&d.scenario.eq('v21_all')&d.scope.eq('ordinary_no_relation_oos_pending')&d.method.eq('source_mean')].iloc[0];check('same_room_mean_mae',r.mae,6.463518,p,1e-6);check('same_room_prediction_images',r.images,65,p)
    p=BASE/'room_type_similarity/reference_only_attribution/NESTED_ENVIRONMENT_CHECKS.json';d=read(p);check('unresolved_old_predictions',d['results']['v2_original177']['prediction_rows_above_1e_8'],52,p)
    p=BASE/'full_chain_downstream_20261030/repro_repair_20261031/FINAL_CHECKS.json';d=read(p)
    for k,v in [('numerical_tasks_passed',7),('compared_tables',15)]:check('repro_'+k,d[k],v,p)
    doorway=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
    p=doorway/'CORRECTED_RECORD_LEDGER.json';records=[r for r in read(p) if r['base_candidate']]
    check('doorway_base_records',len(records),584,p)
    for scope,n in [('全部',383),('空间1',79),('空间2',67),(None,24),('都不符合（看不懂）',31)]:
        check('doorway_scope_'+(scope or '待定'),sum(r['final_scope']==scope for r in records),n,p)
    p=doorway/'CORRECTED_PRIMARY_POOLS.json';pools=read(p);check('doorway_pools',len(pools),85,p)
    check('doorway_images',len({r['image'] for r in pools}),17,p);check('doorway_buildings',len({r['building'] for r in pools}),9,p)
    p=doorway/'SOURCE_REFERENCE_CHECKS_51.json';check('doorway_references',len(read(p)),51,p)
    p=doorway/'computed_delta/CORRECTED_HEADLINES.json';d=read(p)
    for name,mean,n in [('screening_k10',.466270,3507),('whole_compatible_k10',1.481182,3618),('screened_6_to_10',-1.619496,2927)]:
        r=d[name]['B8L2'];check('doorway_'+name+'_Q',r['mean'],mean,p,1e-6)
        check('doorway_'+name+'_paired',r['paired_finite'],n,p)
        check('doorway_'+name+'_attempts',d[name]['complete_evaluable']['attempts'],4352,p)
        assert abs(sum(r['per_image'].values())/len(r['per_image'])-r['mean'])<1e-12
    p=ROOT/'research/data/doorway_review_20261030/screen439_results_20261031/RELEASE.json';d=read(p)
    for k,v in [('retained',439),('excluded',145),('quality_pair_count_k10',3411),('formation_pair_count_k10',4352)]:check('current439_'+k,d[k],v,p)
    pd.DataFrame(claims).to_csv(OUT/'CLAIM_CHECKS.csv',index=False,encoding='utf-8-sig')
    release=read(BASE/'RELEASE.json');assert release['personnel_reselection']['classification_finalized'] is True
    assert release['other_admitted_spaces']['pending']==[] and release['full_mainline_including_other_targets_complete'] is False
    assert read(BASE.parent/'CURRENT.json')['data_release']=='v2'
    result=dict(date='2026-10-31',modules=len(matrix),readable_sources=len(checked),numeric_claim_checks=len(claims),passed=True,scope='source readability, exact support and saved scalar checks; prior computation receipts inspected, not rerun',new_scoring=0,new_fusion=0,new_classification=0,classification_finalized=True,doorway_review='current_584_439_complete',browser_acceptance='separate_workbench_thread',remote_push=False,remaining=['52_old_same_use_nested_predictions','research_workbench_browser_acceptance','doorway_cache_archive_before_cross_machine_release','fresh_remote_clone_and_full_fusion_not_claimed'])
    (OUT/'CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
