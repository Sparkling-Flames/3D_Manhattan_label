import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import {fileURLToPath} from 'node:url';
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');const html=fs.readFileSync(path.join(base,'workbench/index.html'),'utf8');
const decode=s=>s.replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&quot;','"').replaceAll('&#39;',"'");
class Element{constructor(){this._html='';this.value='';this.textContent='';this.listeners={};this.options=[];}set value(v){this._value=String(v);}get value(){return this._value;}set innerHTML(s){this._html=s;if(s.includes('<option')){this.options=[...s.matchAll(/<option value="([^"]*)">/g)].map(m=>decode(m[1]));this.value=this.options[0]||'';}}get innerHTML(){return this._html;}addEventListener(n,f){this.listeners[n]=f;}}
const elements=new Map();function get(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}
get('data').textContent=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const scripts=[...html.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
vm.runInNewContext(scripts.at(-1),{document:{getElementById:get},console},{timeout:10000});
function choose(id,value){get(id).value=value;get(id).listeners.change?.();}
let checked=0;
for(const id of ['atable','ftable','ctable','btable','ledger']){if(!get(id).innerHTML.includes('<tbody><tr>'))throw Error('Default table empty: '+id);checked++;}
for(const method of [...get('cmethod').options])for(const metric of [...get('cmetric').options]){choose('cmethod',method);choose('cmetric',metric);for(const diff of [...get('cdifficulty').options]){choose('cdifficulty',diff);if(!get('ctable').innerHTML.includes('<tbody><tr>'))throw Error('Curve condition unexpectedly empty: '+[method,metric,diff]);if(!get('cchart').innerHTML.includes('<polyline'))throw Error('Missing curve');checked++;}}
for(const study of [...get('bstudy').options])for(const dir of [...get('bdirection').options]){choose('bstudy',study);choose('bdirection',dir);for(const support of [...get('bsupport').options]){choose('bsupport',support);for(const metric of [...get('bmetric').options]){choose('bmetric',metric);if(!get('btable').innerHTML.includes('<tbody><tr>'))throw Error('ABC condition unexpectedly empty: '+[study,dir,support,metric]);checked++;}}}
for(const method of [...get('fmethod').options]){choose('fmethod',method);if(!get('ftable').innerHTML.includes('<tbody><tr>'))throw Error('Default fixed-n empty: '+method);checked++;}
const receipt={offline_javascript_execution:'pass',rendered_default_tables:5,checked_control_conditions:checked,actual_browser_rendered:false,scope:'DOM control simulation and data population, separate from PNG visual inspection'};fs.writeFileSync(path.join(base,'audit/WORKBENCH_RUNTIME_CHECK.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
