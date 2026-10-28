"""Draw the adopted v2 research results; source reports are linked in CONCLUSIONS_ZH.md.

This script only renders saved findings. It does not fit labels, fuse teams or score layouts.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/statistics/research_closeout_20261022/DATA_EVIDENCE_OVERVIEW_20261026.png'
W, H = 3200, 4660
im = Image.new('RGB', (W, H), '#ffffff')
d = ImageDraw.Draw(im)
INK, GRAY, BLUE, PALE, RUST = '#182d3c', '#536371', '#176a81', '#eaf1f4', '#a35b34'
FONT, BOLD = 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhbd.ttc'

def text(x, y, value, size=36, color=INK, bold=False):
    font = ImageFont.truetype(BOLD if bold else FONT, size)
    box = d.textbbox((x,y), value, font=font)
    assert box[2] <= W-55 and box[3] <= H-35, (value, box)
    d.text((x,y), value, font=font, fill=color)

def para(x,y,value,width,size=36,color=INK,bold=False,gap=13):
    font=ImageFont.truetype(BOLD if bold else FONT,size)
    lines=[]; line=''
    for char in value:
        if char=='\n': lines.append(line); line=''
        elif line and d.textlength(line+char,font=font)>width:
            lines.append(line); line=char
        else: line+=char
    if line: lines.append(line)
    for line in lines:
        text(x,y,line,size,color,bold); y+=size+gap
    return y

def rule(y,x=100,end=3100,color='#c7d2d9',width=2):
    d.line((x,y,end,y),fill=color,width=width)

def section(y,title):
    rule(y,color=INK,width=4)
    text(100,y+22,title,48,INK,True)

text(100,50,'HOHONET  ·  真人标注 v2  ·  2026.10.27',30,BLUE,True)
text(100,113,'全景布局人工标注：研究方法与主要结果',69,INK,True)
para(100,222,'研究问题：图片条件与人员差异，怎样影响原始标注和多人融合后的布局？',3000,40)
text(100,300,'10,439份作答 / 261图 / 62个来源人员ID；正式质量分析：7,302份 / 196图 / 60人。',34,GRAY)
text(100,355,'从头标注（Manual）为主，辅助标注（Semi）为次要分析。',32,GRAY)

section(425,'方法基础：质量评价与完整布局融合')
text(100,522,'质量评价',41,BLUE,True)
para(100,586,'Q综合底面区域、底边位置、方向规整性和高度；与均高3D IoU、逐列深度误差及D10版本比较。',1290,37)
para(100,715,'真人同图、同参考作答中，有438对的3D IoU差小于1分，而Q差超过20分。这些差异可以进一步定位到具体评分项。',1290,37)
para(100,855,'3D IoU按百分制比较；另有控制实验和25组人工审查材料。',1290,30,GRAY)
d.line((1470,520,1470,932),fill='#c7d2d9',width=2)
text(1550,522,'完整布局融合',41,BLUE,True)
para(1550,586,'墙线对应 → 独立人员投票 → 中位位置 → 环连接。对照：选取最接近其他作答的一份原答（medoid）。',1540,37)
text(1550,713,'普通Manual',32,GRAY,True)
text(2040,713,'融合−medoid平均Q',32,GRAY,True)
text(2700,713,'Q提高的图片',32,GRAY,True)
for y, lab, val, count in [(773,'4人团队','+7.108','16/22'),(833,'16人团队','−5.545','8/23')]:
    text(1550,y,lab,37); text(2040,y,val,37,BLUE,True); text(2770,y,count,37)
text(1550,904,'各行取双方完整可评分图片；另保留Lee底面融合对照。',30,GRAY)

section(1000,'图片与人员：原始标注中的结构差异')
text(100,1095,'六转折布局：三种几何条件下的简化比例',41,INK,True)
text(100,1161,'33图、1,023份作答；简化指作答有效转折少于参考。',31,GRAY)
for y,label,pct in [(1240,'无短边、无自遮挡',10.7),(1342,'有短边、无自遮挡',29.8),(1444,'有几何自遮挡',55.7)]:
    text(100,y,label,34)
    d.rectangle((485,y+5,485+820*pct/60,y+49),fill=BLUE)
    text(510+820*pct/60,y,f'{pct:.1f}%',35,BLUE,True)
para(100,1555,'同人比较：47人中，32人在短边条件下简化比例更高；36人在自遮挡条件下更高。',1330,34)
text(100,1675,'难度标签：几何初分，再经视觉检查和人工修订。',30,GRAY)
d.line((1470,1095,1470,1740),fill='#c7d2d9',width=2)
text(1550,1095,'人员分类按研究问题选用',41,INK,True)
for y,name,desc in [
 (1175,'主方法 DSTRUCT','按实际转折、短边、冗余分段及困难图响应分组。'),
 (1300,'RFUSE 融合响应类','按成员与团队几何变化的关系分组。'),
 (1425,'Manual＋Semi＋scope','联合两种标注条件和范围判断，描述跨条件差异。'),
 (1550,'边界类、质量／时间类','分别描述位置与尺度差异，以及质量与用时取舍。')]:
    text(1550,y,name,35,BLUE,True)
    para(1550,y+50,desc,1520,33)
para(1550,1680,'画像另记录质量低尾、被排除作答和已知初始化错误是否被修改。',1520,30,GRAY)

section(1790,'同图团队实验：类别比例与具体成员分别比较')
text(100,1885,'DSTRUCT：14人换7人，42/57图的跨类Q变化大于同类',47,INK,True)
para(100,1960,'A=D+X，B=D+Y，C=D+Z。三队保留相同背景D；X、Y来自同类，Z来自另一类，三块人数相同。',3000,35)
for x,label in [(100,'团队/换人数'),(570,'替换比例'),(980,'同类Q幅度'),(1490,'跨类Q幅度'),(2020,'跨类更大的图片'),(2650,'背景人数')]:
    text(x,2040,label,32,GRAY,True)
rule(2095)
rows=[('10人 / 7人','70%','4.869','7.271','39/57','3'),('14人 / 7人','50%','3.774','6.456','42/57','7'),('20人 / 7人','35%','3.192','5.472','42/57','13'),('21人 / 7人','33.3%','2.846','5.987','44/57','14')]
for i,row in enumerate(rows):
    y=2120+75*i
    if i==1: d.rectangle((90,y-8,3105,y+56),fill=PALE)
    for x,v in zip([100,570,980,1490,2020,2650],row): text(x,y,v,37,INK,i==1)
text(100,2442,'固定7人替换块、逐步加入相同背景；各点57张可评图片未必完全相同。18人换7人的保留建筑检查另有31/40图跨类更大。',29,GRAY)
text(100,2520,'相同配比内，换具体成员仍有较大波动',40,INK,True)
para(100,2585,'40图、22楼的231个比较组中，每组固定背景，从12名候选选6人，计算全部924支团队。',3000,34)
barx,bary,barw=100,2660,3000
split=barx+barw*.143627
assert round(14.3627+85.6373,4)==100
for a,b,c in [(barx,split,BLUE),(split,barx+barw,'#b7cbd4')]: d.rectangle((a,bary,b,bary+64),fill=c)
text(100,2744,'类别配比之间：14.36%',32,BLUE,True)
text(1100,2744,'同一配比的成员之间：85.64%',32,INK,True)
text(100,2805,'两部分占同一个Q总方差，合计100%；分类比例与具体成员都应保留在团队比较中。',31,GRAY)

section(2890,'人数曲线：普通图3→6人平均Q提高，困难图20→30人低尾改善')
for x,label in [(100,'固定图片与人数区间'),(1140,'平均Q变化'),(1700,'P10变化'),(2180,'Q标准差变化'),(2740,'实际失败率变化')]:
    text(x,2990,label,32,GRAY,True)
rule(3046)
for y,row in [(3072,['普通固定157图：3→6人','+4.914','+8.433','−2.720','+1.655 pp']), (3150,['其中困难27图：20→30人','−0.175','+4.246','−4.676','−1.100 pp'])]:
    for x,v in zip([100,1140,1700,2180,2740],row): text(x,y,v,35)
text(100,3245,'3→6人：155/157图Q提高。困难20→30：P10升24/27图，SD降25/27图，V降26/27图。',34,INK)
para(100,3310,'蒙特卡洛：每图随机排列256次，在各人数点统计前缀团队。每条顺序内不重复选人；顺序之间重复出现的团队按次数统计。已有完整目录的点精确计算。固定157图比较3—30人，92图比较30—35人，再看实际满员；Semi沿用原版。',3000,30,GRAY)

section(3440,'一个投票实例：zs-16同一21人团队，10票门槛与11票门槛')
text(100,3540,'10票门槛：6个节点，Q 92.47',42,BLUE,True)
text(1710,3540,'11票门槛：5个节点，Q 45.84',42,RUST,True)
para(100,3620,'退出的结构恰有10人支持。两次计算使用同一组标注，仅改变门槛；布局随节点退出而改变。',3000,36)

section(3735,'同房间、门洞交界与超出标注标准的场景')
for y,title,body in [
 (3830,'同房跨视角','123对同房图中105对个人Q排序正相关；同房均值预测误差5.08分，楼外历史为9.30分。具体换人收益随视角变化。'),
 (3980,'门洞交界','17图满员6图失败。6→10人均Q−1.006，12/17图下降；失败率−13.534个百分点，17图均降。\n20→30人：15图均Q−1.729；16图失败率+9.131个百分点。'),
 (4130,'OOS独立统计','28图涉及斜墙、斜顶、多层顶地面等情况。受当前表示约束，参考边界可能偏离图像中的结构；另行统计人员分歧与范围判断。'),
 (4280,'同用途补充','已知难度与几何后，加入用途，161图平均Q预测误差4.567→4.188（减少8.3%）。个人用途修正未胜过一般历史；用途与同一物理房间分开。')]:
    text(100,y,title,36,BLUE,True)
    end=para(620,y,body,2460,35)
    assert end<y+125
rule(4440)
para(100,4470,'术语：Q为相对固定参考的质量分；P10为第10百分位；标准差描述同人数换组后的分散程度；pp为百分点。Q仅统计可评分团队，真实失败按已执行尝试另计。主要方法比较和人数结果为Manual。',3000,28,GRAY,gap=9)
text(100,4570,'来源：《论文撰写资料入口》《全研究结论主线》及各专题保存表。图片、人员和团队在不同实验中可以重复使用。',27,GRAY)
OUT.parent.mkdir(parents=True,exist_ok=True)
im.save(OUT,dpi=(240,240),optimize=True)
print(OUT)
