"""修复官方类别连接并复用既有曲线作描述；不推断房间实例或停止人数。"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.data_prep.inventory_annotation_research_assets_20260905 import _aligned_pano_region_records

OFFICIAL=Path('D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official')
OUTPUT='analysis_results/scene_similarity_revision_20260909_v1/core'
CLOUD='analysis_results/uncertainty_cloud_inputs_20260906_v1'
PREV='analysis_results/building_convergence_evidence_20260908_v1'
OLD='analysis_results/order_free_cluster_holdout_20260908_v1'
META=['context_key','image_id','building_id','stage','block_index','raw_condition','initialization_kind']


def js(x):return json.dumps(x,ensure_ascii=False)
def read(p):return pd.read_csv(p,dtype=str,keep_default_na=False)


def mapping_row(image_id,values):
    return dict(image_id=image_id,class_values_json=js(sorted(values,key=int)),
                class_code=next(iter(values)) if len(values)==1 else '',class_name='',
                mapping_status='mapped_numeric_class' if len(values)==1 else 'conflict' if values else 'missing',
                class_name_status='unverified_numeric_dictionary',room_instance_id='',
                room_instance_status='missing_official_instance_link',position_x='',position_y='',position_z='',
                position_status='missing_official_panorama_position')


def compare_pair(a,b):
    for f in (a,b):
        if f.duplicated(['replicate','k']).any():raise ValueError('duplicate_replicate_node')
    shared=sorted(set(a.replicate)&set(b.replicate))
    r=dict(shared_replicates=len(shared),shared_replicates_json=js(shared),status='comparable' if shared else 'no_shared_replicates',curve_distance=np.nan)
    if shared:
        aa=a[a.replicate.isin(shared)];bb=b[b.replicate.isin(shared)]
        if set(map(tuple,aa[['replicate','k']].to_numpy()))!=set(map(tuple,bb[['replicate','k']].to_numpy())):
            raise ValueError('different_replicate_nodes')
        av=aa.groupby('k').value.mean();bv=bb.groupby('k').value.mean()
        r['curve_distance']=float((av-bv).abs().mean())
    return r


def run(root,out,official):
    out.mkdir(parents=True,exist_ok=True);(out/'sources').mkdir(exist_ok=True)
    def save(name,rows):pd.DataFrame(rows).to_csv(out/name,index=False,float_format='%.12g')
    images=read(root/CLOUD/'images.csv');assert images.image_id.is_unique
    ids=set(images.image_id);mapping=defaultdict(set);sources=defaultdict(set);evidence=[];source_rows=[]
    for split in ['train','test']:
        for kind in ['pano','single']:
            image_path=official/f'tasks/region_classification/data/{split}_room_{kind}_image.txt'
            label_path=image_path.with_name(image_path.name.replace('_image.txt','_label.txt'))
            if not image_path.exists() or not label_path.exists():
                raise FileNotFoundError(f'missing aligned source pair: {image_path}, {label_path}')
            records,status=_aligned_pano_region_records(image_path,label_path)
            if status!='aligned_pano_region_class':raise ValueError(status)
            for path in [image_path,label_path]:
                shutil.copyfile(path,out/'sources'/path.name)
                source_rows.append(dict(file=path.name,local_source=str(path),bytes=path.stat().st_size,
                    lines=len(path.read_text(encoding='utf-8-sig').splitlines()),split=split,kind=kind,status=status,
                    official_url='https://github.com/niessner/Matterport/blob/master/tasks/region_classification/data/'+path.name))
            for line,(image_id,label) in enumerate(records,1):
                if image_id not in ids:continue
                value=label.split(':',1)[1];mapping[image_id].add(value);sources[image_id].add(image_path.name)
                evidence.append(dict(image_id=image_id,class_code=value,source_image_file=image_path.name,source_label_file=label_path.name,line_number=line,source_split=split,source_kind=kind))
    mapped=pd.DataFrame([mapping_row(i,mapping[i])|dict(source_image_files_json=js(sorted(sources[i]))) for i in images.image_id])
    mapped=images[['image_id','building_id','split','population_role']].merge(mapped,on='image_id',validate='one_to_one')
    save('images_380.csv',mapped);save('source_files.csv',source_rows);save('mapping_evidence.csv.gz',evidence)
    old=read(root/'analysis_results/annotation_research_decision_audit_20260905_v1/inventory/room_region_mapping_records.csv')
    oldmap=old.groupby('image_id').region_class.agg(set).to_dict();diff=[]
    for r in mapped.to_dict('records'):
        before=oldmap.get(r['image_id'],set());after=mapping[r['image_id']]
        diff.append(dict(image_id=r['image_id'],population_role=r['population_role'],old_values_json=js(sorted(before)),
            new_values_json=js(sorted(after)),change='unchanged' if before==after else 'newly_connected' if not before else 'changed_or_conflict'))
    save('mapping_diff.csv',diff)
    a=read(root/CLOUD/'annotations.csv.gz');assert a.canonical_annotation_id.is_unique
    contexts=read(root/PREV/'review/context_coverage.csv')
    contexts=contexts.merge(mapped[['image_id','class_code','mapping_status']],on='image_id',validate='many_to_one')
    support=read(root/PREV/'review/context_split_coverage.csv');support=support[support.scheme=='two_thirds']
    contexts=contexts.merge(support[['context_key','available_splits','window_5_support_splits','window_8_support_splits','window_15_support_splits']],on='context_key',validate='one_to_one')
    for c in ['raw_workers','computable_workers','raw_versions','available_splits','window_5_support_splits','window_8_support_splits','window_15_support_splits']:contexts[c]=pd.to_numeric(contexts[c])
    save('historical_context_support.csv',contexts)
    keys=['stage','block_index','raw_condition','initialization_kind','class_code','mapping_status']
    coverage=contexts.groupby(keys,dropna=False).agg(images=('image_id','nunique'),contexts=('context_key','nunique'),buildings=('building_id','nunique'),
        canonical_responses=('raw_workers','sum'),minimum_workers=('raw_workers','min'),maximum_workers=('raw_workers','max'),
        contexts_window15=('window_15_support_splits',lambda x:int((x>0).sum())),window15_support_splits=('window_15_support_splits','sum')).reset_index()
    save('class_stage_coverage.csv',coverage)
    curves=read(root/PREV/'review/context_curves.csv.gz').merge(mapped[['image_id','class_code','mapping_status']],on='image_id',validate='many_to_one')
    save('curve_support.csv.gz',curves)
    masks=read(root/PREV/'core/fixed_window_membership.csv.gz')
    masks=masks[(masks.stage=='P1')&(masks.block_index=='0')&(masks.raw_condition=='manual')&
        (masks.config=='ospa30_t6')&(masks.scheme=='two_thirds')&(masks.max_k=='15')&
        (masks.path=='full_history_fixed')&(masks.measure=='distribution_tv')]
    allowed={r.context_key:set(json.loads(r.valid_split_ids_json)) for r in masks.itertuples()}
    rows=[]
    for chunk in pd.read_csv(root/OLD/'fixed_taxonomy_prefixes.csv.gz',chunksize=30000):
        z=chunk[(chunk.stage=='P1')&(chunk.raw_condition=='manual')&(chunk.config=='ospa30_t6')&
                (chunk.scheme=='two_thirds')&chunk.k.isin([3,5,8,10,12,15])]
        for r in z.to_dict('records'):
            if r['split_id'] in allowed.get(r['context_key'],set()):
                rows.append({k:r[k] for k in META+['split_id','replicate','k']}|dict(value=float(r['distribution_tv'])))
    values=pd.DataFrame(rows);save('pair_curve_inputs.csv.gz',values)
    assert len(values)==sum(len(s)*6 for s in allowed.values())
    cmeta=contexts.set_index('context_key').to_dict('index');groups={c:g for c,g in values.groupby('context_key')};pairs=[]
    # Same common-replicate curve arithmetic as the previous comparator; all supported
    # images enter here, including singleton buildings, because the grouping question changed.
    for left,right in combinations(sorted(groups),2):
        a0,b0=cmeta[left],cmeta[right];lc,rc=a0['class_code'],b0['class_code']
        pairs.append(dict(left_context=left,right_context=right,left_image=a0['image_id'],right_image=b0['image_id'],
            left_building=a0['building_id'],right_building=b0['building_id'],left_class=lc,right_class=rc,
            stage='P1',block_index='0',raw_condition='manual',initialization_kind=a0['initialization_kind'],
            scheme='two_thirds',config='ospa30_t6',max_k=15,path='full_history_fixed',measure='distribution_tv',
            class_relation='unknown' if not lc or not rc else 'same_numeric_class' if lc==rc else 'different_numeric_class',
            building_relation='same_building' if a0['building_id']==b0['building_id'] else 'different_building',
            **compare_pair(groups[left],groups[right])))
        assert a0['initialization_kind']==b0['initialization_kind']
    pairframe=pd.DataFrame(pairs);save('class_pair_curves.csv',pairframe)
    previous=read(root/PREV/'review/matched_image_pair_distances.csv.gz')
    previous=previous[(previous.stage=='P1')&(previous.raw_condition=='manual')&(previous.block_index=='0')&
        (previous.config=='ospa30_t6')&(previous.scheme=='two_thirds')&(previous.max_k=='15')]
    overlap=pairframe.merge(previous[['left_context','right_context','status','curve_distance','shared_replicates']],
        on=['left_context','right_context'],suffixes=('','_old'),validate='one_to_one')
    assert len(overlap)==len(previous) and (overlap.status==overlap.status_old).all()
    assert (overlap.shared_replicates==pd.to_numeric(overlap.shared_replicates_old)).all()
    errors=(overlap.curve_distance-pd.to_numeric(overlap.curve_distance_old,errors='coerce')).abs()
    assert errors.dropna().max()<1e-10
    summaries=[]
    for cr in ['same_numeric_class','different_numeric_class','unknown']:
        for br in ['same_building','different_building']:
            g=pairframe[(pairframe.class_relation==cr)&(pairframe.building_relation==br)]
            valid=g[g.status=='comparable'].copy()
            valid['building_unit']=[js(sorted((x,y))) for x,y in zip(valid.left_building,valid.right_building)]
            units=valid.groupby('building_unit').curve_distance.mean()
            summaries.append(dict(class_relation=cr,building_relation=br,total_pairs=len(g),valid_pairs=len(valid),
                images=len(set(valid.left_image)|set(valid.right_image)),buildings=len(set(valid.left_building)|set(valid.right_building)),
                building_units=len(units),pair_equal_mean=valid.curve_distance.mean(),building_unit_equal_mean=units.mean(),
                minimum_shared_replicates=valid.shared_replicates.min(),maximum_shared_replicates=valid.shared_replicates.max(),
                total_pair_replicate_occurrences=int(valid.shared_replicates.sum()),
                unique_replicates=len(set(v for x in valid.shared_replicates_json for v in json.loads(x))),
                status='available_descriptive_only' if len(valid) else 'no_comparable_pairs'))
    save('class_pair_summary.csv',summaries)
    missing=[]
    for b,g in mapped.groupby('building_id'):
        missing.append(dict(building_id=b,images=len(g),historical_images=int((g.population_role=='historical_annotated').sum()),
            candidate_images=int((g.population_role!='historical_annotated').sum()),required_relative_file=f'{b}/house_segmentations/{b}.house',
            status='not_found_in_checked_local_sources',required_fields='panorama UUID -> region_index; R label; panorama px/py/pz',
            region_instance_key='building_id + region_index',mesh_required=False))
    save('missing_house_files.csv',missing)
    qa=dict(status='passed',images=len(mapped),canonical=len(a),contexts=len(contexts),
        coverage={role:dict(total=len(g),mapped=int((g.mapping_status=='mapped_numeric_class').sum()),missing=int((g.mapping_status=='missing').sum()),conflict=int((g.mapping_status=='conflict').sum())) for role,g in mapped.groupby('population_role')},
        source_files=len(source_rows),source_bytes=sum(r['bytes'] for r in source_rows),evidence_rows=len(evidence),
        changed_mapping_counts=pd.DataFrame(diff).change.value_counts().to_dict(),instance_links=0,position_links=0,missing_house_buildings=len(missing),
        pair_contexts=len(groups),pair_rows=len(pairframe),pair_input_rows=len(values),curve_support_rows=len(curves),
        prior_pair_overlap=len(overlap),prior_pair_max_rounding_difference=float(errors.max()),
        pair_arithmetic='mean_k(abs(mean_shared_replicates(left)-mean_shared_replicates(right)))',
        pair_population='all supported P1 Manual images; no minimum two images per building filter',
        class_names_verified=False,stopping_rule_defined=False,new_image_prediction_validated=False)
    (out/'RUN_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False))
    return qa


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path);p.add_argument('--official-root',type=Path,default=OFFICIAL)
    args=p.parse_args();run(args.root,args.out or args.root/OUTPUT,args.official_root)
