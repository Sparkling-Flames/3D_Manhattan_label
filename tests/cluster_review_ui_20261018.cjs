// Controller checks without browser, network, or rendering; geometry renderer is separately reused.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.value='';this.checked=false;this.classList={toggle(){}};this.textContent='';}
 append(...xs){this.children.push(...xs);if(this.tag==='select'&&this.value===''&&xs.length)this.value=String(xs[0].value);}
 replaceChildren(...xs){this.children=[];if(this.tag==='select')this.value='';this.append(...xs);}
 querySelectorAll(){return this.children;}
}
const els={};for(const id of ['image','cut','filter','case','verdict'])els[id]=new Element('select');els.cut.value='9';els.filter.value='disagree';
const context={console,setTimeout,Blob,URL,document:{getElementById:id=>els[id]??=new Element(),createElement:tag=>new Element(tag)},WorkbenchGeometry:{mount(){}},ClusterOverlay:{mount(host,image,layers){host.layers=layers;}}};context.window=context;vm.createContext(context);
const base='research/statistics/research_explorer_v1_r2_20261017/';
for(const f of ['cluster-review-data.js','cluster-review.js'])vm.runInContext(fs.readFileSync(base+f,'utf8'),context);
assert.equal(els.image.children.length,8);
for(let i=0;i<8;i++)for(const cut of [6,9,12]){
 els.image.value=String(i);els.cut.value=String(cut);els.image.onchange();
 const image=context.CLUSTER_REVIEW.images[i],state=image.states.find(s=>s.cut===cut);
 for(const method of ['complete','affinity']){const cards=els[method+'-stacks'].children;assert.equal(cards.length,state.groups[method].length+1);assert.equal(cards[0].layers.flatMap(l=>l.members).length,image.records.length);state.groups[method].forEach((g,k)=>assert.deepEqual(Array.from(cards[k+1].children[1].layers.flatMap(l=>l.members)),Array.from(g)));}
 for(const method of ['complete','affinity'])for(let k=0;k<state.groups[method].length;k++){
  els[method].children[k].onclick();assert.equal(els.members.children.length,state.groups[method][k].length);
 }
 for(const filter of ['disagree','cut','boundary','count','all']){els.filter.value=filter;els.filter.onchange();if(filter==='all')assert.equal(els.case.children.length,image.records.length*(image.records.length-1)/2);}
 els['group-comment'].value='C1需核查';els['save-group'].onclick();assert.match(els['group-saved'].textContent,/已保存/);
 els.verdict.value='应分簇';els.comment.value='测试';els.save.onclick();assert.match(els.saved.textContent,/已保存/);
}
console.log('24 configurations: all cluster members, five case filters and review saving passed; no visual rendering checked.');

vm.runInContext(fs.readFileSync(base+'cluster-overlay.js','utf8'),context);
const markup=context.ClusterOverlay.marks([[10,20],[30,40]],'#fff');assert.equal((markup.match(/<circle /g)||[]).length,2);assert.ok(markup.includes('cx="10" cy="20"'));assert.ok(markup.includes('cx="30" cy="40"'));
console.log('Both methods: every cluster overlay contains all original members; overview covers whole pool; group feedback and original point coordinates checked.');
