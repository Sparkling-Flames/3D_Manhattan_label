"""全259研究图按现行独立人员池计算人数响应；Manual/Semi/OOS与门洞状态分开。"""
import json
import warnings
from collections import defaultdict
from statistics import mean, median

import numpy as np
from shapely.geometry import mapping

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
from .research_artifact_io import ROOT, INVENTORY, read_csv, write_csv, write_json
from .research_round_20260929 import prepare_record, reconstruct
from .lee_tile_precision_20261003 import integration_basis
from .worker_count_composition_20261006 import probabilities
from .worker_count_metrics_20261006 import area_summary

OUT=ROOT/'analysis_results/difficulty_full_20261007'
LABELS=('简单','中等','困难')


def scene_axis(meta):
    if meta['oos_status']=='confirmed': return 'oos'
    if meta['oos_status']=='pending': return 'oos_pending'
    if meta['doorway_status']=='annotatable': return 'doorway_annotatable'
    if meta['doorway_status']=='difficult': return 'doorway_difficult'
    if meta['doorway_status']=='pending': return 'doorway_pending'
    return 'ordinary'


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    bundle=load_current_bundle(); panel,mapping_ids=project_bundle(bundle)
    objects={mapping_ids['records'][r['object_id']]:r for r in bundle['data']['objects']}
    inventory={r['image']:r for r in json.loads(INVENTORY.read_text(encoding='utf-8'))['images']}
    labels={r['image']:r['difficulty'] for r in read_csv(ROOT/'analysis_results/difficulty_consensus_20261006/updated/difficulty_roster.csv')}
    images_meta={r['image_code']:r for r in bundle['research']['images']}
    curves=[]; coverage=[]; roster=[]; endpoints=[]; features=[]; issues=[]
    cache={}
    def prepared(r):
        if r['id'] not in cache:
            p=prepare_record(dict(r,source_pair_indices=objects[r['id']]['ordered_source_pair_indices']))
            with warnings.catch_warnings(record=True) as messages:
                warnings.simplefilter('always',RuntimeWarning); g=reconstruct(p)
            for w in messages:issues.append(dict(record=r['id'],stage='reconstruct',message=str(w.message)))
            state=g['representations']['declared_footprint']
            p.update(footprint=g['floor'].tolist() if state['status']=='ok' else None,footprint_state=state)
            cache[r['id']]=p
        return cache[r['id']]
    research=[im for im in panel['images'] if im['population']=='research_annotation_image']
    for ix,im in enumerate(research):
        code=im['code']; meta=images_meta[code]; scene=scene_axis(meta)
        difficulty=labels.get(code,inventory[code]['difficulty'])
        groups=defaultdict(list)
        for r in im['annotations']:
            if r['independent'] and r['consensus_eligible']:
                groups[r['condition'],r['main_consensus_gate']['status']].append(r)
        if not groups:
            coverage.append(dict(image=code,building=im['building'],condition='',gate='',scene=scene,difficulty=difficulty,n=0,pool='',status='no_eligible_pool',reason='existing_independence_or_consensus_gate',quality_compatible=False))
        for (condition,gate),raw in groups.items():
            raw=sorted(raw,key=lambda r:r['worker']); pool=f'{code}|{condition}|{gate}'
            row=dict(image=code,building=im['building'],condition=condition,gate=gate,scene=scene,difficulty=difficulty,n=len(raw),pool=pool,status='ready',reason='',quality_compatible=all(r['quality_candidate'] for r in raw))
            for r in raw:roster.append(dict(pool=pool,image=code,record=r['id'],worker=r['worker'],condition=condition,gate=gate))
            try:
                assert len({r['worker'] for r in raw})==len(raw),'duplicate_person_in_pool'
                records=[prepared(r) for r in raw]
                failed=[r['id'] for r in records if r['footprint'] is None]
                if failed:raise ValueError('unavailable_member_footprint:'+','.join(failed))
                refs={}
                for r in im['references']:
                    try:
                        p=prepared(r)
                        if p['footprint'] is None:raise ValueError(str(p['footprint_state']))
                        refs[r['version']]=p['footprint']
                    except (ValueError,KeyError,IndexError,TypeError,ZeroDivisionError) as e:
                        issues.append(dict(record=r['id'],stage='reference',message=str(e)))
                if not refs:raise ValueError('no_computable_reference')
                basis=integration_basis(records,refs); n=len(records)
                for warning in basis['warnings']:issues.append(dict(record=pool,stage='integration',message=warning))
                # One mesh already exists: union tiles selected by the full-pool threshold.
                from shapely.ops import unary_union
                for method in ('mv50','mv_strict'):
                    support=basis['mesh']['votes'].sum(axis=0)
                    keep=2*support>=n if method=='mv50' else 2*support>n
                    geom=unary_union([t for t,yes in zip(basis['mesh']['tiles'],keep) if yes])
                    features.append(dict(type='Feature',geometry=mapping(geom),properties=dict(pool=pool,image=code,condition=condition,gate=gate,method=method,n=n)))
                    for k in range(1,n+1):
                        q=probabilities(basis['patterns'],((1<<n)-1,),(n,),(k,),method)
                        for version,g in basis['references'].items():
                            m=area_summary(basis['area'],basis['overlap'][version],g.area,q)
                            r=dict(**{f:row[f] for f in ('image','building','condition','gate','scene','difficulty','n','pool','quality_compatible')},method=method,version=version,k=k,
                                D=m['ref_symdiff_ref'],O=m['omission_ref'],E=m['extension_ref'],V=m['member_symdiff_union'])
                            curves.append(r)
                            if k==n:
                                assert abs(r['D']-geom.symmetric_difference(g).area/g.area)<1e-9
                                endpoints.append(r)
            except (ValueError,KeyError,IndexError,TypeError,ZeroDivisionError,AssertionError) as e:
                row.update(status='whole_pool_unavailable',reason=f'{type(e).__name__}:{e}')
                # Explicit failed pool: no partial curves or output is analyzed.
                curves[:]=[r for r in curves if r['pool']!=pool]
                endpoints[:]=[r for r in endpoints if r['pool']!=pool]
                features[:]=[f for f in features if f['properties']['pool']!=pool]
            coverage.append(row)
        if (ix+1)%25==0:print(f'{ix+1}/{len(research)} images; {len(curves)} rows',flush=True)
    for name,rows in [('coverage',coverage),('roster',roster),('curves',curves),('endpoints',endpoints)]:write_csv(OUT/(name+'.csv'),rows)
    write_json(OUT/'all_consensus.geojson',dict(type='FeatureCollection',features=features))
    write_json(OUT/'issues.json',issues)
    summarize(curves)
    write_json(OUT/'field_contract.json',dict(schema='difficulty_full_v1',date='2026-10-07',source_manifest='analysis_results/research_input_20260929/manifest.json',
        sources=['Current load_current_bundle/project_bundle; existing ordered_source_pair_indices','Corrected inventory + 8-image user difficulty update'],
        population='All research_annotation_image entries; two reference-only images not counted. All current independent consensus-eligible records, separated by condition and gate. Failed geometry keeps whole pool unavailable; no member removed to repair it.',
        quality='Difficulty ordinary panel uses manual/main_candidate/all quality_candidate. Expanded panel additionally accepts annotatable doorway with existing three-level label; it does not change quality eligibility. Difficult/pending doorway and all OOS stay separate descriptive strata.',
        metrics='Exact finite-pool uniform k-subset area expectations. D=O+E normalized by GT; V by full-pool union. Full geometry and all endpoints saved; k=N V=0 mechanical.',
        summary='Fixed N>=limit pools, original or revised-where-available, conditions/scenes kept separate. Unknown difficulty has its own descriptive output, never relabeled. Building-equal and image-equal results retained.',
        limits='Scene gates remain observational. Reference validity is geometric, not semantic certification. High D cannot by itself prove difficulty, worker error, or GT error. OOS output only where current declared-footprint model is computable.',
        snapshots='roster.csv provides exact pool membership; issues.json logs representation/reference warnings; coverage includes every research image.',
        images=len(research),pools=len(coverage),success=sum(r['status']=='ready' for r in coverage),geometry_count=len(features)))
    print(json.dumps(dict(images=len(research),pools=len(coverage),ready=sum(r['status']=='ready' for r in coverage),curves=len(curves))))
    deliver()


