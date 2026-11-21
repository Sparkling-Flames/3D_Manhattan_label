"""Build the editable, two-role CSCW overview from the recorded Semi and Manual cases."""
import base64
import gzip
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs/thesis_main"
MATERIAL = DOCS / "论文写作工作资料"
PAPER = DOCS / "论文提纲_LaTeX_20261028"
OUT = MATERIAL / "CSCW图2 候选/交互双角色候选"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)
INK, MUTED, RULE = "#182e38", "#465c65", "#bac8cc"
TEAL, WARM, PAPERWHITE = "#00685e", "#b54a20", "#ffffff"


def element(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}",
                         {k.replace("_", "-"): str(v) for k, v in attrs.items()})


def group(parent, name):
    return element(parent, "g", id=name)


def text(parent, x, y, words, size=15, color=INK, bold=False):
    t = element(parent, "text", x=x, y=y, font_family="Arial", font_size=size,
                font_weight="bold" if bold else "normal", fill=color)
    t.text = words
    return t


def path(parent, points, color, width=1.6, fill="none", closed=False, **attrs):
    coords = " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return element(parent, "path", d="M " + coords + (" Z" if closed else ""),
                   stroke=color, stroke_width=width, fill=fill, stroke_linejoin="round",
                   stroke_linecap="round", **attrs)


def dot(parent, pt, r, fill, stroke="white", **attrs):
    return element(parent, "circle", cx=pt[0], cy=pt[1], r=r, fill=fill, stroke=stroke,
                   stroke_width=1.1, **attrs)


def arrow(parent, points, color=MUTED):
    path(parent, points, color, 1.65)
    end = np.array(points[-1]); prev = np.array(points[-2])
    v = (end-prev)/np.linalg.norm(end-prev)
    normal = np.array([-v[1], v[0]])
    path(parent, [end-6*v+3.1*normal, end, end-6*v-3.1*normal], color, 1.65)


def operator(parent, x, y, color):
    dot(parent, (x+5, y+4), 3.6, color, color)
    element(parent, "path", d=f"M{x-1},{y+16} q0,-7 6,-7 t6,7", fill=color)
    path(parent, [(x+13,y+2),(x+28,y+2),(x+28,y+13),(x+13,y+13)], color, 1.5,
         closed=True)
    path(parent, [(x+20,y+13),(x+20,y+17),(x+26,y+17),(x+15,y+17)], color, 1.4)


def photo(parent, source, crop, box, name):
    x,y,w,h = box
    u,v,r,b = crop
    image = source.crop(tuple(round(c*2) for c in crop))
    image.thumbnail((round(w*5), round(h*5)))
    stream = io.BytesIO()
    image.save(stream, "JPEG", quality=93)
    node = element(parent, "image", id=name, x=x, y=y, width=w, height=h,
                   preserveAspectRatio="none")
    node.set(f"{{{XLINK}}}href", "data:image/jpeg;base64," +
             base64.b64encode(stream.getvalue()).decode())
    return lambda p: (np.asarray(p)-[u,v])*[w/(r-u),h/(b-v)]+[x,y]


def walls(pairs):
    a = (pairs[:,0,0]/1024-.5)*2*np.pi
    elev = (.5-pairs[:,:,1]/512)*np.pi
    radius = -1/np.tan(elev[:,1])
    floor = np.column_stack((radius*np.sin(a), -np.ones(len(a)), -radius*np.cos(a)))
    top = floor.copy()
    top[:,1] = radius*np.tan(elev[:,0])
    return np.stack((top, floor), axis=1)


def supplied_edges(parent, pairs, tr):
    xyz = walls(pairs)
    for ring in xyz.transpose(1,0,2):
        for a,b in zip(ring,np.roll(ring,-1,axis=0)):
            x,y,z = np.linspace(a,b,90).T
            uv = np.column_stack(((np.arctan2(x,-z)/(2*np.pi)+.5)*1024,
                                  (.5-np.arctan2(y,np.hypot(x,z))/np.pi)*512))
            for s in np.split(uv,np.where(np.abs(np.diff(uv[:,0]))>512)[0]+1):
                if len(s)>1:
                    for col,sw in [(INK,2.9),("#94fff0",1.65)]:
                        path(parent,tr(s),col,sw)
    for i,p in enumerate(pairs):
        segment = tr(p)
        path(parent,segment,"#8dfff0",1.4)
        for j,pt in enumerate(segment):
            dot(parent,pt,2.7,TEAL,id=f"supplied-endpoint-{i}-{j}")


def project(xyz):
    return np.stack((.64*xyz[...,0]+.768*xyz[...,2],
                     -.395*xyz[...,0]-.857*xyz[...,1]+.330*xyz[...,2]),axis=-1)


def fit(shapes, box):
    xy = np.concatenate([s.reshape(-1,2) for s in shapes])
    x,y,w,h = box
    scale = min(np.array([w,h])/np.ptp(xy,axis=0))
    off = [x+w/2,y+h/2] - scale*(xy.min(axis=0)+xy.max(axis=0))/2
    return [s*scale+off for s in shapes]


