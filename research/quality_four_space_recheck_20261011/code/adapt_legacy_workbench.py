"""Patch archived v3.4.2 UI; keep its geometry.js byte-for-byte unchanged."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];dst=ROOT/'user/editor';src=ROOT/'vendor/v3.4.2/dist'
def replace(text,a,b):
 assert text.count(a)==1,(a[:80],text.count(a));return text.replace(a,b)
def main():
 app=(src/'app.js').read_text()
 app=replace(app,"KEY='layout-scope-crop-v1'","KEY='quality-four-space-recheck-v1:T30:159eac10:libfile_f704466496208191a307dced921787ab:v0'")
 app=replace(app,'let data,idx=0,',"let recheckState={case_id:'T30',status:'reference_pending',verdict:'',matching_region_ids:[],reason:'',confidence:'',source:'new_independent_rereview',original_history_overwritten:false};\nlet data,idx=0,")
 app=replace(app,"name:b?.primary_name||'原范围',draft:","name:b?.primary_name||'A · 原GT底面',visible:b?.primary_visible!==false,observation_support:b?.primary_observation_support||{status:'not_assessed',source:'not_assessed',record_ids:[],note:''},draft:")
 app=replace(app,'unrecovered_drafts:unrecoveredDrafts}));', 'unrecovered_drafts:unrecoveredDrafts,recheck_state:recheckState}));')
 app=replace(app,"$('#saved').textContent='浏览器保存不可用，请导出';","$('#saved').textContent='浏览器保存不可用：必须导出 JSON，关闭或刷新前请先导出';")
 app=replace(app,"setDraft(hist[c].pop());line=", "setDraft(hist[c].pop());line=") if False else app
 app=replace(app,'function save(){for(const c of data.images)', 'function save(){invalidateChangedReference();for(const c of data.images)')
 # Empty new slots are real empty drafts, not copies of A pretending to be new targets.
 app=replace(app,"if(fromCurrent", "if(fromCurrent") if False else app
 app=replace(app,"d.top_boundary_pending=true;d.updated_at=new Date().toISOString();const b=spaceRegions", "d.top_boundary_pending=true;d.updated_at=new Date().toISOString();const b=spaceRegions") if False else app
 # A new independent empty slot is exposed by the extra manager; legacy copy/from-GT remain explicit user operations.
 app=app.replace("allRegions().filter(r=>r.region_id!==activeRegion().region_id)","allRegions().filter(r=>r.region_id!==activeRegion().region_id&&r.visible!==false&&r.draft.polygon.length)")
 app=replace(app,"svgPoly(r.draft.polygon,'#6e72b7'","svgPoly(r.draft.polygon,regionColor(r.region_id)")
 app=replace(app,"trace(r.draft.polygon,'#959be0',3)","trace(r.draft.polygon,regionColor(r.region_id),3)")
 app=replace(app,"if(current){parts.push(svgPoly(current,", "if(current.length&&(activeRegion().visible!==false||pending())){parts.push(svgPoly(current,")
 app=replace(app,"if(canEdit()&&mode==='edge')current.forEach", "if(canEdit()&&mode==='edge'&&activeRegion().visible!==false)current.forEach")
 app=replace(app,"if($('#showCrop').checked)trace(preview||draft().polygon,'#38edb4',5);", "if($('#showCrop').checked&&(activeRegion().visible!==false||pending()))trace(preview||draft().polygon,'#38edb4',5);")
 app=replace(app,'renderSpaces();renderPhoto();renderNav();renderConfirmation();setEditAvailability()}', 'renderSpaces();renderSpaceManager();renderPhoto();renderNav();renderConfirmation();setEditAvailability();renderRecheck()}')
 app=replace(app,"$('#bev').style.pointerEvents=ok?'auto':'none'", "$('#topPending').checked=true;$('#topPending').disabled=true;$('#confirm').disabled=!ok||(!G.valid(draft().polygon)&&!G.valid(preview||[]));$('#bev').style.pointerEvents=ok?'auto':'none'")
 app=replace(app,"$('#topPending').onchange=()=>{draft().top_boundary_pending=$('#topPending').checked;", "$('#topPending').onchange=()=>{$('#topPending').checked=true;draft().top_boundary_pending=true;")
 app=replace(app,"$('#confirm').onclick=()=>{if(!canEdit())return;", "$('#confirm').onclick=()=>{if(!canEdit())return;if(!G.valid(draft().polygon)&&!G.valid(preview||[])){toast('空空间必须先画有效底面，再确认');return;}")
 app=replace(app,"schema:'manual_scope_crop_review_v2',editor_version:'3.4.2',latest_scope_review_source_commit", "schema:'quality_four_space_recheck_v1',editor_version:'four-space-recheck-v1',historical_feedback_binding:clone(data.feedback_binding||null),historical_feedback:clone(data.historical_feedback||null),independent_T30_rereview:clone(recheckState),user_target_directives:clone(data.user_target_directives||[]),scores_recomputed:false,latest_scope_review_source_commit")
 app=replace(app,"records:data.images.map(c=>{let d=draft(c);", "records:data.images.map(c=>{let d=draft(c);")
 app=replace(app,"image_code:c.image_code,image_id:c.image_id,reference_object_id:c.reference_object_id,original_GT_points_1024x512", "image_code:c.image_code,image_id:c.image_id,baseline_spaces:clone(c.baseline_spaces),reference_object_id:c.reference_object_id,original_GT_points_1024x512")
 app=replace(app,"exportData({applyNoOperationPolicy:true})", "exportData()")
 # No export or no-operation policy auto-confirms unchanged targets.
 app=replace(app,"function exportData(options={}){const out=rawExportData();return options.applyNoOperationPolicy?applyBatchNoOperationPolicy(out):out}", "function exportData(){return rawExportData()}")
 app=replace(app,"const updates={},confirmedUpdates={},spaceUpdates={};", "if(JSON.stringify(x.historical_feedback)!==JSON.stringify(data.historical_feedback)||JSON.stringify(x.historical_feedback_binding)!==JSON.stringify(data.feedback_binding)||JSON.stringify(x.user_target_directives)!==JSON.stringify(data.user_target_directives)||x.scores_recomputed!==false)throw Error('原历史回执/用户指定目标/无重算状态不匹配');\n const checkedRecheck=validateRecheck(x.independent_T30_rereview);\n const updates={},confirmedUpdates={},spaceUpdates={};")
 app=replace(app,"if(!c||r.reference_object_id!==c.reference_object_id", "if(!c||JSON.stringify(r.baseline_spaces)!==JSON.stringify(c.baseline_spaces)||r.reference_object_id!==c.reference_object_id")
 app=replace(app,"spaceUpdates[c.image_code]={active_region_id:incoming.active_region_id,primary_name:primary.name,alternatives};", "spaceUpdates[c.image_code]={active_region_id:incoming.active_region_id,primary_name:primary.name,primary_visible:primary.visible,primary_observation_support:primary.observation_support,alternatives};")
 app=replace(app,"b.alternatives.push({region_id:id,name:'空间 '+id.split('-')[1],draft:d,confirmed_version:null})","b.alternatives.push({region_id:id,name:'空间 '+id.split('-')[1],draft:d,confirmed_version:null,visible:true,observation_support:S.support(null,cur())})")
 app=replace(app,"if(!['manual_scope_crop_review_v1','manual_scope_crop_review_v2'].includes(x.schema)||x.source_commit!==data.source_commit||!Array.isArray(x.records))", "if(x.schema!=='quality_four_space_recheck_v1'||x.editor_version!=='four-space-recheck-v1'||x.GT_modified!==false||x.source_commit!==data.source_commit||!Array.isArray(x.records)||x.records.length!==1)")
 app=replace(app,"if(r.space_regions){", "if(!r.space_regions||r.reference_ready!==false||r.formal_eligibility_changed!==false)throw Error('必须保留四空间和非正式参考状态');if(r.space_regions){")
 app=replace(app," // Validate everything before changing any image; old-format imports retain alternatives.", " validateRecheckAgainst(checkedRecheck,[{region_id:'primary',draft:updates[cur().image_code],confirmed_version:confirmedUpdates[cur().image_code]},...spaceUpdates[cur().image_code].alternatives]);\n // Validate everything before changing any image.")
 app=replace(app,"if(confirmedUpdates[id]&&(!confirmations[id]||Date.parse(confirmedUpdates[id].confirmed_at)>Date.parse(confirmations[id].confirmed_at)))confirmations[id]=confirmedUpdates[id];", "if(JSON.stringify(confirmations[id]||null)!==JSON.stringify(confirmedUpdates[id]||null)&&confirmations[id])unrecoveredDrafts[id+':confirmation_before_import:'+new Date().toISOString()]=clone(confirmations[id]);if(confirmedUpdates[id])confirmations[id]=confirmedUpdates[id];else delete confirmations[id];")
 app=replace(app,"if(x.unrecovered_drafts&&Object.keys(x.unrecovered_drafts).length)unrecoveredDrafts['imported_recovery_'+new Date().toISOString()]=clone(x.unrecovered_drafts);", "for(const [key,value] of Object.entries(x.unrecovered_drafts||{})){if(!(key in unrecoveredDrafts))unrecoveredDrafts[key]=clone(value);else if(JSON.stringify(unrecoveredDrafts[key])!==JSON.stringify(value))unrecoveredDrafts[key+':import_conflict:'+new Date().toISOString()]=clone(value);}")
 # Deterministic restore for this independent dataset: repeated imports do not manufacture 'before import' duplicates.
 start="   for(const old of regionBundle(c)?.alternatives||[])";lines=app.splitlines();lines=[l for l in lines if not l.startswith(start)];app='\n'.join(lines)+'\n'
 app=replace(app,"save();loadImage(idx);toast('已导入并逐个重放校验；空间候选与旧版本草稿均保留')", "recheckState=checkedRecheck;save();loadImage(idx);toast('已导入并逐空间重放校验；A/B基线、历史30回答及独立复审均保留')")
 app=replace(app,"if(pending())throw Error('请先应用或取消预览');const f=e.target.files[0];if(!f)return;const x=JSON.parse(await f.text());", "if(pending())throw Error('请先应用或取消预览');const f=e.target.files[0];if(!f)return;if(f.size>5*1024*1024)throw Error('导入文件超过5 MiB');const x=JSON.parse(await f.text());")
 app=replace(app,"data=x;let saved=null,raw=null;", "data=x;let saved=null,raw=null;")
 app=replace(app,"const state=S.initialize(data,saved);", "if(saved?.recheck_state){try{recheckState=validateRecheck(saved.recheck_state)}catch(e){saved.unrecovered_drafts={...(saved.unrecovered_drafts||{}),rejected_recheck_state:clone(saved.recheck_state)};}}\n const state=S.initialize(data,saved);")
 app=replace(app,"window.workbench={exportData", "$('#showRegions').checked=true;$('#person').value='R02962';if(!draft().polygon.length)setMode('rectangle');render();\n window.workbench={getPreview:()=>clone(preview),getSnapMatches:()=>clone(snapMatches),worldToScreen:screen,worldPerCssPixel:worldPerPixel,getBaselines:()=>clone(cur().baseline_spaces),getRecheck:()=>clone(recheckState),newEmptyRegion,exportData")
 # Replace stale historical score cells with records/geometry only.
 app=app.replace("<td>${percent(m.missing)}</td><td>${percent(m.excess)}</td><td>${percent(m.symmetric_difference)}</td>", '')
 app=app.replace('点击应用修改确认。','点击应用只保存草稿；仍需单独确认。')
 app=app.replace("${esc(a.record_id)} · ${esc(a.worker_id)}", "${a.record_id==='R02962'?'T30 / ':''}${esc(a.record_id)} · ${esc(a.worker_id)}")
 # Append new manager functions (function declarations are hoisted).
 app=replace(app,"fetch('data.json').then(r=>{if(!r.ok)throw Error('data');return r.json()})", "Promise.resolve().then(()=>JSON.parse(document.getElementById('editor-data').textContent))")
 app += (ROOT/'code/four_space_ui_extension.js').read_text()
 (dst/'app.js').write_text(app,encoding='utf-8')
 h=(src/'index.html').read_text();h=h.replace('<title>空间范围全量复核</title>','<title>T30 · 四空间补画与独立复审</title>').replace('同房间范围复核 · v3.4.2','T30单图 · 复用v3.4.2编辑器').replace('按图片查证 · 全量可达','仅T30同一图片 · 20份作答可浏览')
 start=h.index('<details class="catalogueDownloads">');end=h.index('</details>',start)+len('</details>');h=h[:start]+'<details class="catalogueDownloads"><summary>本轮输入与历史回执</summary><a href="target_evidence.json" download>同图20份当前作答与GT绑定</a><a href="data.json" download>四空间编辑数据（A/B保留，C/D为空）</a><a href="../historical_feedback/quality_review30_receipt.json" download>收到的原始30份审核回执</a><a href="../review30/index.html">查看预填的30份历史回答与原视图</a></details>'+h[end:]
 h=h.replace('原图／全体轮廓图卡','原图与同图全部作答').replace('<th>漏出 GT 比</th><th>超出 GT 比</th><th>对称差 / GT</th>','')
 h=h.replace('以下漏出、超出与对称差均除以该次选定 GT 面积，来自既有历史计算。不同条件／资格分组不当作独立投票，不是本次新参考评分。','只展示当前作答、资格与来源；不计算新参考分数或支持人数。不同条件／重复作答不等于独立人员支持。')
 h=h.replace('<section class="spaceRegions"', '<section class="fourSpaceContext"><h2>T30参考待补充 · 原回答保留</h2><p>原回答：两者均不匹配；原原因：另一种空间。A/B底面坐标保留；C/D目前没有坐标，需用户画和确认。四种合理空间不等于四个坐标已经核实，也不自行指定哪两种没有人员支持。</p><p>T29另图的“实际计算的时候按照空间A进行匹配”已记录为用户指定A，不是自动归属。T21/T22停止空间不同仅保留为研究警报，本轮不改它们的参考。</p></section><section class="spaceRegions"')
 h=h.replace('</section><div class="panels">','</section><section id="spaceManager" class="spaceManager" aria-label="四个独立空间"></section><div class="panels">')
 h=h.replace('<section class="panel decision">', (ROOT/'code/recheck_panel.html').read_text()+'<section class="panel decision">')
 h=h.replace('<script src="catalogue.js"></script>', '<script src="four-space-state.js"></script><script src="catalogue.js"></script>')
 h=h.replace('点击应用修改确认。','点击应用只保存草稿；还需单独确认。').replace('本页不会自动上传审核结果。','本页不会自动上传、改正式GT或计算新分数。仅查看、移动、应用和导出都不确认空间。')
 h=h.replace('<strong>空间范围复核</strong>','<strong>T30四空间补充与独立复核</strong>')
 h=h.replace('<div id="leadEvidence" class="leadEvidence"></div>','<details class="historicalContext"><summary>历史空间证据（与本轮补画分开）</summary><div id="leadEvidence" class="leadEvidence"></div></details>')
 h=h.replace('<section id="evidencePanel" class="panel evidencePanel">','<details class="historicalContext"><summary>原评论与同图20份作答来源（展开查证）</summary><section id="evidencePanel" class="panel evidencePanel">').replace('</section><p class="footer">','</section></details><p class="footer">')
 h=h.replace('<script src="geometry.js"></script>', '<script type="application/json" id="editor-data">'+json.dumps(json.loads((dst/'data.json').read_text()),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+'</script><script src="geometry.js"></script>')
 (dst/'index.html').write_text(h,encoding='utf-8');css=(src/'style.css').read_text()+'\n'+(ROOT/'code/four-space.css').read_text();(dst/'style.css').write_text(css,encoding='utf-8')
 print('Adapted v3.4.2 app; geometry kept unchanged; four empty-capable independent slots')
if __name__=='__main__':main()
