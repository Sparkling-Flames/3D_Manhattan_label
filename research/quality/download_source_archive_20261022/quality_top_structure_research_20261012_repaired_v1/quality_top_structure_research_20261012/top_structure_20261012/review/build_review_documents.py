#!/usr/bin/env python3
"""Create two self-contained reading documents, with a strict blind/research split."""
from __future__ import annotations
import argparse,base64,hashlib,html,io,json,re
from pathlib import Path
from html.parser import HTMLParser
import numpy as np
from PIL import Image

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def esc(x):return html.escape(str(x))
def jpg_url(path):
    path=Path(path)
    if path.suffix.lower() in {'.jpg','.jpeg'}:b=path.read_bytes()
    else:
        buf=io.BytesIO();Image.open(path).convert('RGB').save(buf,format='JPEG',quality=92);b=buf.getvalue()
    return 'data:image/jpeg;base64,'+base64.b64encode(b).decode('ascii')
def img(path,alt,caption=''):
    return f'<figure><img src="{jpg_url(path)}" alt="{esc(alt)}"><figcaption>{esc(caption)}</figcaption></figure>'
CSS='''
:root{--ink:#202b36;--muted:#586775;--border:#d6dde4;--pale:#f5f7f9;--green:#0fa568;--orange:#e59a18;--blue:#006acc}
*{box-sizing:border-box}body{margin:0;background:#f0f3f5;color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif}
main{max-width:1220px;margin:auto;background:white;padding:42px 48px 70px}h1{font-size:30px;line-height:1.4;margin:0 0 14px}h2{font-size:24px;margin:0 0 20px;line-height:1.4}h3{font-size:19px;margin:20px 0 10px}p{margin:10px 0 15px}
.kicker{color:var(--muted);font-size:13px;letter-spacing:.07em}.lead{font-size:18px}.meta{color:var(--muted);font-size:14px}.note{border-left:4px solid #7d94a7;background:var(--pale);padding:12px 18px;margin:20px 0}
nav{display:flex;gap:10px;flex-wrap:wrap;border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:13px 0;margin:26px 0}nav a{display:block;padding:4px 12px;border-radius:4px;color:#155686;background:#eaf2f9;text-decoration:none}
section{padding-top:30px;margin-top:35px;border-top:2px solid var(--border);scroll-margin-top:18px}figure{margin:18px 0}img{display:block;width:100%;height:auto}figcaption{font-size:13px;line-height:1.6;color:var(--muted);padding:7px 4px}details{border:1px solid var(--border);padding:8px 14px;border-radius:5px;margin:14px 0;background:#fafbfd}summary{cursor:pointer;font-weight:600}.legend{display:flex;flex-wrap:wrap;gap:18px;padding:13px 0}.legend span{display:inline-flex;align-items:center;gap:7px}.swatch{width:26px;height:4px;display:inline-block}.green{background:var(--green)}.orange{background:var(--orange)}.blue{background:var(--blue)}
.question{background:#f2f6fa;border:1px solid #bdcddd;border-radius:6px;padding:20px 22px;margin-top:24px}.question strong{font-size:18px}.choices{display:flex;gap:9px;flex-wrap:wrap;margin:15px 0 8px}.choices span{border:1px solid #c7d4de;border-radius:4px;padding:4px 12px;background:white}.options-note{font-size:14px;color:var(--muted)}.case{margin:24px 0;padding-top:5px}.case-title{border-left:5px solid #6b8192;padding-left:12px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0}th,td{text-align:left;vertical-align:top;padding:10px 12px;border:1px solid var(--border)}th{background:#edf2f6}code,pre{font-family:ui-monospace,Consolas,monospace;font-size:13px}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#f0f3f5;padding:14px;border-radius:4px}a{color:#155686}.small{font-size:13px}.nowrap{white-space:nowrap}
@media(max-width:720px){main{padding:26px 18px}h1{font-size:25px}h2{font-size:22px}body{font-size:15px}.question{padding:15px}table{font-size:12px}th,td{padding:7px}}
@media print{body{background:white}main{padding:0;max-width:none}nav{display:none}section{break-before:page;border:0}details{display:block}details>*{display:block}figure,.question{break-inside:avoid}img{max-height:24cm;object-fit:contain}}
'''
def page(title,content):return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+CSS+'</style></head><body><main>'+content+'</main></body></html>'
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
def question(q):
    s='<div class="question"><strong>'+esc(q['question_id'])+' · '+esc(q['prompt'])+'</strong>'
    if q.get('context'):s+='<p>'+esc(q['context'])+'</p>'
    s+='<div class="choices">'+''.join('<span>'+esc(o)+'</span>' for o in q['options'])+'</div>'
    if q.get('optional'):s+='<p class="options-note">'+esc(q['optional'])+'</p>'
    return s+'<p class="options-note">可直接回复“问题编号＋选择＋一句理由”。留空表示未回答。</p></div>'

