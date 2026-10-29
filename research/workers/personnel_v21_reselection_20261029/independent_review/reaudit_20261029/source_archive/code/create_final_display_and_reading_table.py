"""Preserve the frozen review; create two display corrections and a source map.

Only saved result cells are extracted. No classification, fusion, scoring,
aggregation of research observations, or archive creation occurs here.
"""
from pathlib import Path
import argparse,csv,difflib,hashlib,json,math

HEADERS=['reading_group','description_zh','method','scope','stage_scope','n','m','axis','rank_direction',
         'metric','model','weighting','statistic','value','unit','display_value','denominator_value',
         'denominator_field','registered_events','registered_pools','registered_images','registered_buildings',
         'valid_images','valid_buildings','valid_team_links','source_file','source_sha256','source_filter_json',
         'source_csv_record_1based','source_field','interpretation']

def digest(data):return hashlib.sha256(data).hexdigest()

def main(args):
    root=Path(args.delivery_root).resolve();comp=root/'stage02_comparison'
    old=comp/'EVIDENCE_REVIEW_ZH.md';old_bytes=old.read_bytes();old_sha=digest(old_bytes)
    frozen_manifests={p.name:digest(p.read_bytes()) for p in [comp/'DELIVERY_READABILITY_INVENTORY.csv',comp/'DELIVERY_READABILITY_RECEIPT.json']}
    with (comp/'DELIVERY_READABILITY_INVENTORY.csv').open(encoding='utf-8-sig',newline='') as f:
        old_record=next(r for r in csv.DictReader(f) if r['path']=='EVIDENCE_REVIEW_ZH.md')
    assert old_record['sha256']==old_sha
    edits=[
      dict(old='| OPPJOINT K3 | 17.34% | 10.50% | 10.15% | 5.90% |',
           new='| OPPJOINT K3 | 17.35% | 10.50% | 10.15% | 5.90% |',
           source='stage02_comparison/conditional_results/CONDITIONAL_METHOD_SUMMARY.csv',
           filters={'method':'OPPJOINT_K3','metric':'B8L2','model':'exact_Q_quota','weighting':'building_equal'},
           field='candidate_extra_share_total',exact='0.1734511102643704',explanation='比例17.345111026437042%显示两位小数为17.35%。'),
      dict(old='|20/7，54共同池中Q共评52图18楼|1.992|−0.936|44/52|30/52|4.766|2.524|',
           new='|20/7，54共同池中Q共评52图18楼|1.991|−0.936|44/52|30/52|4.766|2.524|',
           source='stage02_comparison/abc_integrated/MAIN_HARD23_COMMON_POOL_READING.csv',
           filters={'stage':'combined_union','n':'20','m':'7','role':'hard_turn_rank_asc:2/3->3/3','metric':'B8L2_same_origin_gap'},
           field='T',exact='1.991497283958946',explanation='保存值直接显示三位小数为1.991，避免先显示五位再二次取整。')]
    new_bytes=old_bytes
    for edit in edits:
        a,b=edit['old'].encode(),edit['new'].encode();assert new_bytes.count(a)==1
        new_bytes=new_bytes.replace(a,b,1)
    diff=list(difflib.unified_diff(old_bytes.decode().splitlines(),new_bytes.decode().splitlines(),lineterm=''))
    assert len([x for x in diff if x.startswith('-') and not x.startswith('---')])==2
    assert len([x for x in diff if x.startswith('+') and not x.startswith('+++')])==2
    final=comp/'FINAL_EVIDENCE_REVIEW_ZH.md'
    if final.exists():assert final.read_bytes()==new_bytes
    else:final.write_bytes(new_bytes)

    cache={};cells=[];checks=[]
    def load(rel):
        if rel not in cache:
            path=root/rel;data=path.read_bytes()
            with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            cache[rel]=(digest(data),rows)
        return cache[rel]
    def select(rel,filters):
        sha,rows=load(rel)
        hits=[(i+1,r) for i,r in enumerate(rows) if all(r.get(k)==str(v) for k,v in filters.items())]
        assert len(hits)==1,(rel,filters,len(hits))
        i,r=hits[0];return sha,i,r
    def emit(rel,filters,field,meta,unit,den=None,description='',interpretation=''):
        sha,i,r=select(rel,filters);v=r[field];denv=r.get(den,'') if den else ''
        if v=='':display='不可评'
        else:
            val=float(v)
            if not math.isfinite(val):display='不可评'
            elif unit=='count':display=str(int(val))
            elif unit.startswith('fraction'):display=f'{val*100:.2f}%'
            else:display=f'{val:.3f}'
        rec=dict(meta,description_zh=description,value=v,unit=unit,display_value=display,
                 denominator_value=denv,denominator_field=den or '',source_file=rel,source_sha256=sha,
                 source_filter_json=json.dumps(filters,ensure_ascii=False,sort_keys=True,separators=(',',':')),
                 source_csv_record_1based=i,source_field=field,interpretation=interpretation)
        assert set(rec)<=set(HEADERS)
        cells.append(rec)

    # Verify both errata against the exact source cells, without recomputing them.
    for edit in edits:
        sha,i,r=select(edit['source'],edit['filters'])
        assert math.isclose(float(r[edit['field']]),float(edit['exact']),rel_tol=0,abs_tol=1e-15)
        edit['source_sha256']=sha;edit['source_csv_record_1based']=i;edit['source_exact_cell']=r[edit['field']]

    qsource='stage02_comparison/abc_integrated/MAIN_CONDITIONS_JOINT_Q.csv'
    qmetrics={'B8L2_same_origin_within':'同原A同类幅度W=|B−A|','B8L2_same_origin_cross':'同原A跨类幅度C_A=|C−A|',
              'B8L2_same_origin_gap':'额外幅度G=|C−A|−|B−A|','joint_Q_BA':'同类有向差B−A',
              'joint_Q_CA':'跨类相对原队有向差C−A','joint_Q_CB':'跨类相对同类有向差C−B'}
    stats=['mean_image','median_image','p10_image','p90_image','valid_images','positive_images',
           'negative_images','near_zero_images','mean_building','valid_buildings','positive_buildings']
    count_fields=['events','pools','images','buildings','jointly_scored_events','A_failed_events','B_failed_events','C_failed_events']
    qconditions=0
    for n,m in [(14,7),(20,7),(12,8),(16,8)]:
        for method in ['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3']:
            for direction in ['2/3->3/3','2/3->1/3']:
                filt=dict(method=method,scope='primary',n=n,m=m,axis='hard_turn_rank_asc',rank_direction=direction,
                          stage_scope='new_only' if m==8 else 'combined_union')
                _,_,r=select(qsource,filt);qconditions+=1
                assert len({r[k+'_valid_images'] for k in qmetrics})==1
                meta=dict(reading_group='strict_ABC_common_three_Q',**filt,registered_events=r['events'],registered_pools=r['pools'],
                          registered_images=r['images'],registered_buildings=r['buildings'],valid_images=r['joint_Q_CA_valid_images'],
                          valid_buildings=r['joint_Q_CA_valid_buildings'])
                note='A/B/C三端Q共同可评；m7旧新合并，m8本轮统一设计；背景→XYZ块→池→图→楼；正值不统一表示更好。'
                for field in count_fields:
                    emit(qsource,filt,field,dict(meta,metric='registration_or_score_status',statistic=field),'count',
                         'events' if field.endswith('_events') else None,description='登记与三端Q可评分母',interpretation=note)
                for metric,desc in qmetrics.items():
                    for stat in stats:
                        is_count=stat.endswith('_images') or stat.endswith('_buildings')
                        denom=metric+'_valid_buildings' if 'building' in stat else metric+'_valid_images'
                        if stat=='valid_images':denom='images'
                        elif stat=='valid_buildings':denom='buildings'
                        emit(qsource,filt,metric+'_'+stat,dict(meta,metric=metric,statistic=stat),'count' if is_count else 'Q',
                             denom,description=desc,interpretation=note)
    assert qconditions==16

    capsource='stage02_capacity/completed_supplement/FINAL_COMPETITIVE_N_M_FUNNEL.csv'
    capfields=['legal_pools','legal_images','legal_buildings','total_n_sufficient_pools','historical_3m_sufficient_pools',
               'class_feasible_pools','class_feasible_images','class_feasible_buildings','total_n_insufficient_pools',
               'historical_insufficient_after_n_pools','class_distribution_insufficient_after_history_pools',
               'old_registered_pools','new_registered_pools','combined_registered_pools','combined_executed_pools',
               'Q_CB_evaluable_pools','Q_gap_evaluable_pools','feasible_not_registered_pools',
               'Q_CB_unscorable_registered_pools','Q_gap_unscorable_registered_pools','old_events','new_events','combined_events']
    core=['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4']
    for method in core:
        for n,m in [(14,7),(20,7),(12,8),(16,8)]:
            filt=dict(method=method,n=n,m=m);_,_,r=select(capsource,filt)
            meta=dict(reading_group='four_grid_capacity_funnel',scope='ordinary_manual_primary_206',stage_scope='combined_coverage',
                      rank_direction='all_class_directions_union',**filt,registered_pools=r['combined_registered_pools'],metric='capacity_or_execution_count')
            for field in capfields:
                den='combined_registered_pools' if field in ['Q_CB_evaluable_pools','Q_gap_evaluable_pools','Q_CB_unscorable_registered_pools','Q_gap_unscorable_registered_pools'] else None
                emit(capsource,filt,field,dict(meta,statistic=field),'count',den,description='四主网格全部类别方向的容量与执行漏斗',
                     interpretation='本源表合法域为206个普通Manual主目标池；另30个准入目标池在四格均因总人数不足退出。所有方向并集，不是上行方向分母；C−B与三端幅度支持分别保留。')

    modelsource='stage02_comparison/conditional_results/CONDITIONAL_METHOD_SUMMARY.csv'
    modelmethods=['TARGET_DSTRUCT_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','V21_DSTRUCT_RAW3_K3','V3_JOINT_QT_COARSE']
    modelfields=['total_variance','baseline_residual_variance','combined_residual_variance','increment_variance',
                 'candidate_extra_share_total','candidate_share_baseline_residual','baseline_explained_share','remaining_share_total',
                 'panels','pools','images','buildings','valid_team_links','nonconstant_images','images_increment_gt_1pct_total']
    for method in modelmethods:
        for metric,model in [('B8L2','exact_Q_quota'),('B8L2','quota_continuous_Q'),('fusion_turn_n','quota_continuous_Q'),('record_time_single_source','quota_continuous_QT')]:
            filt=dict(method=method,metric=metric,model=model,weighting='building_equal');_,_,r=select(modelsource,filt)
            meta=dict(reading_group='same_team_history_Q_QT_control',scope='ordinary_manual_primary_common_history',stage_scope='reused_saved_finite_teams',
                      **filt,valid_images=r['images'],valid_buildings=r['buildings'],valid_team_links=r['valid_team_links'])
            for field in modelfields:
                frac=field in ['candidate_extra_share_total','candidate_share_baseline_residual','baseline_explained_share','remaining_share_total']
                unit='fraction_baseline_residual_variance' if field=='candidate_share_baseline_residual' else 'fraction_total_variance' if frac else 'variance_in_metric_units_squared' if 'variance' in field else 'count'
                den='baseline_residual_variance' if field=='candidate_share_baseline_residual' else 'total_variance' if frac else None
                emit(modelsource,filt,field,dict(meta,statistic=field),unit,den,description='相同有限团队在明确历史Q/QT基线后的描述性增量',
                     interpretation='各指标内部方法共享支持；时间仅130面板31图21楼116966关联。完整候选构成格与Q配比格交叉；非预测准确率、因果独立效应或质量提升百分比。')

    commonsource='stage02_comparison/abc_integrated/MAIN_HARD23_COMMON_POOL_READING.csv'
    for n,m in [(14,7),(20,7),(12,8),(16,8)]:
        for metric,desc in qmetrics.items():
            filt=dict(stage='new_only' if m==8 else 'combined_union',n=n,m=m,role='hard_turn_rank_asc:2/3->3/3',metric=metric)
            _,_,r=select(commonsource,filt)
            meta=dict(reading_group='same_pool_TARGET_RAW3_comparison',scope='ordinary_manual_primary',stage_scope=filt['stage'],method='TARGET_DSTRUCT_K3_vs_V21_DSTRUCT_RAW3_K3',
                      n=n,m=m,axis='hard_turn_rank_asc',rank_direction='2/3->3/3',metric=metric,registered_pools=r['common_registered_pools'],valid_images=r['images'],valid_buildings=r['buildings'])
            for field in ['common_registered_pools','paired_pools','images','buildings','T','R','Tpos','Rpos','Rgreater','Tbuilding','Rbuilding','Tbuildingpos','Rbuildingpos']:
                ismean=field in ['T','R','Tbuilding','Rbuilding']
                den='buildings' if field in ['Tbuilding','Rbuilding','Tbuildingpos','Rbuildingpos'] else 'images' if field in ['T','R','Tpos','Rpos','Rgreater'] else 'common_registered_pools' if field=='paired_pools' else None
                emit(commonsource,filt,field,dict(meta,statistic=field),'Q' if ismean else 'count',den,description=desc+'；T=TARGET，R=RAW3',
                     interpretation='相同目标池、n/m、hard角色方向及指标共评；通常未固定两法相同A/D。m8共同7池中6池实体ABC完全相同，非独立复现。')

    randomsource='stage02_comparison/conditional_results/LABEL_RANDOMIZATION_REFERENCE.csv'
    for method,metric in [('TARGET_DSTRUCT_K3','B8L2'),('TARGET_DSTRUCT_K3','fusion_turn_n'),('TARGET_DSTRUCT_K3','record_time_single_source'),('OPPJOINT_K4','record_time_single_source')]:
        filt=dict(method=method,metric=metric,weighting='building_equal')
        for field in ['replicates','observed_increment_share','randomized_share_mean','randomized_share_p05','randomized_share_p50','randomized_share_p95','observed_minus_randomized_mean']:
            emit(randomsource,filt,field,dict(reading_group='Q_quota_label_randomization_reference',scope='ordinary_manual_primary_common_history',stage_scope='reused_saved_finite_teams',
                 model='exact_Q_quota',statistic=field,**filt),'count' if field=='replicates' else 'fraction_total_variance',description='仅固定Q二分人数的标签容量参照',
                 interpretation='128次Q人员层内标签置换；不含连续Q/T控制；描述格数与容量，不是总体p值或独立样本检验。')

    output=root/'stage05_synthesis/MAIN_COMPARISON_READING_TABLES.csv'
    with output.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=HEADERS);writer.writeheader();writer.writerows(cells)
    # Read each output cell back to the exact saved source record and field.
    with output.open(encoding='utf-8-sig',newline='') as f:reloaded=list(csv.DictReader(f))
    assert len(reloaded)==len(cells)
    for rec in reloaded:
        _,rows=load(rec['source_file']);row=rows[int(rec['source_csv_record_1based'])-1]
        assert row[rec['source_field']]==rec['value']
        assert all(row.get(k)==str(v) for k,v in json.loads(rec['source_filter_json']).items())
    assert old.read_bytes()==old_bytes
    assert all(digest((comp/name).read_bytes())==sha for name,sha in frozen_manifests.items())
    receipt=dict(purpose='仅两处显示取整更正；冻结原文及原哈希清单不变',original_file='stage02_comparison/EVIDENCE_REVIEW_ZH.md',original_sha256=old_sha,
                 final_file='stage02_comparison/FINAL_EVIDENCE_REVIEW_ZH.md',final_sha256=digest(new_bytes),edits=edits,
                 changed_content_lines=2,other_original_content_unchanged=True,original_manifests_unchanged=frozen_manifests,
                 reading_table=dict(file='stage05_synthesis/MAIN_COMPARISON_READING_TABLES.csv',sha256=digest(output.read_bytes()),rows=len(cells),columns=len(HEADERS),
                 groups={g:sum(r['reading_group']==g for r in cells) for g in sorted(set(r['reading_group'] for r in cells))},
                 all_values_roundtrip_to_exact_source_cell=True,source_csv_record_definition='1-based data record excluding header; metadata values and count denominators are copied directly',
                 value_definition='value preserves the exact source CSV cell; display_value is a convenience rendering, fractions shown as percent',
                 sources={rel:sha for rel,(sha,_) in cache.items()}),research_recalculations=0,archives_created=0)
    (comp/'DISPLAY_ERRATA.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'final_sha256':receipt['final_sha256'],'reading_rows':len(cells),'groups':receipt['reading_table']['groups'],'original_and_manifests_unchanged':True},ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--delivery-root',required=True);main(ap.parse_args())
