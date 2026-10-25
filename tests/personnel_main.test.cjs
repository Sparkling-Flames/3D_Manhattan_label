// Exercise the saved-data render and change handlers without a browser or network.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.join(__dirname,'../research/statistics/research_explorer_v1_r2_20261017');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const index=read(path.join(page,'v2-data/index.json'));
const context={window:{}};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(page,'personnel-methods.js'),'utf8'),context);
context.PersonnelMethods=context.window.PersonnelMethods;
vm.runInContext(fs.readFileSync(path.join(page,'population-precision.js'),'utf8'),context);context.PopulationPrecision=context.window.PopulationPrecision;
vm.runInContext(fs.readFileSync(path.join(page,'personnel-main.js'),'utf8'),context);
class Element {
 constructor(tag='div'){this.tag=tag;this.value='';this.listeners={};this.textContent='';}
 set innerHTML(html){this.html=html;if(this.tag==='select')this.value=html.match(/<option value="([^"]*)"/)?.[1]??'';}
 get innerHTML(){return this.html||'';}
 querySelectorAll(){return [];}
 addEventListener(type,fn){this.listeners[type]=fn;}
 change(value){this.value=value;this.listeners.change();}
}
class Host extends Element {
 set innerHTML(html){this.html=html;this.nodes=new Map();for(const m of html.matchAll(/<(select|div|section|p|tbody)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);if(m[1]==='select')e.innerHTML=html.slice(m.index+m[0].length).split('</select>')[0];this.nodes.set('#'+m[2],e);}}
 get innerHTML(){return this.html;}
 querySelector(id){assert(this.nodes.has(id),'missing element '+id);return this.nodes.get(id);}
 querySelectorAll(ids){return ids.startsWith('[')?[]:ids.split(',').map(id=>this.querySelector(id));}
}
const loaded=new Set();
async function table(id){loaded.add(id);const meta=index.tables.find(t=>t.id===id);assert(meta,'missing table '+id);return meta.parts.flatMap(p=>{const d=read(path.join(page,'v2-data',p.path));return d.rows.map(row=>Object.fromEntries(d.columns.map((k,i)=>[k,row[i]])));});}
const shell=fs.readFileSync(path.join(page,'workbench.js'),'utf8'),hintScope={window:{},labels:{},innerWidth:1000,innerHeight:800,esc:v=>String(v)};vm.createContext(hintScope);
vm.runInContext(shell.slice(shell.indexOf('const metricHints='),shell.indexOf('const fieldList='))+'window.hints=metricHints;window.hintButton=hintButton;window.showHint=showHint;window.hideHint=hideHint;window.setPopover=p=>hintPopover=p;' ,hintScope);
const hints=hintScope.window.hints,hintButton=hintScope.window.hintButton;
for(const term of read(path.resolve(page,'../../workers/personnel_main_figures_v2_20261023/GLOSSARY.json')).terms)hints[term.id]=[term.short,term.detail];
for(const key of ['mae','rmse','bias','pearson_r','spearman_r','R2','SD','P10','P50','P90','resampling_unit','natural_paths','saved_endpoint','comparison_event','paired_quality','all_attempts','percentage_points','pair_nodes']){
 assert.equal(hints[key].length,2,key);assert(hints[key].every(x=>typeof x==='string'&&x.length>10),key);
 assert.match(hintButton(key),/type="button".*aria-label="解释 .*aria-describedby="metricHint"/);
}
assert.equal(hints.own_source_mae,hints.mae);assert.equal(hints.attempted_paths,hints.all_attempts);
assert.match(hints.resampling_unit[1],/2000.*24.*k20/);assert.match(hints.paired_quality[1],/不同路径集合/);
assert.match(hints.SD[1],/不是均值的置信区间/);assert.match(hints.P10[1],/分位带不是置信区间/);
assert.match(hints.bias[1],/高估.*低估/);assert.match(hints.percentage_points[1],/5个百分点.*50%/);
assert.match(hints.absolute_error[0],/单次/);assert.notEqual(hints.absolute_error,hints.mae);
assert.equal(hintButton('unregistered_hint'),'');
const popover={hidden:true,textContent:'',style:{},offsetWidth:300,offsetHeight:100},trigger={dataset:{hint:'mae'},setAttribute(k,v){this[k]=v;},getBoundingClientRect:()=>({left:20,top:20,bottom:40})};
hintScope.window.setPopover(popover);hintScope.window.showHint(trigger,false);assert.equal(popover.textContent,hints.mae[0]);assert.equal(popover.hidden,false);
hintScope.window.showHint(trigger,true);assert.equal(popover.textContent,hints.mae.join(' '));assert.equal(trigger['aria-expanded'],'true');
hintScope.window.hideHint();assert.equal(popover.hidden,true);assert.equal(trigger['aria-expanded'],'false');
assert.match(hints.Hmean[0],/0.1.*10%/);assert.match(hints.Hcenter[1],/去掉均高.*不是房间中心/);

async function render(tab){const host=new Host();await context.window.PersonnelMain.render(host,{release:'v2',index,tab,table,hintButton,isCurrent:()=>true});return host;}
(async()=>{
 let host=await render(0);
 assert.equal((host.innerHTML.match(/data-scheme=/g)||[]).length,4);
 assert.equal((host.innerHTML.match(/data-current-method=/g)||[]).length,8);
 assert(host.innerHTML.indexOf('id="currentClassification"')<host.innerHTML.indexOf('id="classificationQuestions"'));
 assert.match(host.querySelector('#newRosterDetail').innerHTML,/困难时保留较多非冗余转折/);
 const guide=context.window.PersonnelMethods.read(index);
 assert(guide.methods.some(m=>m.id==='DSTRUCT_K2'));
 assert.match(host.innerHTML,/术语词典 · 75项/);
 for(const method of guide.methods){
  host.querySelector('#newMethod').change(method.id);
  for(const fold of [...new Set(guide.rosters.map(r=>r.fold))]){
   host.querySelector('#newFold').change(fold);
   const html=host.querySelector('#newRosterDetail').innerHTML;
   assert.match(html,/共62人/);assert.doesNotMatch(html,/undefined|NaN/);
   if(fold!=='ALL')assert.doesNotMatch(html,/C3 · 困难时保留/);
  }
 }
 host.querySelector('#newMethod').change('RFUSE_GEOM_K2');host.querySelector('#newFold').change('ALL');
 assert.match(host.querySelector('#newRosterDetail').innerHTML,/W109、W112、W126、W130/);
 assert(host.innerHTML.indexOf('id="classificationQuestions"')<host.innerHTML.indexOf('id="personCondition"'));
 assert.match(host.innerHTML,/24\/27图/);assert.match(host.querySelector('#personCount').textContent,/248 \/ 248/);
 host.querySelector('#personCondition').change('semi');assert.match(host.querySelector('#personCount').textContent,/124 \/ 248/);
 host=await render(1);assert.match(host.innerHTML,/13,406/);assert.match(host.innerHTML,/全部79格/);
 host.querySelector('#mixtureExample').change('semi_failure');assert.match(host.querySelector('#mixtureDetails').innerHTML,/205队失败/);
 host=await render(2);assert.equal(host.querySelector('#ordinaryExchange').value,'S01');
 assert(host.innerHTML.indexOf('id="currentExchanges"')<host.innerHTML.indexOf('id="ordinaryExchangeResults"'));
 assert.match(host.innerHTML,/n21 \/ m7/);assert.match(host.innerHTML,/n28 \/ m7/);
 assert.match(host.querySelector('#newExchangeDetail').innerHTML,/30图 \/ 235事件/);
 host.querySelector('#newConditionRange').change('all');
 for(let i=0;i<guide.all_conditions.length;i++){
  host.querySelector('#newExchange').change(String(i));
  for(const metric of ['B8L2','D10','IoU3D100','geometry_bev_distance','geometry_top_angle','geometry_bottom_angle','floor_turn5_n']){
   host.querySelector('#newMetric').change(metric);
   assert.doesNotMatch(host.querySelector('#newExchangeDetail').innerHTML,/undefined|NaN/);
  }
 }
 host.querySelector('#newConditionRange').change('main');host.querySelector('#newExchange').change('2');host.querySelector('#newMetric').change('B8L2');
 assert.match(host.querySelector('#newExchangeDetail').innerHTML,/1\.828/);
 assert.match(host.querySelector('#newExchangeDetail').innerHTML,/4\/56/);
 assert(host.innerHTML.indexOf('id="ordinaryExchangeResults"')<host.innerHTML.indexOf('id="sameRoomExtension"'));
 assert(host.innerHTML.includes('<details open><summary>查看同房大块、替换规模与背景结果</summary>'));
 assert.match(host.innerHTML,/20 \/ 6/);assert.match(host.innerHTML,/17 \/ 23/);
 let detail=host.querySelector('#ordinaryExchangeDetail').innerHTML;
 assert.match(detail,/Manual结构类/);assert.match(detail,/96\/120图/);assert.match(detail,/76\/120图/);
 host.querySelector('#ordinaryExchange').change('S03');detail=host.querySelector('#ordinaryExchangeDetail').innerHTML;
 assert.match(detail,/-1\.363/);assert.match(detail,/46\/72图/);
 host.querySelector('#ordinaryExchange').change('J01');assert.match(host.querySelector('#ordinaryExchangeDetail').innerHTML,/-1\.565/);
 for(const [id,n,q] of [['D01',9,'8.59'],['D02',11,'-1.247']]){
  host.querySelector('#ordinaryExchange').change(id);detail=host.querySelector('#ordinaryExchangeDetail').innerHTML;
  assert.match(detail,new RegExp('Q：'+n+'图'));assert(detail.includes(q));
  assert.match(detail,/不借用总体的事件数/);assert.doesNotMatch(detail,/Q：22图|共同Q\/T交集的净Q/);
 }
 host.querySelector('#ordinaryCondition').change('semi');assert.equal(host.querySelector('#ordinaryExchange').value,'E01');
 for(const c of await table('personnel_main__ORDINARY_EXCHANGE_CONDITIONS')){
  host.querySelector('#ordinaryCondition').change(c['评价条件']);host.querySelector('#ordinaryExchange').change(c['编号']);
  assert.doesNotMatch(host.querySelector('#ordinaryExchangeDetail').innerHTML,/undefined|NaN/);
 }
 const allHTML=[host.innerHTML];
 const mechanismHost=await render(5);assert.match(mechanismHost.innerHTML,/B6-47/);assert.match(mechanismHost.innerHTML,/96.60→45.46/);
 for(const tab of [0,1,3,5])allHTML.push((await render(tab)).innerHTML);
 for(const url of allHTML.join('').matchAll(/(?:href|src)="([^"#]+)"/g)){
  if(/^(?:https?:|data:)/.test(url[1]))continue;
  const target=path.resolve(page,url[1].split('#')[0].split('?')[0]);
  assert(fs.existsSync(target),'missing local link '+url[1]);
 }
 const difficulty=await render(3);assert.doesNotMatch(difficulty.innerHTML,/precisionPolicy/);
 const population=await render(4);allHTML.push(population.querySelector('#latePopulation').innerHTML);assert(population.innerHTML.includes('id="precisionNatural"'));assert(population.innerHTML.includes('id="precisionPolicy"'));
 allHTML.push(population.querySelector('#precisionNatural').innerHTML,population.querySelector('#precisionPolicy').innerHTML);
 for(const key of ['natural_paths','saved_endpoint','resampling_unit','paired_quality','all_attempts','percentage_points'])assert(allHTML.join('').includes('data-hint="'+key+'"'),key);
 for(const id of allHTML.join('').matchAll(/data-table-jump="([^"]+)"/g))assert(index.tables.some(t=>t.id===id[1]),id[1]);
 const overview=read(path.join(page,'v2-data/overview.json'));
 assert.deepEqual(overview.sections.map(x=>x.id),['quality','consensus','difficulty','profiles','classification','mixture','exchange','population','same_room','doorway','oos']);
 for(const item of overview.sections){assert(item.finding&&item.support&&item.counterexample);for(const t of item.tables)assert(index.tables.some(x=>x.id===t.id),t.id);assert(fs.existsSync(path.resolve(page,item.source.split('#')[0])),item.source);}
 for(const html of allHTML)assert.doesNotMatch(html,/href="[^"<>]*\.(?:md|json|py|zip)(?:[?#][^"<>]*)?"/i);
 const output={innerHTML:''},presentation={window:{},dataset:{release:'v2'},SNAPSHOT:'v2_integrated_analysis_20261019',overview,assets:read(path.join(page,'v2-resources/index.json')),index:{...index,documents:[{path:'PRIVATE_INTERNAL.md',content:'INTERNAL_DRAFT_SENTINEL'}]},state:{},$:()=>output,esc:hintScope.esc,fmt:String,label:k=>k,hintButton,metricCards:()=>''};
 vm.createContext(presentation);
 vm.runInContext(shell.slice(shell.indexOf('function renderOverview(){'),shell.indexOf('function renderPlan(){'))+shell.slice(shell.indexOf('function renderSources(){'),shell.indexOf('function setTable('))+'renderOverview();',presentation);
 const publicOverview=output.innerHTML;vm.runInContext('renderSources();',presentation);
 for(const html of [publicOverview,output.innerHTML])assert.doesNotMatch(html,/\.md|PRIVATE_INTERNAL|INTERNAL_DRAFT|CONCLUSIONS_ZH|CATALOG|CONSUMER_INTERFACE|上游核对|当前消费/);
 assert.match(publicOverview,/OOS 独立统计/);assert.match(publicOverview,/查看实例与图表/);
 assert.equal((output.innerHTML.match(/data-table-jump=/g)||[]).length,index.tables.length);
 for(const name of ['index.html','oos-review.html'])assert.doesNotMatch(fs.readFileSync(path.join(page,name),'utf8'),/href="[^"<>]*\.md(?:[?#][^"<>]*)?"/i);
 const current=guide.main_conditions.find(x=>x.method==='DSTRUCT_K3');assert(overview.sections.find(x=>x.id==='exchange').finding.includes(current.B8L2_cross_image_equal.toFixed(3)));

 console.log('PASS: CONTEXT hint definitions and population placements, 8 method/layer displays × 23 rosters, 71 × 7 metric selections, 4 historical schemes, all-source links, ordinary-before-same-room, all 18 conditions, Manual/Semi, m6, failure and difficulty denominators');
})().catch(e=>{console.error(e);process.exitCode=1;});