def preview(parent, pairs, box):
    p, = fit([project(walls(pairs))],box)
    path(parent, p[:,1], "#809b99", 1.4, "#eef5f2", True)
    for i in [1,2,3,4]:
        j=(i+1)%len(p)
        path(parent,[p[i,0],p[j,0],p[j,1],p[i,1]],"#718c8a",1.15,
             "#d5e7e3" if i%2==0 else "#edf3f1", True)
    path(parent,p[3],WARM,2.6)
    for j,pt in enumerate(p[3]):
        dot(parent,pt,3.2,WARM,id=f"preview-endpoint-{j}")


def draw():
    with gzip.open(PAPER/"editorial_tools/figure_inputs/bathroom_team_trace.json.gz",
                   "rt",encoding="utf-8") as f:
        evidence=json.load(f)
    case=json.loads((PAPER/"figure_package/dot_fig07/data/consensus_case.json").read_text("utf-8-sig"))
    semi=json.loads((MATERIAL/"semi_editing_source.json").read_text("utf-8-sig"))
    supplied=np.array(semi["initial_points"]).reshape(-1,2,2)
    pic_s=Image.open(ROOT/semi["photo"]).convert("RGB")
    pic_m=Image.open(ROOT/"data/mp3d_layout/valid/img"/(evidence["pool"]["meta"]["image_id"]+".png")).convert("RGB")
    team=case["teams"]["Team 2"]
    worker=next(p for p in team["people"] if p["person"]=="W002")
    record=next(r for r in evidence["pool"]["records"] if r["worker"]=="W002")
    p=np.array(worker["points"]).reshape(-1,2,2)
    np.testing.assert_allclose(p.reshape(-1,2),record["points"])
    turn=team["turns"][0]
    observations=np.array([m["pair"] for m in turn["members"]])
    med=np.asarray(turn["pair"])
    np.testing.assert_allclose(np.median(observations,axis=0),med)
    assert team["n"]==10 and turn["support"]==len(observations)==8
    assert pic_m.size==pic_s.size==(2048,1024)
    root=ET.Element(f"{{{SVG}}}svg",{"width":"139.7mm","height":"77.55mm","viewBox":"0 0 800 444"})
    element(root,"title").text="Independent annotation and offline comparison of panoramic layouts"
    element(root,"rect",x=0,y=0,width=800,height=444,fill="white")
    head=group(root,"roles")
    operator(head,10,8,TEAL)
    text(head,50,24,"Annotator",21,TEAL,True)
    text(head,158,24,"Works independently",15)
    operator(head,490,8,"#805027")
    text(head,532,24,"Researcher",21,"#805027",True)
    text(head,654,24,"After submission",15)
    path(head,[(10,36),(462,36)],TEAL,1.8)
    path(head,[(490,36),(790,36)],"#92673f",1.8)

    s=group(root,"semi-supplied-start")
    text(s,10,65,"Semi",19,INK,True)
    text(s,65,65,"Start with a supplied layout",16)
    tr=photo(s,pic_s,(0,61,1024,463),(10,78,204,80),"semi-photo")
    supplied_edges(group(s,"supplied-walls-and-clicks"),supplied,tr)
    sx,sy=tr(supplied[1,0])
    element(s,"rect",x=sx-6,y=sy-6,width=13.5,height=12,fill="none",
            stroke="white",stroke_width=1.55,id="semi-detail-location")
    arrow(s,[(218,117),(236,117)])
    text(s,247,94,"Inspect the given corners",16,INK,True)
    for x,indices,lab in [(247,[1,2],"Kept both"),(357,[1],"Removed one")]:
        tr=photo(s,pic_s,(343,143,391,165),(x,104,86,39.4),"semi-detail-"+lab.lower().replace(" ","-"))
        for i in indices:
            dot(s,tr(supplied[i,0]),3.5,"#127668")
        text(s,x,162,lab,15)
    path(s,[(10,177),(460,177)],RULE,.8)
    m=group(root,"manual-empty-start")
    text(m,10,204,"Manual",19,INK,True)
    text(m,88,204,"Start with an empty layout",16)
    # Identically sized entry views expose the difference at the start of each task.
    photo(m,pic_m,(0,61,1024,463),(10,217,204,80),"manual-empty-photo")
    arrow(m,[(217,256),(233,256)])
    tr=photo(m,pic_m,(559,115,782,440),(240,218,55,80),"manual-corner-detail")
    pair=tr(p[3])
    path(m,pair,"white",4)
    path(m,pair,WARM,2.1)
    for j,pt in enumerate(pair):
        dot(m,pt,3.7,WARM,id=f"manual-marked-endpoint-{j}")
    arrow(m,[(302,256),(328,256)],TEAL)
    preview(group(m,"individual-3d-preview"),p,(335,217,115,80))
    text(m,10,320,"Unmarked panorama",15)
    text(m,218,320,"Mark each turn",15)
    text(m,344,320,"3D preview",15)
    arrow(m,[(407,328),(407,348),(265,348),(265,328)],TEAL)
    element(m,"rect",x=286,y=333,width=100,height=22,fill="white")
    text(m,289,350,"May revise",15,TEAL)
    handoff=group(root,"submit-manual-drawing")
    arrow(handoff,[(451,256),(471,256),(471,80),(485,80)])
    text(handoff,0,0,"Submit",14,MUTED).set("transform","translate(466 203) rotate(-90)")

    r=group(root,"offline-team-design")
    text(r,490,60,"Group Manual drawings by panorama",15.2,INK,True)
    # These are the two recorded ten-person teams, with their shared people first.
    team1={a["person"] for a in case["teams"]["Team 1"]["people"]}
    team2={a["person"] for a in team["people"]}
    shared=team1 & team2
    assert len(shared)==3 and len(team1)==len(team2)==10
    for side,(members,x,col) in enumerate([(team1,490,"#7b9da3"),(team2,573,"#ae6944")]):
        g=group(r,f"offline-team-{side+1}")
        for i,person in enumerate(sorted(shared)+sorted(members-shared)):
            cx=x+6*(i%5); cy=73+10*(i//5)
            paint=INK if person in shared else col
            element(g,"circle",cx=cx+3,cy=cy,r=2.3,fill=paint)
            element(g,"rect",x=cx+.5,y=cy+3,width=5,height=3.2,rx=1.1,fill=paint)
    arrow(r,[(528,80),(561,80)])
    text(r,617,86,"Fixed size, different people",14)
    path(r,[(490,102),(790,102)],RULE,.8)
    c=group(root,"corner-consensus")
    text(c,490,124,"Paired-corner structural consensus",16,TEAL,True)
    # Angular observations plotted in the same local window, with the long middle
    # of the vertical wall compressed. Upper and lower endpoints remain paired.
    def local(raw,x):
        pts=np.asarray(raw).copy()
        pts[:,0]=x+(pts[:,0]-med[0,0])*1.55
        pts[:,1]=[147+(pts[0,1]-med[0,1])*.72,195+(pts[1,1]-med[1,1])*.72]
        return pts
    for i,ob in enumerate(observations):
        g=group(c,f"supporter-{i+1}")
        v=local(ob,528)
        path(g,v,"#84a6a1",.85)
        for pt in v:
            dot(g,pt,2.45,"#e1efe9",TEAL)
    arrow(c,[(555,171),(578,171)])
    v=local(med,596)
    path(c,v,TEAL,2.5)
    for pt in v:
        dot(c,pt,4.2,TEAL)
    text(c,615,151,"Keep at half or more.",15)
    text(c,615,173,"8 of 10 mark this turn.",15)
    text(c,615,195,"Upper and lower medians",14.5)
    path(c,[(490,215),(790,215)],RULE,.8)
    q=group(root,"geometric-quality")
    text(q,490,241,"Geometric quality Q",17,TEAL,True)
    ref=np.array(case["reference"]).reshape(-1,2,2)
    left,right=fit([project(walls(p)),project(walls(ref))],(491,257,108,88))
    for shape,col,dashes in [(right,"#535965",{"stroke_dasharray":"4 3"}),(left,TEAL,{})]:
        for idx in [0,1]:
            path(q,shape[:,idx],col,1.4,closed=True,**dashes)
        for idx in [1,3,5]:
            path(q,shape[idx],col,1.05,**dashes)
    for y,lab,col in [(267,"Individual drawing",TEAL),(289,"Reference","#535965")]:
        for start,end in ([(616,635)] if y==267 else [(616,620),(623,627),(630,635)]):
            path(q,[(start,y-5),(end,y-5)],col,1.8)
        text(q,643,y,lab,15)
    text(q,616,326,f"Q = {record['B8L2']:.2f}",22,TEAL,True)

    rq=group(root,"research-comparisons")
    path(rq,[(10,368),(790,368)],RULE,1.1)
    text(rq,10,393,"Comparisons",17,INK,True)
    for x,tag,first,second in [
        (10,"RQ1","Compare people","on the same image"),
        (217,"RQ2","Add people","from the same pool"),
        (414,"RQ3","Replace members","at fixed team size"),
        (610,"RQ4","Change viewpoint","within the same room")]:
        text(rq,x,416,tag,14,TEAL,True)
        text(rq,x+36,416,first,15,INK,True)
        text(rq,x+36,436,second,14.4,MUTED)
    return root


if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    root=draw()
    svg=ET.tostring(root,encoding="utf-8",xml_declaration=True)
    (OUT/"Fig2.svg").write_bytes(svg)
    with pymupdf.open(stream=svg,filetype="svg") as vector:
        pdf=vector.convert_to_pdf()
    with pymupdf.open(stream=pdf,filetype="pdf") as doc:
        assert len(doc)==1 and len(doc[0].get_drawings())>50
        doc.save(OUT/"Fig2.pdf",garbage=4,deflate=True)
        doc[0].get_pixmap(dpi=240,alpha=False).save(OUT/"Fig2.png")
