"""Read-only audit of a research-exclusion registry against its formal input checkout.

Usage:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/path/to/existing/dependencies \\
    python verify_registry.py --repo /path/to/3D_Manhattan_label

The supplied repo must materialize the manifest, frozen input and documented quality
update. Install nothing and mutate nothing. The caller supplies its normal research
runtime (including shapely). A different input revision requires a fresh audit;
source-hash mismatches are errors, not instructions to overwrite the data.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--registry',type=Path,default=Path(__file__).with_name('reference_exclusion_registry_20261010.json'))
    args=ap.parse_args()
    root=args.repo.resolve()
    registry=json.loads(args.registry.read_text(encoding='utf-8'))
    for source in registry['source_files']:
        assert hashlib.sha256((root/source['path']).read_bytes()).hexdigest()==source['sha256'], 'source hash changed: '+source['path']
    sys.path.insert(0,str(root))
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    b=load_current_bundle()
    assert b['validation']['status']=='passed'
    objects={x['object_id']:x for x in b['data']['objects']}
    images={x['image_id']:x for x in b['data']['images']}
    annotations=[x for x in objects.values() if x['object_kind']=='annotation']
    checked=0
    fields=['confirmed_reference_exclusions','preserved_user_analysis_holds',
            'reference_evidence_conflicts_primary_research_quarantine',
            'nonautomatic_review_cases','version_resolved_not_global_exclusion']
    for field in fields:
        for row in registry[field]:
            image=images[row['image_id']]
            assert image['image_code']==row['image_code']
            actual=dict(Counter(x['worker_quality_gate'] for x in annotations if x['image_id']==row['image_id']))
            assert actual==row['current_personnel_quality_gate_counts'],row['image_code']+' personnel gate changed'
            for version in row['gt_versions']:
                gt=objects[version['gt_object_id']]
                assert image['references'][version['version']]==gt['object_id']
                assert gt['image_id']==row['image_id']
                assert gt['object_kind']==version['version']
                assert gt['worker_quality_gate']==version['observed_gt_object_worker_quality_gate']
                coordinate_hash=hashlib.sha256(json.dumps(gt.get('points_1024x512'),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                assert coordinate_hash==version['coordinates_sha256']
            assert row['new_research_use']['change_formal_loader_or_gate'] is False
            assert row['new_research_use']['change_raw_data_coordinates_or_other_eligibility'] is False
            checked+=1
    assert len(registry['confirmed_reference_exclusions'])==8
    assert len({v['gt_object_id'] for x in registry['confirmed_reference_exclusions'] for v in x['gt_versions']})==9
    assert len(registry['preserved_user_analysis_holds'])==2
    for code in ['x8F5xyUWy9e-09','jtcxE69GiFV-10']:
        row=next(x for x in registry['nonautomatic_review_cases'] if x['image_code']==code)
        assert row['new_research_use']['exclude_this_reference_from_primary_gt_quality_comparison'] is False
    assert registry['consumer_contract']['registry_applied_in_actual_new_research_run'] is False
    print(json.dumps(dict(status='passed',checked_registry_images=checked,
                         checked_source_files=len(registry['source_files']),
                         loader_validation=b['validation'],
                         mutated_input=False),ensure_ascii=False,indent=2))
if __name__=='__main__':
    main()
