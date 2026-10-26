const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const nodes={};
for(const id of ['metric','method','panel','overview','overallSupport','panelSupport','panelVariance','panelNumbers','distributions','configTable','historical','download'])nodes[id]={value:'',innerHTML:'',textContent:'',listeners:{},addEventListener(e,fn){this.listeners[e]=fn}};
nodes.metric.value='B8L2';nodes.method.value='DSTRUCT_K3';
const context={window:{},document:{getElementById:id=>nodes[id],createElement:()=>({click(){}})},Blob,URL,setTimeout};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../workers/dstruct_composition_bridge_20261026/presentation-data.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'composition-variance.js'),'utf8'),context);
assert.match(nodes.overview.innerHTML,/14.36%/);assert.match(nodes.panelSupport.textContent,/7y3sRwLe3Va-21/);
assert.equal((nodes.panel.innerHTML.match(/<option /g)||[]).length,231);
let renders=0;
for(const method of ['DSTRUCT_K2','DSTRUCT_K3','OLD_STRUCTURE_COARSE','OLD_STRUCTURE_FINE']){
 nodes.method.value=method;
 for(const metric of ['B8L2','D10','fusion_turn_n','log_recorded_time','not_complete_evaluable']){
  nodes.metric.value=metric;nodes.metric.listeners.change();renders++;
  assert.doesNotMatch(nodes.distributions.innerHTML,/NaN|undefined/);
 }
}
const data=context.window.CompositionVarianceData;
const constant=data.panels.find(p=>p.method==='DSTRUCT_K3'&&p.metric==='fusion_turn_n'&&p.total_variance===0);
nodes.method.value='DSTRUCT_K3';nodes.panel.value=constant.panel_id;nodes.metric.value='fusion_turn_n';nodes.panel.listeners.change();assert.match(nodes.panelVariance.innerHTML,/占比不可定义/);
const missing=data.panels.find(p=>p.method==='DSTRUCT_K3'&&p.metric==='log_recorded_time'&&p.valid_teams===0);
nodes.panel.value=missing.panel_id;nodes.metric.value='log_recorded_time';nodes.metric.listeners.change();assert.match(nodes.distributions.innerHTML,/没有这一指标/);
assert.match(nodes.panelVariance.innerHTML,/没有有效记录/);
assert.doesNotMatch(nodes.panelVariance.innerHTML,/总方差为零/);
assert.doesNotMatch(nodes.panelNumbers.innerHTML,/NaN|undefined/);
let plots=0;
for(const p of data.panels){
 nodes.method.value=p.method;nodes.metric.value=p.metric;nodes.panel.value=p.panel_id;nodes.panel.listeners.change();plots++;
 for(const match of nodes.distributions.innerHTML.matchAll(/(?:cx|x1|x2)="([^"]+)"/g)){
  const value=Number(match[1]);assert(Number.isFinite(value)&&value>=0&&value<=620,`${p.panel_id}/${p.method}/${p.metric}: clipped x=${value}`);
 }
 if(p.valid_teams===0)assert.match(nodes.panelVariance.innerHTML,/没有有效记录/);
 else if(p.total_variance===0)assert.match(nodes.panelVariance.innerHTML,/总方差为零/);
}
// Array field contract and numeric distribution consistency, on all saved rows.
const fields=data.configuration_fields;
const idx=k=>fields.indexOf(k);
for(const row of data.configurations){
 assert.equal(row.length,fields.length);
 assert.equal(row[idx('valid_teams')]+row[idx('missing_teams')],row[idx('teams')]);
 if(row[idx('valid_teams')])assert(row[idx('p05')]<=row[idx('p25')]&&row[idx('p25')]<=row[idx('median')]&&row[idx('median')]<=row[idx('p75')]&&row[idx('p75')]<=row[idx('p95')]);
}
console.log(JSON.stringify({renderer_cases:renders,all_panel_plots:plots,constant_panel:true,missing_time:true,configuration_rows:data.configurations.length,panel_options:231,browser_rendering_tested:false,native_download_tested:false}));
