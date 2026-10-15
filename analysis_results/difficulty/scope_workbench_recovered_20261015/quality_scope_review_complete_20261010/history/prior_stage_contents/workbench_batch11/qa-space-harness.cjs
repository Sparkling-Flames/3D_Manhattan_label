'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert'),G=require('./dist/geometry.js'),S=require('./dist/review-state.js'),C=require('./dist/catalogue.js');
const DATA=JSON.parse(fs.readFileSync('dist/data.json')),HTML=fs.readFileSync('dist/index.html','utf8'),KEY='layout-scope-crop-v1';
let checks=0;const check=(v,m)=>{assert(v,m);checks++},eq=(a,b,m)=>{assert.deepStrictEqual(JSON.parse(JSON.stringify(a)),JSON.parse(JSON.stringify(b)),m);checks++},near=(a,b,e=1e-9)=>check(Math.abs(a-b)<=e,`${a} != ${b}`),polyNear=(a,b)=>{eq(a.length,b.length);a.forEach((p,i)=>p.forEach((v,j)=>near(v,b[i][j])))};
function orthogonal(p){for(let i=0;i<4;i++){let a=p[i],b=p[(i+1)%4],c=p[(i+2)%4];near((a[0]-b[0])*(c[0]-b[0])+(a[1]-b[1])*(c[1]-b[1]),0)}}
function coincident(poly,edge,gt,index){for(const p of [poly[edge],poly[(edge+1)%poly.length]])near(G.cross(gt[index],gt[(index+1)%gt.length],p),0)}
async function boot(stored,scale=1){
 const data=S.clone(DATA),elements={},saved=new Map(stored?[[KEY,JSON.stringify(stored)]]:[]),handlers={},downloads=[];
 const el=id=>elements[id]||(elements[id]={value:id==='yaw'?'0':'',checked:new RegExp(`<input[^>]*id="${id}"[^>]*checked`).test(HTML),disabled:false,hidden:false,textContent:'',innerHTML:'',style:{},dataset:{},tagName:'DIV',classList:{toggle(){},remove(){},contains(){return false}},querySelectorAll(){return []},click(){if(!this.disabled)this.onclick?.()},getContext(){return new Proxy({},{get:()=>()=>{}})},setPointerCapture(){},getScreenCTM(){return {a:scale,b:0,c:0,d:scale,e:0,f:0,inverse:()=>({scale})}},createSVGPoint(){return {x:0,y:0,matrixTransform(m){return {x:this.x/m.scale,y:this.y/m.scale}}}}});
 const choices=['allow','full_gt','uncertain'].map(x=>({dataset:{decision:x},classList:{toggle(){}},disabled:false})),modes=['cut','rectangle','edge'].map(x=>({dataset:{mode:x},classList:{toggle(){}},disabled:false}));
 const ctx={console,Geo:G,ReviewState:S,Catalogue:C,document:{querySelector:s=>el(s.slice(1)),querySelectorAll:s=>s==='[data-decision]'?choices:s==='[data-mode]'?modes:s==='[data-mode],[data-decision]'?[...choices,...modes]:[],addEventListener:(k,f)=>handlers[k]=f,activeElement:{tagName:'BODY'},createElement:()=>({click(){downloads.push(this.download)}})},localStorage:{setItem:(k,v)=>saved.set(k,v),getItem:k=>saved.get(k)},Image:class{constructor(){this.complete=false;this.naturalWidth=0}},fetch:async path=>({ok:true,json:async()=>path==='data.json'?data:JSON.parse(fs.readFileSync('dist/'+path))}),setTimeout:()=>1,clearTimeout(){},Date,Blob,URL:{createObjectURL:()=>'',revokeObjectURL(){}},window:null};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/app.js','utf8'),ctx);await new Promise(r=>setImmediate(r));
 const get=s=>vm.runInContext(s,ctx),event=(p,dataset={})=>{const pos=get('screen('+JSON.stringify(p)+')');return {button:0,pointerId:1,preventDefault(){},target:{dataset},clientX:pos[0]*scale,clientY:pos[1]*scale}};
 return {w:ctx.workbench,el,saved,get,event,handlers,downloads,ctx,choices};
}

module.exports={boot,DATA,KEY,G,S,HTML};
