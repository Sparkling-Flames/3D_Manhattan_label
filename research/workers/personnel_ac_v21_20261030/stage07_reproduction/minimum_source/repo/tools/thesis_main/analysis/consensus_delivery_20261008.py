"""基于已审局部选择工作参数，交付全员自动与人工辅助融合；GT不参与。"""
import copy
from collections import Counter
from .correspondence_gap_20261007 import read, key, review_cases
from .population_gap_20261007 import OUT as POP, compare_states
from .refine_review_20261008 import OUT as REF, FINE, scan_image
from .research_artifact_io import ROOT, write_json, write_csv
from .fixed_identity_location_20261007 import median_pair
from .ring_correspondence_20261007 import assemble_fusion, build

OUT=ROOT/'analysis_results/consensus_delivery_20261008'
WORKING_GAP=7.5


def apply_sorting_policy(result):
    """用户规则：两人池保留节点与来源诊断，暂不形成融合排序。"""
    result=copy.deepcopy(result)
    if result['n']==2:
        result['candidate']=dict(status='deferred',reason='two_person_sorting_deferred',
            points=None,footprint=None,feature_ids=[],ring_confirmed=False,
            order_status='two_person_sorting_deferred',geometry_status='not_evaluable')
    return result


def fuse(records, gap=WORKING_GAP, partitions=(), manual_order=None):
    """单图入口：预处理原答→自动融合→可选明确人审分区及顺序；两版本分存。"""
    automatic=build(records,gap=gap);current=copy.deepcopy(automatic)
    for case in partitions:current=apply_partition(current,case)
    if manual_order is not None:
        current.update(assemble_fusion(current['identity_groups'],current['assignments'],manual_order))
    if manual_order is not None and current['n']==2:raise ValueError('two_person_sorting_deferred')
    return dict(gap=gap,automatic=apply_sorting_policy(automatic),assisted=apply_sorting_policy(current) if partitions or manual_order is not None else None)


def relation_error(result,case):
    lookup={key(m):g['feature_id'] for g in result['identity_groups'] for m in g['members']}
    sets=[{lookup[tuple(m)] for m in group} for group in case['groups']]
    if case['kind']=='mixed':return False,len(set.union(*sets))==1
    return any(len(s)>1 for s in sets),any(a&b for i,a in enumerate(sets) for b in sets[i+1:])


def apply_followup(result, feedback):
    """选参后的明确反馈单独应用；不用于追调参数或扩大旧验证分母。"""
    current=copy.deepcopy(result);applied=[]
    for case in feedback.get('partitions',[]):
        current=apply_partition(current,case);applied.append(case['case'])
    if feedback.get('order_policy')=='x_ascending':
        order=[g['feature_id'] for g in sorted((g for g in current['identity_groups'] if g['selected']),key=lambda g:g['center'][0][0])]
        current.update(assemble_fusion(current['identity_groups'],current['assignments'],order))
        current['candidate']['order_status']='user_requested_x_sort'
        applied.append('user_order_x_ascending')
    if 'manual_order' in feedback:
        binding=[dict(feature_id=n['feature_id'],points=n['points']) for n in current['node_consensus']['nodes']]
        if feedback['order_binding']!=binding:
            current['candidate'].update(review_status='needs_order_reconfirmation',review_note='节点已改变，旧排序确认未套用')
        elif current['n']!=2:
            current.update(assemble_fusion(current['identity_groups'],current['assignments'],feedback['manual_order']))
            current['candidate']['order_status']='human_reviewed_order'
            applied.append('user_workbench_order')
    if 'review_issue' in feedback:
        current['candidate'].update(review_status=feedback['review_issue']['status'],review_note=feedback['review_issue']['note'])
    return current,applied


