"""Create the offline HTML report from the delivered Markdown (no network)."""
from pathlib import Path
import argparse,base64,html,json,re
import mistune

def run(root):
    text=(root/'REPORT_ZH.md').read_text(encoding='utf-8')
    md=mistune.create_markdown(escape=True,plugins=['table'])
    body=md(text)
    # Embed existing precise overlays so the separate report HTML remains usable alone.
    def embed(m):
        p=root/m.group(1)
        if not p.is_file():return m.group(0)
        return 'src="data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode()+'"'
    body=re.sub(r'src="(visual/[^\"]+)"',embed,body)
    style='''body{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;color:#1d2733;background:#fff;margin:42px auto;padding:0 24px;max-width:1080px}h1{font-size:31px;line-height:1.4}h2{font-size:23px;border-top:1px solid #d5dce5;padding-top:25px;margin-top:35px}h3{font-size:19px}table{border-collapse:collapse;width:100%;font-size:15px;margin:20px 0;display:block;overflow:auto}th,td{border-bottom:1px solid #d5dce5;padding:9px 13px;text-align:left;vertical-align:top}th{background:#edf2f7}pre{white-space:pre-wrap;background:#f3f5f8;padding:16px;border-radius:6px;font-size:14px;overflow-wrap:anywhere}code{font-family:monospace}img{width:100%;height:auto}a{color:#175285}blockquote{margin:20px 0;padding:4px 18px;border-left:4px solid #7892b0;background:#f5f7fa}p,li{overflow-wrap:anywhere}.tag{font-size:14px;color:#526174} @media print{body{margin:0;font-size:11pt}table,pre{break-inside:avoid}}'''
    out='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>上下绑定与分开按序比较｜研究报告</title><style>'+style+'</style></head><body><p class="tag">2026-09-20 / 冻结输入 / 新增对应规则实算</p>'+body+'</body></html>'
    (root/'REPORT_ZH.html').write_text(out,encoding='utf-8')
    intro='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>从这里开始</title><style>body{font:17px/1.8 system-ui,"Microsoft YaHei",sans-serif;max-width:880px;margin:50px auto;padding:20px;color:#203044}a{color:#175285}td{padding:12px;border-bottom:1px solid #ddd}</style><h1>上下绑定与分开按序：研究交付</h1><p>按本次用户要求比较相同点数、固定x序号的top与bottom；原数据不改，未确认角色和关联保留条件性。</p><table><tr><td><a href="REPORT_ZH.html">中文研究报告</a></td><td>结论、公式、案例、人员诊断、失败与限制</td></tr><tr><td><a href="ATLAS.html">全量交互图册</a></td><td>239个图片×条件单元，17个重点对，逐点原编号与上下关联</td></tr><tr><td><a href="results/focused_case_summary.csv">重点案例结果CSV</a></td><td>成对距离与最终同簇关系分开报告</td></tr><tr><td><a href="results/response_eligibility.csv">逐份资格和关联来源</a></td><td>无有效关联不伪装成单人簇</td></tr><tr><td><a href="results/worker_descriptive_summary.csv">人员描述性结果</a></td><td>同图比较、点数门影响、单人但有近邻情况</td></tr><tr><td><a href="report/SOURCE_TASK.md">原续研任务</a></td><td>本地AI原文，仅作来源，不自动视为结论</td></tr></table><p>所有数值无需联网。图册嵌入15张已有图像，其他单元只显示冻结坐标并明确标注缺少像素；不宣称239个单元均已视觉验收。重点案例中只有此前六图为已有用户裁决，其余保持来源限定。</p><p>复算：<code>python -B code/run_all.py --root .</code>。渲染HTML额外依赖Pillow/mistune，数值部分只用numpy/pandas/scipy。复算会重写派生结果，建议先复制目录。</p></html>'''
    (root/'00_START_HERE.html').write_text(intro,encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args();run(args.root)
