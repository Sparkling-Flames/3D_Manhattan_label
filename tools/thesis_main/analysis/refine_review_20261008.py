"""7.5—9区间迁移与未决局部复审；固定池、MV50和定位，不套用人审修改。"""
import json
from concurrent.futures import ProcessPoolExecutor, as_completed

from .population_gap_20261007 import OUT as POP, compare_states
from .correspondence_gap_20261007 import (OUT as GAP_OUT, DEVELOPMENT, read, key,
    review_cases, evaluate, local_failure_counts)
from .research_artifact_io import ROOT, write_json, write_csv
from .ring_correspondence_20261007 import build

OUT = POP / 'refine_20261008'
COARSE = [7.5, 8., 8.5, 9.]
FINE = [n / 10 for n in range(75, 91)]
QUESTIONS = {
    'jtcxE69GiFV-28': '原G07最右一份与其余来源：请点选具体人员，判断目标。原G14/G15仍不清楚时可继续留不确定。',
    'pa4otMbVnkk-10': '原G09与G03是否是同一处转折？先看各自完整原环；距离大本身不决定身份。',
    'q9vSo1VnCiC-23': '原G05含P027与P007，请分别选择他们与比较对象。上次认为P027勉强可合、P007不同，不要求整组给同一答案。',
    'uNb9QFRL6hY-08': '只补原G04中具体哪份与G06同角，以及右侧两个停止目标；归类可用性的判断另填。原G05与G03同墙线的判断保留。',
    'uNb9QFRL6hY-41': '原G02/G09和G03/G10是否表达里外不同停止点？没有足够场景信息可以继续不确定，已有14份同角判断保留。',
    'uNb9QFRL6hY-65': '请从原9参数G08点选应拆出的那一份，并选择一份对照。上次“最左边”尚未绑定到具体来源。',
    'uNb9QFRL6hY-78': '上次已倾向同墙线，但未勾选完成。仅确认或保留不确定即可，不要求重新核查整图。',
    'uNb9QFRL6hY-86': '请看原G06这位人员的完整连接，判断停止目标；GT有没有画门口不是决定条件。仍看不出意图可留不确定。',
    'wc2JMjhGNzB-53': '原G03/G04包含P001同份作答的两对点，请查看其完整连接，区分细节多画与不同转折。其它局部可以只挑确定的人员；不必强行归类。',
    'yqstnuAEVhm-25': '已有遮挡墙线同目标判断保留。这次只确认所选来源是否仍想标同一墙线，以及所示归类是否可用，不评融合坐标。',
    'zsNo4HB9uLZ-05': '先点选你认为同一遮挡墙线的具体来源，判断是否想标同一墙线，以及所示归类是否可用；不用因为难以定位而强行判成不同墙线。',
}


def scan_image(job):
    item, gaps = job
    code = item['image']; rows = []
    for gap in gaps:
        name = f'{code}_gap_{gap:g}.json'
        sources = [OUT/name, POP/name, GAP_OUT/'fine'/name, GAP_OUT/'fine/check'/name]
        source = next((p for p in sources if p.exists()), None)
        if source:
            result = read(source); origin = 'reused'
        else:
            result = build(item['records'], gap=gap); origin = 'new'
        write_json(OUT/name, result)
        rows.append(dict(image=code, gap=gap, origin=origin))
    return rows


def changing_codes(inputs, gaps):
    return [im['image'] for im in inputs if any(
        compare_states(read(OUT/f"{im['image']}_gap_7.5.json"),
                       read(OUT/f"{im['image']}_gap_{gap:g}.json"))['changed_observations']
        for gap in gaps if gap != 7.5)]


