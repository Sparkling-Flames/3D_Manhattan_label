"""Read-only, source-defined local area probes and path-to-boundary distances.
The closing chord only defines a diagnostic patch; it is NOT a replacement
edge, new annotation, ground truth, or vote. No consensus is recomputed here.
"""
from pathlib import Path
import json, argparse
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon, LineString, shape, mapping
from analyze import roster

def path_measure(path, boundary, n=512):
    t=(np.arange(n)+.5)/n
    d=shapely.distance(shapely.line_interpolate_point(path,t,normalized=True),boundary)
    return dict(path_mean_h=float(np.mean(d)),path_p95_h=float(np.quantile(d,.95)),
                path_sampled_max_h=float(max(d)),samples=n,path_length_h=path.length,
                sampled_max_upper_error_bound_h=path.length/(2*n))

def run(source,result_dir,spec_file):
    source=Path(source);rd=Path(result_dir)
    ims={i['code']:i for i in json.loads((source/'cases.json').read_text())['images']}
    specs=json.loads(Path(spec_file).read_text())
    regs={(f['properties']['image'],f['properties']['method']):shape(f['geometry'])
          for f in json.loads((rd/'full_consensus.geojson').read_text())['features']}
    rows=[];fractions=[];features=[];samples=[]
    for code,s in specs.items():
        recs=roster(ims[code]);target=next(r for r in recs if r['id']==s['id'])
        points=np.array(target['footprint']);inds=s['indices']
        patch_indices=inds if code.startswith('rPc') else [10,11,12]
        patch=Polygon(points[patch_indices]);assert patch.is_valid and patch.area>0
        A=Polygon(target['footprint']);path=LineString(points[inds])
        source_inside=patch.intersection(A).area
        features.append(dict(type='Feature',properties=dict(image=code,record=target['id'],
            processed_pair_indices=patch_indices,source_pair_indices=[target['source_pair_indices'][j] for j in patch_indices],
            purpose='diagnostic_path_vs_chord_patch_not_GT_not_candidate_not_vote',area_h2=patch.area),geometry=mapping(patch)))
        for r in recs:
            fractions.append(dict(image=code,record=r['id'],worker=r['worker'],
                patch_covered_fraction=patch.intersection(Polygon(r['footprint'])).area/patch.area,
                interpretation='area coverage, NOT matched-detail support'))
        for name,g in [(m,regs[code,m]) for m in ['mv50','mv_strict']]+[(r['version'],Polygon(r['footprint'])) for r in ims[code]['references']]:
            pc=patch.intersection(g).area
            row=dict(image=code,source_record=target['id'],object=name,
                patch_area_h2=patch.area,source_covers_fraction=source_inside/patch.area,
                patch_covered_fraction=pc/patch.area,
                source_local_omission_h2=patch.intersection(A).difference(g).area,
                source_local_extension_h2=patch.intersection(g).difference(A).area,
                **path_measure(path,g.boundary))
            rows.append(row)
        samples.append(dict(image=code,source_record=target['id'],processed_pair_indices=inds,
            source_pair_indices=[target['source_pair_indices'][j] for j in inds],
            source_points_C=np.array(target['points']).reshape(-1,2,2)[inds].tolist(),
            path_bev=points[inds].tolist(),role='observed local path, not adjudicated true boundary'))
    # One transparent formula control: every point on the first unit segment
    # has distance 0.2 to the parallel segment. No parameter grid or audit suite.
    c=path_measure(LineString([(0,0),(1,0)]),LineString([(0,.2),(1,.2)]))
    assert abs(c['path_mean_h']-.2)<1e-12 and abs(c['path_sampled_max_h']-.2)<1e-12
    (rd/'local_formula_control.json').write_text(json.dumps(dict(parallel_segment_expected_h=.2,measured=c,passed=True),indent=2))
    pd.DataFrame(rows).to_csv(rd/'local_diagnostics.csv',index=False)
    pd.DataFrame(fractions).to_csv(rd/'local_patch_per_person.csv',index=False)
    (rd/'diagnostic_patches.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,indent=2))
    (rd/'local_source_paths.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2))
    from shapely.affinity import rotate
    rr={r['version']:Polygon(r['footprint']) for r in ims['uNb9QFRL6hY-47']['references']}
    a,b=rr['original'],rr['manual_revision'];rot=rotate(a,90,origin=(0,0))
    m=regs['uNb9QFRL6hY-47','mv50']
    iou=lambda x,y:x.intersection(y).area/x.union(y).area
    diagnostic=dict(image='uNb9QFRL6hY-47',operation='single image-led +90 degree rotation about camera; diagnostic only; no search',
        original_vs_manual_iou=iou(a,b),rotated90_original_vs_manual_iou=iou(rot,b),
        unchanged_original_vs_mv50_iou=iou(a,m),rotated90_original_vs_mv50_iou=iou(rot,m),
        use_in_main_metrics=False,interpretation='Orientation correspondence remains unverified; no source or reference correction authorized.')
    (rd/'uNb47_orientation_diagnostic.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2))
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--results',required=True);p.add_argument('--spec',required=True);a=p.parse_args();run(a.input,a.results,a.spec)
