#!/usr/bin/env python3
"""Join unchanged v2 image difficulty/target/structure evidence for prefix analysis.

No labels, qualification flags or reference geometry are inferred from study outcomes.
"""
from pathlib import Path
import argparse, gzip, json, os
import numpy as np
import pandas as pd


def save_csv(df, path):
    path = Path(path)
    raw = df.to_csv(index=False).encode('utf-8')
    if path.suffix == '.gz':
        raw = gzip.compress(raw, mtime=0)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)
    assert len(pd.read_csv(path)) == len(df)


def main(repo, output, commit):
    repo, output = Path(repo), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rel = 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    rows = json.load(gzip.open(repo/rel, 'rt'))['records']
    droot = repo/'research/difficulty/difficulty_mechanisms_v2_20261020'
    scope = pd.read_csv(droot/'scope_closeout_20261022/image_scope_support.csv')
    ref = pd.read_csv(droot/'reference_conditions.csv')
    first = {}
    for r in rows:
        first.setdefault(r['image_id'], r)
    im = []
    rec = []
    for image_id, r in first.items():
        d = r['image_evidence'].get('difficulty_record', {})
        flags = d.get('reference_flags') or {}
        im.append(dict(
            image_id=image_id, image=r['image_code'], building=r['building_id'],
            room_id=r.get('room_id'), difficulty_coarse=r.get('current_class'),
            difficulty_conditional=d.get('conditional_difficulty'),
            difficulty_main_eligible=d.get('difficulty_analysis_eligible'),
            difficulty_grade_known=d.get('conditional_difficulty') in ('简单','中等','困难'),
            difficulty_basis=d.get('classification_basis'),
            inference_burden=d.get('inference_burden'),
            hidden_geometry_interpretation=d.get('H_interpretation'),
            image_layer='OOS' if r['is_oos'] else ('doorway' if r['is_doorway'] else 'non_doorway'),
            target_id=d.get('target_version'),
            target_N_floor=d.get('N_floor'), target_N_turn=d.get('N_turn'), target_H=d.get('H'),
            reference_status=d.get('reference_status'),
            gt_error_excluded=d.get('gt_error_excluded'),
            gt_detail_omission_mark=flags.get('gt_detail_omission_mark'),
            scope_semantics=d.get('scope_semantics'),
            visual_evidence=d.get('old_visual_evidence'),
            visual_space=r['image_evidence'].get('main_visual_space'),
            expected_annotation_extent=r['image_evidence'].get('expected_annotation_extent'),
            picture_source=d.get('photo'),
        ))
    image = pd.DataFrame(im).merge(scope.drop(columns=['image','target_id']),on='image_id',how='left',validate='one_to_one')
    image = image.merge(ref, left_on='target_id',right_on='reference_id',how='left',validate='many_to_one')
    image['structure_opportunity'] = np.select(
        [image.ref_H.gt(0), image.ref_H.eq(0)&image.ref_short_edges.gt(0), image.ref_H.eq(0)&image.ref_short_edges.eq(0)],
        ['geometric_self_occlusion','short_edge_H0','plain_H0'], default='unknown')
    image['fixed_six_turn_opportunity'] = image.ref_turn5.eq(6)
    save_csv(image.sort_values('image'), output/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv')

    for r in rows:
        b = r.get('binding_evidence') or {}
        rec.append(dict(image_id=r['image_id'],image=r['image_code'],condition=r['condition'],
            worker=r['worker_id'],object_id=r['object_id'], reference_id=r.get('reference_id'),
            target_id=b.get('current_target_id'), current_target_match=b.get('chosen_target_is_current'),
            pool_analysis_eligible=r['pool_analysis_eligible'],independent_vote_eligible=r['independent_vote_eligible'],
            quality_usable=r['quality_usable'],quality_use=r['quality_use'],reference_full_available=r.get('reference_full_available'),
            is_oos=r['is_oos'],is_doorway=r['is_doorway'],
            source_active_time_seconds=r.get('source_active_time_seconds'),
            target_matched_time_seconds=r.get('target_matched_time_seconds'),
            time_source=(r.get('time_evidence') or {}).get('source_kind'),
            time_status=(r.get('time_evidence') or {}).get('source_status'),
        ))
    rdf=pd.DataFrame(rec)
    save_csv(rdf,output/'RECORD_ELIGIBILITY_TIME_LINK.csv.gz')
    pools=[]
    for (iid,condition),g in rdf.groupby(['image_id','condition']):
        p=g[g.pool_analysis_eligible & g.independent_vote_eligible & ~g.is_oos]
        pools.append(dict(image_id=iid,image=g.image.iloc[0],condition=condition,
            inventory_records=len(g),inventory_workers=g.worker.nunique(),
            retained_nonOOS_pool_records=len(p),retained_nonOOS_pool_workers=p.worker.nunique(),
            quality_usable_records=int(g.quality_usable.sum()),quality_usable_pool_records=int(p.quality_usable.sum()),
            complete_reference_pool_records=int(p.reference_full_available.sum()),
            current_target_match_pool_records=int(p.current_target_match.fillna(False).sum()),
            target_time_known_pool_records=int(p.target_matched_time_seconds.notna().sum()),
            source_time_known_pool_records=int(p.source_active_time_seconds.notna().sum()),
            target_time_sum_seconds=p.target_matched_time_seconds.sum(min_count=1),
            source_time_sum_seconds=p.source_active_time_seconds.sum(min_count=1),
            pool_workers='|'.join(sorted(p.worker.unique())),
        ))
    pool=pd.DataFrame(pools).merge(image[['image_id','building','image_layer','difficulty_coarse','difficulty_conditional','structure_opportunity','target_full_status']],on='image_id',how='left',validate='many_to_one')
    save_csv(pool.sort_values(['condition','image']),output/'POOL_DIFFICULTY_SUPPORT.csv')
    counts=pool.assign(pool_present=pool.retained_nonOOS_pool_workers.ge(3)).groupby(['condition','image_layer','difficulty_conditional'],dropna=False).agg(
        inventory_images=('image','nunique'),pool_images=('pool_present','sum'),
        pool_worker_records=('retained_nonOOS_pool_workers','sum'),
        quality_records=('quality_usable_pool_records','sum'),
        time_known_records=('target_time_known_pool_records','sum')).reset_index()
    save_csv(counts,output/'DIFFICULTY_SUPPORT_COUNTS.csv')
    manifest={'commit':commit,'data_version':'v2','new_fusion':0,
        'sources':[rel,'research/difficulty/difficulty_mechanisms_v2_20261020/reference_conditions.csv','research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv'],
        'images':len(image),'records':len(rdf),'image_condition_inventory_pools':len(pool),
        'nonOOS_retained_pool_min3':int(pool.retained_nonOOS_pool_workers.ge(3).sum()),
        'rules':'Existing pool flag, independent vote eligibility and OOS status retained; pool count is inventory support, not certification that every pool is a formal quality pool. Prefix run follows engine registration. Doorway conditional unknown remains unknown; non-doorway special and reference-incomplete records do not acquire scoring qualification.'}
    (output/'ANNOTATION_RECEIPT.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--repo',required=True);a.add_argument('--out',required=True);a.add_argument('--commit',required=True)
    args=a.parse_args();main(args.repo,args.out,args.commit)