def numerical_case_evidence(c):
    o=c['current_formal_input'];p=np.asarray(o['points_1024x512']);idx=o['ordered_source_point_indices'];raw=np.asarray(o['before_preprocessing_points'])[idx]
    alpha=(.5-p[::2,1]/512)*np.pi;beta=(p[1::2,1]/512-.5)*np.pi
    r=1/np.tan(beta);v=r*np.tan(alpha);top=np.asarray(c['frozen_annotation_geometry']['top3d'])
    assert np.max(abs(v-top[:,1]))<1e-10
    delta=(raw[1::2,0]-raw[::2,0]+512)%1024-512
    return {'blind_id':c['blind_id'],'case_id':c['case_id'],'record_id':c['record_id'],'formula':'r/h=cot(beta_bottom); vertical_top/h=(r/h)*tan(alpha_top); wall_height/h=1+vertical_top/h',
            'per_pair':[{'ordered_pair_index_one_based':i+1,'source_point_indices_zero_based':idx[2*i:2*i+2],
                         'raw_top_x':float(raw[2*i,0]),'raw_bottom_x':float(raw[2*i+1,0]),'shared_x':float(p[2*i,0]),
                         'top_y':float(p[2*i,1]),'bottom_y':float(p[2*i+1,1]),'signed_pair_dx_px':float(delta[i]),
                         'signed_pair_delta_azimuth_deg':float(delta[i]*360/1024),'radius_over_camera_height':float(r[i]),
                         'top_vertical_over_camera_height':float(v[i]),'wall_height_over_camera_height':float(1+v[i])} for i in range(len(v))],
            'analytic_matches_frozen_vertical_max_abs':float(np.max(abs(v-top[:,1]))),
            'top_vertical_min':float(v.min()),'top_vertical_max':float(v.max()),
            'reference_top_vertical_values':[float(x[1]) for x in c['fixed_reference_geometry']['top3d']]}

