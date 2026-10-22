#!/usr/bin/env python3
"""Research plates from exact frozen geometry and current pre-average pairs.

These descriptive plates are not human labels and do not grant scope eligibility.
Uses verified original PNG bytes, keeps both coordinate layers and equal 3-D axes.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RECORDS=['R00637','R03106','R01357','R02049','R03041','R00726']

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);args=ap.parse_args()
    root=args.root.resolve();out=args.out.resolve();figdir=out/'figures';figdir.mkdir(parents=True,exist_ok=True);indir=out/'inputs';origdir=indir/'originals';origdir.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(root/'top_structure_20261012/review'));import render_user_figures as renderer
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    components={x['record_id']:x for x in read(b/'results/current_components.json')}
    objects={x['object_id']:x for x in read(b/'inputs/current_formal_loader_data.json')['objects']}
    geoms=read(b/'inputs/current_geometry_compact.json')['geometries']
    images={x['image_id']:x for x in read(root/'study_data/original_image_index.json')}
    filters={x['record_id']:x for x in read(root/'structure_height_preference_20261012/evidence/results/development_907_filter.json')}
    old={x['record_id']:x for x in read(root/'study_quality/results/candidate_scores.json')}
    metrics={x['record_id']:x for x in csv.DictReader((out/'results/development907_structural_metrics.csv').open(encoding='utf-8-sig'))}
    metrics.update({x['record_id']:x for x in csv.DictReader((out/'results/real39_structural_metrics.csv').open(encoding='utf-8-sig'))})
    registry=read(root/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    exposed={x['record_id'] for x in registry['screen_records_in_original_holdout']}
    exposed_groups=set(registry['groups_touched_by_this_screen'])
    hold_rows=list(csv.DictReader((b/'results/room_holdout_manifest.csv').open(encoding='utf-8-sig')))
    hold={x['record_id'] for x in hold_rows if x['held_out_of_sample_and_future_calibration']=='True'}
    assert len(hold)==282
    records=[];manifest=[]
    for rid in RECORDS:
        assert rid not in exposed and rid not in hold
        assert rid in old or filters[rid]['descriptive_development_allowed']
        r=components[rid];o=objects[r['object_id']];im=images[r['image_id']]
        assert filters[rid]['room_group'] not in exposed_groups
        source=next((p for p in [origdir/(r['image_code']+'.png'),Path(__file__).resolve().parent/'inputs/originals'/(r['image_code']+'.png'),Path(im['local_path'])] if p.is_file()),origdir/(r['image_code']+'.png'))
        assert sha(source)==im['sha256'];dest=origdir/(r['image_code']+'.png')
        if not dest.exists():shutil.copyfile(source,dest)
        assert sha(dest)==im['sha256']
        a,g=geoms[r['object_id']],geoms[r['reference_object_id']]
        pts=np.asarray(o['points_1024x512']);back=np.empty_like(pts)
        back[::2]=renderer.pixels(a['top3d']);back[1::2]=renderer.pixels(a['bottom3d'])
        dx=(back[:,0]-pts[:,0]+512)%1024-512;reprojection=float(max(abs(dx).max(),abs(back[:,1]-pts[:,1]).max()))
        assert reprojection<1e-8
        cur=np.asarray(o['before_preprocessing_points'])[o['ordered_source_point_indices']]
        delta=(cur[1::2,0]-cur[::2,0]+512)%1024-512
        mid=(cur[::2,0]+delta/2)%1024
        assert np.max(abs((mid-pts[::2,0]+512)%1024-512))<1e-8
        cid=old[rid].get('old_case_id') if rid in old else rid
        c={'record_id':rid,'blind_id':cid or rid,'image_id':r['image_id'],'image_code':r['image_code'],'scale_group':rid,
           'current_formal_input':o,'fixed_reference_geometry':g,'frozen_annotation_geometry':a,
           'reference_object_id':r['reference_object_id'],'applicability_confirmed':filters.get(rid,{}).get('applicability_confirmed',False),
           'photo':{'relative_path':str(dest.relative_to(out)),'sha256':im['sha256'],'width':im['original_width'],'height':im['original_height']},
           'current_source_matches_original_export':o['before_preprocessing_points']==o['original_export_points'],
           'frozen_reprojection_max_px':reprojection,'metrics':metrics[rid]}
        records.append(c)
    col={'ref':'#cc3b74','raw':'#e99a18','processed':'#117b8a'};limits=renderer.limits_for(records)
    for c in records:
        im=np.asarray(Image.open(out/c['photo']['relative_path']).convert('RGB'))
        fig=plt.figure(figsize=(16,16));gs=fig.add_gridspec(3,3,height_ratios=[1.0,1.0,.82],left=.05,right=.97,top=.93,bottom=.06,hspace=.25,wspace=.22)
        for j in range(2):
            ax=fig.add_subplot(gs[j,:]);renderer.background(ax,im);renderer.draw_geometry_erp(ax,c['fixed_reference_geometry'],col['ref']);renderer.full_axes(ax)
            if j==0:renderer.draw_current(ax,c,col['raw']);title='Current edited coordinates BEFORE shared x (orange); fixed reference (pink)'
            else:renderer.draw_geometry_erp(ax,c['frozen_annotation_geometry'],col['processed']);renderer.draw_processed_points(ax,c,col['processed']);title='Frozen processed geometry AFTER shared x (teal); fixed reference (pink)'
            ax.set_title(c['blind_id']+' / '+c['image_code']+' | '+title,fontsize=11)
        handles=renderer.geometry_axes(fig,[gs[2,i] for i in range(3)],c,limits[c['scale_group']],col,[(28,-55),(18,35)])
        fig.legend(handles,[x.get_label() for x in handles],loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.5,.025))
        fig.suptitle('Research diagnostic; conditional reference status preserved; not a new human quality judgment',fontsize=12,y=.984)
        p=figdir/(c['blind_id']+'_structure_plate.jpg');fig.savefig(p,dpi=120,facecolor='white',pil_kwargs={'quality':93},bbox_inches='tight',pad_inches=.22);plt.close(fig)
        manifest.append({'record_id':c['record_id'],'case_id':c['blind_id'],'image_id':c['image_id'],'file':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p),'frozen_reconstruction':True,'new_unshared_3d_constructed':False,'new_quality_label':None})
    (indir/'selected_real_cases.json').write_text(json.dumps({'records':records,'all_current_pair_midpoints_verified':True,'exposed_records_used':0,'source_points_unchanged':True},ensure_ascii=False,indent=2)+'\n')
    (figdir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'figures':len(manifest),'originals':len({x['image_id'] for x in records}),'files':manifest},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
