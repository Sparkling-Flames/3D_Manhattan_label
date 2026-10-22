#!/usr/bin/env python3
"""Exercise the delivered entry point, focusing on measured defects and null gates."""
import argparse, hashlib, json, math, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'verification/CLI_VERIFICATION.json');a=ap.parse_args()
    routes={r['record_id']:r for r in read(ROOT/'routing/results/routes.json')['rows']}
    results=[]
    def run(label,args,check):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'assess.py')]+args,cwd=ROOT,text=True,capture_output=True)
        assert p.returncode==0,(label,p.stderr)
        x=json.loads(p.stdout);check(x)
        results.append(dict(case=label,status='passed',output_status=x['status'],score=x.get('score'),floor_score=x.get('floor_score'),reason=x.get('reason') or x.get('route',{}).get('route_reason')))
    def full(x):
        assert math.isclose(x['score'],74.28801834510428,abs_tol=1e-9)
        assert x['legacy_input_version'] and x['current_formal_gate']
        assert x['selected_reference']['reference_points_sha256_from_calibration']
        assert x['selected_reference']['points_sha256_canonical_v1'] is None
        assert x['quality_grade'] is None and not x['formal_eligibility_newly_granted']
    def floor(x):
        assert x['score'] is None and x['floor_score'] is not None
        assert x['IoU3D_corner_mean'] is None and x['metrics']['Hm'] is None and x['metrics']['Hc'] is None
        assert x['selected_reference']['full_reference_available'] is False
    def family(x):
        assert x['route']['route_reason']==routes['R03258']['route_reason']
        assert x['route']['candidate_id']==routes['R03258']['selected_candidate_id']
    def unavailable(x):
        assert x['status']=='unavailable' and x['score'] is None and x['floor_score'] is None
        assert x['reason']
    run('T20_full_score_and_separate_hash_identity',['--record-id','R00397'],full)
    run('floor_only_reference_preserves_nulls',['--record-id','R03197'],floor)
    run('manual_family_reason_agrees_with_batch',['--record-id','R03258'],family)
    run('unavailable_record_not_zero',['--record-id','R99999'],unavailable)
    with tempfile.TemporaryDirectory(prefix='quality_cli_') as td:
        d=Path(td)
        geometries=[('empty_bottom',{'bottom3d':[]}),('two_coordinates',{'bottom3d':[[0,0],[1,0],[0,1]]}),('missing_bottom',{}),('wrong_floor_unit',{'bottom3d':[[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1]]}),('wrong_top_shape',{'bottom3d':[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1]],'top3d':[[0,1,0]]})]
        for label,obj in geometries:
            p=d/(label+'.json');p.write_text(json.dumps(obj))
            run(label,['--geometry',str(p),'--image-code','uNb9QFRL6hY-67'],unavailable)
        data=read(ROOT/'routing/inputs/prepared_input.json');rec=next(r for r in data['records'] if r['record_id']=='R03197')
        p=d/'valid_external.json';p.write_text(json.dumps(rec['geometry']))
        def external(x):
            floor(x)
            assert x['qualification']=='external_not_adjudicated' and x['conditional_personnel_eligible'] is False
            assert x['raw_input_diagnostics']['status']=='unavailable'
            assert x['external_input_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
        run('new_geometry_routes_without_fabricating_raw_input_or_eligibility',['--geometry',str(p),'--image-code','uNb9QFRL6hY-67'],external)
    result=dict(schema='delivered_cli_verification_v1',status='passed',case_count=len(results),cases=results,entry_point_sha256=hashlib.sha256((ROOT/'assess.py').read_bytes()).hexdigest())
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
