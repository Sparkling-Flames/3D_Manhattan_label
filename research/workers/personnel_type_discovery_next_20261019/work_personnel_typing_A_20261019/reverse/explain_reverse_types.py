#!/usr/bin/env python3
"""Small, missing-aware rules explaining frozen reverse personnel partitions."""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, adjusted_rand_score

HERE=Path(__file__).resolve().parent


def fit_rule(df,y,features):
    feats=[c for c in features if df[c].notna().sum()>=10 and df[c].dropna().nunique()>1]
    if not feats or len(set(y))<2:return None,feats,None
    med=df[feats].median()
    model=DecisionTreeClassifier(max_depth=3,min_samples_leaf=4,random_state=20261019)
    model.fit(df[feats].fillna(med),y)
    return model,feats,med


def rule_predict(model,features,median,df,fallback):
    if model is None:return np.repeat(fallback,len(df)),np.ones(len(df),bool)
    x=df[features];filled=x.fillna(median)
    pred=model.predict(filled)
    path=model.decision_path(filled)
    known=[]
    for i in range(len(df)):
        split_indices=model.tree_.feature[path.indices[path.indptr[i]:path.indptr[i+1]]]
        split_indices=split_indices[split_indices>=0]
        known.append(bool(x.iloc[i,split_indices].notna().all()))
    known=np.array(known,bool)
    pred=pred.astype(object);pred[~known]='unknown'
    return pred,known