class VisibleText(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.text=[];self.external=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        for k,v in attrs:
            if k in {'href','src'} and v.startswith(('http:','https:','file:')):self.external.append(v)
    def handle_endtag(self,tag):
        if tag in self.tags:self.tags.remove(tag)
    def handle_data(self,data):
        if 'style' not in self.tags and 'script' not in self.tags:self.text.append(data)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--review-dir',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--candidate-json',type=Path,help='Optional research-only list of current candidate records keyed by record_id; never read by blind rendering.')
    args=ap.parse_args();r=args.review_dir.resolve();data=read(r/'inputs/review_inputs.json');notes=read(r/'research_selection_notes.json');qs=read(r/'review_questions_blind.json')
    records={c['blind_id']:c for c in data['records']};numeric=[numerical_case_evidence(c) for c in data['records']]
    (r/'results/per_case_analytic_geometry.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2)+'\n')
    legend='<div class="legend"><span><i class="swatch green"></i>当前固定参考</span><span><i class="swatch orange"></i>当前编辑后、共享x前的输入</span><span><i class="swatch blue"></i>共享x后的存档重建</span></div>'
    chunks=['<p class="kicker">布局质量复核 · 用户版 · 研究轮次 20261012</p><h1>七份作答，五组问题（末组可选）</h1>',
        '<p class="lead">请结合原图、输入点位及三维结果，判断每份作答与图中当前参考之间的差异。可以回答介于两档、各有问题难以排序、无法判断，或参考需要确认。</p>',
        '<p>无需指定分数。每组用“问题编号＋选择＋一句理由”即可；可以只回答最有把握的部分。空白表示未回答。</p>',legend,
        '<div class="note"><p>橙色点来自当前编辑版本，蓝色图来自既有冻结坐标；本轮只重新绘图。橙色连接使用存档配对与环顺序，不能据此认定标注者意图已获确认，也没有从这些橙点推断新的三维房间。</p>'
        '<p>ERP中顶部点的y不同，不直接等于实体顶面高低不同。请结合三维图判断。底面与两组三维视角使用固定相机坐标和物理轴比例，h表示同一个固定相机高度，坐标不是米；没有对标注进行对齐或缩放。底面“＋”是相机。</p>'
        '<p>这些是定向复核材料，部分图片此前可能见过；隐藏评分信息不使它们成为完全未曝光的独立测试集。</p></div>',
        '<nav>'+''.join('<a href="#'+q['question_id']+'">'+q['question_id']+' · '+' / '.join(q['blind_ids'])+'</a>' for q in qs['questions'])+'</nav>']
    for q in qs['questions']:
        chunks.append('<section id="'+q['question_id']+'"><h2>'+q['question_id']+' · '+' / '.join(q['blind_ids'])+'</h2>')
        if q['question_id']=='P01':chunks.append('<p>同一张图、同一个固定参考。两份底面与三维图的坐标范围、轴比例和观察方向完全相同。</p>')
        if q.get('context'):chunks.append('<p>'+esc(q['context'])+'</p>')
        seen=set()
        for bid in q['blind_ids']:
            c=records[bid]
            if c['image_id'] not in seen:
                seen.add(c['image_id']);chunks.append('<details open><summary>'+esc(bid if len(q['blind_ids'])==1 else (' / '.join(q['blind_ids']) if q['question_id']=='P01' else bid))+' · 无叠线原图</summary>'+img(r/c['photo']['relative_path'],'原图','原始全景未改动，网页中显示尺寸不改变图像坐标。')+'</details>')
            chunks.append('<div class="case"><h3 class="case-title">'+bid+'</h3>')
            chunks.append(img(r/'figures'/f'{bid}_input_processed.jpg',bid+'输入与处理后叠线','上：当前编辑后、共享x前的输入；下：共享x后的存档重建。绿色均为同一当前固定参考。'))
            chunks.append('<details><summary>'+bid+' · 查看局部放大与平均前后差异</summary>'+img(r/'figures'/f'{bid}_details.jpg',bid+'局部放大','橙色点与线为当前输入；蓝色叉与线为共享x后的存档结果。裁剪只放大原像素，未移动点线。')+'</details>')
            if q['question_id']!='P01':chunks.append(img(r/'figures'/f'{bid}_geometry.jpg',bid+'底面与三维','同一固定相机坐标。两组三维图为正交投影、物理轴比例；只显示冻结坐标形成的线框。'))
            chunks.append('</div>')
        if q['question_id']=='P01':chunks.append(img(r/'figures/B01_B02_same_scale_geometry.jpg','B01与B02同尺度比较','同一参照、同一坐标范围、同一物理轴比例、相同的两个观察方向。没有为了让形状贴近而重新对齐。'))
        chunks.append(question(q));chunks.append('</section>')
    chunks.append('<section><h2>可选补充</h2><p>'+esc(qs['optional_shared_input_note']['prompt'])+'</p><p class="meta">材料仅用于本轮开发复核。你的新回答将另存，不覆盖旧回执；未回答的问题保持未回答。</p></section>')
    blind=page(qs['title'],''.join(chunks));bp=r/'review_blind_user_20261012.html';bp.write_text(blind,encoding='utf-8')
    parser=VisibleText();parser.feed(blind);visible='\n'.join(parser.text)
    forbidden=[c['case_id'] for c in data['records']]+[c['record_id'] for c in data['records']]+[c['image_code'] for c in data['records']]+['Q_v11','Q_no_topS','Hmean','Hlocal','Hstar','IoU','stage13','γ','候选','预期答案']
    hits=[s for s in forbidden if s in visible]
    assert not hits,hits;assert not parser.external,parser.external
    # Every research-only value is appended after the blind document is already
    # written and checked, so it cannot flow into the user HTML accidentally.
    researcher=['<p class="kicker">布局质量复核 · 研究版 · 研究轮次 20261012</p><h1>选例依据、来源核验与判断后果</h1>',
        '<p class="lead">这份文件含匿名映射与研究解释，不宜与用户版一起展示后再声称盲审。七份均是已曝光开发材料；图像观察由本轮研究者记录，不构成新的人工等级。T07在本轮候选敏感性后追加为可选复核例，不是新独立验证。</p>',
        '<h2>匿名映射与资格边界</h2>']
    rows=[]
    for c in data['records']:
        o=c['current_formal_input'];ledger=c.get('screen_eligibility_record') or {}
        rows.append([c['blind_id'],c['case_id']+' / '+c['record_id'],c['image_code'],o['condition'],o['pairing_basis'],o['order_status'],str(o['ring_confirmed']),o['scene_oos_status']+' / '+o['scene_doorway_status']])
    researcher.append(table(['盲ID','研究ID','图片','采集条件','配对来源','环状态','人工确认环','OOS / 门洞标记'],rows))
    researcher.append('<p>七份本次均核对到 source＝current-before；这只是选中七份的事实，不能推广到其他已编辑记录。已有配对可复用，环仍未人工确认；未命中已知资格障碍不表示参考重新验收。参考对象由旧有效链固定，没有按分数选择。</p>')
    researcher.append('<h2>为什么这五组值得问</h2>')
    for q in notes['decision_questions']:
        researcher.append('<h3>'+esc(q['question_id'])+' · '+esc(' / '.join(q['cases']))+'</h3><p>'+esc(q['why_selected'])+'</p>')
        researcher.append(table(['回答情况','影响的研究决定'],[(k.replace('if_',''),v) for k,v in q.items() if k.startswith('if_')]))
    researcher.append('<h2>独立视觉核查与解析几何</h2><p>本轮看过6张原始2048×1024 PNG，并核对7份当前前处理点、共享后点和冻结三维坐标。以下描述不是用户新标签，也不据此改变参考资格。</p>')
    researcher.append('<p>对合法的既有顶底对：α＝π(0.5−y<sub>top</sub>/512)，β＝π(y<sub>bottom</sub>/512−0.5)，r/h＝cotβ；顶部竖直坐标v/h＝(r/h)tanα，墙高/h＝1＋v/h。相机在v＝0，地板在v＝−h。由ERP公式逐点复算并与冻结顶点比较，差异均小于10<sup>−10</sup>h。</p>')
    for c,num in zip(data['records'],numeric):
        obs=notes['case_observations'][c['blind_id']]
        researcher.append('<h3>'+esc(c['blind_id']+' · '+c['case_id']+' / '+c['record_id'])+'</h3>')
        researcher.append('<p><strong>可观察现象：</strong>'+esc(obs['observed'])+'</p><p><strong>混杂与限度：</strong>'+esc(obs['confounds']+' '+obs['interpretation_limit'])+'</p>')
        researcher.append(table(['既有第几对','顶 y','底 y','r/h','顶部 v/h','墙高/h','平均前 Δx(px)'],
            [[p['ordered_pair_index_one_based'],f"{p['top_y']:.3f}",f"{p['bottom_y']:.3f}",f"{p['radius_over_camera_height']:.5f}",f"{p['top_vertical_over_camera_height']:.5f}",f"{p['wall_height_over_camera_height']:.5f}",f"{p['signed_pair_dx_px']:.5f}"] for p in num['per_pair']]))
        researcher.append(img(r/'figures'/f'{c["blind_id"]}_geometry.jpg',c['case_id']+'几何证据'))
    researcher.append('<div class="note"><h3>S107是“ERP top y不能直接解释实体高低”的真实反例</h3><p>门外新增第3对的top y较大，但由于相应底点更接近地平线，重建深度增大，其顶点v/h约0.88568，高于其余约0.50432～0.59506。不能将ERP中看似向下的折线写成三维顶面下降。此处还混有对象范围扩展；这个例子不单独标定高度惩罚。</p></div>')
    candidate_path=args.candidate_json or (r/'inputs/research_candidate_subset.json' if (r/'inputs/research_candidate_subset.json').is_file() else None)
    if candidate_path:
        candidates=read(candidate_path)
        original_candidate_sha=candidates.get('candidate_source_sha256',sha(candidate_path)) if isinstance(candidates,dict) else sha(candidate_path)
        if isinstance(candidates,dict):candidates=candidates.get('records',candidates.get('cases',[]))
        if not isinstance(candidates,list):raise TypeError('Candidate JSON must contain a list of records')
        chosen={c['record_id']:c for c in candidates if isinstance(c,dict) and c.get('record_id') in {x['record_id'] for x in data['records']}}
        focus=[('Q_v11','v1.1'),('Q_top_1_16','顶项γ=1/16'),('Q_no_topS','去顶项S'),('Q_split_local025','整体/中心化局部高度，局部尺度0.25')]
        score_rows=[]
        for c in data['records']:
            val=chosen.get(c['record_id'])
            if val is not None:score_rows.append([c['case_id']]+[f'{float(val[k]):.4f}' if val.get(k) is not None else '不可计算' for k,_ in focus])
        researcher.append('<h2>本轮重点候选分数（仅研究版）</h2><p>来自主研究的有限候选输出；这些值完全没有进入用户版。它们是计算结果，不是用户指定分数或新人工等级。其他候选保留在主研究完整逐例表。</p>')
        researcher.append(table(['作答']+[label for _,label in focus],score_rows))
        if 'R00678' in chosen:
            x=chosen['R00678']
            researcher.append('<h3>T07的原始输入诊断（仅研究版）</h3><p>下表是有限敏感性候选；8°尺度没有被解释为人工阈值。该例同时有未表达的小折转、壁炉附近多余分段、定位与遮挡，不能用它独立证明X罚项有效。</p>')
            researcher.append(table(['去顶部S','再乘X RMS项','再乘X最大值项','原始X RMS(°)','原始X最大值(°)'],[[f"{x[k]:.5f}" for k in ['Q_no_topS','Q_no_top_Xrms8','Q_no_top_Xmax8','X_rms_deg','X_max_deg']]]))
        source_meta={'candidate_source_sha256':original_candidate_sha,'candidate_source_path':str(candidate_path),'records':list(chosen.values()),'focus_methods':[k for k,_ in focus]}
        if args.candidate_json:(r/'inputs/research_candidate_subset.json').write_text(json.dumps(source_meta,ensure_ascii=False,indent=2)+'\n')
        researcher.append('<p class="small">本次读取候选来源SHA256：<code>'+source_meta['candidate_source_sha256']+'</code>。主体公式为100IC/[1+Sb²/32+γSt²/32+(H*/0.5)²]；分开高度候选则使用(Hmean/0.5)²+(Hcenter/0.25)²，保留同一C和底项。Hcenter定义与适用性见主研究代码及报告。</p>')
    else:researcher.append('<h2>候选数值来源</h2><p>本视图包不独立拟合或重调候选。实际候选分数与参数敏感性由本轮主研究结果表提供；本研究版目前只给出判断如何改变取舍，未把上一轮分数重新命名为本轮新结果。</p>')
    researcher.append('<h2>绘图与输入来源</h2><p>所有图在本轮由冻结数据重新生成；使用正交投影、两组固定视角和物理坐标轴比例。B01/B02共用轴限，局部裁剪也相同。橙色球面连线仅沿既有环连接当前输入射线，没有推断不共享x的三维房间。</p>')
    researcher.append(table(['输入','文件SHA256'],[(k,v['sha256']) for k,v in data['provenance'].items()]))
    researcher.append(table(['原图','分辨率','SHA256'],[(p['image_code'],'2048×1024',p['sha256']) for p in read(r/'inputs/selected_original_images.json')]))
    researcher.append('<h2>运行</h2><pre>python render_user_figures.py --review-dir .\npython build_review_documents.py --review-dir .</pre><p>上面两步只读取随包精确子集；完整来源恢复脚本prepare_review_inputs.py需要父研究的原始正式输入。没有改写原标注、人工回执、参考或正式资格。</p>')
    rp=r/'review_researcher_20261012.html';rp.write_text(page('顶部与结构复核研究版',''.join(researcher)),encoding='utf-8')
    output={'blind_html':{'path':bp.name,'sha256':sha(bp),'bytes':bp.stat().st_size},'research_html':{'path':rp.name,'sha256':sha(rp),'bytes':rp.stat().st_size},
        'anonymity_check':{'visible_text_forbidden_identifiers_found':hits,'external_assets':parser.external,'quality_values_loaded_into_blind_document':False,'answer_fields_all_null':all(q['answer'] is None and q['comment'] is None for q in qs['questions'])},
        'case_count':len(records),'question_groups':len(qs['questions']),'source_original_count':len({x['image_id'] for x in records.values()}),
        'analytic_geometry_checks_all_passed':True,'visual_observation_is_researcher_not_human_relabel':True}
    (r/'results/document_checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output,ensure_ascii=False))

if __name__=='__main__':main()
