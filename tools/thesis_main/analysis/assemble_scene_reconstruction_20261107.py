"""Assemble source/model checks without changing pixels, model geometry or manuscript figures."""
from pathlib import Path
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'docs/thesis_main/论文写作工作资料'
DOOR=WORK/'门洞实景观察_20261107/精细模型'
OOS=WORK/'OOS分步重建_20261107'
sys.path.insert(0,str(Path(__file__).parent/'visual_takeover_20260906'))
from render import perspective

def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf',size)

def white(path):
    im=Image.open(path).convert('RGBA')
    bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
    return bg.convert('RGB')

def place(canvas,im,rect):
    x,y,w,h=rect;im=ImageOps.contain(im,(w,h),Image.Resampling.LANCZOS)
    canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2))

def trimwhite(im):
    bounds=ImageChops.difference(im,Image.new('RGB',im.size,'white')).getbbox()
    assert bounds, 'Empty render'
    return ImageOps.expand(im.crop(bounds),border=20,fill='white')

def doorway():
    canvas=Image.new('RGB',(2400,1450),'white');d=ImageDraw.Draw(canvas)
    d.text((65,28),'Doorway: bathroom and hall',font=font(49),fill='#233b48')
    for i,name in enumerate(['main','reverse']):
        im=white(DOOR/f'doorway_{name}.png');im.save(DOOR/f'doorway_{name}.png')
        place(canvas,trimwhite(im),(i*1200,140,1200,1190))
        d.text((i*1200+65,90),['(a) Hall-side overview','(b) Bathroom-side overview'][i],font=font(30),fill='#526773')
    d.text((65,1360),'Photograph-informed reconstruction. Perimeter walls and doorway openings retained.',font=font(29),fill='#526773')
    canvas.save(DOOR/'doorway_overview.png')
    source=np.asarray(Image.open(ROOT/'data/mp3d_layout/valid/img/2t7WUuJeko7_53937db036374126830e0f1203b04ead.png').convert('RGB'))
    checks=Image.new('RGB',(2080,2180),'white');d=ImageDraw.Draw(checks)
    for i,(name,yaw,pitch,label) in enumerate([
        ('07_hall',0,0,'Hall'),('07_bath',180,0,'Basin and cupboard'),
        ('07_window',math.degrees(math.atan2(-1,-.15)),math.degrees(math.atan2(-.13,math.hypot(1,.15))),'Bathroom length')]):
        photo,_=perspective(source,yaw,pitch,w=1300,h=850,fov=90)
        d.text((25,20+i*720),label+' | photograph',font=font(30),fill='#233b48')
        d.text((1060,20+i*720),'model at the same camera',font=font(30),fill='#233b48')
        place(checks,photo,(20,65+i*720,1000,650))
        place(checks,white(DOOR/f'{name}_reprojection.png'),(1060,65+i*720,1000,650))
    checks.save(DOOR/'camera_comparison.png')
    s=json.loads((ROOT/'analysis_results/doorway_point_folding_20261107/doorway_proportion_fit.json').read_text(encoding='utf-8'))
    w=s['door_half_width'];lo=s['bathroom_bounds_xy'][3];hi=s['hall_bounds_xy'][2]
    xy=np.array([[-w,lo],[-w,hi],[w,hi],[w,lo]])-np.array(s['camera'][:2])
    u=(np.arctan2(xy[:,0],xy[:,1])/(2*np.pi)+.5)*2048
    observed=np.array([450,534,1496,1590]);assert np.max(np.abs(u-observed))<15
    overlay=Image.new('RGB',(2048,1174),'white');overlay.paste(Image.fromarray(source),(0,80));d=ImageDraw.Draw(overlay)
    d.text((22,17),'Doorway turns: observed (orange) and reconstructed (teal)',font=font(32),fill='#233b48')
    for name,a,b in zip(['L1','L2','R2','R1'],observed,u):
        d.line([(int(a),330),(int(a),930)],fill='#c56725',width=3)
        d.line([(int(b),330),(int(b),930)],fill='#207c8b',width=3)
        d.rectangle((int(b)-35,268,int(b)+35,308),fill='white')
        d.text((int(b)-25,270),name,font=font(26),fill='#207c8b')
    d.text((22,1120),'Fixed turns are separate from the open door leaf and cupboard face.',font=font(26),fill='#526773')
    overlay.save(DOOR/'turn_reprojection.png')
    (DOOR/'turn_reprojection.json').write_text(json.dumps({'observed_u':observed.tolist(),'model_u':u.tolist(),'difference_px':(u-observed).tolist(),'scope':'vertical-edge bearing only; not full-room survey accuracy'},indent=2),encoding='utf-8')

def oos():
    cases=[('oblique','Oblique wall: doorway area','test','x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23','main_render.png'),
           ('attic','Sloped ceiling','valid','S9hNv5qa7GM_53d54b73e58940019b731673e65c1902','main.png'),
           ('ceiling','Split-level ceiling','test','q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb','main.png'),
           ('stairs','Split-level floor','test','uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e','main_render.png')]
    canvas=Image.new('RGB',(2400,2500),'white');d=ImageDraw.Draw(canvas)
    for i,(key,title,split,uid,render) in enumerate(cases):
        x=(i%2)*1200;y=(i//2)*1250
        d.text((x+35,y+15),f'({chr(97+i)}) {title}',font=font(38),fill='#233b48')
        place(canvas,white(ROOT/f'data/mp3d_layout/{split}/img/{uid}.png'),(x+35,y+75,1130,400))
        place(canvas,trimwhite(white(OOS/key/render)),(x+20,y+490,1160,730))
        note={'oblique':'Local room model; only three entrance treads are shown.',
              'stairs':'Upper landing, central floor and visible downward start.'}.get(key)
        if note:d.text((x+35,y+1220),note,font=font(24),fill='#526773')
    canvas.save(OOS/'oos_reconstruction_overview.png')

if __name__=='__main__':
    if '--oos' in sys.argv:oos()
    else:doorway()
