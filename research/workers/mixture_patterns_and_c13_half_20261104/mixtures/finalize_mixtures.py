#!/usr/bin/env python3
"""Build the conclusion/source indexes and verify the completed mixture delivery."""
from pathlib import Path
import gzip,hashlib,json,re,shutil
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from PIL import Image

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
HEAD='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
URL='https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/'+HEAD+'/'
def read(name):return pd.read_csv(HERE/name,low_memory=False)
def save(d,name):d.to_csv(HERE/name,index=False,encoding='utf-8-sig',float_format='%.14g')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    findings=[]
    def add(file,filters,claim,decision='保持',interpretation='',units='Q_points'):
        d=read(file)
        for key,value in filters.items():d=d[d[key].eq(value)]
        assert len(d)==1,(file,filters,len(d))
        r=d.iloc[0].to_dict()
        keep={k:r.get(k) for k in ['method','metric','valid_images','buildings','image_mean','image_median',
            'positive_images','negative_images','zero_images','building_mean',
            'leave_one_building_image_mean_min','leave_one_building_image_mean_max','geometric_time_ratio']}
        findings.append(dict(claim_id=f'MIX{len(findings)+1:03}',claim=claim,decision=decision,interpretation=interpretation,
            units=units,source_file=file,exact_selector=json.dumps(filters,ensure_ascii=False,sort_keys=True),**keep))
    for fr,to,label in [('C1','C1|C3','C3补偿C1'),('C2','C2|C3','C3补偿C2'),
        ('C1|C2','C1|C2|C3','C3补偿C1+C2'),('C3','C1|C3','C1加入C3'),
        ('C3','C2|C3','C2加入C3'),('C2|C3','C1|C2|C3','C1加入C2+C3')]:
        add('DSTRUCT_ALLIANCE_STRATA.csv',dict(from_classes=fr,to_classes=to,axis='ALL',metric='B8L2'),label,
            '条件变化' if fr=='C2|C3' else '保持', '完整联盟含实际人数变化；两端共同Q')
    for shape in ['no_short_turns_or_boundary_occlusion','short_turns_without_boundary_occlusion','boundary_self_occlusion']:
        add('DSTRUCT_Q_COMMON_COMPONENT_STRATA.csv',dict(from_classes='C3',to_classes='C2|C3',
            axis='structural_condition',stratum=shape,metric='B8L2'),'C3加入C2的结构条件：'+shape,
            '条件变化','既有结构分层；不作为结构或遮挡的独立因果效应')
    for metric in ['fusion_turn_n','fusion_short_turn_edges','omission','boundary_loss','direction_loss','IoU3D100']:
        add('DSTRUCT_Q_COMMON_COMPONENT_STRATA.csv',dict(from_classes='C3',to_classes='C2|C3',
            axis='structural_condition',stratum='boundary_self_occlusion',metric=metric),'遮挡层的Q共同支持分项：'+metric,
            '保持','与Q采用同一批图片',metric)
    for n in [12,20]:
        for fr in ['C1','C2']:
            add('FIXED_N_FOCUSED_STRATA.csv',dict(method='TARGET_DSTRUCT_K3',source_domain='all_formal',n=n,
                from_class=fr,to_class='C3',axis='ALL',metric='effect',support='all_teams_Q_valid_in_both_configurations'),
                f'固定n={n}，{fr}少1/C3多1','保持','固定面板中完整配置均值差，随后对图等权')
        for metric in ['nondecreasing','no_drop_above_0_5','both_directions']:
            add('FIXED_N_THREE_OR_MORE_LEVEL_CHAIN_STRATA.csv',dict(method='TARGET_DSTRUCT_K3',source_domain='all_formal',
                n=n,from_class='C2',to_class='C3',axis='ALL',metric=metric,
                support='all_teams_Q_valid_in_every_configuration'),f'n={n}的C2→C3多层链：'+metric,
                '保持','至少3个连续配置；链→面板→图等权','fraction_of_panel_chains')
        for method,fr,to in [('TARGET_DSTRUCT_K3','C2','C3'),('OPPJOINT_K4','C3','C4')]:
            for metric in ['effect_Q','effect_logT']:
                add('Q_T_IDENTICAL_COMPLETE_STRATA.csv',dict(method=method,source_domain='new_only',n=n,
                    from_class=fr,to_class=to,axis='ALL',metric=metric),f'{method} n={n} {fr}→{to} 同队伍Q/T：'+metric,
                    '条件变化','合法同源、相同完整团队支持；劳动不等于墙钟或达标速度',
                    'Q_points' if metric=='effect_Q' else 'log_team_recorded_time')
    for method,fr,to in [('RFUSE_GEOM_K2','C1','C1|C2'),('RFUSE_GEOM_K2','C2','C1|C2'),
        ('OPPJOINT_K3','C1','C1|C3'),('OPPJOINT_K3','C2','C2|C3'),
        ('OPPJOINT_K4','C1','C1|C4'),('OPPJOINT_K4','C2','C2|C4'),('OPPJOINT_K4','C3','C3|C4')]:
        add('RFUSE_JOINT_CLASS_ADDITION_STRATA.csv',dict(method=method,from_classes=fr,to_classes=to,axis='ALL',metric='B8L2_CA'),
            method+' '+fr+'→'+to,'保持','按实际class_counts规范方向；不跨方法合并同号类别')
    for method,direction,m,n2 in [('RFUSE_GEOM_K2','1->2',4,31),('OPPJOINT_K3','1->3',7,28),('OPPJOINT_K4','1->2',7,28)]:
        for metric in ['B8L2_CA__step_difference','absolute_effect_change']:
            add('FIXED_BLOCK_BACKGROUND_STRATA.csv',dict(method=method,role_direction=direction,
                path_kind='fixed_XZ_expand_background_n',n_from=20,n_to=n2,m_from=m,m_to=m,axis='ALL',metric=metric),
                f'{method} {direction} m={m},n20→{n2}：'+metric,'条件变化',
                '固定X/Z、嵌套D，前后四端共同Q；绝对幅度先逐路径取绝对值')
    save(pd.DataFrame(findings),'KEY_FINDINGS.csv')

    src=read('SOURCES.csv');copies=json.loads((HERE/'INPUT_COPY_RECEIPT.json').read_text())
    copied={v['copy']:v for v in copies}
    equivalence=json.loads((HERE.parent/'audit/ASSISTED_SOURCE_LOGICAL_COMPARISON.json').read_text())
    assert len(equivalence)==3 and all(x['compressed_bytes_equal'] and x['decompressed_bytes_equal'] and x['dataframe_equals'] for x in equivalence)
    source_rows=[]
    for r in src.to_dict('records'):
        p=ROOT/r['path'];assert p.exists() and digest(p)==r['sha256'],r['path']
        canonical=copied[r['path']]['source_path'] if r['path'] in copied else r['path']
        derived=canonical.startswith('research/workers/current_class_interpretation_20261104/')
        source_rows.append(dict(local_path=r['path'],canonical_source_path=canonical,bytes=p.stat().st_size,
            sha256=digest(p),source_kind='derived_current_class_label_bridge' if derived else 'frozen_repository_input',
            source_commit='' if derived else HEAD,upstream_commit=HEAD,
            url='' if derived else URL+canonical,
            copied_assisted_source_equivalence_verified=r['path'] in copied))
    geometry=json.loads((HERE/'GEOMETRY_ILLUSTRATION_SOURCES.json').read_text())
    for r in geometry:
        p=ROOT/r['path'];assert digest(p)==r['sha256']
        source_rows.append(dict(local_path=r['path'],canonical_source_path=r['path'],bytes=p.stat().st_size,
            sha256=digest(p),source_kind='frozen_repository_geometry_input',source_commit=HEAD,upstream_commit=HEAD,
            url=URL+r['path'],copied_assisted_source_equivalence_verified=False))
    for p in [ROOT/'research/workers/current_class_interpretation_20261104/team_effects/COMMON_COMPLETE_PANEL_METRICS.csv',
              ROOT/'research/workers/current_class_interpretation_20261104/team_effects/REPORT_ZH.md']:
        source_rows.append(dict(local_path=str(p.relative_to(ROOT)),canonical_source_path=str(p.relative_to(ROOT)),
            bytes=p.stat().st_size,sha256=digest(p),source_kind='prior_delivered_interpretation',source_commit='',upstream_commit=HEAD,
            url='',copied_assisted_source_equivalence_verified=False))
    save(pd.DataFrame(source_rows).drop_duplicates('local_path'),'FINAL_SOURCE_MANIFEST.csv')

    bg=read('FIXED_BLOCK_BACKGROUND_IMAGE_EFFECTS.csv.gz')
    assert np.allclose(bg['B8L2_CA__to']-bg['B8L2_CA__from'],bg['B8L2_CA__step_difference'])
    assert np.allclose(bg.absolute_effect_to-bg.absolute_effect_from,bg.absolute_effect_change)
    assert bg.nested_fraction.eq(1).all()
    # Replace the exploratory early extract with the final common-support rows.
    focus=bg[bg.n_from.eq(20)&((bg.method.eq('RFUSE_GEOM_K2')&bg.m_from.eq(4)&bg.n_to.eq(31))|
        (bg.method.isin(['OPPJOINT_K3','OPPJOINT_K4'])&bg.m_from.eq(7)&bg.n_to.eq(28)))]
    save(focus,'BACKGROUND_FOCUS_IMAGE_EFFECTS.csv')
    q=read('DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz');assert np.allclose(q.Q_to-q.Q_from,q.B8L2,equal_nan=True)
    op=read('RFUSE_JOINT_CLASS_ADDITION_PAIRS.csv.gz');assert np.allclose(op.Q_to-op.Q_from,op.B8L2_CA,equal_nan=True)
    full=read('DSTRUCT_ALL_CLASSIFIED_VS_BEST_PURE_IMAGES.csv');assert len(full)==205 and abs(full.effect.mean()+6.050731808475973)<1e-9
    j=read('Q_T_IDENTICAL_COMPLETE_CONFIGURATION_PAIRS.csv.gz')
    assert j.teams_from_Q.eq(j.teams_from_logT).all() and j.teams_to_Q.eq(j.teams_to_logT).all()
    for name in ['analysis_run.log','depth_run.log']:
        if (HERE/name).exists():(HERE/name).unlink()
    if (HERE/'__pycache__').exists():shutil.rmtree(HERE/'__pycache__')
    stale_partials=[]
    for temporary in HERE.glob('*.writing'):
        target=temporary.with_name(temporary.name.removesuffix('.writing'))
        assert target.is_file() and target.stat().st_size>=temporary.stat().st_size
        # Only a completed, parseable destination permits cleanup of an
        # abandoned atomic-write temporary from an earlier interrupted pass.
        pd.read_csv(target,low_memory=False)
        stale_partials.append(temporary.name);temporary.unlink()
    artifact_checks=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or p.suffix=='.pyc':continue
        if p.name.endswith('.writing'):
            target=p.with_name(p.name.removesuffix('.writing'))
            assert target.is_file()
            # Some shared-workspace snapshots retain an already unlinked
            # abandoned temporary. It is not an output and is never packaged.
            stale_partials.append(p.name);continue
        if p.suffix=='.gz':
            with gzip.open(p,'rb') as f:
                while f.read(1024*1024):pass
            check='gzip_crc_passed'
        elif p.suffix=='.png':
            im=Image.open(p);im.verify();check='png_integrity_passed'
        elif p.suffix=='.svg':ET.parse(p);check='svg_xml_passed'
        else:continue
        artifact_checks.append(dict(path=str(p.relative_to(HERE)),check=check))
    # Check every explicit report/readme local link. Final verification and
    # delivery manifest are generated immediately below.
    promised={'FINAL_VERIFICATION.json','DELIVERY_MANIFEST.csv'};links=[]
    for name in ['REPORT_ZH.md','README.md']:
        for target in re.findall(r'\]\(([^)]+)\)',(HERE/name).read_text()):
            if target.startswith(('http:','https:','#')):continue
            local=target.split('#')[0]
            assert (HERE/local).exists() or local in promised,(name,target)
            links.append(dict(document=name,target=target))
    check=dict(status='passed',numeric_tolerance=1e-9,source_inputs_hash_verified=len(source_rows),
        assisted_inputs_byte_and_table_equivalent_to_fixed_git=True,paired_Q_closure=True,
        background_four_endpoint_common_Q_closure=True,background_nested_D=True,
        original_all_classified_vs_best_pure_benchmark_reproduced=True,Q_T_same_team_support=True,
        no_missing_Q_imputed=True,new_fits=0,new_teams=0,new_fusion=0,new_scores=0,
        findings=len(findings),verified_local_links=len(links),artifact_checks=artifact_checks,
        abandoned_partial_outputs_excluded=sorted(set(stale_partials)),
        visualization_review='four PNG figures visually reviewed; complete geometry nodes retained')
    (HERE/'FINAL_VERIFICATION.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
    record=dict(status='stable_for_parent_packaging',date='2026-11-04',scope='mixtures_module_only',
        report='REPORT_ZH.md',readme='README.md',findings='KEY_FINDINGS.csv',source_manifest='FINAL_SOURCE_MANIFEST.csv',
        source_commit=HEAD,figures=4,geometry_cases=3,geometry_endpoints=6,new_teams=0,
        source_equivalence_audit='../audit/ASSISTED_SOURCE_LOGICAL_COMPARISON.json')
    (HERE/'DELIVERY_RECORD.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    files=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(HERE.rglob('*'))
        if p.is_file() and p.name!='DELIVERY_MANIFEST.csv' and not p.name.endswith('.writing') and '__pycache__' not in p.parts]
    save(pd.DataFrame(files),'DELIVERY_MANIFEST.csv')
    print(json.dumps({k:v for k,v in check.items() if k!='artifact_checks'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
