#!/usr/bin/env python3
"""Build a self-contained panorama and relative-3D annotation review page.

Input: RUN_DIR/review_cases.json. Coordinates use a 1024 x 512 panorama,
with adjacent top/bottom points. Point order is preserved. Lines are only
coordinate illustrations. The optional 3D view uses raw rays without fitting.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from tools.thesis_main.analysis.simulated_annotators_3d import reconstruct_for_review


WIDTH, HEIGHT = 1024, 512
GROUPS = ("models", "human", "synthetic")
COLORS = {"models": "#f8d44c", "human": "#36dbf0", "synthetic": "#ff777b"}
IDENTITIES = {"models": "模型预测", "human": "真人标注", "synthetic": "模拟标注"}


def periodic_segments(a, b):
    """Return line segments clipped at the panorama's periodic horizontal seam."""
    ax, ay = float(a[0]) % WIDTH, float(a[1])
    dx = (float(b[0]) - ax + WIDTH / 2) % WIDTH - WIDTH / 2
    bx, by = ax + dx, float(b[1])
    for shift in (-WIDTH, 0, WIDTH):
        x0, x1 = ax + shift, bx + shift
        if max(x0, x1) < 0 or min(x0, x1) > WIDTH:
            continue
        lo, hi = 0.0, 1.0
        if dx:
            t0, t1 = (0 - x0) / dx, (WIDTH - x0) / dx
            lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
        if lo <= hi:
            yield ((x0 + dx * lo, ay + (by - ay) * lo),
                   (x0 + dx * hi, ay + (by - ay) * hi))


def coordinate_edges(points):
    """Connect pairs and each ordered role ring without sorting input points."""
    for i in range(0, len(points), 2):
        yield points[i], points[i + 1]
    for role in (0, 1):
        ring = points[role::2]
        if len(ring) > 1:
            for i, point in enumerate(ring):
                yield point, ring[(i + 1) % len(ring)]


