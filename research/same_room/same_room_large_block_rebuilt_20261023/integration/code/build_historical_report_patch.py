#!/usr/bin/env python3
"""Prepare a reviewable historical report patch; never edit the repository.

All old numeric results are retained. This patches the interpretation of
already independently checked statistics and adds a new-study handoff.
"""
import argparse,csv,difflib,hashlib,json,re,shutil
from pathlib import Path,PurePosixPath

COMMIT='e92abe8631d7f01dc192ee796b46f295ece37a6d'
OLD='research/same_room/same_room_current_classes_v2_20261023/REPORT_ZH.md'
REVIEW='research/statistics/pro_return_review_20261023/same_room/SRCC_INDEPENDENT_REVIEW.md'
CHECKS='research/statistics/pro_return_review_20261023/same_room/INDEPENDENT_CHECKS.json'
SRC_GATE='research/statistics/pro_return_review_20261023/same_room/INDEPENDENT_SOURCE_GATE_CHANGES.csv'
TIME='research/statistics/pro_return_review_20261023/same_room/INDEPENDENT_TIME_Q_M1.csv'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--repo',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--new-repo-dir',default='research/same_room/same_room_large_block_rebuilt_20261023')
    x=a.parse_args();x.out.mkdir(parents=True,exist_ok=True)
    src=x.repo/OLD;original=src.read_text(encoding='utf-8');text=original;changes=[]
    assert blob(src)=='76298a1aa901504e5db87c3d5f359c859e1c8683','Historical report differs from frozen main input'
    assert blob(x.repo/REVIEW)=='b66fb3e537a6b344c07ff57f0eb1b86980c76840','Review differs from frozen main input'
    new_dir=PurePosixPath(x.new_repo_dir)
    # Both report packages are siblings under research/same_room by default.
    import posixpath
    new_link=posixpath.relpath(str(new_dir/'REPORT_ZH.md'),str(PurePosixPath(OLD).parent))
    review_link='../../statistics/pro_return_review_20261023/same_room/SRCC_INDEPENDENT_REVIEW.md'
    gate_link='../../statistics/pro_return_review_20261023/same_room/INDEPENDENT_SOURCE_GATE_CHANGES.csv'
    time_link='../../statistics/pro_return_review_20261023/same_room/INDEPENDENT_TIME_Q_M1.csv'
    checks_link='../../statistics/pro_return_review_20261023/same_room/INDEPENDENT_CHECKS.json'
    def replace_once(change_id,old,new,evidence):
        nonlocal text
        assert text.count(old)==1,(change_id,text.count(old))
        # Retain every literal numeric token from the replaced historical text.
        old_numbers=re.findall(r'\d+(?:\.\d+)?',old)
        new_numbers=re.findall(r'\d+(?:\.\d+)?',new)
        it=iter(new_numbers)
        assert all(any(q==n for q in it) for n in old_numbers),(change_id,old_numbers,new_numbers)
        text=text.replace(old,new,1)
        changes.append(dict(change_id=change_id,action='interpretation_or_handoff_only',
          old_text=old,new_text=new,evidence=evidence,historical_numeric_tokens_preserved=True))

    title='# 当前人员类别构成作用的同房跨视角重复性与差异来源\n'
    replace_once('handoff',title,title+f'''\n> **2026-10-23 接续说明。** 本文保留原研究使用的提交、人员标签、团队设计、结果规模与历史数值，仅依据[独立核验]({review_link})补正三处统计口径。较大块严格 ABC 的新设计、实际新增端点与条件分析已完成，完整结果与复现入口见[同房大块接续主报告]({new_link})。该接续使用 main `{COMMIT}`，属于本轮新实验，不是上轮未取得原始设计的恢复；新旧支持与计权分别保留。\n''',REVIEW)
    replace_once('source_gate_definition',
      '但双端活跃筛选已经看过目标结果，不能直接用作部署成功率。仅用源端极差至少 2 分选入时，409 个有向面板、260 个不同面板、116 图对中：',
      '但双端活跃筛选已经看过目标结果，不能直接用作部署成功率。以下源端极差也先在两视角共同可评分的团队支持上计算，再按源端极差至少 2 分选入；保留原统计的 409 个有向面板、260 个不同面板、116 图对。这应称为“共同可评支持上的回顾性源端阈值分析”，不是只根据源端全部可评分团队即可执行的筛选规则：',
      SRC_GATE)
    replace_once('source_gate_interpretation',
      '因此，看到源图类别作用明显，可以把该构成列为目标图的有根据候选；仍应给目标“变化很小”保留相当权重。不能把活跃条件下的 73.23% 写成任意目标图的成功率。',
      f'''因此，这一共同支持上的回顾性结果说明，源端出现构成响应时，目标端仍有较多“变化很小”的情况；不能把双端活跃条件下的 73.23% 写成任意目标图的成功率。它提供解释与候选组织依据，不直接给出只看源端的部署成功率。\n\n独立核验只发现一个有向面板的源触发身份因此改变：`SRCC23P_a4466a1392f288cc75cb`，G202，`wc2JMjhGNzB-26 → wc2JMjhGNzB-53`，n6。共同可评分的 10 队给出源配比极差 0.323860；只要求源端可评的 14 队给出 6.495464。这里保留原表及其共同支持分母，并明确筛选含义；没有把未按纯源支持重算的原表重新命名为可部署结果。详见[发生变化的源触发记录]({gate_link})。''',
      SRC_GATE)
    replace_once('replacement_source_gate_support',
      '例如纯类别三人替换，双端非小条件下的分层同向率约 **77.66%**，仅源端非小触发后在目标同向的比例约 **41.96%**。',
      '例如纯类别三人替换，双端非小条件下的分层同向率约 **77.66%**，在替换前后共同四端点可评支持上、仅按源端非小触发后，目标同向的比例约 **41.96%**。',
      REVIEW)
    time_note='表为未设效果阈值的方向诊断；原始计时机会分别 14,556、13,642，涉及 96/113 个图对、10 楼。小变化阈值与各缺失分母在 [时间表](results/key_tables/TIME_Q_SAME_SUPPORT.csv) 保存。它衡量记录劳动成本，不能换称现实交付、排队时间或金钱。'
    replace_once('zero_threshold_receipt',time_note,time_note+f'''\n\n**严格零阈值的已定位差异：** G178 的 `uNb9QFRL6hY-72/78`，面板 `SRCC23P_56a5cd47250488457b70`，n11、同配比 m1；当前交付端点独立复算为 **49/120**，原保存事件汇总为 **50/120**。下游分层比例分别为 **40.512657%** 与 **40.513319%**，上表均四舍五入为 **40.51%**，故保留上表历史显示值，精确核对采用当前端点复算的 49/120。该计数沿用 `sign(ΔQ_a)=sign(ΔQ_b)`，包含双方恰为零的符号一致，不等于两边都发生非零同向变化。其它主 m1 面板未发现同类差异；现有汇总不足以指定原生产中不同的是哪个事件或原因，不将其擅自归因于浮点误差。详见[逐面板独立时间/Q表]({time_link})及[独立核验说明]({review_link})。''',
      TIME+'; '+REVIEW)
    replace_once('labor_ratio_arithmetic',
      '劳动比采用逐事件 log 后分层还原，不是所有人的总劳动和之比。',
      f'''劳动比先计算每次可用视角增人机会的“后队劳动量／前队劳动量”，在同一增人系列内平均，再按图对、声明组、建筑逐层作算术平均；它不是所有人的总劳动和之比。独立复算的分层算术值为 2.005611778，保留本文的 2.006；若对同一记录改为平均 log 后还原，则为 1.940114092，这是另一个统计量。原文“逐事件 log 后分层还原”的方法描述在此更正，未更换原结果。见[独立复算值]({checks_link})。''',
      CHECKS)
    replace_once('summary_gate_wording',
      '|把同向率直接当作迁移成功率|同时保留两端小变化、真同向、反向、单端小变化；双端筛选与仅源端触发分开|',
      '|把同向率直接当作迁移成功率|同时保留两端小变化、真同向、反向、单端小变化；双端筛选、共同可评支持上的源端触发与纯源信息执行规则分开|',
      REVIEW)
    target=x.out/'patched_repo'/OLD;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding='utf-8')
    shutil.copy2(target,x.out/'REPORT_ZH_corrected_copy.md')
    patch=''.join(difflib.unified_diff(original.splitlines(keepends=True),text.splitlines(keepends=True),
      fromfile='a/'+OLD,tofile='b/'+OLD))
    (x.out/'old_same_room_report_corrections.patch').write_text(patch,encoding='utf-8')
    with (x.out/'HISTORICAL_REPORT_CHANGES.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(changes[0]));w.writeheader();w.writerows(changes)
    sources=[]
    for rel in [OLD,REVIEW,CHECKS,SRC_GATE,TIME]:
        pp=x.repo/rel;sources.append({'repo_path':rel,'commit':COMMIT,'bytes':pp.stat().st_size,'sha256':sha(pp),'git_blob':blob(pp)})
    receipt={'source_commit':COMMIT,'source_report':OLD,'source_sha256':sha(src),'source_git_blob':blob(src),
      'new_report_repo_path':str(new_dir/'REPORT_ZH.md'),'new_report_ready_at_patch_generation':(x.out.parent/'REPORT_ZH.md').is_file(),
      'status':'reviewable_patch_apply_with_completed_new_report','repository_modified':False,
      'historical_report_numeric_results_changed':False,'replacement_numeric_tokens_preserved':True,
      'original_report_commit_and_scale_retained':True,'corrections':['source_gate_common_support','labor_ratio_arithmetic','strict_zero_threshold_49_vs_50'],
      'change_blocks':len(changes),'patched_sha256':sha(target),'patch_sha256':sha(x.out/'old_same_room_report_corrections.patch'),'sources':sources}
    (x.out/'HISTORICAL_PATCH_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
