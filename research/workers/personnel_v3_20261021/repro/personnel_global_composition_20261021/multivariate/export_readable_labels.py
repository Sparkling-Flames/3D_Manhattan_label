#!/usr/bin/env python3
"""Readable Chinese class definitions, member inventory and research-table fields."""
import gzip
import json
import numpy as np
import pandas as pd
from build_multivariate import HERE,REPO,SOURCE,INDEX,DOMAIN_ORDER,DOMAINS,js,sha

NAMES={
 'MV_QTD_manual':{
  'QH':('质量基准以上组','任务调整后的自身 Manual Q 效应 >=0；是当前合格样本内的质量父层，不等于结构风格。'),
  'QL':('质量基准以下组','任务调整后的自身 Manual Q 效应 <0；并不表示所有作答都差或融合贡献低。'),
  'QH.1':('较高Q·相对快、困难相对回落','较高Q父层内，时间效应较低、时间尾较短；困难相对简单的质量效应更低。'),
  'QH.2':('较高Q·相对慢、困难相对保持','较高Q父层内，时间效应较高，困难相对简单的质量效应较高；成员来源有明显偏倚。'),
  'QL.1':('较低Q·时间长尾、中等图相对回落','较低Q父层内，速度平均偏快但时间残差长尾明显，中等图相对简单图回落；10人中9人为旧来源。'),
  'QL.2':('较低Q·时间尾较短、难度效应较平','较低Q父层内，时间尾较短，中等和困难相对简单的效应较平；混合来源的辅助分层。'),
 },
 'MV_QTD_manual_new':{
  'QH':('较高Q·不作细分','新批中自身 Manual Q 效应>=0的15人；T/D子分割出现小于4人的分支，依预定规则不采用细分。'),
  'QL':('质量基准以下组','新批中自身 Manual Q 效应<0的20人；再按T/D分为有容量的两个细类。'),
  'QL.1':('较低Q·快、中等图相对占优','11人，训练T效应较低，中等相对简单Q效应较高；楼外速度差22/22建筑同向。相对慢类的Q优势在中等图更明显，不把训练困难适应解释为已验证的困难−简单优势。'),
  'QL.2':('较低Q·较慢、中等图相对回落','9人，训练T效应较高，中等相对简单Q效应较低；楼外慢−快Q差在中等−4.291、简单−0.903、困难−0.843，困难−简单相对优势未清楚重现。'),
 },
 'MV_QTScopeSemi_semi_new':{
  'QH':('Semi质量基准以上组','自身 Semi 终稿Q效应>=0；Q与Manual分别估计，不借Manual类别充当Semi类别。'),
  'QL':('Semi质量基准以下组','自身 Semi 终稿Q效应<0；仅对应当前终稿质量父层。'),
  'QH.1':('较高Semi Q·快、较少报告编辑','4人，速度较快、out_of_scope回答倾向较高、报告编辑较少；错误机会未改效应相对较高。'),
  'QH.2':('较高Semi Q·较慢、更常报告编辑','10人，速度较慢、报告编辑较多、报告错误机会下未改较少；不等于已证实修对。'),
  'QL.1':('较低Semi Q·报告编辑较多、未改较少','17人，相对另一低Q细类更常报告编辑、out_of_scope倾向较低，报告错误机会下未改较少。'),
  'QL.2':('较低Semi Q·少报编辑、错误未改较多','4人，报告编辑较少、报告错误机会下未改较多、时间尾较长；缺精确初始化，不能解释为盲信或具体编辑轨迹。'),
 },
 'MV_TDScopeSemi_manual_new':{
  'C1':('较快·少报编辑、未改较多倾向','新Manual的T/D/scope与跨条件Semi行为共同形成的25人组；未输入Q。跨楼成员不稳定，仅保留探索。'),
  'C2':('较慢·多报编辑、未改较少倾向','10人，Manual更慢、out_of_scope回答倾向较高、Semi报告编辑较多且错误未改较少。跨楼成员不稳定。'),
  'C1.1':('快组内·困难回落、范围内回答较多','7人；困难相对简单回落更大，out_of_scope倾向更低，报告错误未改较少。'),
  'C1.2':('快组内·少报编辑、错误未改较多','18人；跨条件Semi报告编辑较少、错误机会未改较多。'),
  'C2.1':('慢组内·编辑报告积极分支','4人；相对同父类另支Manual较快，Semi报告编辑效应最高、错误未改效应最低。此名称描述记录，不推断心理动机。'),
  'C2.2':('慢组内·耗时较高分支','6人；Manual相对时间更高；报告编辑与错误未改处于父类中的另一水平。'),
 },
}
ROLES={
 'MV_QTD_manual':'跨来源辅助；细类明显关联来源，主要使用同新批敏感性检查判断增量',
 'MV_QTD_manual_new':'采用为新Manual条件工作分类；稳定速度差及中等图差可解释，未提供连续QT外的Q预测改善；团队用途以实测为准',
 'MV_QTScopeSemi_semi_new':'采用为新Semi描述性行为工作分类；11楼Q预测未优于source基线，不作为跨楼质量预测工具；团队用途以实测为准',
 'MV_TDScopeSemi_manual_new':'不推荐为稳定人员身份；保留无Q四域探索/负结果及实际构成对照',
}

