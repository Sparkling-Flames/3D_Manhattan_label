"""Numeric replies to the 16 preserved comments; never new visual adjudication."""
from __future__ import annotations
import itertools,collections,json
import numpy as np,pandas as pd
from common import *

COMMENTS=[
'原文说明的是同一隐藏墙角的作答意图及明显位置漂移，不能据此自动补齐跨人员对应。所给W002 bottom连接序列属于单份作答内墙体连接顺序，不直接替代跨人员点位映射。当前数值对应可计算，但“唯一最优横向绑定”不等于物理对应已确认。保持暂缓；需核对W001/W002/W033这一局部的完整上下对应。',
'不是多个点偏差累加：当前距离取所有端点中的最大值。更直接的障碍是W012的数值上下绑定仍有并列最优解，不能把角色分开视图中的可比较，直接升级为唯一绑定可计算。本项给出角色分开固定顺序的残差，但不擅自选择一组绑定。原文“配对是对的”保留；仍需把所指审核候选明确绑定到原点号后才可机器应用。',
'文字已指出W027/W029试图标同一被完全遮挡的位置，但位置差不为零；这与W031遗漏该处不是同一种观测。当前严格整份表达仍受有效点数硬门约束。没有完整人工跨人映射时只报告固定/循环/自由诊断，不以自由匹配更小自动纠正。保持暂缓。',
'该例不能仅凭“想标同一点”把实际坐标差清零。应分别记录意图解释、对应和定位残差；是否把这种残差容许在同组内仍由用户裁决。本轮保留原点与原暂缓状态。',
'W008存在上下绑定歧义；仅给出W008 p8与W006 p11的局部文字关联，尚不能授权完整整份绑定。采用角色分开诊断而不是把不可计算填成零、单人簇或不存在。保持暂缓。',
'原文指定了W032 p12点对与W033 p6，应核对该局部的上下点号及整份跨人对应；当前两个端点最大差异不由平均值掩盖。保持暂缓，数值超阈值不自动推翻遮挡解释。',
'两份指定作答本身近；完整链接拆分需查看所属两组中的其他成员，不能用两份之间的距离解释整组关系。代表半径可以保留它们在一组，但同时必须检查代表组内最远成员。原文对“簇1与簇2”的更广泛意见仍绑定旧审核版本，不能仅用指定对符合就称两整个旧簇已通过。',
'原文已接受p6 bottom略有偏差。最大端点指标会保留这个偏差，但当前探针下指定对仍相近；完整链接的分开主要需解释整簇跨成员约束，而不是再把这两份判成不相近。',
'指定对相近已确认；无文字理由不补造视觉解释。距离改变可能改变其他成员的合并顺序，因此图上完整链接是否合在一起不能简化成“所有距离都更小”。完整组成员同时输出。',
'OOS只是研究条件，不把该处top差异删除。W018在旧组中的归属不能作为W028/W032必同组或必异组的推理依据；本轮列出三人各自逐端点差异及所在整组。原关系空白且暂缓，保持未决。',
'用户明确要求保留W031/W032差异，即使二者都不正确。球面与平面距离对此指定对的结论可不同，原因是投影测量而非错误更正。原“簇3为何单拎”另按旧成员身份回接新方法，不能把新簇号3误当旧簇3。',
'原关系虽填“应分开”，但defer=true优先，本项仍未裁决。后续澄清为W017 p10与W018 p6，不覆盖旧文字的W008。一个局部端点是否足以形成独立整份表达组，不能由点的数量少直接否定；应结合该端点差和整组约束判断。',
'已确认相近，原文字空白；保留该指定对作为开发约束，不推断全图或整个当前簇都已验收。',
'已确认相近，原文字空白；报告数值和当前整簇范围，不额外制造视觉理由。',
'已确认相近，原文字空白；维持已有判断，同时保留整组内端点极值与成员检查。',
'已确认相近，原文字空白；当前一致仅属于开发案例符合，不能称独立验证准确率。'
]

