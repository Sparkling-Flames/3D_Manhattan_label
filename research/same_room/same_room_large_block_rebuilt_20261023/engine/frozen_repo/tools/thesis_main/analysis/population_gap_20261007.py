"""全量Manual池参数迁移：自动结果、局部人审和人工修正严格分开。"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

from .correspondence_gap_20261007 import (OUT as GAP_OUT, DIRECT, DEVELOPMENT, read, key,
    review_cases, evaluate, local_failure_counts)
from .research_artifact_io import ROOT, write_json, write_csv
from .ring_correspondence_20261007 import build
from .direct_fusion_20261007 import adjacent_cohort_signals

OUT=GAP_OUT/'population'
GAPS=[5.7,7.5,9.,9.5,10.,10.5,11.,11.5,12.,12.5,13.,13.5,18.]


def compare_states(reference, result):
    def signatures(r):
        groups={frozenset(key(m) for m in g['members']):g for g in r['identity_groups']}
        lookup={m:s for s in groups for m in s}
        selected={s:g['center'] for s,g in groups.items() if g['selected']}
        return lookup,selected
    before,a=signatures(reference);after,b=signatures(result)
    assert set(before)==set(after)
    return dict(changed_observations=sum(before[m]!=after[m] for m in before),
        selected_memberships_equal=set(a)==set(b),selected_centers_equal=a==b)


def image_scan(item):
    code,records,image_id=item
    old=read(DIRECT/(code+'.json'))
    if old.get('pool_error'):
        # Recheck the known failing pool once; the voter is never silently dropped.
        try:build(records,gap=9.)
        except ValueError as e:return [],[],[],dict(image=code,n=len(records),error=str(e))
        raise AssertionError('previous input failure unexpectedly disappeared: '+code)
    states={};origins={};cases=[c for c in review_cases() if c['image']==code]
    for gap in GAPS:
        filename=f'{code}_gap_{gap:g}.json';dest=OUT/filename
        sources=[dest,GAP_OUT/'fine'/filename,GAP_OUT/'fine/check'/filename,GAP_OUT/filename]
        source=next((p for p in sources if p.exists()),None)
        if source:r=read(source);origin='reused'
        elif gap==13.5:r=old['correspondence'];origin='reused'
        else:r=build(records,gap=gap);origin='new'
        states[gap]=r;origins[gap]=origin;write_json(dest,r)
    rows=[];relations=[];signals=[]
    for gap,r in states.items():
        local=[dict(gap=gap,**evaluate(r,c)) for c in cases];relations.extend(local)
        sig=adjacent_cohort_signals(r['identity_groups'],r['assignments'])
        signals.extend(dict(image=code,gap=gap,**s) for s in sig)
        a=compare_states(states[9.],r);b=compare_states(states[13.5],r)
        rows.append(dict(image=code,gap=gap,n=len(records),origin=origins[gap],
            development=code in DEVELOPMENT,identities=len(r['identity_groups']),
            nodes=len(r['node_consensus']['nodes']),observations=sum(len(g['members']) for g in r['identity_groups']),
            changed_observations_vs9=a['changed_observations'],selected_equal_vs9=a['selected_centers_equal'],
            changed_observations_vs13_5=b['changed_observations'],selected_equal_vs13_5=b['selected_centers_equal'],
            connection_ready=bool(r['candidate']['points']),geometry_status=r['candidate'].get('geometry_status','not_evaluable'),
            review_signals=len(sig),**local_failure_counts(local)))
    return rows,relations,signals,None


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    OUT.mkdir(exist_ok=True)
    bundle=load_current_bundle();data,aliases=project_bundle(bundle)
    objects={aliases['records'][o['object_id']]:o for o in bundle['data']['objects']}
    pools=[];inventory=[]
    for im in data['images']:
        records=sorted([dict(r) for r in im['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']=='main_candidate'],key=lambda r:r['id'])
        inventory.append(dict(image=im['code'],n=len(records),included=len(records)>=2))
        if len(records)<2:continue
        for r in records:
            o=objects[r['id']];r.update(object_id=o['object_id'],source_pair_indices=o['ordered_source_pair_indices'])
        old=read(DIRECT/(im['code']+'.json'))
        identity=lambda rs:{r['id']:(r['worker'],r['points'],r['source_pair_indices']) for r in rs}
        assert identity(records)==identity(old['records']),im['code']
        pools.append((im['code'],records,old['image_id']))
    write_json(OUT/'inputs.json',dict(images=[dict(image=c,records=r,image_id=i) for c,r,i in pools]))
    write_csv(OUT/'inventory.csv',inventory)
    write_json(OUT/'PLAN.json',dict(gaps=GAPS,images=len(pools),records=sum(len(r) for _,r,_ in pools),
        selection='All current independent eligible Manual main_candidate pools N>=2; Semi not mixed.',
        fixed='Same full pools, MV50, medians and source order; no GT selection, no assisted corrections applied.',
        validation='Parameter transfer and review triage; unchanged or valid geometry is not identity accuracy.',
        refinement='Full panel uses range representatives; refine only new consequential changes after this scan.'))
    write_json(OUT/'field_contract.json',dict(unit='one image and gap; not independent samples',
        changed_observations='Observations whose full identity membership set differs from the stated baseline; node labels ignored.',
        selected_equal='Same retained membership sets AND centers; does not assess ring order or semantic correctness.',
        review_signals='Adjacent-cohort diagnostic, not errors. No signal does not mean correct.',
        failures='Input failure reported once per pool, excluded from all setting totals without deleting any voter.',
        local_cases='Only existing explicit reviews; provisional and uncertain identities not hard accuracy labels.',
        schemas='summary.csv contains counts, equality flags, order/geometry statuses; totals.csv aggregates by gap.'))
    rows=[];relations=[];signals=[];failures=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(image_scan,item):item[0] for item in pools}
        for i,f in enumerate(as_completed(futures),1):
            r,l,s,error=f.result();rows.extend(r);relations.extend(l);signals.extend(s)
            if error:failures.append(error)
            print(i,'/',len(pools),futures[f],flush=True)
    rows.sort(key=lambda r:(r['image'],r['gap']))
    assert len(rows)==(len(pools)-len(failures))*len(GAPS)
    totals=[]
    for g in GAPS:
        rs=[r for r in rows if r['gap']==g]
        totals.append(dict(gap=g,images=len(rs),nodes=sum(r['nodes'] for r in rs),
            partition_changed_vs9=sum(r['changed_observations_vs9']>0 for r in rs),
            selected_changed_vs9=sum(not r['selected_equal_vs9'] for r in rs),
            selected_changed_vs13_5=sum(not r['selected_equal_vs13_5'] for r in rs),
            changed_nondevelopment_vs9=sum(not r['selected_equal_vs9'] and not r['development'] for r in rs),
            connection_ready=sum(r['connection_ready'] for r in rs),
            geometry_ok=sum(r['geometry_status']=='ok' for r in rs),
            images_with_signals=sum(r['review_signals']>0 for r in rs),
            failed_confirmed_cases=sum(r['failed_confirmed_cases'] for r in rs)))
    write_csv(OUT/'summary.csv',rows);write_csv(OUT/'totals.csv',totals)
    write_json(OUT/'relations.json',relations);write_json(OUT/'signals.json',signals);write_json(OUT/'failures.json',failures)
    print('DONE',Counter(r['origin'] for r in rows),totals,flush=True)


def inspection():
    from .research_artifact_io import read_csv
    from .direct_fusion_20261007 import draw_layout
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    inputs={r['image']:r for r in read(OUT/'inputs.json')['images']}
    rows=read_csv(OUT/'summary.csv');queue=[]
    for code in sorted({r['image'] for r in rows}):
        rs=[r for r in rows if r['image']==code]
        changes=[float(r['gap']) for r in rs if r['selected_equal_vs9']=='False']
        queue.append(dict(image=code,n=int(rs[0]['n']),development=code in DEVELOPMENT,
            changed_gaps=changes,min_nodes=min(int(r['nodes']) for r in rs),max_nodes=max(int(r['nodes']) for r in rs),
            max_changed_observations=max(int(r['changed_observations_vs9']) for r in rs),
            signals_at9=int(next(r for r in rs if float(r['gap'])==9)['review_signals']),
            identity_status='not_fully_reviewed'))
    write_json(OUT/'review_queue.json',queue)
    changed=sorted([r for r in queue if r['changed_gaps'] and not r['development']],key=lambda r:-r['max_changed_observations'])
    panel=[];buildings=Counter()
    for r in changed:
        building=r['image'].split('-')[0]
        if buildings[building]>=2:continue
        panel.append(r['image']);buildings[building]+=1
        if len(panel)==12:break
    controls=[]
    for r in queue:
        if r['changed_gaps'] or r['development']:continue
        building=r['image'].split('-')[0]
        if building in controls:continue
        panel.append(r['image']);controls.append(building)
        if len(controls)==4:break
    write_json(OUT/'visual_panel.json',dict(images=panel,controls=controls,
        selection='Up to12 consequential nondevelopment images, max2 per building;4 unchanged controls from different buildings. Not random accuracy sample.'))
    for code in panel:
        im=inputs[code];photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+im['image_id']+'.png')))
        fig,axes=plt.subplots(1,3,figsize=(18,4.8))
        for ax,gap in zip(axes,[5.7,9,13.5]):
            state=read(OUT/f'{code}_gap_{gap:g}.json');ax.imshow(photo,extent=(0,1024,512,0))
            for r in im['records']:draw_layout(ax,r['points'],'#009dff',.65)
            if state['candidate']['points']:draw_layout(ax,state['candidate']['points'],'red',.9)
            for g in state['identity_groups']:
                if g['selected']:
                    pair=g['center'];ax.plot([p[0] for p in pair],[p[1] for p in pair],'-o',color='red',lw=1.4,ms=3)
                    ax.text(pair[0][0],pair[0][1]-6,str(g['support'])+'/'+str(state['n']),color='#ffdf00',fontsize=8,bbox=dict(facecolor='black',alpha=.5,pad=.5))
            ax.set_title(f"gap={gap:g}; {len(state['node_consensus']['nodes'])}节点");ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        fig.suptitle(code+'：青蓝=人员原答；红=自动共识；无连线时仍显示节点；不使用GT')
        fig.tight_layout();fig.savefig(OUT/(code+'_comparison.png'),dpi=130);plt.close(fig)
    (OUT/'visual_panel.md').write_text('# 全量参数对照图\n\n'+''.join(f'## {c}\n\n![{c}]({c}_comparison.png)\n\n' for c in panel),encoding='utf-8')
    print('inspection',len(queue),len(changed),panel,flush=True)


def upper_edge_review():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    import numpy as np
    from .direct_fusion_20261007 import draw_layout
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    inputs={r['image']:r for r in read(OUT/'inputs.json')['images']};requests=[]
    for code in ['7y3sRwLe3Va-23','q9vSo1VnCiC-03']:
        a=read(OUT/f'{code}_gap_9.json');b=read(OUT/f'{code}_gap_9.5.json');changes=[]
        for g in b['identity_groups']:
            keys={key(m) for m in g['members']}
            parts=[h for h in a['identity_groups'] if keys&{key(m) for m in h['members']}]
            if len(parts)>1 and g['selected']:changes.append((g,sorted(parts,key=lambda h:-h['support'])))
        im=inputs[code];photo=Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+im['image_id']+'.png')))
        fig,axes=plt.subplots(len(changes),2,figsize=(12,5*len(changes)),squeeze=False)
        for row,(g,parts) in enumerate(changes):
            assert len(parts)==2
            coords=np.array([m['points'] for m in g['members']]).reshape(-1,2)
            xmin,xmax=coords[:,0].min()-70,coords[:,0].max()+70
            ymin,ymax=coords[:,1].min()-55,coords[:,1].max()+55
            for ax,part,color in zip(axes[row],parts,['#008bff','#ff3535']):
                ax.imshow(photo,extent=(0,1024,512,0))
                for m in part['members']:
                    r=next(r for r in im['records'] if r['id']==m['id']);draw_layout(ax,r['points'],color,.25)
                    xy=np.array(m['points']);ax.plot(xy[:,0],xy[:,1],'-o',c=color,lw=2)
                ax.set_xlim(max(0,xmin),min(1024,xmax));ax.set_ylim(min(512,ymax),max(0,ymin));ax.axis('off')
                ax.set_title(f"位置{row+1}：{part['support']}人；"+' / '.join(m['worker'] for m in part['members']),fontsize=10)
        fig.suptitle(code+'：9分开、9.5合并；左右是否同一目标？只判身份，不评精确坐标')
        fig.tight_layout();fig.savefig(OUT/(code+'_review.png'),dpi=145);plt.close(fig)
        requests.append(dict(image=code,status='pending',comparison=[9,9.5],
            changes=[dict(wide_group=g['feature_id'],cohorts=[p['members'] for p in ps]) for g,ps in changes],
            question='左右是否表达同一墙角，还是不同停止/转折目标？7y两处请结合范围判断。'))
    write_json(OUT/'review_request.json',requests)


def apply_population_review():
    from .direct_fusion_20261007 import human_split
    requests=read(OUT/'review_request.json');cases=[];decisions=[];effects=[];comparisons=[]
    for req in requests:
        code=req['image'];quote='不同的停止位置' if code.startswith('7y') else '也是不同的转折位置'
        decisions.append(dict(image=code,quote=quote,scope='Different targets at each displayed location; no coordinate or whole-image certification.',changes=req['changes']))
        req.update(status='answered',answer=quote,response_source='user_review.json')
        for index,change in enumerate(req['changes'],1):
            cases.append(dict(case=code+'_population_local_'+str(index),image=code,status='confirmed_local',
                groups=[[list(key(m)) for m in cohort] for cohort in change['cohorts']]))
        for gap in GAPS:
            r=read(OUT/f'{code}_gap_{gap:g}.json')
            effects.extend(dict(gap=gap,**evaluate(r,c)) for c in cases if c['image']==code)
        assisted=read(OUT/f'{code}_gap_9.5.json')
        for change in req['changes']:
            assisted=human_split(dict(image=code,correspondence=assisted),dict(feature_id=change['wide_group'],review_source='population/user_review.json',
                groups=[dict(identity='reviewed_target_'+str(j),members=cohort) for j,cohort in enumerate(change['cohorts'])]))
        write_json(OUT/(code+'_assisted_from9_5.json'),assisted)
        comparisons.append(dict(image=code,**compare_states(assisted,read(OUT/f'{code}_gap_9.json'))))
    write_json(OUT/'review_request.json',requests)
    write_json(OUT/'user_review.json',dict(source='User reply in current thread',decisions=decisions))
    write_json(OUT/'review_cases.json',cases);write_json(OUT/'new_review_relations.json',effects)
    write_json(OUT/'assisted_comparison.json',comparisons)
    rows=[dict(gap=g,**local_failure_counts([e for e in effects if e['gap']==g])) for g in GAPS]
    write_csv(OUT/'new_review_scores.csv',rows);print(comparisons,rows)
    inputs={x['image']:x for x in read(OUT/'inputs.json')['images']};boundary=[]
    for code in {c['image'] for c in cases}:
        for gap in [9,9.1,9.2,9.3,9.4,9.5]:
            path=OUT/f'{code}_gap_{gap:g}.json'
            r=read(path) if path.exists() else build(inputs[code]['records'],gap=gap)
            write_json(path,r)
            boundary.extend(dict(gap=gap,**evaluate(r,c)) for c in cases if c['image']==code)
    write_json(OUT/'new_review_boundary.json',boundary)



def build_review():
    import json
    import os
    inputs={x['image']:x for x in read(OUT/'inputs.json')['images']}
    queue=read(OUT/'review_queue.json');images=[]
    preferred=[7.5,9.]+[g for g in GAPS if g not in [7.5,9.]]
    for item in queue:
        code=item['image'];source=inputs[code];observations=[];lookup={}
        for r in source['records']:
            for k in range(len(r['points'])//2):
                lookup[r['id'],k]=len(observations)
                observations.append(dict(id=r['id'],worker=r['worker'],pair_index=k,
                    source_pair_index=r['source_pair_indices'][k],points=r['points'][2*k:2*k+2]))
        states={};identities={}
        for gap in preferred:
            result=read(OUT/f'{code}_gap_{gap:g}.json');groups=[]
            for g in result['identity_groups']:
                members=sorted(lookup[key(m)] for m in g['members']);signature=tuple(members)
                if signature not in identities:identities[signature]=len(identities)+1
                groups.append(dict(label='G'+str(identities[signature]).zfill(2),members=members,
                    support=g['support'],selected=g['selected'],center=g['center'],feature_id=g['feature_id']))
            assert sorted(i for g in groups for i in g['members'])==list(range(len(observations)))
            states[f'{gap:g}']=groups
        photo=next(ROOT.glob('data/mp3d_layout/*/img/'+source['image_id']+'.png'))
        priority=not compare_states(read(OUT/f'{code}_gap_7.5.json'),read(OUT/f'{code}_gap_9.json'))['selected_centers_equal']
        images.append(dict(code=code,n=len(source['records']),image_id=source['image_id'],
            src=os.path.relpath(photo,OUT).replace(os.sep,'/'),priority=priority,
            observations=observations,states=states))
    assert sum(x['priority'] for x in images)==17
    data=dict(schema='wall_identity_review_20261007_v1',gaps=GAPS,images=images)
    template=(ROOT/'tools/thesis_main/analysis/wall_identity_review_20261007.html').read_text(encoding='utf-8')
    page=template.replace('/*__DATA__*/',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    (OUT/'review.html').write_text(page,encoding='utf-8')
    print(OUT/'review.html',len(images),len(page))


if __name__=='__main__':run()
