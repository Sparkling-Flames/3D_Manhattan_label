"""用户确认新增真人数据的v2收件和库存审计；不授予评分或投票资格。"""
import argparse
import csv
import gzip
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/intake_W100_W134_20261019'
RELEASE=ROOT/'research/data/releases/v2'
NAMES=['annotations_label_studio_W100-W134.min.json','excluded_label_studio_W100-W134.min.json']
PREPROCESSING='shared_x_periodic_shortest_arc_v1'


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def geometry_checks(r):
    points=r['points_1024x512'];links=r['matterport_links_zero_based'];nxt=r['boundary_next_pair_indices']
    flags=[]
    valid=all(isinstance(p,list) and len(p)==2 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in p)
              and 0<=p[0]<1024 and 0<=p[1]<512 for p in points)
    if not valid:flags.append('invalid_coordinate')
    paired=all(isinstance(p,list) and len(p)==2 and all(isinstance(i,int) for i in p) for p in links)
    paired=paired and sorted(i for p in links for i in p)==list(range(len(points)))
    if not paired:flags.append('incomplete_or_repeated_pairing')
    n=len(links);cycle=isinstance(nxt,list) and len(nxt)==n and n>0 and all(isinstance(i,int) for i in nxt) and sorted(nxt)==list(range(n))
    if cycle:
        seen=[];i=0
        for _ in range(n):seen.append(i);i=nxt[i]
        cycle=len(set(seen))==n and i==0
    if not cycle:flags.append('not_single_boundary_cycle')
    if n<4:flags.append('fewer_than_four_pairs_review')
    gap=None
    if paired and valid:
        gap=max((abs((points[a][0]-points[b][0]+512)%1024-512) for a,b in links),default=0)
        if any(points[a][1]>=points[b][1] for a,b in links):flags.append('top_bottom_order_conflict')
    return flags,gap


def preprocess_record(r):
    flags,_=geometry_checks(r)
    blockers=[f for f in flags if f!='fewer_than_four_pairs_review']
    if r['geometry_status'] not in ('valid','below_four_pairs'):
        blockers.append('reported_'+r['geometry_status'])
    points=None
    if not blockers:
        try:
            points=shared_x(r['points_1024x512'],r['matterport_links_zero_based']).tolist()
        except ValueError as exc:
            blockers.append(str(exc))
    return dict(preprocessing=PREPROCESSING,preprocessing_status='blocked' if blockers else 'ready',
        preprocessing_blockers=blockers,preprocessed_points=points)


def audit(main,excluded,images):
    ids=[r['annotation_id'] for r in main+excluded]
    assert len(ids)==len(set(ids)),'duplicate annotation id'
    keys=[(r['worker_id'],r['image_id'],r['condition']) for r in main]
    assert len(keys)==len(set(keys)),'multiple retained submissions in same person/image/condition'
    mainkeys=dict(zip(keys,[r['annotation_id'] for r in main]));rows=[]
    for disposition,records in [('retained_user',main),('excluded_by_user',excluded)]:
        for r in records:
            assert r['image_id'] in images and images[r['image_id']]==r['image_code'],'image identity mismatch'
            assert r['condition'] in ['manual','semi'] and r['scope'] in ['in_scope','out_of_scope']
            flags,gap=geometry_checks(r);prepared=preprocess_record(r)
            t=r['active_time_seconds'];time_ok=isinstance(t,(int,float)) and math.isfinite(t) and t>0
            if not time_ok:flags.append('invalid_reported_active_time')
            k=(r['worker_id'],r['image_id'],r['condition'])
            rows.append(dict(data_release='v2',origin_release='new_batch_20261019',object_id='v2:new:'+str(r['annotation_id']),
                annotation_id=r['annotation_id'],image_id=r['image_id'],image_code=r['image_code'],worker_id=r['worker_id'],condition=r['condition'],
                disposition=disposition,exclusion_reason=r.get('exclusion_reason',''),scope_raw=r['scope'],
                scope_normalized='oos' if r['scope']=='out_of_scope' else 'in_scope',point_count=len(r['points_1024x512']),pair_count=len(r['matterport_links_zero_based']),
                geometry_status_reported=r['geometry_status'],geometry_review_flags='|'.join(flags),max_pair_x_gap_px=gap,
                preprocessing_status=prepared['preprocessing_status'],preprocessing_blockers='|'.join(prepared['preprocessing_blockers']),
                active_time_seconds=t,time_value_positive_finite=time_ok,time_provenance='user_processed_reported_not_raw_log_replayed',
                matching_retained_annotation_id=mainkeys.get(k) if disposition=='excluded_by_user' else None,
                quality_status='excluded_by_user' if disposition=='excluded_by_user' else 'not_scored_reference_and_eligibility_pending',
                initialization_kind=r.get('initialization_kind'),initialization_unchanged=r.get('initialization_unchanged'),
                known_error_unchanged=r.get('known_error_unchanged'),error_specific_outcome=r.get('error_specific_outcome')))
    return rows


