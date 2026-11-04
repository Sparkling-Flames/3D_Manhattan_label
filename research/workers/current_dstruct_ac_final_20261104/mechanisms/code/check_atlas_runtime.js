/* Execute every offline atlas case and interaction with a small DOM test
 * double. This validates JavaScript behavior, not browser pixel layout. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const out=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(out,'CURRENT_DSTRUCT_AC_ATLAS.html'),'utf8');
const match=html.match(/<script>([\s\S]*?)<\/script>/);assert(match);
const all=[];
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.dataset={};this.style={};this._text='';this.checked=false;all.push(this)}
 set textContent(t){this._text=String(t);this.children=[]}get textContent(){return this._text+this.children.map(c=>c.textContent??String(c)).join('')}
 append(...ns){this.children.push(...ns.map(n=>typeof n==='string'?new Text(n):n))}appendChild(n){this.append(n);return n}
 replaceChildren(...ns){this._text='';this.children=[];this.append(...ns)}
 setAttribute(k,v){this.attributes[k]=String(v)}getAttribute(k){return this.attributes[k]??null}
 click(){if(this.onclick)this.onclick()}remove(){}
}
class Text extends Element{constructor(t){super('#text');this._text=String(t)}}
const ids=new Map();for(const m of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)){const e=new Element(m[1]);e.id=m[3];e.checked=/\bchecked\b/.test(m[2]);ids.set(e.id,e)}
const document={getElementById:id=>{assert(ids.has(id),'Unknown DOM id '+id);return ids.get(id)},createElement:tag=>new Element(tag),createElementNS:(ns,tag)=>new Element(tag),createTextNode:t=>new Text(t),querySelectorAll:selector=>{assert.equal(selector,'[data-worker]');return all.filter(e=>e.dataset.worker)}};
const context=vm.createContext({document,console,Blob,URL:{createObjectURL:()=> 'blob:local-test',revokeObjectURL:()=>{}},setTimeout:fn=>{fn();return 1},fetch:()=>{throw Error('Network request is forbidden in offline atlas')},assert});
vm.runInContext(match[1],context,{timeout:30000,filename:'CURRENT_DSTRUCT_AC_ATLAS.inline.js'});
const evaluate=code=>vm.runInContext(code,context,{timeout:30000});
assert.equal(evaluate('DATA.cases.length'),12);assert.equal(ids.get('case').children.length,12);assert.equal(ids.get('abc_panels').children.length,3);
const checks=[];
for(let i=0;i<12;i++){
 evaluate(`chosen=DATA.cases[${i}];render()`);
 const caseid=evaluate('chosen.case_id');
 assert.equal(ids.get('rawdetails').children.length,evaluate("list(chosen.event.D_workers).length+list(chosen.event.X_workers).length+list(chosen.event.Z_workers).length"));
 assert(ids.get('metrics').children.length>=28);assert(ids.get('case_notes').children.length>=4);
 assert.equal(ids.get('anchor_table').children[0].children[1].children.length,evaluate('chosen.D_anchor_links.length'));
 evaluate("$('donly').onclick()");assert.equal(evaluate('visible.size'),evaluate("list(chosen.event.D_workers).length"));
 evaluate("$('blockonly').onclick()");assert.equal(evaluate('visible.size'),evaluate('2*chosen.event.m'));
 evaluate("$('allraw').onclick()");assert.equal(evaluate('visible.size'),evaluate('chosen.event.n+chosen.event.m'));
 evaluate("$('noraw').onclick()");assert.equal(evaluate('visible.size'),0);
 if(evaluate('chosen.D_anchor_links.some(r=>r.link_type===\'exact_same_nonempty_D_observations\')')){
  evaluate("setFocus('0')");assert.notEqual(ids.get('a_svg').getAttribute('viewBox'),'0 0 1024 512');evaluate("setFocus('all')");assert.equal(ids.get('a_svg').getAttribute('viewBox'),'0 0 1024 512');
 }
 evaluate("$('showgroups').checked=true;draw();$('showgroups').checked=false;draw()");
 if(evaluate("chosen.arms.C.score_status==='no_connection'")){
  assert.equal(ids.get('metrics').children[0].children[2].textContent,'不可评');assert.equal(ids.get('metrics').children[0].children[3].textContent,'不可评');
 }
 assert.equal(evaluate('chosen.approved_manual_order_match.A.exact_team_pool_reference_match'),false);
 assert.equal(evaluate('chosen.approved_manual_order_match.C.exact_team_pool_reference_match'),false);
 for(const name of ['a_svg','c_svg'])for(const el of ids.get(name).children){if(el.tagName==='path')assert(!/NaN|undefined|null/.test(el.attributes.d));}
 evaluate("$('downloads').children[0].onclick()");
 checks.push({case_id:caseid,raw_answer_controls:true,anchor_zoom:true,metrics_and_missing_Q:true,download_json:true,finite_svg_paths:true});
}
const receipt={status:'passed',runtime:'Node V8 with minimal DOM test double; no graphical browser run claimed',case_count:12,existing_ABC_panels:3,checks,external_network_calls:0,atlas_sha256:crypto.createHash('sha256').update(html).digest('hex')};
fs.writeFileSync(path.join(out,'ATLAS_JS_RUNTIME_CHECKS.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({status:receipt.status,case_count:12,existing_ABC_panels:3}));
