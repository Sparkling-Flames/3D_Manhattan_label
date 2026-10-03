"""Read-only binding check against an exact current handoff.

No raw identity map, private corpus, reordering or preprocessing is used.
Coordinate hashes use compact UTF-8 JSON (not hashes of original files).
"""
import argparse, csv, hashlib, json, math
from pathlib import Path

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--returned',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    source=args.root/'analysis_results/layout_3d_quality_probe_20261002'
    d=json.loads((source/'results.json').read_text())
    input_data=json.loads((args.returned/'inputs/current_numeric_subset.json').read_text())
    objects={o['record']['id']:o for o in d['objects']}
    actual=read_csv(args.returned/'results/real_selected_metrics.csv')
    selected={r['annotation']:r for r in actual}
    csvs=read_csv(source/'metrics.csv')
    orig={(r['id'],r['reference_version']):r for r in csvs}
    sha=lambda x:hashlib.sha256(json.dumps(x,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    rows=[]; references=[]
    for im in input_data['images']:
        for r in im['annotations']:
            o=objects.get(r['id']); a=o['record'] if o else None
            row=dict(record_id=r['id'],used_in_six_comparisons=r['id'] in selected,present_in_source_objects=a is not None,returned_points_sha256=sha(r['points']))
            if a:
                row.update(source_image=o['image'],source_points_sha256=sha(a['points']),points_exact=r['points']==a['points'],returned_worker_alias=r['worker'],source_worker_alias=a['worker'],source_csv_aliases=sorted(set(x['worker'] for x in csvs if x['id']==r['id'])),source_real_aliases=sorted(set(x['a']['worker'] for x in d['real'] if x['id']==r['id'])),returned_source_point_indices=r['source_point_indices'],source_source_point_indices=a['source_point_indices'],point_indices_exact=r['source_point_indices']==a['source_point_indices'])
            else:
                row['exact_coordinate_matches_among_source_objects']=[o['record']['id'] for o in d['objects'] if o['record']['points']==r['points']]
            rows.append(row)
        for ref in im['references']:
            rs=next(r['b'] for r in d['real'] if r['image']==im['code'] and r['reference_version']==ref['version'])
            references.append(dict(returned_id=ref['id'],source_id=rs['id'],points_exact=ref['points']==rs['points'],points_sha256=sha(ref['points']),source_point_indices_exact=ref['source_point_indices']==rs['source_point_indices']))
    result=dict(source_commit=input_data['source']['commit'],source_results_git_blob=input_data['source']['blob_sha'],scope='Public aliases only, no real-identity resolution; no private mapping or full source bundle is read',input_annotation_count=len(rows),source_same_image_annotation_count=sum(o['image'] in [i['code'] for i in input_data['images']] for o in d['objects']),used_annotation_count=len(selected),records=rows,references=references)
    (args.out/'source_binding_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    rename={'bev_iou':'bev_iou','column_iou':'column_iou','current_model_volume_iou':'model_volume_iou','current_height_mean_a_h':'height_mean_h','current_height_rms_a_h':'height_rms_h','self_axis_rms_deg':'direction_self_rms_deg'}
    field_rows=[]
    for r in read_csv(args.returned/'inputs/read_upstream_csv_subset.csv'):
        a=orig[(r['annotation'],'original')]; b=selected[r['annotation']]
        for key,target in rename.items():
            if r[key]=='':
                field_rows.append(dict(id=r['annotation'],field=key,missing=(a[target]==b[key]==''))); continue
            x,y,z=float(r[key]),float(a[target]),float(b[key])
            field_rows.append(dict(id=r['annotation'],field=key,copied_exact=x==y,returned_error=abs(z-y),returned_close=math.isclose(z,y,rel_tol=1e-9,abs_tol=1e-10)))
    (args.out/'35_fields_current_source_binding.json').write_text(json.dumps(field_rows,indent=2)+'\n')
    print(json.dumps(dict(input_annotation_count=len(rows),used_annotation_count=len(selected),all_selected_points_exact=all(r.get('points_exact',False) for r in rows if r['used_in_six_comparisons']),source_point_index_mismatch_ids=[r['record_id'] for r in rows if r.get('point_indices_exact') is False],worker_alias_mismatch_ids=[r['record_id'] for r in rows if 'source_worker_alias' in r and r['source_worker_alias']!=r['returned_worker_alias']],unbound_ids=[r['record_id'] for r in rows if not r['present_in_source_objects']],available_numeric_fields=sum('copied_exact' in r for r in field_rows),all_copied_numeric_fields_exact=all(r.get('copied_exact',True) for r in field_rows),all_returned_numeric_fields_close=all(r.get('returned_close',True) for r in field_rows),max_returned_numeric_difference=max(r.get('returned_error',0) for r in field_rows)),indent=2))

if __name__=='__main__':main()
