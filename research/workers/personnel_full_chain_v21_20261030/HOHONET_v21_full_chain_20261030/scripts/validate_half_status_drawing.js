// Validate the saved half-team viewer's actual canvas paths by endpoint status.
// Node VM execution is separate from the real-browser acceptance receipt.
// Run: node scripts/validate_half_status_drawing.js
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),out=path.join(root,'stage01_half_team');
const html=fs.readFileSync(path.join(out,'HOHONET_latest_half_all36_viewer_ZH.html'),'utf8');
const json=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1],data=JSON.parse(json),elements={},contexts={};
const colors={A:'#176fbc',B:'#8551b6',C:'#d34931'};
function canvas(id){
  if(contexts[id])return contexts[id];
  const s={strokeStyle:'',fillStyle:'',strokes:[],fills:[],path:{lines:0,arcs:0,closed:false},stack:[]};
  const handlers={
    clearRect(){s.strokes=[];s.fills=[];},
    beginPath(){s.path={lines:0,arcs:0,closed:false};},
    moveTo(){},lineTo(){s.path.lines++;},arc(){s.path.arcs++;},
    closePath(){s.path.closed=true;},
    stroke(){s.strokes.push({color:s.strokeStyle,...s.path});},
    fill(){s.fills.push({color:s.fillStyle,...s.path});},
    save(){s.stack.push([s.strokeStyle,s.fillStyle,s.globalAlpha,s.lineWidth]);},
    restore(){const x=s.stack.pop();if(x)[s.strokeStyle,s.fillStyle,s.globalAlpha,s.lineWidth]=x;}
  };
  const ctx=new Proxy(s,{
    get(o,k){if(k in o)return o[k];return (...args)=>{for(const a of args)if(typeof a==='number')assert(Number.isFinite(a),'nonfinite '+id+' '+k);if(handlers[k])handlers[k](...args);};},
    set(o,k,v){o[k]=v;return true;}
  });
  contexts[id]=ctx;return ctx;
}
function element(id){
  if(elements[id])return elements[id];
  let html='';
  const e={value:'',checked:false,textContent:id==='data'?json:'',dataset:{},getContext:()=>canvas(id),querySelectorAll:()=>[],click(){}};
  Object.defineProperty(e,'innerHTML',{get(){return html;},set(v){html=v;const m=v.match(/<option value="([^"]*)"/);if(m)e.value=m[1];}});
  elements[id]=e;return e;
}
element('arm').value='C';
const sandbox={document:{getElementById:element,createElement:()=>({click(){}})},Image:class{constructor(){this.complete=true;this.naturalWidth=1536;}set src(x){this._src=x;}},URL:{createObjectURL:()=>'',revokeObjectURL(){}},Blob:class{},setTimeout(){},console};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'scripts/half_case_viewer.js'),'utf8'),sandbox);
let visited=0,complete=0,incomplete=0,rawChecks=0;
const statusCounts={},anchor=[];
for(const [im,info] of Object.entries(data.images)){
  element('image').value=im;element('image').onchange();
  for(const eid of info.event_ids){
    element('event').value=eid;element('event').onchange();
    for(const arm of ['A','B','C']){
      element('arm').value=arm;element('raw').value='';element('allraw').checked=false;element('groups').checked=false;element('arm').onchange();
      const t=data.teams[data.events[eid][arm+'_team_key']],col=colors[arm],good=t.score_status==='complete_conditional';
      visited++;statusCounts[t.score_status]=(statusCounts[t.score_status]||0)+1;
      const pano=contexts.pano,floor=contexts.floor;
      const pLines=pano.strokes.filter(s=>s.color===col&&(s.lines>0||s.closed)),fLines=floor.strokes.filter(s=>s.color===col&&(s.lines>0||s.closed));
      assert(floor.strokes.some(s=>s.color==='#121921'&&s.closed),'reference ring missing');
      if(good){
        complete++;
        assert(pLines.length>0,'complete pano ring removed '+eid+arm);
        assert(fLines.some(s=>s.closed),'complete floor ring removed '+eid+arm);
      }else{
        incomplete++;
        assert.strictEqual(pLines.length,0,'incomplete pano connected '+eid+arm);
        assert.strictEqual(fLines.length,0,'incomplete floor connected '+eid+arm);
        const selected=t.full_state.identity_groups.filter(g=>g.selected&&g.center).length;
        assert(pano.fills.filter(s=>s.color===col&&s.arcs).length>=selected*2,'selected corners absent');
        assert(floor.fills.filter(s=>s.color===col&&s.arcs).length>=selected,'selected floor points absent');
        assert(elements.notes.innerHTML.includes('仅显示真实已选角点'),'status message absent');
        if(eid==='3541b27a4eff744938462e2b')anchor.push({image:im,event_id:eid,arm,score_status:t.score_status,selected_nodes:selected,pano_connection_strokes:pLines.length,floor_connection_strokes:fLines.length});
        element('raw').value=t.member_workers[0];element('raw').onchange();
        assert(contexts.pano.strokes.some(s=>s.color==='#ec9b13'&&s.lines>0),'raw panorama ring removed');
        assert(contexts.floor.strokes.some(s=>s.color==='#ec9b13'&&s.closed),'raw floor ring removed');
        rawChecks++;element('raw').value='';
      }
    }
  }
}
assert.strictEqual(visited,348);assert.strictEqual(complete,330);assert.strictEqual(incomplete,18);assert.strictEqual(anchor.length,2);
for(const a of anchor)assert.strictEqual(a.selected_nodes,3);
const before=JSON.parse(fs.readFileSync(path.join(out,'VIEWER_SCIENTIFIC_FILES_BEFORE.json'),'utf8')),scientific=[];
for(const [file,hash] of Object.entries(before)){
  const after=crypto.createHash('sha256').update(fs.readFileSync(path.join(out,file))).digest('hex');
  assert.strictEqual(after,hash,'science file changed '+file);
  scientific.push({file,sha256:after,unchanged:true});
}
const receipt={
  passed:true,
  validation:'Instrumented canvas stroke paths by team color: every non-complete endpoint must have zero connecting/closed strokes in both panorama and floor; complete consensus and real reference/raw rings remain.',
  images:Object.keys(data.images).length,events:Object.keys(data.events).length,endpoints:visited,
  complete_endpoints_with_rings:complete,incomplete_endpoints_points_only:incomplete,status_counts:statusCounts,
  raw_ring_checks_on_incomplete_endpoints:rawChecks,anchor_below_four:anchor,scientific_files_unchanged:scientific,
  reference_and_raw_geometry_unchanged:true,new_fusion_or_scoring:0,browser_visual_acceptance:false,
  method_scope:'This receipt validates all saved endpoint drawing paths in a Node VM canvas shim; it does not claim real-browser visual acceptance.',
  browser_acceptance_record:'stage06_synthesis/browser_acceptance/BROWSER_EXECUTION_CHECKS.json'
};
fs.writeFileSync(path.join(out,'VIEWER_STATUS_DRAWING_CHECKS.json'),JSON.stringify(receipt,null,2));
console.log(JSON.stringify({passed:true,endpoints:visited,complete,incomplete,rawChecks,anchor}));
