#!/usr/bin/env python3
"""Readable full-fit personnel table and descriptive summaries of frozen outputs."""
from pathlib import Path
import hashlib,json,re,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'forward'))
from atomic_exports import csv_verified


def main():
    p=HERE/'results';e=HERE/'explanations'
    c=pd.read_csv(p/'all_candidate_classes.csv.gz').fillna({'class_id':'unknown'})
    full=c[c.fold_id.eq('FULL')]
    f=pd.read_csv(HERE.parent/'forward/fold_features.csv.gz')
    f=f[f.fold_id.eq('FULL') & f.metric.eq('B8L2')]
    f=f[f.inner_group.isna()] if 'inner_group' in f else f
    out=full[full.method_id.eq('reverse_selected')][['worker_id','n_images','n_buildings','n_records','class_id','unknown_reason']].rename(columns={'class_id':'reverse_global_class'})
    for method,domain,name in [('reverse_selected_swap','global','reverse_swap_class'),
                                ('reverse_selected_difficulty','easy','reverse_easy_class'),
                                ('reverse_selected_difficulty','medium','reverse_medium_class'),
                                ('reverse_selected_difficulty','hard','reverse_hard_class')]:
        g=full[full.method_id.eq(method)&full.domain.eq(domain)].set_index('worker_id').class_id
        out[name]=out.worker_id.map(g)
    feature_cols=['person_origin','q_beta','q_abs_mean','q_abs_p10','q_abs_sd','t_source_origin_effect','t_log_residual_tail',
                  'hard_minus_easy','hard_minus_medium','pair_count_effect','pair_count_residual_sd',
                  'semi_old_error_nonedit_effect','semi_new_error_nonedit_effect','scope_out_effect',
                  'individual_review_records','specific_error_candidate_n','legacy_explicit_person_error_n']
    out=out.merge(f[['worker_id']+feature_cols],on='worker_id',validate='one_to_one')
    stability=pd.read_csv(p/'worker_classmate_stability.csv')
    for method,prefix in [('reverse_selected','global'),('reverse_selected_swap','swap')]:
        g=stability[stability.method_id.eq(method)&stability.domain.eq('global')].set_index('worker_id')
        for feature in ['mean_classmate_jaccard','minimum_classmate_jaccard','singleton_empty_comparisons']:
            out[prefix+'_'+feature]=out.worker_id.map(g[feature])
    exports=[csv_verified(out.sort_values('worker_id'),p/'FULL_PERSONNEL_TYPES.csv')]
    selections=pd.read_csv(p/'selected_candidates.csv')
    counts=selections[selections.fold_id.ne('FULL')].groupby(['method_id','selected_candidate']).size().reset_index(name='outer_folds')
    exports.append(csv_verified(counts,p/'SELECTOR_COUNTS.csv'))
    co=pd.read_csv(p/'coassignment_stability.csv.gz')
    class_stability=[]
    for (method,dom,cl),g in full[full.method_id.str.startswith('reverse_selected')&full.class_id.ne('unknown')].groupby(['method_id','domain','class_id']):
        members=set(g.worker_id)
        z=co[(co.method_id==method)&(co.domain==dom)&co.worker_a.isin(members)&co.worker_b.isin(members)&co.n_supported_folds.ge(16)]
        class_stability.append({'method_id':method,'domain':dom,'full_class_id':cl,'members':'|'.join(sorted(members)),
            'n_members':len(members),'supported_classmate_pairs':len(z),
            'coassignment_mean':z.coassignment_rate.mean(),'coassignment_p10':z.coassignment_rate.quantile(.1),
            'coassignment_min':z.coassignment_rate.min(),'pairs_coassigned_at_least90pct_folds':int(z.coassignment_rate.ge(.9).sum()),
            'is_interchangeability_verification':False})
    exports.append(csv_verified(pd.DataFrame(class_stability),p/'FULL_CLASS_MEMBERSHIP_STABILITY.csv'))
    usage=[]
    domains=json.loads((HERE.parent/'forward/FEATURE_DOMAINS.json').read_text())
    feature_domain={feature:domain for domain,features in domains.items() for feature in features}
    for section in (e/'rules.txt').read_text().split('## ')[1:]:
        header,body=section.split('\n',1);fold,method,dom=header.strip().split(' / ')
        used={}
        for feature,value in re.findall(r'\|--- ([A-Za-z0-9_]+) <=\s*(-?[\d.]+)',body):
            used.setdefault(feature,set()).add(float(value))
        for feature,thresholds in used.items():
            usage.append({'fold_id':fold,'method_id':method,'domain':dom,'feature':feature,'feature_domain':feature_domain.get(feature),
                          'unique_split_thresholds':len(thresholds),'minimum_threshold':min(thresholds),'maximum_threshold':max(thresholds),
                          'meaning':'tree split usage; may contain redundant leaf predictions, not incremental or causal evidence'})
    exports.append(csv_verified(pd.DataFrame(usage),e/'RULE_FEATURE_USAGE.csv'))
    (HERE/'EXCHANGE_SUMMARY_RECEIPT.json').write_text(json.dumps({'exports':exports,'new_fits':0,'new_selection':0,
        'full_table_use':'descriptive labels from all current history; use per-fold labels for evaluation, never FULL at heldout building'},indent=2)+'\n')
    print({'rows':len(out),'class_stability_rows':len(class_stability),'tree_feature_rows':len(usage)},flush=True)


if __name__=='__main__':main()