def summarize(curves):
    grouped=defaultdict(dict)
    for r in curves:grouped[r['pool'],r['method'],r['version']][r['k']]=r
    output=[]; trajectory=[]
    for (pool,method,v),c in grouped.items():
        first=c[1]; n=first['n']; assert len(c)==n
        r={f:first[f] for f in ('pool','image','building','condition','gate','scene','difficulty','quality_compatible','n','method','version')}
        r.update({f'D{k}':c[k]['D'] if k in c else None for k in (1,2,4,8,16,20,24)})
        r.update(D_all=c[n]['D'],O_all=c[n]['O'],E_all=c[n]['E'])
        for a,b in ((1,4),(4,8),(8,16),(16,20),(9,17)):
            r[f'gain_{a}_{b}']=c[a]['D']-c[b]['D'] if b in c else None
        trajectory.append(r)
    for condition in ('manual','semi','oos'):
        for scope in ('ordinary_quality','with_annotatable_door','with_labeled_door','doorway_other','oos','oos_pending'):
            candidates=[]
            for key,c in grouped.items():
                r=c[1]
                if r['condition']!=condition or r['version']!='original' or r['method']!='mv50':continue
                ordinary=r['scene']=='ordinary' and r['gate']=='main_candidate' and r['quality_compatible']
                chosen=(scope=='ordinary_quality' and ordinary) or (scope=='with_annotatable_door' and (ordinary or r['scene']=='doorway_annotatable')) or (scope=='doorway_other' and r['scene'] in ('doorway_difficult','doorway_pending')) or (scope in ('oos','oos_pending') and r['scene']==scope)
                if scope=='with_labeled_door':
                    chosen=ordinary or (r['scene'].startswith('doorway_') and r['difficulty'] in LABELS)
                if chosen:candidates.append(r)
            for limit in (2,4,8,16,20,24):
                for label in (*LABELS,'未知'):
                    selected=[r for r in candidates if r['n']>=limit and (r['difficulty']==label if label!='未知' else r['difficulty'] not in LABELS)]
                    if not selected:continue
                    for policy in ('original','revised_where_available'):
                        for method in ('mv50','mv_strict'):
                            for k in range(1,limit+1):
                                rs=[grouped[r['pool'],method,'manual_revision' if policy!='original' and (r['pool'],method,'manual_revision') in grouped else 'original'][k] for r in selected]
                                bs=defaultdict(list)
                                for r in rs:bs[r['building']].append(r['D'])
                                output.append(dict(condition=condition,scope=scope,limit=limit,difficulty=label,evaluation=policy,method=method,k=k,pool_n=len(rs),image_n=len({r['image'] for r in rs}),building_n=len(bs),D=mean(r['D'] for r in rs),median_D=median(r['D'] for r in rs),building_D=mean(mean(x) for x in bs.values()),O=mean(r['O'] for r in rs),E=mean(r['E'] for r in rs),images='|'.join(sorted({r['image'] for r in rs}))))
    write_csv(OUT/'per_image.csv',trajectory);write_csv(OUT/'summary.csv',output)


