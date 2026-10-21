"""Exact class-count and member denominators for the registered member panels.

This attaches frozen LOBO labels to all 924 actual member sets. Unknown labels
are not a zero-count class. Every feasible full labelled-domain count vector is
enumerated, even when no current panel reaches it; member sets outside the
conditional panels are counted combinatorially, never claimed evaluated.
"""
from __future__ import annotations
import collections, csv, gzip, io, itertools, json, math, os
from pathlib import Path
import pandas as pd
from multin_design import HERE, gs, h, sha, write_csv
from design_matched_events import label_maps

OUT = HERE / 'configuration'

def vectors(capacities, n):
    """Yield every bounded integer vector exactly once (including n=0)."""
    capacities = tuple(capacities)
    suffix = [sum(capacities[j:]) for j in range(len(capacities) + 1)]
    def visit(j, left, prefix):
        if j == len(capacities):
            if left == 0: yield tuple(prefix)
            return
        lo, hi = max(0, left - suffix[j+1]), min(capacities[j], left)
        for k in range(lo, hi + 1):
            yield from visit(j+1, left-k, prefix+[k])
    yield from visit(0, n, [])

def counter_string(classes, counts):
    return gs.canonical_counts(dict(zip(classes, counts)))

def check_csv(path, expected_rows, key_cols=None):
    seen = set(); n = 0
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as f:
        r = csv.reader(f); cols = next(r)
        indexes = [cols.index(c) for c in (key_cols or [])]
        for row in r:
            if len(row) != len(cols): raise ValueError(('ragged', path, n))
            if indexes:
                key = tuple(row[j] for j in indexes)
                if key in seen: raise ValueError(('duplicate', path, key))
                seen.add(key)
            n += 1
    if n != expected_rows: raise ValueError(('incomplete_csv', path, n, expected_rows))
    return dict(rows=n, columns=len(cols), bytes=path.stat().st_size, sha256=sha(path))

