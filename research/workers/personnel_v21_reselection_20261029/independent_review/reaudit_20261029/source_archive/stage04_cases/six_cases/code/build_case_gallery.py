#!/usr/bin/env python3
"""Build a local, self-contained navigation page for the six frozen cases."""
from pathlib import Path
import html
import pandas as pd

root = Path(__file__).resolve().parents[1]
s = pd.read_csv(root / "results/CASE_SUMMARY.csv")
summaries = {
 "7y3sRwLe3Va-04": ("高分集中，Q 微变但几何仍响应", "四角各16票，结构相同；AC 角距和底面差异均大于 AB。无需额外范围裁定。"),
 "B6ByNegPMKs-48": ("四角满票，定位及顶边共同偏差", "Q 与 IoU3D 的变化方向不同。人工可核对两端停止边和主顶面/梁底边界；当前参考保持。"),
 "uNb9QFRL6hY-40": ("同类成员在远角上跨过门槛", "远角 A7、B10、C6票；同类 B 从五角变六角。看缝边 x≈0、4 的远近两条边及遮挡地面落点。"),
 "x8F5xyUWy9e-08": ("两个互斥8人组同时入选，连接失败", "局部 x≈144、155 两组各8票，没有来源环覆盖全部五个入选组。人工区分同角定位误差与不同边界表达。"),
 "jtcxE69GiFV-13": ("跨类补短折，伴随共同背景对应调整", "两个短折达到8/9票；Q 提升18.44分，来源匹配记录劳动量增加12.58%。共同D的W106观测发生重分组。"),
 "S9hNv5qa7GM-09": ("已固定范围下的旧分支部分过线", "当前四角目标已由用户裁定。两个旧分支角各8票、另一角7票，当前停止边也8票，最终连接失败。无需重复裁定范围。"),
}

def q(v):
 return "不可评" if pd.isna(v) else f"{float(v):.4f}"

h = ["""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOHONET v2.1 · 普通 Manual 严格 ABC 机制案例</title><style>
:root{font-family:system-ui,'Noto Sans CJK SC',sans-serif;color:#172737;background:#edf2f5}body{max-width:1260px;margin:auto;padding:30px}h1{font-size:30px}h2{font-size:23px}p{line-height:1.7}a{color:#17668d}nav{display:flex;flex-wrap:wrap;gap:10px}nav a{padding:8px 12px;background:#e4eef4;border-radius:6px}section{background:white;border:1px solid #d4dfe6;border-radius:10px;padding:22px;margin:24px 0}table{border-collapse:collapse;display:block;overflow-x:auto}th,td{padding:9px 12px;border-bottom:1px solid #dce4e8;text-align:left;white-space:nowrap}th{background:#eff5f8}img{display:block;width:100%;height:auto;margin-top:14px;border:1px solid #dce4e8}small,.muted{color:#586a76}code{font-size:.88em;word-break:break-all}summary{cursor:pointer;font-weight:600;padding:12px 0}.tag{display:inline-block;padding:4px 8px;background:#e9f3ef;color:#27664e;border-radius:4px}.links{display:flex;gap:14px;flex-wrap:wrap}
</style><body><h1>普通 Manual 严格 ABC：六个机制案例</h1>
<p>全部为 n=16、m=8，D/X/Y/Z 真实互斥，A=D+X、B=D+Y、C=D+Z。类别来自留楼外历史；本页是在完整实验后按机制选出的案例，不代表总体比例。失败 Q 留空，不计零分。</p>
<p class="links"><a href="CASE_MECHANISM_REVIEW_ZH.md">完整中文机制报告</a><a href="results/CASE_SUMMARY.csv">案例数值总表</a><a href="results/CASE_EXACT_EVENT_ROWS.csv">精确设计与成员</a><a href="results/CASE_EXACT_VOTE_GROUPS.csv">完整票账</a><a href="results/MECHANISM_AUDIT_RECEIPT.json">来源与核验</a></p><nav>"""]
for r in s.itertuples():
 h.append(f'<a href="#{r.event_id}">{r.image}</a>')
h.append("</nav><section><h2>同类、跨类幅度与方向</h2><table><thead><tr><th>图片</th><th>方法/当前折方向</th><th>Q A/B/C</th><th>B−A</th><th>C−A</th><th>C−B</th><th>对称跨幅度−同类</th></tr></thead><tbody>")
for r in s.itertuples():
 h.append(f'<tr><td>{r.image}</td><td>{r.method}<br>{r.source_class}→{r.target_class}</td><td>{q(r.Q_A)} / {q(r.Q_B)} / {q(r.Q_C)}</td><td>{q(r.Q_B_minus_A)}</td><td>{q(r.Q_C_minus_A)}</td><td>{q(r.Q_C_minus_B)}</td><td>{q(r.Q_symmetric_gap)}</td></tr>')
h.append('</tbody></table><p class="muted">同类 |B−A|；对称跨类 (|C−A|+|C−B|)/2。类别号仅对相应方法和留楼外折有定义。</p></section>')
for r in s.itertuples():
 title, summary = summaries[r.image]
 base = f"figures/{r.event_id}"
 h.append(f'<section id="{r.event_id}"><span class="tag">{r.image} · {r.source_class}→{r.target_class}</span><h2>{title}</h2><p>{summary}</p><p class="muted">事件 <code>{r.event_id}</code> · {r.method}</p>')
 h.append(f'<p class="links"><a href="originals/{r.image}.png">原始全景图</a><a href="{base}/RAW_ANSWERS.csv">原答及人员</a><a href="{base}/VOTE_GROUPS_WITH_BLOCKS.csv">分块票账</a><a href="{base}/COMMON_D_GROUP_LINKS.csv">共同 D 对应关系</a><a href="traces/{r.event_id}.json.gz">完整重放状态</a><a href="{base}/ERP_BEV.pdf">PDF</a></p>')
 h.append(f'<img src="{base}/ERP_BEV.png" loading="lazy" alt="{r.image}全景及底面实际几何">')
 if (root / base / "LOCAL_CRITICAL_VOTES.png").exists():
  h.append(f'<details open><summary>关键局部与逐组票数</summary><img src="{base}/LOCAL_CRITICAL_VOTES.png" loading="lazy" alt="关键局部和支持门槛"></details>')
 h.append(f'<details><summary>三维代理与完整支持票</summary><img src="{base}/3D_VOTES.png" loading="lazy" alt="三维及投票"></details></section>')
h.append('<p class="muted">图像均由冻结原答和实际融合状态绘制。三维按相机高归一；失败仅画入选点，不补造完整环。六例18臂的标量复现误差≤1.42×10⁻¹⁴。</p></body></html>')
(root / "index.html").write_text("\n".join(h), encoding="utf-8")
print(root / "index.html")
