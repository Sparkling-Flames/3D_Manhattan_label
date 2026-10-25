const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const scope={window:{}};vm.createContext(scope);vm.runInContext(fs.readFileSync(path.join(__dirname,'../research/statistics/research_explorer_v1_r2_20261017/current-class-answers.js'),'utf8'),scope);const A=scope.window.CurrentClassAnswers;
test('image and answer selection keeps target fold, actual membership, Manual and ordinary scene',()=>{
 const images=[{image_id:'a',building_id:'one',scene:{doorway_status:'none'}},{image_id:'b',building_id:'two',scene:{doorway_status:'none'}},{image_id:'o',building_id:'one',scene:{doorway_status:'none'},flags:{oos:true}},{image_id:'d',building_id:'one',scene:{doorway_status:'doorway'}}];
 const records=images.map(i=>({image_id:i.image_id,condition:'manual',worker_id:'W1'}));
 assert.deepEqual(A.imageChoices(images,records,'one','W1'),[images[0]]);
 assert.equal(A.imageChoices(images,records,'ALL','missing').length,0);
 const detail={annotations:[{object_id:'x',condition:'manual',worker_id:'W1'},{object_id:'y',condition:'semi',worker_id:'W1'},{object_id:'z',condition:'manual',worker_id:'W2'}]};
 assert.deepEqual(A.answers(detail,{workers:['W1']}),[detail.annotations[0]]);
 assert.equal(A.answers(detail,{workers:['W1']},'W2').length,0);
});
class Element{
 constructor(){this.value='';this.html='';this.options=[];this.textContent='';}
 set innerHTML(s){this.html=s;this.options=[...s.matchAll(/<option value="([^"]*)"/g)].map(x=>({value:x[1]}));this.value=this.options[0]?.value||'';}
 get innerHTML(){return this.html;}
}
class Host extends Element{querySelector(id){return this.nodes[id]??=(new Element());}constructor(){super();this.nodes={};}}
test('roster focus draws exact saved objects and rejects a late image read after navigation',async()=>{
 const host=new Host(),mounted=[],meta={image_id:'img',image_code:'code',building_id:'one',scene:{doorway_status:'none'}},detail={image_id:'img',annotations:[{worker_id:'W1',object_id:'a',condition:'manual',points:[[1,2],[1,3]]},{worker_id:'W2',object_id:'b',condition:'manual',points:[[2,2],[2,3]]}]};
 let current=true,read=async()=>detail;
 const ctx={isCurrent:()=>current,table:async()=>detail.annotations.map(a=>({...a,image_id:'img'})),assets:{images:[meta]},imageDetail:id=>read(id)};
 scope.window.WorkbenchGeometry={mount:(slot,image,a,reference)=>mounted.push({image,a,reference})};
 const data={rosters:[{method:'m',fold:'ALL',class_id:'C1',known:true,workers:['W1']},{method:'m',fold:'ALL',class_id:'C2',known:true,workers:['W2']}],role:r=>r.class_id};
 const viewer=await A.mount(host,ctx,data);await viewer.update('m','ALL');assert.equal(mounted.at(-2).a.object_id,'a');assert.equal(mounted.at(-1).a.object_id,'b');assert.equal(mounted[0].reference,null);
 await viewer.focus('W2');assert.equal(host.querySelector('#classAnswerGroupA').value,'C2');assert.equal(mounted.at(-2).a.object_id,'b');
 let resolve;read=()=>new Promise(r=>resolve=r);const pending=viewer.update('m','ALL');const count=mounted.length;current=false;resolve(detail);await pending;assert.equal(mounted.length,count);
});
const page=path.join(__dirname,'../research/statistics/research_explorer_v1_r2_20261017'),indexFile=path.join(page,'v2-data/index.json');
test('current packed methods draw only their actual Manual members in ALL and target-building views',{skip:!fs.existsSync(indexFile)},async()=>{
 const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),index=read(indexFile),assets=read(path.join(page,'v2-resources/index.json'));
 vm.runInContext(fs.readFileSync(path.join(page,'personnel-methods.js'),'utf8'),scope);const d=scope.window.PersonnelMethods.read(index),meta=index.tables.find(t=>t.id==='quality__shared_records');
 const records=meta.parts.flatMap(p=>{const x=read(path.join(page,'v2-data',p.path));return x.rows.map(row=>Object.fromEntries(x.columns.map((k,i)=>[k,row[i]])));});
 const cache=new Map(),mounted=[],host=new Host();scope.window.WorkbenchGeometry={mount:(slot,img,answer)=>mounted.push({img,answer})};
 const ctx={isCurrent:()=>true,table:async()=>records,assets,imageDetail:async id=>{if(!cache.has(id))cache.set(id,read(path.join(page,'v2-resources',assets.images.find(i=>i.image_id===id).detail)));return cache.get(id);}};
 const viewer=await A.mount(host,ctx,d),fold=d.rosters.find(r=>r.fold!=='ALL').fold;
 for(const method of d.methods)for(const selected of ['ALL',fold]){
  mounted.length=0;await viewer.update(method.id,selected);
  for(const {img,answer} of mounted){assert.equal(answer.condition,'manual');assert(d.rosters.some(r=>r.method===method.id&&r.fold===selected&&r.workers.includes(answer.worker_id)));if(selected!=='ALL')assert.equal(assets.images.find(i=>i.image_id===img.image_id).building_id,selected);}
  const worker=d.rosters.find(r=>r.method===method.id&&r.fold===selected&&r.known).workers[0];mounted.length=0;await viewer.focus(worker);
  assert(!host.querySelector('#classAnswerStatus').textContent.includes('读取失败'));
  if(mounted.length)assert.equal(mounted.at(-2)?.answer.worker_id||mounted[0].answer.worker_id,worker);
 }
});
