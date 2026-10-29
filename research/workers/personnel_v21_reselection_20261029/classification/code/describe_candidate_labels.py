#!/usr/bin/env python3
from pathlib import Path
import csv,hashlib,json
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parent
def save(d,name):d.to_csv(ROOT/name,index=False,encoding='utf-8-sig')
def transitions(a,b,label):
    sums=[];links=[];pairs=[]
    common=sorted(set(a.method)&set(b.method))
    for method in common:
        aa=a[a.method==method];bb=b[b.method==method]
        for fold in sorted(set(aa.heldout_building)&set(bb.heldout_building)):
            x=aa[aa.heldout_building==fold][['worker_id','class_id','known']].merge(bb[bb.heldout_building==fold][['worker_id','class_id','known']],on='worker_id',suffixes=('_old','_new'),how='outer')
            g=x[x.known_old.eq(True)&x.known_new.eq(True)]
            tab=pd.crosstab(g.class_id_old,g.class_id_new)
            if tab.empty:continue
            ii,jj=linear_sum_assignment(-tab.to_numpy())
            mapping={tab.columns[j]:tab.index[i] for i,j in zip(ii,jj)}
            x['new_class_mapped_for_overlap_only']=x.class_id_new.map(mapping)
            x['overlap_changed']=np.where(x.known_old.eq(True)&x.known_new.eq(True),x.class_id_old.ne(x.new_class_mapped_for_overlap_only),np.nan)
            x['method']=method;x['heldout_building']=fold;x['comparison']=label
            x['interpretation']='overlap diagnostic only; native fold labels remain experimental input'
            links.append(x)
            for oldc in tab.index:
                for newc in tab.columns:
                    pairs.append({'comparison':label,'method':method,'heldout_building':fold,'old_class_id':oldc,'new_class_id':newc,'members_n':int(tab.loc[oldc,newc]),'members':'|'.join(g[(g.class_id_old==oldc)&(g.class_id_new==newc)].worker_id),'mapped_pair':mapping.get(newc)==oldc})
            sums.append({'comparison':label,'method':method,'heldout_building':fold,'both_known':len(g),'old_known':int(x.known_old.eq(True).sum()),'new_known':int(x.known_new.eq(True).sum()),'ARI':adjusted_rand_score(g.class_id_old,g.class_id_new),'overlap_changed_n':int(x.overlap_changed.sum()),'new_to_old_overlap_mapping':json.dumps(mapping)})
    return pd.DataFrame(sums),pd.concat(links,ignore_index=True),pd.DataFrame(pairs)
