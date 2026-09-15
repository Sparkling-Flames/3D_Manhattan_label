#!/usr/bin/env python3
"""Build a self-contained coordinate review page for simulated annotators.

Input: RUN_DIR/review_cases.json. Coordinates use a 1024 x 512 panorama,
with adjacent top/bottom points. Point order is preserved. Lines are only
coordinate illustrations, not a projection of recovered 3D walls.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


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
@media(max-width:1000px){.layout{grid-template-columns:1fr}.panel{max-height:none}.toolbar{gap:12px}body{padding:16px}}
</style></head><body>
<h1>不同标注者模拟试验</h1>
<p class="muted">从同一张全景图出发，检查模型、真人与模拟样本的坐标差异。</p>
<div class="notice"><strong>模拟样本不计入真人标注。</strong> 本页模拟基于离线模型预测与训练楼栋的经验分布，无新视觉推理。本轮仅模拟候选偏好与坐标变化，尚未模拟门洞范围等语义判断。模拟结果需要独立真人数据验证。</div>
<div class="toolbar">
<label>图片 <select id="caseSelect" aria-label="选择图片"></select></label>
<button id="previous" type="button">上一张</button><button id="next" type="button">下一张</button>
<label>模拟方法 <select id="methodSelect" aria-label="选择模拟方法"></select></label>
<label>标注透明度 <input id="opacity" type="range" min="0.1" max="1" step="0.05" value="0.9"><output id="opacityValue">90%</output></label>
<button id="reset" type="button">恢复单个模拟对比</button>
</div>
<p id="methodInfo" class="muted" style="margin-bottom:16px;font-size:14px"></p>
<div class="layout"><div class="viewer">
<canvas id="canvas" width="1024" height="512" aria-label="全景图标注坐标示意"></canvas>
<div class="caption"><div class="legend"><span><i class="dot" style="background:#f8d44c"></i>模型预测</span><span><i class="dot" style="background:#36dbf0"></i>真人标注</span><span><i class="dot" style="background:#ff777b"></i>模拟标注</span></div>
<p id="caseInfo"></p><p class="muted">坐标画布为 1024 × 512。相邻上下点成对，保留输入点序，横向接缝按周期连接。直线仅表示坐标连接，不代表三维墙面投影。</p></div>
<div id="selectedInfo" class="selected"></div></div><aside id="panel" class="panel" aria-label="标注显示选择"></aside></div>
<script id="review-data" type="application/json">__DATA__</script>
<script>
"use strict";
const cases=JSON.parse(document.getElementById('review-data').textContent), W=1024,H=512;
const groups=['models','human','synthetic'], titles={models:'模型预测',human:'真人标注',synthetic:'模拟标注'}, colors={models:'#f8d44c',human:'#36dbf0',synthetic:'#ff777b'};
const methodNames={hohonet:'HoHoNet 固定结果',uniform:'随机选择模型候选',pooled:'总体经验分布',worker:'个人历史倾向'};
const methodNotes={hohonet:'固定使用同一份 HoHoNet 预测，作为无个体差异的对照。',uniform:'等概率选择已有模型候选，作为随机差异的对照。',pooled:'按训练楼栋总体经验选择候选，并抽取同族同点数的历史坐标残差。',worker:'按个人历史倾向选择候选；个人残差不足时使用总体经验。历史倾向仅表示坐标接近程度。'};
const $=id=>document.getElementById(id), ctx=$('canvas').getContext('2d');
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
const version=++loadId;img=new Image();img.onload=()=>{if(version===loadId)draw()};img.src=c.image_data;resetSelection()}
function makeText(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
function renderPanel(){$('methodInfo').textContent=methodNotes[method()]??'可按方法筛选模拟样本，勾选具体样本查看坐标差异。';const panel=$('panel');panel.replaceChildren();groups.forEach(g=>{const section=document.createElement('section');section.className='group';const title=document.createElement('label');title.className='group-title';
const toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=visible[g];toggle.onchange=()=>{visible[g]=toggle.checked;draw()};title.append(toggle,makeText('span',titles[g]));section.append(title);
let count=0;cases[current][g].forEach((row,i)=>{if(!eligible(g,i))return;count++;const label=document.createElement('label');label.className='person';const box=document.createElement('input');box.type='checkbox';box.checked=chosen[g].has(i);box.onchange=()=>{if(box.checked)chosen[g].add(i);else chosen[g].delete(i);draw()};
const name=document.createElement('span'),dot=document.createElement('i');dot.className='dot';dot.style.background=colors[g];name.append(dot,document.createTextNode(row.name??`样本 ${i+1}`));
if(g==='synthetic')name.append(makeText('small',`方法：${row.method??'未标明'}；几何状态：${row.geometry_status??'未提供'}`));
label.append(box,name);section.append(label)});if(!count)section.append(makeText('p','暂无此类结果'));panel.append(section)})}
function segment(a,b){const ax=mod(a[0],W),dx=mod(b[0]-ax+W/2,W)-W/2;[-W,0,W].forEach(shift=>{ctx.moveTo(ax+shift,a[1]);ctx.lineTo(ax+shift+dx,b[1])})}
function drawRow(row,color){const p=row.points;ctx.beginPath();for(let i=0;i<p.length;i+=2)segment(p[i],p[i+1]);for(let role=0;role<2;role++){const ring=p.filter((_,i)=>i%2===role);ring.forEach((a,i)=>segment(a,ring[(i+1)%ring.length]))}
ctx.strokeStyle='#09121d';ctx.lineWidth=5;ctx.stroke();ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();p.forEach((q,i)=>{ctx.beginPath();ctx.arc(mod(q[0],W),q[1],4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#09121d';ctx.lineWidth=1;ctx.stroke()})}
function draw(){ctx.clearRect(0,0,W,H);if(img.complete&&img.naturalWidth)ctx.drawImage(img,0,0,W,H);ctx.globalAlpha=Number($('opacity').value);const lines=[];groups.forEach(g=>{if(!visible[g])return;chosen[g].forEach(i=>{if(!eligible(g,i))return;const row=cases[current][g][i];drawRow(row,colors[g]);lines.push(`${titles[g]}：${row.name??`样本 ${i+1}`}，${row.points.length/2} 对角点${g==='synthetic'?`，${row.method??'未标明方法'}，几何状态 ${row.geometry_status??'未提供'}`:''}`)})});ctx.globalAlpha=1;$('selectedInfo').replaceChildren(...(lines.length?lines.map(t=>makeText('p',t)):[makeText('p','当前仅显示原图。')]));}
$('caseSelect').onchange=()=>switchCase(Number($('caseSelect').value));$('previous').onclick=()=>switchCase(current-1);$('next').onclick=()=>switchCase(current+1);
$('methodSelect').onchange=()=>{chosen.synthetic=new Set();const i=cases[current].synthetic.findIndex((_,i)=>eligible('synthetic',i));if(i>=0)chosen.synthetic.add(i);renderPanel();draw()};
$('opacity').oninput=()=>{$('opacityValue').textContent=`${Math.round(Number($('opacity').value)*100)}%`;draw()};$('reset').onclick=resetSelection;switchCase(0);
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
    html_path.write_text(HTML.replace("__DATA__", data), encoding="utf-8")
    sheet_path = run_dir / "contact_sheet.png"
    create_contact_sheet(cases, sheet_path)
    print(json.dumps({"cases": len(cases), "review_html": str(html_path),
                      "contact_sheet": str(sheet_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