def missing_zh(s):
    if not isinstance(s,str) or not s:return ''
    names={'outside_declared_new_source_population':'不在本方法声明的新批适用人群',
           'insufficient_Q_opportunity':'自身条件合格Q任务/建筑机会不足',
           'insufficient_T_opportunity':'自身条件同来源有效时间任务/建筑机会不足',
           'insufficient_D_opportunity':'自身条件简单/中等/困难机会未同时达标',
           'insufficient_scope_opportunity':'自身条件scope回答量或同任务分歧机会不足',
           'insufficient_Semi_opportunity':'Semi编辑或错误机会未改行为支持不足',
           'no_observed_semi_record':'没有非OOS Semi作答，无法形成自身Semi类别',
           'joint_supported_population_lt8':'联合支持人数不足8，未拟合'}
    return '；'.join(names.get(x,x) for x in s.split('|'))

def main():
    f=pd.read_csv(HERE/'continuous_features_lobo.csv.gz');labels=pd.read_csv(HERE/'candidate_labels.csv')
    labels=pd.concat([labels,pd.read_csv(HERE/'same_source_candidate_labels.csv')],ignore_index=True)
    idx=pd.read_csv(INDEX);records=json.load(gzip.open(SOURCE,'rt'))['records'];valid=set(idx.object_id)
    historical=pd.DataFrame([{'object_id':r['object_id'],'historical_worker_exclusion':bool((r.get('exclusion_attribution') or {}).get('historical_worker_exclusion')),
                             'specific_person_error_candidate':bool((r.get('exclusion_attribution') or {}).get('specific_person_error_candidate')),
                             'legacy_explicit_person_error':bool((r.get('exclusion_attribution') or {}).get('legacy_explicit_person_error'))} for r in records if r['object_id'] in valid])
    inventory=idx.merge(historical,on='object_id',validate='one_to_one')
    inv=[]
    for (w,c),g in inventory.groupby(['worker_id','condition']):
        a=g[g.panel.eq('ordinary')];gate=a.quality_usable&a.quality_use.eq('ordinary_primary')
        inv.append(dict(worker_id=w,condition=c,nonOOS_records=len(g),nonOOS_images=g.image_id.nunique(),nonOOS_buildings=g.building_id.nunique(),
                        ordinary_inventory_records=len(a),doorway_inventory_records=int(g.panel.eq('doorway').sum()),
                        ordinary_quality_eligible_records=int(gate.sum()),ordinary_pool_eligible_records=int(a.pool_analysis_eligible.sum()),
                        ordinary_independent_vote_eligible_records=int(a.independent_vote_eligible.sum()),
                        special_quality_records=int(a.quality_use.eq('special_conditional_only').sum()),
                        quality_excluded_ordinary_records=int((~gate).sum()),
                        historical_worker_exclusion_records=int(g.historical_worker_exclusion.sum()),
                        specific_person_error_candidate_records=int(g.specific_person_error_candidate.sum()),
                        legacy_explicit_person_error_records=int(g.legacy_explicit_person_error.sum()),
                        cleaning_dispositions=json.dumps(g.cleaning_disposition.value_counts().to_dict(),ensure_ascii=False),
                        formal_team_eligibility_rule='每图每作答沿用frozen pool_analysis_eligible和independent_vote_eligible；标签不授予资格'))
    inv=pd.DataFrame(inv);inv.to_csv(HERE/'worker_condition_inventory.csv',index=False)
    workers=sorted(idx.worker_id.unique());full=labels[labels.heldout_building.eq('ALL')].copy()
    # Explicit missing-condition row: W022 has Manual inventory but no Semi answer.
    for method,g in full.groupby('method_id'):
        c=g.condition.iloc[0]
        for w in sorted(set(workers)-set(g.worker_id)):
            row={col:np.nan for col in full.columns};row.update(method_id=method,condition=c,heldout_building='ALL',worker_id=w,known=False,
                coarse_class='unknown',fine_class='unknown',support='unknown',missing_reason='no_observed_'+c+'_record',domains=g.domains.iloc[0],label_status='final_all_data_exploratory')
            full=pd.concat([full,pd.DataFrame([row])],ignore_index=True)
    full=full.merge(f[f.heldout_building.eq('ALL')],on=['worker_id','condition','heldout_building'],how='left',suffixes=('','_feature'),validate='many_to_one')
    full=full.merge(inv,on=['worker_id','condition'],how='left',validate='many_to_one')
    full['coarse_name_zh']=[NAMES[m].get(c,('证据不足/适用人群之外',''))[0] for m,c in zip(full.method_id,full.coarse_class)]
    full['fine_name_zh']=[NAMES[m].get(c,('证据不足/适用人群之外',''))[0] for m,c in zip(full.method_id,full.fine_class)]
    full['fine_explanation_zh']=[NAMES[m].get(c,('',''))[1] for m,c in zip(full.method_id,full.fine_class)]
    full['missing_reason_zh']=full.missing_reason.map(missing_zh);full['research_role']=full.method_id.map(ROLES)
    full['class_name_scope']='仅全数据最终标签的中文解释；目标楼外类别以训练侧成员和均值解释，不把全数据名字当训练输入'
    first=['method_id','condition','worker_id','known','coarse_class','coarse_name_zh','fine_class','fine_name_zh','fine_explanation_zh','research_role','missing_reason','missing_reason_zh']
    full=full[first+[c for c in full if c not in first]].sort_values(['method_id','worker_id'])
    full.to_csv(HERE/'personnel_labels_readable.csv',index=False,encoding='utf-8-sig')
    # Readable class summary includes explicit source composition and member lists.
    cc=pd.concat([pd.read_csv(HERE/'class_members_and_features.csv'),pd.read_csv(HERE/'same_source_class_members.csv')],ignore_index=True)
    cc['name_zh']=[NAMES[m][c][0] for m,c in zip(cc.method_id,cc.class_id)];cc['explanation_zh']=[NAMES[m][c][1] for m,c in zip(cc.method_id,cc.class_id)]
    cc['research_role']=cc.method_id.map(ROLES)
    cc.to_csv(HERE/'class_explanations_zh.csv',index=False,encoding='utf-8-sig')
    # Every fold gets its own training-side class centroid; no target interpretation leakage.
    joined=labels[labels.known&~labels.heldout_building.eq('ALL')].merge(f,on=['worker_id','condition','heldout_building'],suffixes=('','_feature'),validate='many_to_one')
    folds=[]
    for (method,b,level),g in (( (m,b,l),gg ) for (m,b),gg in joined.groupby(['method_id','heldout_building']) for l in ('coarse_class','fine_class')):
        for c,h in g.groupby(level):
            row={'method_id':method,'condition':h.condition.iloc[0],'heldout_building':b,'level':level,'class_id':c,'members_n':len(h),'members':'|'.join(sorted(h.worker_id)),
                 'origins':json.dumps(h.origin.value_counts().to_dict()),'label_uses_target_building':False}
            for feature in list(dict.fromkeys(sum(DOMAINS.values(),[]))):row[feature+'_mean']=h[feature].mean()
            folds.append(row)
    pd.DataFrame(folds).to_csv(HERE/'training_class_centroids_lobo.csv.gz',index=False)
    # Small alias in the schema requested by root's canonical expression script.
    sens=labels[labels.method_id.eq('MV_QTD_manual_new')&~labels.heldout_building.eq('ALL')]
    sens.to_csv(HERE/'labels_lobo_new_source_sensitivity.csv.gz',index=False)
    js(HERE/'FIELD_SCHEMA.json',{
      'primary_tables':{'personnel_labels_readable.csv':'248行：4种方法×62人；Manual3法、Semi1法；非统一层级。W022的Semi显式未知。',
                        'class_explanations_zh.csv':'各方法粗/细类中文名、解释、实际成员、域均值、来源组成。',
                        'labels_lobo.csv.gz':'原3候选22楼外机器接口。','same_source_candidate_labels.csv':'同新批QTD敏感性候选，含ALL及22楼外。',
                        'continuous_features_lobo.csv.gz':'条件×楼外折×人员：每域连续特征、支持、机会量及时间来源/秒单位。',
                        'training_class_centroids_lobo.csv.gz':'每个外楼训练侧各类真实成员及域均值，供目标机制解释。',
                        'domain_subset_26_coverage.csv':'Manual/Semi各26子集，单固定Ward2机会/稳定性筛查，不等于构成实验。'},
      'join_keys':['method_id','condition','heldout_building','worker_id'],
      'all_data_key':'heldout_building=ALL仅作最终研究标签；目标图/建筑结果必须使用其building_id对应楼外行。',
      'class_columns':{'coarse_class':'父层类别ID；QH/QL是同条件任务调整Q效应正负，C1/C2是训练侧无Q等权Ward2。','fine_class':'父层+小数编号；无合格细分时等于父层，不是缺失。','known':'是否满足该方法全部域与人群支持。','missing_reason':'逐域机会不足或人群之外；不可作0或恢复组队资格。'},
      'gates':{'Q_manual':'8个任务且3建筑，ordinary_primary且quality_usable；Q_semi=4任务且3建筑。','T':'6任务且3建筑，pool_analysis_eligible且ordinary_difficulty_eligible，正源活动秒；按origin/time_source_kind单独估计。','D':'简单、中等、困难每档均6任务且3建筑；否则D未知，即使部分池化给出数字也不采用。','scope':'10个自身条件非OOS普通图回答任务、3建筑、至少2个有人员回答分歧的任务；ridge5任务效应。','Semi':'编辑6任务3建筑；错误机会未改3任务2建筑；二者均足；旧精确初始化与新报告层级不混。'},
      'domain_features':DOMAINS,
      'weights':'单域内特征平均平方距离，域间等权；训练人群IQR缩放并clip[-3,3]。层级Q父层只用Q效应；子层各进入域等权。',
      'scope_correctness':'全数据普通非OOS有裁定机会Manual25、Semi68，均报告为正确且无差异；不拿正确率强行分型。scope_out_effect仅回答倾向。',
      'Semi_interpretation':'新批525条均无精确初始化，edited/error_nonedit来自用户处理报告；未改/编辑不是心理动机或纠错成功。Manual的Semi域是跨条件辅助。',
      'inventory_qualification':'行为可用已筛除或GT暂停记录；Q仍资格限定。标签不修改原图/原标注/环序/GT/参考绑定/评分/融合/人员池资格。门洞库存单列，不把普通类别门洞表现当独立类别验证。',
      'source_main':'51b519f943b2dd3a4fb2f0198133ac5dd17209ab',
      'selection_status':'全库存已反复探索；楼外重拟合是真实样本外建筑检查，不称新盲测。新增同来源敏感性在看到来源关联后追加，仍在融合结果前冻结。'})
    js(HERE/'READABLE_LABELS_RECEIPT.json',{'rows':len(full),'workers':len(workers),'method_counts':full.groupby('method_id').known.agg(['sum','count']).to_dict(),
         'outputs_sha256':{n:sha(HERE/n) for n in ['personnel_labels_readable.csv','class_explanations_zh.csv','worker_condition_inventory.csv','FIELD_SCHEMA.json']},
         'original_label_hash_unchanged':sha(HERE/'candidate_labels.csv')==json.loads((HERE/'FREEZE.json').read_text())['label_sha256']})
    print('Readable labels',len(full),'class rows',len(cc),'inventory rows',len(inv))

if __name__=='__main__':main()
