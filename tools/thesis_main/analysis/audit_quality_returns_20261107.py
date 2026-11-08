"""Audit returned quality ratings; final answers are primary by user instruction.

Grade ranks (poor=0, medium=1, good=2) are a summary of ordinal judgments,
not a calibration of Q. Unknown, self-excluded and absent answers stay missing.
"""
import argparse
import gzip
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely.geometry import Polygon

from .collect_independent_review_20261107 import validate_answer
from .scope_quality_scoring_20261016 import scoring_engine

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'research/quality/validation_followup_20261107/human_review'
RANK = {'poor': 0, 'medium': 1, 'good': 2}


def effective_turns(floor):
    points = np.asarray(floor, float)
    edges = np.roll(points, -1, axis=0) - points
    previous = np.roll(edges, 1, axis=0)
    assert np.all(np.linalg.norm(edges, axis=1) > 0)
    cross = previous[:, 0] * edges[:, 1] - previous[:, 1] * edges[:, 0]
    turns = np.degrees(np.abs(np.arctan2(cross, (previous * edges).sum(axis=1))))
    return int((turns >= 5).sum())


def defect_summary(ratings, metrics):
    rows = []
    for (cid, side), group in ratings[ratings.valid].groupby(['case_id', 'side']):
        selected = [json.loads(v) for v in group.final_defects]
        known = [v for v in selected if v and 'unknown' not in v]
        row = dict(case_id=cid, side=side, known_defect_raters=len(known))
        for name in ['missing', 'extra', 'position', 'height', 'connection', 'none']:
            row[name + '_votes'] = sum(name in v for v in known)
            row[name + '_rate'] = row[name + '_votes'] / len(known) if known else np.nan
        rows.append(row)
    data = pd.DataFrame(rows).merge(metrics, on=['case_id', 'side'], validate='one_to_one')
    relations = [('missing', 'missing_turns'), ('missing', 'floor_omission'),
                 ('extra', 'extra_turns'), ('extra', 'floor_extension'),
                 ('position', 'S_bottom_deg'), ('position', 'dir'),
                 ('height', 'Hmean'), ('height', 'Hcenter'), ('height', 'height_loss')]
    summaries = []
    for defect, metric in relations:
        sub = data[[defect + '_rate', metric]].dropna()
        more = sub[sub[defect + '_rate'] >= .5][metric]
        less = sub[sub[defect + '_rate'] < .5][metric]
        summaries.append(dict(defect=defect, metric=metric, items=len(sub),
                              spearman=float(spearmanr(sub.iloc[:, 0], sub.iloc[:, 1]).statistic),
                              half_or_more_items=len(more), below_half_items=len(less),
                              half_or_more_median=float(more.median()), below_half_median=float(less.median())))
    return data, pd.DataFrame(summaries)


def mean_prism_iou(a, g):
    pa, pg = Polygon(a['floor']), Polygon(g['floor'])
    assert pa.is_valid and pg.is_valid and pa.area > 0 and pg.area > 0
    ha = np.mean(np.asarray(a['top3d'])[:, 1] - np.asarray(a['bottom3d'])[:, 1])
    hg = np.mean(np.asarray(g['top3d'])[:, 1] - np.asarray(g['bottom3d'])[:, 1])
    assert ha > 0 and hg > 0
    inter = pa.intersection(pg).area * min(ha, hg)
    return 100 * inter / (pa.area * ha + pg.area * hg - inter)


