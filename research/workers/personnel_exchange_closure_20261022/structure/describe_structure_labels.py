#!/usr/bin/env python3
"""Readable all-data description and separate actual LOBO experiment roles.

No new labels are fitted. Missing Q/T/difficulty opportunities stay missing.
"""
import pandas as pd
from register_structure import HERE, ROOT, write, save, sha, gs

ALL=ROOT/'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy/ALL_METHOD_LABELS_ALL_DATA.csv'
HIST=ROOT/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz'

def main():
    d=pd.read_csv(ALL,keep_default_na=False)
    d=d[(d.method=='V3_BEHAVIOR')&(d.condition=='manual')].copy()
    hist=pd.read_csv(HIST,keep_default_na=False)
    hist=hist[hist.condition.eq('manual')&hist.heldout_building.eq('ALL')]
    aux=['q_effect','q_absolute_mean','q_absolute_p10','q_downside','t_effect','t_tail','hard_minus_easy','medium_minus_easy',
         'scope_out_effect','scope_gold_n','scope_gold_correct_n','semi_edit_effect','semi_error_nonedit_effect']
    flags=['Q_supported','T_supported','D_supported','scope_supported','semi_edit_supported','semi_error_nonedit_supported']
    aux=[x for x in aux if x in hist];flags=[x for x in flags if x in hist]
    d=d.merge(hist[['worker_id']+aux+flags],on='worker_id',how='left',suffixes=('','_aux'),validate='one_to_one')
    semantics={'M1':'相对简化表达','M2':'常规表达','M3':'较多转折','unknown':'证据不足'}
    d['class_semantics']=d.coarse_label.map(semantics)
    d['label_use']='all_data_description_not_target_evaluation'
    outputs=[write(HERE/'CLASS_LABELS_ALL_DATA_DESCRIPTION.csv',d)]
    rows=[]
    for c,g in d.groupby('coarse_label',sort=True):
        r=dict(raw_class_id=c,semantics=semantics.get(c,c),n_members=len(g),members='|'.join(g.worker_id),
            selected_family='TURN',label_use='all_data_description_not_target_evaluation',class_center_available=c!='unknown')
        for f in ['turn_history','short_history','redundancy_history','area_history','height_history',
                  'simple_turn_history','complex_turn_history','complex_short_history','n_images','n_buildings']:
            x=pd.to_numeric(g[f],errors='coerce')
            if c=='unknown' and f not in ['n_images','n_buildings']:x=pd.Series(float('nan'),index=g.index)
            r[f+'_mean']=x.mean();r[f+'_min']=x.min();r[f+'_max']=x.max()
        for f in aux:
            ff='q_downside_aux' if f=='q_downside' and 'q_downside_aux' in g else f
            flag=('Q_supported' if f.startswith('q_') else 'T_supported' if f.startswith('t_') else 'D_supported' if f in ['hard_minus_easy','medium_minus_easy'] else
                  'scope_supported' if f=='scope_out_effect' else 'semi_edit_supported' if f=='semi_edit_effect' else 'semi_error_nonedit_supported' if f=='semi_error_nonedit_effect' else None)
            x=pd.to_numeric(g[ff],errors='coerce')
            if flag and flag in g:x=x.where(g[flag].astype(str).str.lower().isin(['true','1']))
            r[f+'_mean']=x.mean();r[f+'_known_people']=x.notna().sum()
        rows.append(r)
    outputs.append(write(HERE/'CLASS_DESCRIPTION_CENTERS.csv',rows))
    roles=pd.read_csv(HERE/'CLASS_ROLES_REUSED.csv')
    summary=[]
    for role,g in roles.groupby('role_id'):
        r=dict(training_role=role,folds=len(g),member_count_min=g.n_members.min(),member_count_max=g.n_members.max())
        for f in ['centroid_turn_history','centroid_short_history','centroid_redundancy_history','centroid_area_history','centroid_height_history']:
            r[f+'_min']=g[f].min();r[f+'_median']=g[f].median();r[f+'_max']=g[f].max()
        summary.append(r)
    outputs.append(write(HERE/'LOBO_ROLE_CENTER_RANGE.csv',summary))
    special=[dict(p['meta'],study_status='special_scope_not_in_new_ordinary_n20_experiment',
                  retained='Previous classification and scope-specific studies retained; no eligibility restoration')
             for p in gs.pool_lookup().values() if p['meta']['condition']=='manual' and p['meta']['layer']!='ordinary_manual']
    outputs.append(write(HERE/'SCOPE_NOT_IN_PRIMARY.csv',special))
    save(HERE/'LABEL_DESCRIPTION_COMPLETION.json',dict(all_data_input=str(ALL.relative_to(ROOT)),all_data_sha256=sha(ALL),
        auxiliary_input=str(HIST.relative_to(ROOT)),auxiliary_sha256=sha(HIST),outputs=outputs,
        feature_definition='Raw expression minus same-image/reference peer median, first averaged per training building then equally over buildings; effective turns exclude near-straight <=5 degree nodes; short edges require local turns and relative perimeter <4%.',
        semantics='More/fewer expression is not a correctness judgement; necessary structure, reference-omitted detail, scope, redundancy and error are separated by local evidence.',
        unknown='Missing opportunity is not imputed to zero. Auxiliary domain means require their prior support flag.',
        cross_condition='Semi auxiliary fields are clearly auxiliary histories; all fusion outcomes in this directory are Manual.'))
    print(pd.DataFrame(rows)[['raw_class_id','semantics','n_members','turn_history_mean','short_history_mean','q_effect_mean','t_effect_mean']].to_string(index=False))

if __name__=='__main__':main()
