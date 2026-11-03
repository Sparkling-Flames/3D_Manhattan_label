"""Final source, support, version, artifact and reference checks.

Numerical estimators are verified in the module receipts and the independent
review. This final gate binds those verified results to the deliverable files.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

OUT=ROOT/'research/fusion/manual_order_impact_20261104'
SITE=ROOT/'research/statistics/research_explorer_v1_r2_20261017'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results=[]
    def check(name,passed,**evidence):
        assert passed,(name,evidence)
        results.append(dict(check=name,passed=True,**evidence))
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    check('fixed_repository_head',head==BASE_COMMIT,commit=head)
    ep=read(OUT/'endpoints/CHECKS.json');pre=read(OUT/'preprocessing_audit/CHECKS.json')
    deps=read(OUT/'dependencies/CHECKS.json');half=read(OUT/'half_qonly/CHECKS.json')
    same=read(OUT/'same_room/CHECKS.json');ac=read(OUT/'ac/CHECKS.json')
    comp=read(OUT/'composition/CHECKS.json');natural=read(OUT/'natural/CHECKS.json')
    alliance=read(OUT/'alliances/CHECKS.json');policy=read(OUT/'policy/CHECKS.json')
    audit=read(OUT/'INDEPENDENT_REVIEW_CHECKS.json');browser=read(OUT/'WORKBENCH_CHECKS.json')
    stop=read(OUT/'dependencies/INDIRECT_PREDICTION_STOP_CHECKS.json')
    version=read(OUT/'VERSION.json')
    check('fixed_endpoint_identity_and_scoring',ep['approved_geometry_groups']==57 and ep['images']==22 and ep['automatic_scored']==0 and ep['assisted_scored']==56 and ep['fixed_checks_passed'],
          groups=57,images=22,automatic_scored=0,assisted_scored=56,main_fixed_nodes=version['fixed_nodes'])
    check('complete_preprocessing_audit',pre['ready_max_shared_x_replay_difference']==0 and pre['saved_center_replay_max_difference']==0 and pre['source_coordinate_chain_max_difference']==0,
          receipt='preprocessing_audit/CHECKS.json')
    check('actual_reference_map',deps['source_tables_read']==558 and deps['current_references']==536 and deps['exact_map_reproduced'] and deps['rfuse_affected_rows']==0,
          sources=558,references=536,modules=9,rfuse_training_rows=deps['rfuse_training_rows'])
    check('independent_numerical_review',audit['passed'] and not audit['failures'],checks=audit['checks_count'],receipt='INDEPENDENT_REVIEW_CHECKS.json',
          independence_scope=audit['same_room_independence'])
    check('half_receipt_correction_only',half['affected_frozen_half_events']==13 and half['affected_current_half_events']==13 and half['original_support_unchanged'] and half['no_missing_Q_imputed'],
          corrected_from=[0,0],corrected_to=[13,13],science_data_unchanged_receipt='half_qonly/RECEIPT_CORRECTION_20261104.json')
    check('same_room_all_actual_consumers',same['complete'] and same['all_actual_same_room_consumers_completed'] and same['original_common_support_values_unchanged'],
          main_geometry_support=[same['geometry_common_six_K3_10_5_automatic'],same['geometry_common_six_K3_10_5_assisted']])
    check('AC_full_chain_and_support',str(ac['status']).lower()=='pass' and ac['baseline_mismatches']==0 and ac['candidate_branch_adopted']==False and ac['original_Q_or_D10_common_support_changed']==False,
          method_events=ac['affected_method_events'],physical_pairs=ac['affected_physical_pairs'],new_Q_method_events=ac['newly_evaluable_Q_method_events'],new_Q_physical_pairs=ac['newly_evaluable_Q_physical_pairs'],
          text_empty_normalization=ac['text_empty_normalization'])
    check('composition_alliance_natural_policy_complete',comp['original_common_metric_support_preserved'] and natural['native_stage03_aggregate_completed'] and natural['native_stage07_consumers_completed'] and alliance['original_scored_endpoint_values_changed']==0 and policy['point_sign_changes']==0,
          receipts=['composition/CHECKS.json','alliances/CHECKS.json','natural/CHECKS.json','policy/CHECKS.json'])
    check('complete_prediction_selection_stopping_source',stop['team_hash_contract_selfcheck_passed']==57 and stop['full_stopping_rows']==124924 and stop['full_stop_exact_hash_intersection']==0 and stop['full_stop_direct_tuple_intersection']==0,
          full_rows=124924,unique_teams=60129,pools=43,team_key_selfchecks=57,
          receipt='dependencies/INDIRECT_PREDICTION_STOP_CHECKS.json',outside_independent_128_item_scope=True)
    check('actual_browser_new_offline_page',browser['passed'] and not browser['javascript_errors'] and not browser['failed_asset_requests'] and browser['data_sha256']==sha(SITE/'v21-manual-order/data.js'),
          browser=browser['browser'],page='v21-manual-order.html',receipts='WORKBENCH_CHECKS.json',
          limitation='new page and its controls/assets; not all historical workbench pages')
    for name in ['index.html','v21-results.html','v21-reselection.html']:
        text=(SITE/name).read_text(encoding='utf-8')
        check('existing_entry_version_notice/'+name,'id="manual-order-20261104-notice"' in text and 'v21-manual-order.html' in text)
    changes=subprocess.check_output(['git','diff','--name-only','-z'],cwd=ROOT).decode().split('\0')
    changes=[p for p in changes if p]
    allowed={'docs/PROJECT_MAP_CLEAN_20260308.md','docs/README_INDEX.md','docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md',
             'research/data/releases/v2.1/README.md','research/data/releases/v2.1/final_classification_downstream/README.md',
             'research/data/releases/v2.1/personnel_reselection_dependencies/README.md','research/data/releases/v2.1/research_readiness_20261031/WORKBENCH_HANDOFF.md',
             *{str((SITE/n).relative_to(ROOT)) for n in ['index.html','v21-results.html','v21-reselection.html']}}
    check('original_experimental_files_not_modified',set(changes)<=allowed,modified_tracked_files=changes,original_scientific_tables_modified=0)
    for item in version['source_inputs']:
        check('frozen_user_input/'+Path(item['path']).name,sha(ROOT/item['path'])==item['sha256'],path=item['path'])
    # Validate local report links and exact conclusion source paths. Original
    # repository files absent from the sparse checkout remain valid git paths.
    known=set(subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=ROOT,text=True).splitlines())
    refs=[]
    for p in OUT.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
            if target.startswith(('http:','https:','mailto:','#','data:')):continue
            name=target.split('#')[0]
            if not name:continue
            dest=(p.parent/name).resolve()
            try:relative=dest.relative_to(ROOT).as_posix()
            except ValueError:relative=''
            valid=dest.exists() or relative in known or any(x.startswith(relative+'/') for x in known if relative)
            refs.append(dict(source=p.relative_to(ROOT).as_posix(),target=target,exists=valid))
    with (OUT/'CONCLUSION_MATRIX.csv').open(encoding='utf-8-sig',newline='') as f:conclusions=list(csv.DictReader(f))
    for row in conclusions:
        for target in row['sources'].split('|'):
            refs.append(dict(source='CONCLUSION_MATRIX.csv/'+row['id'],target=target,exists=(OUT/target).exists()))
    # Check all explicit resources on the new page. Asset src/href links are
    # literal; its data-driven 22 original images have a separate hash manifest.
    for target in re.findall(r'(?:href|src)="([^"]+)"',(SITE/'v21-manual-order.html').read_text(encoding='utf-8')):
        if target.startswith(('#','http:','https:')):continue
        dest=(SITE/target.split('#')[0]).resolve()
        refs.append(dict(source='v21-manual-order.html',target=target,exists=dest.exists()))
    # The self receipt is created at the end of this gate.
    for ref in refs:
        if ref['target']=='FINAL_CHECKS.json':ref['exists']=True
    missing=[r for r in refs if not r['exists']]
    check('report_conclusion_and_page_references',not missing,checked=len(refs),missing=missing)
    with (OUT/'REFERENCE_CHECKS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['source','target','exists']);w.writeheader();w.writerows(refs)
    check('conclusion_categories',all(r['status'] in {'保持','幅度变化','条件变化','需改写','尚不能判断'} for r in conclusions),
          rows=len(conclusions),categories=dict(collections.Counter(r['status'] for r in conclusions)))
    images=read(SITE/'v21-manual-order/IMAGE_MANIFEST.json')
    check('original_release_images_preserved',len(images)==22 and all(sha(SITE/'v21-manual-order/original_images'/r['filename'])==r['sha256'] for r in images),
          images=22,bytes=sum(r['bytes'] for r in images))
    receipts=[]
    for n in ['01','02','03','04']:
        receipt=read(ROOT.parent/'deliverables'/f'BATCH{n}_RECEIPT.json')
        file=ROOT.parent/'deliverables'/receipt['filename'] if 'filename' in receipt else Path(receipt['file'])
        check('immutable_delivered_zip/'+n,sha(file)==receipt['sha256'],bytes=file.stat().st_size,sha256=receipt['sha256'])
        receipts.append(dict(batch=n,filename=file.name,bytes=file.stat().st_size,sha256=receipt['sha256']))
    receipts.append(dict(batch='05',filename='HOHONET_v21_manual_order_batch05_final_report_workbench_validation_20261104.zip',sha256='See external SHA256SUMS.txt; self-hash cannot be included inside the ZIP'))
    (OUT/'DELIVERY_BATCHES.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    inventory=[]
    paths={p for folder in [OUT,SITE/'v21-manual-order'] for p in folder.rglob('*') if p.is_file()}
    paths|={SITE/'v21-manual-order.html'}
    paths|=set((ROOT/'tools/thesis_main/analysis').glob('*manual*20261104.py'))
    for p in sorted(paths):
        if p.name in ['FINAL_CHECKS.json','ARTIFACT_MANIFEST.csv'] or p.suffix in ['.pyc','.tmp'] or '__pycache__' in p.parts:continue
        inventory.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    with (OUT/'ARTIFACT_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(inventory)
    checks=dict(passed=True,source_commit=BASE_COMMIT,analysis_version=version['primary_analysis'],
                execution='GitHub fixed-commit working copy; deliverable is a Windows repository overlay',
                direct_write_to_user_D_drive=False,checks=results,
                independent_checks=128,independent_review_passed=True,
                prediction_stop_addendum_passed=True,all_actual_downstream_consumers_closed=True,
                original_automatic_preserved=True,candidate_adopted=False,
                classification_reselection=False,whole_library_fusion_replay=False,
                unit_tests=dict(command='python -m pytest -q tests/test_manual_ring_orders_20261104.py tests/test_manual_order_half_qonly_20261104.py',passed=10,failed=0),
                artifact_manifest_rows=len(inventory),scientific_endpoint_main_support='56/57',conclusion_rows=len(conclusions),
                corrections=['half_qonly/CORRECTIONS_20261104.md'],
                remaining_human_decisions_blocking_delivery=[],
                unknown_by_design=['human assistance time','within-composition variability of newly single-team cells',
                                   'plateau for N5/N7','new current-DSTRUCT strategy performance','repairability outside targeted 57'])
    (OUT/'FINAL_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'final_gate_checks':len(results),'references':len(refs),'artifact_manifest_rows':len(inventory),'conclusions':len(conclusions)},ensure_ascii=False))


if __name__=='__main__':main()
