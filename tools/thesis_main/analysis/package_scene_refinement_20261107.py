"""Prepare only adopted scene assets and source photographs for Dot; never touch the paper."""
from pathlib import Path
import csv, json, shutil, zipfile
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'docs/thesis_main/论文写作工作资料'
OOS=WORK/'OOS分步重建_20261107'
DOOR=WORK/'门洞实景观察_20261107'
PACK=WORK/'Dot_Scene_Refinement_20261107'
CASES=[
 ('01_doorway','门洞交界',DOOR/'精细模型','doorway_complete.blend','doorway_display.blend','doorway_main.png','doorway_reverse.png',
  ['camera_comparison.png','turn_reprojection.png','turn_reprojection.json','VERIFICATION.json'],
  '浴室与走廊偏置相接；门框左右固定转折和开启门扇分开。重点精修门套厚度、窗框与器具比例，不沿有遗漏的GT闭合。'),
 ('02_oblique','斜墙',OOS/'oblique','reconstruction.blend','presentation.blend','main_render.png','reverse_render.png',
  ['source_view_comparison.png','wireframe.png','observed_points_and_depth.png','observed_points.json','model_manifest.json','verification.json'],
  '主角是两门之间的非正交墙面与连续回折。保留完整门区及楼梯入口三阶；不要恢复长梯间、高墙或远端门。原图支持楼梯继续，但后续不在本局部模型范围内。'),
 ('03_sloped_ceiling','斜顶',OOS/'attic','full_model.blend','presentation.blend','main.png','reverse.png',
  ['camera_check.png','camera_return_opposite.png','wireframe.png','candidate_points.png','candidate_points.json','mesh_wireframe.json','depth_check.json','validation.json'],
  '双坡与中央平顶连续相接，后窗上方保持封顶，只打开前段屋顶用于展示。近端全景接缝是同一个门洞；S9-23不能替代本房尺寸。'),
 ('04_split_ceiling','分层天花',OOS/'ceiling','full_model.blend','presentation.blend','main.png','reverse.png',
  ['camera_check.png','camera_return_opposite.png','wireframe.png','candidate_points.png','candidate_points.json','mesh_wireframe.json','depth_check.json','validation.json'],
  '保留起居区高顶、入口低顶、木梁与真实通道。门口浅色收边应对应照片；梁纹沿长轴，不能用地板板缝贴木梁。'),
 ('05_split_floor','分层地面',OOS/'stairs','reconstruction.blend','reconstruction.blend','main_render.png','reverse_render.png',
  ['source_view_comparison.png','wireframe.png','observed_points_and_depth.png','observed_points.json','model_manifest.json','verification.json','house_search/entry_15.png','house_search/index.json'],
  '主地面占主要面积，左侧小平台上行、中央落脚处、右侧下行分别建面。窗墙至推拉门墙的近侧转接已补回，不可再删成侧面缺口。下行通道沿墙走，不横向封堵。未找到该入口第二机位，后续梯段不作完整恢复。'),
 ('06_glazed_boundary','转向玻璃边界',OOS/'glazed_boundary','full_model.blend','presentation.blend','main.png','reverse.png',
  ['wireframe.png','observed_track_pixels.json','perspective_sources.json','source_comparison.png','source08_model.png','source03_model.png','source08_kitchen_model.png','Uw08_perspective_110.png','Uw03_perspective_110.png','asset_manifest.json'],
  '先以Uw08的固定底轨和玻璃接缝核对转向，再用03/01/06/16核对长向连通、端部和内部短墙。开启门扇不当固定边界。不能画成简单圆房，也不要将分片连续转向压成一条直线。')
]
PHOTO_SPECS={
 '01_doorway':('valid','2t7WUuJeko7',[('07','53937db036374126830e0f1203b04ead'),('06','3be66dc4f0fb46449d63b07d92c74f3f'),('08','5db6d45b905f458a8290e69ff3e8d820'),('15','b72b7b78675f429a9f382a44e551cffc'),('16','cc34e9176bfe47ebb23c58c165203134')]),
 '02_oblique':('test','x8F5xyUWy9e',[('09','a51a0e2811f342a599ae4cdb9b84ff23'),('01','1be9a97aada84e4795f64583ac0e3b76')]),
 '03_sloped_ceiling':('valid','S9hNv5qa7GM',[('07','53d54b73e58940019b731673e65c1902')]),
 '04_split_ceiling':('test','q9vSo1VnCiC',[('09','69591068e5614642b710a8fb7733bdeb'),('30','dc873df7717c43888a1cff13713fe146')]),
 '05_split_floor':('test','uNb9QFRL6hY',[('69','ce88ee8b7ee84fca92c13ab16599d90e')]),
 '06_glazed_boundary':('test','UwV83HsGsw3',[('08','71ada030981d4468b76dcebc1b6fb940'),('03','16af52545aff47afb4d7b330a49091a2'),('01','0f1385fc03994285ad8253b49516d77b'),('06','528d342bf5494b3b94983545d6a1a282'),('16','b979526475874ad68ae33f02d407a1fc')])
}

