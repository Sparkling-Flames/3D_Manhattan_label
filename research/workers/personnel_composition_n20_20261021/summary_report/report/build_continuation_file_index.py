#!/usr/bin/env python3
"""Produce a precise download index for frozen files; no large cache duplication."""
from pathlib import Path
import json
from build_continuation_report import sha, write_csv, atomic_text, TITLE

HERE=Path(__file__).resolve().parent
CONT=HERE.parent
STUDY=CONT.parent
WORK=STUDY.parents[2].parent
OLD=WORK/"HOHONET_delivery_20261021"

def main():
    specs=[]
    def add(group, path, description, rows="", columns="", stage="第二阶段新增"):
        p=Path(path);assert p.is_file(),p
        specs.append(dict(group=group,stage=stage,filename=p.name,absolute_path=str(p),
          sandbox_link="sandbox:"+str(p),rows=rows,columns=columns,description_zh=description,
          bytes=p.stat().st_size,sha256=sha(p)))
    group="1 总报告、采用判断与主要图表"
    add(group,HERE/(TITLE+".md"),"完整中文续研总报告，包含修复、分类采用、配比、替换、风险、机制及边界")
    add(group,HERE/(TITLE+".html"),"自包含离线报告，嵌入五张实际数据图及字体")
    add(group,HERE/"HOHONET_续研总报告与关键图表_20261021.zip","小型总报告与绘图代码包，不含大事件缓存")
    add(group,HERE/"分类采用判断_续研_20261021.csv","16个方法/条件/层级用途判断；保留探索与不可评身份",16)
    add(group,HERE/"N20_MATCHED_INTEGRATED_KEY_RESULTS.csv","Manual/Semi关键匹配结果及父类内细分，含指标分母与区间",10)
    add(group,HERE/"N20_TIME_RESPONSE_KEY_RESULTS.csv","共同端点上粗细类别与连续QT的时间响应",16)
    add(group,HERE/"研究台接入_续研字段说明.md","真实主键、阶段、去重、缺失和时间字段接口")
    add(group,HERE/"N20_同构成与改构成_质量和形状.png","匹配事件的质量变幅及B8/D10联合稳定图")
    add(group,HERE/"N20_效率细类与连续特征.png","效率细类与连续特征在共同端点的比较")

    group="2 人员标签与阶段覆盖账"
    for f,r in [("Manual_逐人分类_20261021.csv",434),("Semi_逐人分类_20261021.csv",186),("人员类别_成员名单_20261021.csv",44)]:
        add(group,OLD/f,"保持原标签身份；目标实验需使用楼外验证映射",r,stage="第一阶段保留")
    add(group,CONT/"integration/PHASE1_PHASE2_DOMAIN_SUBSET_COVERAGE_26x2.csv","26域子集×两条件的旧/新阶段覆盖，旧值保留",52,70)
    add(group,CONT/"integration/N20_METHOD_CONDITION_TIER_COVERAGE.csv","16行方法/条件/层级的配置、容量及事件覆盖",16)
    add(group,CONT/"integration/STAGE_COVERAGE_LEDGER_ZH.md","域组合与结构/关系方法分账说明")
    add(group,CONT/"integration/HOHONET_阶段身份_52行域组合与n20方法覆盖_20261021.zip","含882行逐池容量、恢复代码、字段映射与旧方法合法支持")

    group="3 原12953事件修复：完整表、分表及字典"
    base=CONT/"event_repair/ready_batch02"
    add(group,OLD/"人员构成_12953逐事件结果_20261021.csv","修复后的原名称关键表；原缺6290行已恢复",12953,95,"第一阶段结果修复")
    add(group,base/"ABC_EVENT_RESULTS_COMPLETE.csv.gz","全部实际成员、差值和三队绝对终点",12953,719,"第一阶段结果修复")
    for f,r in [("ABC_EVENTS_MANUAL_ORDINARY_PART01_COMPLETE.csv",4000),("ABC_EVENTS_MANUAL_ORDINARY_PART02_COMPLETE.csv",3835),("ABC_EVENTS_SEMI_ORDINARY_COMPLETE.csv",2069),("ABC_EVENTS_MANUAL_DOORWAY_COMPLETE.csv",3049)]:
        add(group,base/f,"完整字段独立分表，四片合计12953且互不重叠",r,719,"第一阶段结果修复")
    add(group,base/"EVENT_FIELD_DICTIONARY.csv","719字段的中文定义、单位和缺失语义",719,stage="第一阶段结果修复")
    add(group,base/"COMPLETE_TABLE_GUIDE_ZH.md","完整表读取和联接说明",stage="第一阶段结果修复")
    add(group,CONT/"event_repair/HOHONET_完整事件表修复包_20261021.zip","完整压缩表、诊断、回执、字典及修复代码；不重复四个展开CSV",stage="第一阶段结果修复")

    group="4 n20原生终点：六批与精确覆盖"
    ns=CONT/"next_stage"
    add(group,ns/"HOHONET_n20_续研冻结设计与恢复代码_20261021.zip","六方法冻结标签、48321配置及144642队精确请求")
    add(group,ns/"HOHONET_n20_已算18374终点复用_20261021.zip","18374个已有终点的便携表与精简几何",18374)
    for i,n in enumerate([5713,25000,25000,25000,25000,20555],1):
        add(group,ns/f"HOHONET_n20_batch_{i:03d}_20261021.zip","新增原生请求、98列标量、精简几何、完成和执行回执",n)
    add(group,ns/"HOHONET_n20_全量完成覆盖与恢复代码_20261021.zip","全局配置、成员、顺序的精确覆盖和剩余量；不含原生大缓存")
    add(group,ns/"coverage/本批计算与组合覆盖回执_20261021.md","累计418172队；全配置与成员抽样分别报告")
    add(group,ns/"coverage/N20_METHOD_COMPLETION.csv","六方法n20完整配置覆盖",6)

    group="5 新同构成/改构成匹配事件：九批Manual与独立Semi"
    ab=CONT/"n20_abc"
    add(group,ab/"HOHONET_n20_Manual_269814同构成改构成匹配对照_冻结设计_20261021.zip","269814事件精确团队、背景、m和构成，独立于目标结果")
    counts=[161,17305,30442,5179,35455,55667,30612,40330,54663]
    for i,n in enumerate(counts,1):
        add(group,ab/f"checkpointed_manual/ready/HOHONET_n20_manual_匹配对照结果_第{i:03d}批_{n}事件.zip","Manual完整事件分片；九批并集269814、697列",n,697)
    add(group,ab/"HOHONET_n20_Semi_1517匹配ABC_冻结设计_20261021.zip","Semi有限面板精确匹配设计；ABC是团队臂")
    add(group,ab/"HOHONET_n20_Semi_1517同构成改构成匹配对照_完整结果_20261021.zip","Semi完整事件、全部指标及恢复代码",1517,697)
    add(group,ab/"HOHONET_n20_同构成改构成匹配对照_总结代码与九批索引_20261021.zip","完整统计、m/难度/来源/尾部、875方向事件和代码；不重复宽表")
    add(group,ab/"MANUAL_N20_FINDINGS_ZH.md","Manual可独立读取的匹配结论")
    add(group,ab/"results_semi/RESULTS_ZH.md","Semi可独立读取的匹配结论")
    add(group,ab/"checkpointed_manual/summary/N20_MANUAL_KEY_FINDINGS.csv","Manual关键质量、几何、稳定和失败指标",7,35)
    add(group,ab/"results_semi/N20_ABC_PRIMARY_SUMMARY.csv","Semi分层关键指标及分母",666)
    add(group,ab/"checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv","875个仅QL.1/QL.2人数转移的真实方向事件",875)
    add(group,ab/"N20_MATCHED_EVENT_FIELD_DICTIONARY.csv","新697字段合同，独立于旧719列",697)
    add(group,ab/"final_summary/N20_MANUAL_RESULT_BATCH_INDEX.csv","九个结果包的精确行数、建筑、字节及哈希",9)

    group="6 全配置分析、辅助证据与机制图"
    na=CONT/"n20_analysis"
    for name,desc in [("N20_MANUAL_ANALYSIS_BATCH_20261021.zip","Manual全配置、共同端点、连续对照及全16结局"),
                      ("N20_SEMI_ANALYSIS_BATCH_20261021.zip","Semi全配置、共同端点及完整负结果"),
                      ("N20_SEMI_COMPOSITION_OPPORTUNITIES_20261021.zip","Semi同粗内细构成真实机会的补充"),
                      ("N20_FINAL_INTERPRETATION_ADDENDUM_20261021.zip","两条件采用判断、共同端点16项、层级与QT增量、两权重口径")]:
        add(group,na/name,desc)
    for cond in ["manual","semi"]:
        add(group,na/cond/"N20_FINDINGS_ZH.md",cond+" 全配置分析中文报告")
        add(group,na/cond/"N20_KEY_RESULTS.csv",cond+" 全配置主要结果")
        add(group,na/cond/"N20_COVERAGE.csv",cond+" 分析输入和结果支持")
    add(group,na/"N20_INTEGRATION_NOTES_ZH.md","两条件共同端点结论与单位说明")
    add(group,na/"N20_COMMON_ENDPOINT_DECISION_TABLE.csv","共同端点全部16分项和粗细、QT模型对照")
    add(group,CONT/"scope/SCOPE_FINDINGS_ZH.md","scope作为辅助证据的机会与条件边界")
    add(group,CONT/"scope/SCOPE_AUXILIARY_BATCH_20261021.zip","scope支持、原事件连接和恢复代码；不更改资格")
    add(group,CONT/"evidence/HOHONET_n20_Semi尺度机制正例与反例_20261021.zip","一张实际原图、两个匹配案例、真实票账、ERP/BEV/3D及代码")
    add(group,CONT/"evidence/README_ZH.md","新坐标中位数机制的正例与反例解释")
    add(group,CONT/"evidence/figures/N20_SP_q9_coordinate_medians.png","116条实际观察与六个原生中位数")
    add(group,ns/"analysis_check/N20_ANALYSIS_SMALL_INDEPENDENT_CHECK_20261021.zip","限定风险独立重聚合，未运行新融合/拟合")
    add(group,ns/"analysis_check/NEW_ANALYSIS_CHECK_ZH.md","小型独立复核说明")

    group="7 第一阶段完整交付：原身份保留"
    add(group,OLD/"HOHONET_人员分类与整体构成_报告_20261021.md","第一阶段报告；累计291904队与12953旧事件的阶段身份",stage="第一阶段保留")
    add(group,OLD/"HOHONET_人员分类与整体构成_报告_20261021.pdf","第一阶段22页PDF，不是新增n20续研报告",stage="第一阶段保留")
    add(group,OLD/"HOHONET_人员分类与整体构成_研究包_20261021.zip","已更新正确12953行关键表的原整合包；不含本续研",stage="第一阶段结果修复")
    assert len({r['absolute_path'] for r in specs})==len(specs)
    write_csv(HERE/"HOHONET_续研_文件总索引_20261021.csv",specs)
    lines=["# HOHONET 续研文件总索引（2026-10-21）", "",
      "先读第二阶段总报告和采用判断。原12,953行事件表已修复；新增原生终点分六批、新Manual匹配事件分九批保存，Semi独立保存。下面每项均可单独取得，不必依赖一个大ZIP。", "",
      "类别数K不限制为三；n20是团队人数，每格至多3队是成员抽样量，A/B/C是对照团队。类别人数配置、具体成员集合及加入顺序分别记账。", "",
      "哈希和绝对路径见同名CSV；本索引不重复打包数据。报告小包不含案例原图和大缓存；HTML已嵌入必要图，可独立阅读。", ""]
    last=None
    for row in specs:
        if row['group']!=last:
            lines += ["## "+row['group'],"","|文件|范围／用途|大小|","|---|---|---:|"]
            last=row['group']
        shape=(f"{int(row['rows']):,} 行" if row['rows']!="" else "")+(f" × {row['columns']} 列" if row['columns']!="" else "")
        desc=(shape+"；" if shape else "")+row['description_zh']
        size=row['bytes']/1024/1024
        lines.append(f"|[{row['filename']}]({row['sandbox_link']})|{desc}|{size:.2f} MiB|")
    lines += ["","本次完成范围：48,321个登记类别人数配置、144,642个登记实际团队（其中126,268新增），以及269,814个Manual和1,517个Semi有限面板匹配对照。全人口成员集合与所有顺序未穷尽，精确剩余数保留在覆盖回执。","",
      "后续恢复以精确请求和缺失键为单位：先检查已有分批结果，不重复计算相同实际成员集合。旧标签、全数据展示标签与目标建筑外验证标签不能相互替代。",""]
    atomic_text(HERE/"HOHONET_续研_文件总索引_20261021.md","\n".join(lines))
    atomic_text(HERE/"FILE_INDEX_RECEIPT.json",json.dumps({"entries":len(specs),"unique_paths":len(specs),"hash_algorithm":"sha256","index_excludes_itself":True,"all_referenced_paths_exist":True},indent=2)+"\n")
    print(json.dumps({"files":len(specs),"bytes_referenced":sum(r['bytes'] for r in specs)},ensure_ascii=False))

if __name__=="__main__":main()
