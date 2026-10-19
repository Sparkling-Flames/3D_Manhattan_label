"""Audited error-retention refinements on one comparable opportunity stratum."""
from collections import Counter
import pandas as pd
from pool_io import OUT,ROOT,read,load_pools,save,save_gz,csv,sha,digest
from register_forward import istrue,finite,DIFF,KS,QUALITY_TOLERANCE

def main():
    pfile=ROOT/'work_v2_20261019/audit/fold_behavior_profiles.csv';frame=pd.read_csv(pfile)
    folds=read(OUT/'FOLD_PROFILE_SELECTION_SNAPSHOT.json.gz')['records'];pf={(r['heldout_building'],r['worker_id']):r for r in folds}
    evidence={}
    for r in frame.to_dict('records'):evidence[r['heldout_building'],r['worker_id'],r['evidence_level']]=r
    levels=sorted(frame.evidence_level.dropna().unique());requests=[];ledger=[]
    for p in load_pools():
        if p['meta']['layer']!='ordinary_manual':continue
        b=p['meta']['building'];diff=DIFF[p['meta']['difficulty']]
        for level in levels:
            allowed=[]
            for record in p['records']:
                w=record['worker_id'];person=pf[b,w];event=evidence.get((b,w,level))
                if event and istrue(event['supported']) and istrue(person['Q_supported']) and istrue(person['T_source_supported']) \
                    and finite(person['T_source_effect']) and finite(event['retention_fraction']):allowed.append(w)
            q=lambda w:pf[b,w]['theta_'+diff+'_B8L2'];t=lambda w:pf[b,w]['T_source_effect'];risk=lambda w:evidence[b,w,level]['retention_fraction']
            ordered=sorted(allowed,key=lambda w:(-q(w),w))
            for k in KS:
                meta=dict(pool_id=p['pool_id'],k=k,evidence_level=level,available=len(allowed))
                if len(allowed)<k:ledger.append(dict(meta,status='same_evidence_QTD_known_pool_below_k'));continue
                cutoff=q(ordered[k-1])-QUALITY_TOLERANCE;candidates=[w for w in allowed if q(w)>=cutoff]
                assert len(candidates)>=k
                baseline=sorted(candidates,key=lambda w:(t(w),-q(w),w))[:k]
                selected=sorted(candidates,key=lambda w:(risk(w),t(w),-q(w),w))[:k]
                for name,workers in [('QTD_same_behavior_opportunity_pool',baseline),('QTD_error_retention_first',selected)]:
                    rid='BEH_'+digest([p['pool_id'],k,level,name,workers])[:24]
                    requests.append(dict(request_id=rid,pool_id=p['pool_id'],k=k,worker_ids=workers,
                        request_family='behavior_policy',strategy=name,selection_metric='B8L2',candidate_pool='behavior_'+level,
                        evidence_level=level,profile_training_excludes_building=b,quality_cut=cutoff,admissible_worker_ids=candidates,
                        selected_retention_fraction_mean=sum(risk(w) for w in workers)/k,
                        behavior_interpretation='documented_or_reported_bad_initialization_retention_not_confirmed_correction_success'))
                ledger.append(dict(meta,status='paired_requests_defined',candidate_count=len(candidates),quality_cut=cutoff,same_team=sorted(baseline)==sorted(selected)))
    save(OUT/'BEHAVIOR_FUSION_REGISTRATION.json',dict(schema='v2_behavior_composition_registration_v1',k=list(KS),behavior_source_sha256=sha(pfile),
        audit_registration_sha256=sha(ROOT/'work_v2_20261019/audit/BEHAVIOR_REGISTRATION.json'),
        quality_profiles_snapshot_sha256=sha(OUT/'FOLD_PROFILE_SELECTION_SNAPSHOT.json.gz'),
        rule='One evidence level only, supported opportunities and Q/T history supported; no unknown=0. Same candidate people and theta >= kth theta-3. Baseline T ascending, added behavior retention fraction ascending then T, theta descending, worker ID.',
        interpretation='Confirmed-old and reported-new error opportunities remain distinct. Lower observed retention on targeted opportunities is not general correction success or severe-error risk. No scope/serious exclusion composite.',
        classification_and_selection_frozen_before_behavior_fusion_outcomes=True,request_count=len(requests),
        evidence_levels=levels,families=dict(Counter(r['evidence_level'] for r in requests))))
    save_gz(OUT/'REQUESTS_BEHAVIOR.json.gz',dict(registration_sha256=sha(OUT/'BEHAVIOR_FUSION_REGISTRATION.json'),requests=requests))
    csv(OUT/'BEHAVIOR_SELECTION_COVERAGE.csv',ledger)
    print({'requests':len(requests),'paired_cells':len(requests)//2,'coverage_cells':len(ledger)},flush=True)

if __name__=='__main__':main()
