// Execute every saved image/event/arm against an instrumented DOM/canvas shim.
// This verifies execution and finite drawing commands, not browser layout QA.
const fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'stage01_half_team');
const html=fs.readFileSync(path.join(out,'HOHONET_latest_half_all36_viewer_ZH.html'),'utf8');
const json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const data=JSON.parse(json),elements={},calls={renderOperations:0,nonfinite:0};
const context=new Proxy({}, {get:(obj,name)=>obj[name]??((...args)=>{for(const x of args)if(typeof x==='number'&&!Number.isFinite(x)){calls.nonfinite++;throw Error('Nonfinite '+name)}calls.renderOperations++;}),set:(obj,key,val)=>(obj[key]=val,true)});
function element(id){if(elements[id])return elements[id];let inner='';const x={value:'',checked:id==='groups',textContent:id==='data'?json:'',dataset:{},getContext:()=>context,querySelectorAll:()=>[],click:()=>{}};
Object.defineProperty(x,'innerHTML',{get:()=>inner,set:v=>{inner=v;const m=v.match(/<option value="([^"]*)"/);if(m)x.value=m[1];}});elements[id]=x;return x;}
element('arm').value='C';
const sandbox={document:{getElementById:element,createElement:()=>({click:()=>{}})},Image:class{constructor(){this.complete=true;this.naturalWidth=1536;}set src(x){this._src=x;}},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},Blob:class{},setTimeout:()=>{},console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(root,'scripts/half_case_viewer.js'),'utf8'),sandbox);
let images=0,events=0,arms=0,rawLayers=0;
for(const [im,info] of Object.entries(data.images)){
  element('image').value=im;element('image').onchange();images++;
  for(const eid of info.event_ids){element('event').value=eid;element('event').onchange();events++;
    for(const a of ['A','B','C']){element('arm').value=a;element('arm').onchange();arms++;
      const team=data.teams[data.events[eid][a+'_team_key']];
      if(!elements.scores.innerHTML.includes(team.score_status))throw Error('Status absent');
      element('raw').value=team.member_workers[0];element('allraw').checked=true;element('raw').onchange();rawLayers++;
      element('raw').value='';element('allraw').checked=false;
    }
  }
}
const receipt={passed:true,images,events,arms,rawLayers,...calls,js_syntax_passed:true,all_embedded_json_parsed:true,browser_visual_acceptance:false,method_scope:'This receipt verifies every saved image/event/arm and raw layer in a Node VM with instrumented DOM/canvas. It does not claim real-browser visual acceptance; the real-browser checks are recorded separately.',browser_acceptance_record:'stage06_synthesis/browser_acceptance/BROWSER_EXECUTION_CHECKS.json'};
fs.writeFileSync(path.join(out,'VIEWER_EXECUTION_CHECKS.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
