const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.resolve(__dirname,'../research/statistics/research_explorer_v1_r2_20261017');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.textContent='';this.value='';}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;this.value='';}
 get options(){return this.children;}
 addEventListener(type,fn){this.listeners[type]=fn;}
}
function load(){const elements={},document={getElementById:id=>elements[id]??=(new Element(id)),createElement:tag=>new Element(tag)};const context={window:{},document};vm.createContext(context);for(const file of ['v21-results-data.js','v21-current.js'])vm.runInContext(fs.readFileSync(path.join(page,file),'utf8'),context);const change=(id,value)=>{elements[id].value=value;elements[id].listeners.change();};return {elements,change,data:context.window.V21_RESULTS.current_research};}
const text=el=>el.textContent+el.children.map(text).join(' ');
const rows=el=>el.children[0].children[1].children;

test('current half support and frozen support remain distinct; same-room is six-endpoint support',()=>{
 const {elements:e,change}=load();assert.equal(e.currentModuleRows.children.length,21);
 assert.equal(rows(e.currentHalfSummary)[0].children[0].textContent,'147');assert.equal(rows(e.currentHalfSummary)[0].children[2].textContent,'67');
 change('currentHalfScope','frozen_design');assert.equal(rows(e.currentHalfSummary)[0].children[0].textContent,'197');assert.equal(rows(e.currentHalfSummary)[0].children[2].textContent,'83');
 change('currentHalfN','20');assert.match(e.currentHalfRatio.textContent,/35%/);
 assert.match(e.currentRoomSupport.textContent,/322.*295/);assert.equal(rows(e.currentRoomPairs).length,19);
 assert.match(e.currentAllianceStatus.textContent,/403.*403.*11/);
});
test('full policy comparison and different-selection subset retain their own denominators and failures',()=>{
 const {elements:e,change,data}=load();assert.match(e.currentQOverlap.textContent,/119 \/ 147/);
 assert.equal(rows(e.currentQSummary)[0].children[0].textContent,'140');assert.match(rows(e.currentQSummary)[0].children[5].textContent,/0\.0619/);
 assert.equal(rows(e.currentDifferentSummary)[0].children[0].textContent,'28');
 const unscored=data.different_events.find(r=>r.n==='14'&&r.comparator==='Q_RAW'&&r.structure_scored==='False');
 assert.ok(unscored);change('currentDifferentEvent',unscored.event_id);assert.equal(rows(e.currentDifferentDetail)[0].children[7].textContent,'缺失／不可估');
 assert.equal(rows(e.currentDifferentMembers).length,2);
 change('currentQN','20');assert.match(e.currentQOverlap.textContent,/35%.*54 \/ 61/);
 assert.equal(rows(e.currentQSummary)[0].children[0].textContent,'59');assert.match(rows(e.currentQSummary)[0].children[5].textContent,/-0\.1135/);
 change('currentQComparator','Q_PEER');assert.equal(rows(e.currentQSummary).length,1);
});
test('worker queries keep scope and Manual/Semi separate, preserving missing difficulty',()=>{
 const {elements:e,change,data}=load();assert.match(e.currentWorkerSupport.textContent,/60 人、6512/);assert.equal(e.currentWorker.value,'W109');assert.equal(rows(e.currentWorkerResults).length,3);
 change('currentWorkerScope','all_admitted');assert.match(e.currentWorkerSupport.textContent,/60 人、6739/);
 change('currentWorker','W017');assert.match(rows(e.currentWorkerResults)[2].children[1].textContent,/63\.21|63\.22/);
 assert.equal(rows(e.currentWorkerPreference)[0].children[6].textContent,'hard_advantage');
 change('currentWorkerCondition','semi');assert.match(e.currentWorkerSupport.textContent,/59 人、964/);assert.match(text(e.currentWorkerPreference),/没有已保存结果/);
 const missing=data.worker_wide.find(r=>r.scope==='primary'&&['easy_Q_image_mean','medium_Q_image_mean','hard_Q_image_mean'].some(k=>r[k]===''));
 if(missing){change('currentWorkerScope','primary');change('currentWorkerCondition','manual');change('currentWorker',missing.worker_id);assert.match(text(e.currentWorkerResults),/缺失／不可估/);}
});
test('current UI has all controls and local sources; display never fetches research data',()=>{
 const {elements:e}=load(),html=fs.readFileSync(path.join(page,'v21-results.html'),'utf8');
 for(const id of Object.keys(e))assert.ok(html.includes('id="'+id+'"'),id);
 const collect=el=>[el,...el.children.flatMap(collect)];
 for(const el of Object.values(e).flatMap(collect).filter(x=>x.tag==='a'&&x.href&&!x.href.startsWith('#')))assert.ok(fs.existsSync(path.resolve(page,el.href)),el.href);
 assert.doesNotMatch(fs.readFileSync(path.join(page,'v21-current.js'),'utf8'),/\bfetch\s*\(/);
 assert.match(html,/最终分类仍待确定|最终分类尚未定案/);
});


test('figure and doorway navigation resolves local artifacts and keeps adopted evidence identities',()=>{
 const html=fs.readFileSync(path.join(page,'v21-results.html'),'utf8');
 assert.doesNotMatch(html,/门洞双版本与GT在专门线程处理中/);
 for(const id of ['current-figures','current-doorway'])assert.ok(html.includes('id="'+id+'"'));
 for(const name of ['quality_policy_comparison','paired_image_quality'])for(const ext of ['pdf','svg','png'])assert.ok(html.includes(name+'.'+ext));
 for(const name of ['e9zR4mvMWw7-09','e9zR4mvMWw7-16','2t7WUuJeko7-07','7y3sRwLe3Va-10'])assert.ok(html.includes(name+'_original_gt.png'));
 assert.match(html,/7y-10：漏转折较强候选/);assert.match(html,/F01\/F03\/F04\/F06保留更新前标签身份/);
 for(const match of html.matchAll(/(?:href|src)="([^"#]+)"/g)){
  const url=match[1].replace(/&amp;/g,'&').split('#')[0];
  if(!/^[a-z]+:/i.test(url))assert.ok(fs.existsSync(path.resolve(page,url)),url);
 }
});