def run():
    OUT.mkdir(exist_ok=True)
    failures = {x['image'] for x in read(POP/'failures.json')}
    inputs = [im for im in read(POP/'inputs.json')['images'] if im['image'] not in failures]
    prior = read(POP/'user_review_workbench_20261008.json')
    reviewed = {d['image'] for d in prior['decisions'] if d['note'] or d['issues'] or d['verdicts']}
    write_json(OUT/'PLAN.json', dict(coarse=COARSE, fine=FINE, images=len(inputs),
        input='Same recorded full pools as population/inputs.json; known whole-pool failure unchanged.',
        refine='Any partition change at 7.5/8/8.5/9, plus reviewed images and existing development cases.',
        fixed='Original algorithm, full N MV50, equal-person medians; no GT or manual edits in automatic states.',
        limitation='Discrete sample changes, not continuous breakpoints or certified accuracy.'))
    rows = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(scan_image, (im, COARSE)): im['image'] for im in inputs}
        for i, future in enumerate(as_completed(jobs), 1):
            rows.extend(future.result())
            print('coarse', i, '/', len(inputs), jobs[future], flush=True)
        changed = changing_codes(inputs, COARSE)
        refine = set(changed) | reviewed | set(DEVELOPMENT)
        todo = [im for im in inputs if im['image'] in refine]
        jobs = {pool.submit(scan_image, (im, [g for g in FINE if g not in COARSE])): im['image'] for im in todo}
        for i, future in enumerate(as_completed(jobs), 1):
            rows.extend(future.result())
            print('fine', i, '/', len(todo), jobs[future], flush=True)
    write_json(OUT/'refined_images.json', dict(sampled_partition_changes=changed,
        fine_images=[im['image'] for im in todo], review_images=list(QUESTIONS)))
    cases = review_cases() + read(POP/'review_cases.json')
    summary = []; relations = []; transitions = []
    for im in inputs:
        code = im['image']; gaps = FINE if code in refine else COARSE
        states = {g: read(OUT/f'{code}_gap_{g:g}.json') for g in gaps}
        for gap, result in states.items():
            local = [dict(gap=gap, **evaluate(result, c)) for c in cases if c['image'] == code]
            relations.extend(local)
            comparison = compare_states(states[9.], result)
            summary.append(dict(image=code, gap=gap, n=len(im['records']),
                nodes=len(result['node_consensus']['nodes']), **comparison, **local_failure_counts(local)))
        for a, b in zip(gaps, gaps[1:]):
            change = compare_states(states[a], states[b])
            if change['changed_observations']:
                transitions.append(dict(image=code, lower=a, upper=b, **change))
    write_csv(OUT/'computed.csv', sorted(rows, key=lambda r: (r['image'], r['gap'])))
    write_csv(OUT/'summary.csv', summary); write_csv(OUT/'transitions.csv', transitions)
    write_json(OUT/'relations.json', relations)
    write_json(OUT/'field_contract.json', dict(
        rows='summary: image/gap, n/nodes, membership and center equality vs9, known local relation counts.',
        transitions='Adjacent sampled gaps with changed full partition, not exact critical value.',
        human='Prior workbench feedback remains raw text, not automatically converted to hard constraints.',
        identity_mixed='Contains-different means selected observations are not all one identity, not that every pair is different.',
        review_schema='wall_identity_review_20261008_v2; prior read-only, new decisions initially blank; issues.groups preserve full algorithm groups, selected_members records the precise observations judged; identity judgement concerns selected_members only; verdicts describe usability. User does not choose parameters or judge coordinate estimators.'))
    build_review()
    print('DONE', len(inputs), len(todo), len(summary), len(transitions), flush=True)


def build_review():
    # Preserve original G labels and all prior answers; new signatures get new labels.
    old = (POP/'review.html').read_text(encoding='utf-8')
    data = json.loads(old.split('<script id="source" type="application/json">')[1].split('</script>')[0])
    prior = {r['image']: r for r in read(POP/'user_review_workbench_20261008.json')['decisions']}
    for im in data['images']:
        im['src'] = '../' + im['src']; im['priority'] = im['code'] in QUESTIONS
        im['question'] = QUESTIONS.get(im['code'], '非本轮必审图，可选查看。')
        im['prior'] = prior[im['code']]
        lookup = {key(m): i for i, m in enumerate(im['observations'])}
        labels = {tuple(g['members']): g['label'] for groups in im['states'].values() for g in groups}
        available = []
        for gap in FINE:
            path = OUT/f"{im['code']}_gap_{gap:g}.json"
            if not path.exists(): continue
            available.append(gap); groups = []
            for g in read(path)['identity_groups']:
                members = sorted(lookup[key(m)] for m in g['members']); sig = tuple(members)
                if sig not in labels: labels[sig] = 'G' + str(len(labels)+1).zfill(2)
                groups.append(dict(label=labels[sig], members=members, support=g['support'],
                    selected=g['selected'], center=g['center'], feature_id=g['feature_id']))
            im['states'][f'{gap:g}'] = groups
        im['available_gaps'] = available
    data.update(schema='wall_identity_review_20261008_v2', revision=True, gaps=FINE,
                priority_count=sum(im['priority'] for im in data['images']))
    template = (ROOT/'tools/thesis_main/analysis/wall_identity_review_20261007.html').read_text(encoding='utf-8')
    page = template.replace('/*__DATA__*/', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    (OUT/'review.html').write_text(page, encoding='utf-8')


if __name__ == '__main__': run()
