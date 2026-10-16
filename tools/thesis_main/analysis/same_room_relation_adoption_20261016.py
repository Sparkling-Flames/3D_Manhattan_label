"""已有260组用户分类的版本化采用；状态不作门，不跨组传递。"""
from collections import Counter
from itertools import combinations
import json

import pandas as pd

from .same_room_b8l2_20261016 import ROOT
from .same_room_quality_curves_20261015 import save

SOURCE = ROOT / 'analysis_results/final_review_summary_20260929/同房分类_原始完整记录.json'
OUT = ROOT / 'research/same_room/relation_adoption_20261016'
VERSION = 'same_room_user_working_classification_20261016_v2'


def adopt_relations(registry):
    groups = {g['review_code']: g for g in registry['groups']}
    pairs = {}; candidates = []
    def add(ids, evidence):
        for pair in combinations(sorted(ids), 2):
            pairs.setdefault(pair, dict(candidates=[], evidence=[]))['evidence'].append(evidence.copy())
    for group in groups.values():
        current = group['raw_current']
        interpretation = group['interpretation']
        # G196 comment identifies 42 as possibly outside the 61/82 room, not just a different view.
        outside = set(interpretation.get('oos_numbers', [])) if group['review_code'] == 'G196' else set()
        numbers = dict(zip(group['image_ids'], group['numbers']))
        for pair in combinations(sorted(group['image_ids']), 2):
            substantive_conflict = bool(outside & {numbers[i] for i in pair})
            scope_exception = bool(interpretation.get('subgroups') or interpretation.get('core'))
            if group['review_code'] == 'G214' and 41 in {numbers[i] for i in pair}:
                scope_exception = True
            oos = bool(interpretation.get('oos')) and (not interpretation.get('oos_numbers') or
                bool(set(interpretation['oos_numbers']) & {numbers[i] for i in pair}))
            raw_comparable = (current['physical_same']=='支持' and current['main_visual_alignment']=='一致'
                and current['extent_alignment']=='预期相近' and not scope_exception and not substantive_conflict)
            add(pair, dict(source_group_codes=[group['review_code']], source_kind='original_group',
                physical_value=current['physical_same'], physical_supported=current['physical_same']=='支持' and not substantive_conflict,
                substantive_conflict=substantive_conflict, comparable=raw_comparable and not oos,
                scope_comparable=raw_comparable, oos_pending=oos,
                difficulty_similarity=current['difficulty_similarity'], review_state=group['review_state'],
                note=current['note'], scope_basis='original group physical classification; candidate scopes separate'))
    for candidate in registry['candidates']:
        source = [groups[code] for code in candidate['source_group_codes']]
        main = source[0]
        interpretation = main['interpretation']
        scope = candidate['subset_scope']
        comparable = candidate['comparable_for_prediction']
        basis = 'existing candidate visual/extent classification'
        if scope == 'information_mismatch' or candidate['candidate_id'] == 'G172':
            comparable = (main['raw_current']['main_visual_alignment']=='一致' and
                          main['raw_current']['extent_alignment']=='预期相近')
            basis = 'original scope fields retained; view information/doorway location alone is not scope negation'
        if scope == 'explicit_split' and interpretation.get('subgroups'):
            comparable = True
            basis = 'user explicitly permits pairing inside each declared split'
        elif scope == 'comment_supported_subset' and (
            main['raw_current']['extent_alignment'] == '预期相近' or '可以归一起' in main['raw_current']['note']):
            comparable = True
            basis = 'user declared retained subgroup; parent exceptions excluded; working comparability'
        physical = candidate['physical_same_supported'] and all(g['raw_current']['physical_same']=='支持' for g in source)
        adopted = physical and comparable and not candidate['oos_pending']
        blocked_by_status = (candidate['physical_same_supported'] and candidate['comparable_for_prediction']
            and not candidate['oos_pending'] and candidate['review_state'] != 'explicit_confirmed')
        audit = dict(candidate_id=candidate['candidate_id'], source_group_codes=candidate['source_group_codes'],
            image_ids=candidate['image_ids'], numbers=candidate['numbers'], review_state=candidate['review_state'],
            old_comparable=candidate['comparable_for_prediction'], adopted_comparable=adopted,
            physical_supported=physical, scope_comparable=bool(comparable), oos_pending=candidate['oos_pending'],
            scope_basis=basis, subset_scope=scope, difficulty_similarity=candidate['difficulty_similarity'],
            status_only_previously_blocked=blocked_by_status, notes=[g['raw_current']['note'] for g in source])
        candidates.append(audit)
        evidence = dict(audit, source_kind='candidate_subset', physical_value='支持' if physical else main['raw_current']['physical_same'],
            comparable=adopted, substantive_conflict=False, note='\n'.join(audit['notes']))
        add(candidate['image_ids'], evidence)
        for pair in combinations(sorted(candidate['image_ids']), 2):
            pairs[pair]['candidates'].append(candidate['candidate_id'])
    for pair, row in pairs.items():
        ev = row['evidence']
        negative = any(e['physical_value']=='不支持' for e in ev)
        positive = any(e['physical_supported'] for e in ev)
        conflict = any(e['substantive_conflict'] for e in ev) or (negative and positive)
        physical = positive and not conflict
        comparable = physical and any(e['comparable'] for e in ev)
        row.update(adoption_version=VERSION, physical_adopted=physical,
            scope_comparable=physical and any(e.get('scope_comparable', False) for e in ev), substantive_conflict=conflict,
            oos_pending=any(e['oos_pending'] for e in ev),
            user_group_ids=sorted({code for e in ev for code in e['source_group_codes']}),
            tier='user_classified_comparable' if comparable else 'user_classified_other_scope' if physical else
                 'content_disputed' if conflict else 'not_supported' if negative else 'physical_pending')
        row['analysis_layer'] = row['tier']
    return pairs, candidates


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = json.loads(SOURCE.read_text(encoding='utf-8'))
    csv = pd.read_csv(SOURCE.parent / '同房原分组_完整分类.csv').fillna('').set_index('review_code')
    for group in registry['groups']:
        assert group['viewed']
        for key, value in group['raw_current'].items():
            assert csv.loc[group['review_code'], key] == value, (group['review_code'], key)
    pairs, candidates = adopt_relations(registry)
    save(OUT, 'original_groups.json', registry['groups'])
    save(OUT, 'candidate_adoption.json', candidates)
    save(OUT, 'relations.json', [dict(image_a=a, image_b=b, **r) for (a,b),r in sorted(pairs.items())])
    save(OUT, 'status_string_blocked_candidates.csv', pd.DataFrame([c for c in candidates if c['status_only_previously_blocked']]))
    save(OUT, 'candidate_adoption.csv', pd.DataFrame(candidates))
    save(OUT, 'pair_adoption.csv', pd.DataFrame([dict(image_a=a, image_b=b,
        **{k:v for k,v in r.items() if k!='evidence'}, evidence=json.dumps(r['evidence'], ensure_ascii=False))
        for (a,b),r in sorted(pairs.items())]))
    save(OUT, 'SUMMARY.json', dict(version=VERSION, original_groups=len(registry['groups']),
        all_groups_viewed=all(g['viewed'] for g in registry['groups']),
        raw_physical_classification=dict(Counter(g['raw_current']['physical_same'] for g in registry['groups'])),
        original_review_states=dict(Counter(g['review_state'] for g in registry['groups'])),
        candidates=len(candidates), pairs=len(pairs), pair_layers=dict(Counter(r['tier'] for r in pairs.values())),
        status_only_blocked=[c['candidate_id'] for c in candidates if c['status_only_previously_blocked']],
        viewed_status_only_blocked=[c['candidate_id'] for c in candidates if c['status_only_previously_blocked'] and c['review_state']=='viewed_per_user_statement'],
        candidate_scope_repaired=[c['candidate_id'] for c in candidates if c['adopted_comparable'] and not c['old_comparable']],
        cross_group_transitive_extension=False, stable_physical_room_id_required=False))
    manifest = dict(version=VERSION, status='frozen_for_same_room_and_statistics_consumers', frozen=True,
        supersedes='v1 development delivery; v2 freezes restored original scope fields and comment exceptions',
        original_source=SOURCE.relative_to(ROOT).as_posix(),
        original_csv=(SOURCE.parent/'同房原分组_完整分类.csv').relative_to(ROOT).as_posix(),
        relations=(OUT/'relations.json').relative_to(ROOT).as_posix(),
        original_groups=(OUT/'original_groups.json').relative_to(ROOT).as_posix(),
        candidate_adoption=(OUT/'candidate_adoption.json').relative_to(ROOT).as_posix(),
        rules=dict(review_status='provenance only, never admission',
            physical='positive existing group classification; explicit contrary comment/conflict retained',
            scopes='original physical group and user-declared comparison subsets separate; comment repairs audited',
            difficulty='retain original similarity/difference; not a comparison admission gate',
            quality='actual shared quality_usable, own reference, same condition and common people required separately',
            time='source/time-binding gates independent of quality and scope',
            closure='only directly listed group members and explicitly merged group, no cross-group transitive closure'))
    save(OUT, 'CROSS_MODULE_RELATIONS.json', manifest)
    save(OUT, 'FIELD_CONTRACT.json', dict(version=VERSION,
        relation_fields=list(next(iter(pairs.values()))),
        tiers=['user_classified_comparable','user_classified_other_scope','content_disputed','not_supported','physical_pending'],
        evidence='original fields and notes + candidate subset provenance; original_groups retains all 260 classifications',
        physical='working user classification, not new geometry certification',
        scope='working expected annotation-scope comparability, not precise geometric identity',
        OOS='relation oos_pending preserved separately; never overrides shared OOS diagnostic-only rule',
        status='explicit_confirmed/viewed/discussion retained without standalone gating'))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
