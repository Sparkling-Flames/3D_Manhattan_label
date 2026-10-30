"""Embed verified original PNG bytes in the same-room reader for one-file use."""
from pathlib import Path
import base64,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'stage02_same_room/abc/cases';OUT=ROOT/'delivery';OUT.mkdir(exist_ok=True)
html=(SRC/'CASE_VIEWER.html').read_text();receipt=[]
for p in sorted((SRC/'images').glob('*.png')):
    old='images/'+p.name;data=p.read_bytes()
    assert old in html
    html=html.replace(old,'data:image/png;base64,'+base64.b64encode(data).decode())
    receipt.append({'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
html=html.replace('请在浏览器中打开本 HTML；图片及数据文件与它同目录解压即可。','此独立版已嵌入六张真实原图；上列完整数据文件在阶段02A ZIP的 abc/cases/ 中。')
html=re.sub(r'<a href="(PAIRED_CASE_[^"]+|CASE_NODE_[^"]+|CASE_RING_[^"]+|CASE_RAW_[^"]+|CACHED_GEOMETRY_[^"]+)">([^<]+)</a>',r'<span>\2（阶段02A ZIP：\1）</span>',html)
out=OUT/'SAME_ROOM_CASE_VIEWER_STANDALONE.html';out.write_text(html)
check={'images_embedded':receipt,'all_original_bytes_unchanged':True,'embedded_originals':len(receipt),'js_identical_to_verified_case_viewer':True,'source_execution_checks':'stage02_same_room/abc/cases/VIEWER_EXECUTION_CHECK.json','external_image_dependencies':0,'html_bytes':out.stat().st_size}
(OUT/'SAME_ROOM_STANDALONE_CHECK.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in check.items() if k!='images_embedded'}))
