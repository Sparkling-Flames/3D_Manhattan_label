"""Paired finite member panels for frozen current Manual classes.

Only existing adopted direct room relations and out-of-building labels select
panels. No target quality, geometry or time enters member selection.
"""
from pathlib import Path
import argparse, collections, gzip, hashlib, itertools, json, math, os
import numpy as np
import pandas as pd


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


def dump(path, obj):
    op = gzip.open if str(path).endswith('.gz') else open
    temp = path.with_name(path.name+'.tmp')
    with op(temp, 'wt', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(temp,path)


def save_csv(frame,path):
    temp=path.with_name(path.name+'.tmp')
    frame.to_csv(temp,index=False,compression='gzip' if path.suffix=='.gz' else None)
    os.replace(temp,path)


def build(repo, capacity_dir, out):
    out.mkdir(parents=True, exist_ok=True)
    cap = pd.read_csv(capacity_dir / 'DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv')
    cap = cap[cap.method.eq('V3_BEHAVIOR')].sort_values('pair_key')
    cls = pd.read_csv(capacity_dir / 'DIRECT_PAIR_CLASS_MEMBERS.csv')
    cls = cls[cls.method.eq('V3_BEHAVIOR') & cls.class_id.ne('unknown')]
    lab = pd.read_csv(repo / 'research/workers/personnel_mixture_comparison_20261022/inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz')
    lab = lab[lab.condition.eq('manual')]
    lablookup = {(r.method,r.heldout_building,r.worker_id):r for r in lab.itertuples()}
    panels, links, requests, omissions = [], [], {}, []
    for pair in cap.itertuples():
        labels = cls[cls.pair_key.eq(pair.pair_key)].sort_values(['turn_history_mean','complex_turn_history_mean','class_id'])
        common = sorted(set(w for x in labels.members for w in x.split('|')))
        total = len(common)
        if total < 4 or len(labels) < 2:
            omissions.append({'pair_key':pair.pair_key, 'reason':'fewer_than_4_known_common_people_or_2_classes','common_n':total})
            continue
        for lo, hi in itertools.combinations(list(labels.itertuples()),2):
            members = [lo.members.split('|'), hi.members.split('|')]
            k = min(4,len(members[0]),len(members[1]),total-3)
            if k < 1:
                continue
            previous = set()
            n_mid = max(3,k,min(total-k,total//2))
            sizes = sorted(set(max(3,k,min(total-k,x)) for x in [math.ceil(total/3),total//2,total//2+1,math.ceil(2*total/3)]))
            for replicate in [0,1]:
                # Building-stable order increases reuse across truly observed
                # view pairs sharing a roster, without adding room relations.
                seed = f'SRCC23|{pair.building}|{lo.class_id}|{hi.class_id}|{replicate}'
                chosen = [sorted(m,key=lambda w:digest(seed+'|variable|'+w))[:k] for m in members]
                candidates = sorted(chosen[0]+chosen[1])
                rest = sorted(set(common)-set(candidates),key=lambda w:digest(seed+'|background|'+w))
                use_sizes = sizes if replicate == 0 else [n_mid]
                for n in use_sizes:
                    core = sorted(rest[:n-k])
                    panel_signature=(tuple(candidates),tuple(core))
                    if panel_signature in previous:
                        continue
                    previous.add(panel_signature)
                    panel_id = 'SRCC23P_'+digest(pair.pair_key+'|'+lo.class_id+'|'+hi.class_id+'|'+str(n)+'|'+str(replicate))[:20]
                    row = {
                        'panel_id':panel_id,'pair_key':pair.pair_key,'building':pair.building,'groups':pair.groups,
                        'image_a':pair.image_a,'image_b':pair.image_b,'image_id_a':pair.image_id_a,'image_id_b':pair.image_id_b,
                        'pool_id_a':pair.pool_id_a,'pool_id_b':pair.pool_id_b,'reference_id_a':pair.reference_id_a,'reference_id_b':pair.reference_id_b,
                        'ordinary_comparable':bool(pair.ordinary_comparable),'relation_tier':pair.relation_tier,'scope_comparable':bool(pair.scope_comparable),
                        'layer_a':pair.layer_a,'layer_b':pair.layer_b,'difficulty_a':pair.difficulty_a,'difficulty_b':pair.difficulty_b,
                        'method':'V3_BEHAVIOR','selected_family':pair.selected_family,'class_lo':lo.class_id,'class_hi':hi.class_id,
                        'lo_members_in_common':lo.members,'hi_members_in_common':hi.members,
                        'turn_center_lo':lo.turn_history_mean,'turn_center_hi':hi.turn_history_mean,
                        'complex_turn_center_lo':lo.complex_turn_history_mean,'complex_turn_center_hi':hi.complex_turn_history_mean,
                        'short_center_lo':lo.short_history_mean,'short_center_hi':hi.short_history_mean,
                        'n':n,'m_max':k,'k_selected':k,'candidate_n':2*k,'known_common_n':total,
                        'replicate':replicate,'core':'|'.join(core),'candidates':'|'.join(candidates),
                        'lo_candidates':'|'.join(sorted(chosen[0])),'hi_candidates':'|'.join(sorted(chosen[1])),
                        'n_finite_teams':math.comb(2*k,k),'member_selection':'building_stable_hash_without_target_outcomes',
                    }
                    panels.append(row)
                    for selected in itertools.combinations(candidates,k):
                        workers=sorted(core+list(selected))
                        mkey='|'.join(workers)
                        hcount=len(set(selected)&set(chosen[1]))
                        config={}
                        for method in ['V3_BEHAVIOR','V3_JOINT_QT']:
                            counts=collections.Counter()
                            known=True
                            for w in workers:
                                z=lablookup.get((method,pair.building,w))
                                good=z is not None and bool(z.known)
                                counts[z.coarse_label if good else 'unknown']+=1
                                known &= good
                            config[method]={'vector':json.dumps(dict(sorted(counts.items())),sort_keys=True,separators=(',',':')),'known':known}
                        team_keys=[]
                        for side,pool_id in [('a',pair.pool_id_a),('b',pair.pool_id_b)]:
                            key=pool_id+'__'+digest(json.dumps(workers,sort_keys=True,separators=(',',':')))[:20]
                            team_keys.append(key)
                            requests.setdefault(key,{'team_key':key,'pool_id':pool_id,'workers':workers,'members_key':mkey,'n':n,'study_request_id':'SRCC23T_'+digest(pool_id+'||'+mkey)[:24]})
                        links.append({'panel_id':panel_id,'member_set_key':mkey,'selected':'|'.join(selected),'selected_mask':sum(1<<candidates.index(w) for w in selected),
                                      'hi_selected':hcount,'lo_selected':k-hcount,'team_key_a':team_keys[0],'team_key_b':team_keys[1],
                                      'structure_vector':config['V3_BEHAVIOR']['vector'],'joint_vector':config['V3_JOINT_QT']['vector'],'joint_all_known':config['V3_JOINT_QT']['known']})
    p,l=pd.DataFrame(panels),pd.DataFrame(links)
    save_csv(p,out/'PANELS.csv')
    save_csv(l,out/'PANEL_TEAM_LINKS.csv.gz')
    save_csv(pd.DataFrame(omissions),out/'DESIGN_OMISSIONS.csv')
    dump(out/'REQUESTS.json.gz',list(requests.values()))
    summary=[]
    for layer,d in [('all_adopted_manual',p),('ordinary_comparable',p[p.ordinary_comparable]),('other_conditions',p[~p.ordinary_comparable])]:
        ll=l[l.panel_id.isin(d.panel_id)]
        summary.append({'layer':layer,'panels':len(d),'pairs':d.pair_key.nunique(),'images':len(set(d.image_a)|set(d.image_b)),
                        'buildings':d.building.nunique(),'groups':len(set('|'.join(d.groups).split('|'))-set([''])),
                        'panel_team_links':len(ll),'unique_teams':len(set(ll.team_key_a)|set(ll.team_key_b)),
                        'n_min':int(d.n.min()),'n_max':int(d.n.max()),'block_max':int(d.m_max.max())})
    pd.DataFrame(summary).to_csv(out/'DESIGN_SUMMARY.csv',index=False)
    receipt={'version':'SRCC23_paired_finite_panels_v1','seed':'SRCC23','purpose':'current class composition repetition vs exact member and view differences',
             'source_commit':'72a44e80c344975962e1071bd54d894dd86bb4b4','selection_uses_target_outcomes':False,
             'classification':'current V3_BEHAVIOR LOBO coarse; V3_JOINT_QT LOBO on identical teams as control',
             'room_relation_version':'same_room_user_working_classification_20261016_v2','requests':len(requests),'summary':summary,
             'variable_panel':'each available unordered structure-class pair; k=min(4,class_a_n,class_b_n,N-3); 2k choose k complete',
             'team_sizes':'replicate 0: ceil(N/3),floor(N/2),floor(N/2)+1,ceil(2N/3), clipped to [max(3,k),N-k]; replicate 1: clipped floor(N/2)',
             'replicates':'second independent deterministic member ordering; omit exact duplicate candidate/core panels',
             'comparison':'unordered pairs of the finite sets; m=half member symmetric difference; r=half class vector L1; same exact retained core for matched comparisons',
             'aggregation':'keep pair/group/building counts; main summaries first finite contrasts, then class-pair/replicate, direct pair, declared group, building equally; also display direct-pair weights',
             'failure':'all requests retained; missing/failed quality never replaced by zero',
             'not_exhaustive':'complete chosen variable-member panel only, not all common-person subsets or all possible core selections'}
    dump(out/'DESIGN_RECEIPT.json',receipt)
    print(pd.DataFrame(summary).to_string(index=False))
    print('n distribution',p.groupby('n').size().to_dict())
    print('candidate k',p.groupby('k_selected').size().to_dict())
    return receipt


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--capacity-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    build(a.repo,a.capacity_dir,a.out)
