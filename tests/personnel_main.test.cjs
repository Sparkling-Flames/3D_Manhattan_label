// Exercise the saved-data render and change handlers without a browser or network.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.join(__dirname,'../research/statistics/research_explorer_v1_r2_20261017');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const index=read(path.join(page,'v2-data/index.json'));
const context={window:{}};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(page,'personnel-main.js'),'utf8'),context);
class Element {
 constructor(tag='div'){this.tag=tag;this.value='';this.listeners={};this.textContent='';}
 set innerHTML(html){this.html=html;if(this.tag==='select')this.value=html.match(/<option value="([^"]*)"/)?.[1]??'';}
 get innerHTML(){return this.html||'';}
 addEventListener(type,fn){this.listeners[type]=fn;}
 change(value){this.value=value;this.listeners.change();}
}
class Host extends Element {
 set innerHTML(html){this.html=html;this.nodes=new Map();for(const m of html.matchAll(/<(select|div|p|tbody)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);if(m[1]==='select')e.innerHTML=html.slice(m.index+m[0].length).split('</select>')[0];this.nodes.set('#'+m[2],e);}}
 get innerHTML(){return this.html;}
 querySelector(id){assert(this.nodes.has(id),'missing element '+id);return this.nodes.get(id);}
 querySelectorAll(ids){return ids.split(',').map(id=>this.querySelector(id));}
}
const loaded=new Set();
async function table(id){loaded.add(id);const meta=index.tables.find(t=>t.id===id);assert(meta,'missing table '+id);return meta.parts.flatMap(p=>{const d=read(path.join(page,'v2-data',p.path));return d.rows.map(row=>Object.fromEntries(d.columns.map((k,i)=>[k,row[i]])));});}
async function render(tab){const host=new Host();await context.window.PersonnelMain.render(host,{release:'v2',index,tab,table,hintButton:()=>'',isCurrent:()=>true});return host;}
(async()=>{
 let host=await render(0);
 assert.equal((host.innerHTML.match(/data-scheme=/g)||[]).length,4);
 assert(host.innerHTML.indexOf('id="classificationQuestions"')<host.innerHTML.indexOf('id="personCondition"'));
 assert.match(host.innerHTML,/24\/27图/);assert.match(host.querySelector('#personCount').textContent,/248 \/ 248/);
 host.querySelector('#personCondition').change('semi');assert.match(host.querySelector('#personCount').textContent,/124 \/ 248/);
 host=await render(1);assert.match(host.innerHTML,/13,406/);assert.match(host.innerHTML,/全部79格/);
 host.querySelector('#mixtureExample').change('semi_failure');assert.match(host.querySelector('#mixtureDetails').innerHTML,/205队失败/);
 host=await render(2);assert.equal(host.querySelector('#ordinaryExchange').value,'S01');
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
 for(const tab of [0,1])allHTML.push((await render(tab)).innerHTML);
 for(const id of allHTML.join('').matchAll(/data-table-jump="([^"]+)"/g))assert(index.tables.some(t=>t.id===id[1]),id[1]);
 console.log('PASS: four schemes, all-source links, ordinary-before-same-room, all 18 conditions, Manual/Semi, m6, failure and difficulty denominators');
})().catch(e=>{console.error(e);process.exitCode=1;});
