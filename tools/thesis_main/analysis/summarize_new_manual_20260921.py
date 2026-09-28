"""汇总新版分簇、留图比较与同人员控制；不推断最终停止人数。"""
import collections
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.analyze_new_manual_20260921 import ROOT,OUT,read,dump
from tools.thesis_main.analysis.clustering_release.pipeline import rows_at
from tools.thesis_main.analysis.clustering_numeric_research.common import next_uncovered
from tools.thesis_main.analysis.audit_collection_plan_20260921 import blocks


def local(name):return json.loads((OUT/name).read_text(encoding='utf8'))


def aggregate_transfer():
    data=pd.DataFrame(local('transfer.json'));stats=[]
    for key,all_rows in data.groupby(['pool','metric','cut','k']):
        for scope in ['all','new_affected_targets']:
            g=all_rows if scope=='all' else all_rows[all_rows.new_target]
            if g.empty:continue
            g=g.copy();g['room_error']=abs(g.target_value-g.same_room_prediction);g['baseline_error']=abs(g.target_value-g.external_baseline)
            means=g.groupby(['building','family'])[['room_error','baseline_error']].mean().groupby('building').mean()
            gains=(means.baseline_error-means.room_error).to_numpy()
            rng=np.random.default_rng(20260921)
            boot=rng.choice(gains,(10000,len(gains)),replace=True).mean(1)
            stats.append(dict(pool=key[0],metric=key[1],cut=int(key[2]),k=int(key[3]),scope=scope,targets=len(g),
                rooms=g.family.nunique(),buildings=len(means),same_room_MAE=means.room_error.mean(),baseline_MAE=means.baseline_error.mean(),
                gain=gains.mean(),building_bootstrap_interval95=np.quantile(boot,[.025,.975]).tolist(),
                buildings_improved=int((gains>0).sum()),per_building=means.to_dict('index')))
    return stats


def controls():
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    candidates=[c for c in registry['candidates'] if c['physical_same_supported']]
    family=blocks(candidates);pair_groups=collections.defaultdict(set)
    for c in candidates:
        for a,b in itertools.combinations(sorted(c['image_ids']),2):pair_groups[a,b].add(c['candidate_id'])
    rows={r['canonical_annotation_id']:r for r in rows_at(OUT/'responses.jsonl.gz')}
    matrices={}
    for v in local('distances.json'):
        if v['condition'] not in ['manual','oos']:continue
        ix=[i for i,cid in enumerate(v['ids']) if not rows[cid]['imputed_point']]
        matrices[v['pool'],v['image_id']]=dict(ids=[v['ids'][i] for i in ix],workers=[rows[v['ids'][i]]['worker_id'] for i in ix],
            image=np.asarray(v['image'])[np.ix_(ix,ix)],code=v['code'])
    same_people=[];historical_source=[]
    for pool in ['strict','conditional']:
        for (a,b),groups in sorted(pair_groups.items()):
            if (pool,a) not in matrices or (pool,b) not in matrices:continue
            aa,bb=matrices[pool,a],matrices[pool,b]
            common=sorted(set(aa['workers'])&set(bb['workers']))
            if len(common)>=10:
                ia=[aa['workers'].index(w) for w in common];ib=[bb['workers'].index(w) for w in common]
                va=next_uncovered(aa['image'][np.ix_(ia,ia)],5,25.6);vb=next_uncovered(bb['image'][np.ix_(ib,ib)],5,25.6)
                same_people.append(dict(pool=pool,a=aa['code'],b=bb['code'],building=a.split('_')[0],groups=sorted(groups),N_common=len(common),workers=common,
                    uncovered_a=va,uncovered_b=vb,absolute_difference=abs(va-vb)))
        targets={i:v for (p,i),v in matrices.items() if p==pool and len(v['ids'])>=13 and any(rows[cid]['stage']=='scene_stability_stage1' for cid in v['ids'])}
        for target,t in targets.items():
            related={b if a==target else a for a,b in pair_groups if target in [a,b]}
            source={i:matrices['historical',i] for i in related if ('historical',i) in matrices and len(matrices['historical',i]['ids'])>=13}
            if not source:continue
            baseline={i:v for (p,i),v in matrices.items() if p=='historical' and i.split('_')[0]!=target.split('_')[0] and len(v['ids'])>=13}
            truth=next_uncovered(t['image'],8,25.6)
            historical_source.append(dict(pool=pool,target=t['code'],building=target.split('_')[0],family=family[target],
                source_codes=[v['code'] for v in source.values()],target_value=truth,
                same_room_prediction=np.mean([next_uncovered(v['image'],8,25.6) for v in source.values()]),
                external_baseline=np.mean([next_uncovered(v['image'],8,25.6) for v in baseline.values()])))
    return same_people,historical_source