def prepare():
    PACK.mkdir(exist_ok=True)
    records=[]
    def copy(src,dst,role):
        assert src.is_file(),src
        dst=PACK/dst;assert dst.resolve().is_relative_to(PACK.resolve())
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        records.append({'file':dst.relative_to(PACK).as_posix(),'source':str(src),'role':role,'bytes':dst.stat().st_size})
    for key,title,src,full,pres,main,reverse,evidence,note in CASES:
        for source_name,dest_name in [(full,'full_model.blend'),(pres,'presentation.blend'),(main,'main.png'),(reverse,'reverse.png')]:copy(src/source_name,f'{key}/{dest_name}','adopted model/render')
        for name in evidence:copy(src/name,f'{key}/evidence/{name}','adopted observation or check')
        if key=='01_doorway':
            for name in ['07_observation.png','same_room_views.png','doorway_turns_detail.png']:copy(DOOR/name,f'{key}/evidence/{name}','photo evidence')
            copy(ROOT/'analysis_results/doorway_point_folding_20261107/doorway_proportion_fit.json',f'{key}/evidence/doorway_proportion_fit.json','photo/pose fit')
        if key=='06_glazed_boundary':
            for p in sorted((src/'evidence').glob('*')):
                if p.is_file():copy(p,f'{key}/evidence/{p.name}','adopted multi-view evidence')
            for name in ['model_manifest.json','model_parameters.json','checks.json','verification.json','validation.json','观察说明.md']:
                if (src/name).exists():copy(src/name,f'{key}/evidence/{name}','model documentation')
        split,house,views=PHOTO_SPECS[key]
        for tag,uid in views:copy(ROOT/f'data/mp3d_layout/{split}/img/{house}_{uid}.png',f'{key}/sources/{tag}_{house}_{uid}.png','original panorama; no enhancement')
        if key in ('02_oblique','03_sloped_ceiling','04_split_ceiling','05_split_floor'):
            stem=house+'_'+views[0][1]
            copy(ROOT/f'analysis_results/oos_depth_probe_20261107/{stem}.raw_pred_m.npy',f'{key}/evidence/predicted_radial_depth_m.npy','HoHoNet raw float prediction; not sensor depth')
        (PACK/key/'README.md').write_text(f'# {title}\n\n{note}\n\n- `presentation.blend`：当前主图镜头与显示状态。\n- `full_model.blend`：完整已建实体，含可恢复的顶盖。\n- `main.png`、`reverse.png`：本轮主反预览。\n- `sources/`：2048×1024原始全景，编号与原UUID保留。\n- `evidence/`：采用的观察、线框及核对记录。\n\n这些是照片支持的解释模型，未替换GT，也不是实验原答的精装版。\n',encoding='utf-8')
    copy(Path('C:/Users/ASUS/Downloads/全景室内布局论文样图制作SOP.docx'),'requirements/原始建模SOP.docx','user-supplied SOP')
    copy(WORK/'实景重建SOP_多视角与深度_20261107.md','requirements/多视角与深度SOP_项目源文档.md','SOP supplement; links refer to original project')
    copy(ROOT/'analysis_results/oos_depth_probe_20261107/RAW_MANIFEST.json','requirements/PREDICTED_DEPTH_SOURCE.json','prediction units and invalid-value handling')
    scripts=['rebuild_doorway_scene_20261107.py','rebuild_oos_ceilings_20261107.py','rebuild_oos_walls_floor_20261107.py','focus_oblique_20261107.py','render_scope_blender_20261107.py','render_photo_scope_blender_20261107.py']
    for name in scripts:copy(ROOT/'tools/thesis_main/analysis'/name,'code_reference/'+name,'construction code; original project paths retained')
    copy(OOS/'glazed_boundary/build_glazed_boundary.py','code_reference/build_glazed_boundary.py','glass reconstruction source')
    dot=WORK/'Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest/output'
    for name in ['appearance_assets.py','geometry_core.py']:copy(dot/name,'code_reference/dot_helpers/'+name,'appearance helper reference')
    with (PACK/'FILES.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['file','source','role','bytes']);writer.writeheader();writer.writerows(records)
    assert len([r for r in records if r['role'].startswith('original panorama')])==16
    assert len([r for r in records if r['file'].endswith('.blend')])==12
    # Delivery overview is a contact sheet, not a new scientific figure.
    board=Image.new('RGB',(2400,2400),'white');draw=ImageDraw.Draw(board);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',38)
    for i,(key,title,*_) in enumerate(CASES):
        x=i%2*1200;y=i//2*800
        draw.text((x+25,y+15),title,font=font,fill='#253c48')
        im=Image.open(PACK/key/'main.png').convert('RGB');im=ImageOps.contain(im,(1160,725),Image.Resampling.LANCZOS)
        board.paste(im,(x+(1200-im.width)//2,y+65+(725-im.height)//2))
    board.save(PACK/'OVERVIEW.png')
    changes=Image.new('RGB',(2400,880),'white');draw=ImageDraw.Draw(changes)
    for i,(key,label) in enumerate([('02_oblique','斜墙：楼梯仅留入口三阶'),('05_split_floor','分层地面：补回侧墙'),('06_glazed_boundary','新增：转向玻璃边界')]):
        draw.text((i*800+20,20),label,font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',29),fill='#253c48')
        im=ImageOps.contain(Image.open(PACK/key/'main.png').convert('RGB'),(790,790),Image.Resampling.LANCZOS)
        changes.paste(im,(i*800+(800-im.width)//2,75+(790-im.height)//2))
    changes.save(PACK/'CHANGES.png')
    print(json.dumps({'files_copied':len(records),'source_panoramas':16,'blend_files':12,'package':str(PACK)},ensure_ascii=False))

def archive():
    assert (PACK/'README.md').is_file() and (PACK/'PACKAGE_CHECK.json').is_file()
    check=json.loads((PACK/'PACKAGE_CHECK.json').read_text(encoding='utf-8'))
    assert len(check['models'])==12 and all(not r['missing_external_files'] for r in check['models'])
    for path in PACK.rglob('*'):
        assert path.suffix!='.blend1' and not path.name.startswith(('draft_','preview_')),path
    with (PACK/'FILES.csv').open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    for row in records:row['bytes']=(PACK/row['file']).stat().st_size
    with (PACK/'FILES.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['file','source','role','bytes']);writer.writeheader();writer.writerows(records)
    target=PACK.with_suffix('.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(PACK.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(PACK.parent))
    with zipfile.ZipFile(target) as z:
        assert len([n for n in z.namelist() if n.endswith('.blend')])==12
        assert all(i.file_size>0 for i in z.infolist())
    print(json.dumps({'zip':str(target),'MiB':round(target.stat().st_size/1024**2,2)},ensure_ascii=False))

if __name__=='__main__':
    import sys
    archive() if '--zip' in sys.argv else prepare()
