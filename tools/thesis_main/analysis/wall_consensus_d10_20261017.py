"""Same saved fusion states, same eligibility: B8L2 versus D10 after batch admission."""
from dataclasses import asdict
import json

import numpy as np
import pandas as pd

from .wall_consensus_b8l2_20261016 import ROOT, OUT as OLD, COMPONENTS, finite
from .quality_b8l2_d10_20261017 import dual_scores, model_parameters, read, write
from .scope_quality_scoring_20261016 import scoring_engine
from .current_annotation_context_20261017 import load_current_context
from .wall_consensus_population_20261014 import prepare_record
from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.project_public_research_20260929 import project_bundle

OUT = ROOT/'research/fusion/wall_consensus_d10_20261017'
SHARED = ROOT/'research/quality/quality_b8l2_d10_20261017'
ENGINE = ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'


def add_dual(frame, models):
    result = frame.copy()
    values = [dual_scores(r,models) if finite(r,COMPONENTS) else dict(B8L2=np.nan,D10=np.nan)
              for r in result.to_dict('records')]
    result['B8L2_numeric'] = [r['B8L2'] for r in values]
    result['D10_numeric'] = [r['D10'] for r in values]
    # Existing B8L2 availability is the identical comparison mask, including diagnostic holds.
    mask = result['B8L2'].notna()
    result['D10'] = result.D10_numeric.where(mask)
    result['D10_minus_B8L2_numeric'] = result.D10_numeric-result.B8L2_numeric
    result['B8L2_version'] = 'WQ-B8L2-20261015'
    result['D10_version'] = 'B8L2-D10-20261016'
    assert result.D10.notna().equals(mask)
    assert np.allclose(result.loc[mask,'B8L2'],result.loc[mask,'B8L2_numeric'])
    return result


def target_relation(chosen, reference_id):
    if any(not x for x in chosen):return 'pending'
    return 'all_declared_target' if all(x==reference_id for x in chosen) else 'contains_other_target'


