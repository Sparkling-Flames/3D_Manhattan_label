"""Zero-fusion relabelling by independently trained A2 geometric personnel types."""
from collections import Counter
import json
import numpy as np
import pandas as pd
import study as s

METHOD='A2_samecount_source_residual'


def maps():
    f=pd.read_csv(s.TAX/'route_a/worker_labels_lobo.csv',keep_default_na=False)
    f=f[(f.method==METHOD)&(f.stage=='leave_building_out')]
    return {(c,b):{r.worker_id:r.class_id for r in g.itertuples() if r.class_id not in ('','unknown','unassigned')}
            for (c,b),g in f.groupby(['condition','target_building'])}


def vector(ws,labels):
    return dict(sorted(Counter(labels[w] for w in ws).items()))


def aggregate_common(data,keys,metrics,outname):
    rows=[];anchors=[]
    for key,g in data.groupby(keys):
        for metric in metrics:
            sub=g[g[metric].notna()]
            possible=sub.groupby('anchor_id').arm.nunique()
            sub=sub[sub.anchor_id.isin(possible[possible==2].index)]
            a=sub.groupby(['anchor_id','image','building','arm'])[metric].mean().reset_index()
            a=a.rename(columns={metric:'value'});a['metric']=metric
            for k,v in zip(keys,key):a[k]=v
            anchors.extend(a.to_dict('records'))
            t=a.groupby(['building','image','arm']).value.mean().groupby(['building','arm']).mean().groupby('arm').mean()
            row=dict(zip(keys,key));row.update(metric=metric,pairs=len(sub),common_anchors=sub.anchor_id.nunique(),
                images=sub.image.nunique(),buildings=sub.building.nunique(),same=t.get('same'),cross=t.get('cross'),
                cross_minus_same=t.get('cross',np.nan)-t.get('same',np.nan))
            rows.append(row)
    s.csv(s.OUT/(outname+'_SUMMARY.csv'),pd.DataFrame(rows))
    s.csv(s.OUT/(outname+'_ANCHORS.csv.gz'),pd.DataFrame(anchors))


def common_library(mm):
    source=s.CORNER/'common_library/COMMON_ENDPOINT_PAIRS.csv.gz'
    fields=['anchor_id','pool_id','image','building','n','m','pair_id','A_team_key','B_team_key','left_workers','right_workers',
            'bev_mean_h','bev_max_h','top_mean_h','top_max_h','valid_distance','different_count','missing_geometry','noncomplete']
    f=pd.read_csv(source,usecols=fields);rows=[]
    for e in f.to_dict('records'):
        labels=mm.get(('manual',e['building']),{})
        aa,bb=e['left_workers'].split('|'),e['right_workers'].split('|')
        if not all(w in labels for w in aa+bb):continue
        ca,cb=vector(aa,labels),vector(bb,labels)
        rows.append(dict(e,arm='same' if ca==cb else 'cross',left_class_counts=json.dumps(ca),right_class_counts=json.dumps(cb)))
    result=pd.DataFrame(rows);s.csv(s.OUT/'A2_REUSED_COMMON_LABELS.csv.gz',result)
    aggregate_common(result,['n','m'],['bev_mean_h','bev_max_h','top_mean_h','valid_distance','different_count','missing_geometry','noncomplete'],'A2_REUSED_COMMON')


def new_b_design(mm):
    requests={e['event_id']:e for e in s.read(s.OUT/'REQUESTS.json.gz')['events']}
    f=pd.read_csv(s.OUT/'EVENTS.csv.gz');rows=[];coverage=[]
    metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','valid_distance','different_count','unavailable_geometry',
             'floor_jaccard_difference','abs_B8L2_change','abs_D10_change','joint_stable_main']
    for e in f.to_dict('records'):
        request=requests[e['event_id']];labels=mm.get((e['condition'],e['building']),{})
        if not all(w in labels for a in 'ABC' for w in request[a+'_workers']):continue
        va=vector(request['A_workers'],labels);arms=[]
        for letter,name in [('B','within'),('C','cross')]:
            vb=vector(request[letter+'_workers'],labels);arm='same' if va==vb else 'cross';arms.append(arm)
            row={k:e[k] for k in ['event_id','pool_id','image','building','condition','layer','difficulty','design_tier','n','m']}
            row.update(anchor_id=e['event_id'],arm=arm,original_B_design_arm=name,
                       left_class_counts=json.dumps(va),right_class_counts=json.dumps(vb))
            row.update({k:e[name+'_'+k] for k in metrics});rows.append(row)
        coverage.append(dict(event_id=e['event_id'],condition=e['condition'],layer=e['layer'],n=e['n'],m=e['m'],
                             has_same_and_cross=len(set(arms))==2))
    result=pd.DataFrame(rows);s.csv(s.OUT/'A2_NEW_B_DESIGN_LABELS.csv.gz',result)
    aggregate_common(result,['condition','layer','n','m'],metrics,'A2_NEW_B_DESIGN')
    s.csv(s.OUT/'A2_NEW_B_DESIGN_COVERAGE.csv',pd.DataFrame(coverage))


if __name__=='__main__':
    mm=maps();common_library(mm);new_b_design(mm)
    s.save(s.OUT/'A2_RELABEL_RECEIPT.json',dict(method=METHOD,training='target-building excluded A2 class_id',
        geometry_recomputed=False,primary_design='Frozen B structural class requests; A2 is a secondary common-anchor relabelling',
        historical_design='Existing 63476 common endpoints, 11 images, 6 buildings, reused not independent',
        aggregation='metric-specific common anchors with both same and cross composition; anchor -> image -> building equal',
        units='BEV and top distances in camera-height h, not metres'))
