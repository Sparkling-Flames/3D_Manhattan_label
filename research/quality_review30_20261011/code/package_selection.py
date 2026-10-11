"""Selection-stage evidence only: actual photos, selected geometry, and audit notes.
Does not generate final user review overlays, receipts, or human answers.
"""
import argparse,hashlib,json,zipfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
SOURCE=None
ASSETS=None
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 global ROOT,SOURCE,ASSETS
 ap=argparse.ArgumentParser();ap.add_argument('--frozen-root',type=Path,required=True);ap.add_argument('--photo-root',type=Path,required=True);ap.add_argument('--out-root',type=Path,default=ROOT);args=ap.parse_args();SOURCE=args.frozen_root;ASSETS=args.photo_root;ROOT=args.out_root
 d=read(ROOT/'results/selection_private.json');ns=list(dict.fromkeys(r['image_code'] for r in d['records']));font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',20)
 # Full panorama at half scale plus a pixel-exact central crop; source photos also archived.
 for i in range(0,len(ns),6):
  canvas=Image.new('RGB',(1536,6*420),'white')
  for j,n in enumerate(ns[i:i+6]):
   ids=[x['case_id'] for x in d['records'] if x['image_code']==n];ImageDraw.Draw(canvas).text((8,j*420),n+' | '+','.join(ids),font=font,fill='black')
   with Image.open(ASSETS/(n+'.jpg')) as im:im.load();canvas.paste(im.resize((768,384)),(0,j*420+30));canvas.paste(im.crop((384,192,1152,576)),(768,j*420+30))
  canvas.save(ROOT/'results'/f'pixel_sheet_{i//6+1}.jpg',quality=93)
 photozip=ROOT/'results/selected_original_photos_private.zip'
 with zipfile.ZipFile(photozip,'w',compression=zipfile.ZIP_STORED) as z:
  for n in ns:
   p=ASSETS/(n+'.jpg');info=zipfile.ZipInfo('originals/'+p.name,date_time=(2026,10,11,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.external_attr=0o100644<<16;z.writestr(info,p.read_bytes())
 geo=read(SOURCE/'inputs/current_geometry_compact.json')['geometries'];ids={x['object_id'] for x in d['records']}|{x['reference_object_id'] for x in d['records']};subset={k:geo[k] for k in sorted(ids)};confirmation={r['image_code']:r for r in read(SOURCE/'inputs/scope/normalized_confirmation_overlay.json')['records']}
 save(ROOT/'results/selected_geometry_private.json',{'selection_version':d['selection_version'],'source_geometry_sha256':sha(SOURCE/'inputs/current_geometry_compact.json'),'geometries':subset,'confirmed_B_floors_only':{r['case_id']:{'polygon_XZ_h':confirmation[r['image_code']]['polygon'],'top_status':'top_pending','new_B_top_created':False,'original_confirmation_ledger':confirmation[r['image_code']]} for r in d['records'][24:]},'user_answers_filled':False})
 notes={
 'wc2JMjhGNzB-40':'墙、窗和门框构成可见正交主结构；门洞后邻室与遮挡必须按认可GT范围比较。',
 'e9zR4mvMWw7-10':'卧室隔墙、门洞和窗框可见；开放门扇与床是遮挡，不能当布局边。',
 '7y3sRwLe3Va-13':'走廊转角及多个相邻门洞可见；范围/位置代理样本需明确认可空间。',
 'rPc6DW4iMge-20':'卫浴主墙和门洞可见；镜面与相邻空间不是新增目标依据。',
 'uNb9QFRL6hY-40':'大厅梁格与主墙可见；梁、拱饰、邻室开口造成顶界语义歧义，不能仅凭D判严重。',
 'B6ByNegPMKs-10':'办公室隔墙和外露设备可见；主顶面、设备及假顶混杂，H/S同时大的样本不能称纯高度实验。',
 'uNb9QFRL6hY-45':'同大厅另一视角，主墙/梁可见；顶界模型及开口范围需主审确认。',
 'q9vSo1VnCiC-15':'卧室木梁、顶面与门洞可见；实际木梁/顶面与全景投影曲线需区别，D端点仅条件几何诊断。',
 'B6ByNegPMKs-11':'办公室走廊、凸出立柱和相邻门洞可见；局部结构代理并非人工确认错误原因。',
 'Z6MFQCViBuw-08':'装饰餐厅墙面、门洞及格状顶面可见；柱饰及天花复杂度需主审确认认可边界。',
 'yqstnuAEVhm-27':'狭窄通道和多个突出隔墙可见；全景曲线与非矩形结构需依据GT/原图叠线确认，暂不声称纯D适用。',
 'B6ByNegPMKs-47':'办公室走廊有正交主墙/柱、开放管线及门洞；已见照片不能预填优劣。',
 'yqstnuAEVhm-05':'客厅直墙与展示柜可见；顶角装饰弧线与真实顶界需区别。',
 'q9vSo1VnCiC-02':'门厅及多个开口可见；通过门洞的邻室不自动并入当前认可GT空间。',
 'wc2JMjhGNzB-20':'狭窄门厅主墙和两个开口可见；参考边界的遮挡必须保留不确定选项。',
 'jtcxE69GiFV-09':'浴室隔墙、门洞与顶缘可见；浴缸弧形装饰与认可顶界有语义局限，F端点待叠线终审。',
 'jh4fc5c5qoQ-02':'小卧室/更衣通道可见，主墙/顶缘近直线；该例D/F/H同时较大，仅作联合诊断。',
 'wc2JMjhGNzB-18':'门厅的直墙和多个开口可见；此图片及两份记录已在C04展示，明确标记历史曝光。',
 'rPc6DW4iMge-22':'浴室、玻璃淋浴隔断与门洞可见；只审核已认可A/B底面，不从镜面或Q推断意图。',
 'pRbA3pwrgk9-02':'卫浴分区与玻璃/墙交界可见；空间B顶界待定，只比较底面。',
 'wc2JMjhGNzB-61':'卧室邻接空间及门洞可见；两目标近邻，仅是双兼容采样候选。',
 'uNb9QFRL6hY-26':'浴室、淋浴、浴缸和邻接门洞可见；角点/边界偏好冲突需保留，不能指定真实意图。',
 'uNb9QFRL6hY-67':'淋浴分区与更大浴室范围可见；两区别区相交的面积尺度不对称，不能直接叫斜跨真实意图。',
 'uNb9QFRL6hY-88':'浴室另一视角有门洞和分区；两参考均远是几何候选，允许不确定/两者均不匹配。'}
 assert set(notes)==set(ns)
 save(ROOT/'results/pixel_audit_private.json',{'inspection_scope':'实际读取24张1536x768 JPEG像素：四张接触图，三个复杂案例另查看原尺寸；不是最终叠线验收或人工质量答案。','decoded_unique_photos':24,'decoded_records':30,'all_selected_reference_errors_and_holds_remain_filtered':True,'owner_final_applicability_review_pending':True,'final_user_render_done':False,'photo_zip_sha256':sha(photozip),'photos':[{'image_code':n,'case_ids':[r['case_id'] for r in d['records'] if r['image_code']==n],'photo_sha256':sha(ASSETS/(n+'.jpg')),'visual_observation':notes[n],'owner_applicability_review_pending':True} for n in ns]})
 print('photos',len(ns),'ZIP',photozip.stat().st_size,'sha256',sha(photozip))
if __name__=='__main__':main()