def main():
    progress=json.loads((ROOT/'PROGRESS.json').read_text())
    assert progress['status']=='labels_frozen_complete'
    new=pd.read_csv(ROOT/'NEW_LABELS_ALL_LOBO.csv.gz')
    base=pd.read_csv(ROOT/'BASE_CURRENT_LABELS_ALL_LOBO.csv.gz')
    oldroot=WORK/'prior_v2/research/workers/personnel_exchange_discrimination_20261025'
    old=pd.concat([pd.read_csv(oldroot/'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz'),pd.read_csv(oldroot/'reverse/REVERSE_LABELS_ALL_LOBO.csv.gz')],ignore_index=True)
    sums,links,pairs=transitions(old,base,'same_method_v2_to_official_v21')
    save(sums,'OLD_V2_TO_CURRENT_V21_LABEL_CHANGE_SUMMARY.csv')
    save(links,'OLD_V2_TO_CURRENT_V21_WORKER_LABEL_TRANSITIONS.csv.gz')
    save(pairs,'OLD_V2_TO_CURRENT_V21_CLASS_OVERLAPS.csv.gz')
    renamed=new.copy()
    renamed['actual_new_method']=renamed.method
    renamed['method']=renamed.method.str.replace('TARGET_DSTRUCT','DSTRUCT',regex=False).str.replace('OPPSTRUCT','DSTRUCT',regex=False).str.replace('OPPGEOM','DBOUNDARY',regex=False).str.replace('OPPJOINT','DJOINT',regex=False)
    ns=[];nl=[];npair=[]
    for family in ['TARGET_DSTRUCT','OPPSTRUCT','OPPGEOM','OPPJOINT']:
        part=renamed[renamed.actual_new_method.str.startswith(family+'_')]
        ss,ll,pp=transitions(base,part,'official_v21_to_'+family)
        ns.append(ss);nl.append(ll);npair.append(pp)
    save(pd.concat(ns,ignore_index=True),'NEW_TO_OFFICIAL_BASELINE_OVERLAP_SUMMARY.csv')
    save(pd.concat(nl,ignore_index=True),'NEW_TO_OFFICIAL_BASELINE_WORKER_TRANSITIONS.csv.gz')
    save(pd.concat(npair,ignore_index=True),'NEW_TO_OFFICIAL_BASELINE_CLASS_OVERLAPS.csv.gz')
    hist=pd.read_csv(ROOT/'HISTORY_FEATURES_ALL_LOBO.csv.gz')
    centers=pd.read_csv(ROOT/'NEW_CLASS_CENTERS_ALL_LOBO.csv.gz')
    desc=centers[centers.heldout_building=='ALL'].copy()
    def role(r):
        a=[]
        if r.m_challenge_turn_n>.3:a.append('复杂结构机会下较多非冗余转折')
        elif r.m_challenge_turn_n<-.5:a.append('复杂结构机会下较多简化')
        else:a.append('接近常规结构表达')
        if r.m_all_near_straight_nodes_5deg>.05:a.append('近共线冗余偏多')
        if r.m_all_matched_bottom_bias_deg>.25:a.append('底界相对同伴偏下')
        if r.m_all_matched_top_bias_deg<-.2:a.append('顶界相对同伴偏上')
        if r.m_all_log_area_ratio<-.03:a.append('底面范围相对收缩')
        if r.m_all_B8L2>5:a.append('历史Q相对较高')
        if r.m_all_log_time>.04:a.append('来源内记录时间较长')
        elif r.m_all_log_time<-.04:a.append('来源内记录时间较短')
        return '；'.join(a)
    desc['descriptive_role']=desc.apply(role,axis=1)
    desc['usage_status']='descriptive candidate; team usefulness determined by global frozen-label comparison'
    cols=['method','family','class_id','workers','members','descriptive_role','m_all_images','m_all_buildings','m_all_targets','m_challenge_images','m_hard_images','m_easy_images','m_all_turn_n','m_challenge_turn_n','m_opp_slope_turn_n','m_all_short_turn_edges','m_all_near_straight_nodes_5deg','m_all_matched_bottom_bias_deg','m_all_matched_top_bias_deg','m_all_log_area_ratio','m_all_log_height','m_all_B8L2','m_all_B8L2_p20','m_all_log_time','usage_status']
    save(desc[cols],'NEW_CLASS_DEFINITIONS_ALL.csv')
    raw=pd.read_csv(ROOT/'RAW_TARGET_RESPONSE_RECORDS.csv.gz')
    support=raw.groupby(['scope','condition','layer','history_eligible'],dropna=False).agg(records=('object_id','size'),pools=('pool_id','nunique'),images=('image_id','nunique'),buildings=('building','nunique'),workers=('worker_id','nunique'),graded_records=('official_difficulty','count')).reset_index()
    save(support,'NEW_CANDIDATE_INPUT_SUPPORT.csv')
    # Per-worker sources and unknowns remain distinct from formal team qualification.
    save(new[new.heldout_building=='ALL'][['method','worker_id','origin','class_id','known','missing_reason','input_conditions','history_scope']],'NEW_PERSONNEL_LABELS_AND_MISSING_ALL.csv')
    save(hist[hist.heldout_building=='ALL'],'NEW_PERSONNEL_HISTORY_ALL.csv')
    summary={'data':'v2.1','new_methods':new.method.nunique(),'folds':new.heldout_building.nunique(),'label_rows':len(new),'new_known_ALL_by_method':new[(new.heldout_building=='ALL')&new.known].groupby('method').size().to_dict(),'raw_records':len(raw),'raw_target_pools':raw.pool_id.nunique(),'ordinary_history_records':int(raw.history_eligible.sum()),'other_target_history_records':int((raw.history_eligible&raw.scope.eq('other_admitted')).sum()),'history_has_no_target_grade_imputation':bool(raw[raw.scope.eq('other_admitted')].official_difficulty.isna().all()),'all_feature_formula_max_difference':float(pd.read_csv(ROOT/'RAW_FEATURE_CORRESPONDENCE_CHECK.csv').abs_difference.max())}
    (ROOT/'NEW_CANDIDATE_BUILD_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()

