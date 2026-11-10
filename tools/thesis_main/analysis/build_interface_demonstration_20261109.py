"""Reconstruct a local interface using an archived annotation and the actual viewer."""
from pathlib import Path
import base64
import json
import math
import html as html_lib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/fusion/interface_demonstration_20261109'
SOURCE = 'export_label/人工精标/project-20-at-2026-03-27-14-57-e66c6481.json'
IMAGE = 'data/mp3d_layout/img_v/wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c.jpg'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    task = next(t for t in json.loads((ROOT/SOURCE).read_text(encoding='utf-8-sig')) if t['id'] == 2501)
    ann = next(a for a in task['annotations'] if a['id'] == 2613)
    points = [[v['value']['x'] * 10.24, v['value']['y'] * 5.12]
              for v in ann['result'] if v['type'] == 'keypointlabels']
    assert len(points) == 8 and IMAGE.split('/')[-1] in task['data']['image']
    corners = []
    for i in range(0, 8, 2):
        top, bottom = sorted(points[i:i+2], key=lambda p: p[1])
        delta = (bottom[0]-top[0]+512) % 1024 - 512
        corners.append(dict(x=(top[0]+delta/2) % 1024, y_ceiling=top[1], y_floor=bottom[1]))
    assert all(c['y_ceiling'] < 256 < c['y_floor'] for c in corners)
    xyz = []
    for c in corners:
        azimuth = c['x']/1024*2*math.pi-math.pi
        radius = 1.6/math.tan((c['y_floor']/512-.5)*math.pi)
        xyz.append({'floor':[radius*math.sin(azimuth),-1.6,-radius*math.cos(azimuth)],
                    'ceiling':[radius*math.sin(azimuth),-radius*math.tan((c['y_ceiling']/512-.5)*math.pi),-radius*math.cos(azimuth)]})
    payload = {'points':points,'corners':corners,
               'image':'data:image/jpeg;base64,'+base64.b64encode((ROOT/IMAGE).read_bytes()).decode()}
    (OUT/'data.js').write_text('const DEMO = '+json.dumps(payload)+';\n',encoding='utf-8')
    viewer = (ROOT/'tools/label_studio/vis_3d.html').read_text(encoding='utf-8')
    for name in ['three.min.js','OrbitControls.js']:
        viewer = viewer.replace(f'src="{name}"',f'src="../../../tools/label_studio/{name}"')
    # Presentation-only HUD removal; geometry, texture projection and orbit logic are unchanged.
    viewer = viewer.replace('</head>','<style>#info,#controls,#inspection-hud{display:none!important}</style></head>')
    (OUT/'viewer.html').write_text(viewer,encoding='utf-8')
    userscript = (ROOT/'tools/label_studio/official/ls_userscript_annotator.js').read_text(encoding='utf-8')
    style = userscript.split('function ensurePreviewControlPanelStyle()',1)[1].split('style.textContent = `',1)[1].split('`;',1)[0]
    ids = {'PREVIEW_PANEL_ID':'panel','PREVIEW_PANEL_BODY_ID':'panel-body','PREVIEW_PANEL_HEADER_ID':'panel-header'}
    for key, value in ids.items():
        style = style.replace('${'+key+'}',value)
    assert '${' not in style
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Annotation interface demonstration</title>
<style>*{box-sizing:border-box}body{margin:0;background:white;color:#222;font:16px Arial,sans-serif}main{width:1440px;padding:16px;display:flex;gap:12px}.left{width:60%;padding:8px}.right{width:40%;border-left:1px solid #ccc;padding-left:10px;position:relative}h2{font-size:20px;margin:0 0 14px;font-weight:600}.panorama{border:1px solid #eee;position:relative}.panorama svg{width:100%;display:block}iframe{width:100%;height:410px;border:0;background:#111}.labels{display:flex;gap:8px;padding:10px 4px}.label{padding:4px 12px;border-radius:3px;font-size:14px}.corner{background:#ff4d4f;color:white}.wall{background:#52c41a;color:white}.refresh{background:#007bff;color:white;border:0;border-radius:4px;padding:8px 16px;font-size:14px;cursor:pointer;margin-top:8px}.help{font-size:13px;color:#666;margin:9px 0}.toolbar{display:flex;gap:10px;align-items:center;background:#fafafa;border-top:1px solid #eee;padding:8px;font-size:13px}.toolbar button{background:white;border:1px solid #ddd;border-radius:3px;padding:3px 8px;cursor:pointer}__PANEL_STYLE__
#panel{position:absolute;right:12px;top:47px}#panel[data-collapsed="1"]{width:190px}
</style><main><section class="left"><h2>Panorama annotation</h2><div class="panorama"><svg viewBox="0 0 1024 512" id="pano" role="img" aria-label="Archived panorama with original annotated endpoints"></svg><div class="toolbar"><span>Zoom</span><button onclick="zoomPano(1.2)">+</button><button onclick="zoomPano(1/1.2)">−</button><button onclick="zoomPano(0)">Reset</button></div></div><div class="labels"><span class="label corner">● Corner</span><span class="label wall">Wall</span></div></section><section class="right"><h2>3D Layout Preview</h2><iframe id="viewer" title="Linked 3D preview"></iframe><button class="refresh" onclick="send({type:'update_layout',width:1024,height:512,corners:DEMO.corners,imageUrl:DEMO.image,inspectionMode:true})">Refresh 3D Preview</button><div class="help">Drag to rotate · Scroll to zoom</div>
<div id="panel" data-collapsed="1"><div id="panel-header"><div><div class="hp-title">Preview order</div><div class="hp-slot" id="slot">Pair 1 / 4</div></div><button class="hp-toggle" id="toggle">Expand</button></div><div id="panel-body"><div class="hp-note">Changes the 3D preview only.</div><div class="hp-section"><div class="hp-label">Select pair</div><div class="hp-row"><button onclick="order('prev_pair')">Previous</button><button onclick="order('next_pair')">Next</button></div></div><div class="hp-section"><div class="hp-label">Swap current pair</div><div class="hp-row"><button onclick="order('swap_prev')">With previous</button><button onclick="order('swap_next')">With next</button></div></div><div class="hp-section"><div class="hp-label">Save and reset</div><div class="hp-row"><button class="hp-primary" onclick="order('save')">Save</button><button onclick="order('reset_default_order')">Reset</button></div><div class="hp-row"><button class="hp-warn" onclick="order('delete_saved_override')">Clear saved order</button></div></div></div></div></section></main>
<script>let panoZoom=1;function zoomPano(f){panoZoom=f?panoZoom*f:1;const w=1024/panoZoom,h=512/panoZoom;document.getElementById('pano').setAttribute('viewBox',[(1024-w)/2,(512-h)/2,w,h].join(' '));}</script>''' + '<script src="data.js"></script><script>\nconst frame=document.getElementById(\'viewer\');window.demoReady=false;window.demoMessages=[];\nconst send=d=>frame.contentWindow.postMessage(d,\'*\');\nfunction preset(p){send({type:\'hohonet_inspection_command\',command:\'camera_preset\',preset:p});}\nwindow.addEventListener(\'message\',e=>{if(e.source!==frame.contentWindow)return;const d=e.data;window.demoMessages.push({type:d.type,status:d.status});\n if(d.type===\'hohonet_viewer_ready\')send({type:\'update_layout\',width:1024,height:512,corners:DEMO.corners,imageUrl:DEMO.image,inspectionMode:true});\n if(d.type===\'hohonet_texture_status\'&&d.status===\'loaded\'){preset(\'isometric\');window.demoReady=true;}\n});\nconst ns=\'http://www.w3.org/2000/svg\',svg=document.getElementById(\'pano\');\nconst img=document.createElementNS(ns,\'image\');img.setAttribute(\'href\',DEMO.image);img.setAttribute(\'width\',\'1024\');img.setAttribute(\'height\',\'512\');svg.appendChild(img);\nfor(let i=0;i<DEMO.points.length;i++){let [x,y]=DEMO.points[i];let circle=document.createElementNS(ns,\'circle\');circle.setAttribute(\'cx\',x);circle.setAttribute(\'cy\',y);circle.setAttribute(\'r\',5);circle.setAttribute(\'fill\',\'#ef4261\');circle.setAttribute(\'stroke\',\'white\');circle.setAttribute(\'stroke-width\',\'1.3\');svg.appendChild(circle);let txt=document.createElementNS(ns,\'text\');txt.setAttribute(\'x\',x+9);txt.setAttribute(\'y\',y-8);txt.setAttribute(\'fill\',\'white\');txt.setAttribute(\'stroke\',\'#303030\');txt.setAttribute(\'stroke-width\',\'2.5\');txt.setAttribute(\'paint-order\',\'stroke\');txt.setAttribute(\'font-size\',\'16\');txt.textContent=String(Math.floor(i/2)+1);svg.appendChild(txt);}\nfunction order(action,extra={}){send({type:\'hohonet_preview_order_command\',action,...extra});}\nwindow.addEventListener(\'message\',e=>{if(e.source===frame.contentWindow&&e.data.type===\'hohonet_preview_order_state\'){document.getElementById(\'slot\').textContent=\'Pair \'+e.data.selectedPairNumber+\' / \'+e.data.pairCount;}});\ndocument.getElementById(\'toggle\').onclick=()=>{const p=document.getElementById(\'panel\');p.dataset.collapsed=p.dataset.collapsed===\'1\'?\'0\':\'1\';document.getElementById(\'toggle\').textContent=p.dataset.collapsed===\'1\'?\'Expand\':\'Collapse\';};\nframe.src=\'viewer.html\';\n</script></html>'
    (OUT/'index.html').write_text(html.replace('__PANEL_STYLE__',style),encoding='utf-8')
    feedback_xml = 'tools/label_studio/config_history/scope_instruction_v1_pre_block2/en/label_studio_view_config_manual_en.xml'
    config = ET.parse(ROOT/feedback_xml).getroot()
    answers = {r['from_name']:r['value']['choices'] for r in ann['result'] if r['type']=='choices'}
    forms = []
    mapping = {}
    for field in ['scope','difficulty']:
        choices = config.find(".//Choices[@name='"+field+"']")
        mapping[field] = {c.attrib['alias']:c.attrib['value'] for c in choices}
        assert set(answers[field]) <= set(mapping[field])
        rows = []
        for alias,label in mapping[field].items():
            kind = 'radio' if field=='scope' else 'checkbox'
            checked = ' checked' if alias in answers[field] else ''
            rows.append('<label><input type="'+kind+'" name="'+field+'"'+checked+'> '+html_lib.escape(label)+'</label>')
        forms.append('<section class="feedback-box"><h3>'+('1. Scope' if field=='scope' else '2. Difficulty')+'</h3>'+''.join(rows)+'</section>')
    feedback = html.replace('__PANEL_STYLE__',style)
    feedback = feedback.replace('</style>', '.feedback-box{padding:12px;margin:10px 0;border:1px solid #f0f0f0;background:#fdfdfd;border-radius:6px}.feedback-box h3{font-size:24px;color:#1890ff;margin:0 0 10px}.feedback-box label{display:flex;align-items:baseline;gap:7px;font-size:22px;line-height:1.3;margin:10px 0}.feedback-box input{accent-color:#1890ff;width:18px;height:18px;flex-shrink:0}.feedback-title{font-size:25px;border-bottom:2px solid #1890ff;padding-bottom:5px;display:inline-block;margin:10px 0} </style>')
    feedback = feedback.replace('</section><section class="right">','<h3 class="feedback-title">Annotation Feedback and Stratification</h3>'+''.join(forms)+'</section><section class="right">',1)
    feedback = feedback.replace('id="panel" data-collapsed="1"','id="panel" data-collapsed="0"').replace('id="toggle">Expand','id="toggle">Collapse')
    feedback = feedback.replace('</style>', '#panel{position:static;width:100%;margin-top:24px;background:rgba(40,44,50,.95)}#panel .hp-title{font-size:24px}#panel .hp-slot,#panel .hp-note,#panel .hp-label,#panel button{font-size:22px}#panel-header{padding:12px 14px}#panel-body{padding:12px 14px}#panel .hp-row{margin-top:10px;gap:10px}#panel .hp-section{margin-top:14px;padding-top:12px}#panel .hp-row button{padding:9px 12px} </style>')
    (OUT/'interface_feedback.html').write_text(feedback,encoding='utf-8')
    (OUT/'FEEDBACK_SOURCE.json').write_text(json.dumps({'kind':'reconstructed_scope_difficulty_interface','xml_source':feedback_xml,'annotation_source':SOURCE,'task_id':2501,'annotation_id':2613,'option_labels':mapping,'saved_answers':{k:answers[k] for k in mapping},'identity_note':'Archived annotation verifies saved fields and selections. Historical XML supplies option labels and styling; exact deployment wording on the annotation date is not established. Instruction/hint text is omitted. Model-initialization feedback is outside this Manual scope/difficulty demonstration; no claim of complete historical task form.'},ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'SOURCE.json').write_text(json.dumps({'kind':'reconstructed_interface_demonstration',
        'image':IMAGE,'annotation_source':SOURCE,'task_id':2501,'annotation_id':2613,
        'viewer_source':'tools/label_studio/vis_3d.html','points_pixels':points,'preview_corners':corners,'preview_xyz':xyz,
        'presentation_changes':'60/40 layout and label colors from manual XML; floating preview-order panel CSS from official annotator userscript; English labels and cropped task form. Actual viewer geometry/shaders unchanged. Reconstructed demonstration, not a captured historical session.',
        'scope':'Same panorama as historical screenshot. Archived annotation is not asserted to be the exact unsaved screenshot state. No GT/experimental score or participant-performance result is represented.',
        'pairing':'Stored adjacent pairs; upper/lower by vertical coordinate; circular horizontal midpoint. Stored pair order preserved. Camera height 1.6 as in viewer, scale convention not a measured room dimension.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(OUT)


if __name__=='__main__': main()

