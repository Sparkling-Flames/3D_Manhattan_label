"""Separate anonymous user ZIP and private mapping; verify every payload."""
import argparse,hashlib,importlib.metadata,json,platform,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def archive(path,files,prefix=None):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p,name in files:
   info=zipfile.ZipInfo((prefix or '')+name,date_time=(2026,10,11,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 with zipfile.ZipFile(path) as z:assert z.testzip() is None
 return {'filename':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'files':len(files)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--review-root',type=Path,default=ROOT);args=ap.parse_args();root=args.review_root;res=root/'results';user=root/'user';art=root/'artifacts';art.mkdir(exist_ok=True);selection=read(res/'selection_private.json');order=read(res/'display_order.json');renders=read(res/'render_manifest_private.json');response=read(user/'responses.json');schema=read(res/'receipt_schema_anonymous.json');tests=read(res/'review30_browser_tests.json')
 assert sha(res/'selection_private.json')=='bf1c3265184fe21d313c96415c80741a65ce6f531f1141aa7ff79ea1e40d2bf8';assert order['selection_sha256']==sha(res/'selection_private.json');assert len(set(order['primary_display_order']))==30;assert response['case_ids']==[f'T{i:02d}' for i in range(1,31)] and response['display_order']==order['primary_display_order'];assert len(response['answers'])==30 and len(response['pair_answers'])==1
 assert all(r[f]=='' for r in response['answers'] for f in schema['active_fields'][r['case_id']]);assert all(r[f]=='' for r in response['pair_answers'] for f in schema['pair_active_fields'][r['pair_id']]);assert tests['failed']==0 and tests['passed_groups']==14
 assert {r['case_id'] for r in renders['records']}==set(response['case_ids']);assert len(renders['records'])==30
 for r in renders['records']:
  assert len(r['files'])==4 and not r['B_top_created']
  for f in r['files']:assert sha(user/f['filename'])==f['sha256']
  assert sha(user/(r['case_id']+'_original.jpg'))==r['photo_sha256']
 pair=[r for r in renders['records'] if r['case_id'] in ['T23','T24']];assert pair[0]['BEV_span_h']==pair[1]['BEV_span_h'] and pair[0]['3D_span_h']==pair[1]['3D_span_h'] and pair[0]['center_xyz_h']==pair[1]['center_xyz_h']
 forbidden=['worker_id','Q_alpha30','Q_alpha45','Q_stage13','Q_stage24','v1.1','selection_labels']+[r['object_id'] for r in selection['records']]+[r['selection_private']['record_id'] for r in selection['records']]
 textual='\n'.join(p.read_text(encoding='utf-8-sig') for p in user.iterdir() if p.suffix in ['.html','.js','.json','.csv','.md']);assert all(t not in textual for t in forbidden)
 allowed={f['filename'] for r in renders['records'] for f in r['files']}|{'index.html','review30_receipt.js','responses.json','responses.csv','使用说明.md'};assert {p.name for p in user.iterdir() if p.is_file()}==allowed;assert len(allowed)==125
 payload=[{'filename':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(user.iterdir()) if p.is_file()];write(res/'user_payload_manifest.json',{'image_count':120,'primary_answer_count':30,'optional_pair_count':1,'all_answers_initially_blank':True,'user_numeric_and_personnel_identifiers_present':False,'files':payload})
 specs={'ERP_overlay':{'size':[1536,768],'line_samples_per_edge':161,'panorama_seam_split_u_jump':.5,'aspect':.5,'geometry_registration':'none'},'BEV':{'size':[840,840],'span_factor':1.2,'shared_for_same_image':True},'3D':{'size':[840,840],'span_factor':1.2,'elev':24,'azim':-60,'shared_for_same_image':True,'new_B_top_created':False,'space_cases_floor_only':True},'colors':{'annotation':'#ed6a05','reference_A':'#149341','reference_B':'#1978c9'},'versions':{x:importlib.metadata.version(x) for x in ['numpy','matplotlib','Pillow','playwright']},'python':platform.python_version(),'fonts':{'regular_path':'/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','regular_sha256':sha(Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'))},'receipt_format_version':'quality_review30_receipt_v1','display_seed':order['seed'],'case_id_order_unchanged':True,'selection_modified':False,'primary_completion_rule':'nonempty absolute_quality or space_compatibility; unknown counts; blank/view/reason-only does not','optional_pair_completion_separate':True};write(res/'render_and_receipt_parameters.json',specs)
 userzip=archive(art/'quality_review30_user_20261011.zip',[(p,p.name) for p in sorted(user.iterdir()) if p.is_file()],prefix='user/')
 private_names=['selection_private.json','selection_private.csv','boundary_coverage_private.json','selection_audit.json','selection_checks.json','display_order.json','selected_geometry_private.json','pixel_audit_private.json','render_manifest_private.json','receipt_schema_anonymous.json','render_and_receipt_parameters.json','user_payload_manifest.json','review30_browser_tests.json']
 privatezip=archive(art/'quality_review30_private_mapping_20261011.zip',[(res/n,n) for n in private_names],prefix='private/')
 summary={'delivery_version':'quality_review30_final_render_v1','selected_record_count':30,'selected_object_count':30,'quality_count':24,'space_count':6,'primary_display_order':order['primary_display_order'],'seed':order['seed'],'selection_sha256':sha(res/'selection_private.json'),'display_order_sha256':sha(res/'display_order.json'),'selection_unchanged':True,'old8_work_unchanged':True,'room_holdout_overlap':0,'primary_images':120,'optional_pair_reused_images':8,'all_blank_defaults':True,'browser_tests_passed_groups':14,'B_top_created':False,'strict_Manhattan_wall_certification_claimed':False,'owner_selection_approval_received':True,'owner_final_render_acceptance_pending':True,'owner_reported_final_24_Q_representation_check':{'max_Q_range':0.0004662692887080766,'six_ring_representations':True,'sampling':[2048,4096],'no_crossing_thresholds':[50,60,75,85,90,95],'source':'owner message; owner independently archives evidence','this_executor_repeated':False},'artifacts':[userzip,privatezip]};write(res/'final_delivery_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
