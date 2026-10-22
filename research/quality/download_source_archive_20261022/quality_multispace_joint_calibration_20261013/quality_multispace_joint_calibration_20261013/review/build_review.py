#!/usr/bin/env python3
"""Build score-free, offline 3D review pages and a separate numeric diagnosis.

The three cases were selected from method disagreements, not from new labels.
Original PNG bytes are copied intact from the received original-image archives.
Subsequent reproduction uses these three individually hashed image assets.
"""
from __future__ import annotations
import argparse, base64, hashlib, io, json, math, zipfile
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def asset(image_code,image_id,out,archives):
    target=out/'images'/f'{image_code}.png';manifest=out/'original_image_manifest.json'
    prior=load(manifest) if manifest.exists() else []
    if target.exists():
        row=next((r for r in prior if r['image_id']==image_id),None)
        assert row is not None and sha(target)==row['sha256'], 'Image requires its original byte manifest'
        with Image.open(target) as im:im.load();assert list(im.size)==row['pixel_size']
        return 'images/'+target.name,row
    assert archives, f'Missing {target}; supply --archives containing the received independent ZIP archives'
    matches=[]
    for zp in Path(archives).rglob('*.zip'):
        with zipfile.ZipFile(zp) as z:
            for name in z.namelist():
                if image_id in name and name.lower().endswith('.png'):matches.append((zp,name))
    assert len(matches)==1,(image_id,matches)
    zp,name=matches[0]
    with zipfile.ZipFile(zp) as z:content=z.read(name)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    with Image.open(io.BytesIO(content)) as im:im.load();size=list(im.size)
    row=dict(image_code=image_code,image_id=image_id,path='images/'+target.name,sha256=sha(target),bytes=len(content),pixel_size=size,source_archive=zp.name,source_archive_sha256=sha(zp),source_member=name,content_modified=False)
    prior.append(row);dump(manifest,prior)
    return row['path'],row

def erp(p):
    p=np.asarray(p,float);return np.column_stack(((np.arctan2(p[:,0],-p[:,2])/(2*np.pi)+.5)*1024,(.5-np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2]))/np.pi)*512))
