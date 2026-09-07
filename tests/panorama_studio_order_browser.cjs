/* Focused real-WebGL regression for manual paired-corner ordering. */
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
const runtime=process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
const {chromium}=require(runtime);
const studio=path.resolve(process.argv[2]);
(async()=>{
  // Test current source against the real case without deploying over review artifacts.
  let server=null,url=pathToFileURL(path.join(studio,'index.html')).href;
  if(process.argv.includes('--source')){
    const fs=require('node:fs'),http=require('node:http');
    const source=path.resolve(__dirname,'../tools/label_studio/panorama_studio');
    server=http.createServer((req,res)=>{
      const name=new URL(req.url,'http://localhost').pathname.slice(1)||'index.html';
      if(name!==path.basename(name)){res.writeHead(404).end();return;}
      const file=path.join(['studio.js','studio.css','index.html'].includes(name)?source:studio,name);
      if(!fs.existsSync(file)){res.writeHead(404).end();return;}
      res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');
      fs.createReadStream(file).pipe(res);
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    url=`http://127.0.0.1:${server.address().port}/`;
  }
  const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  try{
    await page.goto(url);
    await page.waitForFunction(()=>window.STUDIO?.snapshot().textureReady,{timeout:30000});
    const topology=await page.evaluate(()=>{
      const floor=p=>p.map(([x,z])=>[x,-1,z]);
      const cases={rectangle:[[-2,-2],[2,-2],[2,2],[-2,2]],
        concave:[[-3,-3],[1,-3],[1,-1],[3,-1],[3,3],[-3,3]],
        collinear:[[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]],
        crossing:[[-2,-2],[2,2],[2,-2],[-2,2]],
        duplicate:[[-2,-2],[2,-2],[2,-2],[-2,2]],
        touching:[[-2,-2],[2,-2],[0,0],[2,2],[-2,2],[0,0]],
        degenerate:[[0,0],[1,0],[2,0]],
        backtrack:[[-2,-2],[2,-2],[0,-2],[2,2],[-2,2]]};
      const results=Object.fromEntries(Object.entries(cases).map(([name,p])=>[name,previewPolygon(floor(p))]));
      results.missing=previewPolygon([null,[0,-1,1],[1,-1,0]]);
      results.nonfinite=previewPolygon([[Infinity,-1,0],[0,-1,1],[1,-1,0]]);
      const base=clone(sourceGeometry),order=base.pairs.map((_,i)=>i).reverse();
      base.raw.ceiling[0]=null;
      results.badCeiling=orderedPreview(base,order).raw;
      return results;
    });
    for(const key of ['rectangle','concave','collinear'])assert.equal(topology[key].valid,true,key);
    assert.equal(topology.rectangle.area,16);assert.equal(topology.concave.area,32);
    for(const key of ['crossing','duplicate','touching','degenerate','backtrack','missing','nonfinite'])assert.equal(topology[key].valid,false,key);
    assert.equal(topology.badCeiling.surface_valid,false);assert.deepEqual(topology.badCeiling.ceiling_triangles,[]);
    const variants=await page.locator('#variant-select option').allTextContents();
    const worker31=variants.findIndex(name=>/W31|worker.?31|人工.*31/i.test(name));
    assert.ok(worker31>=0,`W31 variant missing: ${variants}`);
    await page.selectOption('#variant-select',String(worker31));
    const original=await page.evaluate(()=>STUDIO.snapshot());
    const originalGeometry=JSON.parse(original.sourceGeometry);
    assert.equal(originalGeometry.pairs.length,4);
    assert.equal(originalGeometry.raw.surface_valid,false);
    assert.ok(originalGeometry.raw.issues.includes('invalid_footprint'));
    assert.deepEqual(original.previewOrder,[0,1,2,3]);
    await page.locator('#order-permutation').fill('4,3,1,2');
    await page.locator('#order-apply').click();
    const preview=await page.evaluate(()=>STUDIO.snapshot());
    assert.deepEqual(preview.previewOrder,[3,2,0,1]);
    assert.equal(preview.fitStatus,'blocked');
    assert.equal(await page.locator('#raw-title').textContent(),'顺序预览副本');
    assert.equal(preview.orderRecord.preview_surface_valid,true);
    assert.equal(preview.orderRecord.preview_validation.annotation_correctness_confirmed,false);
    assert.match(await page.locator('#provenance').textContent(),/原始顺序诊断/);
    assert.equal(JSON.parse(preview.geometry).raw.surface_valid,true);
    assert.ok(!JSON.parse(preview.geometry).raw.issues.includes('invalid_footprint'));
    assert.ok(JSON.parse(preview.geometry).raw.source_issues.includes('invalid_footprint'));
    const surfaces=await page.evaluate(()=>({visibleWalls:views[0].walls.filter(w=>w.mesh.visible).length,
      triangles:geometry.raw.floor_triangles,clay:views[0].walls.every(w=>w.mesh.material.isMeshStandardMaterial)}));
    assert.equal(surfaces.visibleWalls,4);assert.equal(surfaces.triangles.length,2);assert.equal(surfaces.clay,true);
    const clay=await page.locator('#viewport-raw canvas').evaluate(c=>c.toDataURL());
    await page.locator('[data-material="texture"]').click();
    assert.ok(await page.evaluate(()=>views[0].walls.every(w=>w.mesh.visible&&w.mesh.material.isShaderMaterial&&w.mesh.material.uniforms.pano.value)));
    assert.notEqual(await page.locator('#viewport-raw canvas').evaluate(c=>c.toDataURL()),clay);
    assert.equal(preview.sourceGeometry,original.sourceGeometry);
    assert.deepEqual(preview.orderRecord.preview_source_pair_ids,
      [3,2,0,1].map(index=>originalGeometry.pairs[index].source_pair_id));
    assert.deepEqual(preview.orderRecord.preview_endpoint_payload_slot_to_original_zero_based,[6,7,4,5,0,1,2,3]);
    assert.deepEqual(preview.orderRecord.preview_endpoint_payload_slot_to_original_one_based,[7,8,5,6,1,2,3,4]);
    assert.equal(preview.orderRecord.top_bottom_roles_preserved,true);
    assert.ok(await page.locator('#viewport-raw canvas').evaluate(canvas=>canvas.width>0&&canvas.height>0));
    const pendingDownload=page.waitForEvent('download');
    await page.locator('#order-export').click();
    const exported=JSON.parse(require('node:fs').readFileSync(await (await pendingDownload).path(),'utf8'));
    assert.deepEqual(exported.preview_position_to_original_one_based,[4,3,1,2]);
    assert.deepEqual(exported.preview_endpoint_original_point_ids,[6,7,4,5,0,1,2,3]);
    if(process.argv[3]&&!process.argv[3].startsWith('--')) await page.screenshot({path:path.resolve(process.argv[3]),fullPage:true});
    await page.locator('#order-restore').click();
    const restored=await page.evaluate(()=>STUDIO.snapshot());
    assert.deepEqual(restored.previewOrder,[0,1,2,3]);
    assert.equal(restored.geometry,restored.sourceGeometry);
    assert.equal(await page.locator('#raw-title').textContent(),'原始重建');
    assert.equal(restored.orderRecord.preview_validation,null);
    assert.equal(JSON.parse(restored.geometry).raw.surface_valid,false);
    assert.ok(await page.evaluate(()=>views[0].walls.every(w=>!w.mesh.visible)));
    await page.locator('#pair-buttons button').first().click();
    await page.locator('#order-later').click();
    assert.deepEqual(await page.evaluate(()=>STUDIO.snapshot().previewOrder),[1,0,2,3]);
    await page.locator('#order-earlier').click();
    assert.deepEqual(await page.evaluate(()=>STUDIO.snapshot().previewOrder),[0,1,2,3]);
    await page.locator('#order-permutation').fill('1,1,2,3');
    await page.locator('#order-apply').click();
    assert.deepEqual(await page.evaluate(()=>STUDIO.snapshot().previewOrder),[0,1,2,3]);
    assert.ok(await page.locator('#fatal').isVisible());
    const inverted=await page.evaluate(index=>{
      const pairs=STUDIO_DATA.cases[0].variants[index].geometry.pairs,prior=pairs.map(pair=>pair.source_pair_id);
      pairs[0].source_pair_id='raw:3/2';pairs[1].source_pair_id='ann:top/bottom';chooseVariant(index);
      const snapshot=STUDIO.snapshot(),map=document.getElementById('order-map').textContent;
      pairs.forEach((pair,i)=>pair.source_pair_id=prior[i]);
      return {record:snapshot.orderRecord,map};
    },worker31);
    assert.deepEqual(inverted.record.preview_endpoint_payload_slot_to_original_zero_based.slice(0,4),[0,1,2,3]);
    assert.deepEqual(inverted.record.preview_endpoint_original_point_ids.slice(0,4),[3,2,null,null]);
    assert.match(inverted.map,/top=3, bottom=2/);
    assert.match(inverted.map,/不可解析 \(null\)/);
    console.log(JSON.stringify({passed:true,variant:variants[worker31],checks:['simple/concave/collinear accepted; crossing/touching/degenerate/missing rejected',
      'W31 4,3,1,2 has 4 visible walls, 2 new floor triangles and actual texture',
      'source geometry and point IDs preserved; old issues retained separately','fit disabled; original invalid state restored',
      'actual JSON download, previous/next moves, duplicate permutation rejected']}));
  }finally{await browser.close();if(server)await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exit(1)});
