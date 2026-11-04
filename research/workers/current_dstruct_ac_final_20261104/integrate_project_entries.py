"""Add traceable, idempotent entry points; never alter previous research data."""
from pathlib import Path
import csv
import hashlib
import re

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
START='<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_START -->'
END='<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_END -->'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def insert_md(text, addition):
    text=re.sub(re.escape(START)+r'.*?'+re.escape(END)+r'\s*', '', text, flags=re.S)
    first, sep, rest=text.partition('\n')
    return first+'\n\n'+START+'\n'+addition.strip()+'\n'+END+'\n'+rest.lstrip('\n')


def main():
    out=HERE/'delivery';out.mkdir(exist_ok=True)
    manifest=out/'INTEGRATED_PROJECT_FILES.csv'
    prior={r['path']:r for r in csv.DictReader(manifest.open(encoding='utf-8'))} if manifest.exists() else {}
    rows=[]
    def save(path, text, kind):
        p=REPO/path;p.parent.mkdir(parents=True,exist_ok=True)
        old=p.read_bytes() if p.exists() else b''
        oldsha=prior.get(path,{}).get('before_sha256',digest(old) if old else '')
        p.write_text(text,encoding='utf-8')
        rows.append(dict(path=path,change_kind=kind,before_sha256=oldsha,after_sha256=digest(p.read_bytes()),
                         numerical_data_modified=False))
    p='research/data/releases/v2.1/CURRENT_RESEARCH_BASIS.md'
    add='''## 2026-11-04：当前 DSTRUCT 直接 AC 最后一轮（第 13–15 批，已收尾）

[完整报告](../../../workers/current_dstruct_ac_final_20261104/REPORT_ZH.html) · [六方向离线研究台](../../../workers/current_dstruct_ac_final_20261104/workbench/index.html) · [原图机制图册](../../../workers/current_dstruct_ac_final_20261104/mechanisms/CURRENT_DSTRUCT_AC_ATLAS.html) · [逐条采用与来源](../../../workers/current_dstruct_ac_final_20261104/CONCLUSION_LEDGER.csv)。底座为 main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 与已交付第08–12批；本段是后续增量，旧段落保留各自时间、方法和支持身份。

- **先按当前楼外标签审计，再复用存量。** 旧TARGET 52,544事件中，28,420个物理AC对满足当前定义；43个合法改向保留原身份。混合D的16,364事件、含未知D的152事件保留。5,062个仅一般AC成立的事件不沿用失效的原特定背景设计。存量筛选不称为当前分类的重新均匀抽样。
- **仅补真实核心容量缺口。** 14/7与20/7共22格、7图、4楼；固定种子后补704对、1,408队，1,388有Q、20无连接，684共同Q对。另引用第12批4,096个已有直接腿，不重算ABC。
- **六方向全部列示。** 主目标自动版“合法存量＋缺口”C1→C2/C1→C3/C2→C3：14/7为+2.776/+2.590/+6.190（44/7/83图），20/7为+2.033/+2.097/+4.484（44/7/84图）。反向为相同物理对的镜像，不是独立验证。C1→C3已有6/3、8/4、10/5分别37/26/20图，均值+9.295/+15.417/+8.596；不同预算不拼成受控比例曲线。
- **条件与机制。** 20/7 C2→C3简单57图+3.933、困难10图+9.633；困难与边界自遮挡主要放大变化，反例及几何分项同时保留。事前248对诊断支持实际票数跨固定阈值与较大变化相关；同节点、同票、同连接仍可因定位改变Q。12个原图AC例和1个既有ABC附录可追溯。 已算704对中，固定XZ有276个可比背景块，56块跨正负；进一步固定D类别人数的120子组仍有18个跨正负，具体成员作用保留，附3组原图对照。
- **劳动与支持不能替代。** 20/7 C2→C3合法全队同源共同Q/T为561对、40图、18楼，Q+4.406、记录劳动+121.050秒；其它两个大预算类对无共同Q/T。当前合法AC消费者64个全部接续，原共同Q变化0；批准人工扩展41共同对，来自7个唯一端点，11个受影响正向条件无图均翻向。该身份不同于下文旧全库AC验收范围。

本轮未重分类，未开展新的联盟、固定配比、人数曲线、RFUSE、JOINT、Q/T选队或严格ABC。当前直接AC的问题已计算、解释并完成交付；完整支持、容量、失败及来源见专题文件。'''
    save(p,insert_md((REPO/p).read_text(),add),'add_current_adoption_section')
    for p in ['research/workers/personnel_ac_v21_20261030/README.md',
              'research/workers/current_class_interpretation_20261104/README.md',
              'research/workers/mixture_patterns_and_c13_half_20261104/README.md']:
        add='''## 后续采用：当前 DSTRUCT 直接 AC 已完成（第 13–15 批）

[完整直接AC报告](../current_dstruct_ac_final_20261104/REPORT_ZH.html)与[六方向研究台](../current_dstruct_ac_final_20261104/workbench/index.html)已接续当前楼外标签合法性、逐图容量、有限缺口补充、几何分项、记录劳动和12个原图案例。旧TARGET在当前标签下逐成员审计，合法改向保留原事件；存量团队结果不冒称重新均匀抽样。旧目录数值继续保留原方法与支持身份，本次未重算本目录的联盟、配比、曲线或ABC估计。'''
        save(p,insert_md((REPO/p).read_text(),add),'add_current_AC_followup_link')
    pages={
      'research/statistics/research_explorer_v1_r2_20261017/index.html':'../../workers/current_dstruct_ac_final_20261104/workbench/index.html',
      'research/workers/current_class_interpretation_20261104/workbench/index.html':'../../current_dstruct_ac_final_20261104/workbench/index.html',
      'research/workers/mixture_patterns_and_c13_half_20261104/workbench/index.html':'../../current_dstruct_ac_final_20261104/workbench/index.html'}
    for p,link in pages.items():
        s=(REPO/p).read_text()
        s=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',s,flags=re.S)
        banner=(START+'<aside id="current-dstruct-ac-final-20261104" style="max-width:1360px;margin:16px auto;'
                'padding:18px 22px;border:1px solid #bcd3dc;border-left:5px solid #215d7a;background:#edf6fa;'
                'color:#183e4e;font:15px/1.8 system-ui;box-sizing:border-box"><strong>当前 DSTRUCT 直接替换 AC '
                '已收尾 · 第 13–15 批</strong>：逐成员验收旧团队、六方向与真实容量、704 个有限补缺对、'
                '分项/劳动/输出状态及原图机制。20/7 C2→C3 平均 Q +4.484（84 图）；反向、负例和失败完整保留。 '
                f'<a href="{link}" style="font-weight:700;color:#145974">打开当前直接 AC 研究台</a>。'
                '本页原图表继续保留其来源与支持身份。</aside>'+END)
        assert '<body>' in s
        save(p,s.replace('<body>','<body>'+banner,1),'add_navigation_banner_only')
    path='docs/thesis_main/CURRENT_DSTRUCT_DIRECT_AC_20261104.md'
    save(path,'''# 当前 DSTRUCT 直接 AC：论文采用与研究收尾

本补充采用固定 main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 和第08–12批底座，交付第13–15批。详细[中文报告](../../research/workers/current_dstruct_ac_final_20261104/REPORT_ZH.html)、[结论台账](../../research/workers/current_dstruct_ac_final_20261104/CONCLUSION_LEDGER.csv)、[原图机制](../../research/workers/current_dstruct_ac_final_20261104/mechanisms/CURRENT_DSTRUCT_AC_ATLAS.html)及[最终验收](../../research/workers/current_dstruct_ac_final_20261104/DELIVERY_CHECKS.json)为当前直接AC引用入口。

## 可采用的核心表述

在当前楼外DSTRUCT标签下，对历史等人数替换逐成员复核，并在两个核心预算的真实容量缺口内补充后，固定同图、同参考、同人数和共同背景的C2→C3直接替换在14/7、20/7分别平均提高Q 6.190和4.484分（83、84图；均21楼）。C1→C2平均提高2.776和2.033分（均44图）；C1→C3大预算仅7图，较小已有半队预算另有37、26、20图的正向证据。相反方向由相同物理对翻号，不能作为独立验证。

困难与边界自遮挡的C2→C3变化幅度较大；简单图也普遍有较小正向变化。实际支持票跨固定门槛、对应重分组、完整来源环与定位/方向/范围提供不同机制。节点相同、票数相同或IoU提高，不保证Q不变或必然提高。原图正反例和失败事件使这些边界可直接核查。

20/7 C2→C3的合法全队同源共同Q/T支持为40图18楼，Q+4.406、记录劳动+121.050秒；不是完整流程成本或收敛速度。其它两个大预算类对无合法共同时间支持，保留缺失。

## 必须与表述同时保留的身份

- 历史TARGET与当前标签34个LOBO人员行不同；52,544旧事件中28,420物理AC对当前合法，43个改向映射完整保留。混合D及含未知D可合法，原特定背景约束另验收。
- 筛选旧团队是存量条件分析，不是按当前类别重新均匀抽样。14/7、20/7的22格补充先固定种子，704对、1,408队，684共同Q对。
- 全部33,220物理对中自动共同Q32,086；批准辅助共同Q32,127，新增41来自7个唯一端点；原共同分数不变。两核心预算没有辅助新增共同Q。
- 当前AC说明“这次换入怎样变化”；严格ABC说明“跨类变化是否超过同类”；联盟说明“组合类型的整体结果”。三者各自引用，不互相替代。

本轮计算及展示已完成。新的联盟、配比、人数曲线、RFUSE/JOINT或Q/T选队不属于本交付；相关已有估计保持原身份。逐条保持、幅度变化、条件变化、需改写或尚不能判断见结论台账。
''','new_thesis_adoption_note')
    with manifest.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(f'Integrated {len(rows)} documentation/navigation files; old embedded datasets untouched.')


if __name__=='__main__':main()
