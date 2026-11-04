"""Add current analysis pointers without overwriting frozen experimental tables."""
from pathlib import Path
import os,json,re
BASE=Path(__file__).resolve().parent
REPO=BASE.parents[2]
changed=[]
def link(target,destination):return os.path.relpath(destination,target.parent).replace(os.sep,'/')
def mdinsert(path,body):
 if not path.exists():raise FileNotFoundError(path)
 text=path.read_text(encoding='utf-8')
 start='<!-- MIXTURE_C13_20261104_START -->';end='<!-- MIXTURE_C13_20261104_END -->'
 block=start+'\n'+body.strip()+'\n'+end
 if start in text:text=re.sub(re.escape(start)+r'.*?'+re.escape(end),lambda _:block,text,flags=re.S)
 else:
  i=text.index('\n')+1;text=text[:i]+'\n'+block+'\n'+text[i:]
 path.write_text(text,encoding='utf-8');changed.append(str(path.relative_to(REPO)))
def htmlinsert(path,title,text,destination):
 s=path.read_text(encoding='utf-8')
 aid='mixture-c13-20261104'
 block=f'<aside id="{aid}" style="max-width:1360px;margin:16px auto;padding:18px 22px;border:1px solid #bcd3dc;border-left:5px solid #136e7d;background:#edf7f9;color:#183e4e;font:15px/1.8 system-ui;box-sizing:border-box"><strong>{title}</strong>：{text} <a href="{link(path,destination)}" style="font-weight:700;color:#0c6076">打开混合规律与 C1↔C3 研究台</a>。</aside>'
 if f'id="{aid}"' in s:s=re.sub(r'<aside id="'+aid+r'".*?</aside>',lambda _:block,s,count=1,flags=re.S)
 else:s=re.sub(r'<body([^>]*)>',lambda m:m.group(0)+block,s,count=1)
 path.write_text(s,encoding='utf-8');changed.append(str(path.relative_to(REPO)))
p=REPO/'research/data/releases/v2.1/CURRENT_RESEARCH_BASIS.md'
mdinsert(p,f'''## 2026-11-04：混合人群规律、进入过程与 C1↔C3 半队补充（第 11–12 批）

[完整报告]({link(p,BASE/'REPORT_ZH.html')}) · [离线研究台]({link(p,BASE/'workbench/index.html')}) · [23 条结论与来源]({link(p,BASE/'CONCLUSION_LEDGER.csv')})。

- **现有混合规律得到加强。** 当前 DSTRUCT C2→C2+C3 共同 204 图 Q +2.768，166 图正；C3→同一联盟 184 图 Q −4.749，139 图负。边界自遮挡层 C3→C2+C3 为 −18.467（36 图），并伴随转折/短段减少和遗漏增多。固定人数 C2 少 1/C3 多 1，n12 +1.969、n20 +1.192；多数有限配比链逐步不下降。人数、成员与背景分别解释。
- **已有自然序列支持早期过程优势。** 前 6 人 DSTRUCT C2+C3 对 C1+C2，6–20 人完整路径平均 Q +1.780（190 图/22 楼，165 图正）；困难层 +2.696。先遇到高 Q、窗口内持续达标、合法记录劳动与几何稳定分别报告。最终全员成员与 Q 相同。
- **C1↔C3 50% 严格 ABC 已真实补算。** 3,200 事件、4,992 唯一新团队；4,898 有 Q、94 无连接。6/3 同图同 D 的四端共同支持 36 图/10 楼，双向 GS +3.269/+3.955，C3−C1 Q +7.865，32/36 图正。最大 8/4 两方向 24/4 图，无共同图片，另列；不能用 8/4 反向四图替代同图双向证据。
- **K4 小池实际辅助消费者已补接。** 1,081 端点中命中两个批准人工顺序；原 1,046 个有 Q 端点保持，扩展为 1,048。高历史 Q 早期政策差 +1.500→+1.534，快类 −1.900→−1.926。主自然路径 1,488,398 个唯一端点与 57 人工端点交集为 0。

本批不重新分类，原有效预处理、原答 Q/T、参考和历史自动版保持。新增团队仅用于已授权的 C1↔C3 缺口。正式可评与可见核诊断分开；核内敏感性保留主要方向，不新增坐标修正规则。新大池策略和重新 Q/T 选队继续暂缓。''')
p=REPO/'research/workers/current_class_interpretation_20261104/README.md'
mdinsert(p,f'''## 后续补充：第 11–12 批已完成

本目录第 08–10 批的类别画像与原图保持。现已进一步完成[混合人群规律及 C1↔C3 50% 严格 ABC]({link(p,BASE/'REPORT_ZH.html')})：完整联盟、固定人数比例、具体成员与背景、早期曲线、合法记录劳动及 K4 两端实际消费者接续。新增端点只在这个后续专题中，原图册和原画像数值没有因此重算。[打开新研究台]({link(p,BASE/'workbench/index.html')})。''')
for rel in ['research/workers/current_class_interpretation_20261104/workbench/index.html','research/statistics/research_explorer_v1_r2_20261017/index.html']:
 htmlinsert(REPO/rel,'混合规律与 C1↔C3 50% 严格 ABC 已完成 · 第 11–12 批','固定人数、场景、成员、背景和早期过程已经串联。6/3 同图双向 GS +3.269/+3.955，C3−C1 Q +7.865（36 图）；K4 小池两个实际辅助端点已接续。',BASE/'workbench/index.html')
