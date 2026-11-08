from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Draw the B candidate explanatory plan; all dimensions are estimates, not registered GT.')
parser.add_argument('--output',type=Path,default=ROOT/'06_candidate_B_plan.png')
parser.add_argument('--font',type=Path,default=ROOT/'assets/fonts/NotoSansCJK-Regular.ttc')
args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(1400,1450),'white');d=ImageDraw.Draw(im);f=lambda s:ImageFont.truetype(str(args.font),s)
def p(x,y):return (90+(x+1.1)*100,130+(3-y)*100)
def line(a,b,c='#555555',w=8):d.line([p(*a),p(*b)],fill=c,width=w)
def rect(a,b,c):d.rectangle([p(a[0],b[1]),p(b[0],a[1])],fill=c,outline='#999999',width=2)
def txt(x,y,t,s=22,c='black'):d.text(p(x,y),t,font=f(s),fill=c)
d.text((40,25),'06 B候选：浅沙发区＋后侧支段，整体后界仍未建',font=f(32),fill='black')
rect((3.87,-2.78),(6,3),'#f1f0ec');txt(4.05,2.45,'未确认后侧范围',25);txt(4.05,1.95,'不补外围/家具',23);txt(4.05,1.45,'不认定冰箱口',23)
line((-1.08,-7.15),(-1.08,3),'#329cb1',5);line((3.8,-7.15),(3.8,-3.85));line((1.735,-2.85),(6,-2.85));line((3.8,-3.915),(6,-3.915));line((3.8,-2.85),(3.8,3))
rect((3.8,-3.85),(6,-2.92),'#dbe8e5');txt(4,-3.15,'净宽 0.93m',22,'#246e63')
rect((2.56,-6.975),(3.7,-3.925),'#e2dcce');rect((1.65,-6.975),(3.62,-5.955),'#e2dcce');txt(2.65,-4.8,'完整L沙发',19);txt(2.65,-5.25,'不缩短',19)
rect((1.43,-1.4),(2.45,.90),'#d2d4d4');txt(1.53,.2,'岛台',21);txt(1.53,-.2,'2.30m',21)
rect((3.155,-2.25),(3.765,1.775),'#bea887');rect((1.68,-2.775),(3.765,-2.25),'#bea887');rect((1.91,1.83),(3.05,2.35),'#858d91');rect((3.075,1.83),(3.695,2.35),'#675747');txt(1.95,2.7,'冰箱 / 烤箱列',18)
for y in [-.92,-.25,.42]:rect((.84,y-.21),(1.26,y+.21),'#efefef')
line((2.45,-.3),(3.155,-.3),'#a54433',3);txt(2.46,-.45,'0.705',18,'#a54433')
txt(1.5,1.60,'端部净距0.93',19,'#a54433');txt(1.3,-1.65,'端部净距0.85',19,'#a54433')
for y in [3-i*.3 for i in range(21)]:line((6.1,y),(6.1,y-.14),'#44837b',3)
# explanatory legend beside plan
x=890
for i,t in enumerate(['可审模型内已建：','• 原柜前比例保留','• 返回柜/灰墙 +0.30m','• 岛台/三凳/水槽适配','• 约0.93m后侧支段','• 柜后墙可能是内隔','  这仍是候选解释','','淡灰/虚线区域：','• 整体后侧可能更深','• 不是真实外边界','• 不填充完整房间','• 冰箱到23路线未证实','','玻璃端墙与已封收口不动。','后侧如何绕接该端墙未知。']):d.text((x,170+i*47),t,font=f(23),fill='#444444')
d.text((50,1220),'所有新尺寸为审核候选，不是GT标定。23门未配准，当前不另造门洞。',font=f(25),fill='black')
d.text((50,1270),'新增支段展示约2.2m深，末端开放仅表示未建范围；不等同真实走道终点。',font=f(25),fill='black')
d.text((50,1320),'照片灰后退实面存在，但位置未定，已移出渲染；正式v3工程完全未改。',font=f(25),fill='black')
im.save(args.output)
