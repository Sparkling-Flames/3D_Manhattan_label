#!/usr/bin/env python3
"""Bind frozen current original answers to LOBO labels and prepare exact examples.

No fitting, no quality scoring, no annotation rewriting. Q/T are read only after
selection by coverage and geometric median distance. Run render_examples.py next.
"""
from pathlib import Path
import gzip, hashlib, json, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
BASIS=HERE.parent/'basis'
HEAD='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
METHODS={'TARGET_DSTRUCT_K3':['C1','C2','C3'],'RFUSE_GEOM_K2':['C1','C2'],'OPPJOINT_K3':['C1','C2','C3'],
         'OPPJOINT_K4':['C1','C2','C3','C4']}
# Batch 10 adds K4 to the existing images; it does not rerun image selection.
IMAGE_SELECTION_METHODS=('TARGET_DSTRUCT_K3','RFUSE_GEOM_K2','OPPJOINT_K3')
FEATURES=['turn_n','short_turn_edges','near_straight_nodes_5deg','matched_horizontal_bias_deg',
          'matched_top_bias_deg','matched_bottom_bias_deg','log_area_ratio','log_height']
PRIMARY_IMAGES=['jtcxE69GiFV-10','jtcxE69GiFV-09','jtcxE69GiFV-26']
SUPPLEMENT_IMAGE='yqstnuAEVhm-01'

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.bool_,)):return bool(v)
    if isinstance(v,(float,np.floating)):return float(v) if math.isfinite(v) else None
    return v

def read_csv(p,**kwargs):return pd.read_csv(p,low_memory=False,float_precision='round_trip',**kwargs)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def traits(points):
    p=np.asarray(points,float);bottom=p[1::2];ang=bottom[:,0]*2*np.pi/1024
    radius=1/np.tan((bottom[:,1]/512-.5)*np.pi)
    floor=np.column_stack([-np.sin(ang)*radius,np.cos(ang)*radius])
    edges=np.roll(floor,-1,axis=0)-floor;length=np.linalg.norm(edges,axis=1)
    turn=np.degrees(np.arccos(np.clip((edges*np.roll(edges,1,axis=0)).sum(1)/(length*np.roll(length,1)),-1,1)))
    short=(length/length.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)
    return dict(floor_xz_h=floor.tolist(),turn_deg=turn.tolist(),edge_length_h=length.tolist(),
                turn_nodes_1based=(np.flatnonzero(turn>5)+1).tolist(),
                near_straight_nodes_1based=(np.flatnonzero(turn<=5)+1).tolist(),
                short_edge_start_nodes_1based=(np.flatnonzero(short)+1).tolist())

