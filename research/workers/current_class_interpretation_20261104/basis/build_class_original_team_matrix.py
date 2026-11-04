#!/usr/bin/env python3
"""Join current class definitions, held-out originals, and existing team evidence."""
from pathlib import Path
import json
import hashlib
import numbers
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
BASE=OUT.parent
METHODS=['TARGET_DSTRUCT_K3','RFUSE_GEOM_K2','OPPJOINT_K3','OPPJOINT_K4']
FILES={
 'members':'basis/CLASS_MEMBERS_ALL.csv',
 'capacity':'basis/CLASS_CAPACITY_SUMMARY.csv',
 'contract':'basis/CURRENT_METHOD_CONTRACT.json',
 'dstruct_profile':'dstruct/ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv',
 'other_profile':'rfuse_joint/ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv',
 'dstruct_person':'dstruct/SAME_PERSON_SAME_BUILDING_DIFFICULTY.csv.gz',
 'dstruct_response':'dstruct/SAME_PERSON_DIFFICULTY_RESPONSE_SUMMARY.csv',
 'other_person':'rfuse_joint/DIFFICULTY_SAME_WORKER_BUILDING.csv.gz',
 'other_response':'rfuse_joint/DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv',
 'team_variance':'team_effects/COMMON_COMPLETE_PANEL_METRICS.csv',
 'abc_current':'team_effects/STRICT_ABC_CURRENT_METRICS.csv',
 'abc_frozen':'team_effects/STRICT_ABC_FROZEN_OTHER_METHODS.csv',
 'ac':'team_effects/DIRECT_AC_EXISTING_CONDITIONS.csv.gz',
 'alliances':'team_effects/TARGET_K3_ALLIANCE_METRICS.csv',
 'coalitions':'team_effects/EXISTING_COALITIONS_MEMBERS_BACKGROUND_Q.csv.gz',
}
DESCRIPTIONS={
 ('TARGET_DSTRUCT_K3','C1'):'ALL描述：困难结构较简化、近共线冗余偏多',
 ('TARGET_DSTRUCT_K3','C2'):'ALL描述：常规结构表达',
 ('TARGET_DSTRUCT_K3','C3'):'ALL描述：局部转折与短墙表达较多',
 ('RFUSE_GEOM_K2','C1'):'ALL描述：多数融合响应组',
 ('RFUSE_GEOM_K2','C2'):'ALL描述：困难转折融合响应较高',
 ('OPPJOINT_K3','C1'):'ALL描述：几何机会下较简化',
 ('OPPJOINT_K3','C2'):'ALL描述：常规且含长记录劳动成员',
 ('OPPJOINT_K3','C3'):'ALL描述：较高历史Q、更多局部细节',
 ('OPPJOINT_K4','C1'):'ALL描述：常规、较短记录劳动',
 ('OPPJOINT_K4','C2'):'ALL描述：几何机会下较简化',
 ('OPPJOINT_K4','C3'):'ALL描述：长记录劳动',
 ('OPPJOINT_K4','C4'):'ALL描述：较高历史Q、更多局部细节',
}
FEATURES={
 'TARGET_DSTRUCT_K3':'有效转折、短墙、近共线点、未匹配参考点；整体与困难响应两域；参考辅助',
 'RFUSE_GEOM_K2':'真实自然团队的结构、边界/尺度岭响应；总体/困难/困难−简单；GEOM无Q/T直接特征',
 'OPPJOINT_K3':'结构机会响应、边界机会响应、Q总体/低尾/响应、同源logT总体/响应四域',
 'OPPJOINT_K4':'结构机会响应、边界机会响应、Q总体/低尾/响应、同源logT总体/响应四域',
}

def read(key):return pd.read_csv(BASE/FILES[key],low_memory=False)
def save(d,name):d.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def one(d):
    assert len(d)==1,f'Expected 1 row, got {len(d)}'
    return d.iloc[0]
def md(d,columns,labels=None):
    d=d[columns].copy()
    if labels:d=d.rename(columns=labels)
    def v(x):
        if pd.isna(x):return ''
        if isinstance(x,numbers.Real) and not isinstance(x,numbers.Integral):return f'{x:.3f}'
        return str(x).replace('|',' / ').replace('\n',' ')
    rows=['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']
    rows += ['| '+' | '.join(v(x) for x in row)+' |' for row in d.itertuples(index=False,name=None)]
    return '\n'.join(rows)

