"""固定输入三模型看图批次；复用现有看图器，不改参考、资格或工作参数。"""
import copy
import csv
import importlib.util
import json
import os
import random
import shutil
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from .scope_quality_scoring_20261016 import scoring_engine
from .scope_redundant_vertices_20261016 import normalize_boundary, compact_geometry

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/quality/quality_three_model_review_20261017'
SHARED=ROOT/'research/statistics/b8l2_shared_v6_20261016'
USAGE=ROOT/'research/statistics/b8l2_usage_v6_20261016'
PRO=Path('C:/Users/ASUS/Downloads/panorama_quality_resumed_final_20261016/panorama_quality_resumed_20261016')
BASE=ROOT/'analysis_results/quality/quality_ab_human_review_20261015'
SCOPE=ROOT/'research/data/scope_redundant_vertices_20261016'
SCHEMA='quality_three_model_review_20261017_v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def csvrows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def stratified(rows,bands,per_band,used):
    """按冻结B8L2分位覆盖取图；分位只用于抽样，不解释成人工档位。"""
    rows=sorted(rows,key=lambda r:(float(r['B8L2']),r['object_id']))
    rng=random.Random(20261017);result=[]
    for band in range(bands):
        group=rows[len(rows)*band//bands:len(rows)*(band+1)//bands]
        rng.shuffle(group);n=0
        for r in group:
            if r['image_id'] in used:continue
            result.append(dict(r,sampling_band=band));used.add(r['image_id']);n+=1
            if n==per_band:break
        if n!=per_band:raise ValueError('not enough distinct images in score band')
    return result


def compact_pair(g):
    b,t=g['bottom3d'],g['top3d']
    m=normalize_boundary([[p[0],p[2]] for p in b],[a[1]-z[1] for a,z in zip(t,b)])
    q=compact_geometry(g,m['pair_kept_1based']);q['original_labels']=m['pair_kept_1based']
    return q,m['pair_removed_1based']


def load_model(path):
    spec=importlib.util.spec_from_file_location('review_ebc2_frozen',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    return m


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    # 保存只依赖numpy/shapely的原模型，不引入存在资格问题的Pro批量入口。
    model_path=OUT/'ebc2_original.py'
    if not model_path.exists():shutil.copyfile(PRO/'src/envelope_quality.py',model_path)
    assert model_path.read_bytes()==(PRO/'src/envelope_quality.py').read_bytes()
    model=load_model(model_path)
    fixed=read(SHARED/'FROZEN_INPUTS.json')
    objects={o['object_id']:o for o in fixed['bundle']['data']['objects']}
    refs={r['target_id']:r for r in read(SHARED/'inputs/reference_catalog.json')}
    images={r['image_id']:r for r in fixed['difficulty']['records']}
    rows=csvrows(USAGE/'quality_records.csv');by_id={r['object_id']:r for r in rows}
    assert len(rows)==1787 and all(r['quality_usable']=='True' for r in rows)
    pro_scores={r['object_id']:r for r in csvrows(PRO/'results/SCORES_891.csv')}
    # 已看过的24例图片不混进新的分数覆盖随机抽样。
    feedback=read('C:/Users/ASUS/Downloads/quality_resumed_optional_feedback_20261016_v1.json')
    exposed={b['image_id'] for c in feedback['cases'] for b in c['bindings']}
    used=set(exposed)
    normal=[r for r in rows if r['quality_use']=='ordinary_primary' and r['condition']=='manual']
    chosen=[dict(r,phase='ordinary',selection='five_score_quantiles') for r in stratified(normal,5,4,used)]
    candidates=sorted((r for r in normal if r['object_id'] in pro_scores),
        key=lambda r:(-abs(float(pro_scores[r['object_id']]['EBC2_L2'])-float(r['B8L2'])),r['object_id']))
    extras=[]
    for r in candidates:
        if r['image_id'] in used:continue
        extras.append(dict(r,phase='ordinary',selection='model_disagreement'))
        used.add(r['image_id'])
        if len(extras)==6:break
    assert len(extras)==6
    chosen+=extras;random.Random(20261017).shuffle(chosen)
    doors=[r for r in rows if r['quality_use']=='doorway_quality' and r['condition']=='manual']
    # 门洞有限池按低中高覆盖，与普通批次保持不同图片。
    chosen += [dict(r,phase='doorway',selection='doorway_score_coverage') for r in stratified(doors,3,2,used)]
    geometries={};cards=[];scores={};variants={};provenance=[];scan=[];scopes=read(SCOPE/'scope_views.json')
    def photo_url(image_id):
        path=Path(images[image_id]['photo'])
        if not path.is_absolute():path=ROOT/path
        assert path.is_file(),str(path)
        assert path.resolve().is_relative_to(ROOT.resolve()),str(path)
        return quote(Path(os.path.relpath(path,OUT)).as_posix(),safe='/')
    with scoring_engine(SHARED/'inputs/measurement_engine.zip',SHARED/'inputs/working_models.py') as (engine,models):
        d10=replace(models.MODELS['B8L2'],version='B8L2-D10-20261016',direction_scale_deg=10.)
        def measure(a,r):
            old=engine.measure(a,r);new=model.normalized_pair(a,r)
            assert old['status']=='complete' and new['status']=='complete',(old.get('reasons'),new.get('reason'))
            m=old['metrics'];v=[m[k] for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')]
            return dict(B8L2=float(models.score(*v,models.MODELS['B8L2'])),D10=float(models.score(*v,d10)),EBC2=float(new['score_l2']))
        answer_cache={}
        redundant=[]
        for r in rows:
            a=engine.geometry(objects[r['object_id']]['points_1024x512']);ar,removed=compact_pair(a)
            ref=refs[r['current_target_id']];rr,ref_removed=compact_pair(ref['geometry'])
            scan.append(dict(object_id=r['object_id'],target_id=ref['target_id'],answer_removed=removed,reference_removed=ref_removed))
            if removed or ref_removed:
                redundant.append(dict(r,phase='redundant',selection='all_current_eligible_exact_redundancy'))
                answer_cache[r['object_id']]=a
        for r in redundant+chosen:
            phase=r['phase'];idx=sum(c['phase']==phase for c in cards)+1
            cid={'redundant':'R','ordinary':'N','doorway':'D'}[phase]+f'{idx:02d}'
            ref=refs[r['current_target_id']];rid=ref['target_id'];oid=r['object_id']
            a=answer_cache.get(oid) or engine.geometry(objects[oid]['points_1024x512']);rg=copy.deepcopy(ref['geometry'])
            a['original_labels']=list(range(1,len(a['bottom3d'])+1));rg['original_labels']=list(range(1,len(rg['bottom3d'])+1))
            geometries[oid]=a;geometries[rid]=rg
            score=measure(a,rg);assert abs(score['B8L2']-float(r['B8L2']))<1e-8
            binding=dict(label='本份标注',record_id=r['record_id'] or r['inventory_record_id'],object_id=oid,image_id=r['image_id'],image_code=r['image_code'],reference_object_id=rid,photo=photo_url(r['image_id']),quality_use=r['quality_use'],condition=r['condition'])
            cards.append(dict(id=cid,phase=phase,bindings=[binding]));scores[cid]=score
            provenance.append(dict(case_id=cid,object_id=oid,image_id=r['image_id'],reference_id=rid,selection=r['selection'],sampling_band=r.get('sampling_band'),B8L2=score['B8L2']))
            if phase=='redundant':
                ca,da=compact_pair(a);cr,dr=compact_pair(rg)
                variants[cid]=dict(answer=ca,reference=cr,answer_removed=da,reference_removed=dr,
                    raw=score,reference_only=measure(a,cr),both=measure(ca,cr),kind='actual_annotation')
        # 两个完整参考自比只检验表示等价性，不冒充两份真人作答。
        for scope in scopes:
            pair=scope['paired_view']
            if not pair or not pair['mapping']['pair_removed_1based']:continue
            cid='R'+f'{sum(c["phase"]=="redundant" for c in cards)+1:02d}'
            rg=copy.deepcopy(refs[scope['target_id']]['geometry']);rg['original_labels']=list(range(1,len(rg['bottom3d'])+1));cr,dr=compact_pair(rg)
            oid='self-control:'+scope['target_id'];geometries[oid]=copy.deepcopy(rg);geometries[scope['target_id']]=rg
            score=measure(rg,rg);scores[cid]=score
            cards.append(dict(id=cid,phase='redundant',bindings=[dict(label='参考自比控制（非真人作答）',record_id='参考自比',object_id=oid,image_id=scope['image_id'],image_code=scope['image_code'],reference_object_id=scope['target_id'],photo=photo_url(scope['image_id']),quality_use='self_control',condition='control')]))
            variants[cid]=dict(answer=cr,reference=cr,answer_removed=dr,reference_removed=dr,raw=score,reference_only=measure(rg,cr),both=measure(cr,cr),kind='reference_self_control')
    cards.sort(key=lambda c:({'redundant':0,'ordinary':1,'doorway':2}[c['phase']],c['id']))
    manifest=dict(schema=SCHEMA,model='B8L2 / B8L2-D10 / EBC2-L2',cards=cards,counts=dict(Counter(c['phase'] for c in cards)),grade_scale='five_level_transition_v1',grades=['good','good_average','average','average_poor','poor','scope','uncertain'],input_version='b8l2_shared_v6_20261016_v1',usage_version='b8l2_scene_usage_v6_20261016_v2',review_purpose='development_comments_not_exact_score_targets',sampling_seed=20261017)
    for name,value in [('manifest.json',manifest),('geometries.json',geometries),('scores.json',scores),('redundancy_variants.json',variants),('selection_provenance.json',provenance),('redundancy_scan1787.json',scan)]:write(OUT/name,value)
    (OUT/'data.js').write_text('const DATA='+json.dumps(manifest,ensure_ascii=False)+';\nconst GEOMETRIES='+json.dumps(geometries)+';\nconst SCORES='+json.dumps(scores)+';\nconst VARIANTS='+json.dumps(variants)+';',encoding='utf-8')
    build_ui()
    build_scope_index(scopes,scan,variants)
    checks=dict(cards=len(cards),counts=manifest['counts'],distinct_quality_images=len({r['image_id'] for r in chosen}),actual_redundant_annotations=len(redundant),reference_self_controls=len(variants)-len(redundant),all_scope_views=len(scopes),complete_scope_references=sum(r['full_reference_available'] for r in scopes),mainline_changed=False,source_coordinates_changed=False,all_photos_exist=True,ebc_source_unmodified=True)
    checks['max_exact_compaction_score_delta']=max(abs(v[k][model]-v['raw'][model]) for v in variants.values() for k in ['reference_only','both'] for model in ['B8L2','D10','EBC2'])
    write(OUT/'CHECKS.json',checks);print(json.dumps(checks,ensure_ascii=False))


def build_ui():
    html=(BASE/'REVIEW.html').read_text(encoding='utf-8').replace('A10 / B8L2 质量核验','三种质量算法看图核验').replace('先普通24份，再门洞6份。','先看冗余点对照，再看普通26份、门洞6份。')
    html=html.replace('<main><nav>','<main><p><a href="REDUNDANCY.html">全部43个空间与冗余点影响</a> · <a href="RECORD.md">本次意见记录</a></p><nav>')
    html=html.replace('未拉直、平顶或修点。','原数据未改写；冗余对照仅在副本中删除几何等价点。')
    html=html.replace('<p id="phaseHint" class="notice"></p>','<p id="phaseHint" class="notice"></p><div id="redundancyPanel" hidden><label>对照视图 <select id="variant"><option value="raw">原始点对</option><option value="reference_only">只精简参考的等价点</option><option value="both">双方都精简等价点</option></select></label><p id="redundancyInfo"></p><pre id="redundancyScores" style="white-space:pre-wrap"></pre></div>')
    (OUT/'REVIEW.html').write_text(html,encoding='utf-8')
    for name in ['geometry-core.js','viewer3d.js']:shutil.copyfile(BASE/name,OUT/name)
    js=(BASE/'app.js').read_text(encoding='utf-8')
    start=js.index('  function progress()');end=js.index('  function drawPhoto()',start)
    js=js[:start]+'''  function phaseLabel(c){return {redundant:'冗余点',ordinary:'普通',doorway:'门洞'}[c.phase];}
  function progress(){const done=DATA.cards.filter(c=>state.decisions[c.id].grade!==null||state.decisions[c.id].comment.trim()).length;$('progress').textContent=`已记录 ${done}/${DATA.cards.length}`;for(const o of $('jump').options){const c=DATA.cards[Number(o.value)];o.textContent=`${phaseLabel(c)} ${c.id} · ${c.bindings[0].image_code}`;}}
  function score(){const c=DATA.cards[index],a=state.decisions[c.id],v=VARIANTS[c.id],s=v?v[$('variant').value]:SCORES[c.id];$('scores').hidden=!a.score_revealed_at;$('scores').textContent=`原B8L2：${s.B8L2.toFixed(2)}　D10：${s.D10.toFixed(2)}　EBC2-L2：${s.EBC2.toFixed(2)}。只判断大致是否合适，不要求逐例符合体感。`;$('reveal').textContent=a.score_revealed_at?'已查看三版分数':'可选：查看三版分数';}
  const originals=JSON.parse(JSON.stringify(GEOMETRIES));
  function variant(){const c=DATA.cards[index],b=c.bindings[0],v=VARIANTS[c.id],mode=$('variant').value;GEOMETRIES[b.object_id]=originals[b.object_id];GEOMETRIES[b.reference_object_id]=originals[b.reference_object_id];if(v&&mode!=='raw')GEOMETRIES[b.reference_object_id]=v.reference;if(v&&mode==='both')GEOMETRIES[b.object_id]=v.answer;$('redundancyPanel').hidden=!v;
    if(v){$('redundancyInfo').textContent=`${v.kind==='actual_annotation'?'真人作答':'参考自比控制，不是人工标注质量样本'}。参考删除原编号 ${v.reference_removed.join('、')||'无'}；作答删除原编号 ${v.answer_removed.join('、')||'无'}。只删除底边与高度同时等价的点。`; $('redundancyScores').textContent=['原始分数／仅精简参考／双方精简（满分100）',...['B8L2','D10','EBC2'].map(k=>`${k}: ${v.raw[k].toFixed(6)} / ${v.reference_only[k].toFixed(6)} / ${v.both[k].toFixed(6)}；最大差 ${Math.max(Math.abs(v.raw[k]-v.reference_only[k]),Math.abs(v.raw[k]-v.both[k])).toExponential(2)}`)].join('\\n');}
    drawPhoto();drawBEV();Review3D.open(c);score();
  }
''' +js[end:]
    js=js.replace("$('phase').textContent=c.phase==='ordinary'?'第一阶段 · 普通':'第二阶段 · 门洞';","$('phase').textContent=phaseLabel(c);")
    js=js.replace("$('next').textContent=index===DATA.counts.ordinary-1?'下一份：进入门洞':'下一份';","$('next').textContent='下一份';")
    js=js.replace("$('phaseHint').textContent=c.phase==='ordinary'?","$('phaseHint').textContent=c.phase==='redundant'?'这里核查等价点处理是否改变分数；参考自比不需要评人工质量，备注可单独填写。':c.phase==='ordinary'?")
    js=js.replace("image.src=b.photo;drawBEV();Review3D.open(c);score();save();","image.src=b.photo;$('variant').value='raw';variant();save();")
    js=js.replace("$('overlayMode').onchange=drawPhoto;","$('overlayMode').onchange=drawPhoto;$('variant').onchange=()=>{const a=state.decisions[DATA.cards[index].id];a.variant_views=a.variant_views||[];a.variant_views.push({view:$('variant').value,at:R.now()});variant();save();};")
    # 原编号仅显示底点，避免精简后的数组位置被误读为原标注点号。
    js=js.replace("g.bottom3d.forEach((p,j)=>segment(p,g.top3d[j]));","g.bottom3d.forEach((p,j)=>{segment(p,g.top3d[j]);const q=uv(p);ctx.font=`bold ${Math.max(14,w/90)}px system-ui`;ctx.strokeStyle='#17251e';ctx.lineWidth=3;const text=(oid===b.object_id?'A':'R')+(g.original_labels?.[j]||j+1);ctx.strokeText(text,q[0]+5,q[1]-6);ctx.fillStyle=color;ctx.fillText(text,q[0]+5,q[1]-6);ctx.strokeStyle=color;ctx.lineWidth=Math.max(2,w/600);});")
    js=js.replace("ctx.closePath();ctx.stroke();}\n    const [x,y]", "ctx.closePath();ctx.stroke();const g=GEOMETRIES[oid];ctx.font='13px system-ui';ctx.fillStyle=color;ring.forEach((p,j)=>{const q=xy(p);ctx.fillText((oid===b.object_id?'A':'R')+(g.original_labels?.[j]||j+1),q[0]+4,q[1]-5);});}\n    const [x,y]")
    # 复用现有回执校验；保留本轮额外视图曝光记录。
    js=js.replace("grade_at_first_score_reveal:null}","grade_at_first_score_reveal:null,variant_views:[]}")
    js=js.replace("grade===null?'not_reviewed':'reviewed'","grade===null?(state.decisions[c.id].comment.trim()?'comment_only':'not_reviewed'):'reviewed'")
    (OUT/'app.js').write_text(js,encoding='utf-8')


def build_scope_index(scopes,scan,variants):
    ordered=sorted(scopes,key=lambda r:(r['image_code'],not r['current_target'],r['target_id']))
    rows=[]
    for i,r in enumerate(ordered):
        n=sum(x['target_id']==r['target_id'] for x in scan)
        removed='、'.join(map(str,r['precision_removed'])) or '无残留中间点'
        status='完整参考可用' if r['full_reference_available'] else '缺合格完整顶界；三种完整分数留空'
        rows.append(f'<tr><td><a target="scope" href="../../data/scope_redundant_vertices_20261016/REVIEW.html#{i+1}">{r["image_code"]}'+(' 当前' if r['current_target'] else ' 备选')+f'</a></td><td>{removed}</td><td>{n}</td><td>{status}</td></tr>')
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>全部空间 冗余点与评分影响</title><style>body{font:16px/1.6 system-ui;margin:25px;color:#213a34}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}a{color:#176f65}iframe{width:100%;height:850px;border:1px solid #ccc}</style><h1>全部空间 冗余点与评分影响</h1><p>此前确认的41图43空间全部保留。点击表中图片，在下方查看原图与每个原编号。严格共线与精度内近共线仍分别显示；原始参考未改写。</p><p>当前1787份可用作答中，1份绑定了带严格冗余点的完整参考（wc2-61）；作答本身未发现严格等价冗余点。三模型的处理前后比较另有2份完整参考自比控制，不能算作真人样本。近共线点或缺顶界的空间不伪造完整分数。</p><p><a href="REVIEW.html">打开3个冗余对照与32份质量抽样</a> · <a href="RECORD.md">用户意见与审查说明</a></p><table><thead><tr><th>空间</th><th>严格或精度内中间点原编号</th><th>当前完整质量作答数</th><th>完整参考状态</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><iframe title="全部空间原图及逐点对照" name="scope" src="../../data/scope_redundant_vertices_20261016/REVIEW.html"></iframe></html>'''
    (OUT/'REDUNDANCY.html').write_text(html,encoding='utf-8')


if __name__=='__main__':run()