def load_cases(run_dir):
    payload = json.loads((run_dir / "review_cases.json").read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise ValueError("review_cases.json must contain a nonempty cases list")
    for case in cases:
        path = Path(case["image_path"])
        if not path.is_absolute() or not path.is_file():
            raise ValueError(f"Image must be an existing absolute path: {path}")
        for group in GROUPS:
            rows = case.setdefault(group, [])
            if not isinstance(rows, list):
                raise ValueError(f"{case['image_id']}: {group} must be a list")
            for row in rows:
                points = row.get("points", [])
                if len(points) < 4 or len(points) % 2:
                    raise ValueError(f"{case['image_id']}: {row.get('name')} needs paired points")
                for point in points:
                    if (not isinstance(point, (list, tuple)) or len(point) != 2
                            or any(not isinstance(v, (float, int)) or not math.isfinite(v)
                                   for v in point)):
                        raise ValueError(f"{case['image_id']}: invalid point {point!r}")
                row['geometry3d'] = reconstruct_for_review(row, group)
        with Image.open(path) as source:
            original = ImageOps.exif_transpose(source).convert("RGB")
            panorama = original.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        panorama.save(buf, format="JPEG", quality=88)
        case["image_data"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return cases


def font(size):
    for path in ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/STHeiti Light.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def fit_text(draw, text, face, width):
    text = str(text)
    if draw.textlength(text, font=face) <= width:
        return text
    while text and draw.textlength(text + "…", font=face) > width:
        text = text[:-1]
    return text + "…"


def create_contact_sheet(cases, path):
    """Render up to four cases with one example of each explicitly named group."""
    cell_w, image_h, header_h = 512, 256, 66
    margin, top, bottom = 20, 100, 55
    rows = cases[:4]
    sheet = Image.new("RGB", (margin * 2 + cell_w * 3,
                              top + len(rows) * (image_h + header_h + margin) + bottom), "#111923")
    draw = ImageDraw.Draw(sheet)
    title_font, label_font, small_font = font(27), font(19), font(15)
    draw.text((margin, 15), "不同标注者模拟试验 · 坐标示意", fill="white", font=title_font)
    draw.text((margin, 55), "模拟样本不计入真人数据。使用离线模型与训练楼栋经验分布，无新视觉推理。",
              fill="#c9d3df", font=label_font)
    for row_idx, case in enumerate(rows):
        img_bytes = base64.b64decode(case["image_data"].split(",", 1)[1])
        with Image.open(io.BytesIO(img_bytes)) as source:
            panorama = source.convert("RGB")
        y = top + row_idx * (image_h + header_h + margin)
        for col, group in enumerate(GROUPS):
            x = margin + col * cell_w
            selected = case[group][0] if case[group] else None
            if group == "synthetic":
                selected = next((r for r in case[group] if r.get("method") == "worker"), selected)
            draw.text((x + 8, y), fit_text(draw, f"{IDENTITIES[group]} · {case['image_id']}",
                                         label_font, cell_w - 16),
                      fill=COLORS[group], font=label_font)
            detail = selected.get("name", "未命名") if selected else "无可用结果"
            if selected and group == "synthetic":
                detail += " / " + str(selected.get("method", "未标明方法"))
            draw.text((x + 8, y + 30), fit_text(draw, detail, small_font, cell_w - 16),
                      fill="#c9d3df", font=small_font)
            overlay = panorama.copy()
            line_draw = ImageDraw.Draw(overlay)
            if selected:
                points = selected["points"]
                for a, b in coordinate_edges(points):
                    for start, end in periodic_segments(a, b):
                        line_draw.line([start, end], fill="#101010", width=7)
                        line_draw.line([start, end], fill=COLORS[group], width=4)
                for px, py in points:
                    px %= WIDTH
                    line_draw.ellipse((px - 5, py - 5, px + 5, py + 5),
                                      fill=COLORS[group], outline="black", width=1)
            sheet.paste(overlay.resize((cell_w, image_h), Image.Resampling.LANCZOS),
                        (x, y + header_h))
    draw.text((margin, sheet.height - 39),
              "保留输入点序；横向接缝按周期连接。直线仅表示坐标连接，不代表三维墙面投影。",
              fill="#c9d3df", font=label_font)
    sheet.save(path)


def create_3d_contact_sheet(cases, path):
    """Static visual QA for simple, hard and doorway cases using shared scales."""
    selected = []
    for kinds in (('simple', '简单'), ('hard', '困难'), ('unclassified_doorway', '单列')):
        case = next((c for c in cases if c.get('image_type') in kinds and c not in selected), None)
        if case is not None:
            selected.append(case)
    if not selected:
        selected = cases[:3]
    cell_w, cell_h, header = 500, 350, 90
    sheet = Image.new('RGB', (cell_w * 3 + 40, header + len(selected) * cell_h + 50), '#111923')
    draw = ImageDraw.Draw(sheet)
    face, small = font(18), font(14)
    draw.text((20, 14), '标注 3D 线框 · 同图共享视角与尺度', fill='white', font=font(25))
    draw.text((20, 53), '相机离地高度 = 1；墙顶距离由配对底点估算；保持原始环序。', fill='#bdcad8', font=face)
    for j, case in enumerate(selected):
        rows = [next((r for r in case[g] if r['geometry3d']['status'] in ('available', 'wireframe_warning')),
                     case[g][0] if case[g] else None) for g in GROUPS]
        all_points = [[0, 0, 0], [0, -1, 0]]
        for row in rows:
            if row is None or row['geometry3d']['status'] == 'unavailable':
                continue
            g = row['geometry3d']
            all_points.extend(g['floor'])
            all_points.extend(p for p in g['top'] if p is not None)
        lo = [min(p[i] for p in all_points) for i in range(3)]
        hi = [max(p[i] for p in all_points) for i in range(3)]
        center = [(a + b) / 2 for a, b in zip(lo, hi)]
        radius = max(.5, max(math.dist(p, center) for p in all_points))
        for col, (group, row) in enumerate(zip(GROUPS, rows)):
            ox, oy = 20 + col * cell_w, header + j * cell_h
            def project(p):
                x, y, z = [v - c for v, c in zip(p, center)]
                yaw, pitch = math.radians(-35), math.radians(25)
                u = x * math.cos(yaw) - z * math.sin(yaw)
                depth = x * math.sin(yaw) + z * math.cos(yaw)
                v = y * math.cos(pitch) - depth * math.sin(pitch)
                scale = 270 * .4 / radius
                return ox + cell_w / 2 + u * scale, oy + 210 - v * scale
            draw.text((ox + 5, oy), fit_text(draw, IDENTITIES[group] + ' · ' + case['image_id'], face, cell_w - 20), fill=COLORS[group], font=face)
            detail = row.get('name', '') if row else '无标注'
            draw.text((ox + 5, oy + 28), fit_text(draw, detail, small, cell_w - 20), fill='#bdcad8', font=small)
            for k in range(5):
                x, z = lo[0] + (hi[0] - lo[0]) * k / 4, lo[2] + (hi[2] - lo[2]) * k / 4
                draw.line([project([x, -1, lo[2]]), project([x, -1, hi[2]])], fill='#29384a', width=1)
                draw.line([project([lo[0], -1, z]), project([hi[0], -1, z])], fill='#29384a', width=1)
            if row is not None and row['geometry3d']['status'] != 'unavailable':
                g = row['geometry3d']
                rings = [g['floor']]
                if all(p is not None for p in g['top']):
                    rings.append(g['top'])
                for ring in rings:
                    draw.line([project(p) for p in ring + ring[:1]], fill=COLORS[group], width=2)
                if len(rings) == 2:
                    for a, b in zip(*rings):
                        draw.line([project(a), project(b)], fill=COLORS[group], width=2)
                message = '原始线框；环序或配对待确认' if g['issues'] else '相对尺度还原'
            else:
                message = '无法还原：' + ', '.join(row['geometry3d']['issues']) if row else '无可用标注'
            p = project([0, 0, 0])
            draw.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill='white')
            draw.text((p[0] + 6, p[1]), '相机', fill='#bdcad8', font=small)
            draw.text((ox + 5, oy + cell_h - 30), fit_text(draw, message, small, cell_w - 20), fill='#bdcad8', font=small)
    draw.text((20, sheet.height - 35), '各组首个可还原样本；黄 = 模型，青 = 真人，红 = 模拟。保留自交和墙顶起伏。', fill='#bdcad8', font=face)
    sheet.save(path)


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>不同标注者模拟试验</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,"PingFang SC",sans-serif;color:#e8edf4;background:#101721}
*{box-sizing:border-box}body{margin:0;padding:24px;max-width:1600px;margin:auto}h1{font-size:26px;margin:0 0 10px}
p{line-height:1.65;margin:6px 0}.muted{color:#a6b6c9}.notice{padding:12px 16px;border:1px solid #7e6436;border-radius:10px;background:#29251d;margin:16px 0}
.toolbar{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:18px 0}.toolbar label{display:flex;gap:8px;align-items:center}
select,button{background:#1a293a;color:#f5f8fc;border:1px solid #526276;border-radius:7px;padding:8px;font:inherit;max-width:100%}
button{cursor:pointer}input{accent-color:#5fc2ee}input[type=range]{width:120px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px}
.viewer,.panel{background:#18222f;border:1px solid #314155;border-radius:12px;overflow:hidden}.viewer{align-self:start}canvas{display:block;width:100%;height:auto;background:#080c12}
.caption{padding:12px 16px;font-size:13px}.panel{padding:14px;max-height:750px;overflow:auto}.group{margin:0 0 16px}.group-title{font-weight:650;display:flex;gap:8px;align-items:center;margin-bottom:8px}
.person{display:flex;gap:8px;align-items:flex-start;margin:8px 0;padding:7px 6px;background:#111b27;border-radius:6px;font-size:13px;overflow-wrap:anywhere}
.person input{margin-top:3px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}.person small{display:block;color:#9caec3;margin-top:3px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:7px}.selected{padding:0 18px 16px;overflow-wrap:anywhere;font-size:13px}.empty{font-size:13px;color:#9caec3}
#views{display:grid;grid-template-columns:minmax(0,1fr)}#views[data-view=split]{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.view-pane{min-width:0}.view-pane h2{font-size:15px;margin:0;padding:10px 14px;background:#1c2b3d}.view-pane+ .view-pane{border-left:1px solid #314155}
#canvas3d{height:420px;touch-action:none;cursor:grab}#canvas3d:active{cursor:grabbing}#canvas3d:focus-visible{outline:2px solid #5fc2ee;outline-offset:-2px}
.view-controls{display:flex;gap:8px;flex-wrap:wrap;padding:10px 14px}.geometry-status{font-size:12px;line-height:1.6;color:#c4d0de;padding:0 14px 14px;max-height:170px;overflow:auto}
[hidden]{display:none!important}
@media(max-width:1000px){.layout{grid-template-columns:1fr}.panel{max-height:none}.toolbar{gap:12px}body{padding:16px}}
@media(max-width:760px){#views[data-view=split]{grid-template-columns:minmax(0,1fr)}.view-pane+ .view-pane{border-left:0;border-top:1px solid #314155}}
</style></head><body>
<h1>不同标注者模拟试验</h1>
__TRIALNOTICE__
<p class="muted">从同一张全景图出发，检查模型、真人与模拟样本的坐标差异。</p>
<div class="notice"><strong>模拟样本保留合成来源。</strong> 本页使用离线模型预测与训练楼栋经验分布。时间、半自动改动和范围作答如有模拟，均保留来源与回退状态。范围作答采样不构成对当前几何范围的确认。模拟结果需要独立真人数据验证。</div>
<div class="toolbar">
<label>图片 <select id="caseSelect" aria-label="选择图片"></select></label>
<button id="previous" type="button">上一张</button><button id="next" type="button">下一张</button>
<label>模拟方法 <select id="methodSelect" aria-label="选择模拟方法"></select></label>
<label>标注透明度 <input id="opacity" type="range" min="0.1" max="1" step="0.05" value="0.9"><output id="opacityValue">90%</output></label>
<button id="reset" type="button">恢复单个模拟对比</button>
<label>视图 <select id="viewMode" aria-label="选择全景或3D视图"><option value="panorama">全景</option><option value="3d">3D</option><option value="split" selected>并排</option></select></label>
</div>
<p id="methodInfo" class="muted" style="margin-bottom:16px;font-size:14px"></p>
<div class="layout"><div class="viewer">
<div id="views" data-view="split"><section id="panoramaPane" class="view-pane"><h2>全景坐标</h2>
<canvas id="canvas" width="1024" height="512" aria-label="全景图标注坐标示意"></canvas>
</section><section id="threePane" class="view-pane"><h2>相对尺度 3D 线框</h2>
<canvas id="canvas3d" width="640" height="420" tabindex="0" aria-label="3D标注视图，拖动或方向键旋转，滚轮或加减键缩放"></canvas>
<div id="threeControls" class="view-controls"><button id="viewTop" type="button">俯视</button><button id="viewFront" type="button">正视</button><button id="viewReset" type="button">重置视角</button></div>
<div id="geometryStatus" class="geometry-status" aria-live="polite"></div></section></div>
<div class="caption"><div class="legend"><span><i class="dot" style="background:#f8d44c"></i>模型预测</span><span><i class="dot" style="background:#36dbf0"></i>真人标注</span><span><i class="dot" style="background:#ff777b"></i>模拟标注</span></div>
<p id="caseInfo"></p><p class="muted">坐标画布为 1024 × 512。相邻上下点成对，保留输入点序，横向接缝按周期连接。直线仅表示坐标连接，不代表三维墙面投影。</p></div>
<p class="caption muted">3D 以相机离地高度为 1，地面 y/h = -1；墙顶距离由配对底点估算。保留原始点序与墙顶起伏，未强制拟合曼哈顿布局。环序未确认或自交时仅显示带提示的原始线框。</p>
<div id="selectedInfo" class="selected"></div></div><aside id="panel" class="panel" aria-label="标注显示选择"></aside></div>
<script id="review-data" type="application/json">__DATA__</script>
<script>__VIEWER3D__</script>
<script>
"use strict";
const cases=JSON.parse(document.getElementById('review-data').textContent), W=1024,H=512;
const groups=['models','human','synthetic'], titles={models:'模型预测',human:'真人标注',synthetic:'模拟标注'}, colors={models:'#f8d44c',human:'#36dbf0',synthetic:'#ff777b'};
const methodNames={hohonet:'HoHoNet 固定结果',uniform:'随机选择模型候选',pooled:'总体经验分布',worker:'个人历史倾向'};
const methodNotes={hohonet:'固定使用同一份 HoHoNet 预测，作为无个体差异的对照。',uniform:'等概率选择已有模型候选，作为随机差异的对照。',pooled:'按训练楼栋总体经验选择候选，并抽取同族同点数的历史坐标残差。',worker:'按个人历史倾向选择候选；个人残差不足时使用总体经验。历史倾向仅表示坐标接近程度。'};
const $=id=>document.getElementById(id), ctx=$('canvas').getContext('2d');
const viewer3d=SimulatedReview3D.create($('canvas3d'),$('geometryStatus'));
let current=0,img=new Image(),loadId=0,visible={models:true,human:false,synthetic:true},chosen={models:new Set(),human:new Set(),synthetic:new Set()};
const mod=(x,m)=>(x%m+m)%m;
cases.forEach((c,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${c.image_id} · 楼栋 ${c.building_id??'未标明'}`;$('caseSelect').append(o)});
function method(){return $('methodSelect').value}
function eligible(group,i){return group!=='synthetic'||method()==='__all__'||String(cases[current][group][i].method??'未标明方法')===method()}
function resetSelection(){groups.forEach(g=>{chosen[g]=new Set();const n=cases[current][g].findIndex((_,i)=>eligible(g,i));if(n>=0)chosen[g].add(n)});visible={models:true,human:false,synthetic:true};renderPanel();draw()}
function switchCase(index){current=mod(index,cases.length);$('caseSelect').value=current;const c=cases[current];const old=method();$('methodSelect').replaceChildren();
const methods=[...new Set(c.synthetic.map(r=>String(r.method??'未标明方法')))];
[['__all__','全部方法'],...methods.map(m=>[m,methodNames[m]??m])].forEach(([v,t])=>{const o=document.createElement('option');o.value=v;o.textContent=t;$('methodSelect').append(o)});
if(methods.includes(old))$('methodSelect').value=old;else if(methods.includes('worker'))$('methodSelect').value='worker';else if(methods.length)$('methodSelect').value=methods[0];
$('caseInfo').textContent=`图片 ${c.image_id} · 楼栋 ${c.building_id??'未标明'} · 真人 ${c.human.length} 份 · 模拟 ${c.synthetic.length} 份`;
const version=++loadId;img=new Image();img.onload=()=>{if(version===loadId)draw()};img.src=c.image_data;resetSelection();viewer3d.reset()}
function makeText(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
function renderPanel(){$('methodInfo').textContent=methodNotes[method()]??'可按方法筛选模拟样本，勾选具体样本查看坐标差异。';const panel=$('panel');panel.replaceChildren();groups.forEach(g=>{const section=document.createElement('section');section.className='group';const title=document.createElement('label');title.className='group-title';
const toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=visible[g];toggle.onchange=()=>{visible[g]=toggle.checked;draw()};title.append(toggle,makeText('span',titles[g]));section.append(title);
let count=0;cases[current][g].forEach((row,i)=>{if(!eligible(g,i))return;count++;const label=document.createElement('label');label.className='person';const box=document.createElement('input');box.type='checkbox';box.checked=chosen[g].has(i);box.onchange=()=>{if(box.checked)chosen[g].add(i);else chosen[g].delete(i);draw()};
const name=document.createElement('span'),dot=document.createElement('i');dot.className='dot';dot.style.background=colors[g];name.append(dot,document.createTextNode(row.name??`样本 ${i+1}`));
if(g==='synthetic'){
name.append(makeText('small',`方法：${row.method??'未标明'}；几何状态：${row.geometry_status??'未提供'}`));
name.append(makeText('small',`画像匹配：${row.profile_found??'未记录'}；实际残差：${row.residual_source??'未记录'}；回退：${row.residual_fallback_reason??row.profile_fallback_reason??'无'}`));
name.append(makeText('small',`条件：${row.condition??'未记录'}；时间：${row.active_time_seconds??'缺失'} 秒；Semi：${row.semi_status??'未记录'}；范围作答：${row.worker_scope_response??'缺失'}`));}
if(g==='synthetic'&&row.lead_time_status){
name.append(makeText('small',`活动时间状态 ${row.timing_status??'缺失'}；lead_time ${row.lead_time_seconds??'缺失'} 秒（${row.lead_time_status}）；供体 ${row.lead_time_donor_annotation_id??'无'}`));
name.append(makeText('small',`范围状态 ${row.scope_status??'缺失'}；采样层 ${row.scope_pool??'缺失'}；范围意向 ${row.scope_variant??'不适用'}；仅为采样回应，不构成几何裁决。`));
if(row.condition==='semi')name.append(makeText('small',`Semi 初始提案见模型栏同名 S 人员；行为 ${row.semi_behavior??'未支持'}；用途 ${row.semi_purpose??'未记录'}；供体 ${row.semi_donor_annotation_id??'无'}`));}
if(g==='synthetic'&&row.source_profile){
const q=row.source_profile.axes?.quality?.effect,t=row.source_profile.axes?.time?.effect;
name.append(makeText('small',`来源画像：质量 ${row.source_profile.quality}，速度 ${row.source_profile.speed}；训练 WQ 相对效应 ${q==null?'缺失':q.toFixed(2)}；log 时间效应 ${t==null?'缺失':t.toFixed(2)}`));
if(row.mixture_weights)name.append(makeText('small',`供体 W${row.residual_donor_worker_id??'缺失'}；个人 ${(row.mixture_weights.personal*100).toFixed(0)}%，同类 ${(row.mixture_weights.prototype*100).toFixed(0)}%，总体 ${(row.mixture_weights.pooled*100).toFixed(0)}%`));
if(!row.evaluation?.length)name.append(makeText('small','生成结果：该图暂无获准的完整参考，不评分。'));
for(const e of row.evaluation??[]){const text=e.WQ==null?'无法评分：'+(e.reason_codes??[]).join('；'):`生成结果 WQ ${e.WQ.toFixed(1)} / 100，3D IoU ${e.IoU3D100==null?'缺失':e.IoU3D100.toFixed(1)} / 100`;
const detail=makeText('small',text);detail.setAttribute('title',e.reference_id??'');name.append(detail);}}
name.append(makeText('small','3D：'+SimulatedReview3D.describe(row.geometry3d)));
label.append(box,name);section.append(label)});if(!count)section.append(makeText('p','暂无此类结果'));panel.append(section)})}
function segment(a,b){const ax=mod(a[0],W),dx=mod(b[0]-ax+W/2,W)-W/2;[-W,0,W].forEach(shift=>{ctx.moveTo(ax+shift,a[1]);ctx.lineTo(ax+shift+dx,b[1])})}
function drawRow(row,color){const p=row.points;ctx.beginPath();for(let i=0;i<p.length;i+=2)segment(p[i],p[i+1]);for(let role=0;role<2;role++){const ring=p.filter((_,i)=>i%2===role);ring.forEach((a,i)=>segment(a,ring[(i+1)%ring.length]))}
ctx.strokeStyle='#09121d';ctx.lineWidth=5;ctx.stroke();ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();p.forEach((q,i)=>{ctx.beginPath();ctx.arc(mod(q[0],W),q[1],4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#09121d';ctx.lineWidth=1;ctx.stroke()})}
function draw(){ctx.clearRect(0,0,W,H);if(img.complete&&img.naturalWidth)ctx.drawImage(img,0,0,W,H);ctx.globalAlpha=Number($('opacity').value);const lines=[],selected=[];groups.forEach(g=>{if(!visible[g])return;chosen[g].forEach(i=>{if(!eligible(g,i))return;const row=cases[current][g][i];drawRow(row,colors[g]);selected.push({row,color:colors[g],title:titles[g]});lines.push(`${titles[g]}：${row.name??`样本 ${i+1}`}，${row.points.length/2} 对角点${g==='synthetic'?`，${row.method??'未标明方法'}，几何状态 ${row.geometry_status??'未提供'}`:''}`)})});ctx.globalAlpha=1;viewer3d.update(selected,Number($('opacity').value));$('selectedInfo').replaceChildren(...(lines.length?lines.map(t=>makeText('p',t)):[makeText('p','当前仅显示原图。')]));}
function setViewMode(mode){$('views').dataset.view=mode;$('viewMode').value=mode;$('panoramaPane').hidden=mode==='3d';$('threePane').hidden=mode==='panorama';draw();}
$('caseSelect').onchange=()=>switchCase(Number($('caseSelect').value));$('previous').onclick=()=>switchCase(current-1);$('next').onclick=()=>switchCase(current+1);
$('methodSelect').onchange=()=>{chosen.synthetic=new Set();const i=cases[current].synthetic.findIndex((_,i)=>eligible('synthetic',i));if(i>=0)chosen.synthetic.add(i);renderPanel();draw()};
$('opacity').oninput=()=>{$('opacityValue').textContent=`${Math.round(Number($('opacity').value)*100)}%`;draw()};$('reset').onclick=resetSelection;
$('viewMode').onchange=()=>setViewMode($('viewMode').value);$('viewTop').onclick=viewer3d.top;$('viewFront').onclick=viewer3d.front;$('viewReset').onclick=viewer3d.reset;switchCase(0);
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path,
                        help="Directory containing review_cases.json")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    cases = load_cases(run_dir)
    data = json.dumps(cases, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html_path = run_dir / "review.html"
    viewer_script = Path(__file__).with_name('simulated_annotators_review_3d.js').read_text(encoding='utf-8')
    acceptance_path = run_dir / 'trial_acceptance.json'
    notice = ''
    if acceptance_path.exists() and json.loads(acceptance_path.read_text()).get('overall_trial_passed') is False:
        notice = '<div class="notice"><strong>本轮分层生成方案尚未通过整体验收，继续停在试点。</strong>角点分布有所改善，个人质量误差与几何问题仍需修复。来源人员画像仅描述训练证据，单份生成标注请结合独立评分和几何状态审看。当前产物仅供本地研究。</div>'
    html_path.write_text(HTML.replace("__TRIALNOTICE__", notice).replace("__VIEWER3D__", viewer_script).replace("__DATA__", data), encoding="utf-8")
    geometry_path = run_dir / 'review_geometry3d.json'
    geometry_path.write_text(json.dumps(dict(schema='annotation_review_3d_v1', cases=[
        dict(image_id=c['image_id'], **{g: [dict(index=i, name=r.get('name'), geometry3d=r['geometry3d'])
             for i, r in enumerate(c[g])] for g in GROUPS}) for c in cases]),
        ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    sheet_path = run_dir / "contact_sheet.png"
    create_contact_sheet(cases, sheet_path)
    create_3d_contact_sheet(cases, run_dir / 'contact_sheet_3d.png')
    print(json.dumps({"cases": len(cases), "review_html": str(html_path),
                      "contact_sheet": str(sheet_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
