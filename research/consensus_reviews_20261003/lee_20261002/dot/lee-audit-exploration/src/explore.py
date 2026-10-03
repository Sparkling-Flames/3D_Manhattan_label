"""Independent finite-pool benchmark for the frozen equal-weight Lee BEV panel.

The full-pool overlay is an OFFLINE integration basis, never a predictive input.
No source module is imported; prefix geometry is separately rebuilt for checks.
No repair, snapping, small-cell deletion, eligibility or reference modification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
import hashlib
from itertools import combinations
import json
from math import comb
from pathlib import Path
import platform
import sys
import warnings
import zlib

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
METHODS = ('mv50', 'mv_strict')
GATES = {'main_candidate', 'oos_doorway_exploratory', 'stable_nonorthogonal_separate'}
INPUT_SHA256 = '4a7ffc036cfbafc21e8adaa84ead6a101dcf6dda84cc047ee2ad3858f9cc604c'
WARNINGS = []


@contextmanager
def capture(stage, **context):
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always')
        yield
    WARNINGS.extend(dict(stage=stage, **context, category=w.category.__name__,
                         message=str(w.message)) for w in seen)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def save_csv(path, rows):
    if not rows:
        path.write_text('')
        return
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def selected(support, k, method):
    return 2*support >= k if method == 'mv50' else 2*support > k


def hypergeom(N, s, k):
    """Exact integer combinatorial weights, converted only at final division."""
    denominator = comb(N, k)
    return [(j, comb(s,j)*comb(N-s,k-j)/denominator)
            for j in range(max(0,k-(N-s)), min(s,k)+1)]


def selection_and_transition(N, s, k, method):
    mass = hypergeom(N,s,k)
    q = sum(p for j,p in mass if selected(j,k,method))
    grow = shrink = 0.0
    if k < N:
        for j,p in mass:
            for added, probability in ((1,(s-j)/(N-k)), (0,(N-s-k+j)/(N-k))):
                before, after = selected(j,k,method), selected(j+added,k+1,method)
                grow += p*probability*(not before and after)
                shrink += p*probability*(before and not after)
    return q,grow,shrink


def validate_polygon(coords, label):
    if coords is None:
        raise ValueError('unavailable_footprint:'+label)
    points = np.asarray(coords, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points)<3 or not np.isfinite(points).all():
        raise ValueError('invalid_coordinates:'+label)
    polygon = Polygon(points)
    if not polygon.is_valid or not np.isfinite(polygon.area) or polygon.area<=0:
        raise ValueError('invalid_polygon:'+label)
    return polygon


def overlay(polygons):
    """Independent scalar point-membership implementation of planar overlay."""
    cells = list(polygonize(unary_union([p.boundary for p in polygons])))
    representatives=[cell.representative_point() for cell in cells]
    votes = np.array([[p.contains(point) for point in representatives]
                      for p in polygons], dtype=bool)
    keep = votes.any(axis=0)
    cells = [cell for cell,use in zip(cells,keep) if use]
    votes = votes[:,keep]
    area = np.array([c.area for c in cells])
    domain = unary_union(polygons)
    tol = 1e-9*max(1.0,domain.area)
    area_error = abs(float(area.sum())-domain.area)
    worker_error = float(np.max(abs(votes@area-np.array([p.area for p in polygons]))))
    if not np.isfinite(area).all() or np.any(area<=0):
        raise ValueError('nonpositive_or_nonfinite_cell')
    if area_error>tol or worker_error>tol:
        raise ValueError('partition_mismatch')
    return cells,votes,area,dict(domain_area_h2=float(domain.area),
        partition_area_error_h2=area_error, worker_area_error_h2=worker_error)


def rebuild_prefix(polygons, method):
    cells,votes,area,_ = overlay(polygons)
    keep = selected(votes.sum(axis=0),len(polygons),method)
    result = unary_union([c for c,k in zip(cells,keep) if k])
    if not result.is_valid or not np.isfinite(result.area):
        raise ValueError('invalid_prefix_geometry')
    return result


def summarize(values):
    v=np.asarray(values)
    return dict(mean=float(v.mean()),p10=float(np.quantile(v,.1)),p90=float(np.quantile(v,.9)))


def run(input_path, out, published=None):
    out.mkdir(parents=True,exist_ok=True)
    raw=input_path.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=INPUT_SHA256:
        raise ValueError('fixed_input_sha256_mismatch')
    data=json.loads(raw)
    if data['schema']!='lee_tile_stage1_input_v1':
        raise ValueError('unsupported_input_schema')
    expectation_rows=[]; exact_rows=[]; sample_rows=[]; support_rows=[]; validations=[]
    cell_rows=[]; coverage=[]; sample_curve=[]; endpoint_rows=[]
    max_refine=max_direct_iou=max_exact_identity=max_transition_identity=0.0
    total_subsets=0
    for image in data['images']:
        groups=defaultdict(list)
        for rec in image['annotations']:
            gate=rec['main_consensus_gate']['status']
            if rec['independent'] and rec['consensus_eligible'] and gate in GATES:
                groups[rec['condition'],gate].append(rec)
        coverage.append(dict(image=image['code'],input_records=len(image['annotations']),
            eligible_records=sum(map(len,groups.values())),
            retained_excluded_records=len(image['annotations'])-sum(map(len,groups.values())),
            upstream_gates=dict(Counter(r['main_consensus_gate']['status'] for r in image['annotations']))))
        for (condition,gate),records in sorted(groups.items()):
            ident=dict(image=image['code'],condition=condition,gate=gate)
            rec=sorted(records,key=lambda r:r['id']);N=len(rec)
            if len({r['id'] for r in rec})!=N or len({r['worker'] for r in rec})!=N:
                raise ValueError('duplicate_id_or_worker')
            with capture('full_overlay',**ident):
                polygons=[validate_polygon(r['footprint'],r['id']) for r in rec]
                cells,V,A,check=overlay(polygons)
            refs={r['version']:validate_polygon(r['footprint'],r['version'])
                  for r in image['references'] if r['footprint'] is not None}
            reference_areas={v:float(g.area) for v,g in refs.items()}
            with capture('cell_reference_intersection',**ident):
                overlaps={v:np.array([c.intersection(g).area for c in cells]) for v,g in refs.items()}
            for version,I in overlaps.items():
                if not np.isfinite(I).all() or np.any(I < -1e-12) or np.any(I>A+1e-10):
                    raise ValueError('invalid_cell_reference_overlap')
            support=V.sum(axis=0);p=support/N
            for i,(a,s) in enumerate(zip(A,support)):
                cell_rows.append(dict(**ident,cell=i,area_h2=float(a),support=int(s),roster_n=N,
                    member_indices='|'.join(str(j) for j in np.flatnonzero(V[:,i])),
                    original_overlap_h2=float(overlaps['original'][i]) if 'original' in overlaps else None,
                    manual_revision_overlap_h2=float(overlaps['manual_revision'][i]) if 'manual_revision' in overlaps else None))
            cache={}
            def state(inds,method):
                key=(inds,method)
                if key not in cache:
                    mask=selected(V[list(inds)].sum(axis=0),len(inds),method)
                    area=float(A@mask)
                    st=dict(mask=mask,area_h2=area)
                    for ver,I in overlaps.items():
                        inter=float(I@mask);g=reference_areas[ver]
                        iou=inter/(g+area-inter)
                        if not np.isfinite(iou) or iou < -1e-12 or iou>1+1e-12:
                            raise ValueError('inconsistent_iou')
                        st[ver]=dict(iou=min(1.,max(0.,iou)),intersection_h2=inter,
                                     omission_h2=g-inter,extension_h2=area-inter)
                    cache[key]=st
                return cache[key]
            seed=data['plan']['seed']+zlib.crc32('|'.join(ident.values()).encode())
            rng=np.random.default_rng(seed)
            orders=[rng.permutation(N).tolist() for _ in range(data['plan']['permutations'])]
            sampled={k:sorted({tuple(sorted(o[:k])) for o in orders}) for k in range(1,N+1)}
            exact_ks=list(range(1,N+1)) if N<=9 else sorted({1,2,N-2,N-1,N})
            all_exact={k:list(combinations(range(N),k)) for k in exact_ks}
            total_subsets+=sum(map(len,all_exact.values()))
            prefix_checked=0; local_refine=local_iou=local_identity=0.0
            # Complete fresh-prefix validation in every <=9-person group. For larger
            # pools check every singleton and deterministic first/last pairs,
            # complements, the full roster, and all k on one permutation.
            prefix_subsets=set(x for xs in all_exact.values() for x in xs) if N<=9 else set(
                all_exact[1]+all_exact[2][:3]+all_exact[2][-3:]+all_exact[N-1][:3]+all_exact[N-1][-3:]+all_exact[N])
            prefix_subsets.update(tuple(sorted(orders[0][:k])) for k in range(1,N+1))
            for inds in sorted(prefix_subsets,key=lambda t:(len(t),t)):
                with capture('fresh_prefix_validation',**ident,k=len(inds),members=list(inds)):
                    # Build each current-members-only partition once for both rules.
                    current_cells,current_V,_,_=overlay([polygons[i] for i in inds])
                    for method in METHODS:
                        current_keep=selected(current_V.sum(axis=0),len(inds),method)
                        current=unary_union([c for c,use in zip(current_cells,current_keep) if use])
                        st=state(inds,method)
                        offline=unary_union([c for c,use in zip(cells,st['mask']) if use])
                        err=float(current.symmetric_difference(offline).area)
                        local_refine=max(local_refine,err)
                        tolerance=1e-8*max(1.,check['domain_area_h2'])
                        if err>tolerance:
                            raise ValueError('offline_prefix_refinement_mismatch')
                        for version,gt in refs.items():
                            inter=float(current.intersection(gt).area)
                            direct=inter/(current.area+gt.area-inter)
                            ie=abs(direct-st[version]['iou'])
                            local_iou=max(local_iou,ie)
                            if ie>1e-9:
                                raise ValueError('offline_direct_iou_mismatch')
                prefix_checked+=1
            # The support-field identities apply to fixed finite populations.
            for version,I in overlaps.items():
                g=reference_areas[version]
                B=float((A@(p*p)-2*I@p+g)/g)
                D=float(A@(p*(1-p))/g)
                D_area=float(A@(p*(1-p)))
                D_union=D_area/check['domain_area_h2']
                with capture('support_identity_direct',**ident,version=version):
                    hard=float(np.mean([poly.symmetric_difference(refs[version]).area/g for poly in polygons]))
                hard_error=abs(hard-B-D)
                for k in range(1,N+1):
                    factor=(N-k)/(k*(N-1)) if N>1 else 0.
                    expected_B=B+factor*D; expected_D=(1-factor)*D
                    empirical_B=empirical_D=None
                    if k in all_exact:
                        qs=[V[list(inds)].mean(axis=0) for inds in all_exact[k]]
                        empirical_B=float(np.mean([(A@(q*q)-2*I@q+g)/g for q in qs]))
                        empirical_D=float(np.mean([A@(q*(1-q))/g for q in qs]))
                        local_identity=max(local_identity,abs(empirical_B-expected_B),abs(empirical_D-expected_D))
                    support_rows.append(dict(**ident,version=version,N=N,k=k,B_full=B,D_full=D,
                        reference_independent_D_area_h2=D_area,
                        reference_independent_D_union=D_union,
                        expected_D_k_union=(1-factor)*D_union,
                        distinct_person_pair_symmetric_difference_union=2*N/(N-1)*D_union if N>1 else None,
                        mean_individual_symmetric_difference_gt=hard,hard_identity_error=hard_error,
                        finite_population_factor=factor,expected_B_k=expected_B,expected_D_k=expected_D,
                        exact_enumerated_B_k=empirical_B,exact_enumerated_D_k=empirical_D,
                        distinct_person_pair_symmetric_difference_gt=2*N/(N-1)*D if N>1 else None))
            for method in METHODS:
                Q={}; transition={}
                for k in range(1,N+1):
                    table={s:selection_and_transition(N,s,k,method) for s in set(support)}
                    q=np.array([table[s][0] for s in support]);Q[k]=q
                    grow=np.array([table[s][1] for s in support]);shrink=np.array([table[s][2] for s in support])
                    earea=float(A@q);grow_area=float(A@grow);shrink_area=float(A@shrink)
                    distinct_count=comb(N,k)
                    member_difference=float(2*A@(q*(1-q))*distinct_count/(distinct_count-1)) if distinct_count>1 else 0.
                    transition[k]=grow_area,shrink_area
                    chosen=[state(inds,method) for inds in sampled[k]]
                    for version,I in overlaps.items():
                        g=reference_areas[version];ei=float(I@q)
                        eomit=g-ei;eext=earea-ei
                        sr=dict(**ident,method=method,version=version,N=N,k=k,
                            total_subsets=comb(N,k),sampled_unique_subsets=len(chosen),
                            sampled_iou_mean=float(np.mean([st[version]['iou'] for st in chosen])),
                            sampled_area_h2=float(np.mean([st['area_h2'] for st in chosen])),
                            sampled_omission_gt=float(np.mean([st[version]['omission_h2']/g for st in chosen])),
                            sampled_extension_gt=float(np.mean([st[version]['extension_h2']/g for st in chosen])))
                        sample_curve.append(sr)
                        er=dict(**ident,method=method,version=version,N=N,k=k,
                            total_subsets=comb(N,k),full_tiles=len(cells),reference_area_h2=g,
                            expected_area_h2=earea,expected_intersection_h2=ei,
                            expected_omission_h2=eomit,expected_extension_h2=eext,
                            expected_omission_gt=eomit/g,expected_extension_gt=eext/g,
                            expected_symmetric_difference_gt=(eomit+eext)/g,
                            ratio_of_expected_intersection_union_NOT_expected_iou=ei/(g+earea-ei),
                            expected_adjacent_expansion_h2=grow_area if k<N else None,
                            expected_adjacent_shrinkage_h2=shrink_area if k<N else None,
                            expected_adjacent_symmetric_difference_h2=(grow_area+shrink_area) if k<N else None,
                            expected_adjacent_symmetric_difference_gt=(grow_area+shrink_area)/g if k<N else None,
                            expected_adjacent_symmetric_difference_union=(grow_area+shrink_area)/check['domain_area_h2'] if k<N else None,
                            expected_distinct_subset_pair_symmetric_difference_h2=member_difference,
                            expected_distinct_subset_pair_symmetric_difference_union=member_difference/check['domain_area_h2'],
                            sample16_omission_error_gt=sr['sampled_omission_gt']-eomit/g,
                            sample16_extension_error_gt=sr['sampled_extension_gt']-eext/g)
                        if k in all_exact:
                            exact_states=[state(inds,method) for inds in all_exact[k]]
                            vals=[st[version]['iou'] for st in exact_states]
                            summary=summarize(vals)
                            exactrow=dict(**ident,method=method,version=version,N=N,k=k,
                                all_subsets=len(vals),sampled_unique_subsets=len(chosen),
                                exact_iou_mean=summary['mean'],exact_iou_p10=summary['p10'],exact_iou_p90=summary['p90'],
                                sample16_iou_mean=sr['sampled_iou_mean'],
                                sample16_iou_error=sr['sampled_iou_mean']-summary['mean'],
                                ratio_of_expected_areas=ei/(g+earea-ei),
                                ratio_minus_exact_expected_iou=ei/(g+earea-ei)-summary['mean'])
                            exact_rows.append(exactrow)
                            for name,analytic,ev in [('area',earea,[s['area_h2'] for s in exact_states]),
                                ('intersection',ei,[s[version]['intersection_h2'] for s in exact_states]),
                                ('omission',eomit,[s[version]['omission_h2'] for s in exact_states]),
                                ('extension',eext,[s[version]['extension_h2'] for s in exact_states])]:
                                local_identity=max(local_identity,abs(float(np.mean(ev))-analytic))
                            er['exact_iou_mean_when_enumerated']=summary['mean']
                        else:
                            er['exact_iou_mean_when_enumerated']=None
                        expectation_rows.append(er)
                # Analytic transition must agree with difference of all-k mean areas.
                for k in range(1,N):
                    grow,shrink=transition[k]
                    te=abs(float(A@(Q[k+1]-Q[k]))-(grow-shrink))
                    max_transition_identity=max(max_transition_identity,te)
                    if method=='mv50':
                        forbidden=shrink if k%2 else grow
                    else:
                        forbidden=grow if k%2 else shrink
                    if forbidden>1e-12:
                        raise ValueError('parity_transition_violation')
                    if N<=9:
                        changes=[]
                        for inds in all_exact[k]:
                            before=state(inds,method)['mask']
                            for member in range(N):
                                if member not in inds:
                                    after=state(tuple(sorted((*inds,member))),method)['mask']
                                    changes.append(float(A@(before!=after)))
                        te=abs(float(np.mean(changes))-grow-shrink)
                        max_transition_identity=max(max_transition_identity,te)
                # Save exact subset outcomes for every bounded enumerated slice.
                for k,subsets in all_exact.items():
                    for inds in subsets:
                        st=state(inds,method)
                        for version in refs:
                            endpoint_rows.append(dict(**ident,method=method,version=version,N=N,k=k,
                                members='|'.join(rec[i]['id'] for i in inds),area_h2=st['area_h2'],**st[version]))
            max_refine=max(max_refine,local_refine);max_direct_iou=max(max_direct_iou,local_iou)
            max_exact_identity=max(max_exact_identity,local_identity)
            validations.append(dict(**ident,N=N,full_tiles=len(cells),references=list(refs),
                exhaustive_all_k=N<=9,enumerated_k=exact_ks,
                enumerated_subsets=sum(map(len,all_exact.values())),
                fresh_current_member_prefixes_checked=prefix_checked,
                max_prefix_refinement_symmetric_difference_h2=local_refine,
                max_direct_geometry_iou_error=local_iou,max_expectation_identity_error=local_identity,
                **check,status='passed'))
            print(json.dumps(validations[-1],ensure_ascii=False),flush=True)
    save_csv(out/'all_k_expectations.csv',expectation_rows)
    save_csv(out/'exact_iou_vs_16.csv',exact_rows)
    save_csv(out/'bounded_exact_subset_outcomes.csv',endpoint_rows)
    save_csv(out/'sample16_offline_curves.csv',sample_curve)
    save_csv(out/'support_field_identities.csv',support_rows)
    save_csv(out/'full_pool_integration_cells.csv',cell_rows)
    save_json(out/'coverage.json',coverage)
    save_json(out/'warnings.json',WARNINGS)
    save_json(out/'validation.json',dict(input_sha256=sha,groups=validations,
        bounded_enumerated_subsets=total_subsets,
        max_refinement_symmetric_difference_h2=max_refine,
        max_direct_geometry_iou_error=max_direct_iou,
        max_expectation_identity_error=max_exact_identity,
        max_transition_identity_error=max_transition_identity,
        captured_warnings=len(WARNINGS),
        environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,
                         geos=shapely.geos_version_string,platform=platform.platform()),
        geometry_repaired=False,source_imported=False,source_mutated=False,
        exact_expected_iou_at_unenumerated_middle_k=False))
    if published:
        compare_published(published,out,sample_curve)


def compare_published(published,out,sample_curve):
    with published.open(encoding='utf-8-sig') as f:
        original=list(csv.DictReader(f))
    bykey={(r['image'],r['condition'],r['gate'],r['method'],int(r['k'])):r for r in original}
    diffs=[]
    for row in sample_curve:
        key=tuple(row[k] for k in ('image','condition','gate','method','k'))
        source=bykey[key]
        field=row['version']+'_mean'
        diffs.append(dict(image=row['image'],method=row['method'],k=row['k'],version=row['version'],
            published_iou_mean=float(source[field]),offline_iou_mean=row['sampled_iou_mean'],
            absolute_error=abs(float(source[field])-row['sampled_iou_mean']),
            unique_subsets_match=int(source['unique_subsets'])==row['sampled_unique_subsets']))
    save_csv(out/'published_sample_comparison.csv',diffs)
    save_json(out/'published_sample_comparison.json',dict(rows=len(diffs),
        max_iou_mean_difference=max(r['absolute_error'] for r in diffs),
        all_unique_subset_counts_match=all(r['unique_subsets_match'] for r in diffs)))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=ROOT/'inputs/fixed_input.json')
    parser.add_argument('--out',type=Path,default=ROOT/'results')
    parser.add_argument('--published-summary',type=Path)
    args=parser.parse_args()
    run(args.input,args.out,args.published_summary)
