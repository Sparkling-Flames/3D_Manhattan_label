#!/usr/bin/env python3
"""Persist inventory, definitions, selection frequencies and source references.

No labels are fitted or changed here. Inventory reconciliation uses original
records, not a claim in an earlier report. All outputs remain separate from
formal team eligibility.
"""
import gzip,hashlib,json,platform
from importlib.metadata import version
import numpy as np
import pandas as pd
import discover_behavior_classes as b

NAMES={
 ('V3_BEHAVIOR','manual','M1.1'):('复杂结构明显简化','复杂机会中非近共线转折和短转折较少；简单图差别很小。'),
 ('V3_BEHAVIOR','manual','M2.1'):('常规转折表达','相对同图多数人员接近或略简化；成员多，仍保留成员连续差异。'),
 ('V3_BEHAVIOR','manual','M3.1'):('较多转折与短细节表达','主要在复杂结构机会中表达更多非近共线转折与短边。'),
 ('V3_BEHAVIOR','semi','S1.1'):('偏简化终稿','常规/较少表达粗类中进一步分出较少转折的终稿。'),
 ('V3_BEHAVIOR','semi','S1.2'):('常规终稿','相对同图多数人员接近，短转折与近共线点较少。'),
 ('V3_BEHAVIOR','semi','S2.1'):('近共线分段较多终稿','多点主要来自近共线分段，而非更多明显转折；旧来源支持较强。'),
 ('V3_BEHAVIOR','semi','S3.1'):('较多转折终稿','更多非近共线转折及短转折，不能与近共线点组混为多点组。'),
 ('V3_JOINT_QT','manual','J1.1'):('较快、适度转折','记录时间较短，复杂机会下适度保留转折；历史Q与J2/J3接近。'),
 ('V3_JOINT_QT','manual','J2.1'):('常规时间、略简化','记录时间接近本来源常规值，复杂机会中略少转折。'),
 ('V3_JOINT_QT','manual','J3.1'):('复杂结构明显简化','与结构M1.1同6人；Q接近J1/J2但结构表达不同。'),
 ('V3_JOINT_QT','manual','J4.1'):('较慢、常规转折','记录时间较长，转折表达接近同图常规值。'),
 ('V3_JOINT_QT','manual','J5.1'):('较高历史Q、较多细节','历史Q较高，复杂结构机会下转折与短边表达较强。'),
 ('V3_JOINT_QT','semi','K1.1'):('较低历史Q、适度转折','自己的Semi终稿历史Q较低，时间接近常规，转折表达适度。'),
 ('V3_JOINT_QT','semi','K2.1'):('较低历史Q、常规转折','自己的Semi历史Q略低，时间接近常规、短转折较少。'),
 ('V3_JOINT_QT','semi','K3.1'):('较快、较多转折','Semi记录时间较短，同时终稿转折表达较多。'),
 ('V3_JOINT_QT','semi','K4.1'):('较慢、常规或偏少转折','Semi记录时间较长，转折表达接近常规或较少。'),
 ('V3_JOINT_QT','semi','K5.1'):('较高历史Q、较快常规表达','Semi历史Q较高，记录时间较短，转折接近常规。'),
}

