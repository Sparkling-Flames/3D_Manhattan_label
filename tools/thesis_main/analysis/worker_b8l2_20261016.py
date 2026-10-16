"""Frozen B8L2 personnel profiles and real-member replacement comparisons."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .worker_wq_integration_20261015 import read, fit_axis, geometry_equal, summarize_entrants
from .worker_classification_progress_20261014 import half_stability
from .scope_quality_scoring_20261016 import scoring_engine
from .wall_consensus_quality_20261015 import measured, save
from .wall_consensus_b8l2_20261016 import apply_scores

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/workers/worker_b8l2_20261016'
SHARED = ROOT/'research/statistics/b8l2_shared_v6_20261016'
OLD = ROOT/'research/workers/worker_four_axis_update_20261015'
TEAMS = ROOT/'research/workers/worker_wq_integration_20261015'
FUSION = ROOT/'research/fusion/wall_consensus_b8l2_20261016'
COMPONENTS = ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']


def csv(name, frame, directory=None):
    frame = pd.DataFrame(frame).copy()
    for col in frame:
        if frame[col].map(lambda x: isinstance(x, (list, dict))).any():
            frame[col] = frame[col].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x,(list,dict)) else x)
    frame.to_csv((directory or OUT)/name, index=False, encoding='utf-8-sig')


def bind_admission(scores, gates):
    gates = pd.DataFrame(gates).set_index('object_id')
    if not gates.index.is_unique or not scores.object_id.is_unique:
        raise ValueError('duplicate object identity')
    rows = []
    for r in scores.to_dict('records'):
        g = gates.loc[r['object_id']]
        if any(r[k] != g[k] for k in ('image_id','worker_id','condition')):
            raise ValueError('admission identity mismatch')
        for k in ('original_holdout','role','personnel_barriers','context_barriers'):
            r['admission_'+k] = g[k]
        oos=(r['condition']=='oos' or 'oos' in str(r.get('scene',''))
             or r.get('oos_subtype','not_recorded') not in ('not_recorded','not_oos'))
        doorway='doorway' in str(r.get('scene',''))
        r['profile_allowed'] = (r['condition']=='manual' and r['quality_use']=='ordinary_primary' and not oos and not doorway
            and g['role']=='manual_development_candidate' and not g['original_holdout']
            and not g['personnel_barriers'] and not g['context_barriers'])
        rows.append(r)
    return pd.DataFrame(rows)


def inventory_coverage(current, gates):
    """Missing scores are not evidence of geometric failure; keep source reasons separate."""
    inventory=bind_admission(pd.read_csv(SHARED/'shared_records.csv'),gates)
    inventory['in_current_Q_profile']=inventory.object_id.isin(current.object_id)
    inventory['oos_diagnostic_only']=(inventory.condition.eq('oos')|inventory.scene.str.contains('oos',na=False)
        |~inventory.oos_subtype.isin(['not_recorded','not_oos']))
    inventory['doorway_special']=inventory.scene.str.contains('doorway',na=False)
    inventory['source_pairing_unavailable']=inventory.geometry_status.eq('pairing_unavailable')
    inventory['numeric_complete']=inventory.rescore_status.eq('complete')
    inventory['quality_applicability']='not_in_current_Q_profile'
    inventory.loc[inventory.in_current_Q_profile,'quality_applicability']='ordinary_Q_profile'
    inventory.loc[inventory.doorway_special,'quality_applicability']='doorway_separate_pending_shared_use_revision'
    inventory.loc[inventory.oos_diagnostic_only,'quality_applicability']='OOS_diagnostic_not_quality'
    assert not inventory.loc[inventory.oos_diagnostic_only,'in_current_Q_profile'].any()
    columns=['object_id','worker_id','image_code','condition','scene','oos_subtype','cleaning_disposition','geometry_status',
        'pool_vote_eligible','pool_analysis_eligible','current_quality_eligible','quality_use','rescore_status',
        'quality_exclusion_reasons','pool_vote_exclusion_reasons','pool_analysis_exclusion_reasons',
        'source_active_time_seconds','target_matched_time_seconds','in_current_Q_profile','oos_diagnostic_only',
        'doorway_special','source_pairing_unavailable','numeric_complete','quality_applicability']
    csv('personnel_inventory_audit.csv',inventory[columns])
    counts=[];reasons=[]
    for worker,d in inventory.groupby('worker_id'):
        counts.append(dict(worker_id=worker,total_annotations=len(d),retained_source=int(d.cleaning_disposition.eq('retained').sum()),
            review_excluded=int(d.cleaning_disposition.eq('excluded_by_review').sum()),historically_not_accepted=int(d.cleaning_disposition.eq('historical_not_accepted').sum()),
            retained_pending=int(d.cleaning_disposition.eq('retained_pending').sum()),
            source_vote_excluded=int((~d.pool_vote_eligible).sum()),outside_current_Q_profile=int((~d.in_current_Q_profile).sum()),
            current_Q_profile=int(d.in_current_Q_profile.sum()),numeric_complete=int(d.numeric_complete.sum()),
            source_pairing_unavailable=int(d.source_pairing_unavailable.sum()),doorway_rows=int(d.doorway_special.sum()),
            OOS_diagnostic_rows=int(d.oos_diagnostic_only.sum())))
        for field in ['quality_exclusion_reasons','pool_vote_exclusion_reasons','pool_analysis_exclusion_reasons']:
            exploded=d[field].dropna().map(json.loads).explode().dropna().value_counts()
            reasons.extend(dict(worker_id=worker,reason_field=field,reason=reason,annotations=int(n)) for reason,n in exploded.items())
    csv('worker_exclusion_counts.csv',counts);csv('worker_exclusion_reasons.csv',reasons)
    special=inventory[inventory.doorway_special|inventory.oos_diagnostic_only]
    csv('special_computability_coverage.csv',special.groupby(['worker_id','scene','condition'],dropna=False).agg(
        annotations=('object_id','size'),existing_numeric_complete=('numeric_complete','sum'),
        source_pairing_unavailable=('source_pairing_unavailable','sum')).reset_index())
    save(OUT/'SPECIAL_DEPENDENCIES.json',dict(shared_version=read(SHARED/'CROSS_MODULE_INPUTS.json')['version'],
        doorway_single_answer_scores='shared v1 has no doorway quality rows; await revised common computability/use manifest; do not score a competing library',
        OOS='all numeric values diagnostic only; no Q training validation or quality benefit',
        missing_score='not_queued does not mean uncomputable; pairing_unavailable is a recorded source geometry status, not a complete failure taxonomy',
        needed=['revised per-object numerical computability and analysis applicability','trusted bound doorway reference and measured values',
                'full failure reasons including insufficient valid paired points'],
        current_worker_counts='worker_exclusion_counts.csv distinguishes review exclusion, source vote exclusion and outside Q profile'))


def prediction_rows(test, fit, axis, time_fit=None):
    fit = fit[fit.supported & fit.label.ne('unclassified')].copy()
    fit['class_effect'] = fit.groupby('label').effect.transform('mean')
    fields = ['worker_id','effect','label','class_effect']
    if time_fit is not None:
        t = time_fit[time_fit.supported & time_fit.label.ne('unclassified')]
        fit = fit.merge(t[['worker_id','label']].rename(columns={'label':'time_label'}), on='worker_id')
        fit['QT_label'] = fit.label + '|' + fit.time_label
        # Two supported training people per cell avoids treating singleton cells as a taxonomy.
        fit = fit[fit.groupby('QT_label').worker_id.transform('size').ge(2)].copy()
        fit['QT_effect'] = fit.groupby('QT_label').effect.transform('mean')
        fields += ['QT_effect','QT_label']
    d = test.merge(fit[fields], on='worker_id', validate='many_to_one')
    d = d[d.groupby('context_key').worker_id.transform('size').ge(2)].copy()
    d['target'] = d[axis]-d.groupby('context_key')[axis].transform('mean')
    for name, field in [('continuous','effect'),('class','class_effect')]+([('QT','QT_effect')] if time_fit is not None else []):
        d[name+'_prediction'] = d[field]-d.groupby('context_key')[field].transform('mean')
        d[name+'_sqerr'] = (d.target-d[name+'_prediction'])**2
    d['baseline_sqerr'] = d.target**2
    return d


def primary_attempt(im, selected):
    return (im['use']=='ordinary_conditional' and im['source_pool']['pool_analysis_eligible']
        and all(m['quality_gate']['status']=='candidate_pending_geometry'
            and m['worker_quality_gate']=='candidate_pending_geometry' and not m['legacy_personnel_barriers']
            and not m['original_holdout']
            and (not m['binding'] or m['binding']['chosen_target_id']==im['reference']['target_id']) for m in selected))


def performance(preds):
    rows = []
    if preds.empty:
        return pd.DataFrame()
    for (panel,axis,comparison), d in preds.groupby(['panel','axis','comparison']):
        methods = ['continuous','class']+(['QT'] if comparison.startswith('QT_') else [])
        by = d.groupby('building_id')[[x+'_sqerr' for x in ['baseline',*methods]]].mean()
        for method in methods:
            rows.append(dict(panel=panel,axis=axis,comparison=comparison,method=method,
                rows=len(d),workers=d.worker_id.nunique(),buildings=len(by),
                building_equal_reduction=1-by[method+'_sqerr'].mean()/by.baseline_sqerr.mean(),
                pooled_reduction=1-d[method+'_sqerr'].sum()/d.baseline_sqerr.sum(),
                improved_buildings=int((by[method+'_sqerr']<by.baseline_sqerr).sum())))
    return pd.DataFrame(rows)


def profile_panel(data, name, axes, extra_buildings=()):
    fits, predictions = [], []
    for axis in axes:
        for building in [None,*sorted(set(data.building_id)|set(extra_buildings))]:
            fit = fit_axis(data, axis, building)
            fit['panel'] = name
            fits.append(fit)
            if building is None:
                continue
            test = prediction_rows(data[data.building_id.eq(building)],fit,axis)
            test['panel'], test['axis'], test['comparison'] = name, axis, 'Q_only'
            predictions.append(test)
    return pd.concat(fits,ignore_index=True), pd.concat(predictions,ignore_index=True)


def freeze_inputs():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest = read(SHARED/'CROSS_MODULE_INPUTS.json')
    assert manifest['version']=='b8l2_shared_v6_20261016_v1'
    assert manifest['score_version']=='WQ-B8L2-20261015'
    gates = read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']
    fields = ['object_id','image_id','worker_id','condition','original_holdout','role','personnel_barriers','context_barriers']
    frozen = OUT/'admission_snapshot.json'
    if not frozen.exists():
        save(frozen,[{k:g[k] for k in fields} for g in gates])
    gates = read(frozen)
    scores = bind_admission(pd.read_csv(SHARED/'quality_records.csv'), gates)
    csv('score_admission_audit.csv',scores[['object_id','worker_id','condition','quality_use','profile_allowed',
        *['admission_'+k for k in fields[4:]]]])
    current = scores[scores.profile_allowed].copy()
    current['context_key'] = current[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    assert not current.duplicated(['worker_id','context_key']).any()
    assert current.pool_analysis_eligible.all() and current.current_quality_eligible.all()
    csv('current_quality_panel.csv',current)
    save(OUT/'INPUTS.json',dict(shared=manifest,admission_source='research/quality_data_admission_audit_20261013/FULL_ADMISSION.json',
        admission_snapshot='admission_snapshot.json',fusion_snapshot=str(FUSION.relative_to(ROOT)/'input_snapshot.json'),
        old_panel=str(OLD.relative_to(ROOT)/'quality_panel_931.csv'),support_rule='6 informative tasks and 3 buildings; no target-building data',
        classification='training effect sign; exact zero/unsupported unclassified; no threshold tuning',
        global_registration='pending coordinator; no global catalog or index mutation'))
    return current, gates


def run_profiles(current, gates, models, extra_buildings):
    old = pd.read_csv(OLD/'quality_panel_931.csv')
    old['B8L2'] = models.score(*[old[k].to_numpy() for k in COMPONENTS],params=models.B)
    assert np.allclose(models.score(*[old[k].to_numpy() for k in COMPONENTS],params=models.WQ),old.WQ,rtol=0,atol=1e-8)
    changes = pd.read_csv(SHARED/'member_changes.csv')
    retained = current[current.object_id.isin(changes.loc[changes.membership_change.eq('retained'),'object_id'])].copy()
    panels = {'historical931_fixed_reference':old,'current_retained_only':retained,'current949':current}
    fits, preds, coverage = [], [], []
    for name,d in panels.items():
        f,p = profile_panel(d,name,['WQ','B8L2','IoU3D100'],extra_buildings)
        fits.append(f);preds.append(p)
        coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique()))
    for difficulty,d in current.groupby('difficulty_class'):
        name='condition_'+difficulty
        f,p=profile_panel(d,name,['B8L2'],extra_buildings)
        fits.append(f);preds.append(p)
        coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique()))
    source = pd.read_csv(SHARED/'shared_records.csv')
    source = bind_admission(source,gates)
    time_allowed = (source.condition.eq('manual') & source.pool_analysis_eligible & source.ordinary_difficulty_eligible
        & source.admission_role.eq('manual_development_candidate') & ~source.admission_original_holdout
        & source.admission_personnel_barriers.map(len).eq(0) & source.admission_context_barriers.map(len).eq(0))
    times = {}
    for name,col in [('T_source','source_active_time_seconds'),('T_target','target_matched_time_seconds')]:
        d = source[time_allowed & source[col].notna()].copy()
        assert d[col].gt(0).all() and d.time_source.notna().all() and d.time_source_file.notna().all()
        assert not d.time_source.str.contains('lead_time',case=False).any()
        keys=['image_id','condition']+(['reference_id','reference_version'] if name=='T_target' else [])
        assert d[keys].notna().all().all()
        d['context_key'] = d[keys].apply(lambda r:json.dumps(r.tolist()),axis=1)
        d[name] = np.log1p(d[col])
        csv(name+'_panel.csv',d)
        f,p = profile_panel(d,name,[name],extra_buildings)
        fits.append(f);preds.append(p);times[name]=f
        coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique()))
    fits = pd.concat(fits,ignore_index=True)
    for name,tf in times.items():
        for building in sorted(current.building_id.unique()):
            qf = fits[(fits.panel=='current949') & (fits.axis=='B8L2') & (fits.fold==building)]
            test = current[current.building_id.eq(building)]
            # Target-time comparisons only evaluate answers with audited same-target time.
            if name=='T_target':test=test[test.target_matched_time_seconds.notna()]
            p=prediction_rows(test,qf,'B8L2',tf[tf.fold.eq(building)])
            p['panel'],p['axis'],p['comparison']='current949','B8L2','QT_'+name
            preds.append(p)
    preds=pd.concat(preds,ignore_index=True)
    csv('fold_profiles.csv',fits)
    csv('profiles.csv',fits[fits.fold.eq('full_descriptive')])
    keep=['object_id','worker_id','building_id','context_key','panel','axis','comparison','target','label',
          'continuous_prediction','class_prediction','QT_prediction','baseline_sqerr','continuous_sqerr','class_sqerr','QT_sqerr']
    csv('predictions.csv',preds.reindex(columns=keep))
    csv('prediction_performance.csv',performance(preds));csv('coverage.csv',coverage)
    full=fits[fits.fold.eq('full_descriptive')]
    sensitivity=[]
    for pa,aa,pb,ab,kind in [('historical931_fixed_reference','WQ','historical931_fixed_reference','B8L2','metric_only_historical'),
        ('current949','WQ','current949','B8L2','metric_only_current'),
        ('current_retained_only','B8L2','current949','B8L2','new_score_coverage'),
        ('historical931_fixed_reference','B8L2','current949','B8L2','reference_and_membership_combined')]:
        a=full[(full.panel==pa)&(full.axis==aa)].set_index('worker_id')
        b=full[(full.panel==pb)&(full.axis==ab)].set_index('worker_id')
        d=a[['effect','label','supported']].join(b[['effect','label','supported']],lsuffix='_a',rsuffix='_b',how='outer').reset_index()
        d['comparison']=kind;d['label_changed']=d.label_a.ne(d.label_b)
        sensitivity.append(d)
    csv('profile_sensitivity.csv',pd.concat(sensitivity,ignore_index=True))
    overlap=old[['object_id','reference_id','WQ','B8L2','IoU3D100']].merge(current[['object_id','reference_id','WQ','B8L2','IoU3D100']],on='object_id',how='outer',suffixes=('_old','_current'),indicator=True)
    overlap['same_reference_id']=overlap.reference_id_old.eq(overlap.reference_id_current)
    references={r['target_id']:r for r in read(SHARED/'inputs/reference_catalog.json')}
    oldgeometries=read(TEAMS/'reference_geometries.json')
    oldkeys=old.set_index('object_id').reference_geometry_key
    overlap['same_reference_geometry']=[geometry_equal(oldgeometries[oldkeys[r.object_id]]['geometry'],references[r.reference_id_current]['geometry'])
        if r.object_id in oldkeys.index and pd.notna(r.reference_id_current) else None for r in overlap.itertuples()]
    csv('historical_current_overlap.csv',overlap)
    halves=[]
    for name,data,axis in [('current949',current,'B8L2'),*[(n,pd.read_csv(OUT/(n+'_panel.csv')),n) for n in times]]:
        h=half_stability(data.assign(value=data[axis]),sorted(data.worker_id.unique()))
        h['axis'],h['panel']=axis,name
        halves.append(h)
    csv('disjoint_halves.csv',pd.concat(halves,ignore_index=True).replace({'faster':'below_pool','slower':'above_pool'}))
    # Preserve auxiliary axes as historical evidence, not relabelled current S/B correctness or gain.
    aux=pd.read_csv(OLD/'four_axis_profiles.csv').drop(columns=['Q','T'])
    q=full[(full.panel=='current949')&full.supported].pivot(index='worker_id',columns='axis',values='effect')
    for name in times:
        q[name]=full[(full.panel==name)&full.supported].set_index('worker_id').effect
    combined=aux.merge(q.reset_index(),on='worker_id',how='outer')
    csv('four_axis_evidence.csv',combined)
    corr=[]
    for a in ['S_rejection','S_clear_rejection','B_edit','B_legacy_gain']:
        for b in ['B8L2','T_source','T_target']:
            d=combined[[a,b]].dropna()
            corr.append(dict(auxiliary=a,current_axis=b,workers=len(d),spearman=d[a].rank().corr(d[b].rank())))
    csv('auxiliary_correlations.csv',corr)
    return fits


def team_scores(engine,models,snapshot):
    old=pd.read_csv(TEAMS/'cached_team_scores.csv')
    frozen_scores=OUT/'shared_fusion_scores.csv'
    if not frozen_scores.exists():
        shared=pd.read_csv(FUSION/'subset_scores.csv').merge(old[['image','subset']],on=['image','subset'],validate='one_to_one')
        csv('shared_fusion_scores.csv',shared)
    shared=pd.read_csv(frozen_scores).set_index(['image','subset'])
    oldrefs={r['image']:r for r in read(TEAMS/'team_references.json')}
    rows=[]
    for im in snapshot['images']:
        targets=old[old.image.eq(im['image'])]
        if targets.empty:continue
        assert im['members_equal_frozen'] and not im['changed_geometry_records']
        payload=read_gzip(ROOT/im['state_source'])
        states={tuple(sorted(s['workers'])):s['automatic'] for s in payload['states']}
        extra=TEAMS/'new_states'/f"{im['image']}.json.gz"
        if extra.exists():states.update({tuple(sorted(s['workers'])):s['automatic'] for s in read_gzip(extra)['states']})
        aliases={m['public_worker']:m['worker_id'] for m in im['members']}
        ref=im['reference'];oldref=oldrefs[im['image']]
        equal=bool(oldref['geometry'] and ref['geometry'] and geometry_equal(oldref['geometry'],ref['geometry']))
        for r in targets.to_dict('records'):
            key=tuple(r['subset'].split('|'));state=states[key]
            assert len(key)==len(set(key)) and '|'.join(sorted(aliases[w] for w in key))==r['workers']
            use=im['use'];primary=primary_attempt(im,[m for m in im['members'] if m['public_worker'] in key])
            if (im['image'],r['subset']) in shared.index:
                measured_row=shared.loc[(im['image'],r['subset'])].to_dict()
                assert measured_row['reference_id']==ref['target_id']
                origin='fusion_shared_exact_members'
            else:
                measured_row=apply_scores(measured(engine,state,dict(points=ref['points_1024x512'],floor=ref['floor_xz_h'])),models,use)
                origin='personnel_frozen_added_states_same_engine'
            old_b=None
            if pd.notna(r['WQ']):
                if equal:
                    assert abs(measured_row['WQ']-r['WQ'])<1e-7,'fixed team old WQ mismatch'
                    old_b=measured_row['B8L2']
                else:
                    result=engine.measure(engine.geometry(state['candidate']['points']),oldref['geometry'])
                    assert result['status']=='complete' and abs(result['scores']['WQ']-r['WQ'])<1e-7
                    old_b=float(models.score(*[result['metrics'][k] for k in COMPONENTS],params=models.B))
            rows.append(dict(image=r['image'],building_id=r['building_id'],subset=r['subset'],workers=r['workers'],k=r['k'],
                original_holdout=r['original_holdout'],restricted_member_n=r['restricted_member_n'],use=use,
                primary_attempt_eligible=primary,primary_comparison_eligible=primary and pd.notna(measured_row.get('B8L2')),
                reference_id=ref['target_id'],reference_version=ref['reference_version'],
                reference_equal_historical=equal,old_WQ=r['WQ'],old_B8L2=old_b,old_IoU3D100=r['IoU3D100'],
                B8L2=measured_row.get('B8L2'),WQ=measured_row.get('WQ'),IoU3D100=measured_row.get('IoU3D100'),
                score_status=measured_row['score_status'],origin=origin,**{k:measured_row.get(k) for k in COMPONENTS}))
        print('scored frozen personnel teams',im['image'],len(targets),flush=True)
    result=pd.DataFrame(rows)
    csv('team_scores.csv',result)
    return result


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:return json.load(handle)


def replacements(teams,fits):
    pairs=pd.read_csv(TEAMS/'replacement_pairs.csv')
    lookup=teams.set_index(['image','subset'])
    profiles=fits[(fits.panel=='current949')&(fits.axis=='B8L2')].set_index(['fold','worker_id'])
    time=fits[fits.panel=='T_source'].set_index(['fold','worker_id'])
    rows=[]
    for r in pairs.to_dict('records'):
        a,b=lookup.loc[(r['image'],r['team_a'])],lookup.loc[(r['image'],r['team_b'])]
        aw,bw=set(a.workers.split('|')),set(b.workers.split('|'))
        assert aw-bw=={r['removed']} and bw-aw=={r['added']} and len(aw)==len(bw)==r['k']
        assert a.reference_id==b.reference_id
        row={k:r[k] for k in ['image','building_id','k','base','team_a','team_b','removed','added','floor_change','raw_pair_change','original_holdout']}
        row.update(primary_attempt_eligible=bool(a.primary_attempt_eligible and b.primary_attempt_eligible),
            primary_comparison_eligible=bool(a.primary_comparison_eligible and b.primary_comparison_eligible),
            reference_id=a.reference_id,B8L2_change=b.B8L2-a.B8L2,WQ_change=b.WQ-a.WQ,
            old_B8L2_change=b.old_B8L2-a.old_B8L2,old_WQ_change=b.old_WQ-a.old_WQ,IoU3D100_change=b.IoU3D100-a.IoU3D100,
            legacy959_WQ_swap=r['WQ_swap'])
        for axis,source in [('B8L2',profiles),('T_source',time)]:
            keys=[(r['building_id'],w) for w in [r['removed'],r['added']]]
            if all(key in source.index and source.loc[key].supported and source.loc[key].label!='unclassified' for key in keys):
                x,y=[source.loc[key] for key in keys]
                row[axis+'_swap']='same_class' if x.label==y.label else 'cross_class'
                row[axis+'_effect_change']=y.effect-x.effect
            else:row[axis+'_swap']='unclassified';row[axis+'_effect_change']=np.nan
        row['QT_swap']=('unclassified' if 'unclassified' in [row['B8L2_swap'],row['T_source_swap']] else
            'same_class' if row['B8L2_swap']==row['T_source_swap']=='same_class' else 'cross_class')
        rows.append(row)
    edges=pd.DataFrame(rows);csv('replacement_pairs.csv',edges)
    summaries=[];entrants=[]
    for (image,k,base),d in edges.groupby(['image','k','base']):
        for axis in ['B8L2','T_source','QT']:
            same=d[d[axis+'_swap']=='same_class'];cross=d[d[axis+'_swap']=='cross_class']
            if same.empty or cross.empty:continue
            summaries.append(dict(image=image,k=k,base=base,axis=axis,primary=bool(d.primary_attempt_eligible.all()),
                same_pairs=len(same),cross_pairs=len(cross),same_quality_pairs=int(same.B8L2_change.notna().sum()),
                cross_quality_pairs=int(cross.B8L2_change.notna().sum()),
                floor_cross_minus_same=cross.floor_change.mean()-same.floor_change.mean(),
                absolute_quality_cross_minus_same=cross.B8L2_change.abs().mean()-same.B8L2_change.abs().mean()))
        if k!=8:continue
        subset_ids=set(d.team_a)|set(d.team_b);base_set=set(base.split('|'));imteams=teams[teams.image.eq(image)].set_index('subset')
        individuals=[]
        for subset in sorted(subset_ids):
            row=imteams.loc[subset]
            # Alias-to-real mapping follows the verified single-person edge identities.
            worker=next((r.removed if r.team_a==subset else r.added for r in d.itertuples() if subset in (r.team_a,r.team_b)))
            assert len(set(subset.split('|'))-base_set)==1
            key=(row.building_id,worker)
            effect=profiles.loc[key].effect if key in profiles.index and profiles.loc[key].supported else np.nan
            individuals.append(dict(image=image,k=k,base=base,subset=subset,worker_id=worker,effect=effect,
                B8L2=row.B8L2,WQ=row.WQ,IoU3D100=row.IoU3D100,primary=row.primary_attempt_eligible))
        entrants.extend(individuals)
    csv('matched_base_comparisons.csv',summaries);csv('fixed_base_entrants.csv',entrants)
    stats=[]
    for (image,base),d in pd.DataFrame(entrants).groupby(['image','base']):
        for outcome in ['B8L2','WQ','IoU3D100']:
            stats.append(dict(image=image,base=base,outcome=outcome,primary=bool(d.primary.all()),attempted_entrants=len(d),
                **summarize_entrants(d.effect,d[outcome])))
    csv('fixed_base_associations.csv',stats)


def diagnostic_summaries(fits):
    edges=pd.read_csv(OUT/'replacement_pairs.csv')
    contrasts=[('historical931_fixed_reference','WQ'),('historical931_fixed_reference','B8L2'),
        ('current_retained_only','B8L2'),('current949','WQ'),('current949','B8L2')]
    for panel,axis in contrasts:
        f=fits[(fits.panel==panel)&(fits.axis==axis)].set_index(['fold','worker_id'])
        labels=[]
        for r in edges.itertuples():
            keys=[(r.building_id,r.removed),(r.building_id,r.added)]
            if all(k in f.index and f.loc[k].supported and f.loc[k].label!='unclassified' for k in keys):
                labels.append('same_class' if f.loc[keys[0]].label==f.loc[keys[1]].label else 'cross_class')
            else:labels.append('unclassified')
        edges[panel+'_'+axis+'_swap']=labels
    csv('replacement_pairs.csv',edges)
    summary=[]
    for a,b,label in [(0,1,'metric_only_historical931'),(3,4,'metric_only_current949'),(2,4,'new_score_coverage')]:
        ca='_'.join(contrasts[a])+'_swap';cb='_'.join(contrasts[b])+'_swap'
        summary.append(dict(comparison=label,pairs=len(edges),changed=int(edges[ca].ne(edges[cb]).sum()),
            primary_pairs=int(edges.primary_attempt_eligible.sum()),
            changed_primary=int((edges[ca].ne(edges[cb])&edges.primary_attempt_eligible).sum())))
    csv('replacement_label_sensitivity.csv',summary)
    panel=pd.read_csv(OUT/'current_quality_panel.csv')
    coverage=panel.groupby(['worker_id','difficulty_class']).agg(records=('object_id','size'),images=('image_id','nunique'),
        buildings=('building_id','nunique')).reset_index()
    coverage['minimum_coverage']=coverage.images.ge(6)&coverage.buildings.ge(3)
    csv('conditional_coverage.csv',coverage)
    predictions=pd.read_csv(OUT/'predictions.csv')
    matched_predictions=[]
    for (condition,building),p in predictions[predictions.panel.str.startswith('condition_')].groupby(['panel','building_id']):
        test=panel[panel.object_id.isin(p.object_id)]
        fit=fits[(fits.panel=='current949')&(fits.axis=='B8L2')&(fits.fold==building)]
        general=prediction_rows(test,fit,'B8L2')
        paired=p[['object_id','target','baseline_sqerr','continuous_sqerr']].merge(
            general[['object_id','target','continuous_sqerr']],on='object_id',suffixes=('_condition','_general'),validate='one_to_one')
        assert len(paired)==len(p) and np.allclose(paired.target_condition,paired.target_general)
        paired['condition'],paired['building_id']=condition,building
        matched_predictions.append(paired)
    matched=pd.concat(matched_predictions,ignore_index=True)
    csv('condition_general_matched_predictions.csv',matched)
    comparison=[]
    for condition,d in matched.groupby('condition'):
        by=d.groupby('building_id')[['baseline_sqerr','continuous_sqerr_condition','continuous_sqerr_general']].mean()
        comparison.append(dict(condition=condition,rows=len(d),buildings=len(by),
            condition_reduction=1-by.continuous_sqerr_condition.mean()/by.baseline_sqerr.mean(),
            general_reduction=1-by.continuous_sqerr_general.mean()/by.baseline_sqerr.mean(),
            condition_better_buildings=int((by.continuous_sqerr_condition<by.continuous_sqerr_general).sum())))
    csv('condition_general_comparison.csv',comparison)
    fold=fits[(fits.panel=='current949')&(fits.axis=='B8L2')&fits.fold.ne('full_descriptive')]
    boundary=fold.groupby('worker_id').agg(min_effect=('effect','min'),max_effect=('effect','max'),supported_folds=('supported','sum')).reset_index()
    boundary['sign_crosses_zero']=boundary.min_effect.lt(0)&boundary.max_effect.gt(0)
    csv('boundary_workers.csv',boundary)
    full=fits[fits.fold.eq('full_descriptive') & fits.supported]
    q=full[(full.panel=='current949')&(full.axis=='B8L2')][['worker_id','effect','label']]
    for tname in ['T_source','T_target']:
        t=full[full.panel.eq(tname)][['worker_id','effect','label']]
        labels=q.merge(t,on='worker_id',how='left',suffixes=('_Q','_T'))
        labels['QT_label']=labels.label_Q+'|'+labels.label_T
        csv(tname+'_candidate_labels.csv',labels)
    perf=pd.read_csv(OUT/'prediction_performance.csv')
    team=pd.read_csv(OUT/'team_scores.csv')
    bases=pd.read_csv(OUT/'fixed_base_associations.csv')
    b=bases[bases.primary & bases.outcome.eq('B8L2')]
    matched=pd.read_csv(OUT/'matched_base_comparisons.csv')
    m=matched[matched.primary & matched.k.eq(8)&matched.axis.eq('B8L2')]
    byimage=m.groupby('image').floor_cross_minus_same.mean()
    save(OUT/'RESULTS.json',dict(performance=perf.to_dict('records'),
        boundary_workers=boundary.loc[boundary.sign_crosses_zero,'worker_id'].tolist(),
        team_counts=dict(attempts=len(team),numeric=int(team.B8L2.notna().sum()),primary_attempts=int(team.primary_attempt_eligible.sum()),
            primary_numeric=int(team.primary_comparison_eligible.sum()),old_numeric=int(team.old_B8L2.notna().sum())),
        fixed_eight_person_bases=dict(primary_bases=len(b),images=b.image.nunique(),positive_class_gap=int(b.class_gap.gt(0).sum()),
            negative_class_gap=int(b.class_gap.lt(0).sum()),attempted_entrants=int(b.attempted_entrants.sum()),evaluable_entrants=int(b.evaluable_entrants.sum()),
            cross_class_larger_floor_change_bases=int(m.floor_cross_minus_same.gt(0).sum()),comparable_bases=len(m),
            cross_class_larger_floor_change_images=int(byimage.gt(0).sum()),comparable_images=len(byimage)),
        distinct_statistical_units='images/buildings; overlapping pairs are not independent replicates',
        S_B_status='historical measured axes retained and associated; current correctness and same-reference B8L2 gain not certified'))


def validate_ordinary_bridge(old, current):
    keys=['object_id','worker_id','image_id','condition','reference_id','reference_version',
          'input_version','B8L2_version','building_id']
    values=['B8L2','WQ','IoU3D100',*COMPONENTS,'source_active_time_seconds','target_matched_time_seconds']
    if not old.object_id.is_unique or not current.object_id.is_unique or set(old.object_id)!=set(current.object_id):
        raise ValueError('ordinary membership changed; explicit new fit required')
    a=old.set_index('object_id').sort_index();b=current.set_index('object_id').sort_index()
    if not a[keys[1:]].equals(b[keys[1:]]):
        raise ValueError('ordinary identity/reference changed; explicit new fit required')
    for col in values:
        if not np.allclose(a[col].to_numpy(dtype=float),b[col].to_numpy(dtype=float),rtol=0,atol=1e-8,equal_nan=True):
            raise ValueError('ordinary values changed: '+col)
    bridge=b[keys[1:]].copy()
    bridge['B8L2_delta']=b.B8L2-a.B8L2
    bridge['ordinary_model_reused']=True
    return bridge.reset_index()


def doorway_training_rows(bound):
    return bound[bound.quality_use.eq('doorway_quality') & bound.quality_usable & bound.is_doorway
        & ~bound.is_oos & bound.condition.eq('manual') & ~bound.admission_original_holdout].copy()


def run_usage_update():
    source=ROOT/'research/statistics/b8l2_usage_v6_20261016'
    destination=OUT/'usage_v2'
    destination.mkdir(exist_ok=True)
    manifest=read(source/'CROSS_MODULE_INPUTS.json')
    assert manifest['usage_version']=='b8l2_scene_usage_v6_20261016_v2'
    assert manifest['input_version']=='b8l2_shared_v6_20261016_v1' and manifest['score_version']=='WQ-B8L2-20261015'
    def write(name,frame):csv(name,frame,directory=destination)
    ledger=pd.read_csv(source/'calculation_ledger.csv')
    assert ledger.object_id.is_unique and len(ledger)==3152
    assert not ledger.loc[ledger.is_oos,'quality_usable'].any()
    assert ledger.loc[ledger.is_oos,['B8L2','WQ','IoU3D100']].isna().all().all()
    gates=read(OUT/'admission_snapshot.json')
    bound=bind_admission(ledger,gates)
    old=pd.read_csv(OUT/'current_quality_panel.csv')
    ordinary=bound[bound.profile_allowed & bound.quality_usable]
    bridge=validate_ordinary_bridge(old,ordinary)
    write('ordinary949_bridge.csv',bridge)
    time_bridges=[]
    for name,column in [('T_source','source_active_time_seconds'),('T_target','target_matched_time_seconds')]:
        prior=pd.read_csv(OUT/(name+'_panel.csv')).set_index('object_id')
        latest=bound.set_index('object_id').loc[prior.index]
        identity=['worker_id','image_id','condition','building_id','time_source','time_source_file','time_rule_version']
        if name=='T_target':identity+=['reference_id','reference_version']
        assert prior[identity].fillna('').equals(latest[identity].fillna('')),'frozen time identity/source changed'
        assert np.allclose(prior[column],latest[column],rtol=0,atol=1e-8,equal_nan=True),'frozen time values changed'
        d=prior[['worker_id','image_id','condition']].copy()
        d['panel'],d['seconds_delta'],d['model_reused']=name,latest[column]-prior[column],True
        time_bridges.append(d.reset_index())
    write('time_profile_bridge.csv',pd.concat(time_bridges,ignore_index=True))
    ordinary_hold=bound[bound.quality_use.eq('ordinary_primary') & bound.condition.eq('manual') & bound.admission_original_holdout]
    door=bound[bound.quality_use.eq('doorway_quality') & bound.quality_usable].copy()
    assert door.is_doorway.all() and not door.is_oos.any() and door.condition.eq('manual').all()
    assert door.reference_full_available.all() and door.target_binding_unique.all() and door.full_input_available.all()
    assert set(door.object_id).isdisjoint(ordinary_hold.object_id)
    door['context_key']=door[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    train=doorway_training_rows(door)
    write('doorway_records.csv',door)
    write('doorway_nonholdout_panel.csv',train)
    fits,preds=profile_panel(train,'doorway_separate',['B8L2','WQ','IoU3D100'])
    write('doorway_fold_profiles.csv',fits);write('doorway_profiles.csv',fits[fits.fold.eq('full_descriptive')])
    predkeys=['object_id','worker_id','building_id','context_key','axis','panel','comparison','target','label',
              'continuous_prediction','class_prediction','baseline_sqerr','continuous_sqerr','class_sqerr']
    write('doorway_predictions.csv',preds[predkeys]);write('doorway_prediction_performance.csv',performance(preds))
    # Existing ordinary fits predict the new special observations without fitting on doorways.
    ordinary_fits=pd.read_csv(OUT/'fold_profiles.csv')
    ordinary_fits=ordinary_fits[(ordinary_fits.panel=='current949') & ordinary_fits.axis.eq('B8L2')]
    general_predictions=[];paired_predictions=[]
    for building,test in train.groupby('building_id'):
        fit=ordinary_fits[ordinary_fits.fold.eq(building)]
        if fit.empty:
            assert building not in set(old.building_id),'missing existing ordinary target-building fit'
            fit=ordinary_fits[ordinary_fits.fold.eq('full_descriptive')]
        general=prediction_rows(test,fit,'B8L2')
        general['panel'],general['axis'],general['comparison']='ordinary_to_doorway','B8L2','Q_only'
        general_predictions.append(general)
        conditional=preds[preds.building_id.eq(building)&preds.axis.eq('B8L2')]
        if conditional.empty:continue
        common=prediction_rows(test[test.object_id.isin(conditional.object_id)],fit,'B8L2')
        paired=conditional[['object_id','target','baseline_sqerr','continuous_sqerr']].merge(
            common[['object_id','target','continuous_sqerr']],on='object_id',suffixes=('_doorway','_ordinary'),validate='one_to_one')
        assert len(paired)==len(conditional) and np.allclose(paired.target_doorway,paired.target_ordinary)
        paired['building_id']=building;paired_predictions.append(paired)
    general=pd.concat(general_predictions,ignore_index=True)
    write('ordinary_to_doorway_predictions.csv',general[predkeys])
    write('ordinary_to_doorway_performance.csv',performance(general))
    paired=pd.concat(paired_predictions,ignore_index=True) if paired_predictions else pd.DataFrame()
    write('doorway_ordinary_matched_predictions.csv',paired)
    compare={}
    if not paired.empty:
        by=paired.groupby('building_id')[['baseline_sqerr','continuous_sqerr_doorway','continuous_sqerr_ordinary']].mean()
        compare=dict(rows=len(paired),buildings=len(by),
            doorway_reduction=1-by.continuous_sqerr_doorway.mean()/by.baseline_sqerr.mean(),
            ordinary_reduction=1-by.continuous_sqerr_ordinary.mean()/by.baseline_sqerr.mean(),
            doorway_better_buildings=int((by.continuous_sqerr_doorway<by.continuous_sqerr_ordinary).sum()))
    train_counts=train.groupby('worker_id').agg(training_records=('object_id','size'),training_images=('image_id','nunique'),training_buildings=('building_id','nunique'))
    coverage=door.groupby('worker_id').agg(records=('object_id','size'),images=('image_id','nunique'),buildings=('building_id','nunique'),
        original_holdout_records=('admission_original_holdout','sum')).join(train_counts).reset_index()
    coverage['minimum_coverage']=coverage.training_images.ge(6)&coverage.training_buildings.ge(3)
    coverage=coverage.merge(fits[fits.fold.eq('full_descriptive')&fits.axis.eq('B8L2')][['worker_id','supported']],on='worker_id',validate='one_to_one')
    write('doorway_worker_coverage.csv',coverage)
    image_stats=door.groupby(['image_code','condition','reference_id','doorway_status']).agg(records=('object_id','size'),
        workers=('worker_id','nunique'),holdout_records=('admission_original_holdout','sum'),B8L2_mean=('B8L2','mean'),
        B8L2_median=('B8L2','median'),B8L2_sd=('B8L2','std'),IoU3D100_mean=('IoU3D100','mean')).reset_index()
    write('doorway_image_descriptions.csv',image_stats)
    cols=['object_id','image_id','image_code','worker_id','condition','scene','scene_bucket','is_doorway','is_oos',
        'quality_use','quality_usable','calculation_status','full_score_state','input_geometry_status','input_geometry_reasons',
        'measurement_reasons','full_input_available','floor_input_available','reference_full_available','target_binding_unique',
        'primary_reason','quality_exclusion_reasons','purpose_bypass','source_active_time_seconds','target_matched_time_seconds',
        'admission_original_holdout','B8L2','diagnostic_B8L2','input_version','usage_version','B8L2_version']
    audit=bound[cols].copy()
    audit['ordinary_Q_profile']=audit.object_id.isin(old.object_id)
    audit['doorway_quality_evidence']=audit.object_id.isin(door.object_id)
    audit['doorway_profile_training']=audit.object_id.isin(train.object_id)
    write('personnel_usage_ledger.csv',audit)
    workers=pd.read_csv(source/'worker_usage_summary.csv')
    assert workers.worker_id.nunique()==27 and workers.n_submissions.sum()==len(ledger)
    for col in ['ordinary_Q_profile','doorway_quality_evidence','doorway_profile_training']:
        workers=workers.merge(audit.groupby('worker_id')[col].sum().rename('n_'+col).reset_index(),on='worker_id',validate='one_to_one')
    workers['n_outside_ordinary_Q_profile']=workers.n_submissions-workers.n_ordinary_Q_profile
    workers['n_not_quality_usable']=workers.n_submissions-workers.n_quality_usable
    write('worker_usage_summary.csv',workers)
    for name in ['worker_primary_reasons.csv','worker_reason_hits.csv','worker_scene_usage.csv','scene_usage.csv']:
        write(name,pd.read_csv(source/name))
    changes=pd.read_csv(source/'member_changes.csv')
    changes=changes.merge(audit[['object_id','ordinary_Q_profile','doorway_quality_evidence','doorway_profile_training',
        'quality_use','admission_original_holdout']],on='object_id',validate='one_to_one')
    write('membership_bridge.csv',changes)
    # Reuse the completed ordinary outcomes verbatim; this update adds no team geometry or score.
    summary=dict(usage_version=manifest['usage_version'],input_version=manifest['input_version'],ordinary_rows=len(old),
        ordinary_members_references_values_unchanged=True,ordinary_max_B8L2_delta=float(bridge.B8L2_delta.abs().max()),
        ordinary_model_refitted=False,time_profile_sources_members_values_unchanged=True,
        ordinary_original_holdout_records=len(ordinary_hold),
        doorway_rows=len(door),doorway_images=door.image_id.nunique(),doorway_buildings=door.building_id.nunique(),doorway_workers=door.worker_id.nunique(),
        doorway_original_holdout_records=int(door.admission_original_holdout.sum()),
        doorway_training_rows=len(train),doorway_training_images=train.image_id.nunique(),doorway_training_buildings=train.building_id.nunique(),
        doorway_supported_workers=int(coverage.supported.sum()),
        doorway_and_ordinary_holdout_id_intersection=len(set(door.object_id)&set(ordinary_hold.object_id)),
        doorway_vs_ordinary_same_rows=compare,workers=len(workers),inventory=len(ledger),
        calculation_counts=ledger.calculation_status.value_counts().to_dict(),geometry_counts=ledger.input_geometry_status.value_counts().to_dict(),
        quality_usable=int(ledger.quality_usable.sum()),OOS_records=int(ledger.is_oos.sum()),OOS_quality_usable=int(ledger.loc[ledger.is_oos,'quality_usable'].sum()),
        previous_ordinary_results=read(OUT/'RESULTS.json'),fusion_rescored=False,S_B_relabelled=False)
    save(destination/'RESULTS.json',summary)
    save(destination/'INPUTS.json',dict(shared_delivery=manifest,admission_snapshot='../admission_snapshot.json',
        ordinary_fits='../fold_profiles.csv',ordinary_results='../RESULTS.json',
        special_model='same task-adjusted effect and 6-task/3-building support; original holdout excluded',
        exclusions='shared primary reasons exclusive; reason hits overlap; never add them'))
    save(destination/'FIELD_CONTRACT.json',dict(usage_version=manifest['usage_version'],
        tables={p.name:dict(rows=len(pd.read_csv(p)),columns=pd.read_csv(p,nrows=0).columns.tolist()) for p in destination.glob('*.csv')},
        diagnostic_B8L2='numeric only; OOS forbidden in quality profiles/evaluation/benefits',
        doorway='quality evidence includes held observations; profile_training excludes original holdout',
        missing='blank never zero; input geometry state separate from mutually exclusive calculation_status',
        ordinary_bridge='identity/reference equality and metric/time equality within absolute 1e-8; existing fits reused'))
    save(OUT/'SPECIAL_DEPENDENCIES.json',dict(status='resolved_by_shared_usage_v2',usage_version=manifest['usage_version'],
        report='usage_v2/README.md',ledger='usage_v2/personnel_usage_ledger.csv',
        remaining='coverage limits and unresolved individual targets/references remain recorded; no missing common delivery'))
    inputs=read(OUT/'INPUTS.json')
    inputs.update(latest_usage_version=manifest['usage_version'],latest_usage_delivery=str((source/'CROSS_MODULE_INPUTS.json').relative_to(ROOT)),
        usage_update='usage_v2/INPUTS.json',ordinary_model_preserved=True)
    save(OUT/'INPUTS.json',inputs)
    checks=read(OUT/'CHECKS.json')
    checks.update(latest_usage_version=manifest['usage_version'],ordinary949_bridge_verified=True,
        ordinary_model_refitted=False,doorway_records=len(door),doorway_nonholdout_records=len(train),all_worker_ledger_rows=len(ledger))
    save(OUT/'CHECKS.json',checks)
    contract=read(OUT/'FIELD_CONTRACT.json')
    contract.update(latest_usage_version=manifest['usage_version'],usage_tables='usage_v2/FIELD_CONTRACT.json',
        historical_root_tables='v1 phase preserved; latest exclusion and computability ledger in usage_v2')
    save(OUT/'FIELD_CONTRACT.json',contract)


def main():
    current,gates=freeze_inputs()
    inventory_coverage(current,gates)
    frozen_fusion=OUT/'fusion_snapshot.json'
    if not frozen_fusion.exists():save(frozen_fusion,read(FUSION/'input_snapshot.json'))
    snapshot=read(frozen_fusion)
    assert snapshot['difficulty_version']==read(SHARED/'CROSS_MODULE_INPUTS.json')['difficulty_version']
    buildings=[m['building_id'] for im in snapshot['images'] for m in im['members']]
    with scoring_engine(SHARED/'inputs/measurement_engine.zip',SHARED/'inputs/working_models.py') as (engine,models):
        fits=run_profiles(current,gates,models,buildings)
        print('profiles complete',flush=True)
        teams=team_scores(engine,models,snapshot)
        replacements(teams,fits)
        diagnostic_summaries(fits)
    save(OUT/'CHECKS.json',dict(current_profile_rows=len(current),current_profile_workers=current.worker_id.nunique(),
        current_profile_images=current.image_id.nunique(),holdouts_excluded=True,
        frozen_formula_replay=True,real_members_and_single_replacements_verified=True,
        same_reference_old_WQ_parity=True,team_rows=len(teams),fusion_rerun=False,global_files_edited=False))
    save(OUT/'FIELD_CONTRACT.json',dict(version='worker_b8l2_20261016_v1',
        inputs='INPUTS.json and frozen admission/fusion snapshots; shared b8l2_shared_v6_20261016_v1',
        missing='null/blank; never zero; no complete score from floor upper bound',
        profile='effect is task-adjusted relative performance; signs descriptive; unsupported/zero unclassified',
        prediction='leave entire target building out; same-context relative targets; building_equal_reduction is ratio of building-mean MSEs',
        QT='training Q-sign by time-sign; at least two supported people per training cell; Q-only comparators use same evaluable rows',
        time='log1p(seconds); T_source actual collection time, T_target preexisting audited same-target subset; neither substitutes lead_time',
        primary_attempt_eligible='current pool/member/target gates without successful-output requirement',
        primary_comparison_eligible='primary attempt and available full B8L2; excluded failures remain in attempted denominator',
        auxiliary='S/B columns retain historical source definitions; B_legacy_gain is OSPA30 not B8L2',
        tables={p.name:dict(rows=len(pd.read_csv(p)),columns=pd.read_csv(p,nrows=0).columns.tolist()) for p in sorted(OUT.glob('*.csv'))}))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--usage-only',action='store_true',help='Reuse ordinary fits and add the published usage-v2 doorway/ledger update')
    args=parser.parse_args()
    if not args.usage_only:main()
    run_usage_update()
