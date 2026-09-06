/* End-to-end checks against real WebGL, image loading, and user controls. */
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
const runtime=process.env.PLAYWRIGHT_MODULE||'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
const {chromium}=require(runtime);
const out=path.resolve(process.argv[2]||'analysis_results/panorama_studio_20260906_v2');
const qa=path.join(out,'browser_qa');fs.mkdirSync(qa,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1512,height:1100},deviceScaleFactor:1});
  const errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  try{
    await page.goto(pathToFileURL(path.join(out,'index.html')).href);
    await page.waitForFunction(()=>window.STUDIO?.snapshot().textureReady,{timeout:30000});
    await page.screenshot({path:path.join(qa,'01_clay.png'),fullPage:true});
    assert.deepEqual(errors,[]);checks.push('actual WebGL and local images loaded');
    const initial=await page.evaluate(()=>STUDIO.snapshot());
    assert.equal(initial.fitStatus,'ok');
    assert.deepEqual(initial.cameras[0],initial.cameras[1]);
    assert.equal(initial.cameras[0].type,'OrthographicCamera');
    assert.ok((await page.locator('#viewport-raw').boundingBox()).y<350);
    assert.equal(initial.clipping.enabled,false);
    const visibility=await page.evaluate(()=>{
      const v=views[0],hidden=v.markers.filter(m=>!pointVisible(v,m.position));
      const results=hidden.map(m=>{const p=m.position.clone().project(v.camera),r=v.renderer.domElement.getBoundingClientRect();
        return {expected:m.userData,hit:hitTest(v,{clientX:r.left+(p.x+1)*r.width/2,clientY:r.top+(1-p.y)*r.height/2})?.object.userData};});
      return {hiddenCount:hidden.length,results};
    });
    assert.ok(visibility.hiddenCount>0);
    assert.ok(visibility.results.every(r=>r.hit?.kind!=='point'||r.hit.index!==r.expected.index||r.hit.endpoint!==r.expected.endpoint));
    await page.locator('#xray').check();
    assert.ok(await page.evaluate(()=>views[0].markers.every(m=>!m.material.depthTest)));
    await page.locator('#xray').uncheck();
    checks.push('occluded endpoints are not picked unless x-ray is explicitly enabled');
    await page.locator('#pair-buttons button').nth(0).click();
    assert.equal((await page.evaluate(()=>STUDIO.snapshot())).selected.index,0);
    await page.locator('[data-endpoint="bottom"]').click();
    assert.equal((await page.evaluate(()=>STUDIO.snapshot())).endpoint,'bottom');
    checks.push('point identity and endpoint selection linked');
    await page.locator('[data-material="texture"]').click();
    await page.screenshot({path:path.join(qa,'02_texture.png'),fullPage:true});
    const textured=await page.evaluate(()=>STUDIO.snapshot());assert.equal(textured.materialMode,'texture');
    await page.locator('#decor').uncheck();
    assert.equal((await page.evaluate(()=>STUDIO.snapshot())).geometry,initial.geometry);
    await page.locator('#decor').check();checks.push('display changes preserve geometry exactly');
    await page.locator('#cutaway').check();
    await page.locator('#cut-height').fill('55');
    const cut=await page.evaluate(()=>STUDIO.snapshot());
    assert.equal(cut.clipping.enabled,true);
    assert.equal(cut.clipping.fraction,.55);
    assert.equal(cut.geometry,initial.geometry);
    assert.ok(cut.sectionSegments.every(n=>n>0));
    assert.deepEqual(cut.clipPlanes[0],cut.clipPlanes[1]);
    await page.screenshot({path:path.join(qa,'02b_section.png'),fullPage:true});
    await page.locator('#cutaway').uncheck();
    await page.locator('#ceiling').check();await page.locator('#ceiling').uncheck();
    checks.push('shared clipping plane and real section contours preserve geometry');
    await page.locator('[data-view="top"]').click();
    await page.screenshot({path:path.join(qa,'03_top_texture.png'),fullPage:true});
    assert.deepEqual(...(await page.evaluate(()=>STUDIO.snapshot())).cameras);
    await page.locator('[data-view="inside"]').click();
    await page.screenshot({path:path.join(qa,'04_inside_texture.png'),fullPage:true});
    assert.deepEqual((await page.evaluate(()=>STUDIO.snapshot())).cameras[0].position,[0,0,0]);
    assert.equal((await page.evaluate(()=>STUDIO.snapshot())).cameras[0].type,'PerspectiveCamera');
    await page.locator('[data-view="iso"]').click();
    const viewport=await page.locator('#viewport-raw canvas').boundingBox();
    await page.mouse.move(viewport.x+viewport.width*.5,viewport.y+viewport.height*.5);
    await page.mouse.down();await page.mouse.move(viewport.x+viewport.width*.65,viewport.y+viewport.height*.55,{steps:8});await page.mouse.up();
    assert.deepEqual(...(await page.evaluate(()=>STUDIO.snapshot())).cameras);
    checks.push('orbit, top, interior and synchronized cameras');
    const preserved=(await page.evaluate(()=>STUDIO.snapshot())).cameras;
    await page.selectOption('#variant-select','1');
    assert.deepEqual((await page.evaluate(()=>STUDIO.snapshot())).cameras,preserved);
    checks.push('source switch preserves inspection camera');
    await page.locator('[data-expand="raw"]').click();
    assert.equal(await page.locator('#card-fit').isVisible(),false);
    await page.locator('[data-expand="raw"]').click();
    await page.locator('#panorama-panel summary').click();
    assert.equal(await page.locator('#panorama').isVisible(),true);
    await page.locator('#panorama-panel summary').click();
    assert.equal(await page.locator('#panorama').isVisible(),false);
    checks.push('single viewport and panorama folding');
    const textureCalibration=await page.evaluate(()=>{
      const colors=['#bb3333','#338844','#3344bb','#bbaa33','#33aaaa','#aa33aa','#886644','#667788'];
      const c=document.createElement('canvas');c.width=400;c.height=200;const ctx=c.getContext('2d');
      colors.forEach((color,i)=>{ctx.fillStyle=color;ctx.fillRect(i%4*100,Math.floor(i/4)*100,100,100);});
      const saved=texture;texture=new THREE.CanvasTexture(c);texture.minFilter=THREE.NearestFilter;texture.magFilter=THREE.NearestFilter;
      materialMode='texture';selected=null;$('ceiling').checked=true;rebuild(false);preset('inside');
      const samples=[];
      for(let i=0;i<8;i++){
        const u=(i%4+.5)/4,v=(Math.floor(i/4)+.5)/2,longitude=(u-.5)*2*Math.PI,latitude=(.5-v)*Math.PI;
        const direction=new THREE.Vector3(Math.cos(latitude)*Math.sin(longitude),Math.sin(latitude),-Math.cos(latitude)*Math.cos(longitude));
        views.forEach(x=>x.camera.lookAt(direction));renderAll();
        const canvas=views[0].renderer.domElement,probe=document.createElement('canvas');probe.width=canvas.width;probe.height=canvas.height;
        const pc=probe.getContext('2d');pc.drawImage(canvas,0,0);
        samples.push({expected:Array.from(ctx.getImageData(u*400,v*200,1,1).data).slice(0,3),actual:Array.from(pc.getImageData(canvas.width/2,canvas.height/2,1,1).data).slice(0,3)});
      }
      texture.dispose();texture=saved;$('ceiling').checked=false;materialMode='clay';rebuild(false);preset('iso');
      return samples;
    });
    assert.ok(textureCalibration.every(s=>s.actual.every((v,i)=>Math.abs(v-s.expected[i])<=2)),JSON.stringify(textureCalibration));
    checks.push('eight directional texture color probes verify panorama longitude/latitude orientation');
    // Load every source version: catches stale scenes and blocked-state failures.
    const cases=await page.evaluate(()=>STUDIO_DATA.cases.map(c=>c.variants.length));
    let loaded=0;
    for(let c=0;c<cases.length;c++){
      await page.selectOption('#case-select',String(c));
      await page.waitForFunction(i=>STUDIO.snapshot().caseIndex===i&&STUDIO.snapshot().textureReady,c);
      for(let v=0;v<cases[c];v++){
        await page.selectOption('#variant-select',String(v));
        const snap=await page.evaluate(()=>STUDIO.snapshot());assert.equal(snap.variantIndex,v);loaded++;
      }
    }
    checks.push(`all ${loaded} source versions rendered`);
    await page.selectOption('#case-select','9');
    await page.waitForFunction(()=>STUDIO.snapshot().textureReady);
    await page.selectOption('#variant-select','0');
    await page.locator('[data-material="clay"]').click();
    await page.screenshot({path:path.join(qa,'05_invalid_order.png'),fullPage:true});
    await page.selectOption('#case-select','0');await page.waitForFunction(()=>STUDIO.snapshot().textureReady);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(qa,'06_mobile.png'),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    checks.push('390px layout has no horizontal overflow');
    // Inject one decode failure, then prove selecting another case recovers without stale texture.
    await page.evaluate(()=>{const decode=Image.prototype.decode;let once=true;Image.prototype.decode=function(){
      if(once){once=false;return Promise.reject(new Error('QA simulated image decode failure'));}return decode.call(this);};});
    await page.selectOption('#case-select','1');
    await page.waitForFunction(()=>!document.getElementById('fatal').hidden);
    assert.equal((await page.evaluate(()=>STUDIO.snapshot())).textureReady,false);
    await page.selectOption('#case-select','0');await page.waitForFunction(()=>STUDIO.snapshot().textureReady);
    assert.equal(await page.locator('#fatal').isVisible(),false);
    checks.push('image failure shown explicitly; next case recovers without stale imagery');
    const prior=JSON.parse(fs.readFileSync(path.resolve('analysis_results/panorama_studio_20260906_v1/geometry_audit.json')));
    const current=JSON.parse(fs.readFileSync(path.join(out,'geometry_audit.json')));
    assert.deepEqual(current.cases.map(c=>c.variants.map(v=>v.geometry)),prior.cases.map(c=>c.variants.map(v=>v.geometry)));
    checks.push('all 75 geometry results exactly match v1');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(qa,'QA.json'),JSON.stringify({passed:true,checks,errors},null,2));
    console.log(JSON.stringify({passed:true,checks,errors}));
  }catch(error){
    await page.screenshot({path:path.join(qa,'failure.png'),fullPage:true});
    fs.writeFileSync(path.join(qa,'QA.json'),JSON.stringify({passed:false,checks,errors,failure:String(error)},null,2));
    throw error;
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
