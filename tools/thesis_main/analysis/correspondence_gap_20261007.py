"""固定人审关系下的跳过代价对照；不以GT、点数或几何通过率选参数。"""
import itertools
import json

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from .ring_correspondence_20261007 import build
from .correspondence_expanded_20261007 import partition

OUT = ROOT / 'analysis_results/direct_fusion_20261007/gap_sweep'
DIRECT = ROOT / 'analysis_results/direct_fusion_20261007'
RING = ROOT / 'analysis_results/ring_correspondence_20261007'
GAPS = (9., 13.5, 18.)
DEVELOPMENT = ['2t7WUuJeko7-06', 'rPc6DW4iMge-06', 'yqstnuAEVhm-25',
               'uNb9QFRL6hY-41', 'uNb9QFRL6hY-67', 'uNb9QFRL6hY-36',
               'uNb9QFRL6hY-04', 'B6ByNegPMKs-11', 'q9vSo1VnCiC-32', 'jtcxE69GiFV-26']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def key(member):
    return (member['id'], member['pair_index'])


def review_cases():
    cases = []
    old = ROOT / 'research/structure_constraints_20261006/human_review.json'
    for r in read(old)['reviews']:
        if r['relation'] != 'same_corner_pair':
            continue  # Different upper targets do not establish different wall-line identities.
        members = list(zip(r['record_ids'], r['processed_pair_indices']))
        groups = [members]
        if r['case_id'] == 'rpc_lower':
            groups.append([(r['record_ids'][-1], r['rejected_previous_purple_processed_pair_index'])])
        cases.append(dict(case=r['case_id'], image=r['image'], groups=groups,
                          status='confirmed_local', source=str(old.relative_to(ROOT))))
    yq = read(RING / 'user_review.json')
    cases.append(dict(case='yq_five_confirmed_additions', image=yq['image'],
        groups=[yq['identity']['members']], status='confirmed_local',
        source='analysis_results/ring_correspondence_20261007/user_review.json:identity',
        scope='Only the five explicitly reviewed additions; not all 18 automatically certified.'))
    rows = read_csv(ROOT / 'analysis_results/adaptive_point_20261007/expanded/g184/source_ledger.csv')
    members = [(r['record'], int(r['processed_pair_index'])) for r in rows if r['image'] == 'uNb9QFRL6hY-41']
    assert len(members) == len(set(members)) == 14
    cases.append(dict(case='uNb41_known14', image='uNb9QFRL6hY-41', groups=[members],
        status='confirmed_local', source='analysis_results/ring_correspondence_20261007/user_review.json:followup_20261007',
        member_source='analysis_results/adaptive_point_20261007/expanded/g184/source_ledger.csv'))
    for r in read(DIRECT / 'user_review.json')['decisions']:
        provisional = r['decision'] == 'retain_same_identity_provisionally'
        groups = [[key(m) for m in r['members']]] if provisional else [
            [key(m) for m in g['members']] for g in r['groups']]
        cases.append(dict(case=r['image']+'_'+r['feature_id'], image=r['image'], groups=groups,
            status='provisional' if provisional else 'confirmed_local',
            source='analysis_results/direct_fusion_20261007/user_review.json', decision=r['decision']))
    updated = OUT / 'user_review.json'
    if updated.exists():
        for r in read(updated)['decisions']:
            if r['image']=='yqstnuAEVhm-25':
                case=next(c for c in cases if c['case']=='yq_five_confirmed_additions')
                case.update(case='yq_ten_confirmed',groups=[sorted(set(map(tuple,case['groups'][0])) |
                    {tuple(m) for m in r['confirmed_same_members']})],
                    followup_source=str(updated.relative_to(ROOT)),scope='Ten explicitly reviewed observations; the other eight remain unreviewed individually.')
            elif r['image']=='rPc6DW4iMge-06':
                original=next(c for c in cases if c['case']=='rpc_lower')
                cases.append(dict(case='rpc_first_new_A',image=r['image'],status='user_A_interpretation',
                    groups=[original['groups'][0]+r['first_A_members'],original['groups'][1]],
                    source=str(updated.relative_to(ROOT)),scope='First new source interpreted as A; second source is target-ambiguous and excluded from hard relations.'))
    return cases