def apply_partition(result,case):
    """只改完整覆盖的已审身份组；不推断未审成员归属，不允许同人两节点合票。"""
    r=copy.deepcopy(result);wanted=[set(map(tuple,g)) for g in case['groups']]
    flat=set.union(*wanted)
    if sum(map(len,wanted))!=len(flat):raise ValueError('overlapping_review')
    touched=[g for g in r['identity_groups'] if {key(m) for m in g['members']}&flat]
    lookup={key(m):m for g in touched for m in g['members']}
    if set(lookup)!=flat:raise ValueError('partial_group_requires_member_policy')
    new=[];mapping={}
    for i,keys in enumerate(wanted):
        ms=[lookup[k] for k in sorted(keys)]
        if len({m['worker'] for m in ms})!=len(ms):raise ValueError('same_person_multiple_nodes')
        fid='review_'+case['case']+'_'+str(i)
        new.append(dict(feature_id=fid,members=ms,support=len(ms),selected=2*len(ms)>=r['n'],center=median_pair(ms)))
        mapping.update({key(m):fid for m in ms})
    touched_ids={g['feature_id'] for g in touched}
    r['identity_groups']=[g for g in r['identity_groups'] if g['feature_id'] not in touched_ids]+new
    for row in r['assignments']:
        row['feature_ids']=[mapping.get((row['id'],i),f) for i,f in enumerate(row['feature_ids'])]
    r.update(assemble_fusion(r['identity_groups'],r['assignments']))
    return r


def cases():
    result=[dict(c,kind='partition') for c in review_cases()+read(POP/'review_cases.json') if c['status']=='confirmed_local']
    old=read(POP/'user_review_workbench_20261008.json')['decisions']
    new=read(REF/'user_review_20261008.json')['decisions']
    touched={r['image'] for r in new if r['issues'] or r['note'] or any(r['verdicts'].values())}
    deferred=[]
    for version,rows in [('first',old),('revisit',new)]:
        for row in rows:
            if version=='first' and row['image'] in touched:continue
            for i,issue in enumerate(row['issues']):
                cid=row['image']+'_'+version+'_'+str(i)
                ms=issue.get('selected_members',[m for g in issue['groups'] for m in g['members']])
                ms=list({key(m):m for m in ms}.values());keys=[list(key(m)) for m in ms]
                same=issue['type'] in ['都想标同一墙线','同角被拆散，应合并']
                mixed=issue['type'] in ['包含不同墙线','不同角误合，应拆开']
                reason=None
                if not same and not mixed:reason='uncertain_or_usability_only'
                elif row['image']=='uNb9QFRL6hY-86':reason='explicit_uncertainty_in_note'
                elif row['image']=='q9vSo1VnCiC-23' and len(ms)==2:reason='P027_explicitly_uncertain'
                elif same and len({m['worker'] for m in ms})!=len(ms):reason='same_person_multiple_nodes'
                elif row['image']=='zsNo4HB9uLZ-05' and {m['pair_index'] for m in ms}=={3}:reason='superseded_by_explicit_followup'
                if reason:deferred.append(dict(case=cid,image=row['image'],reason=reason,raw_issue=issue));continue
                result.append(dict(case=cid,image=row['image'],kind='partition' if same else 'mixed',groups=[keys],
                    source=version,note=issue['note']))
    follow=read(REF/'user_review_followup_20261008.json')
    result.append(dict(case='zs05_corrected_fourth',image=follow['image'],kind='partition',
        groups=[[list(key(m)) for m in g['members']] for g in follow['groups']],source='explicit_followup'))
    # The 18-source review supersedes the older ten-source subset; don't double count.
    result=[c for c in result if c['case']!='yq_ten_confirmed']
    unique={}
    for c in result:
        signature=(c['image'],c['kind'],tuple(sorted(tuple(sorted(map(tuple,g))) for g in c['groups'])))
        unique.setdefault(signature,c)
    return list(unique.values()),deferred


def get_state(im,gap):
    path=REF/f"{im['image']}_gap_{gap:g}.json"
    if not path.exists():scan_image((im,[gap]))
    return read(path)


