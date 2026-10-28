"""Generate the offline v2.1 workbench snapshot from saved tables and receipts."""
import csv
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone
from .rebuild_v21_20261028 import ROOT, OUT

PAGE=ROOT/'research/statistics/research_explorer_v1_r2_20261017'


def table(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def one(rows,**filters):
    selected=[r for r in rows if all(r.get(k)==v for k,v in filters.items())]
    if len(selected)!=1:raise ValueError((filters,'expected exactly one row',len(selected)))
    return selected[0]


def receipt(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else None


def main():
    inventory=receipt(OUT/'quality_inventory.json');counts=receipt(OUT/'ORIGINAL_CHECKS.json')
    eligible=[r for r in inventory if r['quality_usable']]
    assert len(inventory)==counts['quality_usable']+sum(not r['quality_usable'] for r in inventory)
    assert len(eligible)==counts['quality_usable']
    natural=table(OUT/'natural_results/SUPPORT_STRATIFIED_SUMMARY.csv.gz')
    curve=[dict(scope=r['support'],k=int(r['k']),q=float(r['estimate']),images=int(r['images']),buildings=int(r['buildings'])) for r in natural if r['panel']=='fixed_N_ge_30' and r['layer']=='ordinary_manual' and r['metric']=='Q_mean' and r['weighting']=='image_equal' and r['estimate']]
    for point in curve:
        rates=[r for r in natural if r['support']==point['scope'] and int(r['k'])==point['k'] and r['panel']=='fixed_N_ge_30' and r['layer']=='ordinary_manual' and r['metric']=='actual_consensus_failure_rate' and r['weighting']=='image_equal']
        assert len(rates)<=1
        if rates:
            r=rates[0]
            point.update(failure=float(r['estimate']),failure_images=int(r['images']),failure_eligible=int(r['eligible_images']))
    k2=table(OUT/'two_person_natural256/IMAGE_RESULTS.csv')
    meta=table(OUT/'natural_results/HYBRID_DISPLAY_CURVES.csv.gz')
    origins={r['pool_id']:r['support_origin'] for r in meta if r['layer']=='ordinary_manual'}
    k2rows=[r for r in k2 if r['layer']=='ordinary_manual' and int(r['pool_n'])>=30 and r['Q2']]
    k2points=[]
    for scope in ['original','added','combined']:
        rows=[r for r in k2rows if scope=='combined' or origins[r['pool_id']]==('original_pool' if scope=='original' else 'new_reference_pool')]
        if rows:
            group=[r for r in k2 if r['layer']=='ordinary_manual' and int(r['pool_n'])>=30 and (scope=='combined' or origins[r['pool_id']]==('original_pool' if scope=='original' else 'new_reference_pool'))]
            mean=lambda field:sum(float(r[field]) for r in group if r[field])/sum(bool(r[field]) for r in group) if any(r[field] for r in group) else None
            k2points.append(dict(scope=scope,k=2,q=sum(float(r['Q2']) for r in rows)/len(rows),images=len(rows),buildings=len({r['building'] for r in rows}),failure=mean('consensus_failure_rate'),pair12=mean('delta_1_2'),pair23=mean('delta_2_3'),paired12=sum(int(float(r['paired_1_2'])) for r in group),paired23=sum(int(float(r['paired_2_3'])) for r in group),eligible_images=len(group)))
            k2points[-1].update(failure_images=sum(bool(r['consensus_failure_rate']) for r in group),failure_eligible=len(group))
    variance=table(OUT/'composition_variance/SUMMARY.csv.gz')
    v=[]
    for name in ['DSTRUCT_K3','DSTRUCT_K3_V21']:
        r=one(variance,scope='all',value='all',method=name,metric='B8L2');v.append(dict(method=name,share=float(r['between_share']),panels=int(r['panels']),images=int(r['images']),buildings=int(r['buildings'])))
    comparison=table(OUT/'difficulty_computable_comparison/COMPARISONS.csv')
    dif=[]
    for outcome in ['turn_deficit','reduced','Q']:
        r=one(comparison,outcome=outcome,model='three_geometry',reference='three');dif.append(dict(outcome=outcome,old=float(r['reference_loss']),new=float(r['model_loss']),improvement=float(r['relative_improvement_pct']),better=int(r['better_buildings']),buildings=int(r['buildings'])))
    interval_path=OUT/'two_person_natural256/K2_AGGREGATE_INTERVALS.csv'
    intervals=[]
    if interval_path.exists():
        for r in table(interval_path):
            if r['panel']=='N_ge_30' and r['layer']=='ordinary_manual' and r['weighting']=='image_equal':
                intervals.append(dict(scope=r['scope'],metric=r['metric'],uncertainty=r['uncertainty'],estimate=float(r['estimate']),low=float(r['low']) if r['low'] else None,high=float(r['high']) if r['high'] else None,valid_draws=int(r['valid_draws']),images=int(r['images']),valid_paths=int(r['valid_paths'])))
    stages={}
    for stage in ['confirm','reverse_confirm']:
        r=receipt(OUT/'current_exchange_results'/stage/'COMPLETION.json')
        stages[stage]=None if r is None else dict(complete=bool(r['complete']),registered=int(r['registered_events']),measured=int(r['measured_events']),pending_pools=len(r['pending_pools']))
    strict_rows=table(OUT/'current_exchange_results/confirm/combined/summary/METHOD_N_M_COMPARISON.csv')
    strict_comparison=[r for r in strict_rows if r['method']=='DSTRUCT_K3' and r['metric']=='B8L2']
    assert strict_comparison
    data=dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),release=receipt(OUT/'RELEASE.json'),current=receipt(OUT.parent/'CURRENT.json'),inventory=dict(records=len(inventory),quality=len(eligible),images=len({r['image_id'] for r in eligible})),
        natural_receipt=receipt(OUT/'natural_results/AGGREGATE_BANDS_CHECKS.json'),natural=curve,k2_receipt=receipt(OUT/'two_person_natural256/SUMMARY_CHECKS.json'),k2=k2points,
        k2_intervals=intervals,k2_interval_receipt=receipt(OUT/'two_person_natural256/K2_INTERVAL_CHECKS.json'),
        variance_receipt=receipt(OUT/'composition_variance/CHECKS.json'),variance=v,
        difficulty_receipt=receipt(OUT/'difficulty_computable_comparison/CHECKS.json'),difficulty=dif,strict=stages,strict_comparison=strict_comparison,
        strict_summary=receipt(OUT/'current_exchange_results/SUMMARY_CHECKS.json'),
        d10_formation=receipt(OUT/'d10_formation_sensitivity/SUMMARY_COMPLETE.json'),
        current_same_room_finite=receipt(OUT/'same_room_current_results/finite/exact_changes/ANALYSIS_RECEIPT.json'),
        current_same_room_large=receipt(OUT/'same_room_current_results/large/ANALYSIS_COMPLETE.json'),
        descriptive=receipt(OUT/'descriptive_statistics/CHECKS.json'),room_type=receipt(OUT/'room_type_similarity/INDEPENDENT_CHECKS.json'),
        fusion_common=receipt(OUT/'fusion_common_panel/CHECKS.json'),
        frozen_policy=receipt(OUT/'policy_frozen_design/CHECKS.json'),
        same_room=receipt(OUT/'same_room_frozen_design/INPUT_CHECKS.json'),
        current_policy_design=receipt(OUT/'current_policy_design/CHECKS.json'),
        current_policy_results={c:receipt(OUT/'current_policy_results'/c/'CHECKS.json') for c in ['original_common32','added_reference32']},
        current_same_room=receipt(OUT/'current_same_room_endpoints/CHECKS.json'))
    (PAGE/'v21-results-data.js').write_text('window.V21_RESULTS='+json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))+';\n',encoding='utf8')
    print('v2.1 snapshot: records',len(inventory),'quality',len(eligible),'images',data['inventory']['images'],'curve cells',len(curve))


if __name__=='__main__':main()