def evaluate(result, case):
    """Only explicit same/different relations are scored; extra members remain unreviewed."""
    lookup = {key(m): g for g in result['identity_groups'] for m in g['members']}
    groups = [[tuple(m) for m in group] for group in case['groups']]
    same = [p for group in groups for p in itertools.combinations(group, 2)]
    different = [p for a, b in itertools.combinations(groups, 2) for p in itertools.product(a, b)]
    same_group = lambda a, b: lookup[a]['feature_id'] == lookup[b]['feature_id']
    reviewed = set(itertools.chain.from_iterable(groups))
    touched = {lookup[m]['feature_id']: lookup[m] for m in reviewed}
    return dict(case=case['case'], image=case['image'], review_status=case['status'],
        same_pairs=len(same), split_pairs=sum(not same_group(*p) for p in same),
        different_pairs=len(different), merged_pairs=sum(same_group(*p) for p in different),
        reviewed_members=len(reviewed),
        groups=[dict(feature_id=g['feature_id'], support=g['support'], selected=g['selected'], center=g['center'],
                     reviewed_members=sorted(reviewed & {key(m) for m in g['members']}),
                     unreviewed_members=sorted({key(m) for m in g['members']} - reviewed)) for g in touched.values()])


def same_pair_trace(result, cases, gap):
    """Locate whether a confirmed split occurs in pairwise matching or subsequent grouping."""
    lookup = {key(m): g for g in result['identity_groups'] for m in g['members']}
    matches = {(p['a'], p['b']): set(map(tuple, p['matches'])) for p in result['pairwise']}
    rows = []
    for case in cases:
        for cohort in case['groups']:
            for a, b in itertools.combinations(map(tuple, cohort), 2):
                if a[0] == b[0]:
                    continue
                if (a[0], b[0]) not in matches:
                    a, b = b, a
                paired = (a[1], b[1]) in matches[a[0], b[0]]
                joined = lookup[a]['feature_id'] == lookup[b]['feature_id']
                if not joined:
                    rows.append(dict(case=case['case'], gap=gap, a=a, b=b, directly_matched=paired,
                        a_partner=[q for p, q in matches[a[0], b[0]] if p == a[1]],
                        b_partner=[p for p, q in matches[a[0], b[0]] if q == b[1]],
                        a_group=lookup[a]['feature_id'], b_group=lookup[b]['feature_id'],
                        a_support=lookup[a]['support'], b_support=lookup[b]['support']))
    return rows


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    OUT.mkdir(parents=True, exist_ok=True)
    extra = read(DIRECT / 'workflow/panel.json')['new_images']
    codes = DEVELOPMENT + [c for c in extra if c not in DEVELOPMENT]
    buildings = {c.split('-')[0] for c in DEVELOPMENT}
    panel = [dict(image=c, role='development' if c in DEVELOPMENT else
                  ('same_building_check' if c.split('-')[0] in buildings else 'other_building_check')) for c in codes]
    cases = review_cases()
    write_json(OUT / 'PLAN.json', dict(panel=panel, gaps=GAPS, baseline=13.5,
        input='load_current_bundle, same full independent Manual main_candidate pools; shared-x and source order unchanged',
        selection='explicit local same/different identities; provisional case separate; no GT selection',
        transfer='Other-building images are previously viewed development material, not a blind validation or labelled accuracy panel.',
        fixed='MV50 full N, equal-person coordinate median, source-order suggestion; no human edits applied to parameter candidates',
        adoption='No automatic replacement of production default; inspect false merges and splits separately.'))
    write_json(OUT / 'review_cases.json', cases)
    write_json(OUT / 'field_contract.json', dict(schema='correspondence_gap_v1',
        summary='One image/gap row. partitions_equal_baseline compares source membership sets, not unstable node IDs.',
        relations='Explicit within-reviewed-cohort pairs should join; cross-cohort pairs should separate. Counts are dependent relations, not independent people or whole-image accuracy.',
        unreviewed='Members beyond each reviewed set remain unknown; no scores inferred from absence of review.',
        human_status='confirmed_local, provisional and user_A_interpretation remain separate; target-ambiguous sources do not create hard relations.',
        trace='Failed same pairs: direct pairwise match vs final group membership. Missing fields fail visibly.',
        states='Automatic results only, source members and complete node/candidate outputs. Current human-assisted workflow untouched.'))
    bundle = load_current_bundle(); data, aliases = project_bundle(bundle)
    images = {im['code']: im for im in data['images']}
    objects = {aliases['records'][o['object_id']]: o for o in bundle['data']['objects']}
    all_rows = []; relations = []; traces = []; inputs = []
    for row in panel:
        code = row['image']
        records = sorted([dict(r) for r in images[code]['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'], key=lambda r:r['id'])
        for r in records:
            o = objects[r['id']]; r.update(object_id=o['object_id'], source_pair_indices=o['ordered_source_pair_indices'])
        old = read(DIRECT / (code+'.json'))
        assert {r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in records} == {
            r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in old['records']}, code
        inputs.append(dict(image=code, image_id=old['image_id'], records=records))
        states = {gap:build(records,gap=gap) for gap in GAPS}
        baseline = states[13.5]
        assert partition(baseline) == partition(old['correspondence']), code
        for gap, result in states.items():
            write_json(OUT / f'{code}_gap_{gap:g}.json', result)
            group_lookup = {key(m): frozenset(key(x) for x in g['members']) for g in result['identity_groups'] for m in g['members']}
            base_lookup = {key(m): frozenset(key(x) for x in g['members']) for g in baseline['identity_groups'] for m in g['members']}
            item = dict(**row, gap=gap, n=len(records), nodes=len(result['node_consensus']['nodes']),
                identities=len(result['identity_groups']), partitions_equal_baseline=partition(result)==partition(baseline),
                changed_observations=sum(group_lookup[k]!=base_lookup[k] for k in base_lookup),
                ordered_points_equal_baseline=result['candidate']['points']==baseline['candidate']['points'],
                geometry_status=result['candidate'].get('geometry_status','not_evaluable'))
            all_rows.append(item)
            local = [c for c in cases if c['image']==code]
            relations.extend(dict(gap=gap,**evaluate(result,c)) for c in local)
            traces.extend(dict(image=code,**r) for r in same_pair_trace(result,local,gap))
        print(code, 'N='+str(len(records)), [(g, len(states[g]['node_consensus']['nodes'])) for g in GAPS], flush=True)
    write_json(OUT / 'inputs.json', dict(images=inputs))
    write_csv(OUT / 'summary.csv', all_rows)
    write_json(OUT / 'relations.json', relations)
    write_csv(OUT / 'relations.csv', [{k:v for k,v in r.items() if k!='groups'} for r in relations])
    write_json(OUT / 'split_trace.json', traces)
    report(all_rows, relations)


def report(rows, relations):
    lines = ['# 跳过代价9／13.5／18对照', '',
        '研究解释与后续安排见[首轮结论](CONCLUSIONS.md)。', '',
        '固定当前输入、全池MV50和中位数，仅改变对应中的跳过代价；不使用GT选参数。', '',
        '人审仅约束列明来源。未审成员不认证；关系对数不是独立样本。jtc-26暂定判断单列。', '',
        '| 已有人审案例 | 状态 | 9° 拆散／误合 | 13.5° 拆散／误合 | 18° 拆散／误合 | 同角／异角关系总数 |',
        '|---|---|---|---|---|---|']
    for name in dict.fromkeys(r['case'] for r in relations):
        rr = [r for r in relations if r['case']==name]
        status={'confirmed_local':'已确认局部','provisional':'暂按同角','user_A_interpretation':'新增A解释'}[rr[0]['review_status']]
        lines.append('| '+name+' | '+status+' | '+' | '.join(f"{r['split_pairs']}／{r['merged_pairs']}" for r in rr)+f" | {rr[0]['same_pairs']}／{rr[0]['different_pairs']} |")
    lines += ['', '## 完整输出与扩展检查', '', '| 图片 | 检查范围 | N | 9／13.5／18节点数 | 9／18变化观察数 |', '|---|---|---|---|---|']
    for code in dict.fromkeys(r['image'] for r in rows):
        rr = [r for r in rows if r['image']==code]
        role={'development':'开发案例','same_building_check':'同建筑其它图','other_building_check':'其它建筑'}[rr[0]['role']]
        lines.append(f"| {code} | {role} | {rr[0]['n']} | "+'／'.join(str(r['nodes']) for r in rr)+f" | {rr[0]['changed_observations']}／{rr[-1]['changed_observations']} |")
    lines += ['', '变化观察数指所在成员集合发生变化；节点数与几何通过均不作语义准确率。',
        '建筑外图片也是已查看过的开发材料，只能检验参数敏感性，不能宣称盲测或完整对应正确率。', '',
        '来源：[人审关系](review_cases.json)、[分组与未审成员](relations.json)、[同角拆散路径](split_trace.json)、[逐图汇总](summary.csv)。', '',
        '复算：`python -m tools.thesis_main.analysis.correspondence_gap_20261007`。现行13.5默认值和人工辅助结果不覆盖。']
    (OUT / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def refresh_reviews():
    """New human relations reuse the already computed states; no geometry or matching rerun."""
    cases=review_cases();relations=[];traces=[]
    for row in read(OUT/'PLAN.json')['panel']:
        local=[c for c in cases if c['image']==row['image']]
        for gap in GAPS:
            r=read(OUT/f"{row['image']}_gap_{gap:g}.json")
            relations.extend(dict(gap=gap,**evaluate(r,c)) for c in local)
            traces.extend(dict(image=row['image'],**t) for t in same_pair_trace(r,local,gap))
    write_json(OUT/'review_cases.json',cases)
    write_json(OUT/'relations.json',relations)
    write_csv(OUT/'relations.csv',[{k:v for k,v in r.items() if k!='groups'} for r in relations])
    write_json(OUT/'split_trace.json',traces)
    report(read_csv(OUT/'summary.csv'),relations)


def diagnostics():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from .direct_fusion_20261007 import draw_layout
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    inputs = {r['image']:r for r in read(OUT / 'inputs.json')['images']}

    def photo(code):
        return Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+inputs[code]['image_id']+'.png')))

    def state(code, gap):
        return read(OUT / f'{code}_gap_{gap:g}.json')

    effects = []
    for code in ['yqstnuAEVhm-25', 'rPc6DW4iMge-06', 'uNb9QFRL6hY-04', 'B6ByNegPMKs-11', 'q9vSo1VnCiC-32']:
        fig, axes = plt.subplots(1,3,figsize=(18,5))
        for ax, gap in zip(axes,GAPS):
            r = state(code,gap); ax.imshow(photo(code),extent=(0,1024,512,0))
            for record in inputs[code]['records']:
                draw_layout(ax,record['points'],'gray',.10)
            p = r['candidate']['points']
            if p:
                draw_layout(ax,p,'#ff4040',.85)
            for g in r['identity_groups']:
                if not g['selected'] or g['center'] is None:
                    continue
                x,y = g['center'][0]
                ax.text(x,y-8,str(g['support'])+'/'+str(r['n']),color='#ffc000',fontsize=8,
                        bbox=dict(facecolor='black',alpha=.45,pad=.6))
            ax.set_title(f'跳过代价{gap:g}°；{len(r["node_consensus"]["nodes"])}个节点')
            ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        fig.suptitle(code+'：自动结果／相同原始人员池；灰为来源，红为融合，黄色为支持人数；没有GT')
        fig.tight_layout();fig.savefig(OUT/(code+'_comparison.png'),dpi=135);plt.close(fig)
        if (DIRECT/(code+'_assisted.json')).exists():
            assisted=read(DIRECT/(code+'_assisted.json'))
            def selected(r):
                return {frozenset(key(m) for m in g['members']):g['center'] for g in r['identity_groups'] if g['selected']}
            effects.append(dict(image=code, gap=9, selected_members_and_centers_equal_assisted=selected(state(code,9))==selected(assisted)))
    write_json(OUT/'assisted_comparison.json',effects)

    code='rPc6DW4iMge-06';conflicts=[]
    for gap in GAPS:
        r=state(code,gap);lookup={key(m):g for g in r['identity_groups'] for m in g['members']}
        a,b=lookup['R02452',2],lookup['R01986',2]
        matches={(p['a'],p['b']):set(map(tuple,p['matches'])) for p in r['pairwise']}
        incompatible=[];matched=0;duplicates=[]
        for x,y in itertools.product(a['members'],b['members']):
            if x['id']==y['id']:
                duplicates.append([key(x),key(y)]);continue
            if (x['id'],y['id']) not in matches:x,y=y,x
            pairs=matches[x['id'],y['id']]
            if (x['pair_index'],y['pair_index']) in pairs:matched+=1
            else:incompatible.append(dict(a=x,b=y,alternatives=[list(p) for p in pairs if p[0]==x['pair_index'] or p[1]==y['pair_index']]))
        conflicts.append(dict(gap=gap,group_supports=[a['support'],b['support']],cross_matched=matched,
                              duplicate_person_pairs=duplicates,incompatible=incompatible))
    write_json(OUT/'rPc_group_conflicts.json',conflicts)

    code='yqstnuAEVhm-25'
    base=state(code,13.5);small=state(code,9)
    ref=('R00401',3)
    bg=next(g for g in base['identity_groups'] if ref in {key(m) for m in g['members']})
    sg=next(g for g in small['identity_groups'] if ref in {key(m) for m in g['members']})
    removed=[m for m in bg['members'] if key(m) not in {key(x) for x in sg['members']}]
    assert len(removed)==5
    source={r['id']:r for r in inputs[code]['records']}
    reference=next(m for m in bg['members'] if key(m)==ref)
    fig,axes=plt.subplots(1,6,figsize=(17,5.8))
    for i,(ax,m) in enumerate(zip(axes,[reference]+removed)):
        ax.imshow(photo(code),extent=(0,1024,512,0))
        draw_layout(ax,source[m['id']]['points'],'#dddddd',.5)
        p=np.array(m['points']);ax.plot(p[:,0],p[:,1],'-o',c='#00cfff' if i==0 else '#ff4040',lw=2)
        ax.set_xlim(660,850);ax.set_ylim(430,100);ax.axis('off')
        ax.set_title(('已确认参照' if i==0 else '待判断'+str(i))+f"\n{m['worker']} / {m['id']} 第{m['pair_index']+1}对",fontsize=9)
    fig.suptitle('yq-25：9°新拆出的另5份来源；只问是否同一遮挡墙角，不评精确位置')
    fig.tight_layout();fig.savefig(OUT/'yq25_split_sources.png',dpi=150);plt.close(fig)
    requests=[dict(image=code,source_image='yq25_split_sources.png',reference=reference,members=removed,
                   question='这5份是否也表达参照的被遮挡墙角？与上次新增5份不同。',status='pending')]

    code='rPc6DW4iMge-06';r=state(code,13.5)
    members={key(m):m for g in r['identity_groups'] for m in g['members']}
    refs=[members['R02452',2],members['R01986',2],members['R01557',4]]
    other=members['R01557',2]
    candidates=[members['R02468',2],members['R01662',0]]
    coords=np.array([m['points'] for m in refs+[other]+candidates]).reshape(-1,2)
    lo,hi=coords.min(axis=0),coords.max(axis=0)
    fig,axes=plt.subplots(1,3,figsize=(14,6))
    for i,ax in enumerate(axes):
        ax.imshow(photo(code),extent=(0,1024,512,0))
        for m in refs if i==0 else [refs[0]]:
            p=np.array(m['points']);ax.plot(p[:,0],p[:,1],'-o',c='#00cfff',lw=1.5,alpha=.8)
        p=np.array(other['points']);ax.plot(p[:,0],p[:,1],'-o',c='#ffac32',lw=1.5)
        if i:
            m=candidates[i-1];p=np.array(m['points']);ax.plot(p[:,0],p[:,1],'-o',c='#ff4040',lw=2)
        ax.set_xlim(max(0,lo[0]-45),min(1024,hi[0]+45));ax.set_ylim(min(512,hi[1]+35),max(0,lo[1]-35));ax.axis('off')
        ax.set_title('参照：青色A已确认同角\n橙色B已确认另一细节' if i==0 else f"待判断{i}：红色 {m['worker']} / {m['id']}\n原作答第{m['pair_index']+1}对",fontsize=10)
    fig.suptitle('rPc-06：两处冲突来源更像表达A、B，还是其它位置？不要求确认坐标')
    fig.tight_layout();fig.savefig(OUT/'rPc_conflict_sources.png',dpi=150);plt.close(fig)
    requests.append(dict(image=code,source_image='rPc_conflict_sources.png',references=refs,other=other,members=candidates,
                         question='两份红色分别表达A同角、B另一细节，还是其它位置？',status='pending'))
    if (OUT/'user_review.json').exists():
        responses={r['image']:r for r in read(OUT/'user_review.json')['decisions']}
        for request in requests:
            if request['image'] in responses:
                request.update(status='answered',response_source='user_review.json',
                    remaining_uncertainty=responses[request['image']].get('remaining_uncertainty'))
    write_json(OUT/'review_request.json',requests)


