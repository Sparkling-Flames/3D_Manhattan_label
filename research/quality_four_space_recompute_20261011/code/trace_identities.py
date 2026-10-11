from pathlib import Path
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);repo=Path(p.parse_args().repo)
 seed=json.loads((ROOT/'inputs/previous/editor_seed_data.json').read_text());frozen={r['record_id']:r for r in json.loads((ROOT/'inputs/frozen_components_20.json').read_text())};rows=[];selected=[];cache={}
 for a in seed['images'][0]['annotations']:
  src=a['source'];f=repo/src['path']
  if str(f) not in cache:cache[str(f)]=(f.read_bytes(),json.loads(f.read_text()))
  raw,tasks=cache[str(f)];assert isinstance(tasks,list)
  task=next(t for t in tasks if t['id']==src['task']);ann=next(t for t in task['annotations'] if t['id']==src['annotation']);assert int(ann['completed_by'])==int(a['worker_id'][1:])
  q=frozen[a['record_id']];metadata={k:v for k,v in ann.items() if k!='result'};choices=[v for v in ann['result'] if v.get('type')=='choices'];rows.append(dict(record_id=a['record_id'],object_id=a['object_id'],worker_id=a['worker_id'],condition=a['condition'],source_path=src['path'],source_file_sha256=hashlib.sha256(raw).hexdigest(),project=src['project'],task=src['task'],annotation=src['annotation'],ground_truth=ann['ground_truth'],was_cancelled=ann['was_cancelled'],parent_annotation=ann.get('parent_annotation'),parent_prediction=ann.get('parent_prediction'),prediction=ann.get('prediction'),created_at=ann['created_at'],declared_derivation='none_in_export_metadata' if not ann.get('parent_annotation') and not ann.get('parent_prediction') and not ann.get('prediction') else 'declared_parent_or_prediction_present',current_selected_points_sha256=a['current_points_sha256'],current_points_changed_from_prior=q['geometry_changed_from_old'],point_review_source=a.get('point_review_source'),cached_footprint_missing=a['footprint'] is None,independent_vote_eligible=q['independent_vote_eligible'],in_current_manual_pool=a['in_current_manual_pool'],main_consensus_gate=q['main_consensus_gate'],main_quality_gate=q['main_quality_gate'],primary_included=q['primary_included'],cleaning_disposition=q['cleaning_disposition'],primary_exclusion_reasons=q['primary_exclusion_reasons'],original_choices=choices))
  selected.append(dict(record_id=a['record_id'],source=src,source_file_sha256=hashlib.sha256(raw).hexdigest(),annotation=ann))
 assert len(rows)==20 and all(not r['ground_truth'] and not r['was_cancelled'] for r in rows)
 (ROOT/'results/object_identity_20.json').write_text(json.dumps({'objects':rows,'GT_or_derived_workbench_reference_objects_in_this_list':0,'manual_pool_records':sum(r['in_current_manual_pool'] for r in rows),'quality_primary_included_records':sum(r['primary_included'] for r in rows),'no_eligibility_changed':True},ensure_ascii=False,indent=2)+'\n')
 (ROOT/'inputs/selected_raw_annotation_evidence.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n');print('20 manual source annotations traced; no GT flags, no cancelled records; original gates preserved')
if __name__=='__main__':main()