for rel in ['research/workers/personnel_v21_reselection_20261029/composition/exact_small_pool_policies_OPPJOINT_K4/README.md','research/data/releases/v2.1/personnel_reselection_dependencies/README.md']:
 p=REPO/rel
 mdinsert(p,f'''## 2026-11-04 K4 小池辅助消费者接续

下文及原 CSV 保留 **自动版** 的冻结结果。当前 57 组批准人工顺序中，两个精确端点命中本 K4 小池政策的实际前缀：rPc6DW4iMge-06 / other_space_10 的 n4，以及 uNb9QFRL6hY-88 / other_space_22 的 n3。成员、池、参考和输入已核对，原 1,046 个可评端点数值不变，新增两端使可评端点成为 1,048/1,081。

辅助版的高历史 Q / 多转折 / 历史快类早期平均 Q 差分别为 **+1.534 / +1.526 / −1.926**，对应自动版 +1.500 / +1.491 / −1.900，质量方向保持。15 个有前缀池、14 图/8 楼；原无 Q 不按 0 分算改善。新增两端均低于80/90，这两个阈值的首次/持续概率未因辅助接续改变。

当前引用：[完整说明]({link(p,BASE/'curves/REPORT_ZH.html')})、[辅助与自动汇总]({link(p,BASE/'curves/K4_EARLY_QUALITY_ALL_SUPPORT_SUMMARY.csv')})、[实际消费者变化]({link(p,BASE/'curves/K4_MANUAL_ASSISTED_CONSUMER_CHANGES.csv')})。政策、类别、类内随机规则保持；未新增融合、评分或新政策选队。''')
p=REPO/'docs/thesis_main/MIXTURE_PATTERNS_C13_HALF_20261104.md';p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(f'''# 混合人群规律与 C1↔C3 半队替换（2026-11-04）

当前入口：[完整整合报告]({link(p,BASE/'REPORT_ZH.html')})、[离线研究台]({link(p,BASE/'workbench/index.html')})、[逐条结论]({link(p,BASE/'CONCLUSION_LEDGER.csv')})、[方法与范围]({link(p,BASE/'METHODS_AND_SCOPE.md')})。

第11批接续既有联盟、配比、成员、背景、自然路径和K4小池实际辅助消费者；第12批完成当前DSTRUCT C1↔C3的50%严格ABC、整合报告及入口。当前分类、参考、有效预处理和历史自动结果保留。新的随机团队仅对应用户指定的C1↔C3缺口。

核心规律是结构信息的补充与稀释、困难/遮挡放大、配比均值与成员波动并存、背景吸收换人幅度，以及早期类别构成改善接近参考的过程。首次高Q、持续质量、记录劳动和逐边几何稳定分别评价。所有具体结论和反向图片均在当前入口中按真实支持报告。
''',encoding='utf-8');changed.append(str(p.relative_to(REPO)))
(BASE/'audit'/'UPDATED_PROJECT_ENTRIES.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2))
print(json.dumps({'updated':len(changed),'paths':changed},ensure_ascii=False))