def replay_calibration():
    """单独复现开发选参，不覆盖冻结选择或当前交付。"""
    destination=OUT/'history/calibration_replay';destination.mkdir(parents=True,exist_ok=True)
    failed={r['image'] for r in read(POP/'failures.json')}
    inputs={im['image']:im for im in read(POP/'inputs.json')['images'] if im['image'] not in failed}
    constraints,_=cases()
    effects=[];scores=[]
    for gap in FINE:
        states={code:get_state(inputs[code],gap) for code in {c['image'] for c in constraints}}
        local=[]
        for c in constraints:
            split,merged=relation_error(states[c['image']],c)
            row=dict(gap=gap,case=c['case'],image=c['image'],kind=c['kind'],split=split,merged=merged,failed=split or merged)
            local.append(row);effects.append(row)
        scores.append(dict(gap=gap,cases=len(local),failed=sum(r['failed'] for r in local),
            split=sum(r['split'] for r in local),merged=sum(r['merged'] for r in local)))
    best=min(r['failed'] for r in scores);tied=[r['gap'] for r in scores if r['failed']==best]
    # Equal local-case failures first; prefer fewer false merges among ties.
    fewer_merges=min(r['merged'] for r in scores if r['failed']==best)
    eligible=[r['gap'] for r in scores if r['failed']==best and r['merged']==fewer_merges]
    runs=[]
    for gap in eligible:
        if not runs or round(gap-runs[-1][-1],1)!=.1:runs.append([])
        runs[-1].append(gap)
    band=max(runs,key=lambda a:(len(a),-a[0]));chosen=band[(len(band)-1)//2]
    write_csv(destination/'parameter_scores.csv',scores);write_csv(destination/'local_effects.csv',effects)
    write_json(destination/'selection.json',dict(gap=chosen,best_sampled=tied,working_band=band,
        rule='Equal weight per explicit local case; minimize failed cases, then false-merge cases, then lower midpoint of longest contiguous tied run. A development choice, not preregistered.',
        interpretation='Development working parameter, not universal optimum or identity accuracy; mixed means not all same, no inferred partition.',
        no_gt=True))
    print('Calibration replay:',chosen,'; frozen delivery:',WORKING_GAP,flush=True)


def run():
    OUT.mkdir(exist_ok=True)
    failed={r['image'] for r in read(POP/'failures.json')}
    inputs={im['image']:im for im in read(POP/'inputs.json')['images'] if im['image'] not in failed}
    constraints,deferred=cases();write_json(OUT/'review_cases.json',constraints);write_json(OUT/'deferred_reviews.json',deferred)
    chosen=WORKING_GAP
    followups={r['image']:r for r in read(OUT/'user_followup.json')['records']}
    outputs=[];summary=[];interventions=[]
    for code,im in inputs.items():
        auto=apply_sorting_policy(get_state(im,chosen));current=copy.deepcopy(auto);applied=[]
        for c in sorted((c for c in constraints if c['image']==code and c['kind']=='partition'),key=lambda c:-sum(map(len,c['groups']))):
            if not any(relation_error(current,c)):continue
            try:current=apply_partition(current,c);applied.append(c['case'])
            except ValueError as e:interventions.append(dict(image=code,case=c['case'],status='pending',reason=str(e)))
        if applied and code=='uNb9QFRL6hY-36':
            order=[g['feature_id'] for g in sorted((g for g in current['identity_groups'] if g['selected']),key=lambda g:g['center'][0][0])]
            current.update(assemble_fusion(current['identity_groups'],current['assignments'],order))
            current['candidate']['order_status']='user_requested_x_sort'
        if code in followups:
            current,extra=apply_followup(current,followups[code]);applied.extend(extra)
        current=apply_sorting_policy(current)
        remains=[c['case'] for c in constraints if c['image']==code and any(relation_error(current,c))]
        for event in interventions:
            if event['image']==code and event['status']=='pending' and event['case'] not in remains:
                event['status']='resolved_by_followup'
        package=dict(image=code,image_id=im['image_id'],gap=chosen,n=auto['n'],automatic=auto,
            assisted=current if applied or code in followups and 'review_issue' in followups[code] else None,applied_reviews=applied,remaining_review_cases=remains)
        write_json(OUT/(code+'.json'),package)
        for name,r in [('automatic',auto),('assisted',current)]:
            summary.append(dict(image=code,version=name,n=r['n'],nodes=len(r['node_consensus']['nodes']),
                connection_ready=r['candidate']['points'] is not None,geometry_status=r['candidate'].get('geometry_status','not_evaluable'),
                interventions=len(applied) if name=='assisted' else 0,
                remaining_cases=sum(any(relation_error(r,c)) for c in constraints if c['image']==code)))
        outputs.append(dict(image=code,n=current['n'],gap=chosen,origin='human_assisted' if applied else 'automatic',
            node_consensus=current['node_consensus'],candidate=current['candidate'],remaining_review_cases=remains))
        interventions.extend(dict(image=code,case=c,status='applied') for c in applied)
    write_csv(OUT/'summary.csv',summary);write_json(OUT/'outputs.json',outputs)
    write_json(OUT/'interventions.json',interventions);write_json(OUT/'failures.json',read(POP/'failures.json'))
    write_json(OUT/'field_contract.json',dict(schema='consensus_delivery_v1',
        automatic='Chosen working gap, original full-person pool, MV50, all-member coordinate median; GT unused.',
        assisted='Exact reviewed partitions and explicit user order; all sources and full N preserved. Human reviewers may have consulted GT for target interpretation; assisted results are not claimed GT-blind. Post-selection feedback is separate from tuning cases.',
        cases='Deduplicated local relations, not independent samples; mixed is weak not-all-one constraint. Uncertain text and duplicate-person same-target opinions deferred.',
        outputs='177 actual all-person node outputs and candidate connection. Missing connection/failed geometry retained. One known whole-pool failure separate.',
        remaining='Known unresolved relation cases only, not exhaustive error count; no claim of >90% accuracy.',
        sorting_policy='N=2: node output and source diagnostics retained; candidate order/geometry deferred. N>=3 may enter order review. This does not change MV50 votes.',
        review_state='candidate.review_status/review_note are independent of geometry_status. incomplete_consensus_observed records an explained incomplete result, not an open identity-review request or a complete layout.',
        order_import='Confirmed source-bound permutations enter user_followup.manual_order with order_binding; later identity/coordinate change invalidates old order confirmation. Explicit identity_review_resolution may close an uploaded issue without confirming order or completing the layout.',
        followup='user_followup.json stores post-selection identity/order decisions; no changes to 36-case calibration. The interventions count includes identity and order operations; applied_reviews names them.',
        history_order_audit='order_followup/history_order_audit.csv/json joins actual adjacency changes and historical user orders to current candidates. History may be outside current pool; changed_objects_in_pool distinguishes this. Non-x order is a review signal, not error. No automatic ring certification.'))
    gallery(inputs)
    print('Frozen gap',chosen,'; outputs',len(outputs),'; interventions',len(interventions),flush=True)


def gallery(inputs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from .direct_fusion_20261007 import draw_layout
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    links=[]
    codes=[c for c in inputs if read(OUT/(c+'.json'))['applied_reviews']]
    for code in codes:
        p=read(OUT/(code+'.json'));photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+p['image_id']+'.png')))
        fig,axes=plt.subplots(1,3,figsize=(21,5))
        for ax in axes:ax.imshow(photo,extent=(0,1024,512,0));ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        for rec in inputs[code]['records']:draw_layout(axes[0],rec['points'],'#00bfff',.45)
        axes[0].set_title('全部人员原答')
        for ax,res,title in [(axes[1],p['automatic'],'自动融合'),(axes[2],p['assisted'],'明确人审辅助')]:
            if res['candidate']['points']:draw_layout(ax,res['candidate']['points'],'#e51c3e')
            else:
                for node in res['node_consensus']['nodes']:draw_layout(ax,node['points'],'#e51c3e',closed=False)
            for n in res['node_consensus']['nodes']:
                x,y=n['points'][0];ax.text(x,y-5,f"{n['support']}/{res['n']}",fontsize=8,color='red',bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
            ax.set_title(title+' · '+str(len(res['node_consensus']['nodes']))+'节点 · '+res['candidate']['order_status'])
        fig.suptitle(code+f" · gap={p['gap']} · 不含GT；连线为来源建议或已授权人工顺序")
        fig.tight_layout();fig.savefig(OUT/(code+'.png'),dpi=120);plt.close(fig)
        links.append(f'<h2>{code}</h2><a href="{code}.json">完整来源及自动／辅助结果</a><img src="{code}.png" style="width:100%">')
    (OUT/'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>融合共识交付</title><h1>全员融合：自动与人工辅助对照</h1><p>图中顺序为来源建议，少数为已授权人工顺序；不以GT挑融合。不确定处仍保留。</p>'+''.join(links),encoding='utf-8')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay-calibration',action='store_true',help='复现开发选参，输出到history/calibration_replay，不重交付')
    args=parser.parse_args()
    replay_calibration() if args.replay_calibration else run()
