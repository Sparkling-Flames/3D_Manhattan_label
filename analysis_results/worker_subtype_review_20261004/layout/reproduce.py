"""限定认证审查；只执行本目录隔离副本并写本目录结果，不读取GT。"""
import copy
import importlib.util
import itertools
import json
import platform
from pathlib import Path
import subprocess
import sys

import numpy as np
import shapely

BASE=Path(__file__).resolve().parent


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rays(points):
    """独立连续ERP单位向量；角距用atan2(cross,dot)，不调用原型angular/costs。"""
    p=np.asarray(points,float);u=2*np.pi*(p[...,0]/1024-.5);v=np.pi*(.5-p[...,1]/512)
    return np.stack([np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)],axis=-1)


def cost(a,b):
    a=rays(np.asarray(a['points']).reshape(-1,2,2))
    b=rays(np.asarray(b['points']).reshape(-1,2,2))
    cross=np.linalg.norm(np.cross(a[:,None],b[None,:]),axis=-1)
    dot=np.sum(a[:,None]*b[None,:],axis=-1)
    return np.degrees(np.arctan2(cross,dot)).max(axis=2)


def maps(m):
    values=set()
    for ring in (list(range(m)),list(range(m))[::-1]):
        for i in range(m):values.add(tuple(ring[i:]+ring[:i]))
    return sorted(values)


def audit_case(records,original,guarded):
    saved=copy.deepcopy(records)
    before=original.conditional_decision(records,tolerance=5)
    after=guarded.conditional_decision(records,tolerance=5)
    candidate=before['single_candidate'];m=len(candidate['points'])//2
    actual={a['id']:[dict(a['mapping'])[i] for i in range(m)] for a in candidate['alignments']}
    pairs=[]
    for a,b in itertools.combinations(records,2):
        c=cost(a,b);options=sorted((float(c[np.arange(m),p].max()),p) for p in maps(m))
        pairs.append(dict(a=a['id'],b=b['id'],certified_minimax_mapping=list(options[0][1]),
            certified_max_deg=options[0][0],minimax_margin_deg=options[1][0]-options[0][0],
            actual_a_map=actual[a['id']],actual_b_map=actual[b['id']],
            actual_max_deg=float(c[actual[a['id']],actual[b['id']]].max())))
    residuals=[dict(id=r['id'],max_deg=float(cost(candidate,r)[np.arange(m),actual[r['id']]].max())) for r in records]
    assert records==saved
    assert before['status']=='single_candidate_conditional_on_method_tolerance'
    assert after['status']=='unresolved_actual_mapping_certificate_mismatch'
    assert after['single_candidate'] is None
    assert not before['cycle_audit']['conflicts']
    assert all(p['certified_max_deg']<5 and p['minimax_margin_deg']>1e-9 for p in pairs)
    for p,q in zip(pairs,after['actual_induced_pair_errors_deg']):assert abs(p['actual_max_deg']-q['distance'])<1e-10
    return dict(before_status=before['status'],after_status=after['status'],candidate_anchor=candidate['anchor'],
        actual_maps=actual,independent_pairs=pairs,fixed_mapping_candidate_residuals=residuals,
        candidate_points=candidate['points'],guard_diagnostic=after,inputs_unchanged=True)


