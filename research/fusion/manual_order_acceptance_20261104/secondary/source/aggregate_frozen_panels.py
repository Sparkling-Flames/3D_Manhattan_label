#!/usr/bin/env python3
"""Reclassify saved complete finite panels without changing team endpoints.

Frozen LOBO labels form FULL-team class-count vectors, including background D.
Every candidate is evaluated both on its known-team support and the intersection
known by all requested candidates. Teams are never relabelled as strict ABC events.
Checkpoints are written after each method; input tables retain exact memberships.
"""
from __future__ import annotations
import argparse
import gzip
import os
from collections import Counter
import hashlib
import json
from math import comb
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

METRICS = [
    'B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter',
    'omission','extension','ref_node_recall_5','ref_node_recall_9',
    'ref_edge_recall_5','ref_edge_recall_9','diag_corner_recall_05',
    'diag_wall_coverage_03','diag_wall_coverage_05','nodes','fusion_turn_n',
    'fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2',
    'centroid_x_h','centroid_z_h','bounds_min_x_h','bounds_max_x_h',
    'bounds_min_z_h','bounds_max_z_h','height_mean_h','height_min_h','height_max_h',
    'height_mean_ratio','bottom_y_mean_px','top_y_mean_px','minimum_support',
    'selected_support_min','identity_groups_n','unselected_groups_n',
    'minority_observations_n','half_vote_nodes','failure','below_four',
    'location_unresolved','order_tied','connection_available',
    'recorded_time_total_seconds','log_recorded_time',
]
TIME_METRICS = {'recorded_time_total_seconds','log_recorded_time'}
SUMMARY_COLUMNS=['method','condition','support','metric','time_source','total_variance','within_variance',
                 'between_variance','panels','pools','images','buildings','valid_team_links','constant_panels',
                 'between_share','summary_axis','summary_value']


def save_csv(path, frame):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.writing')
    data=frame.to_csv(index=False).encode('utf-8')
    if path.suffix=='.gz':
        data=gzip.compress(data,compresslevel=5,mtime=0)
    with temp.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    temp.replace(path)


def words(value):
    return str(value).split('|') if pd.notna(value) and str(value) else []


def truth(s):
    return s.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])


def vector_string(classes, values):
    return '|'.join(f'{c}:{int(v)}' for c,v in zip(classes,values))


def decompose(y, groups):
    good=np.isfinite(y); x=y[good]; c=groups[good]
    if not len(x):
        return dict(valid_teams=0, configurations=0, singleton_configurations=0,
                    total_variance=np.nan, within_variance=np.nan, between_variance=np.nan, between_share=np.nan)
    ids=np.unique(c); means={i:float(x[c==i].mean()) for i in ids}
    fitted=np.array([means[i] for i in c]); mu=x.mean()
    total=float(np.mean((x-mu)**2)); within=float(np.mean((x-fitted)**2)); between=float(np.mean((fitted-mu)**2))
    assert np.isclose(total,within+between,rtol=1e-9,atol=1e-9)
    return dict(valid_teams=len(x), configurations=len(ids),
                singleton_configurations=sum(np.sum(c==i)==1 for i in ids),
                total_variance=total, within_variance=within, between_variance=between,
                between_share=between/total if total>1e-12 else np.nan)


