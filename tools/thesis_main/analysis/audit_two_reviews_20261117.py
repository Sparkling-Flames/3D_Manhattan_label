"""Read-only receipt audit and geometric evidence; no automatic human adjudication."""
from pathlib import Path
from itertools import combinations
import json, gzip, zipfile, math, csv
from html import escape
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from tools.label_studio.panorama_studio.geometry import pixel_ray

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/fusion/formal_identity_review_20261117'
OUT=BASE/'two_reviews_audit'
SOURCES=[Path('C:/Users/ASUS/Downloads/墙线新判断_1794895272042.json'),Path('C:/Users/ASUS/Documents/xwechat_files/wxid_lvoh11i1addo22_a66c/msg/file/2026-11/墙线新判断_1794885200123.json')]

def project(q):
    # Reuse engine rays, retaining each observation's actual upper direction.
    bottom=np.array([pixel_ray(*p,1024,512,coordinate_convention='continuous') for p in q[:,1]])
    top=np.array([pixel_ray(*p,1024,512,coordinate_convention='continuous') for p in q[:,0]])
    assert np.all(bottom[:,1]<0)
    floor=-bottom/bottom[:,1,None]
    rho=np.linalg.norm(floor[:,[0,2]],axis=1)
    ceiling=top*(rho/np.linalg.norm(top[:,[0,2]],axis=1))[:,None]
    assert np.allclose(floor[:,1],-1)
    return floor,ceiling,rho