def main():
    x=b.load();l=pd.read_csv(b.HERE/'ALL_METHOD_LABELS_ALL_DATA.csv')
    source=b.REPO/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    rr=json.load(gzip.open(source,'rt'))['records']
    nonoos={r['object_id'] for r in rr if r['is_oos'] is False}
    assert nonoos==set(x.object_id),('inventory mismatch',len(nonoos-set(x.object_id)),len(set(x.object_id)-nonoos))
    profile=pd.read_csv(b.PROFILE)
    x=x.merge(profile[['object_id','image_quality_gate','quality_exclusion_reasons']],on='object_id',validate='one_to_one')
    x['gt_error_hold']=x.quality_exclusion_reasons.map(lambda s:any('gt_error' in z or 'gt_substantive_error' in z for z in json.loads(s)))
    x['fit_record']=x.behavior_usable & x.layer.eq('ordinary')
    groups=[]
    for condition in ['ALL','manual','semi']:
        z=x if condition=='ALL' else x[x.condition.eq(condition)]
        slices={'inventory':z,'ordinary':z[z.layer.eq('ordinary')],'doorway':z[z.layer.eq('doorway')],
            'special_conditional':z[z.layer.eq('special_conditional')],'GT_error_hold':z[z.gt_error_hold],
            'excluded_by_review':z[z.cleaning_disposition.eq('excluded_by_review')],
            'historical_not_accepted':z[z.cleaning_disposition.eq('historical_not_accepted')],
            'retained_pending':z[z.cleaning_disposition.eq('retained_pending')]}
        for name,a in slices.items():
            groups.append(dict(condition=condition,slice=name,records=len(a),people=a.worker_id.nunique(),
                images=a.image_id.nunique(),buildings=a.building_id.nunique(),behavior_usable=int(a.behavior_usable.sum()),
                fit_records=int(a.fit_record.sum()),fit_images=a.loc[a.fit_record,'image_id'].nunique(),
                quality_scored_records=int(a.B8L2.notna().sum()),independent_vote_eligible=int(a.independent_vote_eligible.sum())))
    b.save(pd.DataFrame(groups),'RESEARCH_INPUT_INVENTORY.csv')
    b.js('INVENTORY_RECONCILIATION.json',dict(original_records=len(rr),original_nonOOS=len(nonoos),
        derived_inventory=len(x),missing_nonOOS=0,extra_nonOOS=0,source=str(source.relative_to(b.REPO)),
        inventory_qualified_rows=int(x.B8L2.notna().sum()),fit_rows=int(x.fit_record.sum()),
        rule='ordinary comparable original expression only for classification; GT-held behavior may fit, quality remains gated; excluded responses never regain voting eligibility'))
    defs=[]
    for (m,c,co,fi),g in l.groupby(['method','condition','coarse_label','fine_label']):
        known=bool(g.known.all());name,desc=NAMES.get((m,c,fi),('证据不足','保留缺失原因；不作零值或常规类。'))
        defs.append(dict(method=m,condition=c,coarse_label=co,fine_label=fi,name_zh=name,definition_zh=desc,
            known=known,members='|'.join(g.worker_id),n_members=len(g),selected_family=g.selected_family.iloc[0],
            coarse_k=int(g.coarse_k.iloc[0]),fine_k=int(g.fine_k.iloc[0]),
            independent_fine_level=bool(g.coarse_k.iloc[0]<g.fine_k.iloc[0]),
            minimum_history_images=int(g.n_images.min()),minimum_history_buildings=int(g.n_buildings.min()),
            total_history_records=int(g.n_records.sum()),missing_reasons='|'.join(sorted(g.missing_reason.dropna().unique()))))
    definitions=pd.DataFrame(defs)
    b.save(definitions,'CLASS_DEFINITIONS.csv')
    persons=pd.read_csv(b.HERE/'PERSONNEL_LABELS_EXPLAINED.csv').merge(
        definitions[['method','condition','coarse_label','fine_label','name_zh','definition_zh','independent_fine_level']],
        on=['method','condition','coarse_label','fine_label'],validate='many_to_one')
    for condition in ['manual','semi']:
        b.save(persons[persons.condition.eq(condition)],condition.upper()+'_LABELS_EXPLAINED.csv')
    stability=[];dist=[]
    for pre,method in [('', 'V3_BEHAVIOR'),('JOINT_','V3_JOINT_QT')]:
        a=pd.read_csv(b.HERE/(pre+'OUTER_LABEL_STABILITY.csv'));a=a[a.condition_has_target]
        for (cond,fam,co,fi),g in a.groupby(['condition','fold_family','fold_coarse_k','fold_fine_k']):
            dist.append(dict(method=method,condition=cond,family=fam,coarse_k=co,fine_k=fi,folds=len(g)))
        for cond,g in a.groupby('condition'):
            stability.append(dict(method=method,condition=cond,outer_buildings=len(g),
                coarse_ari_mean=g.coarse_ari.mean(),fine_ari_mean=g.fine_ari.mean(),
                fine_ari_min=g.fine_ari.min(),fine_ari_max=g.fine_ari.max(),
                workers_min=g.workers.min(),workers_max=g.workers.max()))
    b.save(pd.DataFrame(dist),'OUTER_SELECTION_DISTRIBUTION.csv')
    b.save(pd.DataFrame(stability),'OUTER_STABILITY_SUMMARY.csv')
    old=pd.read_csv(b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/final_labels.csv')
    z=l[l.method.eq('V3_BEHAVIOR')&l.condition.eq('manual')].merge(
        old[old.condition.eq('manual')][['worker_id','coarse_class','fine_class']],on='worker_id',validate='one_to_one')
    cross=[]
    for (co,fi,oldco,oldfi),g in z.groupby(['coarse_label','fine_label','coarse_class','fine_class'],dropna=False):
        cross.append(dict(new_method='V3_BEHAVIOR',condition='manual',new_coarse=co,new_fine=fi,old_coarse=oldco,old_fine=oldfi,
            members=len(g),worker_ids='|'.join(g.worker_id)))
    b.save(pd.DataFrame(cross),'OLD_NEW_MANUAL_CLASS_CROSSWALK.csv')
    # Full observed near-collinear opportunities, independent of whether a
    # particular outer fold still assigned the person to the same class.
    rw=l[(l.method=='V3_BEHAVIOR')&(l.condition=='semi')&(l.fine_label=='S2.1')].worker_id
    a=x[(x.condition=='semi')&x.worker_id.isin(rw)&x.behavior_usable&x.layer.eq('ordinary')]
    ss=[]
    for worker,g in a.groupby('worker_id'):
        non=g[g.near_straight_nodes_5deg.gt(0)]
        ss.append(dict(worker_id=worker,opportunity_images=g.image_id.nunique(),opportunity_buildings=g.building_id.nunique(),
            nonzero_images=non.image_id.nunique(),nonzero_buildings=non.building_id.nunique(),nonzero_records=len(non),
            exact_initialization_records=int(non.semi_exact_initialization.sum()),
            edited_records=int(non.semi_edited.eq(True).sum()),nonzero_objects='|'.join(non.object_id)))
    b.save(pd.DataFrame(ss),'SEMI_REDUNDANCY_SUPPORT.csv')
    b.save(a[a.near_straight_nodes_5deg.gt(0)],'SEMI_REDUNDANCY_VISIBLE_RECORDS.csv')
    inputs=[b.EXPRESSION,b.PROFILE,source,
        b.REPO/'tools/thesis_main/analysis/personnel_marking_patterns_20261020.py',
        b.REPO/'tools/thesis_main/analysis/paired_split_research/study.py',
        b.REPO/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py',
        b.REPO/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz',
        b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/final_labels.csv',
        b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/lobo_labels.csv',
        b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/semi_adopted_lobo_labels.csv']
    b.save(pd.DataFrame([dict(path=str(p.relative_to(b.REPO)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs]),'INPUTS_AND_CHECKSUMS.csv')
    b.js('RUNTIME_VERSIONS.json',dict(python=platform.python_version(),packages={p:version(p) for p in ['numpy','pandas','scipy','scikit-learn']}))
    print('Saved reconciled inventory, class definitions, source checksums and capacity summaries',flush=True)

if __name__=='__main__':main()
