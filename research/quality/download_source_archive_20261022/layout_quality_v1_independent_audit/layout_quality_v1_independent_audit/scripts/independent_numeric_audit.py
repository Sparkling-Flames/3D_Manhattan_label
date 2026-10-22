#!/usr/bin/env python3
"""Read-only audit of the supplied frozen research-v1 bundle.
Run: python independent_numeric_audit.py --package path/to/layout_quality_research_v1_repro --out fresh_output
No source files are edited; outputs contain deterministic small test geometries.
"""
import argparse, copy, csv, hashlib, json, math, pathlib, sys
sys.dont_write_bytecode = True

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write_csv(p,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader();w.writerows(rows)
def rows(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def independent_score(m):
    # Independently spelled scalar equation, not a call to production score code.
    I=min(1.,max(0.,float(m['iou'])))
    S2=(float(m['S_top_deg'])**2+float(m['S_bottom_deg'])**2)/2
    H=float(m['height_mean_relative_error']);D=float(m['dir']);F=float(m['flat'])
    return 100*I/(1+S2/16+4*H*H)*(1-.075*(D*D/(D*D+25)+F*F/(F*F+4)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',required=True,type=pathlib.Path);ap.add_argument('--out',required=True,type=pathlib.Path);args=ap.parse_args()
    p=args.package.resolve();out=args.out.resolve()
    if out==p or p in out.parents:raise ValueError('Output must be outside supplied package')
    out.mkdir(parents=True,exist_ok=True)
    source=p/'source/oct8-pro-quality-handoff'
    hashes={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()}
    manifest=json.loads((p/'PACKAGE_SHA256.json').read_text())
    manifest_bad=[k for k,v in manifest.items() if not (p/k).is_file() or sha(p/k)!=v]
    sys.path[:0]=[str(p/'code/core'),str(p/'code/geometry')]
    import numpy as np
    from score_layout import score_geometry
    from geometry_experiments import room, xz_scale, top_warp, subdivision, map_rings
    frozen=json.loads((source/'inputs/frozen_geometry.json').read_text())
    records={r['id']:r for im in frozen['images'] for r in im['annotations']+im['groundtruths']}
    verification=[]
    def verify(label,key,a,g,expected):
        result=score_geometry(a,g);m=result['components'];q=result['score']['score_research_v1'];ind=independent_score(m)
        verification.append(dict(panel=label,key=key,geometry_api_score=q,independent_scalar_score=ind,
            delivered_score=float(expected),absolute_delivery_error=abs(q-float(expected)),scalar_error=abs(q-ind)))
    ref48=rows(p/'results/scoring/reference_specific_scores48.csv')
    for r in ref48:verify('reference48',r['review_id']+':'+r['reference_id'],records[r['record_id']],records[r['reference_id']],r['score_research_v1'])
    ctr=json.loads((p/'results/geometry/control_geometries.json').read_text())
    cs={r['case_id']:r for r in rows(p/'results/scoring/control_scores.csv')}
    for c in ctr:verify('control251',c['case_id'],c['annotation'],c['reference'],cs[c['case_id']]['score_research_v1'])
    guards=json.loads((p/'results/height_guard/large_room_uniform_height9_geometries.json').read_text())
    gs={r['case_id']:r for r in rows(p/'results/height_guard/large_room_uniform_height9.csv')}
    for c in guards:verify('height9',c['case_id'],c['annotation'],c['reference'],gs[c['case_id']]['score_final_frozen'])
    write_csv(out/'geometry_api_308_checks.csv',verification)

    # New height stress test: all geometry valid, same footprint and mean height,
    # large alternating endpoint errors; no adjustment of production parameters.
    foot=[[-3,-2],[3,-2],[3,2],[-3,2]];base=room(foot,top=1.)
    counterexamples=[];height=[]
    for scale in [1,2,4,8,16,32]:
        g=xz_scale(base,scale);a=top_warp(g,.99)
        result=score_geometry(a,g);m=result['components']
        c=dict(case=f'alternating_height_xz_scale_{scale}',annotation=a,reference=g)
        counterexamples.append(c)
        height.append(dict(case=c['case'],xz_scale=scale,reference_wall_height_h=2.,minimum_wall_height_h=1.01,maximum_wall_height_h=2.99,
            endpoint_relative_height_error=.495,perimeter_relative_height_rms=m['height_internal_relative_rms'],
            mean_height_relative_error=m['height_mean_relative_error'],S_top_deg=m['S_top_deg'],flat_deg=m['flat'],
            score=result['score']['score_research_v1']))
    write_csv(out/'independent_height_cancellation6.csv',height)

    # Input-contract tests; overlap/touching examples fail the simple-polygon
    # domain but the current implementation accepts them. No external validator
    # library is needed: each failure has explicit intersecting edge evidence.
    malformed=[]
    def attempt(name,a,ref=base,expected='reject',reason=''):
        try:
            result=score_geometry(a,ref)
            malformed.append(dict(case=name,expected=expected,observed='available',score=result['score']['score_research_v1'],reason=reason))
        except Exception as e:
            malformed.append(dict(case=name,expected=expected,observed='rejected',error_type=type(e).__name__,reason=str(e)))
    invalid_footprints={
      'overlapping_backtrack_edges':([[-3,-2],[3,-2],[1,-2],[3,2],[-3,2]],'Edges (v0,v1) and (v1,v2) overlap along x in [1,3], z=-2.'),
      'nonadjacent_vertex_touches_edge':([[-3,-2],[3,-2],[3,2],[0,-2],[-3,2]],'Vertex v3=(0,-2) lies strictly inside nonadjacent edge (v0,v1).'),
    }
    for name,(foot,reason) in invalid_footprints.items():
        a=room(foot);attempt(name,a,reason=reason);counterexamples.append(dict(case=name,annotation=a,reference=base,reason=reason))
    a=copy.deepcopy(base);a['top3d'][0][0]+=.01;attempt('unpaired_xz',a)
    a=copy.deepcopy(base);a['bottom3d'][0][1]=-2;attempt('floor_not_minus_one',a)
    a=copy.deepcopy(base);a['top3d'][0][1]=-1;attempt('top_at_floor',a)
    a=copy.deepcopy(base);a['top3d'][0][1]=float('nan');attempt('nonfinite',a)
    a=copy.deepcopy(base);a['top3d']=a['top3d'][:-1];attempt('unequal_ring_counts',a)
    a=copy.deepcopy(base);a['top3d'][1]=a['top3d'][0];a['bottom3d'][1]=a['bottom3d'][0];attempt('duplicate_adjacent_vertex',a)
    attempt('proper_crossing_bowtie',room([[-3,-2],[3,2],[-3,2],[3,-2]]))
    attempt('valid_triangle',room([[-3,-2],[3,-2],[0,2]]),expected='accept',reason='API explicitly permits n >= 3; project-specific minimum pairs belongs in integration.')
    attempt('valid_collinear_subdivision',room([[-3,-2],[0,-2],[3,-2],[3,2],[-3,2]]),expected='accept')
    write_json(out/'input_contract_checks.json',malformed)
    write_json(out/'independent_counterexample_geometries.json',counterexamples)

    # Scores should be invariant to common yaw and reflection; same-curve vertex
    # subdivision changes representation only. Start-index quadrature can have
    # tiny numerical differences, so record rather than claim exact invariance.
    invariance=[]
    for r in ref48:
        a,g=records[r['record_id']],records[r['reference_id']]
        q0=score_geometry(a,g)['score']['score_research_v1']
        theta=.371;c,s=math.cos(theta),math.sin(theta)
        mat=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        funcs={
          'common_yaw':lambda z:map_rings(z,lambda v,k:v@mat.T),
          'common_reflection':lambda z:map_rings(z,lambda v,k:v*np.array([-1,1,1])),
          'common_subdivision3':lambda z:subdivision(z,3),
        }
        for name,fun in funcs.items():
            q=score_geometry(fun(a),fun(g))['score']['score_research_v1']
            invariance.append(dict(review_id=r['review_id'],reference_id=r['reference_id'],operation=name,baseline=q0,variant=q,absolute_difference=abs(q-q0)))
    write_csv(out/'common_transform_invariance144.csv',invariance)
    unchanged=all(sha(source/k)==v for k,v in hashes.items())
    summary=dict(package_manifest_entries=len(manifest),package_manifest_mismatches=manifest_bad,
       source_files_before=len(hashes),source_files_unchanged=unchanged,
       direct_geometry_scored_rows=len(verification),max_abs_delivery_error=max(r['absolute_delivery_error'] for r in verification),
       max_abs_independent_scalar_error=max(r['scalar_error'] for r in verification),
       invariant_cases=len(invariance),max_invariance_difference=max(r['absolute_difference'] for r in invariance),
       contract_expected_rejections_accepted=[r['case'] for r in malformed if r['expected']=='reject' and r['observed']=='available'],
       valid_triangle_accepted=next(r['observed']=='available' for r in malformed if r['case']=='valid_triangle'),
       height_cancellation_scores={str(r['xz_scale']):r['score'] for r in height},
       scope='Independent scalar and raw-geometry execution checks. Same production geometry functions, so not an independent full geometry implementation. No human score validation or formula retuning.')
    write_json(out/'independent_numeric_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
