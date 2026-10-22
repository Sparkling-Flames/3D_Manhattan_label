"""Select interpretable research uses from the complete saved comparisons.

No fusion, scoring, label fitting or automatic winner search occurs here.
The complete alternative grid remains in exchanges/, difficulty/, direct_ac/.
Run from any directory: python this_file.py
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'integration'
COMMIT = 'ef148c82df18582228b2d23837faa2659e79eba7'


def write_csv(df, path):
    import os
    payload = df.to_csv(index=False, lineterminator='\n').encode('utf-8-sig')
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    allc = pd.read_csv(ROOT/'exchanges/ALL_CONDITIONS.csv').set_index('condition_id')
    qt = pd.read_csv(ROOT/'exchanges/COMMON_QT_CONDITIONS.csv').set_index('condition_id')
    diff = pd.read_csv(ROOT/'difficulty/exchange_difficulty_core.csv')
    # Prioritize clear broad support, targeted benefits, adverse controls and capacity boundaries.
    selected = [
        ('S01','214f58a11c554f2656d1',None,'主文：结构构成','常规表达→较多转折','m4/20人；广支持结构与定位变化；配合困难分层'),
        ('S02','31838b69575a07dea212',None,'主文：较大结构块','常规表达→较多转折','m7/20人；与m4共同路径另读，不把不同图集均值相减'),
        ('S03','2362f64d9bda71772743',None,'主文：反向与稀释','较多转折→常规表达','多数图降质；是构成作用的反向证据'),
        ('J01','b7f3791f74741a73f888',None,'主文：质量与时间兼顾','历史Q更高且相对更快','n20/m4；共同Q/T分母；保留失败及具体成员范围'),
        ('J02','e66456756f4ccdbb88e9',None,'补充：小块广支持','历史Q更高且相对更快','n20/m2覆盖较广；幅度小，作为规模补充'),
        ('J03','9e3313756e09c2f6318b',None,'补充：较大块','历史Q更高且相对更快','n20/m5可用；未显示m增加必然更好'),
        ('J04','b92165c5830d388eaf1a',None,'补充：容量边界','历史Q更高且相对更快','n20/m6仅3图2楼；目标队单例时不估可互换性'),
        ('J05','46c4f2cb2bf2e8abd5b1',None,'主文：用时间换质量','换入该折最高历史Q角色、相对更慢','后选阶段B；共同Q/T分母；与阶段A全部q_up/slower分开'),
        ('J06','601a81f5fd12c11ed4bf',None,'主文对照：一般高Q慢类','历史Q更高且相对更慢','n20/m4全部目标角色；时间代价较大，不等于最高Q目标效果'),
        ('J07','f1fe8399655c5d306053',None,'主文：不利方向','历史Q较低且相对更慢','n20/m3多数图降质且费时；保留反向组织规律'),
        ('J08','ca2a651478a2ab2966a4',None,'主文：总体与条件分开','历史Q较低且相对更快','总体均值正但多数图不改善；必须读简单/困难分层'),
        ('D01','ca2a651478a2ab2966a4','困难','主文：新增条件性定位收益','历史Q较低且相对更快','n20/m3困难图6/9改善；内部探索；并列失败及负例'),
        ('D02','ca2a651478a2ab2966a4','简单','主文：新增质量时间代价','历史Q较低且相对更快','n20/m3简单图0/11改善；同一方向的条件反差'),
        ('D03','81a9856eb2855547a6ff','困难','主文：方向失效机制','历史Q更高且相对更慢','n20/m3困难图多数降质；IoU改善不能替代方向残差和总Q'),
        ('D04','81a9856eb2855547a6ff','简单','补充：小升质大时间代价','历史Q更高且相对更慢','n20/m3简单图多数小升质；记录时间代价约16.5%'),
        ('E01','6f8dcc78d20d07151bde',None,'主文：Semi效率','历史Q较高且更快、表达偏转折目标','n14/m3；来源分区扩展；时间收益与有限质量收益分别评价'),
        ('E02','c3b6ed125cdf1afd7c74',None,'补充：Semi较大替换比例','历史Q较高且更快、表达偏转折目标','n12/m4；时间下降更多但只有5图4楼'),
        ('E03','b4c3a65f81ab691503c3',None,'主文对照：Semi质量代价','历史Q较高且更快、表达偏转折目标','原配置补全n12/m3；多数图Q下降但省时；不同支持不可并为同效应'),
    ]
    rows = []
    for rid,cid,level,use,semantic,reason in selected:
        base = allc.loc[cid].to_dict()
        row = dict(base)
        row.update(recommendation_id=rid, condition_id=cid,
                   difficulty_scope=level or '全部当前难度', recommended_use=use,
                   source_target_semantics=semantic, selection_reason=reason,
                   selection_status='本轮依据完整已存比较作内部探索选择；标签为既有楼外历史',
                   source_commit=COMMIT, data_version='real_v2',
                   exact_events=f"exchanges/{base['analysis_batch']}/EXACT_EVENT_LINKS.csv.gz",
                   scalar_events=f"exchanges/{base['analysis_batch']}/EVENT_OUTCOMES.csv.gz",
                   labels='inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz',
                   complete_alternative_grid='exchanges/ALL_CONDITIONS.csv')
        if level:
            z=diff[(diff.condition_id==cid)&(diff.current_difficulty==level)]
            assert len(z)==1
            row.update(z.iloc[0].to_dict())
            for k in ['registered_rows','unique_oriented_ABC','physical_ABC','backgrounds','three_scored_rows','time_comparable_rows',
                      'A_unique_endpoints','A_failed_unique_endpoints','B_unique_endpoints','B_failed_unique_endpoints',
                      'C_unique_endpoints','C_failed_unique_endpoints','distinct_BC_pairs','distinct_scored_BC_pairs',
                      'distinct_BC_net_loss_gt5','distinct_BC_net_loss_gt10']:
                row[k]=None  # populate precisely from the filtered exact support below where available
            for key in list(row):
                if key.startswith(('image_','building_','background_')):
                    row[key]=None
            for name in ['net_B8L2','cross_B8L2','symmetric_B8L2','abs_advantage_B8L2']:
                for unit in ['images','buildings']:
                    row[f"{unit[:-1]}_{name}_known"]=row[f'{name}_{unit}']
                    row[f"{unit[:-1]}_{name}_positive"]=row[f'{name}_positive_{unit}']
                    row[f"{unit[:-1]}_{name}_negative"]=row.get(f'{name}_negative_{unit}')
            row['images']=row['total_images']; row['buildings']=row['total_buildings']
            row['complete_alternative_grid']='difficulty/exchange_difficulty_core.csv'
            row['time_denominator_note']='时间与质量各自真实支持；困难表分项逐指标分母见 exchange_difficulty_full.csv.gz'
        else:
            q=qt.loc[cid]
            for k in ['joint_common_rows','joint_common_images','joint_common_buildings','net_B8L2','net_D10','net_recorded_time_pct',
                      'net_Q_up_images','net_Q_up_buildings','net_time_down_images','net_time_down_buildings']:
                row['commonQT_'+k]=q[k]
            row['time_denominator_note']='全时间支持与三队Q/T交集同时保留；commonQT_前缀为同分母用途'
        rows.append(row)
    rec=pd.DataFrame(rows)
    members=[]
    for batch in rec.analysis_batch.unique():
        ev=pd.read_csv(ROOT/f'exchanges/{batch}/EXACT_EVENT_LINKS.csv.gz',low_memory=False)
        for i,row in rec[rec.analysis_batch==batch].iterrows():
            sub=ev[ev.condition_id==row.condition_id].copy()
            if row.difficulty_scope!='全部当前难度':
                sub=sub[sub.difficulty==row.difficulty_scope]
            assert len(sub)>0, row.recommendation_id
            rec.loc[i,'registered_rows']=len(sub)
            rec.loc[i,'unique_oriented_ABC']=sub.actual_oriented_ABC.nunique()
            rec.loc[i,'physical_ABC']=sub.actual_physical_ABC.nunique()
            rec.loc[i,'backgrounds']=sub.background_key.nunique()
            rec.loc[i,'fold_class_pairs']=len(sub[['pool_id','source_class','target_class']].drop_duplicates())
            rec.loc[i,'building_class_pairs']=len(sub[['building','source_class','target_class']].drop_duplicates())
            rec.loc[i,'seat_change_r_AC_min']=sub.seat_change_r_AC.min()
            rec.loc[i,'seat_change_r_AC_max']=sub.seat_change_r_AC.max()
            rec.loc[i,'source_replaced_fraction_min']=sub.replace_fraction_source_in_A.min()
            rec.loc[i,'source_replaced_fraction_max']=sub.replace_fraction_source_in_A.max()
            rec.loc[i,'target_in_background_min']=sub.target_class_count_D.min()
            rec.loc[i,'target_in_background_max']=sub.target_class_count_D.max()
            for keys,g in sub.groupby(['building','image','source_class','target_class'],dropna=False):
                b,im,sc,tc=keys
                z={'recommendation_id':row.recommendation_id,'condition_id':row.condition_id,
                   'building':b,'image':im,'source_class_in_this_fold':sc,'target_class_in_this_fold':tc,
                   'n':row.n,'actual_m':row.actual_m_AC,'rows':len(g),'backgrounds':g.background_key.nunique(),
                   'source_block_X_variants':g.outgoing_block_X.nunique(),'same_block_Y_variants':g.same_count_block_Y.nunique(),
                   'target_block_Z_variants':g.changed_count_block_Z.nunique(),'exact_event_file':row.exact_events}
                for c in ['outgoing_block_X','same_count_block_Y','changed_count_block_Z','common_background']:
                    z[c+'_person_union']='|'.join(sorted({w for v in g[c].dropna() for w in v.split('|') if w}))
                for c in [c for c in g if c.startswith('class_center_delta_')]:
                    z[c+'_min']=g[c].min(); z[c+'_max']=g[c].max()
                members.append(z)
    first=['recommendation_id','recommended_use','selection_reason','source_target_semantics','condition','method_id','tier',
           'analysis_batch','study_group','source_domain','difficulty_scope','n','actual_m_AB','actual_m_AC','actual_m_BC',
           'replacement_fraction_team','seat_change_r_AC_min','seat_change_r_AC_max','source_replaced_fraction_min',
           'source_replaced_fraction_max','target_in_background_min','target_in_background_max','images','buildings',
           'backgrounds','same_B8L2','cross_B8L2','net_B8L2','within_abs_B8L2','symmetric_cross_abs_B8L2',
           'image_net_B8L2_positive','image_net_B8L2_known','building_net_B8L2_positive','building_net_B8L2_known',
           'net_D10','net_iou_2d','net_IoU3D100','net_S_bottom_deg','net_dir','net_Hmean','net_Hcenter',
           'net_fusion_turn_n','net_fusion_short_turn_edges','net_fusion_redundancy_n','net_recorded_time_pct',
           'commonQT_net_B8L2','commonQT_net_recorded_time_pct','A_failure','B_failure','C_failure','net_loss_gt5','net_loss_gt10']
    rec=rec[first+[c for c in rec if c not in first]]
    write_csv(rec,OUT/'RECOMMENDED_STRICT_CONDITIONS.csv')
    write_csv(pd.DataFrame(members),OUT/'RECOMMENDED_CONDITION_MEMBERS_BY_FOLD.csv')
    # A concise human-facing table. Complete components and denominators remain above.
    fields={
      'recommendation_id':'编号','recommended_use':'采用用途','source_target_semantics':'类别方向','condition':'评价条件',
      'difficulty_scope':'难度','n':'总人数n','actual_m_AC':'实际换人数m','replacement_fraction_team':'换人占比',
      'source_replaced_fraction_min':'原队源类替换比例最小','source_replaced_fraction_max':'原队源类替换比例最大',
      'target_in_background_min':'背景目标类人数最小','target_in_background_max':'背景目标类人数最大',
      'images':'登记图片数','buildings':'登记建筑数','backgrounds':'精确背景数','same_B8L2':'B减A_Q',
      'cross_B8L2':'C减A_Q','net_B8L2':'C减B_Q','within_abs_B8L2':'同类绝对Q变化',
      'symmetric_cross_abs_B8L2':'跨类对称绝对Q变化','image_net_B8L2_positive':'净Q改善图',
      'image_net_B8L2_known':'净Q可评图','building_net_B8L2_positive':'净Q改善楼','building_net_B8L2_known':'净Q可评楼',
      'net_D10':'净D10','net_iou_2d':'净底面IoU','net_IoU3D100':'净三维IoU百分值',
      'net_dir':'净方向残差度','net_S_bottom_deg':'净底点误差度','net_fusion_turn_n':'净实际转折',
      'net_recorded_time_pct':'全时间支持_净记录时间百分比','commonQT_net_recorded_time_pct':'共同QT支持_净记录时间百分比',
      'C_failure':'C失败率_图楼等权','net_loss_gt5':'净损失超5分率_图楼等权','net_loss_gt10':'净损失超10分率_图楼等权',
      'selection_reason':'采用理由与条件','exact_events':'精确ABC与块关联文件','condition_id':'精确条件键'}
    write_csv(rec[list(fields)].rename(columns=fields),OUT/'有效换类条件表.csv')
    (OUT/'RECOMMENDATION_TABLE_RECEIPT.json').write_text(json.dumps({
      'source_commit':COMMIT,'selection_rows':len(rec),'member_support_rows':len(members),
      'new_fusion':0,'new_scores':0,'new_labels':0,
      'selected_after_comparison':True,'complete_strict_conditions':85,'complete_difficulty_cells':201,
      'notes':['建议表是完整比较后的选型，不替代全部结果。',
               'difficulty_scope行没有把总条件的端点/损失分母复制成该层分母；分层项从完整表与精确成员读取。',
               '有限配对幅度、直接AC、旧重叠设计各自读独立完整表，不用C−B排名C−A。']},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {len(rec)} conditions and {len(members)} fold/image role member rows.')


if __name__=='__main__':
    main()