def local_failure_counts(relations):
    confirmed=[r for r in relations if r['review_status']=='confirmed_local']
    return dict(failed_confirmed_cases=sum(r['split_pairs']>0 or r['merged_pairs']>0 for r in confirmed),
                split_confirmed_cases=sum(r['split_pairs']>0 for r in confirmed),
                merged_confirmed_cases=sum(r['merged_pairs']>0 for r in confirmed))


def fine_run():
    """Coarse 0.5 gap scan, then 0.1 only around observed partition changes."""
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    target=OUT/'fine';target.mkdir(exist_ok=True)
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    images={im['code']:im for im in data['images']}
    objects={aliases['records'][o['object_id']]:o for o in bundle['data']['objects']}
    cases=review_cases();inputs={};states={};rows=[];relations=[]
    coarse=[9+i*.5 for i in range(10)]+[18.]
    requested=[round(9.5+i*.1,1) for i in range(36)]
    write_json(target/'PLAN.json',dict(development=DEVELOPMENT,coarse=coarse,refine_step=.1,lower_expansion_block=3.,lower_bound=0.,explicit_requested_grid=requested,
        refinement='Union of adjacent 0.5 intervals showing partition changes; no claim of continuous constancy between samples.',
        selection='Compare counts of failed confirmed local cases, split and merge separately; not whole-wall accuracy. Provisional/A-interpretation separate.',
        objective='Most wall lines automatic, a small number human-assisted; no zero-error veto from a hard case.',
        fixed='Full-N MV50, same inputs and median; default13.5 unchanged; no GT selection'))

    def records_for(code):
        records=sorted([dict(r) for r in images[code]['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        for r in records:
            o=objects[r['id']];r.update(object_id=o['object_id'],source_pair_indices=o['ordered_source_pair_indices'])
        old=read(DIRECT/(code+'.json'))
        assert {r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in records}=={
            r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in old['records']},code
        inputs[code]=dict(image=code,image_id=old['image_id'],records=records)
        return records

    def compute(code,gap):
        if (code,gap) in states:return states[code,gap]
        records=inputs[code]['records'] if code in inputs else records_for(code)
        previous=target/f'{code}_gap_{gap:g}.json'
        if not previous.exists():previous=OUT/f'{code}_gap_{gap:g}.json'
        r=read(previous) if previous.exists() else build(records,gap=gap)
        states[code,gap]=r
        write_json(target/f'{code}_gap_{gap:g}.json',r)
        local=[dict(gap=gap,**evaluate(r,c)) for c in cases if c['image']==code]
        relations.extend(local)
        rows.append(dict(image=code,gap=gap,n=len(records),identities=len(r['identity_groups']),
            nodes=len(r['node_consensus']['nodes']),
            **local_failure_counts(local),
            geometry_status=r['candidate'].get('geometry_status','not_evaluable')))
        return r

    intervals=set()
    for code in DEVELOPMENT:
        for gap in coarse:compute(code,gap)
        for a,b in zip(coarse[:9],coarse[1:10]):
            if partition(states[code,a])!=partition(states[code,b]):intervals.add((a,b))
        print('coarse',code,flush=True)
    refined=sorted(({round(a+i*.1,1) for a,b in intervals for i in range(1,5)}|set(requested))-set(coarse))
    for code in DEVELOPMENT:
        for gap in refined:compute(code,gap)
        print('refined',code,len(refined),flush=True)
    gaps=sorted(set(coarse+refined))
    # Extend in 3-degree blocks while the sampled lower edge remains tied best.
    # Zero is the non-negative skip-cost boundary, not a proposed usable setting.
    def score(gap):return sum(r['failed_confirmed_cases'] for r in rows if r['gap']==gap)
    expansions=[]
    while min(gaps)>0 and score(min(gaps))==min(map(score,gaps)):
        upper=min(gaps);lower=max(0.,upper-3.)
        block=[round(lower+i*.5,1) for i in range(round((upper-lower)/.5)+1)]
        changed=set()
        for code in DEVELOPMENT:
            for gap in block:compute(code,gap)
            for a,b in zip(block,block[1:]):
                if partition(states[code,a])!=partition(states[code,b]):changed.add((a,b))
        extra=sorted({round(a+i*.1,1) for a,b in changed for i in range(1,5)})
        for code in DEVELOPMENT:
            for gap in extra:compute(code,gap)
            print('extension',lower,upper,code,flush=True)
        intervals.update(changed);gaps=sorted(set(gaps+block+extra))
        expansions.append(dict(lower=lower,upper=upper,changed_intervals=sorted(changed),
            edge_failed_cases=score(lower),best_failed_cases=min(map(score,gaps))))
    write_json(target/'inputs.json',dict(images=list(inputs.values())))
    write_json(target/'refinement.json',dict(intervals=sorted(intervals),gaps=gaps,expansions=expansions,explicit_requested_grid=requested,
        stopping_reason='nonnegative_boundary' if min(gaps)==0 else 'lower_edge_worse_than_sampled_best'))
    write_csv(target/'summary.csv',rows);write_json(target/'relations.json',relations)
    totals=[dict(gap=g,failed_cases=score(g),
        split_cases=sum(r['split_confirmed_cases'] for r in rows if r['gap']==g),
        merged_cases=sum(r['merged_confirmed_cases'] for r in rows if r['gap']==g)) for g in gaps]
    write_csv(target/'scores.csv',totals)
    print('SCORES',totals,flush=True)


def verify_fine_scan():
    """Check the actual adaptive scan: coverage, refinement, scores and stopping."""
    target=OUT/'fine';plan=read(target/'refinement.json')
    gaps=plan['gaps'];assert set(plan['explicit_requested_grid'])<=set(gaps)
    rows=read_csv(target/'summary.csv');relations=read(target/'relations.json')
    scores={float(r['gap']):int(r['failed_cases']) for r in read_csv(target/'scores.csv')}
    assert {(r['image'],float(r['gap'])) for r in rows}==set(itertools.product(DEVELOPMENT,gaps))
    assert len(rows)==len(DEVELOPMENT)*len(gaps)
    for a,b in plan['intervals']:
        assert all(round(a+i*.1,1) in gaps for i in range(1,5))
    for gap in gaps:
        assert scores[gap]==local_failure_counts([r for r in relations if r['gap']==gap])['failed_confirmed_cases']
    assert min(gaps)==0 or scores[min(gaps)]>min(scores.values())
    return dict(states=len(rows),parameters=len(gaps),checks='coverage, refinement, local scores, stopping passed')


def fine_check(gaps):
    """Six other-building images, fixed from input counts before choosing gaps; no fitting here."""
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    from .direct_fusion_20261007 import adjacent_cohort_signals, draw_layout
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    target=OUT/'fine/check';target.mkdir(parents=True,exist_ok=True)
    panel=[('7y3sRwLe3Va-04','24人，全部4对'),('S9hNv5qa7GM-06','10人，全部4对'),
           ('VFuaQ6m2Qom-07','18人，4至12对'),('wc2JMjhGNzB-26','6人，5至10对'),
           ('X7HyMhZNoso-13','24人，全部4对'),('pa4otMbVnkk-14','5人，4至9对')]
    write_json(target/'PLAN.json',dict(panel=panel,gaps=gaps,
        selection='Fixed from input N and pair counts before inspecting fine scores; six buildings outside development, absent from prior20 gap panel.',
        status='Not used for choosing gaps; previously existing research images, not new independent sampling or blind validation.',
        review='No full identity gold. Signals and stability do not establish90% accuracy.'))
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    images={im['code']:im for im in data['images']}
    objects={aliases['records'][o['object_id']]:o for o in bundle['data']['objects']}
    rows=[];signals=[]
    for code,note in panel:
        records=sorted([dict(r) for r in images[code]['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        for r in records:
            o=objects[r['id']];r.update(object_id=o['object_id'],source_pair_indices=o['ordered_source_pair_indices'])
        old=read(DIRECT/(code+'.json'))
        assert {r['id']:r['points'] for r in records}=={r['id']:r['points'] for r in old['records']}
        write_json(target/(code+'_input.json'),dict(image=code,records=records,image_id=old['image_id']))
        photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+old['image_id']+'.png')))
        fig,axes=plt.subplots(1,len(gaps),figsize=(6*len(gaps),4.5),squeeze=False)
        for ax,gap in zip(axes[0],gaps):
            r=old['correspondence'] if gap==13.5 else build(records,gap=gap)
            write_json(target/f'{code}_gap_{gap:g}.json',r)
            signal=adjacent_cohort_signals(r['identity_groups'],r['assignments'])
            signals.extend(dict(image=code,gap=gap,**s) for s in signal)
            rows.append(dict(image=code,gap=gap,n=len(records),nodes=len(r['node_consensus']['nodes']),
                partitions_equal_baseline=partition(r)==partition(old['correspondence']),
                ordered_points_equal_baseline=r['candidate']['points']==old['correspondence']['candidate']['points'],
                review_signals=len(signal),geometry_status=r['candidate'].get('geometry_status','not_evaluable')))
            ax.imshow(photo,extent=(0,1024,512,0))
            for record in records:draw_layout(ax,record['points'],'gray',.12)
            if r['candidate']['points']:draw_layout(ax,r['candidate']['points'],'#ff3030',.9)
            for g in r['identity_groups']:
                if g['selected'] and g['center']:
                    ax.text(g['center'][0][0],g['center'][0][1]-5,str(g['support'])+'/'+str(len(records)),
                            color='#ffdf00',fontsize=8,bbox=dict(facecolor='black',alpha=.4,pad=.5))
            ax.set_title(f"代价{gap:g}；{len(r['node_consensus']['nodes'])}节点；{len(signal)}条提示（非错误数）")
            ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        fig.suptitle(code+'；'+note+'；灰色为来源，红色为融合，无GT')
        fig.tight_layout();fig.savefig(target/(code+'_comparison.png'),dpi=130);plt.close(fig)
        print('check',code,flush=True)
    write_csv(target/'summary.csv',rows);write_json(target/'signals.json',signals)


def fine_figures():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from PIL import Image
    target=OUT/'fine'
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    relations=read(target/'relations.json');gaps=read(target/'refinement.json')['gaps']
    cases=list(dict.fromkeys(r['case'] for r in relations if r['review_status']=='confirmed_local'))
    values={(r['case'],r['gap']):int(r['split_pairs']>0)+2*int(r['merged_pairs']>0) for r in relations}
    fig,ax=plt.subplots(figsize=(max(15,len(gaps)*.22),5.5))
    ax.imshow([[values[c,g] for g in gaps] for c in cases],aspect='auto',interpolation='nearest',vmin=0,vmax=3,
              cmap=ListedColormap(['#e2efd9','#f4bc65','#df7777','#9776b5']))
    ax.set_yticks(range(len(cases)),cases,fontsize=8)
    ax.set_xticks(range(len(gaps)),[f'{g:g}' for g in gaps],rotation=90,fontsize=8)
    ax.set_xlabel('实际采样的跳过代价；列等宽，不表示间隔相同')
    ax.set_title('已确认局部：绿=所审关系无违例；橙=同角拆散；红=异角误合\n不是全图／墙线准确率；允许残留局部由人工处理')
    fig.tight_layout();fig.savefig(target/'local_cases.png',dpi=145);plt.close(fig)
    code='pa4otMbVnkk-14';p=target/'check'
    original=read(p/(code+'_input.json'));small=read(p/(code+'_gap_9.json'));base=read(p/(code+'_gap_13.5.json'))
    photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+original['image_id']+'.png')))
    fig,axes=plt.subplots(1,4,figsize=(15,6));request=[]
    for j,fid in enumerate(['node_002','node_003']):
        g=next(g for g in base['identity_groups'] if g['feature_id']==fid)
        oldkeys={key(m) for m in g['members']}
        h=max(small['identity_groups'],key=lambda g:len(oldkeys&{key(m) for m in g['members']}))
        keep=[m for m in h['members'] if key(m) in oldkeys]
        removed=[m for m in g['members'] if key(m) not in {key(x) for x in keep}]
        coords=np.array([m['points'] for m in g['members']]).reshape(-1,2)
        for k,(ax,members) in enumerate(zip(axes[2*j:2*j+2],[keep,removed])):
            ax.imshow(photo,extent=(0,1024,512,0))
            for m in members:
                q=np.array(m['points']);ax.plot(q[:,0],q[:,1],'-o',c='#008be0' if k==0 else '#ff4040',lw=1.6)
            ax.set_xlim(max(0,coords[:,0].min()-55),min(1024,coords[:,0].max()+55));ax.set_ylim(500,10);ax.axis('off')
            ax.set_title(f"位置{j+1}："+('其余4人的蓝线' if k==0 else 'R02041的红线'))
        request.append(dict(feature_id=fid,retained=keep,separated=removed))
    fig.suptitle('pa4-14：两处红线是否分别与相邻蓝线表达同一墙角？\n只问目标归属；9°将红线各自分成单人组，13.5°则各5人合组')
    fig.tight_layout();fig.savefig(p/'pa4_sources.png',dpi=145);plt.close(fig)
    write_json(p/'review_request.json',dict(image=code,groups=request,question='两处红线分别同角还是不同转折目标？',
        status='answered' if (p/'user_review.json').exists() else 'pending'))