def main():
    original=load_module('layout_original',BASE/'isolated/fixtures/consensus_lab_original.py')
    guarded=load_module('layout_guarded',BASE/'isolated/patched/consensus_lab_guarded.py')
    fixtures=BASE/'isolated/fixtures'
    known=json.loads((fixtures/'known_certification_objective_mismatch.json').read_text(encoding='utf-8'))['records']
    new=json.loads((fixtures/'three_record_actual_mapping_diameter_counterexample.json').read_text(encoding='utf-8'))['records']
    cases={name:audit_case(rows,original,guarded) for name,rows in [('known_two',known),('new_three',new)]}
    assert max(p['actual_max_deg'] for p in cases['known_two']['independent_pairs'])<5
    new_max=max(p['actual_max_deg'] for p in cases['new_three']['independent_pairs'])
    assert abs(new_max-5.579437932904212)<1e-10
    assert all(v['max_deg']<5 for v in cases['new_three']['fixed_mapping_candidate_residuals'])
    # 独立枚举仅用于固定3人×3点反例，不开展真人池联合搜索。
    feasible=[];m=3
    for p1,p2 in itertools.product(maps(m),repeat=2):
        orders=[tuple(range(m)),p1,p2]
        errors=[float(cost(new[i],new[j])[orders[i],orders[j]].max()) for i,j in itertools.combinations(range(3),2)]
        if max(errors)<=5+1e-9:feasible.append(dict(maps=orders,errors_deg=errors,objective=sum(errors)))
    best=min(v['objective'] for v in feasible);optimal=[v for v in feasible if abs(v['objective']-best)<=1e-9]
    assert len(feasible)==2 and len(optimal)==1
    cases['new_three']['independent_joint36']=dict(states=36,feasible_count=len(feasible),optimal_count=len(optimal),optimal=optimal)
    control=json.loads((fixtures/'reference_tests/inputs/current_excerpt.json').read_text(encoding='utf-8'))['images'][0]['annotations']
    decision=guarded.conditional_decision(control)
    assert decision['status']=='single_candidate_conditional_on_method_tolerance'
    c=decision['single_candidate'];actual={a['id']:dict(a['mapping']) for a in c['alignments']};m=len(c['points'])//2
    fixed=[float(cost(c,r)[np.arange(m),[actual[r['id']][i] for i in range(m)]].max()) for r in sorted(control,key=lambda r:str(r['id']))]
    assert np.allclose(fixed,decision['residuals_deg'],atol=1e-10,rtol=0)
    # 剩余接口边界：证据人口混用不会因本补丁自动获得隔离。
    square=original.from_floor([[-2,-2],[2,-2],[2,2],[-2,2]],worker='real')
    real=dict(copy.deepcopy(square),synthetic=False,independent=True,consensus_eligible=True)
    synthetic=dict(copy.deepcopy(square),id='synthetic',worker='synthetic')
    mixed=guarded.derive_candidates([real,synthetic]);mixed_decision=guarded.conditional_decision([real,synthetic],mixed)
    assert mixed['evidence_populations']==dict(real_record_slots=1,synthetic_control_slots=1)
    assert mixed_decision['status']=='single_candidate_conditional_on_method_tolerance'
    assert mixed['candidates'][0]['point_support_counts']==[2]*4
    # Guard没有扩成完整layout物理证书：只检测平面多边形和对应残差。
    low=copy.deepcopy(square)
    for p in low['points'][0::2]:p[1]=270.
    low2=dict(copy.deepcopy(low),id='low2',worker='low2')
    lower=guarded.conditional_decision([low,low2])
    proc=subprocess.run([sys.executable,'-X','utf8','-B',str(BASE/'isolated/code/test_guard_regressions.py')],
                        cwd=BASE,capture_output=True,text=True)
    (BASE/'guard_regressions.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
    assert proc.returncode==0
    result=dict(schema='layout_certificate_independent_review_v1',environment=dict(python=platform.python_version(),numpy=np.__version__,shapely=shapely.__version__),
        cases=cases,ordinary_control=dict(status=decision['status'],fixed_residuals_deg=fixed),
        remaining_mixed_population=dict(populations=mixed['evidence_populations'],support=mixed['candidates'][0]['point_support_counts'],status=mixed_decision['status']),
        remaining_top_domain=dict(status=lower['status'],band_status=lower['single_candidate']['band_status'] if lower.get('single_candidate') else None,
            interpretation='existing floor/correspondence certificate is not full 3D validity; guard does not extend that scope'),
        tests=dict(dot_guard_regressions=6,passed=True,independent_three_record_max_deg=new_max),
        scope='two fixed synthetic counterexamples, one ordinary real control and two API controls; no fusion-panel rerun or prevalence estimate')
    (BASE/'reproduction.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(known_max=max(p['actual_max_deg'] for p in cases['known_two']['independent_pairs']),new_max=new_max,
        joint_states=36,joint_feasible=len(feasible),joint_optimal=len(optimal),control=decision['status'],six_regressions=proc.returncode,
        mixed_status=mixed_decision['status'],top_domain=result['remaining_top_domain']),ensure_ascii=False))


if __name__=='__main__':main()
