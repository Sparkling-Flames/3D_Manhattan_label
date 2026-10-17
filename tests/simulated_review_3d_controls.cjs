// Unit-test the renderer scripts with a minimal DOM and canvas; no browser or file-page access.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const elements={},events={},strokes=[],alphas=[];
const ctx=new Proxy({},{get:(_,k)=>k==='stroke'?()=>strokes.push(1):()=>{},set:(_,k,v)=>{if(k==='globalAlpha')alphas.push(v);return true;}});
let document;
class Element{
 constructor(){this.children=[];this.dataset={};this.style={};this.hidden=false;this.value='';this.checked=false;this.handlers={};this.ownerDocument=document;}
 append(...children){this.children.push(...children);children.forEach(c=>{if(c&&typeof c==='object')c.parentElement=this;});}
 replaceChildren(...children){this.children=[];this.append(...children);}
 setAttribute(){} setPointerCapture(){} focus(){} getBoundingClientRect(){return {width:640};}
 getContext(){return ctx;} addEventListener(k,fn){this.handlers[k]=fn;}
}
document={getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element(),createTextNode:text=>({textContent:text})};
const sandbox={console,document,window:{devicePixelRatio:1,addEventListener(k,fn){events[k]=fn;}},Image:class{constructor(){this.complete=true;this.naturalWidth=1024;}set src(v){this.value=v;}},};
elements['review-data']=new Element();elements['review-data'].textContent=JSON.stringify(fixture.cases);
document.getElementById('opacity').value='.9';document.getElementById('viewMode').value='split';
document.getElementById('threePane').append(document.getElementById('canvas3d'));
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('tools/thesis_main/analysis/simulated_annotators_review_3d.js','utf8')+'\nconst SimulatedReview3D=window.SimulatedReview3D;\n'+fixture.mainScript+`\nglobalThis.testAPI={switchCase,setViewMode,draw,viewer3d,cases,state:()=>({current,visible,chosen})};`,sandbox);
const api=sandbox.testAPI,view=api.viewer3d,canvas=elements.canvas3d,before=JSON.stringify(api.cases);
assert.equal(canvas.dataset.selectedCount,'2');assert.equal(canvas.dataset.drawnCount,'2');
// Exercise actual event handlers wired by the page, including shared selections.
const humanToggle=elements.panel.children[1].children[0].children[0];humanToggle.checked=true;humanToggle.onchange();
assert.equal(canvas.dataset.selectedCount,'3');assert.equal(canvas.dataset.drawnCount,'3');
const syntheticSection=elements.panel.children[2];
const valid=syntheticSection.children[1].children[0];valid.checked=false;valid.onchange();
const invalid=syntheticSection.children[2].children[0];invalid.checked=true;invalid.onchange();
assert.equal(canvas.dataset.selectedCount,'3');assert.equal(canvas.dataset.drawnCount,'2');
assert(elements.geometryStatus.children.some(c=>c.textContent.includes('地平线')));
elements.viewMode.value='panorama';elements.viewMode.onchange();assert(elements.threePane.hidden);assert(!elements.panoramaPane.hidden);
elements.viewMode.value='3d';elements.viewMode.onchange();assert(!elements.threePane.hidden);assert(elements.panoramaPane.hidden);
elements.viewMode.value='split';elements.viewMode.onchange();assert(!elements.threePane.hidden&&!elements.panoramaPane.hidden);
const start=view.snapshot(),n=strokes.length;
canvas.onpointerdown({clientX:0,clientY:0,pointerId:1});canvas.onpointermove({clientX:40,clientY:20});canvas.onpointerup();
assert.notEqual(view.snapshot().camera.yaw,start.camera.yaw);assert(strokes.length>n);
const zoom=view.snapshot().camera.zoom;canvas.handlers.wheel({deltaY:-100,preventDefault(){}});assert(view.snapshot().camera.zoom>zoom);
canvas.onkeydown({key:'ArrowLeft',preventDefault(){}});
elements.viewTop.onclick();assert.equal(view.snapshot().camera.pitch,90);
elements.viewFront.onclick();assert.equal(view.snapshot().camera.pitch,0);
elements.viewReset.onclick();assert.equal(JSON.stringify(view.snapshot().camera),JSON.stringify(start.camera));
elements.opacity.value='.4';elements.opacity.oninput();assert(alphas.includes(.4));
elements.caseSelect.value='1';elements.caseSelect.onchange();assert.equal(api.state().current,1);assert.equal(view.snapshot().camera.pitch,25);
assert.equal(canvas.dataset.selectedCount,'2');
elements.methodSelect.value='uniform';elements.methodSelect.onchange();
assert.equal(api.state().chosen.synthetic.size,1);assert(api.state().chosen.synthetic.has(2));
assert.equal(JSON.stringify(api.cases),before,'viewer mutated annotation data');
events.resize();
const core=sandbox.window.SimulatedReview3D;
assert.equal(core.describe(undefined),'未提供 3D 数据');
const a=core.project([1,0,0],{center:[0,0,0],radius:2},{yaw:0,pitch:0,zoom:1},640,420);
const b=core.project([1,0,0],{center:[0,0,0],radius:2},{yaw:90,pitch:0,zoom:1},640,420);
assert(a.x>320);assert(Math.abs(b.x-320)<1e-8);
console.log('3D controls: selection, invalid rows, modes, rotation, zoom, presets, opacity, image/method switching, projection and immutable sources passed');