def deliver():
    import ast
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=read_csv(OUT/'summary.csv'); coverage=read_csv(OUT/'coverage.csv')
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    fig,axs=plt.subplots(2,3,figsize=(14,8))
    for ax,limit in zip(axs.flat,(2,4,8,16,20,24)):
        for label,color in zip((*LABELS,'未知'),('#297ba6','#bc8628','#b54c65','#999999')):
            rs=[r for r in summary if r['condition']=='manual' and r['scope']=='with_annotatable_door' and int(r['limit'])==limit and r['method']=='mv50' and r['evaluation']=='original' and r['difficulty']==label]
            if not rs:continue
            ax.plot([int(r['k']) for r in rs],[float(r['D']) for r in rs],'--' if label=='未知' else '-',color=color,label=f"{label} {rs[0]['image_n']}图")
        ax.set(title=f'固定 N≥{limit} 面板',xlabel='人数',ylabel='D / 参考面积');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('全量可用Manual质量池＋已明确可标门洞；未知难度单列，OOS不混入');fig.tight_layout();fig.savefig(OUT/'fixed_panels.png',dpi=150);plt.close(fig)
    # Reuse the previous review workbench; selection depends only on missing labels and N.
    selected=[r for r in coverage if r['status']=='ready' and r['condition']=='manual' and int(r['n'])>=20 and r['difficulty'] not in LABELS and
              ((r['scene']=='ordinary' and r['gate']=='main_candidate' and r['quality_compatible']=='True') or r['scene']=='doorway_difficult')]
    metadata={r['image_code']:r for r in load_current_bundle()['research']['images']}
    rows=[]
    for r in selected:
        m=metadata[r['image']]; label=ROOT/m['references']['gt_original'].split(':',2)[2]
        photo=label.parent.parent/'img'/f"{m['image_id']}.png"
        assert photo.is_file(),photo
        rows.append(dict(image_code=r['image'],image_id=m['image_id'],manual_n=int(r['n']),src='../../'+photo.relative_to(ROOT).as_posix()))
    source=ROOT/'tools/thesis_main/analysis/build_candidate_review_20260912.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    template=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='template' for t in n.targets))
    style=template.split('<style>',1)[1].split('</style>',1)[0]
    page=(ROOT/'tools/thesis_main/analysis/difficulty_review_20261006.html').read_text(encoding='utf-8')
    page=page.replace('8图难度补标','全量扩展：10图补充判断').replace('本次8图导出文件','本次全量扩展导出文件').replace('8图标注难度_20261006.json','全量扩展10图难度_20261007.json')
    page=page.replace('前7张用于补齐共同24人×10图面板，第8张为23人补充图。','本页按缺少标签和人数≥20选择7张普通图、3张门洞图，不按融合分数选择。门洞请在备注中说明可标／不可标；可以选择暂不能判断。无需重新审查已完成的图。')
    page=page.replace('OOS：房间结构难以用当前布局准确表达。','OOS保留非正交但可标等子类；请在备注说明，不以可标性直接替代OOS判断。')
    data=dict(schema='difficulty_full_review_20261007_v1',images=rows)
    page=page.replace('/*__STYLE__*/',style).replace('/*__DATA__*/',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    (OUT/'review.html').write_text(page,encoding='utf-8');write_json(OUT/'review_roster.json',dict(selection='N>=20 and missing/unresolved difficulty; seven main-quality ordinary, three doorway-difficult; no score selection',images=selected))


if __name__=='__main__':run()