def main():
    members=read('members');cap=read('capacity')
    dp=read('dstruct_profile').rename(columns={'images':'n_images','buildings':'n_buildings'})
    dp['source_stratum']=dp.source_stratum.replace({'all_sources':'all_origins','origin:new':'origin=new','origin:v1':'origin=v1'}).str.removeprefix('time:')
    dp['metric']=dp.metric.replace({'log_time':'record_log_time','source_active_time_seconds':'record_time_seconds'})
    op=read('other_profile')
    prof=pd.concat([dp,op],ignore_index=True)
    prof=prof[prof.condition.eq('manual')&prof.scope.eq('primary')]
    dperson=read('dstruct_person');dperson['source_stratum']=dperson.source_stratum.replace({'all_sources':'all_origins'})
    person=pd.concat([dperson,read('other_person')],ignore_index=True)
    person=person[person.condition.eq('manual')&person.scope.eq('primary')&person.source_stratum.eq('all_origins')]
    dresp=read('dstruct_response').rename(columns={'buildings':'n_buildings'});dresp['source_stratum']=dresp.source_stratum.replace({'all_sources':'all_origins'})
    resp=pd.concat([dresp,read('other_response')],ignore_index=True)
    resp=resp[resp.condition.eq('manual')&resp.scope.eq('primary')&resp.source_stratum.eq('all_origins')]
    var=read('team_variance');var=var[var.summary_axis.eq('all')&var.summary_value.eq('all')]
    directions=[]
    def add(eid,method,classes,design,quantity,effect,images,buildings,positive,negative,version,source,filter_text):
        directions.append(dict(evidence_id=eid,method=method,classes_involved='|'.join(classes),design=design,quantity=quantity,effect=float(effect),images=int(images),buildings=buildings,positive=positive,negative=negative,label_endpoint_version=version,source=source,source_filter=filter_text,interpretation='directional comparison involving classes; not an intrinsic single-class effect'))
    abc=read('abc_current')
    for metric in ['gap_sym','CB']:
        x=one(abc[abc.method.eq('TARGET_DSTRUCT_K3')&abc.scope.eq('updated_labels_legal_subset')&abc.version.eq('assisted_expanded')&abc.n.eq(14)&abc.m.eq(7)&abc.metric.eq(metric)])
        add('DSTRUCT_14_7_'+metric,'TARGET_DSTRUCT_K3',['C2','C3'],'strict ABC n14 m7 C2→C3',metric,x['mean'],x.images,x.buildings,x.positive,x.negative,'current legal labels; fixed-coordinate assisted expanded',x.source,'scope=updated_labels_legal_subset;version=assisted_expanded;n=14;m=7;metric='+metric)
    alliances=read('alliances')
    for cl in ['C1','C2','C3']:
        x=one(alliances[alliances.version.eq('updated')&alliances.scope.eq('primary')&alliances.condition.eq('manual')&~alliances.unknown_background_included&alliances.classes.eq(cl)&alliances.metric.eq('B8L2')])
        add('DSTRUCT_PURE_'+cl,'TARGET_DSTRUCT_K3',[cl],'all available members of pure class; unequal class capacities','mean_Q_not_contrast',x['mean'],x.valid_images,np.nan,np.nan,np.nan,'updated labels; assisted retained endpoint mixture',x.source,'version=updated;scope=primary;condition=manual;unknown_background_included=False;classes='+cl+';metric=B8L2')
    ac=read('ac')
    for method,direction,n,m,eid in [('RFUSE_GEOM_K2','1->2',20,4,'RFUSE_AC_20_4'),('OPPJOINT_K3','1->2',20,10,'JOINT3_AC_20_10')]:
        x=one(ac[ac.analysis_view.eq('A_fixed_n')&ac.scope.eq('primary')&ac.condition.eq('manual')&ac.method.eq(method)&ac.role_direction.eq(direction)&ac.n_condition.astype(str).eq(str(n))&ac.m_condition.astype(str).eq(str(m))&ac.metric.eq('B8L2_CA')])
        classes=['C'+z for z in direction.split('->')]
        add(eid,method,classes,f'AC n{n} m{m} {direction}', 'Q_C_minus_A',x.image_mean,x.valid_images,x.valid_buildings,x.positive_images,x.negative_images,str(x.label_version)+';'+str(x.endpoint_version),x.source,f'analysis_view=A_fixed_n;n={n};m={m};direction={direction};B8L2_CA')
    oldabc=read('abc_frozen')
    for direction,classes in [('1/3->2/3',['C1','C2']),('1/3->3/3',['C1','C3'])]:
        x=one(oldabc[oldabc.method.eq('OPPJOINT_K3')&oldabc.scope.eq('primary')&oldabc.n.eq(14)&oldabc.m.eq(7)&oldabc.axis.eq('q_rank_asc')&oldabc.rank_direction.eq(direction)])
        add('JOINT3_ABC_14_7_'+classes[-1],'OPPJOINT_K3',classes,'frozen strict ABC n14 m7 '+direction,'gap_sym',x.gap_sym,x.valid,np.nan,x.pos_sym,np.nan,str(x.label_version)+';'+str(x.endpoint_version),x.source,'method=OPPJOINT_K3;scope=primary;n=14;m=7;axis=q_rank_asc;rank_direction='+direction)
    co=read('coalitions')
    co=co[co.analysis_table.eq('COMPLETE_COALITIONS')&co.scope.eq('primary')&co.condition.eq('manual')&co.metric.eq('B8L2_CA')&co.number_condition.eq('more_people')&co.unknown_background_included.astype(str).str.lower().eq('false')]
    coalition_specs=[('RFUSE_GEOM_K2','role1 -> role1+role2',['C1','C2']),('OPPJOINT_K3','role1 -> role1+role2',['C1','C2']),('OPPJOINT_K3','role1 -> role1+role3',['C1','C3']),('OPPJOINT_K3','role2 -> role2+role3',['C2','C3']),('OPPJOINT_K4','role1 -> role1+role2',['C1','C2']),('OPPJOINT_K4','role1 -> role1+role3',['C1','C3']),('OPPJOINT_K4','role1 -> role1+role4',['C1','C4'])]
    for i,(method,direction,classes) in enumerate(coalition_specs):
        x=one(co[co.method.eq(method)&co.role_direction.eq(direction)])
        add('COALITION_'+str(i+1),method,classes,'complete coalition '+direction+'; more people','Q_C_minus_A',x.image_mean,x.valid_images,x.valid_buildings,x.positive_images,x.negative_images,str(x.label_version)+';'+str(x.endpoint_version),x.source,'COMPLETE_COALITIONS;scope=primary;manual;unknown=False;more_people;direction='+direction)
    directions=pd.DataFrame(directions)
    save(directions,'CLASS_TEAM_DIRECTION_LINKS.csv')

    rows=[]
    for method in METHODS:
        for cl in [f'C{i}' for i in range(1,int(method[-1])+1)]:
            m=one(members[members.method.eq(method)&members.class_id.eq(cl)])
            cp=one(cap[cap.method.eq(method)&cap.class_id.eq(cl)&cap.condition.eq('manual')&cap.scope.eq('primary')])
            row=dict(method=method,class_id=cl,classification_features=FEATURES[method],direct_Q_in_features=method.startswith('OPP'),direct_T_in_features=method.startswith('OPP'),reference_or_support_note='DSTRUCT has reference matching; RFUSE GEOM training eligibility requires complete Q outputs; JOINT directly uses Q/T',ALL_description=DESCRIPTIONS[(method,cl)],ALL_workers=int(m.workers),ALL_members=m.members,ALL_use='descriptive only; not permanent heldout membership',LOBO_number_meaning='training Q-center rank' if method.startswith('OPP') else ('training hard fusion-turn response rank' if method.startswith('RFUSE') else 'training hard original-turn center rank'),primary_pool_capacity_min=int(cp.capacity_min),primary_pool_capacity_median=float(cp.capacity_median),primary_pool_capacity_max=int(cp.capacity_max),capacity_pools=int(cp.pools),capacity_images_with_class=int(cp.pools_with_class),capacity_source=FILES['capacity'])
            profile_key='dstruct_profile' if method.startswith('TARGET') else 'other_profile'
            pp=prof[prof.method.eq(method)&prof.class_id.eq(cl)]
            for metric,name in [('B8L2','Q'),('turn_n','turn'),('short_turn_edges','short'),('S_bottom_deg','boundary_deg'),('matched_boundary_abs_deg','matched_boundary_abs_deg'),('omission','omission')]:
                x=one(pp[pp.source_stratum.eq('all_origins')&pp.metric.eq(metric)&pp.difficulty.eq('ALL')])
                row[name+'_image_equal']=float(x.image_equal_mean);row[name+'_building_equal']=float(x.building_equal_mean);row[name+'_images']=int(x.n_images);row[name+'_buildings']=int(x.n_buildings)
            x=one(pp[pp.source_stratum.eq('new|user_processed_reported_not_raw_log_replayed')&pp.metric.eq('record_log_time')&pp.difficulty.eq('ALL')])
            row.update(T_new_geometric_seconds_image_equal=float(np.exp(x.image_equal_mean)),T_new_geometric_seconds_building_equal=float(np.exp(x.building_equal_mean)),T_new_images=int(x.n_images),T_new_buildings=int(x.n_buildings),T_definition='exp(mean raw positive log seconds), all classes common within new origin/source',Q_T_cross_metric_same_support=False,original_profile_source=FILES[profile_key])
            for metric,name in [('B8L2','Q'),('turn_n','turn'),('short_turn_edges','short')]:
                for difficulty,label in [('简单','easy'),('困难','hard')]:
                    x=one(pp[pp.source_stratum.eq('all_origins')&pp.metric.eq(metric)&pp.difficulty.eq(difficulty)])
                    row[name+'_'+label+'_mean']=float(x.image_equal_mean);row[name+'_'+label+'_images']=int(x.n_images)
                row[name+'_hard_minus_easy_cross_section']=row[name+'_hard_mean']-row[name+'_easy_mean']
                pe=person[person.method.eq(method)&person.class_id.eq(cl)&person.metric.eq(metric)]
                pb=pe.groupby('building').hard_minus_easy.mean()
                row['same_person_'+name+'_hard_minus_easy']=float(pb.mean());row['same_person_'+name+'_buildings']=len(pb);row['same_person_'+name+'_worker_buildings']=len(pe)
            response_key='dstruct_response' if method.startswith('TARGET') else 'other_response'
            row['same_person_source']=FILES['dstruct_person' if method.startswith('TARGET') else 'other_person']
            if cl!='C1':
                prev='C'+str(int(cl[1:])-1);row['adjacent_response_reference_class']=prev
                for metric,name in [('B8L2','Q'),('turn_n','turn'),('short_turn_edges','short')]:
                    x=one(resp[resp.method.eq(method)&resp.class_A.eq(prev)&resp.class_B.eq(cl)&resp.metric.eq(metric)])
                    row['adjacent_response_'+name+'_difference']=float(x.building_equal_response_difference);row['adjacent_response_'+name+'_buildings']=int(x.n_buildings);row['adjacent_response_'+name+'_positive_buildings']=int(x.positive_buildings)
            row['adjacent_response_source']=FILES[response_key]
            for metric,name in [('B8L2','Q'),('log_recorded_time','logT'),('recorded_time_total_seconds','secondsT')]:
                x=one(var[var.method.eq(method)&var.metric.eq(metric)])
                row['METHOD_between_'+name+'_share_percent']=float(100*x.between_share);row['METHOD_'+name+'_panels']=int(x.panels);row['METHOD_'+name+'_images']=int(x.images);row['METHOD_'+name+'_buildings']=int(x.buildings)
            row['METHOD_variance_interpretation']='method-level property on common panels, repeated as metadata; never a per-class contribution'
            row['METHOD_variance_source']=FILES['team_variance']
            ev=directions[directions.method.eq(method)&directions.classes_involved.map(lambda s:cl in s.split('|'))]
            row['team_direction_evidence_ids']='|'.join(ev.evidence_id)
            row['team_direction_summary']='; '.join(f'{x.evidence_id}: {x.design}, {x.quantity}={x.effect:+.6f}, {x.images} images' for x in ev.itertuples())
            row['team_direction_source']='basis/CLASS_TEAM_DIRECTION_LINKS.csv'
            rows.append(row)
    matrix=pd.DataFrame(rows)
    save(matrix,'CLASS_ORIGINAL_TEAM_MATRIX.csv')

    methodtable=matrix.groupby('method',sort=False).first().reset_index()
    sections=['# 当前类别—原答—团队效果对照表\n',
       '## 阅读规则\n\n这份表把用户要求的分类依据、人员和容量、实际标法、Q/T、困难响应与团队效果接在一起。四个当前方法分别是DSTRUCT K3、RFUSE K2、OPPJOINT K3/K4；没有重选分类。完整机器表为[CLASS_ORIGINAL_TEAM_MATRIX.csv](CLASS_ORIGINAL_TEAM_MATRIX.csv)，每个类别一行。\n',
       '**ALL名单仅作全数据描述；下列原答和容量使用目标建筑的LOBO标签。Q、转折、短墙、边界各指标使用其全类共同支持；new时间也要求全类共同支持，但具有独立分母。不能将本表不同支持的Q与T直接拼成效率对比，严格同一批原答的Q/T比较应查[共同记录Q/T表](../rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv)。**\n',
       '原答短墙为底面周长占比<4%、两端转角≥15°；转折>5°；边界列为已采用质量分项`S_bottom_deg`。T为正记录劳动的几何均值，单位秒，限定new同一来源。每图容量取206个普通Manual主目标池，零表示该类在该图不存在。\n',
       '## 方法层团队效果：只在这里解释一次\n\n以下Q配比间份额基于共同的174个完整面板、32图、21楼；时间基于其中130个new同源完整面板、31图、21楼。它衡量整个分类方案把固定团队波动组织到配比之间的份额，**不是某一类的贡献，也不是加入该类会提高多少Q**。CSV按类重复这几个字段只是为关联方便。\n',
       md(methodtable,['method','METHOD_between_Q_share_percent','METHOD_between_logT_share_percent','METHOD_between_secondsT_share_percent'],{'method':'方法','METHOD_between_Q_share_percent':'Q配比间份额%','METHOD_between_logT_share_percent':'logT配比间份额%','METHOD_between_secondsT_share_percent':'秒数配比间份额%'})+'\n\n来源：[COMMON_COMPLETE_PANEL_METRICS.csv](../team_effects/COMMON_COMPLETE_PANEL_METRICS.csv)。同配比具体成员仍保留大量波动；K4更细分会影响份额，不能据此简单排名分类器。\n']
    for method in METHODS:
        z=matrix[matrix.method.eq(method)].copy()
        z['capacity']=z.primary_pool_capacity_median.map(lambda x:f'{x:g}')+' ('+z.primary_pool_capacity_min.astype(str)+'–'+z.primary_pool_capacity_max.astype(str)+')'
        z['T_display']=z.T_new_geometric_seconds_image_equal.map(lambda x:f'{x:.2f}')+' / '+z.T_new_images.astype(str)+'图'
        sections += [f'## {method}\n',f'分类依据：{FEATURES[method]}。直接使用Q/T：'+('是 / 是。历史Q/T分离属于建类依据，表中楼外原答用于检验其实际表现。' if method.startswith('OPP') else '否 / 否。RFUSE仍有质量可评性的间接训练支持条件；DSTRUCT具有参考匹配输入。')+'\n',
          md(z,['class_id','ALL_workers','capacity','Q_images','Q_image_equal','turn_image_equal','short_image_equal','boundary_deg_image_equal','T_display'],{'class_id':'楼外类编号','ALL_workers':'ALL描述人数','capacity':'每图容量中位(范围)','Q_images':'Q共同图','Q_image_equal':'原答Q','turn_image_equal':'转折','short_image_equal':'短墙','boundary_deg_image_equal':'边界误差°','T_display':'new几何T秒/独立支持'})+'\n',
          '原答来源：['+FILES['dstruct_profile' if method.startswith('TARGET') else 'other_profile'].split('/')[0]+'](../'+FILES['dstruct_profile' if method.startswith('TARGET') else 'other_profile']+')；人员和容量见本目录对应CSV。\n',
          '### ALL描述性名单\n']
        for row in z.itertuples():sections.append(f'- **{row.class_id}：{row.ALL_description.replace("ALL描述：", "")}，{row.ALL_workers}人。** '+row.ALL_members.replace('|','、')+'。\n')
        sections += ['\n上述描述不随意移植到LOBO；OPPJOINT编号按每折训练Q中心排列，TARGET/RFUSE分别按困难原答转折/困难融合转折响应中心排列。\n',
          '### 困难响应\n\n这里先给同一人员、同一建筑内困难−简单的类均值；每个人两种难度都必须有合法记录，再等权到建筑。各类支持楼不同，所以类间差值另使用相邻类共同楼，不能直接相减本表单类均值。\n',
          md(z,['class_id','same_person_Q_hard_minus_easy','same_person_Q_buildings','same_person_turn_hard_minus_easy','same_person_turn_buildings','same_person_short_hard_minus_easy'],{'class_id':'类','same_person_Q_hard_minus_easy':'同人Q困难−简单','same_person_Q_buildings':'Q楼','same_person_turn_hard_minus_easy':'同人转折困难−简单','same_person_turn_buildings':'转折楼','same_person_short_hard_minus_easy':'同人短墙困难−简单'})+'\n',
          md(z[z.class_id.ne('C1')],['class_id','adjacent_response_reference_class','adjacent_response_turn_difference','adjacent_response_turn_buildings','adjacent_response_turn_positive_buildings','adjacent_response_Q_difference','adjacent_response_Q_buildings'],{'class_id':'B类','adjacent_response_reference_class':'A类','adjacent_response_turn_difference':'B−A转折响应差','adjacent_response_turn_buildings':'共同楼','adjacent_response_turn_positive_buildings':'转折正向楼','adjacent_response_Q_difference':'B−A Q响应差','adjacent_response_Q_buildings':'Q共同楼'})+'\n\n完整困难分层Q/转折/短墙均值与独立图数、同人楼数均已保留在总矩阵。\n',
          '### 与这些类别有关的实际团队方向\n']
        ev=directions[directions.method.eq(method)].copy()
        sections.append(md(ev,['evidence_id','classes_involved','design','quantity','effect','images','positive','negative'],{'evidence_id':'证据ID','classes_involved':'涉及类','design':'条件','quantity':'量','effect':'值','images':'图','positive':'正图','negative':'负图'})+'\n')
        sections.append('逐条源路径、版本、过滤条件见[CLASS_TEAM_DIRECTION_LINKS.csv](CLASS_TEAM_DIRECTION_LINKS.csv)。完整联盟的“more people”包含人数增加；纯类绝对Q使用不同图片和人数，只是该类可用全员的描述，不作组间因果差。严格ABC的gap说明额外变化幅度，CB/AC才另列方向。\n')
    sections += ['## 输入、版本与复现\n\n原答、标签、团队三层各自保留实际支持与版本。没有把ALL成员当作每折永久人员，也没有把方法层方差解释为单类效果。方向性证据包括当前DSTRUCT辅助扩展合法子集、RFUSE/JOINT标签已验一致的冻结AC、JOINT冻结自动ABC与明确人数变化的完整联盟。完整方法关系与限制见[合同](README_ZH.md)、[原答报告](../rfuse_joint/REPORT_ZH.md)和[团队报告](../team_effects/REPORT_ZH.md)。\n\n运行：\n\n```bash\npython research/workers/current_class_interpretation_20261104/basis/build_class_original_team_matrix.py\n```\n\n输入散列与依赖路径见[CLASS_MATRIX_INPUT_MANIFEST.csv](CLASS_MATRIX_INPUT_MANIFEST.csv)。此脚本只接续已完成表格，新增原答评分、团队、融合、分类拟合均为0。\n']
    (OUT/'CLASS_ORIGINAL_TEAM_TABLES.md').write_text('\n'.join(sections),encoding='utf-8')
    manifest=[]
    for key,path in FILES.items():
        b=(BASE/path).read_bytes();manifest.append(dict(role=key,path=str((BASE/path).relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),source_type='derived_from_frozen_48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'))
    save(pd.DataFrame(manifest),'CLASS_MATRIX_INPUT_MANIFEST.csv')
    checks=dict(class_rows=len(matrix),methods=METHODS,directional_rows=len(directions),Q_common_images=matrix.groupby('method').Q_images.first().to_dict(),T_new_common_images=matrix.groupby('method').T_new_images.first().to_dict(),method_variance_not_class_attributed=True,ALL_members_descriptive_only=True,metric_specific_support=True,new_scoring=0,new_fusion=0,new_classification_fit=0)
    (OUT/'CLASS_MATRIX_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