def bridge(contract):
    snapshot = read(OLD/'input_snapshot.json')
    bundle = load_current_bundle(ROOT/contract['input_manifest'])
    context = load_current_context(bundle)
    projected, aliases = project_bundle(bundle)
    objects = {o['object_id']:o for o in bundle['data']['objects']}
    records = {r['id']:r for im in projected['images'] for r in im['annotations']}
    refs = {r['target_id']:r for r in context['reference_catalog']}
    shared = pd.read_csv(ROOT/contract['full_inventory_with_metric_eligibility'],keep_default_na=False).set_index('object_id')
    prior = pd.read_csv(OLD/'usage_v2/shared_usage_member_bridge.csv',keep_default_na=False).set_index('object_id')
    pools = pd.read_csv(ROOT/contract['source_pools'],keep_default_na=False)
    bindings = pd.read_csv(ROOT/contract['all_pre_score_bindings'],keep_default_na=False).set_index('object_id')
    new_images = {r['image_id'] for r in bundle['batch_admission']['records']}
    overlap = new_images & {im['image_id'] for im in snapshot['images']}
    assert not overlap, 'new batch changes fusion pool; geometry reuse must be reviewed'
    checks=[]; member_rows=[]
    for im in snapshot['images']:
        pool=pools[(pools.image_code==im['image']) & (pools.condition=='manual')].iloc[0]
        same_workers=set(json.loads(pool.effective_worker_ids))=={m['worker_id'] for m in im['members']}
        ref=refs[im['reference']['target_id']]
        same_ref=all(ref[k]==im['reference'][k] for k in ('points_1024x512','floor_xz_h','full_reference_available'))
        frozen={r['id']:r for r in im['records']}
        for m in im['members']:
            obj=objects[m['object_id']]; row=shared.loc[m['object_id']]; old=prior.loc[m['object_id']]
            prepared=prepare_record(dict(records[aliases['records'][m['object_id']]],source_pair_indices=obj['ordered_source_pair_indices']))
            assert prepared['points']==frozen[m['record_id']]['points'],m['record_id']
            assert prepared['source_pair_indices']==frozen[m['record_id']]['source_pair_indices'],m['record_id']
            assert row.worker_id==m['worker_id'] and row.image_id==im['image_id'] and row.condition=='manual'
            assert bool(row.pool_vote_eligible)==m['pool_vote_eligible']
            member_rows.append(dict(image=im['image'],object_id=m['object_id'],record_id=m['record_id'],
                worker_id=m['worker_id'],quality_usable=bool(row.quality_usable),
                quality_usable_unchanged=bool(row.quality_usable)==bool(old.shared_quality_usable),
                quality_use=row.quality_use,previous_quality_use=old.shared_quality_use,
                quality_use_unchanged=row.quality_use==old.shared_quality_use,
                is_oos=bool(row.is_oos),
                chosen_target_id=bindings.loc[m['object_id'],'chosen_target_id'],
                previous_chosen_target_id=old.shared_chosen_target_id,
                binding_unchanged=bindings.loc[m['object_id'],'chosen_target_id']==old.shared_chosen_target_id,
                module_original_holdout=m['original_holdout']))
        checks.append(dict(image=im['image'],workers=len(im['members']),worker_set_equal=same_workers,
            source_points_and_order_equal=True,reference_equal=same_ref,
            pool_gate_equal=bool(pool.pool_analysis_eligible)==im['source_pool']['pool_analysis_eligible']))
    assert all(c['worker_set_equal'] and c['reference_equal'] and c['pool_gate_equal'] for c in checks)
    members=pd.DataFrame(member_rows)
    changed=members[~members.quality_use_unchanged]
    purpose_changes=members[~members.quality_usable_unchanged | ~members.binding_unchanged | ~members.quality_use_unchanged]
    pd.DataFrame(checks).to_csv(OUT/'pool_bridge.csv',index=False,encoding='utf-8-sig')
    members.to_csv(OUT/'member_bridge.csv',index=False,encoding='utf-8-sig')
    write(OUT/'INPUT_BRIDGE.json',dict(shared_contract=contract,input_manifest=contract['input_manifest'],
        new_records=len(bundle['batch_admission']['records']),new_images=len(new_images),overlap_images=sorted(overlap),
        fusion_images=18,source_records=len(members),reference_and_points_equal=True,
        member_quality_eligibility_equal=bool(members.quality_usable_unchanged.all()),
        purpose_changes=purpose_changes.to_dict('records'),
        comparison_mask='Frozen prior common mask retained for formula-only comparison; updated routing attached separately, never changes geometry or selects reference.',
        fusion_rerun=False,extra_geometry_measurements=0,source_usage='fusion_compute_use_separated_20261016_v2'))
    return members