def render_contact(data,out):
    """Static scientific companion; not a screenshot of an unexecuted browser."""
    for case in data['cases']:
        fig=plt.figure(figsize=(14,8.3),layout='constrained');fig.suptitle(case['case_id']+' | Original panorama, shared-scale floor and 3D',fontsize=15)
        gs=fig.add_gridspec(2,3,width_ratios=[1.5,1,1]);allg=[g for p in case['panels'] for g in [p['geometry'],*[r['geometry'] for r in p['references']]]]
        pts=np.array([v for g in allg for r in [g.get('bottom3d',[]),g.get('top3d',[])] for v in r]);minima=pts.min(0);maxima=pts.max(0);margin=np.maximum((maxima-minima)*.08,.15)
        for i,p in enumerate(case['panels']):
            ax=fig.add_subplot(gs[i,0]);ax.imshow(Image.open(out/p['image_path']),extent=(0,1024,512,0));ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_title(p['label'].replace('参考 ','Ref ')+' | '+p['subtitle'].replace('同一作答','Same response'));ax.set_xlabel('ERP x / 1024');ax.set_ylabel('ERP y / 512')
            pa=fig.add_subplot(gs[i,1]);th=fig.add_subplot(gs[i,2],projection='3d');th.view_init(24,-50)
            items=[(r['geometry'],'#177b65','--') for r in p['references']]+[(p['geometry'],'#bd521e','-')]
            for g,color,style in items:
                for key in ['bottom3d','top3d']:
                    if not g.get(key):continue
                    ring=np.asarray(g[key],float);cl=np.vstack((ring,ring[0]));th.plot(cl[:,0],cl[:,2],cl[:,1],color=color,linestyle=style,lw=1.5)
                    if key=='bottom3d':pa.plot(cl[:,0],cl[:,2],color=color,linestyle=style,lw=1.6)
                    for a,b in zip(cl[:-1],cl[1:]):
                        line=erp(np.linspace(a,b,100));edges=np.where(np.abs(np.diff(line[:,0]))>512)[0]+1
                        for q in np.split(line,edges):
                            if len(q)>1:ax.plot(q[:,0],q[:,1],color=color,ls=style,lw=1)
                if g.get('top3d'):
                    for a,b in zip(g['bottom3d'],g['top3d']):th.plot([a[0],b[0]],[a[2],b[2]],[a[1],b[1]],color=color,ls=style,lw=.7)
            raw=np.asarray(p.get('raw_points',[]));
            if len(raw):ax.scatter(raw[:,0],raw[:,1],s=8,c='#d5a1ff',edgecolors='none')
            pa.scatter([0],[0],s=18,c='#183040');pa.set_aspect('equal');pa.set_xlim(minima[0]-margin[0],maxima[0]+margin[0]);pa.set_ylim(minima[2]-margin[2],maxima[2]+margin[2]);pa.set_xlabel('x / h');pa.set_ylabel('z / h');pa.grid(alpha=.15)
            th.set_xlim(minima[0]-margin[0],maxima[0]+margin[0]);th.set_ylim(minima[2]-margin[2],maxima[2]+margin[2]);th.set_zlim(minima[1]-margin[1],maxima[1]+margin[1]);th.set_box_aspect(np.maximum((maxima-minima)[[0,2,1]],.3));th.set_xlabel('x / h');th.set_ylabel('z / h');th.set_zlabel('y / h');th.set_title('same camera and scale')
        buffer=io.BytesIO()
        fig.savefig(buffer,format='png',dpi=145,bbox_inches='tight',pad_inches=.18);plt.close(fig)
        content=buffer.getvalue()
        with Image.open(io.BytesIO(content)) as im:im.verify()
        target=out/(case['case_id']+'_static.png');temp=target.with_suffix('.png.tmp')
        temp.write_bytes(content);temp.replace(target)
        with Image.open(target) as im:im.load()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archives',type=Path);ap.add_argument('--out',type=Path,default=ROOT/'review');a=ap.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
    frozen=load(ROOT/'baseline/inputs/calibration_records.json');geom=frozen['geometries'];fixed={r['record_id']:r for r in load(ROOT/'integration/results/fixed_reference_922.json')['rows']};routing=load(ROOT/'routing/inputs/prepared_input.json');route_results={r['record_id']:r for r in load(ROOT/'routing/results/routes.json')['rows']};definitions=[('J01',['R03346','R03347'],'范围与结构的综合权衡','请结合原图与参考综合比较 A、B；哪份作答总体更好，还是近似相当？','同图、同一完整参考。B 曾有单例质量判断；本次只补成对比较，既有意见保留。'),('J02',['R02049','R02244'],'局部异常与广泛轻度歪斜','综合比较两份作答，不必把某一个局部问题当成唯一标准。','同图、同一完整参考。该图的正式人员比较资格尚未确认，本例仅用于方法诊断；若参考不适用，可直接指出。')]
    data=dict(dataset_id='joint_calibration_20261013_three_disagreements_v1',cases=[]);diagnostic=dict(cases={},selection='Three genuine method disagreements; no new human labels, no independent generalization claim')
    for cid,ids,title,question,context in definitions:
        case=dict(case_id=cid,title=title,question=question,context=context,judgment_scope='overall_quality',panels=[]);numeric=dict(record_ids=ids,selection_is_algorithm_disagreement=True,independent_validation=False,records=[])
        for label,rid in zip(['A','B'],ids):
            r=fixed[rid];path,_=asset(r['image_code'],r['image_id'],out,a.archives)
            case['panels'].append(dict(label=label,subtitle=rid+' | '+r['image_code'],image_path=path,geometry=geom[r['object_id']],references=[dict(label='同一既有参考',geometry=geom[r['reference_object_id']])],raw_points=r['raw_points'],raw_links=r['raw_links']))
            numeric['records'].append({k:r[k] for k in ['record_id','object_id','image_code','reference_object_id','reference_version','current_points_sha256','reference_points_sha256'] if k in r}|dict(metrics=r['metrics'],baseline=r['baseline'],candidates=r['candidates'],official_iou3d_x100=r['official_iou3d_x100'],pair_delta_rms_deg=r['pair_delta_rms_deg'],endpoint_adjustment_rms_deg=r['endpoint_adjustment_rms_deg'],conditional_personnel_eligible=r['conditional_personnel_eligible'],use_barriers=r['use_barriers']))
        data['cases'].append(case);diagnostic['cases'][cid]=numeric
    rid='R03197';r=next(r for r in routing['records'] if r['record_id']==rid);im=next(x for x in routing['candidate_images'] if x['image_id']==r['image_id']);path,_=asset(r['image_code'],r['image_id'],out,a.archives);panels=[]
    for label in ['A','B']:
        ref=next(c for c in im['candidates'] if c['space_label']==label);floor=dict(bottom3d=[[x,-1,z] for x,z in ref['floor_xz_h']]);panels.append(dict(label='参考 '+label,subtitle=rid+' | '+r['image_code']+' | 同一作答',image_path=path,geometry=r['geometry'],references=[dict(label='合法底面候选 '+label,geometry=floor)],raw_points=r['source_object']['before_preprocessing_points'],raw_links=r['source_object']['links_zero_based']))
    data['cases'].append(dict(case_id='J03',title='同一作答的多空间参考归属',question='两侧是同一份作答，只有参考底面不同。应按参考 A、参考 B 比较，还是没有足够证据判断空间意图？',context='本例只判断参考归属，不判断作答质量合格。为统一比较，两种参考均只显示底面，未确认顶面没有补造。',judgment_scope='reference_assignment',judgment_options=[['A','参考 A'],['B','参考 B'],['similar','两种均可'],['uncertain','空间意图不确定'],['reference_issue','候选参考有问题']],panels=panels))
    diagnostic['cases']['J03']=dict(record_id=rid,route=route_results[rid],candidates=[{k:v for k,v in c.items() if k not in ['points_1024x512','floor_xz_h','full_geometry']} for c in im['candidates']],selection='floor IoU and normalized symmetric floor boundary disagree; T29 already has a human answer and is not re-requested',independent_validation=False)
    # Exact scores occur only in the diagnostic object, never in blind DATA.
    forbidden=['J_main','J_simple','J_local','baseline','score','metrics','IoU','D_deg','Hm','Hc']
    blind_json=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    assert not any(t in blind_json for t in forbidden)
    dump(out/'blind_data.json',data);dump(out/'diagnostic_data.json',diagnostic)
    template=(ROOT/'review/review_template.html').read_text()
    for standalone in [False,True]:
        d=json.loads(json.dumps(data))
        if standalone:
            for c in d['cases']:
                for p in c['panels']:p['image_path']='data:image/png;base64,'+base64.b64encode((out/p['image_path']).read_bytes()).decode()
        dj=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
        suffix='_standalone' if standalone else ''
        for mode,obj in [('blind',None),('diagnostic',diagnostic)]:
            html=template.replace('__DATA_JSON__',dj).replace('__DIAGNOSTIC_JSON__',json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
            if standalone:html=html.replace("'blind_review.html'","'blind_review_standalone.html'").replace("'diagnostic_review.html'","'diagnostic_review_standalone.html'").replace('href="diagnostic_review.html"','href="diagnostic_review_standalone.html"')
            (out/f'{mode}_review{suffix}.html').write_text(html,encoding='utf-8')
    render_contact(data,out)
    dump(out/'build_verification.json',dict(schema='review_build_check_v1',n_cases=3,n_unique_original_images=3,blind_data_has_algorithm_scores=False,diagnostic_data_separate=True,full_PNG_decodes=3,full_static_PNG_decodes=3,source_manifest_sha256=sha(out/'original_image_manifest.json'),template_sha256=sha(ROOT/'review/review_template.html'),review_data_sha256=sha(out/'blind_data.json'),HTML_variants=4,standalone_embeds_original_unmodified_PNG_bytes=True,static_figures_are_matplotlib_not_browser_screenshots=True,previous_human_exposure_not_reset=True))
    print(json.dumps(dict(status='built',cases=3,images=3,html_variants=4),ensure_ascii=False))
if __name__=='__main__':main()