def main():
    raw_path=BASE/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'
    label_path=BASIS/'WORKER_LABELS_ALL_LOBO.csv.gz'
    raw=read_csv(raw_path)
    d=raw[raw.scope.eq('primary')&raw.layer.eq('ordinary_manual')&raw.condition.eq('manual')].copy()
    labels=read_csv(label_path,keep_default_na=False)
    for method in METHODS:
        lab=labels[labels.method.eq(method)&labels.heldout_building.ne('ALL')&labels.known.astype(str).str.lower().eq('true')]
        assert not lab.duplicated(['heldout_building','worker_id']).any()
        d=d.merge(lab[['heldout_building','worker_id','class_id']].rename(columns={'heldout_building':'building','class_id':method}),
                  on=['building','worker_id'],how='left',validate='many_to_one')
    image_index=read_csv(ROOT/'analysis_results/quality/quality_scope_model_handoff_20261015/original_images/IMAGE_INDEX.csv')
    rows=[]
    for (im,origin,ts),g in d.groupby(['image','origin','time_source']):
        if not g.source_active_time_seconds.gt(0).all():continue
        if g.worker_id.duplicated().any():raise ValueError('Ambiguous worker/image primary record')
        r=dict(image=im,image_id=g.image_id.iloc[0],origin=origin,time_source=ts,difficulty=g.official_difficulty.iloc[0],
               building=g.building.iloc[0],n=len(g),pool_id=g.pool_id.iloc[0],original_available=im in set(image_index.image_code))
        counts=[]
        for method,classes in METHODS.items():
            c=[int(g[method].eq(k).sum()) for k in classes];r[method]='|'.join(map(str,c))
            if method in IMAGE_SELECTION_METHODS:counts+=c
        r['minimum_class_count']=min(counts);rows.append(r)
    coverage=pd.DataFrame(rows)
    coverage.to_csv(HERE/'CANDIDATE_IMAGE_COVERAGE.csv',index=False)
    eligible=coverage[coverage.minimum_class_count.ge(2)&coverage.original_available].sort_values(['minimum_class_count','n','image'],ascending=[False,False,True])
    primary=[eligible[eligible.difficulty.eq(x)].iloc[0].image for x in ['简单','中等','困难']]
    assert primary==PRIMARY_IMAGES,(primary,PRIMARY_IMAGES)
    extra=eligible[eligible.building.ne('jtcxE69GiFV')].iloc[0].image
    assert extra==SUPPLEMENT_IMAGE
    selected_images=primary+[extra]
    selected_groups=eligible[eligible.image.isin(selected_images)].drop_duplicates('image').set_index('image')
    candidates=[];slots=[]
    for im in selected_images:
        ig=selected_groups.loc[im]
        g=d[d.image.eq(im)&d.origin.eq(ig.origin)&d.time_source.eq(ig.time_source)].copy()
        vals=g[FEATURES].astype(float)
        scale=vals.quantile(.75)-vals.quantile(.25)
        scale=scale.where(scale>1e-12,vals.std(ddof=0)).where(lambda x:x>1e-12,np.nan)
        for method,classes in METHODS.items():
            for c in classes:
                cg=g[g[method].eq(c)].copy()
                med=cg[FEATURES].median()
                distances=((cg[FEATURES]-med).abs()/scale).mean(axis=1,skipna=True)
                cg['selection_distance']=distances
                cg=cg.sort_values(['selection_distance','worker_id','object_id'])
                assert len(cg)>=(1 if method=='OPPJOINT_K4' else 2) and cg.selection_distance.notna().all()
                for rank,(_,r) in enumerate(cg.iterrows(),1):
                    result=dict(image=im,method=method,class_id=c,worker_id=r.worker_id,object_id=r.object_id,
                                selection_rank=rank,selected=rank<=2,distance=r.selection_distance,class_available=len(cg),
                                time_source=ig.time_source,**{x:r[x] for x in FEATURES})
                    candidates.append(result)
                    if rank<=2:slots.append(dict(result,record=r.to_dict(),image_group='primary' if im in primary else 'cross_building_supplement'))
    # A transparent feature illustration, kept outside the typical slots.
    near=pd.DataFrame(candidates)
    near=near[near.image.isin(primary)&near.method.eq('TARGET_DSTRUCT_K3')&near.near_straight_nodes_5deg.gt(0)]
    near=near.sort_values(['distance','image','worker_id','object_id']).iloc[0].to_dict()
    assert near['object_id']=='v2:new:103126'
    nr=d[d.object_id.eq(near['object_id'])].iloc[0].to_dict()
    slots.append(dict(near,record=nr,image_group='near_collinear_feature_supplement'))
    # Only here, after object selection is complete, load Q components.
    quality_path=ROOT/'research/data/releases/v2.1/quality_records.csv'
    quality=read_csv(quality_path)
    qkeys=['object_id','reference_id','reference_version']
    assert not quality.duplicated(qkeys).any()
    qindex=quality.set_index(qkeys)
    bundle_path=ROOT/'research/data/releases/v2.1/analysis_input/data.json.gz'
    bundle=json.loads(gzip.decompress(bundle_path.read_bytes()))
    objects={o['object_id']:o for o in bundle['objects']}
    ref_path=ROOT/'research/data/releases/v2.1/reference_catalog.json'
    refs=json.loads(ref_path.read_text())
    refindex={(r['target_id'],r['reference_version']):r for r in refs}
    center_path=BASIS/'CLASS_TRAINING_CENTERS_BY_FOLD.csv.gz'
    rfcenter_path=BASIS/'RFUSE_FUSION_RESPONSE_CENTERS_BY_FOLD.csv.gz'
    centers=read_csv(center_path);rfcenters=read_csv(rfcenter_path)
    image_receipt=json.loads((HERE/'ORIGINAL_IMAGE_RECEIPT.json').read_text())
    receipts={r['image_code']:r for r in image_receipt}
    payload=dict(schema='hohonet-current-class-original-answer-examples-v2',source_commit=HEAD,
                 source_effective_revision=bundle.get('input_revision'),
                 models=list(METHODS),selection_features=FEATURES,selection_rule='SELECTION_RULE.md',
                 image_selection_methods=list(IMAGE_SELECTION_METHODS),
                 selection_per_class='min(2, available); singleton classes are shown in full',
                 annotation_frame=[1024,512],slots=[],objects={},references={},images=[],centers=[])
    record_rows=[]
    for s in slots:
        r=s['record'];key=tuple(r[k] for k in qkeys);q=qindex.loc[key]
        for m in ['B8L2','D10']:
            assert abs(float(r[m])-float(q[m]))<1e-8,(key,m,r[m],q[m])
        obj=objects[r['object_id']]
        assert obj['worker_id']==r['worker_id'] and obj['image_id']==r['image_id']
        p=obj['points_1024x512'];tr=traits(p)
        assert len(p)%2==0 and np.isfinite(p).all()
        assert np.max(np.abs(np.array(p)[::2,0]-np.array(p)[1::2,0]))<1e-7
        for raw_name,calc_name in [('turn_n','turn_nodes_1based'),('short_turn_edges','short_edge_start_nodes_1based'),('near_straight_nodes_5deg','near_straight_nodes_1based')]:
            assert r[raw_name]==len(tr[calc_name]),(r['object_id'],raw_name,r[raw_name],tr[calc_name])
        refkey=(r['reference_id'],r['reference_version']);ref=refindex[refkey]
        assert ref['image_id']==r['image_id']
        refpayloadid='||'.join(refkey)
        payload['references'][refpayloadid]=dict(reference_id=refkey[0],reference_version=refkey[1],
            points_1024x512=ref['points_1024x512'],traits=traits(ref['points_1024x512']),
            status=ref.get('status'),method=ref.get('method'),source_reference_ids=ref.get('source_reference_ids'))
        payload['objects'][r['object_id']]=dict(object_id=r['object_id'],image=r['image'],worker_id=r['worker_id'],
            points_1024x512=p,traits=tr,order_status=obj.get('order_status'),preprocessing_status=obj.get('preprocessing_status'),
            ordered_source_pair_indices=obj.get('ordered_source_pair_indices'),source=obj.get('source'),
            geometry_status=obj.get('geometry',{}).get('status'),reference_key=refpayloadid)
        components={k:q[k] for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100','full_score_state']}
        row={k:v for k,v in s.items() if k!='record'}
        row.update({k:r[k] for k in ['image_id','building','official_difficulty','scope','layer','condition','origin',
            'pool_id','reference_id','reference_version','source_active_time_seconds','target_time_seconds','B8L2','D10',
            'unmatched_ref_9','matched_pair_fraction','matched_boundary_abs_deg','omission','extension','ref_turn5','ref_short_edges']})
        row.update(components)
        row['pair_count']=len(p)//2;row['fold']=r['building'];row['label_source']=str(label_path.relative_to(ROOT))
        payload['slots'].append(dict(row,raw_record=r))
        record_rows.append(row)
    for im in selected_images:
        row=selected_groups.loc[im].to_dict();r0=next(s for s in payload['slots'] if s['image']==im)
        row.update(receipts[im]);row['group']='primary' if im in primary else 'cross_building_supplement'
        row['reference_key']=payload['objects'][r0['object_id']]['reference_key']
        floors=[np.array(o['traits']['floor_xz_h']) for o in payload['objects'].values() if o['image']==im]
        floors.append(np.array(payload['references'][row['reference_key']]['traits']['floor_xz_h']))
        a=np.concatenate(floors+[np.array([[0.,0.]])]);lo=a.min(0);hi=a.max(0);center=(lo+hi)/2;rad=max((hi-lo)/2)*1.12
        row['floor_bounds']=[center[0]-rad,center[0]+rad,center[1]-rad,center[1]+rad]
        payload['images'].append(row)
        for method,classes in METHODS.items():
            source=rfcenters if method.startswith('RFUSE') else centers
            for c in classes:
                sub=source[source.method.eq(method)&source.heldout_building.eq(row['building'])&source.class_id.eq(c)]
                assert len(sub)==1
                rr=sub.iloc[0]
                if method.startswith('TARGET'):
                    name='训练困难图转折同图残差中心';value=rr.m_hard_turn_n
                elif method.startswith('OPPJOINT'):
                    name='训练图 Q 同图残差中心';value=rr.m_all_B8L2
                else:
                    name='训练困难图融合转折响应系数中心';value=rr.hard_floor_turn5_n
                payload['centers'].append(dict(image=im,method=method,class_id=c,heldout_building=row['building'],
                    center_label=name,center_value=value,training_workers=int(rr.workers),interpretation=rr.interpretation))
    cframe=pd.DataFrame(candidates)
    cframe['feature_supplement']=cframe.object_id.eq(near['object_id'])&cframe.method.eq('TARGET_DSTRUCT_K3')
    cframe.to_csv(HERE/'SELECTION_RANKS.csv',index=False)
    record_frame=pd.DataFrame(record_rows)
    record_frame.to_csv(HERE/'SELECTED_RECORDS.csv',index=False)
    record_frame[record_frame.method.eq('OPPJOINT_K4')].to_csv(HERE/'JOINT_K4_SELECTED_RECORDS.csv',index=False)
    pd.DataFrame(payload['images']).to_csv(HERE/'SELECTED_IMAGES.csv',index=False)
    pd.DataFrame(payload['centers']).to_csv(HERE/'SELECTED_FOLD_CENTERS.csv',index=False)
    payload=clean(payload)
    (HERE/'EXAMPLE_DATA.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    originals=[objects[k] for k in payload['objects']]
    (HERE/'SOURCE_OBJECTS.json.gz').write_bytes(gzip.compress(json.dumps(originals,ensure_ascii=False,allow_nan=False).encode(),mtime=0))
    sourcefiles=[raw_path,label_path,quality_path,bundle_path,ref_path,center_path,rfcenter_path]
    manifest=dict(source_commit=HEAD,images=len(payload['images']),models=len(METHODS),slots=len(slots),typical_slots=len(slots)-1,feature_supplement_slots=1,
        unique_annotations=len(payload['objects']),source_files=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p),bytes=p.stat().st_size) for p in sourcefiles],
        verification=dict(current_reference_and_version_join=True,Q_D10_match_tolerance=1e-8,
            structure_counts_recomputed_from_current_coordinates=True,same_x_top_bottom=True,
            current_LOBO_only=True,Q_T_excluded_from_selection=True,
            original_three_method_image_selection_preserved=True,
            K4_singletons_shown_without_duplication=True,
            source_objects_unmodified=True,normalized_floor_units='camera_floor_height'))
    (HERE/'BINDING_AND_VERIFICATION.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['images','models','slots','unique_annotations']},ensure_ascii=False))
    print(pd.DataFrame(record_rows)[['image','method','class_id','worker_id','object_id','pair_count','turn_n','short_turn_edges','near_straight_nodes_5deg','B8L2','D10','source_active_time_seconds']].to_string(index=False))

if __name__=='__main__':main()