def run():
    OUT.mkdir(exist_ok=True)
    contract=read(SHARED/'CROSS_MODULE_INPUTS.json')
    members=bridge(contract)
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (_,models):
        parameters={k:asdict(v) for k,v in zip(('B8L2','D10'),model_parameters(models))}
        assert parameters==contract['parameters']
        frame=add_dual(pd.read_csv(OLD/'usage_v2/trajectory_usage.csv'),models)
        assisted=add_dual(pd.read_csv(OLD/'assisted_endpoints.csv'),models)
    frame['input_bridge_version']='fusion_d10_20261017_v1'
    member_by=members.set_index('record_id')
    frame['current_team_target_relation']=[target_relation(
        [member_by.loc[r,'chosen_target_id'] for r in row.member_record_ids.split('|')],row.reference_id)
        for row in frame.itertuples()]
    frame['comparison_eligibility_version']='frozen_usage_v2_same_mask_not_current_routing_readmission'
    frame['shared_contract_version']=contract['version']
    frame.to_csv(OUT/'trajectory_scores.csv',index=False,encoding='utf-8-sig')
    frame.drop_duplicates(['image','subset']).to_csv(OUT/'subset_scores.csv',index=False,encoding='utf-8-sig')
    endpoints=frame[frame.k.eq(frame.source_pool_workers)].drop_duplicates('image')
    endpoints.to_csv(OUT/'automatic_endpoints.csv',index=False,encoding='utf-8-sig')
    assisted.to_csv(OUT/'assisted_endpoints.csv',index=False,encoding='utf-8-sig')
    summaries=[]; changes=[]
    for (image,k),g in frame.groupby(['image','k']):
        summaries.append(dict(image=image,k=int(k),states=len(g),complete_numeric=int(g.D10_numeric.notna().sum()),
            comparable=int(g.D10.notna().sum()),B8L2=g.B8L2.mean(),D10=g.D10.mean(),
            below_four=int(g.below_four.sum()),no_connection=int((~g.connection_available).sum()),
            diagnostic_only=bool(g.is_oos.all())))
    for image,g in frame.groupby('image'):
        for lo,hi in [(4,8),(8,16),(16,int(g.k.max()))]:
            if hi<=lo or hi>g.k.max():continue
            a=g[g.k.eq(lo)].set_index('path');b=g[g.k.eq(hi)].set_index('path')
            pair=a[['B8L2','D10']].join(b[['B8L2','D10']],lsuffix='_lo',rsuffix='_hi').dropna()
            changes.append(dict(image=image,k_from=lo,k_to=hi,paths=len(a),paired_complete=len(pair),
                B8L2_change=(pair.B8L2_hi-pair.B8L2_lo).mean(),D10_change=(pair.D10_hi-pair.D10_lo).mean()))
    pd.DataFrame(summaries).to_csv(OUT/'by_image_k.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(changes).to_csv(OUT/'matched_changes.csv',index=False,encoding='utf-8-sig')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(5,3,figsize=(13,16),sharey=True)
    for ax,(image,g) in zip(axes.flat,frame[~frame.is_oos].groupby('image')):
        means=g.groupby('k')[['B8L2','D10']].mean()
        ax.plot(means.index,means.B8L2,'o-',ms=2,label='B8L2')
        ax.plot(means.index,means.D10,'x--',ms=3,label='D10')
        label='original_holdout' if g.original_holdout.any() else g.use.iloc[0]
        ax.set_title(image+' / '+label,fontsize=8)
        ax.set_ylim(0,100);ax.set_xlabel('People');ax.grid(alpha=.2)
    axes.flat[0].legend();fig.suptitle('Same observed states: conditional means; OOS excluded; missing values remain gaps')
    fig.tight_layout(rect=(0,0,1,.975));fig.savefig(OUT/'paired_curves.png',dpi=130);plt.close(fig)
    # Stability remains the saved geometry comparison, not a difference between quality indices.
    (OUT/'same_k_geometry_and_legacy_scores.csv').write_bytes((OLD/'same_k_comparison.csv').read_bytes())
    write(OUT/'MODEL_PARAMETERS.json',parameters)
    write(OUT/'CHECKS.json',dict(path_states=len(frame),unique_subsets=len(frame.drop_duplicates(['image','subset'])),
        numeric=int(frame.D10_numeric.notna().sum()),same_mask_comparable=int(frame.D10.notna().sum()),
        oos_quality_count=int(frame.loc[frame.is_oos,'D10'].notna().sum()),
        primary_states=int(frame.primary_comparison_eligible.sum()),automatic_endpoints=len(endpoints),
        assisted_endpoints=len(assisted),fusion_rerun=False,interpolation=False,additional_measurements=0,
        shared_contract_unchanged=contract==read(SHARED/'CROSS_MODULE_INPUTS.json')))
    assert contract==read(SHARED/'CROSS_MODULE_INPUTS.json'), 'shared version changed during run'
    print(read(OUT/'CHECKS.json'))


if __name__=='__main__':run()