def summarize(ratings):
    v = ratings[ratings.valid & ratings.final.notna()]
    items = v.groupby(['case_id', 'side']).agg(
        human=('final', 'mean'), raters=('reviewer', 'nunique'),
        Q=('Q', 'first'), D10=('D10', 'first'), IoU=('IoU', 'first'),
        image=('image', 'first'), difficulty=('difficulty', 'first')).reset_index()
    pairs = []
    for cid, rows in ratings[ratings.valid].groupby('case_id'):
        h = rows.pivot(index='reviewer', columns='side', values='final').dropna()
        assert set(h.columns) == {'left', 'right'}
        diff = h.right - h.left
        metrics = rows.groupby('side')[['Q', 'D10', 'IoU']].first()
        r = dict(case_id=cid, image=rows.image.iloc[0], difficulty=rows.difficulty.iloc[0],
                 complete_raters=len(h), left_higher=int((diff < 0).sum()),
                 same_grade=int((diff == 0).sum()), right_higher=int((diff > 0).sum()),
                 mean_grade_difference=float(diff.mean()))
        for metric in ['Q', 'D10', 'IoU']:
            delta = float(metrics.loc['right', metric] - metrics.loc['left', metric])
            r[metric + '_right_minus_left'] = delta
            r[metric + '_agreement_count'] = int((diff * delta > 0).sum())
        pairs.append(r)
    pairs = pd.DataFrame(pairs)
    mat = v.pivot(index=['case_id', 'side'], columns='reviewer', values='final')
    agree, comparisons = 0, 0
    for a, b in itertools.combinations(mat.columns, 2):
        complete = mat[[a, b]].dropna()
        agree += int((complete[a] == complete[b]).sum())
        comparisons += len(complete)
    distinct_pairs = int((pairs.left_higher + pairs.right_higher).sum())
    summary = dict(
        ratings=len(v), items=len(items), complete_pair_judgments=int(pairs.complete_raters.sum()),
        tied_grade_pairs=int(pairs.same_grade.sum()), distinct_grade_pairs=distinct_pairs,
        item_mean_spearman={m: float(spearmanr(items.human, items[m]).statistic) for m in ['Q', 'D10', 'IoU']},
        pooled_spearman={m: float(spearmanr(v.final, v[m]).statistic) for m in ['Q', 'D10', 'IoU']},
        distinct_grade_direction_agreement={m: int(pairs[m + '_agreement_count'].sum()) for m in ['Q', 'D10', 'IoU']},
        image_mean_direction_agreement={m: int((pairs.mean_grade_difference * pairs[m + '_right_minus_left'] > 0).sum()) for m in ['Q', 'D10', 'IoU']},
        image_mean_ties=int((pairs.mean_grade_difference == 0).sum()),
        rater_pair_exact_grade_agreement=agree / comparisons if comparisons else None,
        rater_pair_comparisons=comparisons)
    return summary, items, pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('answers', nargs='+', type=Path)
    parser.add_argument('--separate-reviewer', help='User-designated respondent code to report separately, e.g. R01.')
    args = parser.parse_args()
    assignment = json.loads((HERE / 'ASSIGNMENT_PRIVATE.json').read_text(encoding='utf-8'))
    cases = json.loads(gzip.decompress((HERE / 'CASES_PRIVATE.json.gz').read_bytes()))
    metrics = []
    for case in cases:
        u = case['public']
        for side in ['left', 'right']:
            metrics.append(dict(case_id=u['id'], side=side, image=u['image'],
                                difficulty=u['difficulty'], multi_space=u['multi_space'],
                                doorway=u['doorway'], Q=u['scores'][side]['B8L2'],
                                D10=u['scores'][side]['D10'], IoU=mean_prism_iou(u[side], u['reference'])))
    engine_dir = ROOT / 'research/statistics/b8l2_shared_v6_20261016/inputs'
    components = []
    with scoring_engine(engine_dir / 'measurement_engine.zip', engine_dir / 'working_models.py') as (engine, models):
        for case in cases:
            u = case['public']
            reference = engine.geometry(u['reference']['points'])
            pg = Polygon(u['reference']['floor'])
            for side in ['left', 'right']:
                result = engine.measure(engine.geometry(u[side]['points']), reference)
                assert result['status'] == 'complete'
                m = result['metrics']
                score = float(models.score(*[m[k] for k in ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']], params=models.B))
                assert abs(score - u['scores'][side]['B8L2']) < 1e-8
                pa = Polygon(u[side]['floor'])
                inter = pa.intersection(pg).area
                turn_delta = effective_turns(u[side]['floor']) - effective_turns(u['reference']['floor'])
                components.append(dict(case_id=u['id'], side=side, **m,
                                       floor_omission=1-inter/pg.area, floor_extension=1-inter/pa.area,
                                       missing_turns=max(0, -turn_delta), extra_turns=max(0, turn_delta),
                                       height_loss=(m['Hmean']/.8)**2 + (m['Hcenter']/.25)**2))
    records, coverage, seen = [], [], set()
    for index, path in enumerate(args.answers, 1):
        d = json.loads(path.read_text(encoding='utf-8-sig'))
        # The organizer confirmed separate anonymous respondents; preserve the missing ID in the manifest.
        missing_id = not d.get('reviewer', '').strip()
        name = d.get('reviewer') or f'unnamed_file_{index}'
        assert name not in seen, 'Duplicate respondent export; choose one explicitly.'
        seen.add(name)
        d['reviewer'] = name
        rows = validate_answer(d, assignment)
        label = f'R{index:02}'
        coverage.append(dict(reviewer=label, source_file=str(path), missing_export_id=missing_id,
                             submitted=len(rows), absent_cases=','.join(sorted(set(d['case_ids']) - set(d['answers']))),
                             self_excluded=sum(r['self_excluded'] for r in rows),
                             score_viewed=sum(r['score_viewed'] for r in rows),
                             reference_viewed_initial=sum(r['reference_viewed_initial'] for r in rows),
                             changed_pairs=sum(any(r[f'{s}_grade_initial'] != r[f'{s}_grade_final'] for s in ['left', 'right']) for r in rows),
                             replacement_characters=sum(a.get('reason', '').count('\ufffd') for a in d['answers'].values())))
        for r in rows:
            for side in ['left', 'right']:
                records.append(dict(reviewer=label, case_id=r['case_id'], side=side,
                                    valid=r['valid_judgment'], self_excluded=r['self_excluded'],
                                    final=RANK.get(r[f'{side}_grade_final'], np.nan),
                                    initial=RANK.get(r[f'{side}_grade_initial'], np.nan),
                                    final_label=r[f'{side}_grade_final'],
                                    final_defects=r[f'{side}_defects_final'],
                                    score_viewed=r['score_viewed'], reference_initial=r['reference_viewed_initial']))
    frame = pd.DataFrame(records).merge(pd.DataFrame(metrics), on=['case_id', 'side'], validate='many_to_one')
    assert not frame.duplicated(['reviewer', 'case_id', 'side']).any()
    if args.separate_reviewer:
        assert args.separate_reviewer in set(frame.reviewer), 'Unknown separately reported reviewer.'
    primary = frame[frame.reviewer != args.separate_reviewer]
    summary, items, pairs = summarize(primary)
    summary.update(primary='final grades, explicitly requested by user',
                   design='30 images / 60 original annotations; ordinal grades, not a forced pairwise preference task',
                   exposure='Scores and provisional 60/80 grade cutoffs could be viewed; final judgments are not score-blind validation.',
                   respondents=primary.reviewer.nunique(), received_respondents=len(coverage),
                   separately_reported_reviewer=args.separate_reviewer,
                   submitted_pairs=sum(r['submitted'] for r in coverage if r['reviewer'] != args.separate_reviewer),
                   self_excluded_pairs=sum(r['self_excluded'] for r in coverage),
                   unknown_item_ratings=int((primary.valid & primary.final.isna()).sum()),
                   changed_item_grades=int(((primary.initial != primary.final) & primary.valid & primary.initial.notna() & primary.final.notna()).sum()),
                   missing_counts_by_image=primary[primary.valid].groupby('case_id').reviewer.nunique().value_counts().to_dict(),
                   buildings=items.image.str.split('-').str[0].nunique())
    grade_summary = primary[primary.valid & primary.final.notna()].groupby('final_label').Q.agg(['count', 'mean', 'median', 'min', 'max']).reset_index()
    per_reviewer = []
    for name, group in frame[frame.valid & frame.final.notna()].groupby('reviewer'):
        per_reviewer.append(dict(reviewer=name, n=len(group), spearman_Q=float(spearmanr(group.final, group.Q).statistic)))
    styles = []
    for name, group in frame[frame.valid].groupby('reviewer'):
        peers = primary[primary.valid & (primary.reviewer != name)]
        means = peers.groupby(['case_id', 'side']).final.mean().rename('peer_mean')
        modes = peers.groupby(['case_id', 'side']).final.agg(lambda v: v.dropna().mode().tolist()).rename('modes')
        matched = group.merge(means, on=['case_id', 'side']).merge(modes, on=['case_id', 'side'])
        matched = matched[matched.final.notna()]
        unique_modes = matched[matched.modes.map(len) == 1]
        choices = [json.loads(v) for v in group.final_defects]
        known = [v for v in choices if v and 'unknown' not in v]
        style = dict(reviewer=name, ratings=int(group.final.notna().sum()),
                     good=int((group.final == 2).sum()), medium=int((group.final == 1).sum()), poor=int((group.final == 0).sum()),
                     unknown=int(group.final.isna().sum()), known_defects=len(known), unknown_defects=sum('unknown' in v for v in choices),
                     peer_grade_mean_delta=float((matched.final - matched.peer_mean).mean()),
                     mode_agree=sum(v.final == v.modes[0] for v in unique_modes.itertuples()), mode_comparable=len(unique_modes))
        for defect in ['none', 'missing', 'extra', 'position', 'height', 'connection']:
            style[defect] = sum(defect in v for v in choices)
        styles.append(style)
    defects, defect_relations = defect_summary(primary, pd.DataFrame(components))
    out = HERE / 'returned_20261107'
    out.mkdir(exist_ok=True)
    if args.separate_reviewer:
        all_summary, all_items, all_pairs = summarize(frame)
        all_defects, all_relations = defect_summary(frame, pd.DataFrame(components))
        separate = frame[frame.reviewer == args.separate_reviewer]
        separate_summary, separate_items, separate_pairs = summarize(separate)
        for prefix, result in [('ALL_NINE', all_summary), ('SEPARATE_REVIEWER', separate_summary)]:
            (out / f'{prefix}_SUMMARY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        for name, data in [('ALL_NINE_ITEM_MEANS', all_items), ('ALL_NINE_PAIR_DIRECTIONS', all_pairs),
                           ('ALL_NINE_DEFECT_COMPONENTS', all_defects), ('ALL_NINE_DEFECT_RELATIONS', all_relations),
                           ('SEPARATE_REVIEWER_RATINGS', separate)]:
            data.to_csv(out / f'{name}.csv', index=False, encoding='utf-8-sig')
    for name, data in [('RATINGS', frame), ('ITEM_MEANS', items), ('PAIR_DIRECTIONS', pairs),
                       ('SOURCE_COVERAGE_PRIVATE', pd.DataFrame(coverage)), ('GRADE_Q', grade_summary),
                       ('PER_REVIEWER', pd.DataFrame(per_reviewer)), ('DEFECT_COMPONENTS', defects),
                       ('DEFECT_RELATIONS', defect_relations), ('REVIEWER_STYLE', pd.DataFrame(styles))]:
        data.to_csv(out / f'{name}.csv', index=False, encoding='utf-8-sig')
    (out / 'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(grade_summary.to_string(index=False))
    print(pd.DataFrame(coverage).drop(columns='source_file').to_string(index=False))
    print(pairs[['case_id', 'complete_raters', 'left_higher', 'same_grade', 'right_higher', 'mean_grade_difference', 'Q_right_minus_left', 'IoU_right_minus_left']].to_string(index=False))
    print(defect_relations.to_string(index=False))


if __name__ == '__main__':
    main()
