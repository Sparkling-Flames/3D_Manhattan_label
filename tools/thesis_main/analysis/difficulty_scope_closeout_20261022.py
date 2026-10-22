"""Close v2 difficulty evidence with target-compatible denominators, not new scores."""
import argparse
import gzip
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/difficulty/difficulty_mechanisms_v2_20261020'
SPEED = ROOT / 'research/difficulty/speed_difficulty_mechanisms_20261021'
OUT = BASE / 'scope_closeout_20261022'


def target_relation(reference_id, target_id):
    if not reference_id or not target_id:
        return 'missing_identity'
    return 'same_target' if reference_id == target_id else 'different_target'


def direction_counts(values):
    observed = values.dropna()
    return dict(images_total=len(values), images_observed=len(observed),
                images_missing=int(values.isna().sum()), negative=int((observed < 0).sum()),
                positive=int((observed > 0).sum()), tied=int((observed == 0).sum()))


def main(zip_path=None):
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz', 'rt', encoding='utf-8') as stream:
        records = json.load(stream)['records']
    rows = []
    for r in records:
        difficulty = r['image_evidence'].get('difficulty_record') or {}
        ref = r['reference_evidence'] or {}
        rows.append(dict(object_id=r['object_id'], image_id=r['image_id'], image=r['image_code'],
            condition=r['condition'], origin=r['origin'], is_oos=r['is_oos'], is_doorway=r['is_doorway'],
            layer='oos' if r['is_oos'] else 'doorway' if r['is_doorway'] else 'non_oos_non_doorway',
            coarse_class=difficulty.get('current_class'), target_id=difficulty.get('target_version'),
            reference_id=r['reference_id'], relation=target_relation(r['reference_id'], difficulty.get('target_version')),
            reference_full_available=r['reference_full_available'],
            payload_full_available=ref.get('full_reference_available'),
            quality_usable=r['quality_usable'], quality_use=r['quality_use'],
            legacy_top_boundary_pending=difficulty.get('top_boundary_pending')))
    d = pd.DataFrame(rows)
    assert d.object_id.is_unique
    d.to_csv(OUT/'record_scope_support.csv.gz', index=False, encoding='utf-8-sig')
    group = ['layer', 'is_doorway', 'condition', 'relation', 'quality_use', 'reference_full_available', 'payload_full_available']
    summary = d.groupby(group, dropna=False).agg(records=('object_id','size'), images=('image_id','nunique')).reset_index()
    summary.to_csv(OUT/'scope_compatibility.csv', index=False, encoding='utf-8-sig')
    image_rows = []
    for iid, f in d.groupby('image_id'):
        targets = f.target_id.dropna().unique()
        assert len(targets) <= 1
        same = f[f.relation.eq('same_target')]
        known = same.reference_full_available.dropna().unique()
        status = 'not_bound_in_inventory' if not len(same) else 'unknown' if not len(known) else 'mixed' if len(known)>1 else 'available' if bool(known[0]) else 'unavailable'
        image_rows.append(dict(image_id=iid, image=f.image.iloc[0], target_id=targets[0] if len(targets) else None,
            coarse_class=f.coarse_class.iloc[0], is_oos=f.is_oos.iloc[0], is_doorway=f.is_doorway.iloc[0],
            records=len(f), assigned_reference_count=f.reference_id.nunique(), same_target_records=len(same),
            different_target_records=int(f.relation.eq('different_target').sum()),
            missing_identity_records=int(f.relation.eq('missing_identity').sum()),
            target_full_status=status, current_target_quality_records=int(same.quality_usable.sum()),
            legacy_top_boundary_pending=None if f.legacy_top_boundary_pending.isna().all() else bool(f.legacy_top_boundary_pending.eq(True).any())))
    images = pd.DataFrame(image_rows)
    images.to_csv(OUT/'image_scope_support.csv', index=False, encoding='utf-8-sig')
    majority = []
    f = pd.read_csv(BASE/'image_mechanisms.csv')
    for mechanism, g in f[f.ref_turn5.eq(6)].groupby('mechanism'):
        majority.append(dict(analysis='fixed6_simplification', mechanism=mechanism,
            direction='positive means over half persons simplified', median_original_value=g.reduction_rate.median(),
            **direction_counts(g.reduction_rate-.5)))
    f = pd.read_csv(SPEED/'common_image_effects.csv')
    for mechanism, g in f[f.domain.eq('above_peer_Q')].groupby('mechanism'):
        majority.append(dict(analysis='highQ_common_speed', mechanism=mechanism,
            direction='negative means mean candidate minus base Q below zero', median_original_value=g.quality_difference.median(),
            **direction_counts(g.quality_difference)))
    pd.DataFrame(majority).to_csv(OUT/'majority_support.csv', index=False, encoding='utf-8-sig')
    pending = images[images.legacy_top_boundary_pending.eq(True)]
    coverage = dict(data_release='v2', inventory=len(d), images=len(images), non_oos_records=int((~d.is_oos).sum()),
        non_oos_images=int((~images.is_oos).sum()), formal_quality_records=int(d.quality_usable.sum()),
        formal_quality_same_target_records=int((d.quality_usable & d.relation.eq('same_target')).sum()),
        different_target_records=int(d.relation.eq('different_target').sum()), missing_identity_records=int(d.relation.eq('missing_identity').sum()),
        legacy_pending_images=len(pending), pending_target_full_status=pending.target_full_status.value_counts().to_dict(),
        labels_references_eligibility_unchanged=True)
    (OUT/'COVERAGE.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if zip_path is not None:
        archive = SPEED/'source_archive_20261022'
        archive.mkdir(parents=True,exist_ok=True)
        names = ['difficulty_summary.csv','speed_n5_historical_difficulty_pairs.csv']
        entries = []; existing = []
        with zipfile.ZipFile(zip_path) as z:
            for name in names:
                member = 'HOHONET_personnel_research_20261020/tables/speed/'+name
                raw = z.read(member)
                dest = archive/(name+'.gz')
                dest.write_bytes(gzip.compress(raw,mtime=0))
                assert gzip.decompress(dest.read_bytes()) == raw
                entries.append(dict(member=member, saved=dest.relative_to(ROOT).as_posix(), original_bytes=len(raw), compressed_bytes=dest.stat().st_size))
            for relative in ['mechanisms/scope_boundary_notes.md', 'tables/profiles/lobo_difficulty_features.csv',
                             'tables/profiles/worker_difficulty.csv', 'tables/quality/n7_difficulty_effects.csv',
                             'tables/speed/speed_n5_historical_difficulty_summary.csv']:
                member = 'HOHONET_personnel_research_20261020/'+relative
                dest = ROOT/'research/workers/personnel_profiles_composition_20261020/source'/relative
                same = dest.read_bytes() == z.read(member)
                assert same, relative
                existing.append(dict(member=member, existing=dest.relative_to(ROOT).as_posix(), same_bytes=True))
        manifest = dict(bundle='HOHONET_personnel_research_20261020.zip', entries=entries, retained_existing=existing,
            decision='Preserve two missing difficulty sources in topic; external ZIP unchanged; no file hashes computed',
            historical_not_current='Archived summaries use their own original supports; not substituted for fixed common-image results')
        (archive/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(coverage,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, help='Optional user-provided research ZIP, read-only')
    main(parser.parse_args().zip)
