"""Portable exhaustive combinatorial tests, without pytest or source imports."""
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
import json

import numpy as np
from explore import selected,selection_and_transition,overlay,validate_polygon


def main():
    checks=0;worst=0.
    for N in range(1,10):
        for s in range(N+1):
            for k in range(1,N+1):
                subsets=list(combinations(range(N),k))
                for method in ('mv50','mv_strict'):
                    states=[sum(i<s for i in inds) for inds in subsets]
                    exact_q=Fraction(sum(selected(j,k,method) for j in states),len(subsets))
                    q,grow,shrink=selection_and_transition(N,s,k,method)
                    errors=[abs(q-float(exact_q))]
                    if k<N:
                        exact_grow=exact_shrink=0
                        for inds,j in zip(subsets,states):
                            before=selected(j,k,method)
                            for extra in range(N):
                                if extra not in inds:
                                    after=selected(j+(extra<s),k+1,method)
                                    exact_grow+=not before and after
                                    exact_shrink+=before and not after
                        denominator=len(subsets)*(N-k)
                        errors.extend([abs(grow-float(Fraction(exact_grow,denominator))),
                                       abs(shrink-float(Fraction(exact_shrink,denominator)))])
                        qnext=selection_and_transition(N,s,k+1,method)[0]
                        errors.append(abs(grow+shrink-abs(qnext-q)))
                    worst=max(worst,*errors)
                    assert max(errors)<2e-15,(N,s,k,method,errors)
                    checks+=1
    root=Path(__file__).resolve().parents[1]
    d=json.loads((root/'inputs/fixed_input.json').read_text())
    im=d['images'][0];rec=sorted(im['annotations'],key=lambda r:r['id'])
    cells,V,A,_=overlay([validate_polygon(r['footprint'],r['id']) for r in rec])
    pair_error=0.
    for k in range(1,9):
        subsets=list(combinations(range(8),k))
        for method in ('mv50','mv_strict'):
            states=[selected(V[list(inds)].sum(axis=0),k,method) for inds in subsets]
            brute=[float(A@(a!=b)) for a,b in combinations(states,2)]
            q=np.array([selection_and_transition(8,int(s),k,method)[0] for s in V.sum(axis=0)])
            M=comb(8,k)
            formula=float(2*A@(q*(1-q))*M/(M-1)) if M>1 else 0.
            pair_error=max(pair_error,abs((float(np.mean(brute)) if brute else 0.)-formula))
    assert pair_error<1e-12
    result=dict(combinatorial_cases=checks,max_probability_error=worst,
        all_first_group_member_pair_area_checks=16,max_member_pair_area_error_h2=pair_error,status='passed')
    (root/'results/formula_tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
