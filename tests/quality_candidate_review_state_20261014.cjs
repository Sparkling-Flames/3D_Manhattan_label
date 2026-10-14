// Test score disclosure and receipt persistence without opening a browser.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const base='research/quality_candidate_review_20261014/';
const elements={},selected={},saved={};
class Element{constructor(){this.value='';this.hidden=false;this.children=[];}append(...x){this.children.push(...x)}replaceChildren(...x){this.children=x}click(){}}
const context={Review3D:{open(){}},console,Date,JSON,setTimeout,Blob,URL,Option:class extends Element{},window:{scrollTo(){}},
 localStorage:{getItem:k=>saved[k],setItem:(k,v)=>saved[k]=v},
 document:{getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element(),createTextNode:t=>t,
 querySelector:s=>selected[s.match(/name="(.*?)"/)[1]],querySelectorAll:()=>[]}};
vm.createContext(context);vm.runInContext(fs.readFileSync(base+'data.js','utf8')+fs.readFileSync(base+'app.js','utf8'),context);
assert.equal(elements.scores.hidden,true);
selected.floor={value:'A_slight'};elements.save.onclick();
elements.reveal.onclick();
let result=JSON.parse(saved.quality_candidate_review_20261014_v1).P01;
assert(result.score_revealed_at);assert.equal(result.answers_at_first_score_reveal.floor.value,'A_slight');
assert.equal(result.answers_at_first_score_reveal.height.value,null);assert.equal(result.overall_conditions_complete,false);
assert.equal(elements.scores.hidden,false);
selected.height={value:'uncertain'};selected.overall={value:'close'};elements.save.onclick();
elements.reveal.onclick();elements.reveal.onclick();
result=JSON.parse(saved.quality_candidate_review_20261014_v1).P01;
assert.equal(result.answers_at_first_score_reveal.height.value,null);
assert.equal(result.answers.height.value,'uncertain');assert.equal(result.overall_conditions_complete,true);
assert.equal(result.bindings[0].record_id,'R02015');
console.log('score reveal, first-answer snapshot and revised receipt passed');
