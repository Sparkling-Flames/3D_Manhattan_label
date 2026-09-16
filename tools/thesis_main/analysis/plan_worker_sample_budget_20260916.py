"""人员采集预算与历史有效时长复算；不改变分型、派发或时间规则。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow

from tools.thesis_main.analysis.worker_behavior_time_20260910 import clean_time, adjusted_time_keys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/worker_sample_budget_20260916'
BASE = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
CN = {1, 2, 6, 8, 10, 12, 13, 15, 17}


def summary(frame):
    seconds = frame.active_time_seconds
    return dict(records=len(frame), workers=frame.worker_id.nunique(),
                mean_minutes=seconds.mean()/60, median_minutes=seconds.median()/60,
                worker_equal_mean_minutes=frame.groupby('worker_id').active_time_seconds.mean().mean()/60,
                total_active_hours=seconds.sum()/3600)


def possible(images, deficits, done, newcomers, new_cap, old_cap):
    """容量核验：每条人员—图片边最多1份；不生成派发方案。"""
    workers=sorted(CN)+list(range(1000,1000+newcomers))
    offset=1+len(images); sink=offset+len(workers); rr=[];cc=[];vv=[]
    def edge(a,b,c):
        rr.append(a);cc.append(b);vv.append(c)
    for i,r in enumerate(images,1):
        edge(0,i,deficits[i-1])
        eligible=set(r['clean_workers'])-done.get(r['image_id'],set())
        for j,w in enumerate(workers):
            if w>=1000 or w in eligible:edge(i,offset+j,1)
    for j,w in enumerate(workers):edge(offset+j,sink,new_cap if w>=1000 else old_cap)
    graph=coo_matrix((np.asarray(vv,dtype=np.int64),(rr,cc)),shape=(sink+1,sink+1)).tocsr()
    return int(maximum_flow(graph,0,sink).flow_value)


def main():
    OUT.mkdir(exist_ok=True)
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    t=pd.read_csv(BASE/'facts/active_time_context.csv.gz',dtype={'worker_id':str,'project_id':str,'runtime_task_id':str})
    a=pd.read_csv(BASE/'annotations.csv.gz')
    d=t.merge(a[['canonical_annotation_id','assistance_exposure']],on='canonical_annotation_id',validate='one_to_one')
    assert len(d)==2501
    shifted=adjusted_time_keys()
    d['known_shift']=[(r.project_id,r.runtime_task_id,r.worker_id) in shifted for r in d.itertuples()]
    d['used']=clean_time(d)&~d.known_shift
    valid=d[d.used].copy()
    assert valid.active_time_seconds.gt(0).all() and not valid.known_shift.any()
    assert not valid.active_time_source.eq('lead_time_fallback').any()
    manual=valid[valid.assistance_exposure=='none']
    semi=valid[valid.assistance_exposure=='model_preannotation']
    current=manual[manual.worker_id.astype(int).isin(CN)]
    stats={name:summary(f) for name,f in [('all_modes',valid),('manual',manual),('semi',semi),
        ('manual_excluding_W019_W026',manual[~manual.worker_id.isin(['19','26'])]),('current_chinese_manual',current)]}
    people=[]
    for w in sorted(d.worker_id.unique(),key=int):
        row=dict(worker_id=int(w),historical_records=int((d.worker_id==w).sum()))
        for label,g in [('manual',manual),('semi',semi),('combined',valid)]:
            g=g[g.worker_id==w];row[label]=summary(g) if len(g) else dict(records=0,mean_minutes=None,median_minutes=None)
        people.append(row)
    assert sum(r['combined']['records'] for r in people)==len(valid)
    axes=pd.read_csv(ROOT/'analysis_results/worker_four_block_exploration_20260910_v1/axes_primary.csv.gz')
    support=axes[axes.worker_id.isin(CN)].groupby(['worker_id','axis']).image_id.nunique().unstack()
    selection=read('analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json')
    package=read('analysis_results/stage1_person_image_packages_20260913_v2/分配建议与核验.json')
    done={}
    for r in package['assignments']:done.setdefault(r['image_id'],set()).add(r['worker_id'])
    images=[r for r in selection['images'] if r['status']=='确定采用' and r['new_needed']>len(done.get(r['image_id'],set()))]
    deficits=[r['new_needed']-len(done.get(r['image_id'],set())) for r in images]
    total=sum(deficits);assert total==592
    budgets=[]
    for old_cap in [20,30]:
        for new_cap in [30,40,50]:
            n=next(n for n in range(40) if possible(images,deficits,done,n,new_cap,old_cap)==total)
            assert n==0 or possible(images,deficits,done,n-1,new_cap,old_cap)<total
            budgets.append(dict(old_people=9,old_additional_cap=old_cap,new_cap=new_cap,minimum_new_people=n))
    assert possible(images,deficits,done,15,28,20)==592
    assert possible(images,deficits,done,15,30,20)==592
    # 40/50张是预算情景；从未把该数量作为分类成功标准。
    time_budget=[]
    new_mean=stats['manual_excluding_W019_W026']['mean_minutes']
    old_mean=stats['current_chinese_manual']['mean_minutes']
    for new_n in [30,40,50]:
        time_budget.append(dict(new_people=15,new_images_each=new_n,old_people=9,old_extra_each=20,
            new_person_hours=new_n*new_mean/60,old_person_hours=20*old_mean/60,
            total_person_images=15*new_n+9*20,total_active_person_hours=(15*new_n*new_mean+9*20*old_mean)/60))
    result=dict(status='预算建议，不是样本量充分性证明或派发',historical_time_records=len(d),valid_time_records=len(valid),
        source_time=str((BASE/'facts/active_time_context.csv.gz').relative_to(ROOT)),
        source_annotations=str((BASE/'annotations.csv.gz').relative_to(ROOT)),
        source_time_rules='worker_behavior_time_20260910.clean_time；阶段原始日志规则及已知人工加秒排除，既有SOURCE_AUDIT可追溯',
        time_missing_workers=[r['worker_id'] for r in people if not r['combined']['records']],
        timing_status_counts=d.timing_status.value_counts().to_dict(),known_shift_rows=int(d.known_shift.sum()),
        timing_summary=stats,workers=people,current_cn_axis_support=support.reset_index().to_dict('records'),
        after_required_deficit=total,capacity_cases=budgets,time_budget=time_budget,
        assumptions=['当前480份必做全部完成且可纳入；未当成已完成事实','不保证其他H选做，未扣W035尚未导出复核结果',
            '旧中文9人可继续，W011不新增；英文无新增任务；新人未接触任何图片',
            '102张采用图为工作量范围，额外H12张及待复核新增图没有统一目标，未自动算入',
            '时间成本保留可用时间的失败/几何异常记录，不按正确或几何可计算筛选',
            '训练、阅读、休息、返工和管理时间未计入；新人时间用历史均值作情景，非新人实测'],
        sample_size_status='未进行每人10/20/30/40/50张的完整分型样本量实验；40—50张仅分阶段预算，允许暂不能分类')
    (OUT/'核算数据.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 人员分类采集量与历史耗时核算（2026-09-16）','',
        '## 可执行建议与证据边界','',
        '最新用户确认新人应多标以积累分析与分类资料。建议新人按每人约50张准备，先收30张，再分批完成其余约20张；按换一批房间后人员画像是否仍可复现来判断证据，不能把50当作足够分类的保证。现有9名中文人员已有历史，建议追加约20张与新人重叠、且本人未接触的新图，检查当前表现。',
        '建议先按15名实际参与新人＋9名旧中文人员编制预算，另保留2—3名候补意向。它比最低采集人数留有余量，但不保证最终各类都足够大。不预定组数，不强行平均，不保证所有类型都收敛。',
        '15名新人各40张的一个容量例子是：12张共同历史比较图＋最多28张候选补标；9名旧中文各最多20张。已核对原有人图接触限制，28×15＋20×9的可分配容量能覆盖592份缺口。12张共同图不代表仅凭12张定型；可结合其余标注中不属于当前被检验房间的部分估计画像。具体选图与各人分配尚未生成。',
        '按每人50张准备时，可增加到约20张新人共同历史比较图＋约30张候选补标图；9名旧中文每人最多追加20张。15×30＋9×20同样通过容量检查。共同历史图应已有旧人员结果，避免要求旧人员重复作答；需另核对实际选中的图覆盖和参考可靠性。20张只是便于比较的共同部分，不能单独宣布已足够定型；其余资料可按房间交叉划分，用其他房间的作答给人分类，再验证当前房间。',
        '这一50张方案预算上限930份。若20张共同图完全位于本轮缺口之外，补齐592份＋共同图300份共892份，余38份是预算余量，不强制派发无研究用途的任务。预计先阶段采集，最终按图和人员覆盖补足。',
        '共同图不是让所有人讨论或统一答案：每个人独立完成。图像应覆盖不同房间、场景与难度，不能40张集中于两个房间。按房间划分用于分类和检验的资料，避免用同一房间的结果给人分类后，又宣称其在该房间内更稳定。保留合理的不同标法，不以偏离多数直接等同低质量。',
        '质量＋时间及规则证据可从Manual起步；scope中的不可标识别还需要明确裁定的OOS测试图，当前只收可标候选无法完整检验这一轴。Semi修改行为必须另有真实半自动任务，不能从Manual时长或角点数推出来。本预算以Manual为主，未自动追加Semi/OOS。','',
        '## 已有分类证据','',
        '9名旧中文人员每人已有58—63张参考偏差记录、40—79张可用时间轴记录、9张不可标scope与28张可标scope记录，以及22—25张修改行为记录。这是可分析覆盖，不是已证明类型稳定。旧固定二分探索中，互不重叠的楼分别分类，一致程度中位数：质量粗分0.113、时间0.789、质量＋Semi 0.244；四项共同分类受scope覆盖限制。此处只引用历史结果，不把它们当作最新19人结果，也不恢复旧“必须再观察5人”的规则。',
        '要同时检查：人员画像换图能否重复；具体子类在同一目标图上有多少真实人员；其标注过程是否稳定。AABC需要该图至少有2名A、1名B、1名C，重复排列不能增加独立人员或独立图片数量。暂无法稳定分类者保留连续画像或未定状态。',
        '历史报告：[四类信息探索](../worker_four_block_exploration_20260910_v1/README_ZH.md)、[多组数扩展](../worker_four_block_exploration_20260910_v1/group_count_extension/README_ZH.md)。',
        '外部研究将人员能力与任务难度/类型联合建模，支持比较时考虑任务构成，但不提供可直接套用到本任务的40张门槛：[Zhao等](https://arxiv.org/abs/1401.3836)、[Kim与Chung](https://arxiv.org/abs/2004.00101)。','',
        '## 人数容量核验','',
        '假设当前480份必做全部有效完成，102张已采用图片还缺592份；此时原有中文人员继续参与，上一轮“至少20名新人”的前提已改变。以下是仅补齐图片的下限，不含额外共同历史比较图、培养/验证或H池外12图的新增目标。','',
        '| 旧中文每人再做 | 新人每人最多 | 最少新人 |','|---:|---:|---:|']
    lines += [f'| {r["old_additional_cap"]} | {r["new_cap"]} | {r["minimum_new_people"]} |' for r in budgets]
    lines += ['', '## 历史实际操作时长','',
        '全部26人、2501条历史记录核对后，1949条符合既有有效计时条件，来自24人；W014/W026没有合格时间，显示缺失而不填零。所有历史人员统计包含W019；研究预算另列排除W019/W026的结果。已知人工加秒、缺失、协议偏离及覆盖不足不进入本次均值，没有使用lead_time。',
        '为了估算任务总工时，均值按每份任务等权；另外保存“先算个人均值、再按人等权”的结果。完成质量不用于筛掉耗时，因失败也会消耗时间。不同模式平均值的差异不是半自动节时的因果估计。','',
        '| 数据范围 | 有效记录 | 人数 | 平均分钟/份 | 中位分钟/份 |','|---|---:|---:|---:|---:|']
    labels={'all_modes':'所有模式合并','manual':'全部历史手工','semi':'全部历史半自动','manual_excluding_W019_W026':'手工（排除W019/W026）','current_chinese_manual':'现有9名中文人员手工'}
    lines += [f'| {labels[k]} | {r["records"]} | {r["workers"]} | {r["mean_minutes"]:.2f} | {r["median_minutes"]:.2f} |' for k,r in stats.items()]
    lines += ['', '手工先算个人均值再按人等权为'+f'{stats["manual"]["worker_equal_mean_minutes"]:.2f}分钟；直接合并任务为{stats["manual"]["mean_minutes"]:.2f}分钟。两者权重不同。W036手工均值约17.40分钟，明显较慢，保留而未当作异常删除；中位数不适合直接替代平均值估算总工时。','',
        '## 逐人历史平均耗时','',
        '以下均为分钟。中文姓名不用于研究数据展示。份数是该模式有效计时记录数，不是这个人全部标注量。','',
        '| 人员 | 手工份数 | 手工均值 | 半自动份数 | 半自动均值 | 合并均值 |','|---|---:|---:|---:|---:|---:|']
    fmt=lambda v:'缺失' if v is None else f'{v:.2f}'
    for r in people:
        m,s,c=r['manual'],r['semi'],r['combined']
        lines.append(f'| W{r["worker_id"]:03d} | {m["records"]} | {fmt(m["mean_minutes"])} | {s["records"]} | {fmt(s["mean_minutes"])} | {fmt(c["mean_minutes"])} |')
    lines += ['', '## 15名新人＋9名旧中文人员的时间预算','',
        f'新人暂用排除W019/W026后的历史手工均值{new_mean:.2f}分钟/份作预算；旧中文用其历史均值{old_mean:.2f}分钟/份。新人并无真实耗时观测，这不是速度保证。','',
        '| 新人每人张数 | 新人每人操作小时 | 旧中文每人追加20张操作小时 | 总人图份数 | 总操作人时 |','|---:|---:|---:|---:|---:|']
    lines += [f'| {r["new_images_each"]} | {r["new_person_hours"]:.2f} | {r["old_person_hours"]:.2f} | {r["total_person_images"]} | {r["total_active_person_hours"]:.2f} |' for r in time_budget]
    lines += ['', '30张方案是第一阶段，不承诺其中已包含全部592份缺口和所有共同比较图；40张容量例子已核验。总人时是所有人耗时相加，不能当成日历工期。40—50张对应每名新人约2.76—3.45小时有效操作；若每天确有1小时有效操作，算术上约3—4天，尚需另计培训、练习、休息、沟通与返工。预算可另留余量，但本次没有把任意加成冒充历史实测。',
        '新人先熟悉流程，练习与正式数据分开标记；分批查看用时和证据是否足够，不能只给分类不稳定者追加困难图而忽略题目构成的变化。不要为了得到稳定类别不断改分类规则或只报告成功组。',
        '## 复算与范围','',
        '`D:/anaconda/python.exe -m tools.thesis_main.analysis.plan_worker_sample_budget_20260916`。内置检查包括记录一对一连接、计时来源/排除、逐人份数加总、每人每图最多一次的容量约束、最低人数前一档不可行，以及15×28＋9×20确可覆盖592份。未生成派发文件、未改正式协议、未修改任何历史标注和人工决定。']
    (OUT/'人员样本量与耗时建议.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(timing=stats,capacity=budgets,budget=time_budget),ensure_ascii=False))


if __name__=='__main__':
    main()
