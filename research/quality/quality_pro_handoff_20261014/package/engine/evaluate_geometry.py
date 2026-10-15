import numpy as np

def evaluate_geometry(a,g,e):
    va=e['valid'].validate_record(a,role='annotation')
    vg=e['valid'].validate_record(g,role='reference')
    reasons=[role+':'+x['code'] for role,v in [('annotation',va),('reference',vg)] for x in v['errors']]
    out=dict(status='unavailable',reason_codes=reasons,metrics=None,candidate_components=None)
    if not va['available'] or not vg['available']:
        return out
    try:
        areas=e['au'].area_metrics(a,g)
        am=e['hm'].height_moments(a);gm=e['hm'].height_moments(g)
        center=e['center'].centered_height_components(a,g,samples=4096,height_module=e['hm'])
        traditional=e['trad'].traditional_metrics_detailed(a,g,areas=areas,annotation_validation=va,reference_validation=vg)
        metrics=dict(iou_2d=areas['iou'],S_bottom_deg=float(e['sp'].spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),
            dir=float(e['au'].direction_residual(a,e['au'].direction_axis(a))),
            Hmean=abs(am['height_mean_h']/gm['height_mean_h']-1),Hcenter=center['Hcenter'],
            height_mean_ratio=am['height_mean_h']/gm['height_mean_h'],
            iou_3d_corner_mean=traditional['hohonet_iou3d_vertex_mean'])
        components={n:e['score'].score_metrics(metrics,c) for n,c in e['configs'].items()}
        out.update(status='complete' if all(c['status']=='complete' for c in components.values()) else 'formula_unavailable',
            metrics=metrics,candidate_components=components,height_diagnostics=center,
            traditional_reason_codes=traditional['traditional_reason_codes'])
    except (ValueError,ArithmeticError) as exc:
        out['reason_codes'].append(type(exc).__name__+':'+str(exc))
    return out
