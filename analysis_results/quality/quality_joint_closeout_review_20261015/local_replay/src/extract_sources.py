from pathlib import Path
import zipfile,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'source'
manifest=[]
def extract(zipname,member,out):
 z=zipfile.ZipFile(zipname); b=z.read(member);p=OUT/out;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 manifest.append(dict(path=out,archive=str(zipname),member=member,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
a=Path('/mnt/data/library/quality_multispace_joint_calibration_20261013.zip');p='quality_multispace_joint_calibration_20261013/'
for m,out in [('calibration/inputs/search_inputs.json','search_922.json'),('baseline/inputs/calibration_records.json','calibration_922.json'),('routing/inputs/prepared_input.json','routing_prepared.json'),('routing/results/routes.json','routing_429.json'),('routing/results/all_candidate_metrics.json','route_candidate_metrics.json'),('sources/routing/research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json','reference_exclusions.json'),('sources/main/research/quality_parallel_local_20261012/fusion_rescore.json','fusion_220_old.json'),('integration/results/fusion_geometries_60.json','fusion_60_geometries.json')]:extract(a,p+m,out)
a=Path('/mnt/data/library/quality_top_structure_research_20261012_repaired_v1.zip');p='quality_top_structure_research_20261012/'
for m,out in [('study_severe/results/ledger_115.json','severe_screen_115.json'),('previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010/results/room_holdout_manifest.csv','holdout_3152.csv'),('new_main_snapshot/research/quality_severe_feedback_20261011/feedback_overlay.json','severe_feedback.json')]:extract(a,p+m,out)
a=Path('/mnt/data/library/quality_parameter_calibration_20261012.zip');extract(a,'quality_parameter_calibration_20261012/inputs/current_formal_loader_data.json','historical_current_formal_loader_data.json')
# Extract exact historical fusion source snapshots. They are not current assignments.
a=Path('/mnt/data/library/quality_multispace_joint_calibration_20261013.zip');z=zipfile.ZipFile(a)
for m in z.namelist():
 if '/sources/fusion/' in m and m.endswith('.json'):extract(a,m,'fusion_sources/'+m.split('/sources/fusion/')[1])
(OUT/'archive_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('Extracted',len(manifest),'files',sum(x['bytes'] for x in manifest))
for n in ['reference_exclusions.json','severe_feedback.json','fusion_220_old.json','routing_prepared.json']:
 d=json.loads((OUT/n).read_text(encoding='utf-8-sig'));print(n,d.keys() if isinstance(d,dict) else len(d))