def build(source):
    main,excluded=[read(source/n) for n in NAMES]
    with (ROOT/'research/difficulty/difficulty_current_20261017/image_metadata.csv').open(encoding='utf-8-sig') as f:
        images={r['image_id']:r['image'] for r in csv.DictReader(f)}
    rows=audit(main,excluded,images)
    with (ROOT/'research/data/releases/v1/records.csv').open(encoding='utf-8-sig') as f:old=list(csv.DictReader(f))
    assert not {r['worker_id'] for r in old}&{r['worker_id'] for r in rows}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'received').mkdir(exist_ok=True);RELEASE.mkdir(parents=True,exist_ok=True)
    for name in NAMES:
        target=OUT/'received'/name
        if target.exists():assert target.read_bytes()==(source/name).read_bytes(),'received source changed'
        else:shutil.copyfile(source/name,target)
    prepared=[]
    for r,row in zip(main+excluded,rows):
        result=preprocess_record(r)
        points=result['preprocessed_points']
        if points is not None:
            assert len(points)==len(r['points_1024x512'])
            assert [p[1] for p in points]==[p[1] for p in r['points_1024x512']]
            assert all(points[a][0]==points[b][0] for a,b in r['matterport_links_zero_based'])
            assert shared_x(points,r['matterport_links_zero_based']).tolist()==points
        prepared.append(dict(r,**result,object_id=row['object_id'],disposition=row['disposition'],
            quality_status=row['quality_status'],before_preprocessing_points=r['points_1024x512'],points_1024x512=points))
    with gzip.open(OUT/'preprocessed_annotations.json.gz','wt',encoding='utf-8') as f:
        json.dump(dict(schema='v2_new_batch_preprocessed_coordinates_v1',data_release='v2',objects=prepared),f,ensure_ascii=False,allow_nan=False)
    prep_summary=dict(schema='v2_new_batch_preprocessing_v1',method=PREPROCESSING,
        implementation='tools/thesis_main/analysis/shared_x_reanalysis_20260922.py:shared_x',
        base_effective_manifest='research/data/processed_input_review_20261018/manifest.json',
        coordinates='research/data/intake_W100_W134_20261019/preprocessed_annotations.json.gz',
        source_files=[(OUT/'received'/n).relative_to(ROOT).as_posix() for n in NAMES],
        records=len(prepared),ready=sum(r['preprocessing_status']=='ready' for r in prepared),
        retained_ready=sum(r['preprocessing_status']=='ready' and r['disposition']=='retained_user' for r in prepared),
        excluded_ready=sum(r['preprocessing_status']=='ready' and r['disposition']=='excluded_by_user' for r in prepared),
        retained_coordinates_changed=sum(r['disposition']=='retained_user' and r['preprocessing_status']=='ready'
            and r['points_1024x512']!=r['before_preprocessing_points'] for r in prepared),
        blocked_annotation_ids=[r['annotation_id'] for r in prepared if r['preprocessing_status']=='blocked'],
        invariants=['y unchanged','point count unchanged','provided pairing and boundary preserved','shared x equal','idempotent'],
        qualification='Preprocessing ready is not scoring or voting eligibility; exclusions and geometry review flags remain.')
    write(OUT/'PREPROCESSING.json',prep_summary)
    table(OUT/'record_audit.csv',rows)
    pools=defaultdict(list)
    for r in rows:pools[(r['image_id'],r['image_code'],r['condition'])].append(r)
    poolrows=[]
    for (iid,code,cond),rr in sorted(pools.items()):
        kept=[r for r in rr if r['disposition']=='retained_user']
        poolrows.append(dict(image_id=iid,image_code=code,condition=cond,retained_records=len(kept),retained_workers=len({r['worker_id'] for r in kept}),
            excluded_records=len(rr)-len(kept),reported_oos=sum(r['scope_normalized']=='oos' for r in kept),
            geometry_flagged=sum(bool(r['geometry_review_flags']) for r in kept)))
    table(OUT/'pool_inventory.csv',poolrows)
    fields=['data_release','origin_release','object_id','image_id','image_code','worker_id','condition','disposition','quality_status']
    membership=[dict(data_release='v2',origin_release='v1',object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],worker_id=r['worker_id'],
        condition=r['condition'],disposition=r['cleaning_disposition'],quality_status='inherited_v1_snapshot_not_v2_rescored') for r in old]
    membership += [{k:r[k] for k in fields} for r in rows]
    assert len({r['object_id'] for r in membership})==len(membership)
    table(RELEASE/'inventory.csv',membership)
    summary=dict(schema='new_worker_intake_20261019_v1',source_confirmation='user confirms new human annotations, not simulated; fields user processed',
        retained=len(main),excluded=len(excluded),new_workers=len({r['worker_id'] for r in rows}),new_images=len({r['image_id'] for r in rows}),
        annotation_ids_unique=True,retained_person_image_condition_unique=True,all_image_id_codes_match=True,
        excluded_with_retained_same_task=sum(r['matching_retained_annotation_id'] is not None for r in rows),
        retained_geometry_status=dict(Counter(r['geometry_status'] for r in main)),
        retained_geometry_flags=dict(Counter(f for r in rows if r['disposition']=='retained_user' for f in r['geometry_review_flags'].split('|') if f)),
        unequal_pair_x_records=sum((r['max_pair_x_gap_px'] or 0)>1e-9 for r in rows if r['disposition']=='retained_user'),
        preprocessing=prep_summary,
        new_batch_missing_existing_images=[images[i] for i in sorted(set(images)-{r['image_id'] for r in rows})],
        merged_inventory_records=len(membership),merged_workers=len({r['worker_id'] for r in membership}),merged_images=len({r['image_id'] for r in membership}),
        missing_provenance=['source project/task/submission timestamps and worker identity mapping','active-time collection rule and raw log linkage',
                            'semi initial geometry/reference and reviewed error evidence linkage','explicit final reference/scope binding for scoring'],
        note='Missing provenance does not discard user-processed data. Inventory admitted; scoring and time-source equivalence not certified.')
    write(OUT/'AUDIT.json',summary)
    release=dict(schema='research_data_release_inventory_v2',data_release='v2',created_on='2026-10-19',
        status='inventory_admitted_analysis_adapter_pending',membership='inventory.csv',
        base_release='research/data/releases/v1/RELEASE.json',base_effective_manifest='research/data/processed_input_review_20261018/manifest.json',
        new_batch=OUT.relative_to(ROOT).as_posix(),source_files=[(OUT/'received'/n).relative_to(ROOT).as_posix() for n in NAMES],
        new_batch_preprocessing_manifest=(OUT/'PREPROCESSING.json').relative_to(ROOT).as_posix(),
        counts=dict(inventory=len(membership),v1=len(old),new_retained=len(main),new_excluded=len(excluded),workers=summary['merged_workers'],images=summary['merged_images']),
        qualification='User exclusions preserved. New retained rows are not automatically quality usable or independent votes. Existing v1 exclusions remain.',
        executable_analysis_manifest=None,analysis_status='No v2 geometry scoring or personnel refit run; v1 results retain v1 identity.')
    if (RELEASE/'RELEASE.json').exists():
        existing=read(RELEASE/'RELEASE.json')
        if existing.get('executable_analysis_manifest'):
            assert existing['counts']==release['counts'] and existing['source_files']==release['source_files']
            release.update({k:existing[k] for k in ('status','executable_analysis_manifest','analysis_status')})
    write(RELEASE/'RELEASE.json',release)
    print(json.dumps(summary,ensure_ascii=True,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=OUT/'received');args=parser.parse_args();build(args.source)
