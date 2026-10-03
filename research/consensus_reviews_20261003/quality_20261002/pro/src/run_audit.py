"""Run independent selected-real and controlled synthetic quality experiments."""
from pathlib import Path
from copy import deepcopy
import json,csv,hashlib,platform,sys
import numpy as np
import scipy,shapely
from quality_core import *
BASE=Path(__file__).resolve().parents[1]
def save_json(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv_save(p,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)

def main():
    out=BASE/'results';out.mkdir(exist_ok=True)
    data=json.loads((BASE/'inputs/current_numeric_subset.json').read_text());im=data['images'][0]
    im['annotations']=[r for r in im['annotations'] if r['id'] in {'R03286','R03288','R03281','R03287','R03284','R03282'}]
    ref=reconstruct(im['references'][0]);real=[]
    for r in im['annotations']:
        g=reconstruct(r);m=compare(g,ref)
        real.append(dict(image=im['code'],annotation=r['id'],worker_from_numeric_excerpt=r['worker'],reference=im['references'][0]['id'],
                         reference_ring_confirmed=False,quality_candidate=r['quality_candidate'],camera_inside=bool(g.polygon.contains(Point(0,0))),**m))
    csv_save(out/'real_selected_metrics.csv',real)
    # 1. Geometry-preserving subdivision of a sloping wall-top model.
    square=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float);H=np.array([1.5,3.5,3.5,1.5])
    base=record_from_geometry(square,H,'same_surface_base');ga=reconstruct(base)
    density=[];synthetic_inputs=[]
    for n in [0,1,2,4,8,16,32]:
        mids=[[2,float(z)] for z in np.linspace(-2,2,n+2)[1:-1]]
        floor=np.array([[-2,-2],[2,-2]]+mids+[[2,2],[-2,2]])
        hh=2.5+.5*floor[:,0];r=record_from_geometry(floor,hh,f'collinear_insert_{n}')
        g=reconstruct(r);m=compare(g,ga)
        density.append(dict(inserted_points=n,pair_count=len(floor),**m));synthetic_inputs.append(dict(case='density',a=r,b=base))
    csv_save(out/'collinear_density.csv',density)
    # 2. Mirror roof slope: equal fitted flat volume, different spatial height field.
    A=record_from_geometry(square,3+.5*square[:,0],'roof_plus')
    B=record_from_geometry(square,3-.5*square[:,0],'roof_minus')
    m=compare(reconstruct(A),reconstruct(B));m.update(case='opposite_sloping_roofs',exact_volume_a_h3=48.,exact_volume_b_h3=48.,
        exact_intersection_h3=40.,exact_synthetic_volume_iou=40/56)
    synthetic_inputs.append(dict(case='opposite_roofs',a=A,b=B))
    # 3. Same observed top pixels; floor range expands by factor q.
    flat=record_from_geometry(square,2.7,'flat_base');gflat=reconstruct(flat);q=1.25
    scaled=record_from_geometry(square*q,1+q*(2.7-1),'scaled_with_fixed_top_angles')
    dep=compare(reconstruct(scaled),gflat);dep.update(case='fixed_top_bottom_range_scale',range_scale=q,
        max_top_pixel_change=float(np.max(abs(np.array(scaled['points'])[::2]-np.array(flat['points'])[::2]))))
    synthetic_inputs.append(dict(case='top_bottom_dependency',a=scaled,b=flat))
    # 4. Same native half-pixel floor perturbation at two distances.
    sensitivity=[]
    for extent in [2.,32.]:
        r=record_from_geometry(square*(extent/2),2.7,f'half_extent_{extent}');s=deepcopy(r);s['points'][3][1]-=.5
        g,gg=reconstruct(r),reconstruct(s);delta=np.linalg.norm(gg.floor-g.floor,axis=1)
        sensitivity.append(dict(half_extent_h=extent,perturbation_px=.5,one_corner_shift_h=float(delta[1]),
            four_corner_rmse_h=float(np.sqrt(np.mean(delta**2))),min_floor_angle_deg=float(np.degrees(np.pi*(np.array(r['points'])[1::2,1]/512-.5)).min()),**compare(gg,g)))
        synthetic_inputs.append(dict(case='horizon_sensitivity',a=s,b=r))
    csv_save(out/'horizon_sensitivity.csv',sensitivity)
    save_json(out/'controlled_results.json',dict(opposite_roofs=m,top_bottom_dependency=dep,horizon=sensitivity))
    # 5. Subdivide the longest physical edge of a real saved record, without changing its surface.
    real_sub=[]
    for r in [im['annotations'][0],im['annotations'][2]]:
        g=reconstruct(r);edge=int(np.argmax(np.linalg.norm(np.roll(g.floor,-1,axis=0)-g.floor,axis=1)))
        for n in [1,4,16]:
            t=np.linspace(0,1,n+2)[1:-1];nxt=(edge+1)%len(g.floor)
            pp=[p.tolist() for p in g.floor];hh=g.heights.tolist()
            mids=[(g.floor[edge]+x*(g.floor[nxt]-g.floor[edge])).tolist() for x in t]
            heights=[float(g.heights[edge]+x*(g.heights[nxt]-g.heights[edge])) for x in t]
            pnew=pp[:edge+1]+mids+pp[edge+1:];hnew=hh[:edge+1]+heights+hh[edge+1:]
            new=record_from_geometry(pnew,hnew,r['id']+f'_derived_subdivide_{n}');gn=reconstruct(new)
            selfcmp=compare(gn,g);vsref=compare(gn,ref)
            real_sub.append(dict(annotation=r['id'],edge_index_zero_based=edge,inserted_points=n,
                same_geometry_bev_iou=selfcmp['bev_iou'],same_geometry_column_iou=selfcmp['column_iou'],
                same_geometry_wall_height_rmse_h=selfcmp['wall_height_rmse_h'],
                same_geometry_current_volume_iou=selfcmp['current_model_volume_iou'],
                original_current_vs_gt=compare(g,ref)['current_model_volume_iou'],derived_current_vs_gt=vsref['current_model_volume_iou'],
                same_geometry_vertex_volume_iou=selfcmp['vertex_ls_volume_iou'],same_geometry_arclength_volume_iou=selfcmp['arclength_ls_volume_iou'],
                original_vertex_height=fit_height(g)['height_h'],derived_vertex_height=fit_height(gn)['height_h'],
                original_vs_gt_volume=compare(g,ref)['vertex_ls_volume_iou'],derived_vs_gt_volume=vsref['vertex_ls_volume_iou']))
            synthetic_inputs.append(dict(case='derived_real_subdivision',a=new,b=r))
    csv_save(out/'derived_real_subdivision.csv',real_sub)
    save_json(BASE/'inputs/controlled_inputs.json',synthetic_inputs)
    # Reversal counts are within ONE image; they are not worker classifications.
    valid=[r for r in real if r['column_status']=='ok'];reversals=[]
    for i,a in enumerate(valid):
        for b in valid[i+1:]:
            for metric in ['current_model_volume_iou','column_iou']:
                if (a['bev_iou']-b['bev_iou'])*(a[metric]-b[metric])<0:
                    reversals.append(dict(a=a['annotation'],b=b['annotation'],other_metric=metric,bev_a=a['bev_iou'],bev_b=b['bev_iou'],other_a=a[metric],other_b=b[metric]))
    csv_save(out/'within_image_reversals.csv',reversals)
    summary=dict(real_images=1,real_responses=len(real),real_references=1,real_bev_comparisons=len(real),real_column_comparisons=len(valid),
        controlled_input_pairs=len(synthetic_inputs),density_cases=len(density),derived_real_subdivisions=len(real_sub),
        image_pair_count=len(valid)*(len(valid)-1)//2,
        within_image_volume_reversals=sum(r['other_metric']=='current_model_volume_iou' for r in reversals),
        within_image_column_reversals=sum(r['other_metric']=='column_iou' for r in reversals),
        max_density_geometry_volume_loss=max(1-r['vertex_ls_volume_iou'] for r in density),
        full_repository_verifier_run=False,full_195_response_recomputation=False,scope='independent selected-coordinate audit; no photos or visual quality adjudication')
    save_json(out/'summary.json',summary)
    save_json(out/'environment.json',dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,shapely=shapely.__version__,platform=platform.platform(),
        input_sha256=hashlib.sha256((BASE/'inputs/current_numeric_subset.json').read_bytes()).hexdigest()))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Density results:')
    for r in density:print(r['inserted_points'],r['vertex_height_a_h'],r['vertex_ls_volume_iou'],r['arclength_ls_volume_iou'])
    return summary
if __name__=='__main__':main()
