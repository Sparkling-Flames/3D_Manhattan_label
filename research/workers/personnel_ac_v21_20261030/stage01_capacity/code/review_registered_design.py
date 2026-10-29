"""Independent identity/capacity audit of the final outcome-blind registration.

Stream large tables through SQLite; never read fusion outputs or target scores.
The reviewer does not modify the registration or qualification rules.
"""
from pathlib import Path
from collections import Counter,defaultdict
from functools import lru_cache
import argparse,csv,gzip,hashlib,json,math,sqlite3,tempfile,time

CAP=Path(__file__).resolve().parents[1]
BASE=CAP.parent

def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(enc(x).encode()).hexdigest()
def team_key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def split(x):return set(x.split('|')) if x else set()
def yes(x):return str(x).lower() in ('true','1','1.0')
def num(x):return int(float(x)) if x not in ('',None) else None
def rows(path):
    opener=gzip.open if path.name.endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        for r in reader:
            assert None not in r,(str(path),'bad_csv_width')
            yield r
def write_csv(data,path):
    data=list(data)
    if not data:return
    opener=gzip.open if path.name.endswith('.gz') else open
    with opener(path,'wt',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)

def main(args):
    started=time.monotonic();reg=BASE/args.registration_path if args.registration_path else BASE/'stage01_design_review'/args.name
    receipt=json.loads((reg/'DESIGN_REGISTRATION_RECEIPT.json').read_text())
    frozen=json.loads((reg/'FROZEN_DESIGN_FILES.json').read_text())
    failures=[];warnings=[];checks=Counter();failure_counts=Counter()
    def check(ok,kind,detail=''):
        checks[kind]+=1
        if not ok:
            failure_counts[kind]+=1
            if len(failures)<100:failures.append({'check':kind,'detail':str(detail)})
        return ok
    for fn,info in frozen['requested_outputs'].items():
        p=reg/fn
        check(p.stat().st_size==info['bytes'],'registration_frozen_size',fn)
        check(hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256'],'registration_frozen_sha256',fn)
    for info in receipt['outcome_blind_inputs']:
        p=BASE/info['path']
        check(hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256'],'capacity_input_sha256',info['path'])
    data=json.loads((CAP/'SCORE_BLIND_POOL_INPUTS.json').read_text())
    pools={p['pool_id']:p for p in data['pools']}
    methods={}
    for r in rows(CAP/'POOL_METHOD_CAPACITY.csv.gz'):
        groups={k:set(v) for k,v in json.loads(r['class_members_json']).items()}
        lookup={w:k for k,ws in groups.items() for w in ws}
        methods[(r['method'],r['pool_id'])]=(groups,lookup,split(r['unknown_workers']))
    labels={}
    for r in rows(CAP/'FROZEN_LABELS_USED_ALL_LOBO.csv.gz'):
        if yes(r['known']) and r['class_id']:
            labels[(r['method'],r['heldout_building'],r['worker_id'])]=r['class_id']
    roles={(r['method'],r['heldout_building'],r['class_id']):r for r in rows(CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv')}
    for (method,pid),(groups,lookup,unknown) in methods.items():
        b=pools[pid]['meta']['building']
        expected={w:labels[(method,b,w)] for w in pools[pid]['workers'] if (method,b,w) in labels}
        check(lookup==expected,'pool_LOBO_class_membership',(method,pid))
        check(unknown==set(pools[pid]['workers'])-set(expected),'pool_unknown_members',(method,pid))
    dbfile=Path(tempfile.gettempdir())/('hohonet_design_capacity_review_'+args.prefix+args.name+'.sqlite3')
    dbfile.unlink(missing_ok=True);db=sqlite3.connect(dbfile)
    db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF');db.execute('PRAGMA temp_store=MEMORY')
    db.execute('CREATE TABLE events(eid TEXT PRIMARY KEY,physical TEXT,method TEXT,pid TEXT,ak TEXT,ck TEXT,d TEXT,x TEXT,z TEXT,families TEXT,na INT,nc INT,source TEXT,target TEXT)')
    db.execute('CREATE TABLE teams(tk TEXT PRIMARY KEY)')
    event_count=0;event_strata=Counter();family_events=Counter();pure_zero_by_method=Counter();by_scope=Counter();by_method=Counter()
    pending=[]
    for e in rows(reg/'AC_EVENTS.csv.gz'):
        event_count+=1;pid=e['pool_id'];method=e['method'];pool=pools[pid];meta=pool['meta']
        groups,lookup,unknown=methods[(method,pid)]
        A=split(e['A_workers']);C=split(e['C_workers']);D=split(e['D_workers']);X=split(e['X_workers']);Z=split(e['Z_workers'])
        check(len(A)==num(e['n_A']) and len(C)==num(e['n_C']) and min(len(A),len(C))>=3,'event_team_sizes',e['event_id'])
        check(A|C<=set(pool['workers']),'event_qualified_pool_members',e['event_id'])
        check(D==A&C and X==A-C and Z==C-A and A!=C,'event_exact_D_X_Z',e['event_id'])
        check(not((X|Z)&unknown),'unknown_only_background',e['event_id'])
        check(e['building']==meta['building']==e['heldout_building'],'event_correct_LOBO_building',e['event_id'])
        check(e['condition']==meta['condition']=='manual' and e['layer']==meta['layer']=='ordinary_manual','ordinary_manual_domain',e['event_id'])
        check(e['scope']==pool['scope'] and e['reference_id']==str(meta.get('reference_id','')) and e['reference_version']==str(meta.get('reference_version','')),'target_scope_and_reference',e['event_id'])
        ak=team_key(pid,A);ck=team_key(pid,C);physical=digest([pid,sorted([ak,ck])])[:24]
        check(e['A_team_key']==ak and e['C_team_key']==ck,'native_team_key',e['event_id'])
        check(e['physical_pair_id']==physical and e['event_id']==digest([pid,method,physical])[:24],'physical_and_method_event_identity',e['event_id'])
        ax=sorted({lookup.get(w,'unknown') for w in X});cz=sorted({lookup.get(w,'unknown') for w in Z})
        source='|'.join(ax);target='|'.join(cz);pure=len(ax)==len(cz)==1 and ax!=cz
        check(e['source_class']==source and e['target_class']==target and yes(e['pure_cross_class_blocks'])==pure,'block_class_ids',e['event_id'])
        same=len(A)==len(C)
        check(yes(e['equal_team_size'])==same and num(e['delta_n'])==len(C)-len(A),'equal_unequal_size_flags',e['event_id'])
        if same:
            check(num(e['n'])==len(A) and num(e['m'])==len(X)==len(Z),'equal_n_m',e['event_id'])
        else:check(e['n']=='' and e['m']=='','unequal_not_pooled_as_equal_n_m',e['event_id'])
        check(num(e['D_n'])==len(D) and num(e['m_X'])==len(X) and num(e['m_Z'])==len(Z),'block_size_columns',e['event_id'])
        ws=bool(X) and len(ax)==1 and X==groups[source]
        wt=bool(Z) and len(cz)==1 and Z==groups[target]
        check(yes(e['whole_source'])==ws and yes(e['whole_target'])==wt,'whole_class_exact_pool_members',e['event_id'])
        check(num(e['mv50_threshold_A'])==math.ceil(len(A)/2) and num(e['mv50_threshold_C'])==math.ceil(len(C)/2),'frozen_MV50_denominator',e['event_id'])
        for tag,S in [('A',A),('C',C),('D',D)]:
            actual=Counter(lookup.get(w,'unknown') for w in S)
            check(json.loads(e[tag+'_class_counts'])==dict(actual),'team_class_composition',e['event_id']+':'+tag)
        if pure:
            sr=roles[method,meta['building'],source];tr=roles[method,meta['building'],target]
            sk=(float(sr['primary_role_rank']),source);tk=(float(tr['primary_role_rank']),target)
            check(sk<tk,'canonical_historical_role_direction',e['event_id'])
            check(e['source_parent_class']==sr['parent_class'] and e['target_parent_class']==tr['parent_class'],'event_true_parent_classes',e['event_id'])
        else:check(ak<ck,'canonical_nonpure_endpoint_direction',e['event_id'])
        families=split(e['design_family'])
        if 'B_equal_whole_class' in families:check(same and pure and (ws or wt),'registered_equal_whole_definition',e['event_id'])
        if 'B_unequal_whole_classes' in families:check(not same and pure and ws and wt,'registered_unequal_whole_definition',e['event_id'])
        stratum=('equal_pure_zero_background' if pure and same and not D else 'equal_mixed_zero_background' if same and not D else 'equal_shared_background' if same else 'unequal_zero_background' if not D else 'unequal_shared_background')
        event_strata[(method,pool['scope'],stratum)]+=1
        if pure and same and not D:pure_zero_by_method[method]+=1
        for family in families:family_events[family]+=1
        by_scope[pool['scope']]+=1;by_method[method]+=1
        pending.append((e['event_id'],physical,method,pid,ak,ck,e['D_workers'],e['X_workers'],e['Z_workers'],e['design_family'],len(A),len(C),source,target))
        if len(pending)>=2000:
            db.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',pending);pending=[]
        if event_count%100000==0:print(json.dumps({'phase':'events','rows':event_count}),flush=True)
    if pending:db.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',pending)
    db.commit()
    check(event_count==receipt['method_events'],'receipt_event_total',event_count)
    check(dict(by_scope)==receipt['by_scope'] and dict(by_method)==receipt['by_method'],'receipt_domain_method_totals')
    physical_pairs=db.execute('SELECT COUNT(DISTINCT physical) FROM events').fetchone()[0]
    check(physical_pairs==receipt['physical_pairs'],'receipt_physical_pair_total',physical_pairs)
    check(db.execute('SELECT COUNT(*) FROM (SELECT physical,method FROM events GROUP BY physical,method HAVING COUNT(*)>1)').fetchone()[0]==0,'no_duplicate_or_reverse_method_event')
    count_teams=0;pending=[]
    for t in rows(reg/'TEAM_REQUESTS.csv.gz'):
        count_teams+=1;pool=pools[t['pool_id']];workers=t['member_workers'].split('|');membermap={r['worker_id']:str(r['object_id']) for r in pool['members']}
        check(len(workers)==len(set(workers))==num(t['n']) and set(workers)<=set(pool['workers']),'requested_team_members',t['team_key'])
        check(t['team_key']==team_key(t['pool_id'],workers),'requested_native_team_key',t['team_key'])
        check(t['member_object_ids']=='|'.join(membermap[w] for w in workers),'requested_exact_qualified_original_objects',t['team_key'])
        check(t['reference_id']==str(pool['meta'].get('reference_id','')) and t['reference_version']==str(pool['meta'].get('reference_version','')),'requested_team_reference',t['team_key'])
        pending.append((t['team_key'],))
        if len(pending)>=2000:db.executemany('INSERT INTO teams VALUES(?)',pending);pending=[]
    if pending:db.executemany('INSERT INTO teams VALUES(?)',pending)
    db.commit();check(count_teams==receipt['unique_teams'],'receipt_team_total',count_teams)
    check(db.execute('SELECT COUNT(*) FROM events e LEFT JOIN teams t ON e.ak=t.tk WHERE t.tk IS NULL').fetchone()[0]==0,'every_A_endpoint_requested')
    check(db.execute('SELECT COUNT(*) FROM events e LEFT JOIN teams t ON e.ck=t.tk WHERE t.tk IS NULL').fetchone()[0]==0,'every_C_endpoint_requested')
    db.execute('CREATE INDEX events_ak ON events(ak)');db.execute('CREATE INDEX events_ck ON events(ck)')
    check(db.execute('SELECT COUNT(*) FROM teams t WHERE NOT EXISTS(SELECT 1 FROM events e WHERE e.ak=t.tk) AND NOT EXISTS(SELECT 1 FROM events e WHERE e.ck=t.tk)').fetchone()[0]==0,'no_orphan_team_requests')
    @lru_cache(maxsize=4096)
    def event(eid):return db.execute('SELECT physical,method,pid,ak,ck,d,x,z,families,na,nc,source,target FROM events WHERE eid=?',(eid,)).fetchone()
    link_count=0;family_links=Counter();cell_usage={};nested={};fixedA={};fixedD={};unequal={};coalition_count=0
    linked_families=Counter();unmatched_families=Counter()
    for l in rows(reg/'DESIGN_LINKS.csv.gz'):
        link_count+=1;e=event(l['event_id'])
        if not check(e is not None,'every_link_event_exists',l['link_id']):continue
        physical,method,pid,ak,ck,ds,xs,zs,fs,na,nc,sc,tc=e
        check(num(l['link_id'])==link_count,'link_id_unique_sequence',l['link_id'])
        check((l['physical_pair_id'],l['method'],l['pool_id'])==(physical,method,pid),'link_event_identity',l['link_id'])
        family=l['design_family'];check(family in split(fs),'link_family_on_event',l['link_id']);family_links[family]+=1
        sign=num(l['input_orientation_sign']);check(sign in [-1,1],'explicit_input_orientation',l['link_id'])
        oa,oc=(ak,ck) if sign==1 else (ck,ak);d=split(ds);x=split(xs);z=split(zs)
        ox,oz=(x,z) if sign==1 else (z,x)
        if l.get('background_id'):
            # The same-target addition leg inherits its parent contrast's
            # outside-class background identifier. Its actual endpoint
            # intersection additionally contains the already added target
            # subset, which remains explicitly present in event.D_workers.
            if family=='B_unequal_additional_same_target_members':
                outside=unequal.get(l['parent_contrast_id'],{}).get('outside_D')
                check(outside is not None and l['background_id']==digest([pid,sorted(split(outside))])[:24],
                      'addition_leg_parent_outside_background_id',l['link_id'])
                check(outside is not None and split(outside)<=d,'addition_leg_contains_parent_background',l['link_id'])
            else:
                check(l['background_id']==digest([pid,sorted(d)])[:24],'link_exact_background_id',l['link_id'])
        if l.get('zero_background'):
            check(yes(l['zero_background'])==(len(d)==0),'explicit_zero_background_flag',l['link_id'])
        cell=l.get('cell_id','')
        if cell:
            blockid=digest([pid,sorted(ox),sorted(oz)])[:24]
            check(l['block_id']==blockid,'registered_exact_block_id',l['link_id'])
            use=cell_usage.setdefault(cell,{'links':0,'blocks':set(),'backgrounds':set(),'pairs':set(),'source_seen':set(),'target_seen':set()})
            use['links']+=1;use['blocks'].add(blockid);use['backgrounds'].add(ds);use['pairs'].add((blockid,ds));use['source_seen']|=ox;use['target_seen']|=oz
        path=l.get('nested_background_path_id','')
        if path:
            # Path IDs describe physical blocks, and may be reused across
            # methods. Background quota paths additionally depend on that
            # method's whole-pool partition, so audit the method/path pair.
            key=(xs,zs);p=nested.setdefault((method,path),{'block':key,'levels':{}})
            check(p['block']==key,'nested_background_keeps_block',path)
            n=num(l['n']);prior=p['levels'].get(n)
            check(prior is None or prior==d,'nested_background_level_unique',path);p['levels'][n]=d
        path=l.get('anchor_A_path_id','')
        if path:
            p=fixedA.setdefault(path,{'A':oa,'m':set()});check(p['A']==oa,'fixed_A_path_keeps_original_A',path);p['m'].add(num(l['m']))
            m=num(l['m']);xx=l['source_prefix_order'].split('|');zz=l['target_prefix_order'].split('|')
            check(ox==set(xx[:m]) and oz==set(zz[:m]),'fixed_A_nested_X_Z_prefix',l['link_id'])
        panel=l.get('fixed_D_panel_id','')
        if panel:
            p=fixedD.setdefault(panel,{'D':ds,'pairs':set(),'A':set(),'C':set()});check(p['D']==ds,'fixed_D_member_panel_background',panel)
            p['pairs'].add(l['event_id']);p['A'].add(oa);p['C'].add(oc)
        parent=l.get('parent_contrast_id','')
        if parent:
            p=unequal.setdefault(parent,{'full':None,'anchors':{},'additions':{}})
            if family=='B_unequal_whole_classes':
                check(p['full'] is None or p['full']==(oa,oc),'one_unequal_full_parent',parent);p['full']=(oa,oc);p['outside_D']=ds
            elif family=='B_unequal_equal_size_anchor':p['anchors'][l['member_rep']]=(oa,oc)
            elif family=='B_unequal_additional_same_target_members':p['additions'][l['member_rep']]=(oa,oc)
        if family=='C_complete_class_alliances':
            coalition_count+=1;groups,lookup,unknown=methods[(method,pid)]
            def coalition(which):
                workers=set()
                for cl in l[which+'_alliance'].split('|'):workers|=groups[cl]
                if yes(l['unknown_background_included']):workers|=unknown
                return team_key(pid,workers)
            check((oa,oc)==(coalition('A'),coalition('C')),'complete_alliance_exact_members',l['link_id'])
        if link_count%200000==0:print(json.dumps({'phase':'links','rows':link_count}),flush=True)
    check(link_count==receipt['design_links'],'receipt_design_link_total',link_count)
    check(dict(family_links)==receipt['family_links'],'receipt_family_link_totals')
    for path,p in nested.items():
        levels=sorted(p['levels'])
        for a,b in zip(levels,levels[1:]):check(p['levels'][a]<=p['levels'][b],'nested_background_members_monotone',path)
    for parent,p in unequal.items():
        check(p['full'] is not None,'unequal_parent_exists',parent)
        check(set(p['anchors'])==set(p['additions']),'unequal_decomposition_paired_legs',parent)
        if p['full']:
            for rep,a in p['anchors'].items():
                b=p['additions'].get(rep)
                check(b and a[0]==p['full'][0] and a[1]==b[0] and b[1]==p['full'][1],'unequal_decomposition_exact_telescoping_teams',parent+':'+rep)
    cell_rows=[];cell_count=0
    for c in rows(reg/'REGISTERED_AC_CELLS.csv.gz'):
        cell_count+=1;groups,lookup,unknown=methods[(c['method'],c['pool_id'])]
        n,m=num(c['n']),num(c['m']);S=groups[c['source_class']];T=groups[c['target_class']];N=len(pools[c['pool_id']]['workers'])
        check(n>=3 and m<=n and len(S)>=m and len(T)>=m and N>=n+m,'registered_cell_capacity',c['cell_id'])
        u=cell_usage[c['cell_id']]
        check(u['links']==num(c['registration_links']),'cell_direction_link_count',c['cell_id'])
        check(len(u['blocks'])==num(c['registered_XZ_blocks']),'cell_registered_block_count',c['cell_id'])
        check(int(c['possible_XZ_blocks'])==math.comb(len(S),m)*math.comb(len(T),m),'cell_possible_block_count',c['cell_id'])
        check(int(c['possible_D_per_XZ'])==math.comb(N-2*m,n-m),'cell_possible_background_count',c['cell_id'])
        cell_rows.append(dict(c,distinct_registered_backgrounds=len(u['backgrounds']),distinct_block_background_pairs=len(u['pairs']),
            source_available_n=len(S),source_members_seen=len(u['source_seen']),source_unseen='|'.join(sorted(S-u['source_seen'])),
            target_available_n=len(T),target_members_seen=len(u['target_seen']),target_unseen='|'.join(sorted(T-u['target_seen'])),
            pure_n_equals_m=n==m,all_XZ_enumerated=len(u['blocks'])==int(c['possible_XZ_blocks'])))
    check(cell_count==receipt['registered_A_B_cells'],'receipt_registered_cell_total',cell_count)
    omitted=list(rows(reg/'NONEXECUTED_SMALL_TEAM_CONTRASTS.csv.gz'))
    for r in omitted:check(min(num(r['n_A']),num(r['n_C']))<3,'small_team_omission_is_small',r['pool_id'])
    alliance_omissions=sum(r['design_family']=='C_complete_class_alliances' for r in omitted)
    capacity_alliances=sum(1 for _ in rows(CAP/'ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz'))
    if not args.bridge_only:
        check(coalition_count+alliance_omissions==capacity_alliances,'complete_alliance_census_including_small_omissions',(coalition_count,alliance_omissions,capacity_alliances))
    omission_trace=not omitted or all(('A_team_key' in r and 'C_team_key' in r) or ('A_workers' in r and 'C_workers' in r) for r in omitted)
    if not omission_trace:warnings.append('Small-team omissions lack exact endpoint identities; same-sized alliances cannot always be uniquely traced from omission rows alone. Complete source alliance census remains available.')
    overlap_expected={}
    for r in rows(reg/'PHYSICAL_PAIR_METHOD_OVERLAP.csv.gz'):
        overlap_expected[r['physical_pair_id']]=split(r['methods'])
        check(num(r['method_count'])==len(split(r['methods'])),'method_overlap_count',r['physical_pair_id'])
    overlap_actual={p:set(ms.split(',')) for p,ms in db.execute('SELECT physical,GROUP_CONCAT(DISTINCT method) FROM events GROUP BY physical')}
    check(overlap_actual==overlap_expected,'cross_method_physical_pair_deduplication')
    strata=[dict(method=k[0],scope=k[1],stratum=k[2],method_events=v) for k,v in sorted(event_strata.items())]
    write_csv(strata,CAP/(args.prefix+'REGISTERED_EVENT_BACKGROUND_STRATA.csv'))
    write_csv(cell_rows,CAP/(args.prefix+'REGISTERED_CELL_MEMBER_BACKGROUND_COVERAGE.csv.gz'))
    panels=[dict(panel_id=k,events=len(p['pairs']),A_variants=len(p['A']),C_variants=len(p['C']),D_workers=p['D']) for k,p in fixedD.items()]
    write_csv(panels,CAP/(args.prefix+'REGISTERED_FIXED_D_PANEL_COVERAGE.csv'))
    out={'status':'passed' if not failures else 'failed','registration_directory':str(reg.relative_to(BASE)),
        'source_commit':receipt['source_commit'],'design_mutated':False,'target_outcomes_read':False,
        'method_events':event_count,'physical_pairs':physical_pairs,'unique_teams':count_teams,'design_links':link_count,
        'registered_A_B_cells':cell_count,'family_links':dict(family_links),'family_unique_method_events':dict(family_events),
        'pure_equal_n_equals_m_events_by_method':dict(pure_zero_by_method),
        'nested_background_paths':len(nested),'fixed_A_paths':len(fixedA),'fixed_D_panels':len(fixedD),
        'fixed_D_panels_with_multiple_pairs':sum(len(p['pairs'])>1 for p in fixedD.values()),
        'fixed_D_panels_with_multiple_A':sum(len(p['A'])>1 for p in fixedD.values()),
        'fixed_D_panels_with_multiple_C':sum(len(p['C'])>1 for p in fixedD.values()),
        'unequal_whole_class_parent_contrasts':len(unequal),'complete_alliance_links':coalition_count,
        'small_team_alliance_omissions':alliance_omissions,'small_team_omissions_have_exact_identities':omission_trace,
        'checks':dict(checks),'failure_counts':dict(failure_counts),'failures':failures,'warnings':warnings,'elapsed_seconds':time.monotonic()-started,
        'interpretation':['Capacity and identity validation only; no claim about Q, geometry, time, evaluability or effect direction.',
          'Reverse links and multiple methods sharing physical endpoints are not independent replications.',
          'n=m pure-class contrasts are separately counted; shared-background response must use the D_n>0 stratum.',
          'Member/background coverage is the registered sample, not uniform exhaustive coverage unless the exact count says so.',
          'For same-target addition decomposition legs, link.background_id refers to the parent outside-class D; event.D_workers records the full actual intersection including the retained target subset.']}
    (CAP/(args.prefix+'DESIGN_CAPACITY_REVIEW.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    db.close();dbfile.unlink(missing_ok=True)
    print(json.dumps({k:v for k,v in out.items() if k not in ['checks','interpretation','family_unique_method_events']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='registered_v2')
    parser.add_argument('--registration-path');parser.add_argument('--prefix',default='')
    parser.add_argument('--bridge-only',action='store_true');main(parser.parse_args())
