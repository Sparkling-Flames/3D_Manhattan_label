#!/usr/bin/env python3
"""Small conditional-development review set; no answers or independent-test claim.

Selection occurred after viewing frozen candidate scores; every source remains
unchanged. The two structural comparisons are same-image/same-reference pairs.
Two further same-image pairs examine local-height action and global-versus-local
height weighting. Output HTML contains neither record IDs nor method scores.
"""
from __future__ import annotations
import argparse,base64,csv,hashlib,html,itertools,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CHOICES=[
 {'pair_id':'C01','records':['R01810','R01385'],'purpose':'mild_structure_vs_range','optional':True,
  'crops':[[365,115,460,420],[665,165,735,365]],
  'question':'只看统一后的固定重建，两份作答哪份整体更接近图像中应标的空间及给定参考？',
  'research_reason':'D只有0.48与1.41度；平均高度、局部高度和顶部边界量相近。cap1与cap2排序相反，检验对小方向偏差是否过罚。原始方位残差有差异，必须将输入判断与统一结果判断分开。'},
 {'pair_id':'C02','records':['R03351','R03350'],'purpose':'moderate_structure_vs_larger_range_error','optional':True,
  'crops':[[420,170,510,318],[595,170,665,313]],
  'question':'两份作答的结构、范围和顶部误差综合考虑，哪份整体更好？',
  'research_reason':'同图同参考、同为手工、平均前上下x残差均为零。较大D与较高IoU对抗，cap1/cap2改变排序；高度和顶部差异仍存在，不能当纯角度单变量。'},
 {'pair_id':'C03','records':['R01033','R01022'],'purpose':'matched_mean_different_local_height','optional':True,
  'crops':[[75,55,155,455],[600,170,670,337]],
  'question':'两份作答的顶部、墙面与点位误差是否有实质区别？请分别判断点位与重建结果。',
  'research_reason':'底面IoU、共同方向及平均高度较接近，中心化局部高度不同；仍保留底界差异，不宣称纯单变量。初选R02196的平均前水平残差5.325度会混淆高度判断，已改用残差约.055度的R01033。'},
 {'pair_id':'C04','records':['R02447','R01973'],'purpose':'global_height_vs_local_height_tradeoff','optional':True,
  'crops':[[665,165,735,365],[885,180,950,342]],
  'question':'这两份作答的整体空间质量如何比较？如果问题不同而难以综合排序，可以直接选择该项。',
  'research_reason':'同图底面IoU与D接近；一份平均高度偏差较小而局部起伏较大，另一份相反。用于检验全局与局部高度的相对处罚，不由开发分数预设答案。'}
]

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def csvwrite(p,rows):
    fs=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fs);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'review_pairs');args=ap.parse_args();root=args.root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    fg=out/'figures';fg.mkdir(exist_ok=True);photo_dir=out/'inputs/originals';photo_dir.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(root/'top_structure_20261012/review'));import render_user_figures as ren
    poolpath=root/'structure_height_preference_20261012/height/results/development907_candidates.json';pool=read(poolpath);byid={x['record_id']:x for x in pool}
    filterpath=root/'structure_height_preference_20261012/evidence/results/development_907_filter.json';filters={x['record_id']:x for x in read(filterpath)}
    # Explicit current registry and complete original holdout are applied again.
    registry_path=root/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json';registry=read(registry_path)
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    hh=list(csv.DictReader((b/'results/room_holdout_manifest.csv').open(encoding='utf-8-sig')))
    hold={x['record_id'] for x in hh if x['held_out_of_sample_and_future_calibration']=='True'}
    if len(hold)!=282:raise ValueError('holdout lineage mismatch')
    exposed={x['record_id'] for x in registry['screen_records_in_original_holdout']};groups=set(registry['groups_touched_by_this_screen'])
    assert all(x['record_id'] not in hold and x['record_id'] not in exposed and x['room_group'] not in groups for x in pool)
    geoms=read(b/'inputs/current_geometry_compact.json')['geometries'];objects={x['object_id']:x for x in read(b/'inputs/current_formal_loader_data.json')['objects']};images={x['image_id']:x for x in read(root/'study_data/original_image_index.json')}
    raw={x['record_id']:x for x in csv.DictReader((root/'top_structure_20261012/representation/results/representation_signals_all3152.csv').open(encoding='utf-8-sig'))}
    # Full enumeration is retained: it is active development selection, not a
    # held-out win rate. Multiple record pairs may repeat the same frozen rings.
    pair_search=[]
    for a,z in itertools.combinations(pool,2):
        if a['image_id']!=z['image_id'] or a['reference_object_id']!=z['reference_object_id']:continue
        m1=a['Q_dbounded1_hsplit']-z['Q_dbounded1_hsplit'];m2=a['Q_dbounded2_hsplit']-z['Q_dbounded2_hsplit']
        if m1*m2>=-1e-10:continue
        pair_search.append({'record_a':a['record_id'],'record_b':z['record_id'],'image_code':a['image_code'],
                            'applicability_explicit':a['applicability_confirmed'] and z['applicability_confirmed'],
                            'cap1_margin_a_minus_b':m1,'cap2_margin_a_minus_b':m2,'no_human_preference_inferred':True})
    csvwrite(out/'candidate_crossing_pairs_research.csv',pair_search)
    records=[];selected=[];fig_manifest=[];cols={'ref':'#cc3b74','raw':'#e99a18','processed':'#117b8a'}
    for choice in CHOICES:
        pair=choice['pair_id'];aa=[byid[rid] for rid in choice['records']]
        assert len({x['image_id'] for x in aa})==1 and len({x['reference_object_id'] for x in aa})==1
        assert all(filters[x['record_id']]['descriptive_development_allowed'] and x['applicability_confirmed'] for x in aa)
        photo=images[aa[0]['image_id']];dest=photo_dir/(aa[0]['image_code']+'.png')
        # Prefer the delivered, hashed original; the historical index may retain
        # an absolute path to a different execution workspace.
        source=next((p for p in [dest,Path(__file__).resolve().parent/'review_pairs/inputs/originals'/dest.name,Path(photo['local_path'])] if p.is_file()),dest)
        assert sha(source)==photo['sha256']
        if not dest.exists():shutil.copyfile(source,dest)
        assert sha(dest)==photo['sha256']
        photo_size=Image.open(dest).size
        assert photo_size==(photo['original_width'],photo['original_height'])
        for label,m in zip(['A','B'],aa):
            o=objects[m['object_id']];g=geoms[m['object_id']];r=geoms[m['reference_object_id']]
            pp=np.asarray(o['points_1024x512']);reproj=np.empty_like(pp);reproj[::2]=ren.pixels(g['top3d']);reproj[1::2]=ren.pixels(g['bottom3d'])
            dx=(reproj[:,0]-pp[:,0]+512)%1024-512;err=max(abs(dx).max(),abs(reproj[:,1]-pp[:,1]).max());assert err<1e-8
            current=np.asarray(o['before_preprocessing_points'])[o['ordered_source_point_indices']]
            d=(current[1::2,0]-current[::2,0]+512)%1024-512;mid=(current[::2,0]+d/2)%1024
            assert np.max(abs((mid-pp[::2,0]+512)%1024-512))<1e-8
            c={'record_id':m['record_id'],'blind_id':pair+label,'pair_id':pair,'within_pair_label':label,'image_id':m['image_id'],'scale_group':pair,'current_formal_input':o,'current_formal_reference_input':objects.get(m['reference_object_id']),'frozen_annotation_geometry':g,'fixed_reference_geometry':r,'reference_object_id':m['reference_object_id'],
               'photo':{'relative_path':str(dest.relative_to(out)),'sha256':photo['sha256'],'width':photo_size[0],'height':photo_size[1]},'source_current_matches_export':o['before_preprocessing_points']==o['original_export_points'],'reprojection_max_px':float(err),'crops':choice['crops']}
            records.append(c)
        selected.append({**choice,'image_id':aa[0]['image_id'],'image_code':aa[0]['image_code'],'source_photo_sha256':photo['sha256'],'full_reference_approved_this_round':False,'prior_applicability_explicit':True,
                         'source_scores_and_components':[{k:m.get(k) for k in ['record_id','worker_id','condition','room_group','iou_2d','iou_3d_corner_mean','dir','flat','Hmean','Hcenter','S_top_deg','S_bottom_deg','Q_v11','Q_official_iou3d','Q_dbounded1_hsplit','Q_dbounded2_hsplit','Q_dbounded1_d10_hsplit','Q_dbounded1_hsplit_weakTop']} for m in aa],
                         'current_pair_residuals':[{'record_id':m['record_id'],'X_rms_deg':float(raw[m['record_id']]['X_pair_rms_deg']),'X_max_deg':float(raw[m['record_id']]['X_pair_max_deg'])} for m in aa],
                         'answers_are_missing':True,'newly_selected_does_not_mean_historically_unexposed':True})
    limits=ren.limits_for(records)
    def save(fig,name,kind,pair):
        p=fg/name;fig.savefig(p,dpi=130,facecolor='white',pil_kwargs={'quality':93},bbox_inches='tight',pad_inches=.22);plt.close(fig)
        fig_manifest.append({'file':str(p.relative_to(out)),'kind':kind,'pair_id':pair,'sha256':sha(p),'bytes':p.stat().st_size,'contains_scores_or_method_names':False,'scale_group':pair})
    for choice in CHOICES:
        pair=choice['pair_id'];rr=[r for r in records if r['pair_id']==pair];im=np.asarray(Image.open(out/rr[0]['photo']['relative_path']).convert('RGB'))
        fig,axs=plt.subplots(2,2,figsize=(16,9.5));fig.subplots_adjust(left=.045,right=.985,top=.94,bottom=.065,hspace=.28,wspace=.08)
        for j,c in enumerate(rr):
            for k in range(2):
                ax=axs[j,k];ren.background(ax,im);ren.draw_geometry_erp(ax,c['fixed_reference_geometry'],cols['ref']);ren.full_axes(ax)
                if k==0:ren.draw_current(ax,c,cols['raw']);title='Current edited input, before shared x'
                else:ren.draw_geometry_erp(ax,c['frozen_annotation_geometry'],cols['processed']);ren.draw_processed_points(ax,c,cols['processed']);title='Frozen processed reconstruction'
                ax.set_title(c['blind_id']+' | '+title,fontsize=11)
        save(fig,pair+'_input_processed.jpg','same_image_two_input_versions',pair)
        fig=plt.figure(figsize=(16,10.8));grid=fig.add_gridspec(2,3,width_ratios=[1,1.1,1.1],left=.05,right=.95,top=.93,bottom=.085,wspace=.19,hspace=.24)
        for j,c in enumerate(rr):handles=ren.geometry_axes(fig,[grid[j,i] for i in range(3)],c,limits[pair],cols,[(28,-55),(18,35)])
        fig.legend(handles,[h.get_label() for h in handles],loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.5,.022));fig.suptitle(pair+' | Shared physical limits and orthographic views',fontsize=13,y=.98)
        save(fig,pair+'_same_scale_geometry.jpg','same_image_same_physical_axes',pair)
        fig,axs=plt.subplots(2,2,figsize=(10,11));fig.subplots_adjust(left=.08,right=.95,top=.93,bottom=.06,hspace=.24,wspace=.25)
        for j,c in enumerate(rr):
            for k,box in enumerate(choice['crops']):
                ax=axs[j,k];ren.background(ax,im,True);ren.draw_geometry_erp(ax,c['fixed_reference_geometry'],cols['ref']);ren.draw_current(ax,c,cols['raw']);ren.draw_geometry_erp(ax,c['frozen_annotation_geometry'],cols['processed']);ren.draw_processed_points(ax,c,cols['processed'])
                ax.set_xlim(box[0],box[2]);ax.set_ylim(box[3],box[1]);ax.set_aspect('equal');ax.set_title(c['blind_id']+f' | Detail {k+1}');ax.set_xlabel('ERP x');ax.set_ylabel('ERP y')
        save(fig,pair+'_details.jpg','same_crop_bounds_for_both',pair)
    write(out/'inputs/selected_pairs_full.json',{'records':records,'shared_limits':limits,'registry_sha256':sha(registry_path),'source_pool_sha256':sha(poolpath),'all_current_pair_midpoints_verified':True,'all_original_holdout_used':0,'new_unshared_3d_inferred':False})
    write(out/'figures/manifest.json',fig_manifest)
    write(out/'selection_research.json',{'selection_stage':'after finite candidate results and initial diagnostic inspection; development selection, not independent validation','candidate_crossing_record_pairs':len(pair_search),'candidate_crossing_images':len({x['image_code'] for x in pair_search}),'explicit_applicability_crossing_record_pairs':sum(x['applicability_explicit'] for x in pair_search),'record_pairs_are_not_independent_samples':True,'selected_pairs':selected,'latest_registry_sha256':sha(registry_path),'original_holdout_records_excluded':282,'exposed_groups_excluded':4,'remaining_103_clean_claim':False,'actual_original_photos_visually_inspected':['wc2JMjhGNzB-18','Z6MFQCViBuw-08','wc2JMjhGNzB-40'],'pair_order_choice_not_human_preference':True})
    options=['A整体更好','B整体更好','两者接近','问题不同，难以综合排序','不确定','参考或范围有问题']
    answer_template={'schema':'targeted_pair_review_20261012','status':'prepared_not_reviewed','answers':[{'pair_id':c['pair_id'],'processed_result_preference':None,'current_input_preference':None,'comment':'','confidence':None} for c in CHOICES]}
    write(out/'answers_blank.json',answer_template)
    def embedded(p):
        mime='image/png' if p.suffix=='.png' else 'image/jpeg';return 'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()
    sections=[]
    for c in CHOICES:
        pair=c['pair_id'];rs=''.join(f'<label><input type="radio" name="{pair}_choice" value="{html.escape(s)}">{html.escape(s)}</label>' for s in options)
        raw_choices=''.join(f'<label><input type="radio" name="{pair}_raw" value="{html.escape(s)}">{html.escape(s)}</label>' for s in options)
        imgs=''.join(f'<details {"open" if kind=="same_scale_geometry" else ""}><summary>{label}</summary><img src="{embedded(fg/(pair+"_"+kind+".jpg"))}" alt="{pair} {label}"></details>' for kind,label in [('same_scale_geometry','同一比例的底面和三维'),('input_processed','原点位与统一后对照'),('details','相同范围的局部放大')])
        photo_path=out/next(r['photo']['relative_path'] for r in records if r['pair_id']==pair)
        sections.append(f'<section><h2>{pair}</h2><p>{html.escape(c["question"])}</p><details><summary>原图</summary><img src="{embedded(photo_path)}" alt="{pair} 原图"></details>{imgs}<fieldset><legend>当前编辑后的原点位质量（共享x之前）</legend>{raw_choices}</fieldset><fieldset><legend>统一后的固定重建结果质量</legend>{rs}</fieldset><p><textarea id="{pair}_comment" placeholder="可选：最影响判断的具体问题"></textarea></p></section>')
    js='''<script>document.getElementById('export').onclick=()=>{const ids=['C01','C02','C03','C04'];const data={schema:'targeted_pair_review_20261012',status:'human_response',answers:ids.map(id=>({pair_id:id,processed_result_preference:document.querySelector('input[name="'+id+'_choice"]:checked')?.value||null,current_input_preference:document.querySelector('input[name="'+id+'_raw"]:checked')?.value||null,comment:document.getElementById(id+'_comment').value,confidence:null}))};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='targeted_pair_review_answers.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};</script>'''
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>布局作答对照材料</title><style>body{font:17px/1.7 system-ui,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;color:#20242a;background:#fafbfd}h1,h2{line-height:1.3}section{background:white;border:1px solid #dce2e8;border-radius:10px;padding:22px;margin:28px 0}img{width:100%;height:auto}summary{cursor:pointer;font-weight:650;padding:9px}label{display:block;padding:4px}fieldset{border:1px solid #dce2e8;margin-top:18px}textarea{width:96%;min-height:75px;font:inherit}button,select{font:inherit;padding:8px}small{color:#555}</style><h1>布局作答对照材料</h1><p>本材料准备供完整交付核验后选择性复核，目前没有预填答案。每组是同一图片下两份作答。可选择性复核；每组分别判断当前点位与统一后的结果。不需要给出精确分数。</p><p>粉色为当前给定参考，橙色为当前编辑版本在统一横坐标之前的点位，蓝绿色为已有固定重建。没有从平均前点位新推断另一份完整三维房间。两份作答采用相同的物理坐标范围与观察角度。可选择不确定、难以排序或参考有问题。</p><p>匿名复核不代表这些图片从未看过，也不构成独立验证集。未答保持缺失，不会转成合格或非严重标签。</p>'''+''.join(sections)+'<button id="export">导出已填答案 JSON</button><p><small>答案只在当前页面中生成；不会自动上传。未回答的问题保留为 null。</small></p>'+js+'</html>'
    (out/'review_pairs_blind_user.html').write_text(page,encoding='utf-8')
    source_paths=[poolpath,filterpath,registry_path,b/'inputs/current_geometry_compact.json',b/'inputs/current_formal_loader_data.json',b/'results/room_holdout_manifest.csv',root/'study_data/original_image_index.json',root/'top_structure_20261012/review/render_user_figures.py',root/'top_structure_20261012/representation/results/representation_signals_all3152.csv']
    write(out/'material_manifest.json',{'script_sha256':sha(Path(__file__)),'figure_count':len(fig_manifest),'original_images':len({c['image_id'] for c in records}),'cases':len(records),'optional_pairs':len(CHOICES),'questions':len(CHOICES),'response_fields_per_pair':2,'all_pairs_optional_to_answer':True,'html_bytes':(out/'review_pairs_blind_user.html').stat().st_size,'html_sha256':sha(out/'review_pairs_blind_user.html'),'labels_or_scores_leaked_in_html':False,'prepared_not_submitted_to_user_for_review':True,'source_hashes':{str(p.relative_to(root)):sha(p) for p in source_paths},'bundled_originals_take_precedence_over_historical_absolute_paths':True})
    print(json.dumps({'figures':len(fig_manifest),'pairs':len(CHOICES),'html_bytes':(out/'review_pairs_blind_user.html').stat().st_size},ensure_ascii=False))

if __name__=='__main__':main()
