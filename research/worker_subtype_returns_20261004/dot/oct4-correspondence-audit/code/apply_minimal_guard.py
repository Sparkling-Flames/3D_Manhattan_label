"""Write only the audit's isolated copy, never the downloaded or remote source."""
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
s=(BASE/'fixtures/consensus_lab_original.py').read_text()
s=s.replace("r.get('source_point_indices',[])[2*j:2*j+2]", "(r.get('source_point_indices') or [])[2*j:2*j+2]")
s=s.replace("r.get('source_point_labels',[])[2*j:2*j+2]", "(r.get('source_point_labels') or [])[2*j:2*j+2]")
old="""    residuals=[full_alignment(pairs(c),pairs(r))['distance'] for r in records]
"""
new="""    # Audit-only fail-closed guard: bind the certificate to the exact maps
    # that produced this candidate. This does not choose a semantic winner.
    m=len(pairs(c));actual={a['id']:a for a in c['alignments']};map_arrays={}
    disagreements=[]
    for r in records:
        row=actual.get(r['id'])
        if row is None or row.get('ambiguous') or len(row.get('mapping',[]))!=m:
            return dict(status='unresolved_actual_mapping_certificate_mismatch',single_candidate=None,
                        reason='candidate_missing_complete_unambiguous_member_mapping')
        mapping=dict(row['mapping']);ix=[mapping.get(i) for i in range(m)]
        expected=full_alignment(pairs(next(r0 for r0 in records if r0['id']==anchor)),pairs(r))
        if ix!=expected['mapping']:
            disagreements.append(dict(id=r['id'],actual_mapping=ix,certified_mapping=expected['mapping']))
        map_arrays[r['id']]=np.asarray(ix,dtype=int)
    induced=[]
    for ra,rb in combinations(records,2):
        distance=float(costs(pairs(ra),pairs(rb))[map_arrays[ra['id']],map_arrays[rb['id']]].max())
        induced.append(dict(a=ra['id'],b=rb['id'],distance=distance))
    if disagreements or any(v['distance']>tolerance+1e-9 for v in induced):
        return dict(status='unresolved_actual_mapping_certificate_mismatch',single_candidate=None,
                    mapping_disagreements=disagreements,actual_induced_pair_errors_deg=induced,cycle_audit=audit)
    residuals=[float(costs(pairs(c),pairs(r))[np.arange(m),map_arrays[r['id']]].max()) for r in records]
"""
assert s.count(old)==1
s=s.replace(old,new)
(BASE/'patched/consensus_lab_guarded.py').write_text(s)