def render_report():
    evidence=json.loads((OUT/'EVIDENCE.json').read_text(encoding='utf-8'))
    with (OUT/'CASE_ASSESSMENTS.tsv').open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
    assessments={r['case']:r for r in rows}
    assert len(rows)==len(assessments)==len(evidence['cases'])==99
    assert set(assessments)=={c['id'] for c in evidence['cases']}
    assert sum(len(c['comments']) for c in evidence['cases'])==len(evidence['comments'])==110
    esc=lambda value:escape(str(value))
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>两份人审逐项核查</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:1250px;margin:24px auto;padding:0 18px;color:#172431}h1{font-size:28px}article{border-top:2px solid #adc0ce;margin-top:32px;padding-top:12px}img{width:100%;height:auto}table{border-collapse:collapse}td,th{border:1px solid #ccd5dc;padding:6px 10px;text-align:left}blockquote{border-left:4px solid #8fabbc;padding:8px 14px;background:#f2f6f9;margin:12px 0}a{color:#145d91}.note{color:#455b6c}nav{display:flex;gap:8px;flex-wrap:wrap}</style><h1>两份墙线人审：99个选择案例，110条原评论</h1><p>同一标准分析，原选项与评论原样保留；下面的分析判断不是人审改答。案例之间可能重叠，不将分类计数解释为算法错误率。看不清的维持当前分组，不计入确认正确。</p><p><a href="README.md">完整结论</a> · <a href="ORDER_DIAGNOSIS.md">角点顺序诊断</a> · <a href="3D_six_cases.png">六例三维对照</a> · <a href="C080_mixed_modes.png">明确表达混合案例</a></p><p class="note">距离、高度以相机高度为单位。n是本次选择的观察数，全组n是实际组大小；“入选”指原算法整组是否达到半数支持。三维统计依次为Q1 / 中位数 / Q3。原图局部为显示而平移接缝，未改变原始几何。</p><nav>']
    parts += [f'<a href="#{c["id"]}">{c["id"]}</a>' for c in evidence['cases']]
    parts.append('</nav>')
    for c in evidence['cases']:
        a=assessments[c['id']]
        parts.append(f'<article id="{c["id"]}"><h2>{c["id"]} · {esc(c["code"])} · {esc(" / ".join(c["groups"]))}</h2><p><strong>{esc(a["assessment"])}</strong>：{esc(a["reason"])}</p>')
        for com in c['comments']:
            metadata='；'.join(f'{k}={com[k]}' for k in ('type','identity','geometry','criterion') if k in com)
            parts.append(f'<blockquote><strong>原评论 {esc(com["reviewer"])} · 第{com["ordinal"]}条</strong><br>{esc(com["note"])}<br><small>{esc(metadata)}</small></blockquote>')
        parts.append(f'<p>人员池 {c["n"]}，达票门槛 {c["threshold"]}；{esc(c["cohort"])}。</p><table><tr><th>组</th><th>选择n / 全组n</th><th>原入选</th><th>径向距离</th><th>局部高度</th></tr>')
        for gid,s in c['stats'].items():
            quant=lambda key:' / '.join(f'{v:.3f}' for v in s[key][1:4])
            parts.append(f'<tr><td>{esc(gid)}</td><td>{s["n"]} / {s["full_n"]}</td><td>{"是" if s["selected"] else "否"}</td><td>{quant("rho")}</td><td>{quant("height")}</td></tr>')
        parts.append('</table>')
        for pair in c['pairs']:
            parts.append(f'<p class="note">{esc(pair["a"])} / {esc(pair["b"])}：已匹配观察对 {pair["linked"]}/{pair["pairs"]}；同时出现在两组的人员 {pair["shared_workers"]}；合计不同人员 {pair["unique_workers"]}。匹配数量不是身份准确率。</p>')
        source=f'figures/{c["id"]}.png'
        assert (OUT/source).is_file()
        parts.append(f'<a href="{source}"><img loading="lazy" src="{source}" alt="{c["id"]}原图叠加、底面和高度散点"></a>')
        full=f'figures/{c["id"]}_full_records.png'
        if (OUT/full).exists():parts.append(f'<p><a href="{full}">查看涉及人员的完整原答与原环</a></p>')
        parts.append('</article>')
    parts.append('<p>核查数据：<a href="EVIDENCE.json">证据JSON</a> · <a href="CASE_ASSESSMENTS.tsv">逐项判断</a>。原回执路径见证据JSON。没有改写回执、分组、顺序或Q。</p></html>')
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True);(OUT/'figures').mkdir(exist_ok=True)
    data=json.loads((BASE/'reviewer/data.js').read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
    scenes={s['id']:s for s in data['scenes']}
    manifest=json.loads((BASE/'COORDINATOR_MANIFEST.json').read_text(encoding='utf-8'))
    cohorts={s['id']:s for s in manifest['scenes']}
    receipts=[json.loads(p.read_text(encoding='utf-8-sig')) for p in SOURCES]
    cases={}; comments=[]
    for reviewer,r in zip('AB',receipts):
        assert r['package']==data['package'] and len(r['answers'])==72
        for sid,a in r['answers'].items():
            s=scenes[sid];assert a['code']==s['code']
            for no,i in enumerate(a['issues'],1):
                allowed={k for g in s['groups'] if g['id'] in i['groups'] for k in g['members']}
                assert set(i['members'])<=allowed and i['members']
                key=(sid,tuple(sorted(i['groups'])),tuple(sorted(i['members'])))
                if key not in cases:cases[key]=dict(id=f'C{len(cases)+1:03}',scene=sid,code=s['code'],groups=key[1],members=key[2],comments=[],cohort=cohorts[sid]['cohort'])
                comment=dict(reviewer=reviewer,ordinal=no,**i);cases[key]['comments'].append(comment)
                comments.append(dict(case=cases[key]['id'],scene=sid,code=s['code'],**comment))
    z=zipfile.ZipFile('C:/Users/ASUS/Downloads/gap75_evidence_20261117.zip');states={}
    for s in scenes.values():
        if not any(c['scene']==s['id'] for c in cases.values()):continue
        name=next(n for n in z.namelist() if '/states/'+cohorts[s['id']]['pool_id'] in n)
        states[s['id']]=json.loads(gzip.decompress(z.read(name)))
    for c in cases.values():
        s=scenes[c['scene']];state=states[c['scene']];p=np.array([o['points'] for o in s['observations']]);edges={tuple(sorted(e)) for e in state['states']['7.5']['pairwise_match_edges']}
        assert np.allclose(p,np.array([o['points'] for o in state['nodes']]))
        c['n']=s['n'];c['threshold']=math.ceil(s['n']/2);c['stats']={};c['pairs']=[]
        for gid in c['groups']:
            g=next(g for g in s['groups'] if g['id']==gid);ix=sorted(set(g['members'])&set(c['members']));q=p[ix];f,t,r=project(q)
            c['stats'][gid]=dict(n=len(ix),full_n=len(g['members']),selected=g['selected'],indices=ix,workers=[s['observations'][k]['worker'] for k in ix],top_y=np.quantile(q[:,0,1],[0,.25,.5,.75,1]).tolist(),bottom_y=np.quantile(q[:,1,1],[0,.25,.5,.75,1]).tolist(),rho=np.quantile(r,[0,.25,.5,.75,1]).tolist(),height=np.quantile(t[:,1]+1,[0,.25,.5,.75,1]).tolist(),floor_center=np.median(f,axis=0).tolist(),floor_scatter=float(np.median(np.linalg.norm(f-np.median(f,axis=0),axis=1))))
        for ga,gb in combinations(c['groups'],2):
            a,b=c['stats'][ga],c['stats'][gb];cross=[(i,j) for i in a['indices'] for j in b['indices']]
            shared=set(a['workers'])&set(b['workers']);linked=sum(tuple(sorted(e)) in edges for e in cross)
            c['pairs'].append(dict(a=ga,b=gb,pairs=len(cross),linked=linked,shared_workers=len(shared),floor_center_distance=float(np.linalg.norm(np.array(a['floor_center'])-b['floor_center'])),unique_workers=len(set(a['workers'])|set(b['workers']))))
        fig,axs=plt.subplots(1,3,figsize=(12,3.3),gridspec_kw={'width_ratios':[1.5,1,1]})
        image=np.asarray(Image.open(BASE/'reviewer'/s['image']).resize((1024,512)));assert image.shape[:2]==(512,1024)
        selected=p[list(c['members'])];x=selected[:,:,0].flatten();angle=np.angle(np.mean(np.exp(2j*np.pi*x/1024)));anchor=(angle/(2*np.pi)*1024)%1024
        shift=int(512-anchor);image=np.roll(image,shift,axis=1);xs=(x+shift)%1024
        axs[0].imshow(image,extent=[0,1024,512,0]);axs[0].set_xlim(max(0,xs.min()-35),min(1024,xs.max()+35));axs[0].set_ylim(min(512,selected[:,:,1].max()+20),max(0,selected[:,:,1].min()-20))
        for j,gid in enumerate(c['groups']):
            ix=c['stats'][gid]['indices'];q=p[ix];f,t,r=project(q);color=plt.get_cmap('tab10')(j%10)
            for k,pair in zip(ix,q):
                px=(pair[:,0]+shift)%1024;axs[0].plot(px,pair[:,1],'-o',color=color,alpha=.5,lw=.7,ms=2)
            axs[0].plot([],[],color=color,label=f'{gid} n={len(ix)}')
            axs[1].scatter(f[:,0],f[:,2],s=14,color=color,label=gid);axs[2].scatter(r,t[:,1]+1,s=14,color=color)
        axs[0].legend(fontsize=7);axs[0].set_title('Panorama crop',fontsize=10);axs[1].set_title('Projected floor (equal axes)',fontsize=10);axs[1].set_aspect('equal',adjustable='datalim');axs[1].set_xlabel('X / camera height');axs[1].set_ylabel('Z / camera height');axs[2].set_title('Depth and local height',fontsize=10);axs[2].set_xlabel('Radial distance / camera height');axs[2].set_ylabel('Height / camera height')
        fig.suptitle(f"{c['id']} {c['code']} {'/'.join(c['groups'])}",fontsize=11);fig.tight_layout();fig.savefig(OUT/'figures'/f"{c['id']}.png",dpi=110);plt.close(fig)
    payload=dict(sources=[str(p) for p in SOURCES],cases=list(cases.values()),comments=comments)
    (OUT/'EVIDENCE.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    # Every raw comment survives the exact-selection deduplication.
    assert len(comments)==sum(len(c['comments']) for c in cases.values())==110
    for start in range(0,len(cases),4):
        subset=list(cases.values())[start:start+4];ims=[Image.open(OUT/'figures'/f"{c['id']}.png").convert('RGB') for c in subset];sheet=Image.new('RGB',(ims[0].width,sum(i.height for i in ims)),'white');y=0
        for im in ims:sheet.paste(im,(0,y));y+=im.height
        sheet.save(OUT/f'sheet_{start//4+1:02}.jpg',quality=90)
    print(json.dumps(dict(comments=len(comments),cases=len(cases),scenes=len(states),sheets=math.ceil(len(cases)/4))))
    if (OUT/'CASE_ASSESSMENTS.tsv').exists():render_report()

if __name__=='__main__':main()