def main():
    raw,by,rec,elig,approved=records();groups=load_groups()
    cases=source_json('evidence/review_manifest_16.json')['cases'];answers=source_json('evidence/user_review_16.json')['decisions'];latest=source_json('evidence/latest_decisions.json')
    comparisons=[];blockers=[];members=[];endpoints=[];output=[];relation_checks=[]
    def analyze(c,index,decision):
        key=c['key'];g=groups.get(key);a=c['id_a'];b=c['id_b'];available=g is not None and a in g['ids'] and b in g['ids'];meta=dict(case=index,key=key,code=c['code'],condition=c['condition'],id_a=a,id_b=b,worker_a=c['worker_a'],worker_b=c['worker_b'])
        row=dict(**meta,original_answer=decision,numeric_reply=COMMENTS[index-1] if index<=16 else '完整人工对应和相近判断已经确认，不再询问。映射变化不强制合并所属整簇。',specified_pair_bound_available=available,raw_source='evidence/user_review_16.json; evidence/latest_decisions.json',new_visual_review=False)
        row['all_record_coverage']=[dict(id=x,worker=by[x]['worker_id'],raw_count=by[x]['raw_point_count'],effective_count=by[x]['effective_point_count'],processing=by[x]['processing_status'],bound_available=x in rec and rec[x]['links'] is not None) for x in c.get('ids',g['ids'] if g else []) if x in by]
        # Original cluster 3 is version-bound and is not current label 3.
        oldlabels=c.get('labels',{}).get('split_cyclic_9',[])
        row['old_cluster3_ids']=[x for x,l in zip(c.get('ids',[]),oldlabels) if str(l)=='3']
        if available:
            ia=g['ids'].index(a);ib=g['ids'].index(b)
            for view,mm in g['matrices'].items():
                for metric,d in mm.items():
                    D=np.asarray(d);dist=float(D[ia,ib])
                    for t0 in CUTS:
                        t=nominal_cut(metric,t0)
                        for kind in ['complete','representative']:
                            method=f'{view}:{metric}:{kind}:{t0:g}';l=np.array(g['labels'][method]);reps=g['representatives'][method]
                            same=bool(l[ia]==l[ib]);comparisons.append(dict(**meta,view=view,metric=metric,partition=kind,nominal_cut=t0,actual_cut=t,distance=dist,within_tolerance=round(dist,8)<=t,same_cluster=same,cluster_a=int(l[ia]),cluster_b=int(l[ib])))
                            if index<=16 and not decision['defer'] and decision['relation'] in ['可视为相近','应分开保留差异']:
                                relation_checks.append(dict(case=index,view=view,metric=metric,partition=kind,nominal_cut=t0,user_relation=decision['relation'],partition_matches_specified_pair=(same==(decision['relation']=='可视为相近')),development_not_accuracy=True))
                            if kind=='complete' and not same:
                                A=np.flatnonzero(l==l[ia]);B=np.flatnonzero(l==l[ib])
                                for i in A:
                                    for j in B:
                                        if round(D[i,j],8)>t:
                                            blockers.append(dict(**meta,view=view,metric=metric,nominal_cut=t0,actual_cut=t,specified_pair_is_near=round(dist,8)<=t,blocker_a=g['ids'][i],blocker_b=g['ids'][j],worker_blocker_a=g['workers'][i],worker_blocker_b=g['workers'][j],distance=float(D[i,j]),kind='final_cluster_incompatibility_witness_not_unique_causal_merge_history'))
                            # All clusters, not only the two specified clusters.
                            for i,cid in enumerate(g['ids']):
                                cc=int(l[i]);rid=reps[cc-1];ri=g['ids'].index(rid);z=np.flatnonzero(l==cc);far=z[np.argmax(D[i,z])]
                                fits=[x for x in reps if round(D[i,g['ids'].index(x)],8)<=t]
                                members.append(dict(case=index,code=c['code'],key=key,view=view,metric=metric,partition=kind,nominal_cut=t0,id=cid,worker=g['workers'][i],cluster=cc,cluster_size=len(z),representative_id=rid,distance_to_representative=float(D[i,ri]),farthest_member=g['ids'][far],farthest_worker=g['workers'][far],distance_to_farthest=float(D[i,far]),compatible_representative_ids='|'.join(fits),effective_count=by[cid]['effective_point_count'],borrowed_imputation=bool(by[cid].get('imputed_point',False))))
            # Per-endpoint diagnostic includes latest confirmed map only for uNb.
            A=rec[a];B=rec[b]
            for view in ['automatic','human_correspondence']:
                mapping=np.arange(len(A['links']))
                for h in latest['confirmed_correspondences']:
                    if (a,b)==(h['id_a'],h['id_b']) and view=='human_correspondence':mapping=np.array(h['pair_order_b_1based'])-1
                for rname,role in [('top',0),('bottom',1)]:
                    aa=A['links'][:,role];bb=B['links'][mapping,role]
                    S=angle_matrix(A['p'][aa],B['p'][bb]);P=image_matrix(A['p'][aa],B['p'][bb])
                    for j,(i,k) in enumerate(zip(aa,bb)):
                        endpoints.append(dict(**meta,view=view,role=rname,pair_a=j+1,pair_b=int(mapping[j])+1,original_point_a=int(i)+1,original_point_b=int(k)+1,ax=float(A['p'][i,0]),ay=float(A['p'][i,1]),bx=float(B['p'][k,0]),by=float(B['p'][k,1]),sphere_deg=float(S[j,j]),image_px=float(P[j,j])))
        else:
            row['coverage_note']='指定对不具有唯一绑定；保留角色分开诊断，不填零距离，不新造单人簇。'
            A=rec.get(a);B=rec.get(b)
            if A and B:
                for role,field in [('top','up'),('bottom','dn')]:
                    aa=A[field];bb=B[field]
                    if len(aa)!=len(bb):continue
                    S=angle_matrix(A['p'][aa],B['p'][bb]);P=image_matrix(A['p'][aa],B['p'][bb])
                    for j,(i,k) in enumerate(zip(aa,bb)):
                        endpoints.append(dict(**meta,view='role_split_fixed_diagnostic_not_bound',role=role,pair_a=j+1,pair_b=j+1,original_point_a=int(i)+1,original_point_b=int(k)+1,ax=float(A['p'][i,0]),ay=float(A['p'][i,1]),bx=float(B['p'][k,0]),by=float(B['p'][k,1]),sphere_deg=float(S[j,j]),image_px=float(P[j,j])))
        return row
    for i,c in enumerate(cases,1):output.append(analyze(c,i,answers[c['key']]))
    h=latest['confirmed_correspondences'][0];g=next(g for g in groups.values() if h['id_a'] in g['ids'])
    c=dict(key=g['key'],code=g['code'],condition=g['condition'],id_a=h['id_a'],id_b=h['id_b'],worker_a=h['worker_a'],worker_b=h['worker_b'],ids=g['ids'])
    output.append(analyze(c,17,dict(relation='可视为相近',defer=False,comment='后续完整对应确认；原点不改；不设统一容差。')))
    comp=save('review/specifed_pair_method_comparisons.csv',comparisons);bl=save('review/complete_link_blocking_members.csv.gz',blockers);me=save('review/all_case_members_and_representatives.csv.gz',members);ep=save('review/specified_endpoint_residuals.csv',endpoints)
    save('review/development_pair_constraints.csv',relation_checks);rc=pd.DataFrame(relation_checks)
    summary=rc.groupby(['view','metric','partition','nominal_cut']).agg(decided_specified_pairs=('case','size'),matched=('partition_matches_specified_pair','sum')).reset_index();save('review/development_constraint_summary.csv',summary)
    dump('review/comment_replies_16_plus_unb.json',output)
    # All comparisons involving the explicitly named third-party workers in comments.
    extra=[]
    for c in cases:
        targets={'b8cTxDM8gDG-19':['W018','W028','W032'],'b8cTxDM8gDG-17':['W027','W029','W031'],'7y3sRwLe3Va-21':['W001','W002','W033']}.get(c['code'])
        if not targets:continue
        g=groups.get(c['key'])
        for i,j in itertools.combinations(range(len(g['ids'])),2):
            if g['workers'][i] not in targets or g['workers'][j] not in targets:continue
            extra.append(dict(code=c['code'],worker_a=g['workers'][i],worker_b=g['workers'][j],id_a=g['ids'][i],id_b=g['ids'][j],count_a=by[g['ids'][i]]['effective_point_count'],count_b=by[g['ids'][j]]['effective_point_count'],sphere_distance=g['matrices']['automatic']['sphere'][i][j],image_distance=g['matrices']['automatic']['image'][i][j],pointcount_gate=g['matrices']['automatic']['sphere'][i][j]>=BLOCK))
    save('review/comment_additional_named_workers.csv',extra)
    # Human pair-specific correspondences need not define a metric globally.
    triangles=[]
    for view in ['automatic','human_correspondence']:
        for g in groups.values():
            for m,d0 in g['matrices'][view].items():
                d=np.asarray(d0);n=len(d)
                for i,j,k in itertools.combinations(range(n),3):
                    ds=[d[i,j],d[i,k],d[j,k]]
                    if max(ds)>=BLOCK:continue
                    for a,b,c in [(i,j,k),(i,k,j),(j,k,i)]:
                        if d[a,b]>d[a,c]+d[c,b]+1e-8:triangles.append(dict(code=g['code'],condition=g['condition'],view=view,metric=m,id_a=g['ids'][a],id_b=g['ids'][b],via=g['ids'][c],worker_a=g['workers'][a],worker_b=g['workers'][b],worker_via=g['workers'][c],direct=d[a,b],via_sum=d[a,c]+d[c,b],excess=d[a,b]-d[a,c]-d[c,b]))
    save('review/triangle_violations_pair_override.csv',triangles)
    # Minimal local queue: retain all 8 deferrals, plus known contrary whole-group
    # constraints and the previously documented equal-linkage-tie case.
    queue=[]
    for i,c in enumerate(cases,1):
        dec=answers[c['key']]
        if dec['defer'] or i in (7,8,9,11):queue.append(dict(case=i,code=c['code'],condition=c['condition'],id_a=c['id_a'],id_b=c['id_b'],workers=c['worker_a']+'|'+c['worker_b'],reason='original_defer' if dec['defer'] else 'method_conflict_or_whole_group_check',request=COMMENTS[i-1],user_decision=None,ordinary_control=False))
    queue.append(dict(case=None,code='yqstnuAEVhm-26',condition='manual',id_a=None,id_b=None,workers=None,reason='already_documented_equal_distance_merge_ties',request='比较已有并列合并选择下改变的完整成员，不把canonical固定顺序视为语义唯一分区。',user_decision=None,ordinary_control=False))
    queue.append(dict(case=None,code='rPc6DW4iMge-15',condition='manual',id_a='1318278d00548b081ebc',id_b='2d83aaed5161b7904cdd',workers='W030|W013|W006|W017',reason='new_numeric_equal_distance_tie_alternative',request='图上完整链接25.6px并列合并可改变45对同簇关系，涉及18名成员；查看diagnostics/equal_distance_partition_variants.json的两套完整成员。不是新增普通对照或视觉裁决。',user_decision=None,ordinary_control=False))
    queue.append(dict(case=17,code='uNb9QFRL6hY-21',condition='manual',id_a='74051761f655b31b',id_b='a4e0cac5adec2e1e',workers='W017|W013',reason='pair_specific_override_inconsistent_with_other_member',request='不重问W006/W013已确认关系；只核对其与W017等其他成员的对应与整组关系。数值上W017与W006固定表示相同，但对W013的距离因只替换一对而不同；不自动传播裁决。',user_decision=None,ordinary_control=False))
    dump('review/local_review_queue.json',queue)
    # Human-readable, traceable answers.
    lines=['# 16项原始comment逐条数值答复\n','本报告只核对文字来源与数值，不新增视觉裁决。下列距离为当前同一有效点集；9°/25.6px仅为既有中间探针。全部成员、其他阈值、逐端点和阻挡明细在同目录CSV/JSON。\n']
    for r in output:
        i=r['case'];d=r['original_answer'];lines += [f"## {i}. {r['code']} / {r['condition']}：{r['worker_a']}—{r['worker_b']}\n",f"状态：{'暂缓，未裁决' if d['defer'] else d['relation']}。\n",'原文：\n> '+d['comment'].replace('\n','\n> ')+'\n',r['numeric_reply']+'\n']
        z=comp[(comp['case']==i)&(comp.nominal_cut==9)]
        if not len(z):lines.append(r.get('coverage_note','不可计算')+'\n')
        else:
            lines += ['|视图|距离|分组|残差|同组|\n|---|---|---|---:|---|']
            for x in z.itertuples():lines.append(f'|{x.view}|{x.metric}|{x.partition}|{x.distance:.6f}|{"是" if x.same_cluster else "否"}|')
            bz=bl[(bl['case']==i)&(bl.nominal_cut==9)&bl.specified_pair_is_near]
            if len(bz):
                lines.append('\n完整链接最终两组的超阈值阻挡成员示例（不是对唯一历史合并路径的宣称）：')
                for _,zz in bz.groupby(['view','metric']):
                    x=zz.sort_values('distance',ascending=False).iloc[0];lines.append(f"{x['view']} / {x['metric']}：{x.worker_blocker_a}({x.blocker_a}) 对 {x.worker_blocker_b}({x.blocker_b}) = {x.distance:.6f}；共有{len(zz)}个超阈值跨组对。")
        if r['old_cluster3_ids']:lines.append('\n旧审核簇3的身份：'+', '.join(r['old_cluster3_ids'])+'。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。')
    lines+=['\n## 开发约束与验收范围\n','8项已决定的指定对并非独立测试集，也不等于8张图的所有组通过。完整图级范围214图/239单元仍待本地逐图验收。', '\n人工只替换某一作答对的对应后，全表可能不再满足三角不等式；本轮显式检查并输出违反项。不能再无条件用“直径≤2倍半径”的度量空间性质解释该后见视图。']
    (OUT/'review/COMMENT_REPLIES_ZH.md').write_text('\n'.join(lines),encoding='utf-8')
    dump('REVIEW_AUDIT.json',dict(original_comments=len(cases),deferred=sum(d['defer'] for d in answers.values()),decided=sum(not d['defer'] for d in answers.values()),new_visual_decisions=0,unb_not_reasked=True,triangle_violations=len(triangles),local_queue_size=len(queue),all_history_visual_acceptance_completed=False))
    print(summary.to_string(index=False),flush=True)
if __name__=='__main__':main()
