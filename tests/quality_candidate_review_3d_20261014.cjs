// Exercise the actual viewer with a canvas mock; no browser access.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const base='research/quality_candidate_review_20261014/',elements={},strokes=[];
const ctx=new Proxy({},{get:(_,k)=>k==='stroke'?()=>strokes.push(1):()=>{},set:()=>true});
class Element{
 constructor(){this.children=[];this.handlers={};}
 append(...v){this.children.push(...v)} replaceChildren(...v){this.children=v}
 setAttribute(){} setPointerCapture(){} getBoundingClientRect(){return {width:600}}
 getContext(){return ctx} addEventListener(k,fn){this.handlers[k]=fn}
}
const sandbox={console,window:{devicePixelRatio:1,addEventListener(){}},document:{getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element()}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(base+'geometry-core.js','utf8')+'\nconst GeometryCore=window.GeometryCore;\n'+fs.readFileSync(base+'data.js','utf8')+fs.readFileSync(base+'viewer3d.js','utf8')+'\nglobalThis.api={Review3D,CARDS,GEOMETRIES,GeometryCore};',sandbox);
const {Review3D,CARDS,GEOMETRIES,GeometryCore}=sandbox.api,before=JSON.stringify(GEOMETRIES);
for(const card of CARDS){Review3D.open(card);assert.equal(elements.geometry.children.length,card.bindings.length);}
Review3D.open(CARDS[0]);const canvas=elements.geometry.children[0].children[1];
const n=strokes.length;canvas.onpointerdown({clientX:0,clientY:0,pointerId:1});canvas.onpointermove({clientX:30,clientY:20});canvas.onpointerup();assert(strokes.length>n);
canvas.handlers.wheel({deltaY:-100,preventDefault(){}});canvas.onkeydown({key:'ArrowLeft',preventDefault(){}});
elements.viewTop.onclick();elements.viewFront.onclick();elements.viewReset.onclick();assert.equal(JSON.stringify(GEOMETRIES),before);
const bounds={center:[0,0,0],radius:2},a=GeometryCore.project([1,0,0],bounds,{yaw:0,pitch:0,zoom:1},600,420),b=GeometryCore.project([1,0,0],bounds,{yaw:90,pitch:0,zoom:1},600,420);
assert(a.x>300);assert(Math.abs(b.x-300)<1e-8);
console.log('8 cards, interactive redraw, presets, projection and unchanged geometry passed');
