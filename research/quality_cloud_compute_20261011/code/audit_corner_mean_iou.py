"""Independent GEOS polygon + corner-mean common-floor prism arithmetic."""
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from common import read,save,csvwrite,sha
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=read(ROOT/'results/current_components.json');geos=read(ROOT/'inputs/current_geometry_compact.json')['geometries'];out=[]
    for r in rows:
        expected=r.get('iou_3d_corner_mean')
        if expected is None:continue
        a,b=geos[r['object_id']],geos[r['reference_object_id']];pa=Polygon(np.asarray(a['bottom3d'])[:,[0,2]]);pb=Polygon(np.asarray(b['bottom3d'])[:,[0,2]])
        ha=float(np.mean(np.asarray(a['top3d'])[:,1]-np.asarray(a['bottom3d'])[:,1]));hb=float(np.mean(np.asarray(b['top3d'])[:,1]-np.asarray(b['bottom3d'])[:,1]));inter=pa.intersection(pb).area*min(ha,hb);value=inter/(pa.area*ha+pb.area*hb-inter)
        out.append({'record_id':r['record_id'],'expected_corner_mean_IoU':expected,'independent_polygon_prism_IoU':value,'difference':value-expected,'primary_gate_reference_allowed':r['primary_gate_and_reference_allowed']})
    error=max(abs(r['difference']) for r in out);assert error<1e-10
    csvwrite(ROOT/'results/current_corner_mean_iou_audit.csv',out);summary={'cases':len(out),'max_abs_error':error,'passed':True,'method':'Shapely polygon intersection, mean corner heights, min-height common-floor prism intersection','official_full_depth_pipeline_run':False,'official_source_commit':'not established from inherited vendor provenance','vendor_eval_sha256':sha(ROOT/'frozen/scope_engine/traditional/vendor/eval_layout.py'),'vendor_postproc_sha256':sha(ROOT/'frozen/scope_engine/traditional/vendor/post_proc.py'),'license_sha256':sha(ROOT/'frozen/scope_engine/traditional/vendor/LICENSE'),'cannot_replace_missing_Pro_official_audit':True};save(ROOT/'results/current_corner_mean_iou_audit_summary.json',summary);print(summary)
if __name__=='__main__':main()