def macro(rows):
    """Panel -> target pool -> image -> building, with conditions separated."""
    if rows.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    fields=['total_variance','within_variance','between_variance']
    scopes=[('all','all',rows)]
    for column in ['scope','difficulty','n','source_domain','geometric_challenge']:
        if column in rows:
            scopes += [(column,str(k),g) for k,g in rows.groupby(column,dropna=False)]
    out=[]
    group=['method','condition','support','metric','time_source']
    for category,value,frame in scopes:
        valid=frame.dropna(subset=['total_variance']).copy()
        if valid.empty:
            continue
        target=valid.groupby(group+['building','image','pool_id'],dropna=False)[fields].mean().reset_index()
        image=target.groupby(group+['building','image'],dropna=False)[fields].mean().reset_index()
        building=image.groupby(group+['building'],dropna=False)[fields].mean().reset_index()
        summary=building.groupby(group,dropna=False)[fields].mean()
        valid['constant']=valid.total_variance.le(1e-12).astype(int)
        counts=valid.groupby(group,dropna=False).agg(
            panels=('panel_id','nunique'),pools=('pool_id','nunique'),images=('image','nunique'),
            buildings=('building','nunique'),valid_team_links=('valid_teams','sum'),
            constant_panels=('constant','sum'))
        summary=summary.join(counts).reset_index()
        summary['between_share']=(summary.between_variance/summary.total_variance).where(summary.total_variance.gt(1e-12))
        summary['summary_axis']=category;summary['summary_value']=value
        out.append(summary)
    return pd.concat(out,ignore_index=True) if out else pd.DataFrame(columns=SUMMARY_COLUMNS)


