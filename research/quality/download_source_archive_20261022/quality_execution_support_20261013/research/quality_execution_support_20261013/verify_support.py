"""Verify restored frozen dependencies; does not tune, reroute or alter inputs."""
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
manifest=json.loads((HERE/'MANIFEST.json').read_text())
for item in manifest['files']:
 p=ROOT/item['path']
 assert p.stat().st_size==item['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
PACKAGE=ROOT/'research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012'
FROZEN=PACKAGE/'source_snapshot/research/quality_scope_comparison_20261010/frozen_engine'
for sub in ['legacy_geometry','validity','height_revision','traditional']:
 sys.path.insert(0,str(FROZEN/sub))
sys.path.insert(0,str(PACKAGE/'scripts'))
import audit_geometry as au, geometric_components as sp, strict_geometry as valid
import height_revision as hm, centered_height as center, traditional_metrics as trad
data=json.loads((PACKAGE/'inputs/calibration_records.json').read_text())
assert len(data['rows'])==922
checks=[]
for i in [0,150,300,450,600,750]:
 r=data['rows'][i];a=data['geometries'][r['object_id']];g=data['geometries'][r['reference_object_id']]
 va=valid.validate_record(a,role='annotation');vg=valid.validate_record(g,role='reference')
 assert va['available'] and vg['available']
 areas=au.area_metrics(a,g);am=hm.height_moments(a);gm=hm.height_moments(g)
 metrics=dict(iou_2d=areas['iou'],S_bottom_deg=float(sp.spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),
 dir=float(au.direction_residual(a,au.direction_axis(a))),Hmean=abs(am['height_mean_h']/gm['height_mean_h']-1),
 Hcenter=center.centered_height_components(a,g,samples=4096,height_module=hm)['Hcenter'])
 error=max(abs(metrics[k]-r['metrics'][k]) for k in metrics)
 iou=trad.traditional_metrics_detailed(a,g,areas=areas,annotation_validation=va,reference_validation=vg)['hohonet_iou3d_vertex_mean']
 error=max(error,abs(iou-r['legacy_metrics']['iou_3d_corner_mean']))
 assert error<1e-8,(r['id'],error)
 checks.append(dict(record_id=r['id'],max_abs_error=error))
print(json.dumps(dict(status='passed',verified_files=len(manifest['files']),frozen_records=922,
 geometry_spot_checks=checks,scope='source hashes and six unchanged frozen geometry comparisons; not full current-loader replay'),indent=2))