def main():
    summary=local('SUMMARY.json');stats=aggregate_transfer();common,prospective=controls()
    dump('transfer_summary.json',stats);dump('same_people_control.json',common);dump('historical_source_prediction.json',prospective)
    curve=pd.DataFrame(local('coverage_curves.json'));parts=pd.DataFrame(local('partitions.json'));changes=pd.DataFrame(local('old_new_changes.json'))
    reports={}
    # 固定至少19人的图片，随k不更换图片组成。
    for pool in ['historical','strict','conditional']:
        c=curve[(curve.pool==pool)&(curve.metric=='image')&(curve.nominal_cut==9)&(curve.N>=19)&(curve.k<=18)]
        reports[pool]=dict(images=c.image_id.nunique(),curve=c.groupby('k').next_uncovered.mean().to_dict())
    dump('fixed_high_count_curves.json',reports)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for pool,label in [('historical','Historical'),('strict','New: strict'),('conditional','New: parent-link sensitivity')]:
        s=reports[pool];axes[0].plot(list(s['curve']),list(s['curve'].values()),marker='.',label=f"{label}, {s['images']} images")
    axes[0].set(xlabel='Observed distinct workers (k)',ylabel='Finite-pool next response without a near neighbour',ylim=(0,1));axes[0].legend(fontsize=8)
    primary=next(s for s in stats if s['pool']=='strict' and s['metric']=='image' and s['cut']==9 and s['k']==8 and s['scope']=='all')
    codes=list(primary['per_building']);gains=[primary['per_building'][b]['baseline_error']-primary['per_building'][b]['room_error'] for b in codes]
    axes[1].barh(codes,gains,color=['#47715e' if g>0 else '#ac654c' for g in gains]);axes[1].axvline(0,color='black',lw=.7);axes[1].set(xlabel='MAE gain from same-room source (>0 is better)',title='Image distance, k=8; exploratory leave-image-out')
    fig.tight_layout();fig.savefig(OUT/'coverage_and_transfer.png',dpi=160);plt.close(fig)
    lines=['# 新增真人数据复算与八组审核回读（2026-09-21）','','本轮为探索分析，不替代正式Paper A协议，不冻结分簇阈值或停止人数。已回读导师交流原文与两份研究SOP。导师关心人数增加的收益、分歧/少数结构、场景预测与人员组合；不能把“簇数少了”当成证明收敛或参考质量正确。','','## 1. 数据接入', '',f"冻结原始历史{summary['raw_history']}份；三份最新导出共{summary['raw_new']}条（包含4条空点记录）。严格池新增{summary['strict_new']}份候选，保留父记录独立性待核查的敏感性池新增{summary['conditional_new']}份。",'',
        '分配外有7条记录：5条进入严格候选；另外2条是历史同人同图再次作答，保留审计，不增加一票。分配内/外不是几何资格判据。本次明确授权覆盖所有分配外记录，不再只认旧5条白名单。', '',
        '45条parent_annotation关联全部找到父记录，其中24条点坐标数组与父记录完全相同。不能据此判断个人动机，但独立性需要核查；主核算暂不把独立性未核实者当成已确认独立样本，同时给出全部纳入的敏感性。10条历史接触不加新人票；2条新奇数点待人工处理；W034/7271、7272同人同图版本未决，两条保留而暂不任选一条。已确认的历史奇数点补/删完整沿用，不重新排除。', '',
        'Project93/7111在最新导出已经是8个点，按最新几何接入；这不证明修改时间是原标注用时。所有新时间未冻结，未以lead_time补入。历史冻结时间/点集没有修改；新表单Difficulty与Model Issue保持未采集。', '',
        f"上下绑定可计算：历史2343份；严格新增后{summary['binding_eligible']['strict']}份；父关联敏感性{summary['binding_eligible']['conditional']}份。严格586份新增候选中582份通过上下绑定，另外4份仍有配对资格问题，详见eligibility.json，不冒充单人簇。", '',
        '## 2. 分簇的实际变化', '',
        '原有上下点对推断＋固定起点环序逐端点最大距离；同有效点数硬约束。图上25.6像素/球面9°是中间探针，6/12及对应像素保留敏感性。没有IoU权重；没有自动执行自由匹配或传播人工映射。旧原始距离重新计算，未拼接旧缓存。', '',
        '| 池 | 方法（图上25.6px） | 图片×条件单元 | 作答 | 组数 | 单人组 | 近对却拆开 | 远对却同组 |','|---|---|---:|---:|---:|---:|---:|---:|']
    for pool in ['historical','strict','conditional']:
        for kind in ['complete','representative']:
            z=parts[(parts.pool==pool)&(parts.metric=='image')&(parts.nominal_cut==9)&(parts.partition==kind)]
            lines.append(f"| {pool} | {kind} | {len(z)} | {z.N.sum()} | {z.groups.sum()} | {z.singletons.sum()} | {z.near_but_split.sum()} | {z.far_but_grouped.sum()} |")
    lines += ['', '总组数增加同时包含新增图片，不能直接判成变差。固定历史图片比较：严格池有12图增加108份绑定可计算的独立候选，其中66份与本图任何旧作答都没有25.6px内的邻居；这些图原先只有1—6份绑定作答，不能将66/108推广到高人数历史图。完整链接未改变这12图旧成员之间的同组关系；代表半径在uNb-26和uNb-67改变5对旧成员关系。这是加入成员后重新选代表/分区的影响，旧坐标没有变化。', '',
        '发现2条新对应预警：uNb-40中W002对W033/W028，固定顺序最大误差约460/456px，循环换起点候选降到19.87/24.84px。只登记待视觉/人工确认，不据此自动合簇。说明固定起点可能制造明显差异，不能把所有新单人组解释为真人不同意见。详见correspondence_alerts.json。', '',
        '## 3. 对同房预测的支持程度', '',
        '本轮可复核目标：观察k人后，下一位剩余历史响应没有容差内近邻的概率。使用同房其他图的该值均值预测目标，与楼外总体均值比较；目标值只用于评价。至少保留5名未观察人员，借用其他人员信息补点的作答不进预测。候选房间关系沿用旧台账、不按效果筛选。先目标平均，再房间，再建筑等权汇总。', '',
        '| 池／距离 | k | 目标图／房间／建筑 | 同房MAE | 楼外基线MAE | 改善 | 建筑重采样95%区间 |','|---|---:|---|---:|---:|---:|---|']
    for s in stats:
        if s['cut']==9 and s['scope']=='all':
            lo,hi=s['building_bootstrap_interval95'];lines.append(f"| {s['pool']} / {s['metric']} | {s['k']} | {s['targets']}/{s['rooms']}/{s['buildings']} | {s['same_room_MAE']:.4f} | {s['baseline_MAE']:.4f} | {s['gain']:.4f} | [{lo:.4f}, {hi:.4f}] |")
    lines += ['', '整体有正向线索，但建筑少、存在明显反例、重采样区间不能当大样本置信保证。这里是已见新数据后的探索留图验证，不是预先冻结的前瞻预测，也不是“大约几人收敛”已验证。新增作答多来自已有人员，不能冒充15名新人的独立验证。', '',
        '所有6/9/12探针、仅新数据影响目标的结果见transfer_summary.json；严格只用旧历史源图预测新数据影响目标见historical_source_prediction.json。后者严格池23张目标、3个房间组，但全部在uNb一栋建筑；等房间汇总MAE改善0.06835（父关联敏感性0.05178）。这是楼内线索，不能保证跨建筑泛化；目标仍可能含旧作答，不是纯新增人员测试。', '',
        '相同人员交集的图对控制见same_people_control.json：严格池120图对、6栋建筑，至少10名共同人员，比较k=5的覆盖概率。q9-02与q9-13控制同一批人员后差异仍约0.91，是必须保留的反例；两图均为旧高人数图，不能归咎本轮新增。不把图对当独立房间。', '',
        '## 4. 收敛能说到哪一步', '',
        '当前复算给出逐人数覆盖曲线及100条真人顺序、每个前缀重新分簇的组数/主组比例（nested_replay.json）。这是有限人员池收益与稳定趋势，不是人口极限或正确性上限。接近全池时的下降含有限池耗尽效应，不能用它宣称未来不会出现新表达。', '',
        '| 固定≥19人图片池 | 图片数 | 观察5人后未覆盖概率 | 观察8人 | 观察12人 | 观察18人 |','|---|---:|---:|---:|---:|---:|']
    for pool,s in reports.items():lines.append(f"| {pool} | {s['images']} | {s['curve'].get(5,float('nan')):.3f} | {s['curve'].get(8,float('nan')):.3f} | {s['curve'].get(12,float('nan')):.3f} | {s['curve'].get(18,float('nan')):.3f} |")
    lines += ['', '每条曲线内部固定图片，不同池的图片集合不同，不能将两条均值差全部归于新人员。停止规则尚未冻结；本轮不编造每图“最终收敛人数”，也没有完成时间预测和人员组合分类的新一轮验证。', '',
        '## 5. 你的八组填写与G234/G235视觉核验', '',
        '七组35图全部采用，G180四图条件暂缓：“这个没有其他更好的候选的时候再采用”。与先前疑似OOS记录相容。G124允许困扰但认为仍能用，并勾选OOS用途，与疑似OOS不冲突；G051明确遮挡导致角点错序风险；G201凸起墙歧义；G234认为较简单但凸起易漏。简单与局部歧义可以同时成立。G155/G130仅勾选整组采用仍是完整采用决定，不补造理由。', '',
        '所有子图images={}，不解释成未审核或不采用；采用仅在派生层按整组应用，原始文件不改。用途未勾选表示未指定，不填“无用途”。G155采用不自动改成跨子组范围完全相同。G235的“感觉同房”是待核实疑问，不是确认合并。', '',
        '**已直接查看8张2048×1024原图。初步支持不同房间、相似用途与装修，保留人工最终确认。** G234的02/06/07/08：半高瓷砖＋大片白墙、暖气和15/16号柜；G235的03/04/05/11：大面积通顶瓷砖、淋浴隔间入口、白色浴袍和13/14号柜。两组洗手池/镜子/柜体与门洞的相对配置也不同。不是仅靠家具相似或房间编号判断。两组适合作为同类型不同房间候选，不建议合成一个八视角同房组。', '',
        '这些视觉意见仅影响后续待确认房间关系；本轮预测沿用旧关系，不因效果合并或拆组。没有创建截图文件。', '',
        '## 6. 复算与下一步', '',
        '运行 `python -X utf8 -B -m tools.thesis_main.analysis.analyze_new_manual_20260921`，再运行同目录`summarize_new_manual_20260921`模块。测试`tests/test_new_manual_20260921.py`。输入版本、每条处置和完整方法在SUMMARY.json/intake.json，所有距离、成员、预测分母另存，原始导出不改。', '',
        '先核对45条父关联及重复版本，审2条新对应预警和剩余奇数点；固定测量/停止规则后，再把新批次作为可追溯的验证阶段。保留OOS与不同表达，不为得到收敛而排除人员或调容差。']
    (OUT/'复算报告.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(primary=primary,common_people_pairs=len(common),historical_source_targets=len(prospective)),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
