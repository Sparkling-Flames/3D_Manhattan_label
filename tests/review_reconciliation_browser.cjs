const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {sceneRuleAdvice}=require('../tools/thesis_main/analysis/review_reconciliation_panel_20260925.js');
const paired={status:'existing_accepted_pairing'};
assert.equal(sceneRuleAdvice({status:'pending',category:'oos'},6,6,paired).action,'confirm_scene');
assert.equal(sceneRuleAdvice({status:'resolved',category:'oos'},6,6,paired).action,'default_exclude');
assert.equal(sceneRuleAdvice({status:'resolved',category:'doorway_difficult'},6,6,paired).action,'no_scene_exclusion');
assert.equal(sceneRuleAdvice({status:'resolved',category:'oos'},7,8,paired).action,'check_repair');
assert.equal(sceneRuleAdvice({status:'resolved',category:'oos'},7,8,paired,true).action,'no_scene_exclusion');
assert.match(sceneRuleAdvice({status:'resolved',category:'oos'},8,8,{status:'unavailable',reason:'ambiguous_horizontal_assignment'}).text,/不等于完全无法配对/);

(async()=>{
  const root=path.resolve(process.argv[2]),browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try{
    const context=await browser.newContext({offline:true,viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
    const inventory=await page.evaluate(()=>dataset.cases.map(c=>({id:c.image_id,code:c.code,script:c.history_script,flags:c.review.flags,ids:c.review.annotation_ids})));
    assert.equal(new Set(inventory.map(c=>c.id)).size,inventory.length,'每张图片只出现一次');
    assert.equal(await page.locator('#recon-filter').inputValue(),'followup');
    assert.equal(await page.locator('#recon-image option').count(),inventory.filter(c=>c.flags.includes('followup')).length);
    assert.ok(await page.locator('#recon-image option').count()<inventory.length,'不能要求所有图片重新审核');
    await page.locator('#recon-filter').selectOption('all');
    assert.equal(await page.locator('#recon-image option').count(),inventory.length);
    assert.ok(await page.locator('.recon-cluster-canvas').count()>0,'簇必须直接显示图像叠加');
    const firstCard=page.locator('.recon-cluster').first();
    await firstCard.locator('details summary').click();
    await firstCard.locator('.recon-individuals canvas').first().waitFor();
    assert.ok(await firstCard.locator('.recon-individuals canvas').count()>0);
    await firstCard.locator('.recon-cluster-canvas').first().click();
    const members=JSON.parse(await firstCard.locator('.recon-cluster-canvas').first().getAttribute('data-members'));
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).focusId,members[0]);
    await page.locator('.recon-final > summary').click();
    assert.equal(await page.locator('.order-editor').isVisible(),false);
    assert.equal(await page.locator('#order-apply').isDisabled(),true);
    const initial=await page.evaluate(()=>RECONCILIATION_APP.snapshot());
    assert.equal(initial.imageDecisions,0);assert.equal(initial.annotationDecisions,0);
    for(const mode of ['raw','shared_x','effective']){
      await page.locator('#recon-points').selectOption(mode);
      assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).pointMode,mode);
    }
    await page.locator('#recon-method').selectOption('complete');
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).clusterMethod,'complete');
    await page.locator('#recon-method').selectOption('affinity');
    await page.locator('#recon-canvas').click({position:{x:100,y:90}});
    assert.equal(await page.locator('#recon-zoom').isVisible(),true);
    await page.locator('#recon-ann-verdict').selectOption('repair_needed');
    await page.locator('#recon-ann-comment').fill('自动化检查：仅保存到隔离浏览器，不是人工裁决。');
    await page.locator('#recon-ann-resolve').click();
    assert.match(await page.locator('#recon-status').textContent(),/不能|只能|待定|修复/);
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).annotationResolved,0);
    await page.locator('#recon-ann-verdict').selectOption('usable');
    await page.locator('#recon-ann-resolve').click();
    const saved=await page.evaluate(()=>RECONCILIATION_APP.snapshot());
    assert.equal(saved.annotationResolved,1);
    assert.match(await page.locator(`[data-decision-id="${saved.focusId}"]`).textContent(),/已确认/);
    await page.locator('#recon-image-category').selectOption('ordinary');
    await page.locator('#recon-image-resolve').click();
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).imageProblemReviewed,true,'图级问题可以一次确认，不要求重填每个对照成员');
    const downloadEvent=page.waitForEvent('download');await page.locator('#recon-export').click();
    const download=await downloadEvent,data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
    assert.equal(data.schema,'review_reconciliation_decisions_v1');
    assert.equal(Object.keys(data.annotation_decisions).length,1);
    await page.reload();await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).annotationResolved,1);
    await page.evaluate(()=>localStorage.clear());await page.reload();
    await page.waitForFunction(()=>window.RECONCILIATION_APP?.snapshot().imageReady);
    assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).annotationDecisions,0);
    const upload=async value=>page.locator('#recon-import').setInputFiles({name:'review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
    await upload(data);await page.waitForFunction(()=>document.getElementById('recon-status').textContent.includes('导入成功'));
    const before=await page.evaluate(()=>RECONCILIATION_APP.exportData());
    for(const bad of [{...data,schema:'consensus_visual_review_decisions_v1'},{...data,binding:{id:'wrong'}},{...data,annotation_decisions:{unknown:Object.values(data.annotation_decisions)[0]}}]){
      await upload(bad);assert.match(await page.locator('#recon-status').textContent(),/导入失败/);
      assert.deepEqual(await page.evaluate(()=>RECONCILIATION_APP.exportData()),before,'错误导入不能覆盖当前答案');
    }
    for(const flag of ['repair','oos','doorway','recheck_yizheng','excluded']){
      const c=inventory.find(c=>c.flags.includes(flag));if(!c)continue;
      await page.locator('#recon-filter').selectOption(['oos','doorway'].includes(flag)?'all':flag);
      await page.locator('#recon-scene-filter').selectOption(['oos','doorway'].includes(flag)?flag:'all');
      await page.waitForFunction(()=>RECONCILIATION_APP.snapshot().imageReady);
      assert.ok(await page.locator('#recon-image option').count()>0);
      await page.locator('#recon-image').selectOption(c.id);
      await page.waitForFunction(id=>RECONCILIATION_APP.snapshot().imageId===id&&RECONCILIATION_APP.snapshot().imageReady,c.id);
      assert.equal(await page.locator('#recon-canvas').isVisible(),true);
      if(['oos','doorway'].includes(flag))assert.equal((await page.evaluate(()=>RECONCILIATION_APP.snapshot())).focusedHasGeometry,false);
    }
    await page.locator('#recon-filter').selectOption('all');
    await page.locator('#recon-scene-filter').selectOption('all');
    await page.locator('#recon-unresolved').check();
    assert.ok(await page.locator('#recon-image option').count()>0,'待定记录仍在未解决队列');
    const outside=inventory.find(c=>c.code==='rPc6DW4iMge-22');
    if(outside){
      await page.locator('#recon-image').selectOption(outside.id);
      await page.waitForFunction(id=>RECONCILIATION_APP.snapshot().imageId===id&&RECONCILIATION_APP.snapshot().imageReady,outside.id);
      const id=await page.evaluate(()=>dataset.cases[currentCase].variants.find(v=>v.source.worker_id==='W002').source.canonical_annotation_id);
      await page.locator('#recon-focus').selectOption(id);await page.locator('#recon-points').selectOption('raw');
      assert.match(await page.locator('#recon-point-warning').textContent(),/p8.*3897\.282/);
      assert.match(await page.locator('#recon-point-changes').textContent(),/389\.728/);
      assert.equal(await page.locator('#recon-point-warning').isVisible(),true,'原图之外的点必须显式列出');
    }
    let geometryCase,geometryId;
    await page.locator('#recon-unresolved').uncheck();
    for(const c of inventory){
      const text=fs.readFileSync(path.join(root,c.script),'utf8'),start=text.indexOf('Object.assign('),json=text.slice(text.indexOf(',',start)+1,text.lastIndexOf(');'));
      const data=JSON.parse(json),v=data.variants.find(v=>v.source.role==='annotation'&&v.geometry?.raw?.surface_valid);
      if(v){geometryCase=c;geometryId=v.source.canonical_annotation_id;break;}
    }
    assert.ok(geometryCase,'至少一份正常作答应能展示实际3D');
    await page.locator('#recon-image').selectOption(geometryCase.id);
    await page.waitForFunction(id=>RECONCILIATION_APP.snapshot().imageId===id&&RECONCILIATION_APP.snapshot().imageReady,geometryCase.id);
    await page.locator('#recon-focus').selectOption(geometryId);
    await page.waitForFunction(()=>STUDIO.snapshot().textureReady&&STUDIO.snapshot().imageReady);
    await page.locator('#recon-3d').click();await page.locator('[data-material="texture"]').click();
    const geometry=await page.evaluate(()=>STUDIO.snapshot());
    assert.ok(geometry.wallVisibility[0].length>=3);assert.equal(geometry.materialMode,'texture');
    assert.equal(geometry.fitStatus,'not_requested','本轮不执行曼哈顿拟合');
    assert.match(await page.locator('#metrics').textContent(),/本轮未运行/);
    assert.equal(await page.locator('#raw-title').textContent(),'既有点对条件重建');
    assert.equal(await page.locator('#order-apply').isDisabled(),true);
    if(process.argv.includes('--screenshot')){
      await page.locator('#recon-status').evaluate(e=>e.textContent='隔离浏览器验证完成；截图中的填写不是真人裁决。');
      await page.locator('#recon-gallery').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      await page.screenshot({path:path.join(root,'qa-temporary.png')});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: 单图去重、离线点图/局部放大、点模式/分簇、门洞OOS无3D仍可审、图外点与修复对照、正常纹理3D、成员审核状态、独立空白裁决、待定与已解决、保存重载、导出导入和错误导入保全');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