def load_labels(paths, requested):
    labels=pd.concat([pd.read_csv(p,low_memory=False) for p in paths],ignore_index=True)
    labels=labels[labels.heldout_building.ne('ALL')].copy()
    if requested:
        labels=labels[labels.method.isin(requested)]
        assert set(requested)<=set(labels.method), sorted(set(requested)-set(labels.method))
    labels['known']=truth(labels.known)
    duplicate=labels.duplicated(['method','heldout_building','worker_id'],keep=False)
    if duplicate.any():
        check=labels[duplicate].groupby(['method','heldout_building','worker_id']).class_id.nunique()
        assert check.le(1).all(),'Conflicting label sources'
        labels=labels.drop_duplicates(['method','heldout_building','worker_id'],keep='last')
    known=labels[labels.known & labels.class_id.notna()]
    maps={method:{(b,w):str(c) for b,w,c in g[['heldout_building','worker_id','class_id']].itertuples(index=False,name=None)}
          for method,g in known.groupby('method')}
    return labels,maps


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--inputs',type=Path,required=True)
    ap.add_argument('--endpoints',type=Path)
    ap.add_argument('--labels',type=Path,nargs='+',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--methods',default='')
    ap.add_argument('--metrics',default='')
    ap.add_argument('--condition',choices=['manual','semi'],default='manual')
    ap.add_argument('--target-conditions',type=Path)
    ap.add_argument('--max-panels',type=int)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    requested=args.methods.split(',') if args.methods else None
    labels,maps=load_labels(args.labels,requested)
    methods=sorted(maps)
    # Method provenance can restrict evaluation; never blend condition endpoints.
    if 'evaluation_condition' in labels:
        permitted={m:any(args.condition in str(x) for x in g.evaluation_condition.dropna())
                   for m,g in labels.groupby('method')}
        methods=[m for m in methods if permitted.get(m,True)]
    assert methods,'No candidate methods permitted for requested condition'
    method_info={m:{k:g.iloc[0].get(k,'') for k in ['family','input_conditions','evaluation_condition']}
                 for m,g in labels.groupby('method')}
    for method,g in labels.groupby('method'):
        if not method_info[method]['input_conditions']:
            method_info[method]['input_conditions']=g.iloc[0].get('condition','')
    panels=pd.read_csv(args.inputs/'PANELS_USED.csv')
    panels=panels[panels.condition.eq(args.condition)].copy()
    if args.max_panels:
        panels=panels.head(args.max_panels)
    if args.target_conditions:
        tc=pd.read_csv(args.target_conditions).set_index('pool_id')
        for col in ['scope','official_difficulty','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges']:
            panels[col]=panels.pool_id.map(tc[col])
        panels['difficulty']=panels.official_difficulty.fillna('未分级')
    links=pd.read_csv(args.inputs/'PANEL_TEAMS.csv.gz')
    links=links[links.panel_id.isin(panels.panel_id)].copy()
    member_path=args.inputs/'TEAM_MEMBERS.csv.gz'
    if not member_path.exists():
        member_path=args.inputs/'TEAM_REQUESTS.csv.gz'
    members=pd.read_csv(member_path).set_index('team_key')
    endpoint_file=args.endpoints or args.inputs/'ENDPOINT_SCALARS.csv.gz'
    end=pd.read_csv(endpoint_file,low_memory=False).set_index('team_key')
    assert end.index.is_unique and members.index.is_unique
    wanted=set(links.team_key)
    assert wanted<=set(end.index),f'{len(wanted-set(end.index))} missing endpoint scalars'
    if 'failure' not in end:
        end['failure']=(~truth(end.complete_evaluable)).astype(float)
    if 'recorded_time_total_seconds' in end:
        recorded=pd.to_numeric(end.recorded_time_total_seconds,errors='coerce')
        eligible=truth(end.recorded_time_eligible) if 'recorded_time_eligible' in end else recorded.gt(0)
        end['recorded_time_total_seconds']=recorded.where(eligible & recorded.gt(0))
        end['log_recorded_time']=np.log(end.recorded_time_total_seconds)
    metrics=[m for m in (args.metrics.split(',') if args.metrics else METRICS) if m in end]
    end[metrics]=end[metrics].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    metadata_columns=[c for c in ['panel_id','pool_id','image','building','condition','n','difficulty',
                                 'source_domain','scope','geometric_challenge','structural_condition'] if c in panels]
    signature=hashlib.sha256()
    signed_inputs=[*args.labels,args.inputs/'PANELS_USED.csv',args.inputs/'PANEL_TEAMS.csv.gz',member_path,endpoint_file]
    if args.target_conditions:
        signed_inputs.append(args.target_conditions)
    for path in signed_inputs:
        signature.update(hashlib.sha256(path.read_bytes()).digest())
    signature.update(json.dumps([methods,metrics,args.condition,args.max_panels],sort_keys=True).encode())
    run_hash=signature.hexdigest()
    # Precompute shared label availability for exact same teams in each panel.
    prepared={}
    for panel in panels.to_dict('records'):
        pp=links[links.panel_id.eq(panel['panel_id'])]
        keys=pp.team_key.tolist(); ms=[words(members.at[k,'member_workers']) for k in keys]
        assert all(len(x)==int(panel['n']) for x in ms)
        D=words(panel.get('background_workers','')); variable=words(panel['variable_workers'])
        selected_n=int(panel.get('selected_variable_n',panel.get('variable_choose',int(panel['n'])-len(D))))
        assert not set(D)&set(variable)
        assert all(set(x)==set(D)|set(words(v)) for x,v in zip(ms,pp.selected_variable_workers))
        building=panel['building']
        all_known={w:all((building,w) in maps[m] for m in methods) for w in set(D)|set(variable)}
        shared=np.array([all(all_known.get(w,False) for w in team) for team in ms])
        prepared[panel['panel_id']]=dict(panel=panel,keys=keys,members=ms,D=D,variable=variable,
                                       selected_n=selected_n,shared=shared,all_known=all_known)
    saves=[]
    for method in methods:
        directory=args.out/'by_method'/method
        checkpoint=directory/'COMPLETE.json'
        if checkpoint.exists() and json.loads(checkpoint.read_text()).get('run_hash')==run_hash:
            saves.append(directory); print('reuse',method,flush=True); continue
        coverage=[]; variances=[]; distribution=[]; configurations=[]; vectors=[]
        lm=maps[method]
        for entry in prepared.values():
            panel=entry['panel']; keys=entry['keys']; building=panel['building']
            classes=sorted({c for (b,w),c in lm.items() if b==building})
            meta={c:panel[c] for c in metadata_columns}; meta['method']=method
            meta.update(method_info[method])
            cindex={c:i for i,c in enumerate(classes)}
            known=np.array([all((building,w) in lm for w in team) for team in entry['members']])
            values=np.zeros((len(keys),len(classes)),dtype=np.int16)
            for i,team in enumerate(entry['members']):
                for w in team:
                    if (building,w) in lm:
                        values[i,cindex[lm[(building,w)]]]+=1
            strings=[vector_string(classes,row) if ok else '' for row,ok in zip(values,known)]
            D=entry['D']; variable=entry['variable']; shared=entry['shared']
            bg=Counter(lm[(building,w)] for w in D if (building,w) in lm)
            bgv=np.array([bg[c] for c in classes],dtype=int)
            missing=sorted({w for team in entry['members'] for w in team if (building,w) not in lm})
            coverage.append(dict(**meta,teams=len(keys),known_teams=int(known.sum()),
                                 unknown_teams=int((~known).sum()),shared_known_teams=int(shared.sum()),
                                 missing_workers='|'.join(missing),source_variable_panel_size=len(variable),
                                 source_background_size=len(D),selected_variable_n=entry['selected_n']))
            vectors += [dict(panel_id=panel['panel_id'],team_key=k,method=method,
                             heldout_building=building,class_counts=s,known=bool(ok),
                             shared_known=bool(common)) for k,s,ok,common in zip(keys,strings,known,shared)]
            ys=end.loc[keys]
            for support,mask in [('method_known',known),('shared_known',shared)]:
                meta2={**meta,'support':support}
                z=ys.iloc[np.flatnonzero(mask)]; v=values[mask]
                if len(v):
                    unique,inverse=np.unique(v,axis=0,return_inverse=True)
                else:
                    unique=np.empty((0,len(classes)),dtype=int); inverse=np.array([],dtype=int)
                eligible_variable=[w for w in variable if (building,w) in lm and
                                   (support!='shared_known' or entry['all_known'][w])]
                capacity=Counter(lm[(building,w)] for w in eligible_variable)
                expected_teams=(comb(len(eligible_variable),entry['selected_n'])
                                if len(eligible_variable)>=entry['selected_n'] and
                                all((building,w) in lm and (support!='shared_known' or entry['all_known'][w]) for w in D)
                                else 0)
                # Method-specific vectors of the FULL team, not just inserted six.
                for ci,count in enumerate(unique):
                    indices=np.flatnonzero(inverse==ci); subset=z.iloc[indices]
                    full_vector=vector_string(classes,count); selected=count-bgv
                    possible=1
                    for c,take in zip(classes,selected):
                        possible *= comb(capacity[c],int(take)) if 0<=take<=capacity[c] else 0
                    configurations.append(dict(
                        **meta2,class_counts=full_vector,
                        background_class_counts=vector_string(classes,bgv),
                        selected_variable_counts=vector_string(classes,selected),
                        variable_class_capacity=vector_string(classes,[capacity[c] for c in classes]),
                        teams=len(subset),possible_member_sets_on_label_support=possible,
                        member_census_complete=len(subset)==possible,
                        scorable_teams=int(subset.B8L2.notna().sum()),
                        failed_teams=int(subset.failure.fillna(0).sum()),
                        failure_rate=float(subset.failure.mean()),
                        member_variation_estimable=len(subset)>1,
                        pure_class_team=bool((count>0).sum()==1),
                        maximum_class_fraction=float(count.max()/int(panel['n'])) if len(count) else np.nan,
                    ))
                measurement_groups=[('not_time',[x for x in metrics if x not in TIME_METRICS],np.ones(len(z),dtype=bool))]
                if TIME_METRICS & set(metrics):
                    kinds=z['time_source_kinds'].fillna('unknown') if 'time_source_kinds' in z else pd.Series('source_unspecified',index=z.index)
                    for kind in sorted(kinds.unique()):
                        if kind and '|' not in str(kind):
                            measurement_groups.append((kind,[x for x in metrics if x in TIME_METRICS],kinds.eq(kind).to_numpy()))
                for time_source,fields,which in measurement_groups:
                    if not fields:
                        continue
                    data=z[fields].to_numpy(dtype=float)[which]; group=inverse[which]
                    for j,metric in enumerate(fields):
                        variances.append(dict(**meta2,metric=metric,time_source=time_source,
                                              teams=int(mask.sum()),expected_known_panel_teams=expected_teams,
                                              complete_known_member_census=int(mask.sum())==expected_teams,
                                              **decompose(data[:,j],group)))
                    for ci in np.unique(group):
                        array=data[group==ci]; valid=np.isfinite(array).sum(axis=0)
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore',RuntimeWarning)
                            mean=np.nanmean(array,axis=0); sd=np.nanstd(array,axis=0,ddof=0)
                            q=np.nanquantile(array,[0,.05,.25,.5,.75,.95,1],axis=0)
                        for j,metric in enumerate(fields):
                            count=int(valid[j]); estimable=count>1
                            distribution.append(dict(
                                **meta2,class_counts=vector_string(classes,unique[ci]),
                                metric=metric,time_source=time_source,teams=len(array),
                                valid_teams=count,missing_teams=len(array)-count,
                                mean=mean[j],p05=q[1,j],p25=q[2,j],median=q[3,j],
                                p75=q[4,j],p95=q[5,j],minimum=q[0,j],maximum=q[6,j],
                                sd=sd[j] if estimable else np.nan,
                                iqr=q[4,j]-q[2,j] if estimable else np.nan,
                                range=q[6,j]-q[0,j] if estimable else np.nan,
                                member_variation_estimable=estimable,
                            ))
        vf=pd.DataFrame(variances); cf=pd.DataFrame(configurations)
        base_columns=metadata_columns+['method','family','input_conditions','evaluation_condition','support']
        if cf.empty:
            cf=pd.DataFrame(columns=base_columns+[
                'class_counts','background_class_counts','selected_variable_counts','variable_class_capacity',
                'teams','possible_member_sets_on_label_support','member_census_complete','scorable_teams',
                'failed_teams','failure_rate','member_variation_estimable','pure_class_team','maximum_class_fraction'])
        dist=pd.DataFrame(distribution)
        if dist.empty:
            dist=pd.DataFrame(columns=base_columns+[
                'class_counts','metric','time_source','teams','valid_teams','missing_teams',
                'mean','p05','p25','median','p75','p95','minimum','maximum','sd','iqr','range','member_variation_estimable'])
        for name,frame in [('PANEL_COVERAGE.csv.gz',pd.DataFrame(coverage)),
                           ('PANEL_VARIANCE.csv.gz',vf),('CONFIGURATION_COUNTS.csv.gz',cf),
                           ('CONFIGURATION_DISTRIBUTIONS.csv.gz',dist),
                           ('TEAM_CLASS_VECTORS.csv.gz',pd.DataFrame(vectors)),
                           ('SUMMARY.csv',macro(vf))]:
            save_csv(directory/name,frame)
        identity_error=float((vf.total_variance-vf.within_variance-vf.between_variance).abs().max()) if len(vf) else np.nan
        receipt=dict(method=method,run_hash=run_hash,condition=args.condition,
                     label_sources=[str(p) for p in args.labels],
                     panels=len(coverage),configuration_rows=len(cf),
                     distribution_rows=len(distribution),team_vectors=len(vectors),
                     metrics=metrics,common_method_set=methods,new_fusions=0,
                     variance_identity_max_error=identity_error if np.isfinite(identity_error) else None,
                     purpose='full_composition_grouping_not_strict_ABC')
        checkpoint.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        saves.append(directory); print('saved',method,'panels',len(coverage),'configs',len(cf),flush=True)
    summaries=[pd.read_csv(p/'SUMMARY.csv') for p in saves]
    save_csv(args.out/'ALL_METHOD_COMPARISON.csv',pd.concat(summaries,ignore_index=True))
    cov=pd.concat([pd.read_csv(p/'PANEL_COVERAGE.csv.gz') for p in saves],ignore_index=True)
    save_csv(args.out/'ALL_METHOD_COVERAGE.csv.gz',cov)
    receipt=dict(run_hash=run_hash,condition=args.condition,methods=methods,panels=len(panels),
                 images=panels.image.nunique(),buildings=panels.building.nunique(),
                 team_links=len(links),unique_endpoints=len(wanted),metrics=metrics,
                 strict_ABC_events_created=0,new_fusions=0)
    (args.out/'COMPLETE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