def main():
    p=argparse.ArgumentParser();p.add_argument('--classes',default=str(HERE/'results/all_candidate_classes.csv.gz'))
    p.add_argument('--features',default=str(HERE.parent/'forward/fold_features.csv.gz'))
    p.add_argument('--feature-domains',default=str(HERE.parent/'forward/FEATURE_DOMAINS.json'))
    p.add_argument('--output',default=str(HERE/'explanations'))
    a=p.parse_args();out=Path(a.output);out.mkdir(exist_ok=True,parents=True)
    c=pd.read_csv(a.classes).fillna({'class_id':'unknown'})
    f=pd.read_csv(a.features);f=f[f.metric.eq('B8L2')]
    f=f[f.inner_group.isna()] if 'inner_group' in f else f
    if f.duplicated(['fold_id','worker_id']).any():raise ValueError('Feature fold/worker not unique')
    dom=json.loads(Path(a.feature_domains).read_text());features=[x for v in dom.values() for x in v]
    selected=['reverse_selected','reverse_selected_global','reverse_selected_difficulty','reverse_selected_geometry','reverse_selected_swap']
    c=c[c.method_id.isin(selected)]
    rows=[];summaries=[];ruletexts=[];members=[];person_tests=[]
    for (fold,method,domain),g in c.groupby(['fold_id','method_id','domain']):
        joined=g.merge(f[f.fold_id.eq(fold)],on='worker_id',suffixes=('','_feature'),validate='one_to_one')
        if not joined.train_key.nunique()==1:raise ValueError('Feature train-set identity mismatch')
        # Train-key strings differ by encoding across routes; direct train building
        # manifests are crosschecked by root. Both sources explicitly name fold.
        mask=joined.class_id.ne('unknown');known=joined[mask].copy()
        if not len(known):continue
        y=known.class_id.to_numpy();mdl,feats,med=fit_rule(known,y,features)
        fallback=pd.Series(y).mode().iloc[0]
        pred,valid=rule_predict(mdl,feats,med,known,fallback)
        idx=known.index.to_numpy();pp={ix:(v,bool(k)) for ix,v,k in zip(idx,pred,valid)}
        for ix,r in joined.iterrows():
            pc,ok=pp.get(ix,('unknown',False))
            rows.append({'method_id':method+'_rule','source_method_id':method,'fold_id':fold,'heldout_building':r.heldout_building,
                         'worker_id':r.worker_id,'condition':'ordinary_manual','difficulty':domain,'domain':domain,
                         'class_id':pc,'discovered_class_id':r.class_id,'rule_features_observed':ok,
                         'n_images':r.n_images,'n_buildings':r.n_buildings,'information_stage':'history_before_target_building'})
        loo=[];loo_known=[];origin_loo=[]
        for i in range(len(known)):
            train=known.iloc[np.arange(len(known))!=i];yy=np.delete(y,i)
            mm,ff,md=fit_rule(train,yy,features)
            fb=pd.Series(yy).mode().iloc[0]
            py,pv=rule_predict(mm,ff,md,known.iloc[[i]],fb)
            loo.append(py[0]);loo_known.append(pv[0])
            same_origin=train[train.person_origin.eq(known.iloc[i].person_origin)]
            origin_loo.append(same_origin.class_id.mode().iloc[0] if len(same_origin) else fb)
            person_tests.append({'fold_id':fold,'method_id':method,'domain':domain,'worker_id':known.iloc[i].worker_id,
                                 'discovered_class':y[i],'predicted_class':py[0],'known_rule_path':bool(pv[0]),
                                 'correct':bool(py[0]==y[i]) if pv[0] else None})
        loo=np.array(loo);loo_known=np.array(loo_known,bool)
        summaries.append({'fold_id':fold,'method_id':method,'domain':domain,'n_workers':len(joined),'n_discovered_supported':len(known),
                          'rule_covered_workers':int(valid.sum()),'rule_coverage':valid.mean(),
                          'fit_agreement_covered':accuracy_score(y[valid],pred[valid]) if valid.any() else np.nan,
                          'fit_agreement_all_supported':np.mean(pred==y),
                          'loo_rule_covered_workers':int(loo_known.sum()),'loo_rule_coverage':loo_known.mean(),
                          'loo_agreement_covered':accuracy_score(y[loo_known],loo[loo_known]) if loo_known.any() else np.nan,
                          'loo_agreement_all_supported':np.mean(loo==y),
                          'loo_coassignment_ari_covered':adjusted_rand_score(y[loo_known],loo[loo_known]) if loo_known.sum()>1 else np.nan,
                          'majority_class_agreement':pd.Series(y).value_counts(normalize=True).max(),
                          'origin_only_loo_agreement':np.mean(np.asarray(origin_loo)==y),
                          'origin_only_loo_agreement_on_rule_covered':np.mean(np.asarray(origin_loo)[loo_known]==y[loo_known]) if loo_known.any() else np.nan,
                          'n_classes':len(set(y)),'n_features':len(feats),'features':'|'.join(feats)})
        rule=export_text(mdl,feature_names=feats,max_depth=3,decimals=4) if mdl else f'constant {fallback}'
        ruletexts.append(f'## {fold} / {method} / {domain}\n\n{rule}\n')
        for cl,z in known.groupby('class_id'):
            record={'fold_id':fold,'method_id':method,'domain':domain,'class_id':cl,'members':'|'.join(sorted(z.worker_id)),
                    'n_members':len(z),'new_origin_share':z.person_origin.eq('new').mean() if 'person_origin' in z else np.nan}
            for feature in features:
                record[feature+'_median']=z[feature].median();record[feature+'_known']=z[feature].notna().sum()
            members.append(record)
    pd.DataFrame(rows).to_csv(out/'rule_classes.csv.gz',index=False)
    pd.DataFrame(summaries).to_csv(out/'explanation_coverage.csv',index=False)
    pd.DataFrame(person_tests).to_csv(out/'leave_one_worker_out_rule_predictions.csv.gz',index=False)
    pd.DataFrame(members).to_csv(out/'class_feature_profiles.csv.gz',index=False)
    (out/'rules.txt').write_text('\n'.join(ruletexts))
    (out/'RECEIPT.json').write_text(json.dumps({'targets':selected,'n_rule_label_rows':len(rows),'n_explanation_groups':len(summaries),
        'input_sha256':{str(Path(x)):hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in [a.classes,a.features,a.feature_domains]},
        'new_fusion_calls':0,'test_building_outcomes_used_for_explanation':False,
        'restriction':'surrogate does not redefine original class; missing split feature makes rule unknown'},indent=2)+'\n')

if __name__=='__main__':main()
