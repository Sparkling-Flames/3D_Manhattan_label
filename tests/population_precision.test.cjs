const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.resolve(__dirname,'../research/statistics/research_explorer_v1_r2_20261017'),scope={window:{}};vm.createContext(scope);
vm.runInContext(fs.readFileSync(path.join(page,'population-precision.js'),'utf8'),scope);const P=scope.window.PopulationPrecision;
const index=JSON.parse(fs.readFileSync(path.join(page,'v2-data/index.json'),'utf8'));
function table(id){const t=index.tables.find(t=>t.id===id);assert(t,id);return t.parts.flatMap(p=>{const d=JSON.parse(fs.readFileSync(path.join(page,'v2-data',p.path),'utf8'));return d.rows.map(r=>Object.fromEntries(d.columns.map((k,i)=>[k,r[i]])));});}
class Pane{
 set innerHTML(html){this.html=html;this.controls=[];for(const m of html.matchAll(/<select data-precision="([^"]+)">([\s\S]*?)<\/select>/g)){const options=[...m[2].matchAll(/<option value="([^"]*)"( selected)?>/g)];this.controls.push({dataset:{precision:m[1]},value:(options.find(o=>o[2])||options[0])?.[1]});}}
 get innerHTML(){return this.html;}
 querySelectorAll(){return this.controls;}
 change(key,value){const el=this.controls.find(e=>e.dataset.precision===key);assert(el,key);el.value=value;el.onchange();}
}
test('marginal points and deferred stage remain separate from entry paths',()=>{
 const rows=P.fixedRows([{panel:'fixed_N_ge_30',layer:'ordinary_manual',difficulty:'全部',metric:'Q_mean',weighting:'image_equal',k:1,estimate:0}],{panel:'fixed_N_ge_30',layer:'ordinary_manual',difficulty:'全部',metric:'Q_mean'});
 assert.equal(rows[0].estimate,0);assert.equal(rows[1].k,2);assert.equal(rows[1].estimate,undefined);assert.equal(rows[1].deferred,true);
 assert.equal(P.estimator({estimator:'exact_finite_uniform_marginal'}),'精确有限边际');assert.equal(P.present(null),false);assert.equal(P.present(0),true);
});
test('real natural controls preserve source versions, complete supports and finite low-tail example',async()=>{
 const pane=new Pane(),view=await P.create('natural',{table,isCurrent:()=>true});view.activate({querySelector:()=>pane});
 assert.match(pane.innerHTML,/26图升/);assert.match(pane.innerHTML,/精确\/随机256图/);assert.match(pane.innerHTML,/未运行/);
 assert.match(pane.innerHTML,/97\.387/);assert.match(pane.innerHTML,/52\.406/);assert.match(pane.innerHTML,/不拼接精确点/);
 for(const panel of ['fixed_N_ge_6','fixed_N_ge_20','fixed_N_ge_30','fixed_N_ge_35']){pane.change('panel',panel);for(const version of ['hybrid256','pooled256','new208','stage1_104','stage2_104','old48','prior96','all_history304','old24','new24']){pane.change('version',version);assert.doesNotMatch(pane.innerHTML,/NaN|undefined/);}}
 pane.change('layer','doorway_manual');assert.match(pane.innerHTML,/门洞 Manual/);assert.doesNotMatch(pane.innerHTML,/所选范围没有保存/);
 pane.change('metric','failure_rate');pane.change('interval','20_to_30');assert.match(pane.innerHTML,/两人延期保留缺口/);assert.match(pane.innerHTML,/共同可评路径Q差/);
 const stale=await P.create('natural',{table,isCurrent:()=>false});assert.equal(stale.head,'');
});
test('corrected policy controls never pool sparse time with all-quality support or hide invalid bootstrap draws',async()=>{
 const pane=new Pane(),view=await P.create('policy',{table,isCurrent:()=>true});view.activate({querySelector:()=>pane});
 assert.match(pane.innerHTML,/7\.669/);assert.match(pane.innerHTML,/2000\/2000；不可估0/);assert.match(pane.innerHTML,/115\/94\/72\/117/);assert.match(pane.innerHTML,/仅148图交集/);
 for(const batch of ['old16','new16','pooled32']){pane.change('batch',batch);for(const phase of ['early_3_to_half','low_3_to_6','late_20_to_Nminus1','full']){pane.change('phase',phase);for(const metric of ['paired_Q_delta','failure_delta','labor_ratio_legal','QT_paired_Q_delta']){pane.change('metric',metric);assert.doesNotMatch(pane.innerHTML,/NaN|undefined/);}}}
 assert.match(pane.innerHTML,/旧67图\/18楼/);assert.match(pane.innerHTML,/不是DSTRUCT\/RFUSE策略验证/);assert.doesNotMatch(pane.innerHTML,/href="[^"<>]*\.md/);
});

test('hybrid summaries keep a fixed image set across legal k, with exact sources and a deferred gap',()=>{
 const data={hybrid_images:table('population256__hybrid_images')};
 for(const layer of ['ordinary_manual','doorway_manual']) for(const metric of ['Q_mean','actual_consensus_failure_rate','output_unscoreable_rate']){
  const rows=P.hybridSummary(data,{layer,panel:'fixed_N_ge_30',difficulty:'全部',metric});
  assert.equal(rows[1].deferred,true);assert.equal(rows.length,30);
  const legal=rows.filter(r=>!r.deferred);assert.equal(new Set(legal.map(r=>r.images)).size,1);
  assert(legal.every(r=>r.exact_images+r.random_images===r.images));
 }
});
