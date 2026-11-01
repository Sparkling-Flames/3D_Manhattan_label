const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');

test('offline case reader renders every current event and arm, including incomplete outputs',()=>{
 const file=path.resolve(__dirname,'../research/data/releases/v2.1/half_team_current_exceptions_20261031/viewer.html');
 const html=fs.readFileSync(file,'utf8'),json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
 const data=JSON.parse(json),script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
 const context2d=new Proxy({}, {get:(target,key)=>target[key]??(()=>{})}),elements={};
 class Element {
  constructor(id){this.id=id;this.value=id==='arm'?'C':'';this.checked=id==='groups';this.textContent=id==='data'?json:'';}
  set innerHTML(value){this.html=value;if(['image','event','raw'].includes(this.id))this.value=value.match(/value="([^"]*)"/)?.[1]??'';}
  get innerHTML(){return this.html;}
  getContext(){return context2d;}
  querySelectorAll(){return [];}
 }
 const context={document:{getElementById:id=>elements[id]??=new Element(id)},Image:class {complete=false;},URLSearchParams,location:{search:'?image=jh4fc5c5qoQ-13'}};
 vm.createContext(context);vm.runInContext(script,context);
 assert.equal(elements.image.value,'jh4fc5c5qoQ-13');
 let rendered=0;
 for(const image of Object.values(data.images)){
  elements.image.value=image.image;elements.image.onchange();
  for(const id of image.event_ids){
   elements.event.value=id;elements.event.onchange();
   for(const arm of ['A','B','C']){
    elements.arm.value=arm;elements.arm.onchange();rendered++;
    const team=data.teams[data.events[id][arm+'_team_key']];
    assert.ok(elements.notes.innerHTML.includes(data.events[id].current_explanation));
    assert.ok(elements.detail.textContent.includes('minimum_support'));
    if(team.score_status!=='complete_conditional')assert.match(elements.notes.innerHTML,/仅显示真实已选角点/);
   }
  }
 }
 assert.equal(rendered,189);
 elements.allraw.checked=true;elements.allraw.onchange();
 elements.raw.value=data.pools[data.events[elements.event.value].pool_id].records[0].worker_id;elements.raw.onchange();
 assert.doesNotMatch(script,/\bfetch\s*\(/);
});