def run():
    OUT.mkdir(exist_ok=True)
    maps, sources = label_maps()
    panels = pd.read_csv(HERE/'PANELS.csv', keep_default_na=False)
    members = pd.read_csv(HERE/'PANEL_MEMBERSHIP.csv.gz', keep_default_na=False)
    panel_members = {pid: g for pid, g in members.groupby('panel_id')}
    panel_configs = []; panel_opportunities = []; domain_state = {}
    map_path = OUT/'PANEL_TEAM_CONFIG_MAPPING.csv.gz'; map_tmp = map_path.with_name(map_path.name+'.tmp')
    fields = ['method_id','tier','panel_id','team_key','configuration_id']
    mapping_n = 0
    with gzip.open(map_tmp, 'wt', encoding='utf-8-sig', newline='', compresslevel=5) as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for panel in panels.to_dict('records'):
            pid = panel['panel_id']; variable = panel['variable_workers'].split('|')
            background = panel['background_workers'].split('|'); domain = panel['domain_workers'].split('|')
            n = int(panel['n']); registered = panel_members[pid]
            for (method,tier,condition,building),(labels,parents) in sorted(maps.items()):
                if (condition,building) != (panel['condition'],panel['building']): continue
                known_domain = [w for w in domain if w in labels]
                classes = sorted({labels[w] for w in known_domain})
                cap = [sum(labels[w] == c for w in known_domain) for c in classes]
                domain_key = (panel['pool_id'],panel['source_domain'],n,method,tier)
                state = domain_state.setdefault(domain_key, dict(
                    meta={k:panel[k] for k in ['pool_id','image','building','condition','difficulty','source_domain']},
                    n=n, method_id=method, tier=tier, classes=classes, cap=cap,
                    domain_n=len(domain), known_n=len(known_domain),
                    unknown_workers='|'.join(sorted(set(domain)-set(known_domain))),
                    actual=collections.defaultdict(set), panels=set(), full_labelled_panels=set()))
                if (state['classes'],state['cap']) != (classes,cap): raise ValueError('domain label inconsistency')
                state['panels'].add(pid)
                var_known = [w for w in variable if w in labels]
                unknown_bg = set(background)-labels.keys()
                vc = [sum(labels[w] == c for w in var_known) for c in classes]
                bc = [sum(labels.get(w) == c for w in background) for c in classes]
                theoretical = math.comb(len(var_known),6) if not unknown_bg and len(var_known)>=6 else 0
                by_vec = collections.defaultdict(list)
                for member in registered.itertuples():
                    selected = member.selected_variable_workers.split('|')
                    if unknown_bg or any(w not in labels for w in selected): continue
                    counts = tuple(bc[j] + sum(labels[w] == c for w in selected) for j,c in enumerate(classes))
                    by_vec[counts].append(member.team_key)
                if sum(map(len,by_vec.values())) != theoretical: raise ValueError('partial support count mismatch')
                complete_panel = theoretical == 924
                if complete_panel: state['full_labelled_panels'].add(pid)
                meta = {k:panel[k] for k in ['panel_id','pool_id','image','building','condition','difficulty','source_domain','n','variable_panel_no']}
                panel_opportunities.append(dict(meta,method_id=method,tier=tier,
                    registered_sets=924,labelled_sets=theoretical,unlabelled_sets=924-theoretical,
                    known_variable_n=len(var_known),unknown_background_n=len(unknown_bg),
                    unknown_variable_workers='|'.join(sorted(set(variable)-set(var_known))),
                    unknown_background_workers='|'.join(sorted(unknown_bg)),
                    known_class_configurations=len(by_vec),domain_labelled_n=len(known_domain),domain_n=len(domain),
                    status='full_924_labelled' if complete_panel else 'partial_labelled_support' if theoretical else 'no_labelled_team_in_registered_background'))
                if not theoretical: continue
                expected_vectors = {}
                for selection in vectors(vc,6):
                    counts = tuple(a+b for a,b in zip(selection,bc))
                    expected_vectors[counts] = math.prod(math.comb(c,k) for c,k in zip(vc,selection))
                if set(expected_vectors) != set(by_vec): raise ValueError('conditional configuration missing')
                for counts,keys in sorted(by_vec.items()):
                    expected = expected_vectors[counts]
                    if len(keys) != expected or len(set(keys)) != len(keys): raise ValueError('conditional member census mismatch')
                    selected_counts = [a-b for a,b in zip(counts,bc)]
                    cid = h('panel-class-configuration',pid,method,tier,dict(zip(classes,counts)))[:24]
                    full_members = math.prod(math.comb(c,k) for c,k in zip(cap,counts))
                    parent_counts = collections.Counter()
                    parent_map = {labels[w]:parents[w] for w in known_domain}
                    for c,k in zip(classes,counts): parent_counts[parent_map[c]] += k
                    panel_configs.append(dict(meta,method_id=method,tier=tier,configuration_id=cid,
                        class_counts=counter_string(classes,counts),parent_class_counts=gs.canonical_counts(dict(parent_counts)),
                        variable_class_capacity=counter_string(classes,vc),background_class_counts=counter_string(classes,bc),
                        selected_variable_counts=counter_string(classes,selected_counts),
                        domain_class_capacity=counter_string(classes,cap),
                        theoretical_conditional_members=expected,actual_conditional_members=len(keys),
                        exhaustive_conditional_members=True,member_variation_estimable=expected>1,
                        singleton_configuration=expected==1,all_924_sets_labelled=complete_panel,
                        full_domain_members_with_this_configuration=full_members,
                        full_domain_members_not_in_this_panel=full_members-len(keys)))
                    state['actual'][counts].update(keys)
                    for key in sorted(keys):
                        writer.writerow(dict(method_id=method,tier=tier,panel_id=pid,team_key=key,configuration_id=cid));mapping_n += 1
    check_csv(map_tmp,mapping_n);map_tmp.replace(map_path)
    write_csv(OUT/'PANEL_CLASS_CONFIGURATIONS.csv.gz',pd.DataFrame(panel_configs))
    write_csv(OUT/'PANEL_LABEL_OPPORTUNITIES.csv',pd.DataFrame(panel_opportunities))
    gs.save(OUT/'CONDITIONAL_COMPLETE.json',dict(status='conditional_complete',
        mapped_rows=mapping_n,conditional_configurations=len(panel_configs),
        mapping_sha256=sha(map_path),configuration_sha256=sha(OUT/'PANEL_CLASS_CONFIGURATIONS.csv.gz')))
    # Every possible source-domain count vector is included, not just observed.
    dp = OUT/'ALL_DOMAIN_CONFIGURATIONS.csv.gz'; dt = dp.with_name(dp.name+'.tmp')
    domain_summary=[]; full_config_n=0; full_member_sum=0
    domain_fields=['pool_id','image','building','condition','difficulty','source_domain','n','method_id','tier','domain_configuration_id','class_counts','domain_class_capacity','known_domain_n','unknown_domain_n','theoretical_members','actual_registered_unique_members','uncovered_members','registered_panels_reaching_configuration','member_variation_estimable_from_current_panels','configuration_reached']
    with io.StringIO(newline='') as f:
        writer=csv.DictWriter(f,fieldnames=domain_fields);writer.writeheader()
        # Count the number of panels reaching each vector independently of
        # member-set union; overlapping panels do not inflate unique coverage.
        reachable=collections.Counter()
        for r in panel_configs:
            reachable[(r['pool_id'],r['source_domain'],int(r['n']),r['method_id'],r['tier'],r['class_counts'])]+=1
        for key,state in sorted(domain_state.items()):
            n=state['n'];classes=state['classes'];cap=state['cap'];actual=state['actual'];cfg_n=0;members_n=0
            for counts in vectors(cap,n):
                count_string=counter_string(classes,counts)
                theoretical=math.prod(math.comb(c,k) for c,k in zip(cap,counts));seen=len(actual.get(counts,set()))
                if seen>theoretical:raise ValueError('domain coverage exceeds possible')
                cid=h('domain-class-configuration',key,dict(zip(classes,counts)))[:24]
                writer.writerow(dict(state['meta'],n=n,method_id=state['method_id'],tier=state['tier'],domain_configuration_id=cid,
                    class_counts=count_string,domain_class_capacity=counter_string(classes,cap),
                    known_domain_n=state['known_n'],unknown_domain_n=state['domain_n']-state['known_n'],
                    theoretical_members=theoretical,actual_registered_unique_members=seen,uncovered_members=theoretical-seen,
                    registered_panels_reaching_configuration=reachable[(*key,count_string)],
                    member_variation_estimable_from_current_panels=seen>1,configuration_reached=seen>0))
                cfg_n+=1;members_n+=theoretical
            expected=math.comb(state['known_n'],n) if state['known_n']>=n else 0
            if members_n!=expected:raise ValueError('Vandermonde identity failed')
            actual_keys=set().union(*actual.values()) if actual else set()
            all_domain=math.comb(state['domain_n'],n)
            domain_summary.append(dict(state['meta'],n=n,method_id=state['method_id'],tier=state['tier'],
                source_domain_n=state['domain_n'],known_domain_n=state['known_n'],unknown_domain_workers=state['unknown_workers'],
                source_domain_member_universe=all_domain,fully_labelled_member_universe=expected,
                teams_with_at_least_one_unknown_label=all_domain-expected,
                feasible_known_configurations=cfg_n,reached_known_configurations=len(actual),unreached_known_configurations=cfg_n-len(actual),
                registered_unique_labelled_teams=len(actual_keys),uncovered_labelled_members=expected-len(actual_keys),
                registered_panels=len(state['panels']),full_924_labelled_panels=len(state['full_labelled_panels']),
                source_domain_capacity=counter_string(classes,cap),all_feasible_known_configurations_listed=True,
                exhaustive_source_domain_members=len(actual_keys)==expected and expected>0))
            full_config_n+=cfg_n;full_member_sum+=members_n
        packed=gzip.compress(f.getvalue().encode('utf-8-sig'),compresslevel=5,mtime=0)
        with open(dt,'wb') as target:
            target.write(packed);target.flush();os.fsync(target.fileno())
    check_csv(dt,full_config_n,['domain_configuration_id']);dt.replace(dp)
    write_csv(OUT/'DOMAIN_COVERAGE.csv',pd.DataFrame(domain_summary))
    counts=pd.DataFrame(domain_summary).groupby(['method_id','tier','condition'],as_index=False).agg(
        strata=('n','size'),pools=('pool_id','nunique'),buildings=('building','nunique'),
        feasible_known_configurations=('feasible_known_configurations','sum'),
        reached_known_configurations=('reached_known_configurations','sum'),
        registered_unique_labelled_teams=('registered_unique_labelled_teams','sum'),
        fully_labelled_member_universe=('fully_labelled_member_universe','sum'),
        unknown_label_member_sets=('teams_with_at_least_one_unknown_label','sum'))
    write_csv(OUT/'METHOD_COVERAGE_SUMMARY.csv',counts)
    frozen=[]
    for p in sorted(OUT.iterdir()):
        if p.name.startswith('.') or '.tmp' in p.name or p.name=='COMPLETION.json':continue
        if p.name.endswith('.csv.gz'):
            size=sum(1 for _ in gzip.open(p,'rt',encoding='utf-8-sig'))-1
            check=check_csv(p,size)
        else:check=dict(bytes=p.stat().st_size,sha256=sha(p))
        frozen.append(dict(path=str(p.relative_to(HERE)),**check))
    receipt=dict(status='complete',panel_configurations=len(panel_configs),mapped_team_method_panel_rows=mapping_n,
        source_domain_strata=len(domain_summary),all_feasible_known_domain_configurations=full_config_n,
        unlabelled_workers_not_treated_as_zero=True,conditional_member_census_verified=True,
        all_domain_vector_member_counts_verified_by_vandermonde=True,unknown_target_fold_maps_are_outside_support=True,
        endpoint_calls=0,label_sources={str(p):sha(p) for p in sources},files=frozen,
        accounting_note='Method/tier/source-domain spaces overlap. Summed denominators are accounting strata, never a unique global team universe. Ordered membership processes are not re-evaluated. Domain vectors are complete only among workers with valid held-out-building labels.')
    gs.save(OUT/'COMPLETION.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