def fine_review():
    from .direct_fusion_20261007 import human_split
    p=OUT/'fine/check';review=read(p/'user_review.json');request=read(p/'review_request.json');code=review['image']
    assert review['decision']=='different_stops_at_both_locations_after_joint_scope_interpretation'
    current=read(p/(code+'_gap_13.5.json'))
    for group in request['groups']:
        fid=group['feature_id']
        rule=dict(feature_id=fid,review_source=str((p/'user_review.json').relative_to(ROOT)),groups=[
            dict(identity=fid+'_four',members=group['retained']),dict(identity=fid+'_cabinet',members=group['separated'])])
        current=human_split(dict(image=code,correspondence=current),rule)
    write_json(p/(code+'_assisted_from_review.json'),current)
    def selected(result):
        return {frozenset(key(m) for m in g['members']):g['center'] for g in result['identity_groups'] if g['selected']}
    equality=selected(current)==selected(read(p/(code+'_gap_9.json')))
    assert equality
    write_json(p/'review_effect.json',dict(image=code,gap=9,selected_members_and_centers_equal_review=equality,
        minority_source='R02041 two1/5 identities preserved below3-vote threshold; not removed as low quality',
        scope='two new local decisions; no whole-image accuracy claim or parameter refit'))
    request.update(status='answered',response_source='user_review.json');write_json(p/'review_request.json',request)


if __name__ == '__main__':
    run()
    diagnostics()
